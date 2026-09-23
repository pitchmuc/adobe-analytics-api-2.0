import time, datetime
from concurrent import futures
from pathlib import Path
from tkinter import NO
from aanalytics2 import WorkspaceManager, Analytics, Login
from rdflib.namespace import RDF, RDFS, XSD
from rdflib import Graph, Namespace, Literal, URIRef, BNode
from collections import Counter
import pandas as pd

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
        self.analyticsAPI = Analytics(config=self.config, company_id=self.companyId)
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

    @staticmethod
    def _normalize_dimension_id(dimension_id: str) -> str:
        """Remove a specific dimension item value from a dimension ID."""
        return dimension_id.partition("::")[0]

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
        self.project_details = []
        def get_project_details(project):
                    project_id = project.get('id')
                    project_details = self.analyticsAPI.getProject(projectId=project_id)
                    return WorkspaceManager(project_details)
        if projects == "all":
            self.projects = self.projects
        elif isinstance(projects, int):
            if sampleMethod == 'most_recent':
                self.projects = sorted(self.projects, key=lambda x: x.get('modified'), reverse=True)[:projects]
            elif sampleMethod == 'random':
                import random
                self.projects = random.sample(self.projects, projects)
            else:
                raise ValueError("Invalid sampleMethod. Please use 'most_recent' or 'random'.")
        elif isinstance(projects, list):
            if sampleMethod == 'users':
                filter_projects = []
                for p in self.projects:
                    owner = p.get('owner',{}).get('login')
                    for user in projects:
                        if user in owner:
                            filter_projects.append(p)
                            break
                self.projects = filter_projects
            else:
                self.projects = [p for p in self.projects if p.get('id') in projects]
        else:
            raise ValueError("Invalid projects argument. Please provide a list of project IDs or a number of projects to load.")
        with futures.ThreadPoolExecutor(max_workers=6) as executor:
            results = executor.map(get_project_details, self.projects)
            self.project_details = list(results)
        
    def buildGraph(self, save:bool=False, filename:str='knowledge_graph.ttl',verbose:bool=False,**kwargs):
        """
        Build the knowledge graph based on the dimensions, metrics, segments, and calculated metrics.
        The dimensions, metrics, segments, calculated metrics and projects are each built into their own
        sub-graph concurrently (threads, since the work is I/O-bound on Adobe Analytics API calls rather
        than CPU-bound) and then merged together at the end.
        Arguments:
            save : OPTIONAL : If set to True, it will save the knowledge graph in a ttl file (bool : default False)
            filename : OPTIONAL : The filename to save the knowledge graph (str : default 'knowledge_graph.ttl')
            verbose : OPTIONAL : Adding print statement during the building of the graph.
        Possible kwargs:
            calculatedMetricWorkers : number of threads used to concurrently scan calculated metrics for their
                    referenced segments/metrics, which involves live API calls (int : default 10)
        """
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
        dict_entity_usage = {}
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
                    entry[key] += value
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
            scannedSegment = self.analyticsAPI.scanSegment(segment)
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
        def build_calculated_graph(graph, usage, calculated_metric, scannedMetric):
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
            def scan(calculated_metric):
                return calculated_metric, self.analyticsAPI.scanCalculatedMetric(calculated_metric, knownSegments=self._segmentsById)
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
            for proj in self.project_details:
                build_project_graph(graph, usage, local_dim_metric_cooc, local_dim_segment_cooc, proj)
            return graph, usage, local_dim_metric_cooc, local_dim_segment_cooc
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
            node = BNode()
            self.graph.add((node, RDF.type, Literal("MetricCooccurrence")))
            self.graph.add((node, self.namespaces['usage'].dimension, dimRef))
            self.graph.add((node, self.namespaces['usage'].metric, metRef))
            self.graph.add((node, self.namespaces['usage'].cooccurrenceCount, Literal(data['count'],datatype=XSD.integer)))
            self.graph.add((node, self.namespaces['usage'].rsid, self.namespaces['reportSuites'][data['rsid']]))
        for (dimRef, segRef), data in dim_segment_cooccurrence.items():
            self.graph.add((dimRef, self.namespaces['usage'].usedWithSegment, segRef))
            self.graph.add((segRef, self.namespaces['usage'].usedWithDimension, dimRef))
            node = BNode()
            self.graph.add((node, RDF.type, Literal("SegmentCooccurrence")))
            self.graph.add((node, self.namespaces['usage'].dimension, dimRef))
            self.graph.add((node, self.namespaces['usage'].segment, segRef))
            self.graph.add((node, self.namespaces['usage'].cooccurrenceCount, Literal(data['count'],datatype=XSD.integer)))
            self.graph.add((node, self.namespaces['usage'].rsid, self.namespaces['reportSuites'][data['rsid']]))
        if save:
            turtle = self.graph.serialize(format="turtle")
            if filename is not None:
                if filename.endswith('.ttl') == False:
                    filename += '.ttl'
                Path(filename).write_text(turtle, encoding="utf-8")
        return self.graph

    def exportGraph(self,filename:str = "knowledge_graph.ttl")->None:
        """
        Export the Knowledge Graph in a turtle format. 
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
        Run a SPARQL query against the graph built by buildGraph() and return the results
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