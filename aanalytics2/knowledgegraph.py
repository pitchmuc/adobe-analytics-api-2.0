import time, datetime
import logging
from concurrent import futures
from pathlib import Path
from tkinter import NO
from aanalytics2 import WorkspaceManager, Login
from rdflib.namespace import RDF, RDFS, XSD
from rdflib import Graph, Namespace, Literal, URIRef, BNode
from collections import Counter
from requests.exceptions import ConnectionError, Timeout
import pandas as pd

logger = logging.getLogger(__name__)

class KnowledgeGraph:
    """
    Build a Knowledge Graph based on your Adobe Analytics data. 
    This class instantiates a connection to your Adobe Analytics implementation and draw relationships between your 
    dimensions, metrics, and segments. 
    It uses the Workspace Manager to understand their relationships and which ones are mostly used together and in which context for your report.
    It can be used to visualize the relationships between different elements of your analytics data, helping you to better understand how they interact with each other.
    """

    def __init__(self, config: dict = None, companyId: str = None, rsids: list|str = None, filterDims: bool = True,**kwargs):
        """
        Initialize the KnowledgeGraph class.
        Arguments: 
            config : OPTIONAL : The config dictionary returned when using the return_object parameter. 
            companyId : OPTIONAL : The company ID to use for building the knowledge graph. If not provided, the first company ID returned will be used.
            rsids : OPTIONAL : The report suite ID to use for the knowledge graph or a list of reportSuite ID.
                    Possible options is "all" is used and all report suites will be used. 
                    If not provided, the most commonly used report suite ID will be used.
            filterDims : OPTIONAL : A boolean to filter out the exit and entry dimensions from the knowledge graph, as well as keeping only oberon reportable dimensions. (bool : default True)
        The proxy is inherited from the configuration for all requests.
        """
        self.config = config
        self.rsids = None
        self.login = Login(config=self.config)
        self.projects = []
        self.dimensions = {}
        self.metrics = {}
        self.marketingChannels = {}
        companyIds = self.login.getCompanyId()
        if len(companyIds) == 0:
            raise ValueError("No company IDs found in the config. Please check if you have the correct access to Adobe Analytics API.")
        if companyId is None:
            self.companyId = companyIds[0]['globalCompanyId']
        else:
            self.companyId = [c['globalCompanyId'] for c in companyIds if c['globalCompanyId'] == companyId][0]
        self.analyticsAPI = self.login.createAnalyticsConnection(companyId=self.companyId)
        self.reportSuites:pd.DataFrame = self.analyticsAPI.getReportSuites(extended_info=True)
        if rsids is None:
            self.projects = self.analyticsAPI.getProjects(format='raw')
            rsids = [p.get('rsid') for p in self.projects if 'rsid' in p and 'vrs' not in p.get('rsid')]
            counter_rsid = Counter(rsids)
            self.rsids = [counter_rsid.most_common(1)[0][0]] ## [('rsid_a', 3)]
        elif rsids == "all":
            rsids:pd.DataFrame = self.analyticsAPI.getReportSuites()
            self.rsids = rsids[rsids.rsid.str.contains('vrs') == False].rsid.tolist()
        elif isinstance(rsids, str):
            self.rsids = [rsids]
        elif isinstance(rsids, list):
            self.rsids = rsids
        def fetch_rsid_data(rsid):
            dimensions = self.analyticsAPI.getDimensions(rsid=rsid,format='raw')
            if filterDims:
                dimensions = [d for d in dimensions if '/entry' not in d['id'] and '/exit' not in d['id'] and 'oberon' in d['reportable']]
            metrics = self.analyticsAPI.getMetrics(rsid=rsid,format='raw')
            marketingChannels = self.analyticsAPI.getMarketingChannels(rsid=rsid)
            return rsid, dimensions, metrics, marketingChannels
        with futures.ThreadPoolExecutor(max_workers=10) as executor:
            for rsid, dimensions, metrics, marketingChannels in executor.map(fetch_rsid_data, self.rsids):
                self.dimensions[rsid] = dimensions
                self.metrics[rsid] = metrics
                self.marketingChannels[rsid] = marketingChannels
        self.segments = self.analyticsAPI.getSegments(extended_info=True,format='raw')
        self._segmentsById = {segment['id']: segment for segment in self.segments}
        self.calculatedMetrics = self.analyticsAPI.getCalculatedMetrics(extended_info=True,format='raw')
        self.dateRanges = self.analyticsAPI.getDateRanges(extended_info=True,format='raw')
        if len(self.projects) == 0:
            self.projects = self.analyticsAPI.getProjects(format='raw')
        self.annotations = self.analyticsAPI.getAnnotations()
        self.namespaces = {
            "calculatedMetrics" : Namespace(f"http://analytics.com/{self.companyId}/calculatedMetric#"),
            "segments" : Namespace(f"http://analytics.com/{self.companyId}/segment#"),
            "marketingChannels" : Namespace(f"http://analytics.com/{self.companyId}/marketingChannel#"),
            "projects" : Namespace(f"http://analytics.com/{self.companyId}/projects#"),
            "reportSuites": Namespace(f"http://analytics.com/{self.companyId}/reportSuite#"),
            "dimensions" : Namespace(f"http://analytics.com/{self.companyId}/dimension#"),
            "metrics" : Namespace(f"http://analytics.com/{self.companyId}/metric#"),
            "dateRange": Namespace(f"http://analytics.com/{self.companyId}/dateRange#"),
            "usage": Namespace(f"http://analytics.com/{self.companyId}/usage#")
            #"annotation": Namespace(f"http://analytics.com/{self.companyId}/annotation#") ## tbd
        }
        for rsid in self.rsids:
            self.namespaces[f"{rsid}/dimensions"] = Namespace(f"http://analytics.com/{self.companyId}/{rsid}/dimension#")
            self.namespaces[f"{rsid}/metrics"] = Namespace(f"http://analytics.com/{self.companyId}/{rsid}/metric#")
        self.project_details = []
        self.graph: Graph = Graph()
        self.entity_usage: dict[URIRef, dict[str, int]] | None = {}
        self.dim_metric_cooccurrence: dict[tuple[URIRef, URIRef, URIRef], int] | None = {}
        self.dim_segment_cooccurrence: dict[tuple[URIRef, URIRef, URIRef], int] | None = {}

    @staticmethod
    def _normalize_dimension_id(dimension_id: str) -> str:
        """Remove a specific dimension item value from a dimension ID."""
        return dimension_id.partition("::")[0]

    def loadGraph(self, filename: str | Path, merge: bool = False) -> Graph:
        """
        Load a local Turtle file into the knowledge graph.
        Arguments:
            filename : REQUIRED : The path to the Turtle file (str or pathlib.Path).
            merge : OPTIONAL : Retain existing triples and add the loaded graph (bool : default False).
                    By default, replace the current graph and counter state with the loaded snapshot.
        Returns the loaded or merged rdflib.Graph, also stored on self.graph.
        File and parsing errors propagate without changing the current graph.
        Counter dictionaries are restored from the loaded graph. Conflicting counters in an
        explicitly merged graph are logged, and the counter attributes are set to None.
        """
        graph = Graph()
        with Path(filename).open("rb") as source:
            graph.parse(source=source, format="turtle")
        if merge:
            self.graph += graph
            for prefix, namespace in graph.namespaces():
                self.graph.bind(prefix, namespace)
        else:
            self.graph = graph
        self._sync_graph_counters()
        return self.graph

    def _read_graph_count(self, subject: URIRef | BNode, predicate: URIRef) -> int:
        values = list(self.graph.objects(subject, predicate))
        if len(values) != 1:
            raise ValueError(
                f"Expected exactly one count for {subject} / {predicate}. "
                "Use buildGraph(merge=False) to create a clean snapshot."
            )
        value = values[0]
        count = value.toPython() if isinstance(value, Literal) else None
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise ValueError(f"Expected a non-negative integer count for {subject} / {predicate}.")
        return count

    def getUsageCounts(self) -> dict[URIRef, dict[str, int]]:
        """
        Return a fresh Python dictionary of the graph's usage counters, keyed by entity URI.
        Each value maps the stored segmentUsage, metricUsage and projectUsage fields to integers.
        Missing fields are omitted and count as zero during incremental builds.
        Editing this snapshot does not change the graph. Invalid or conflicting counts raise ValueError.
        """
        counts: dict[URIRef, dict[str, int]] = {}
        for field in ("segmentUsage", "metricUsage", "projectUsage"):
            predicate = self.namespaces["usage"][field]
            for ref in set(self.graph.subjects(predicate=predicate)):
                if not isinstance(ref, URIRef):
                    raise ValueError(f"Expected an entity URI for usage counter {ref} / {predicate}.")
                counts.setdefault(ref, {})[field] = self._read_graph_count(ref, predicate)
        return counts

    def _get_cooccurrence_counts(
        self, node_type: str, component_field: str,
    ) -> dict[tuple[URIRef, URIRef, URIRef], tuple[URIRef | BNode, int]]:
        counts: dict[tuple[URIRef, URIRef, URIRef], tuple[URIRef | BNode, int]] = {}
        usage = self.namespaces["usage"]
        for node in self.graph.subjects(RDF.type, Literal(node_type)):
            if not isinstance(node, (URIRef, BNode)):
                raise ValueError(f"Invalid co-occurrence node: {node}.")
            references: list[URIRef] = []
            for field in ("dimension", component_field, "rsid"):
                values = list(self.graph.objects(node, usage[field]))
                if len(values) != 1 or not isinstance(values[0], URIRef):
                    raise ValueError(f"Expected exactly one {field} URI for co-occurrence node {node}.")
                references.append(values[0])
            key = (references[0], references[1], references[2])
            if key in counts:
                raise ValueError(
                    f"Duplicate {node_type} records for {key}. "
                    "Use buildGraph(merge=False) to create a clean snapshot."
                )
            counts[key] = (node, self._read_graph_count(node, usage.cooccurrenceCount))
        return counts

    def _sync_graph_counters(self) -> None:
        try:
            entity_usage = self.getUsageCounts()
            metric_counts = self._get_cooccurrence_counts("MetricCooccurrence", "metric")
            segment_counts = self._get_cooccurrence_counts("SegmentCooccurrence", "segment")
        except ValueError as error:
            self.entity_usage = None
            self.dim_metric_cooccurrence = None
            self.dim_segment_cooccurrence = None
            logger.warning(
                "Graph retained, but its counters cannot be initialized: %s "
                "Incremental builds require unambiguous counters.",
                error,
            )
            return
        self.entity_usage = entity_usage
        self.dim_metric_cooccurrence = {key: count for key, (_, count) in metric_counts.items()}
        self.dim_segment_cooccurrence = {key: count for key, (_, count) in segment_counts.items()}

    def _clear_graph_counters(self) -> None:
        usage = self.namespaces["usage"]
        for node_type in ("MetricCooccurrence", "SegmentCooccurrence"):
            for node in set(self.graph.subjects(RDF.type, Literal(node_type))):
                self.graph.remove((node, None, None))
        for field in (
            "segmentUsage", "metricUsage", "projectUsage", "usedWithMetric",
            "usedWithSegment", "usedWithDimension",
        ):
            self.graph.remove((None, usage[field], None))
        # Only registered projects contributed to the current counter snapshot.
        projects = self.namespaces["projects"]
        self.graph.remove((URIRef(projects), projects.contains, None))

    def buildGraph(
        self, save: bool = False, filename: str = 'knowledge_graph.ttl',
        verbose: bool = False, merge: bool = True, incremental: bool = False, **kwargs,
    ) -> Graph:
        """
        Build the knowledge graph based on the dimensions, metrics, segments, and calculated metrics.
        The dimensions, metrics, segments, calculated metrics and projects are each built into their own
        sub-graph concurrently (threads, since the work is I/O-bound on Adobe Analytics API calls rather
        than CPU-bound) and then merged together at the end.
        By default, existing component metadata (including that loaded with loadGraph) is retained.
        A full build replaces generated usage/co-occurrence counters and project registrations
        with a snapshot computed from the current Analytics data and loaded projects.
        With incremental=True, only projects absent from the existing graph are processed.
        Stored counters are read into Python dictionaries, incremented and replaced in the graph.
        Network failures during component scans are logged as warnings. The component metadata is
        retained, but usage counts from the failed scan are omitted.
        Arguments:
            save : OPTIONAL : If set to True, it will save the knowledge graph in a ttl file (bool : default False)
            filename : OPTIONAL : The filename to save the knowledge graph (str : default 'knowledge_graph.ttl')
            verbose : OPTIONAL : Adding print statement during the building of the graph.
            merge : OPTIONAL : Retain existing metadata when building (bool : default True).
                    If False, discard the current graph and build a fresh one.
            incremental : OPTIONAL : Reuse the existing component graph and add only new projects
                    (bool : default False). Requires a non-empty graph and merge=True.
                    Existing project IDs are skipped, even if their definitions have changed.
                    Invalid or ambiguous saved counters raise ValueError before adding projects.
        Possible kwargs:
            calculatedMetricWorkers : number of threads used to concurrently scan calculated metrics for their
                    referenced segments/metrics, which involves live API calls (int : default 10)
        """
        if incremental and not merge:
            raise ValueError("Incremental builds require merge=True.")
        if incremental and len(self.graph) == 0:
            raise ValueError("Incremental builds require an existing graph; load or build one first.")
        dict_entity_usage = self.getUsageCounts() if incremental else {}
        metric_cooccurrence_counts = self._get_cooccurrence_counts("MetricCooccurrence", "metric") if incremental else {}
        segment_cooccurrence_counts = self._get_cooccurrence_counts("SegmentCooccurrence", "segment") if incremental else {}
        if not merge:
            self.graph = Graph()
        self.graph.bind("companyId", Namespace(f"http://analytics.com/{self.companyId}/"))
        if verbose:
            print("creating main entities")
        for rsid in self.rsids:
            self.graph.bind("dimension", self.namespaces[f"{rsid}/dimensions"])
            self.graph.bind("metric", self.namespaces[f"{rsid}/metrics"])
        self.graph.bind("segment", self.namespaces["segments"])
        self.graph.bind("calculatedMetric", self.namespaces["calculatedMetrics"])
        self.graph.bind("marketingChannel", self.namespaces["marketingChannels"])
        self.graph.bind("projects", self.namespaces["projects"])
        self.graph.bind("reportSuites",self.namespaces["reportSuites"])
        dim_metric_cooccurrence = {}
        dim_segment_cooccurrence = {}
        def bump_usage(store, ref, field):
            entry = store.setdefault(ref, {'segmentUsage': 0, 'projectUsage': 0, 'metricUsage': 0})
            entry[field] += 1
        def bump_cooccurrence(store, ref_a, ref_b, rsid):
            entry = store.setdefault((ref_a, ref_b), {'count': 0, 'rsid': rsid})
            entry['count'] += 1
        def merge_usage(target, source):
            for ref, usage in source.items():
                entry = target.setdefault(ref, {'segmentUsage': 0, 'projectUsage': 0, 'metricUsage': 0})
                for key, value in usage.items():
                    entry[key] = entry.get(key, 0) + value
        def add_reportsuite_base(graph, rsid):
            if rsid in self.reportSuites.rsid.tolist():
                row = self.reportSuites[self.reportSuites.rsid == rsid].iloc[0]
                graph.add((self.namespaces['reportSuites'][rsid], RDF.type, Literal("ReportSuite")))
                graph.add((self.namespaces['reportSuites'][rsid], RDFS.label, Literal(row['name'],datatype=XSD.string)))
                graph.add((self.namespaces['reportSuites'][rsid], self.namespaces['reportSuites'].id, Literal(row['rsid'],datatype=XSD.string)))
                graph.add((self.namespaces['reportSuites'][rsid], self.namespaces['reportSuites'].currency, Literal(row['currency'])))
        def build_dimension_graph(graph, dimension,rsid):
            dimension_id = self._normalize_dimension_id(dimension['id'])
            dimension_uri = URIRef(f"http://analytics.com/{self.companyId}/{rsid}/dimension/{dimension_id}")
            graph.add((dimension_uri, RDF.type, Literal("Dimension")))
            graph.add((dimension_uri, self.namespaces['dimensions'].dataType, Literal(dimension['type'])))
            graph.add((dimension_uri, RDFS.label, Literal(dimension['name'])))
            if '.' in dimension_id:
                graph.add((dimension_uri, self.namespaces['dimensions'].classification, Literal(True,datatype=XSD.boolean)))
                parentRef = URIRef(f"http://analytics.com/{self.companyId}/{rsid}/dimension/{dimension_id.split('.')[0]}")
                graph.add((dimension_uri, self.namespaces['dimensions'].parent_dimension, parentRef))
                graph.add((parentRef, self.namespaces['dimensions'].children_dimension, dimension_uri))
            else:
                graph.add((dimension_uri, self.namespaces['dimensions'].classification, Literal(False,datatype=XSD.boolean)))
            graph.add((dimension_uri, self.namespaces['dimensions'].id, Literal(dimension_id)))
            if 'description' in dimension:
                graph.add((dimension_uri, RDFS.comment, Literal(dimension['description'])))
            for reportable in dimension['reportable']:
                graph.add((dimension_uri, self.namespaces['dimensions'].reportable, Literal(reportable)))
            graph.add((dimension_uri, self.namespaces['dimensions'].segmentable,Literal(dimension['segmentable'],datatype=XSD.boolean)))
            graph.add((dimension_uri, self.namespaces['dimensions'].rsid, self.namespaces['reportSuites'][rsid]))
            graph.add((self.namespaces['reportSuites'][rsid], self.namespaces['reportSuites'].dimensions,dimension_uri))
        def build_metric_graph(graph, metric,rsid):
            metric_uri = URIRef(f"http://analytics.com/{self.companyId}/{rsid}/metric/{metric['id']}")
            graph.add((metric_uri, RDF.type, Literal("Metric")))
            graph.add((metric_uri, RDFS.label, Literal(metric['name'])))
            graph.add((metric_uri, self.namespaces['metrics'].id, Literal(metric['id'])))
            graph.add((metric_uri, self.namespaces['metrics'].type, Literal(metric['type'])))
            for reportable in metric['support']:
                graph.add((metric_uri, self.namespaces['metrics'].reportable, Literal(reportable)))
            if 'description' in metric:
                graph.add((metric_uri, RDFS.comment, Literal(metric['description'])))
            graph.add((metric_uri, self.namespaces['metrics'].segmentable,Literal(metric['segmentable'],datatype=XSD.boolean)))
            graph.add((metric_uri, self.namespaces['metrics'].polarity,Literal(metric['polarity'],datatype=XSD.string)))
            graph.add((metric_uri, self.namespaces['metrics'].rsid, self.namespaces['reportSuites'][rsid]))
            graph.add((self.namespaces['reportSuites'][rsid], self.namespaces['reportSuites'].metrics,metric_uri))
        def build_marketing_channel_graph(graph, rsid):
            marketing_channel = URIRef(f"http://analytics.com/{self.companyId}/{rsid}/marketingChannel/")
            graph.add((marketing_channel, RDF.type, Literal("MarketingChannels")))
            mymarketingchannel = self.marketingChannels[rsid]
            for channel in mymarketingchannel['marketingChannels']:
                marketing_channel_uri = URIRef(f"http://analytics.com/{self.companyId}/{rsid}/marketingChannel/{channel['channelId']}")
                graph.add((marketing_channel_uri, RDF.type, Literal("MarketingChannel")))
                graph.add((marketing_channel_uri, RDFS.label, Literal(channel['name'])))
                graph.add((marketing_channel_uri, self.namespaces['marketingChannels'].id, Literal(channel['channelId'])))
                graph.add((marketing_channel_uri, self.namespaces['marketingChannels'].rsid, self.namespaces['reportSuites'][rsid]))
                graph.add((self.namespaces['reportSuites'][rsid], self.namespaces['reportSuites'].marketingChannels,marketing_channel_uri))
                graph.add((marketing_channel, self.namespaces['marketingChannels'].defines,marketing_channel_uri ))
                if channel.get('position') is not None:
                    graph.add((marketing_channel_uri, self.namespaces['marketingChannels'].position, Literal(channel['position'],datatype=XSD.integer)))
                graph.add((marketing_channel_uri, self.namespaces['marketingChannels'].override, Literal(channel['overrideLastTouchChannel'],datatype=XSD.boolean)))
                graph.add((marketing_channel_uri, self.namespaces['marketingChannels'].enabled, Literal(channel['enabled'],datatype=XSD.boolean)))
        def build_dimensions_task():
            graph = Graph()
            for rsid in self.rsids:
                add_reportsuite_base(graph, rsid)
                for dimension in self.dimensions[rsid]:
                    build_dimension_graph(graph, dimension, rsid)
            return graph
        def build_metrics_task():
            graph = Graph()
            for rsid in self.rsids:
                add_reportsuite_base(graph, rsid)
                for metric in self.metrics[rsid]:
                    build_metric_graph(graph, metric, rsid)
                build_marketing_channel_graph(graph, rsid)
            return graph
        def build_segment_graph(graph, usage, segment):
            segment_uri = URIRef(f"http://analytics.com/{self.companyId}/segment/{segment['id']}")
            graph.add((segment_uri, RDF.type, Literal("Segment")))
            graph.add((segment_uri, RDFS.label, Literal(segment['name'])))
            if 'description' in segment:
                graph.add((segment_uri, RDFS.comment, Literal(segment['description'])))
            graph.add((segment_uri, self.namespaces['segments'].id, Literal(segment['id'])))
            graph.add((segment_uri, self.namespaces['segments'].definition, Literal(segment['definition'])))
            graph.add((segment_uri, self.namespaces['segments'].rsid, self.namespaces['reportSuites'][segment['rsid']]))
            graph.add((self.namespaces['reportSuites'][segment['rsid']], self.namespaces['reportSuites'].segments,segment_uri))
            if segment.get('lastRecordedAccess') is not None and segment.get('lastRecordedAccess') != "":
                graph.add((segment_uri, self.namespaces['segments'].lastAccess, Literal(datetime.datetime.fromtimestamp(segment['lastRecordedAccess']/1000).isoformat().split(".")[0],datatype=XSD.dateTime)))
            for tag in segment['tags']:
                graph.add((segment_uri, self.namespaces['segments'].tag, Literal(tag['name'])))
            graph.add((segment_uri, self.namespaces['segments'].shares, Literal(len(segment.get('shares',[])),datatype=XSD.integer)))
            try:
                scannedSegment = self.analyticsAPI.scanSegment(segment)
            except (ConnectionError, Timeout) as error:
                logger.warning(
                    "Could not scan segment %s (%s); keeping its metadata, but skipping its usage counts.",
                    segment['id'], type(error).__name__,
                )
                return
            segRsid = scannedSegment['rsid']
            for dim in scannedSegment['dimensions']:
                dimension_id = self._normalize_dimension_id(dim)
                dimRef = URIRef(f"http://analytics.com/{self.companyId}/{segRsid}/dimension/{dimension_id}")
                bump_usage(usage, dimRef, 'segmentUsage')
            for met in scannedSegment['metrics']:
                metRef = URIRef(f"http://analytics.com/{self.companyId}/{segRsid}/metric/{met}")
                bump_usage(usage, metRef, 'segmentUsage')
            rsidRef = self.namespaces['reportSuites'][segRsid]
            bump_usage(usage, rsidRef, 'segmentUsage')
        def build_segments_task():
            graph = Graph()
            usage = {}
            for segment in self.segments:
                build_segment_graph(graph, usage, segment)
            return graph, usage
        def build_calculated_graph(graph, usage, calculated_metric, scannedMetric: dict | None):
            calculated_metric_uri = URIRef(f"http://analytics.com/{self.companyId}/calculatedMetric/{calculated_metric['id']}")
            graph.add((calculated_metric_uri, RDF.type, Literal("CalculatedMetric")))
            graph.add((calculated_metric_uri, RDFS.label, Literal(calculated_metric['name'])))
            if 'description' in calculated_metric:
                graph.add((calculated_metric_uri, RDFS.comment, Literal(calculated_metric['description'])))
            graph.add((calculated_metric_uri, self.namespaces['calculatedMetrics'].type, Literal(calculated_metric['type'])))
            graph.add((calculated_metric_uri, self.namespaces['calculatedMetrics'].id, Literal(calculated_metric['id'])))
            graph.add((calculated_metric_uri, self.namespaces['calculatedMetrics'].definition, Literal(calculated_metric['definition'])))
            graph.add((calculated_metric_uri, self.namespaces['calculatedMetrics'].rsid, self.namespaces['reportSuites'][calculated_metric['rsid']]))
            graph.add((self.namespaces['reportSuites'][calculated_metric['rsid']], self.namespaces['reportSuites'].calculatedMetrics,calculated_metric_uri))
            if calculated_metric.get('lastRecordedAccess') is not None and calculated_metric.get('lastRecordedAccess') != "":
                graph.add((calculated_metric_uri, self.namespaces['calculatedMetrics'].lastAccess, Literal(datetime.datetime.fromtimestamp(calculated_metric['lastRecordedAccess']/1000).isoformat().split(".")[0],datatype=XSD.dateTime)))
            graph.add((calculated_metric_uri, self.namespaces['calculatedMetrics'].shares, Literal(len(calculated_metric.get('shares',[])),datatype=XSD.integer)))
            graph.add((calculated_metric_uri, self.namespaces['calculatedMetrics'].polarity, Literal(calculated_metric.get('polarity','positive'),datatype=XSD.string)))
            for tag in calculated_metric.get('tags',[]):
                graph.add((calculated_metric_uri, self.namespaces['calculatedMetrics'].tag, Literal(tag['name'])))
            for reportable in calculated_metric['compatibility'].get('supported_products',[]):
                graph.add((calculated_metric_uri, self.namespaces['calculatedMetrics'].reportable, Literal(reportable)))
            if scannedMetric is None:
                return
            metRsid = scannedMetric['rsid']
            for metric in scannedMetric['metrics']:
                metRef = URIRef(f"http://analytics.com/{self.companyId}/{metRsid}/metric/{metric}")
                bump_usage(usage, metRef, 'metricUsage')
            rsidRef = self.namespaces['reportSuites'][metRsid]
            bump_usage(usage, rsidRef, 'metricUsage')
        def build_calculated_metrics_task():
            graph = Graph()
            usage = {}
            workers = int(kwargs.get('calculatedMetricWorkers', 10))
            def scan(calculated_metric: dict) -> tuple[dict, dict | None]:
                try:
                    scanned_metric = self.analyticsAPI.scanCalculatedMetric(
                        calculated_metric, knownSegments=self._segmentsById,
                    )
                except (ConnectionError, Timeout) as error:
                    logger.warning(
                        "Could not scan calculated metric %s (%s); keeping its metadata, but skipping its usage counts.",
                        calculated_metric['id'], type(error).__name__,
                    )
                    return calculated_metric, None
                return calculated_metric, scanned_metric
            # passing knownSegments lets scanCalculatedMetric resolve referenced segments from data
            # already fetched in __init__, avoiding a getSegment API call per reference; the thread
            # pool remains as a safety net for any referenced segment not present in self._segmentsById.
            with futures.ThreadPoolExecutor(max_workers=workers) as executor:
                scanned_results = list(executor.map(scan, self.calculatedMetrics))
            for calculated_metric, scannedMetric in scanned_results:
                build_calculated_graph(graph, usage, calculated_metric, scannedMetric)
            return graph, usage
        def register_element_components(graph, usage, dim_metric_cooc, dim_segment_cooc, element, project_ref, rsid):
            dimRefs, metricRefs, segRefs = [], [], []
            for dimension in element.dimensions:
                dimension_id = self._normalize_dimension_id(dimension['id'])
                dimRef = URIRef(f"http://analytics.com/{self.companyId}/{rsid}/dimension/{dimension_id}")
                graph.add((dimRef, self.namespaces['projects'].dimension_ref,project_ref))
                bump_usage(usage, dimRef, 'projectUsage')
                dimRefs.append(dimRef)
            for metric in element.metrics:
                metRef = URIRef(f"http://analytics.com/{self.companyId}/{rsid}/metric/{metric['id']}")
                graph.add((metRef, self.namespaces['projects'].metric_ref,project_ref))
                bump_usage(usage, metRef, 'projectUsage')
                metricRefs.append(metRef)
            for calc in element.calculatedMetrics:
                calcRef = URIRef(f"http://analytics.com/{self.companyId}/calculatedMetric/{calc['id']}")
                graph.add((calcRef, self.namespaces['projects'].calculated_ref,project_ref))
                bump_usage(usage, calcRef, 'projectUsage')
                metricRefs.append(calcRef)
            for segment in element.segments:
                segRef = URIRef(f"http://analytics.com/{self.companyId}/segment/{segment['id']}")
                bump_usage(usage, segRef, 'projectUsage')
                segRefs.append(segRef)
            for dimRef in dimRefs:
                for metRef in metricRefs:
                    bump_cooccurrence(dim_metric_cooc, dimRef, metRef, rsid)
                for segRef in segRefs:
                    bump_cooccurrence(dim_segment_cooc, dimRef, segRef, rsid)
        def build_project_graph(graph, usage, dim_metric_cooc, dim_segment_cooc, project_detail):
            Wproject = project_detail
            project_ref = URIRef(f"http://analytics.com/{self.companyId}/projects/{Wproject.id}")
            graph.add((URIRef(self.namespaces['projects']), self.namespaces['projects'].contains,project_ref))
            rsidRef = self.namespaces['reportSuites'][Wproject.rsid]
            graph.add((project_ref, self.namespaces['projects'].rsid,rsidRef))
            bump_usage(usage, rsidRef, 'projectUsage')
            graph.add((project_ref, RDFS.label,Literal(Wproject.name)))
            graph.add((project_ref, RDF.type,Literal("Workspace")))
            graph.add((project_ref, self.namespaces['projects'].description,Literal(Wproject.description)))
            if Wproject.created is not None and Wproject.created != "":
                graph.add((project_ref, self.namespaces['projects'].created,Literal(Wproject.created,datatype=XSD.dateTime)))
            for panel in Wproject.panels:
                for element in panel.elements:
                    if element.type == "Text":
                        graph.add((project_ref, self.namespaces['projects'].text,Literal(element.name,datatype=XSD.string)))
                        if element.text is not None and element.text != "":
                            graph.add((project_ref, self.namespaces['projects'].text,Literal(element.text,datatype=XSD.string)))
                    elif element.type == "Visualization":
                        graph.add((project_ref, self.namespaces['projects'].visualition,Literal(element.name,datatype=XSD.string)))
                        register_element_components(graph, usage, dim_metric_cooc, dim_segment_cooc, element, project_ref, Wproject.rsid)
                    elif element.type == "FreeForm":
                        freeformText = f"{element.name}"
                        if element.description != "":
                            freeformText += f": {element.description}"
                        graph.add((project_ref, self.namespaces['projects'].panelFreeForm,Literal(freeformText,datatype=XSD.string)))
                        register_element_components(graph, usage, dim_metric_cooc, dim_segment_cooc, element, project_ref, Wproject.rsid)
        def build_projects_task():
            graph = Graph()
            usage = {}
            local_dim_metric_cooc = {}
            local_dim_segment_cooc = {}
            projects = self.namespaces["projects"]
            seen_projects = set(self.graph.objects(URIRef(projects), projects.contains)) if incremental else set()
            for proj in self.project_details:
                project_ref = URIRef(f"http://analytics.com/{self.companyId}/projects/{proj.id}")
                if incremental and project_ref in seen_projects:
                    continue
                build_project_graph(graph, usage, local_dim_metric_cooc, local_dim_segment_cooc, proj)
                seen_projects.add(project_ref)
            return graph, usage, local_dim_metric_cooc, local_dim_segment_cooc
        if incremental:
            if verbose:
                print("building new projects using the existing component graph")
            projects_graph, projects_usage, dim_metric_cooccurrence, dim_segment_cooccurrence = build_projects_task()
            self.graph += projects_graph
            new_usage_entities = projects_usage.keys() - dict_entity_usage.keys()
            merge_usage(dict_entity_usage, projects_usage)
            for ref in projects_usage:
                for field, value in dict_entity_usage[ref].items():
                    if field == 'projectUsage' or ref in new_usage_entities:
                        self.graph.set((
                            ref, self.namespaces['usage'][field],
                            Literal(value, datatype=XSD.integer),
                        ))
        else:
            if verbose:
                print("building dimensions, metrics, segments, calculated metrics and projects concurrently")
            with futures.ThreadPoolExecutor(max_workers=5) as executor:
                future_dimensions = executor.submit(build_dimensions_task)
                future_metrics = executor.submit(build_metrics_task)
                future_segments = executor.submit(build_segments_task)
                future_calculated = executor.submit(build_calculated_metrics_task)
                future_projects = executor.submit(build_projects_task)
                dimensions_graph = future_dimensions.result()
                metrics_graph = future_metrics.result()
                segments_graph, segments_usage = future_segments.result()
                calculated_graph, calculated_usage = future_calculated.result()
                projects_graph, projects_usage, dim_metric_cooccurrence, dim_segment_cooccurrence = future_projects.result()
            if verbose:
                print("merging sub-graphs")
            self._clear_graph_counters()
            for subgraph in (dimensions_graph, metrics_graph, segments_graph, calculated_graph, projects_graph):
                self.graph += subgraph
            for usage_source in (segments_usage, calculated_usage, projects_usage):
                merge_usage(dict_entity_usage, usage_source)
            for daterange in self.dateRanges:
                drRef = URIRef(f"http://analytics.com/{self.companyId}/dateRange/{daterange['id']}")
                self.graph.add((drRef,RDF.type,Literal("DateRange")))
                self.graph.add((drRef,RDFS.label,Literal(daterange['name'])))
                self.graph.add((drRef,self.namespaces['dateRange'].id,Literal(daterange['id'])))
                self.graph.add((drRef,self.namespaces['dateRange'].description,Literal(daterange['description'])))
                self.graph.add((drRef,self.namespaces['dateRange'].definition,Literal(daterange['definition'])))
            for ref, usage in dict_entity_usage.items():
                for key, value in usage.items():
                    self.graph.add((ref, self.namespaces['usage'][key],Literal(value,datatype=XSD.integer)))
        for (dimRef, metRef), data in dim_metric_cooccurrence.items():
            self.graph.add((dimRef, self.namespaces['usage'].usedWithMetric, metRef))
            self.graph.add((metRef, self.namespaces['usage'].usedWithDimension, dimRef))
            rsid_ref = self.namespaces['reportSuites'][data['rsid']]
            node, previous_count = metric_cooccurrence_counts.get((dimRef, metRef, rsid_ref), (BNode(), 0))
            self.graph.add((node, RDF.type, Literal("MetricCooccurrence")))
            self.graph.add((node, self.namespaces['usage'].dimension, dimRef))
            self.graph.add((node, self.namespaces['usage'].metric, metRef))
            self.graph.set((node, self.namespaces['usage'].cooccurrenceCount, Literal(previous_count + data['count'],datatype=XSD.integer)))
            self.graph.add((node, self.namespaces['usage'].rsid, rsid_ref))
            metric_cooccurrence_counts[(dimRef, metRef, rsid_ref)] = (node, previous_count + data['count'])
        for (dimRef, segRef), data in dim_segment_cooccurrence.items():
            self.graph.add((dimRef, self.namespaces['usage'].usedWithSegment, segRef))
            self.graph.add((segRef, self.namespaces['usage'].usedWithDimension, dimRef))
            rsid_ref = self.namespaces['reportSuites'][data['rsid']]
            node, previous_count = segment_cooccurrence_counts.get((dimRef, segRef, rsid_ref), (BNode(), 0))
            self.graph.add((node, RDF.type, Literal("SegmentCooccurrence")))
            self.graph.add((node, self.namespaces['usage'].dimension, dimRef))
            self.graph.add((node, self.namespaces['usage'].segment, segRef))
            self.graph.set((node, self.namespaces['usage'].cooccurrenceCount, Literal(previous_count + data['count'],datatype=XSD.integer)))
            self.graph.add((node, self.namespaces['usage'].rsid, rsid_ref))
            segment_cooccurrence_counts[(dimRef, segRef, rsid_ref)] = (node, previous_count + data['count'])
        if incremental:
            self.entity_usage = dict_entity_usage
            self.dim_metric_cooccurrence = {key: count for key, (_, count) in metric_cooccurrence_counts.items()}
            self.dim_segment_cooccurrence = {key: count for key, (_, count) in segment_cooccurrence_counts.items()}
        else:
            self._sync_graph_counters()
        if save:
            turtle = self.graph.serialize(format="turtle")
            if filename is not None:
                if filename.endswith('.ttl') == False:
                    filename += '.ttl'
                Path(filename).write_text(turtle, encoding="utf-8")
        return self.graph

    def loadProjects(self, projects: list|int|str,sampleMethod:str='most_recent',**kwargs):
            """
            Load a list of projects to the knowledge graph. 
            This will allow you to build a knowledge graph based on the dimensions, metrics, segments, and calculated metrics used in those projects.
            It gives more context to the relationships between the different elements of your analytics data.
            Arguments:
                projects : A list of project IDs, a number of projects to load or a list of email addresses
                            If a number is provided it will used the sampleMethod to select the projects to load. 
                            if the string "all" is provided, it will used all projects. This is taking a large amount of time (list|int|str)
                sampleMethod : OPTIONAL : The method to use to select the projects to load if a number or a list of email is provided. (str : default 'most_recent', possible values "random")
                    - 'most_recent' : Load the most recent projects based on the last modified date.
                    - 'random' : Load a random sample of projects.
                    - 'users' : Load projects based on the user(s) who own them (requires a list of user email addresses)
            """
            def get_project_details(project):
                        project_id = project.get('id')
                        project_details = self.analyticsAPI.getProject(projectId=project_id)
                        return WorkspaceManager(project_details)
            if projects == "all":
                projects = self.projects
            elif isinstance(projects, int):
                if sampleMethod == 'most_recent':
                    projects = sorted(self.projects, key=lambda x: x.get('modified'), reverse=True)[:projects]
                elif sampleMethod == 'random':
                    import random
                    projects = random.sample(self.projects, projects)
                else:
                    raise ValueError("Invalid sampleMethod. Please use 'most_recent' or 'random'.")
            elif isinstance(projects, list):
                if sampleMethod == 'users':
                    filter_projects = []
                    for p in self.projects:
                        owner = p.get('owner',{}).get('login').lower()
                        for user in projects:
                            if user.lower() in owner:
                                filter_projects.append(p)
                                break
                    projects = filter_projects
                else:
                    projects = [p for p in self.projects if p.get('id') in projects]
            else:
                raise ValueError("Invalid projects argument. Please provide a list of project IDs or a number of projects to load.")
            with futures.ThreadPoolExecutor(max_workers=6) as executor:
                results = executor.map(get_project_details, projects)
                if self.project_details is None:
                    self.project_details = list(results)
                else:
                    self.project_details.extend(list(results))

    def exportGraph(self,filename:str = "knowledge_graph.ttl")->None:
        """
        Export the built or loaded Knowledge Graph in a turtle format.
        Arguments:
            filename : REQUIRED : The name of the turtle file
        """
        if filename is not None:
            if filename.endswith('.ttl') == False:
                filename += '.ttl'
            turtle = self.graph.serialize(format="turtle")
            Path(filename).write_text(turtle, encoding="utf-8")
        else:
            raise Exception("Require at least a filename")

    def query(self, sparql_string: str) -> list:
        """
        Run a SPARQL query against the graph built by buildGraph() or loaded by loadGraph() and return the results
        as a list of dictionaries (one per row) instead of raw rdflib Result objects.
        Arguments:
            sparql_string : REQUIRED : The SPARQL query to execute.
        """
        results = self.graph.query(sparql_string)
        return [
            {str(var): (row[var].toPython() if row[var] is not None else None) for var in results.vars}
            for row in results
        ]

    def addProjectAttribute(self,ProjectId: str, attribute: str, value: str) -> None:
        """
        Add an attribute to a project in the knowledge graph.
        Arguments:
            ProjectId : REQUIRED : The ID of the project to update.
            attribute : REQUIRED : The attribute to add to the project.
            value : REQUIRED : The value of the attribute to add.
        """
        project_node = None
        for s, p, o in self.graph.triples((None, self.namespaces['project'].projectId, Literal(ProjectId))):
            project_node = s
            break
        if project_node is None:
            raise Exception(f"Project with ID {ProjectId} not found in the graph.")
        self.graph.add((project_node, self.namespaces['project'][attribute], Literal(value)))

    def addSegmentAttribute(self,SegmentId:str, attribute:str, value:str) -> None: 
        """
        Add an attribute to a segment in the knowledge graph.
        Arguments:
            SegmentId : REQUIRED : The ID of the segment to update.
            attribute : REQUIRED : The attribute to add to the segment.
            value : REQUIRED : The value of the attribute to add.
        """
        segment_node = None
        for s, p, o in self.graph.triples((None, self.namespaces['segment'].segmentId, Literal(SegmentId))):
            segment_node = s
            break
        if segment_node is None:
            raise Exception(f"Segment with ID {SegmentId} not found in the graph.")
        self.graph.add((segment_node, self.namespaces['segment'][attribute], Literal(value)))

    def addCalculatedAttribute(self,metricId:str, attribute:str, value:str) -> None:
        """
        Add a calculated attribute to a metric in the knowledge graph.
        Arguments:
            metricId : REQUIRED : The ID of the metric to update.
            attribute : REQUIRED : The attribute to add to the metric.
            value : REQUIRED : The value of the attribute to add.
        """
        metric_node = None
        for s, p, o in self.graph.triples((None, self.namespaces['metric'].metricId, Literal(metricId))):
            metric_node = s
            break
        if metric_node is None:
            raise Exception(f"Metric with ID {metricId} not found in the graph.")
        self.graph.add((metric_node, self.namespaces['metric'][attribute], Literal(value)))