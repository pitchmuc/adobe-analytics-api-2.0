import time, datetime
from concurrent import futures
from pathlib import Path
from aanalytics2 import WorkspaceManager, Analytics, Login
from rdflib.namespace import RDF, RDFS, XSD
from rdflib import Graph, Namespace, Literal, URIRef
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
        self.analyticsAPI = Analytics(config=self.config, companyId=self.companyId)
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

    def loadProjects(self, projects: list|int|str,sampleMethod:str='most_recent',**kwargs):
        """
        Load a list of projects to the knowledge graph. 
        This will allow you to build a knowledge graph based on the dimensions, metrics, segments, and calculated metrics used in those projects.
        It gives more context to the relationships between the different elements of your analytics data.
        Arguments:
            projects : A list of project IDs or a number of projects to load. 
                        If a number is provided it will used the sampleMethod to select the projects to load. 
                        if the string "all" is provided, it will used all projects. This is taking a large amount of time (list|int|str)
            sampleMethod : OPTIONAL : The method to use to select the projects to load if a number is provided. (str : default 'most_recent', possible values "random")
                - 'most_recent' : Load the most recent projects based on the last modified date.
                - 'random' : Load a random sample of projects.
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
            self.projects = [p for p in self.projects if p.get('id') in projects]
        else:
            raise ValueError("Invalid projects argument. Please provide a list of project IDs or a number of projects to load.")
        with futures.ThreadPoolExecutor(max_workers=6) as executor:
            results = executor.map(get_project_details, self.projects)
            self.project_details = list(results)
        
    def buildGraph(self, save=False, filename='knowledge_graph.ttl',verbose:bool=False,**kwargs):
        """
        Build the knowledge graph based on the dimensions, metrics, segments, and calculated metrics.
        Arguments:
            save : OPTIONAL : If set to True, it will save the knowledge graph in a ttl file (bool : default False)
            filename : OPTIONAL : The filename to save the knowledge graph (str : default 'knowledge_graph.ttl')
            verbose : OPTIONAL : Adding print statement during the building of the graph.
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
        def build_dimension_graph(dimension,rsid):
            dimension_uri = URIRef(f"http://analytics.com/{self.companyId}/{rsid}/dimension/{dimension['id']}")
            self.graph.add((dimension_uri, RDF.type, Literal("Dimension")))
            self.graph.add((dimension_uri, self.namespaces['dimensions'].dataType, Literal(dimension['type'])))
            self.graph.add((dimension_uri, RDFS.label, Literal(dimension['name'])))
            if '.' in dimension['id']:
                self.graph.add((dimension_uri, self.namespaces['dimensions'].classification, Literal(True,datatype=XSD.boolean)))
                parentRef = URIRef(f"http://analytics.com/{self.companyId}/{rsid}/dimension/{dimension['id'].split('.')[0]}")
                self.graph.add((dimension_uri, self.namespaces['dimensions'].parent_dimension, parentRef))
                self.graph.add((parentRef, self.namespaces['dimensions'].children_dimension, dimension_uri))
            else:
                self.graph.add((dimension_uri, self.namespaces['dimensions'].classification, Literal(False,datatype=XSD.boolean)))
            self.graph.add((dimension_uri, self.namespaces['dimensions'].id, Literal(dimension['id'])))
            if 'description' in dimension:
                self.graph.add((dimension_uri, RDFS.comment, Literal(dimension['description'])))
            for reportable in dimension['reportable']:
                self.graph.add((dimension_uri, self.namespaces['dimensions'].reportable, Literal(reportable)))
            self.graph.add((dimension_uri, self.namespaces['dimensions'].segmentable,Literal(dimension['segmentable'],datatype=XSD.boolean)))
            self.graph.add((dimension_uri, self.namespaces['dimensions'].rsid, self.namespaces['reportSuites'][rsid]))
            self.graph.add((self.namespaces['reportSuites'][rsid], self.namespaces['reportSuites'].dimensions,dimension_uri))
        def build_metric_graph(metric,rsid):
            metric_uri = URIRef(f"http://analytics.com/{self.companyId}/{rsid}/metric/{metric['id']}")
            self.graph.add((metric_uri, RDF.type, Literal("Metric")))
            self.graph.add((metric_uri, RDFS.label, Literal(metric['name'])))
            self.graph.add((metric_uri, self.namespaces['metrics'].id, Literal(metric['id'])))
            self.graph.add((metric_uri, self.namespaces['metrics'].type, Literal(metric['type'])))
            for reportable in metric['reportable']:
                self.graph.add((metric_uri, self.namespaces['metrics'].reportable, Literal(reportable)))
            if 'description' in metric:
                self.graph.add((metric_uri, RDFS.comment, Literal(metric['description'])))
            self.graph.add((metric_uri, self.namespaces['metrics'].segmentable,Literal(metric['segmentable'],datatype=XSD.boolean)))
            self.graph.add((metric_uri, self.namespaces['metrics'].polarity,Literal(metric['polarity'],datatype=XSD.string)))
            self.graph.add((metric_uri, self.namespaces['metrics'].rsid, self.namespaces['reportSuites'][rsid]))
            self.graph.add((self.namespaces['reportSuites'][rsid], self.namespaces['reportSuites'].metrics,metric_uri))
        def build_marketing_channel_graph(rsid):
            marketing_channel = URIRef(f"http://analytics.com/{self.companyId}/{rsid}/marketingChannel/")
            self.graph.add((marketing_channel, RDF.type, Literal("MarketingChannels")))
            mymarketingchannel = self.marketingChannels[rsid]
            for channel in mymarketingchannel['marketingChannels']:
                marketing_channel_uri = URIRef(f"http://analytics.com/{self.companyId}/{rsid}/marketingChannel/{channel['channelId']}")
                self.graph.add((marketing_channel_uri, RDF.type, Literal("MarketingChannel")))
                self.graph.add((marketing_channel_uri, RDFS.label, Literal(channel['name'])))
                self.graph.add((marketing_channel_uri, self.namespaces['marketingChannels'].id, Literal(channel['channelId'])))
                self.graph.add((marketing_channel_uri, self.namespaces['marketingChannels'].rsid, self.namespaces['reportSuites'][rsid]))
                self.graph.add((self.namespaces['reportSuites'][rsid], self.namespaces['reportSuites'].marketingChannels,marketing_channel_uri))
                self.graph.add((marketing_channel, self.namespaces['marketingChannels'].defines,marketing_channel_uri ))
                if channel.get('position') is not None:
                    self.graph.add((marketing_channel_uri, self.namespaces['marketingChannels'].position, Literal(channel['position'],datatype=XSD.integer)))
                self.graph.add((marketing_channel_uri, self.namespaces['marketingChannels'].override, Literal(channel['overrideLastTouchChannel'],datatype=XSD.boolean)))
                self.graph.add((marketing_channel_uri, self.namespaces['marketingChannels'].enabled, Literal(channel['enabled'],datatype=XSD.boolean)))
        if verbose:
            print("building dimensions, metrics, marketing channels")
        for rsid in self.rsids:
            if rsid in self.reportSuites.rsid.tolist():
                row = self.reportSuites[self.reportSuites.rsid == rsid].iloc[0]
                self.graph.add((self.namespaces['reportSuites'][rsid], RDF.type, Literal("ReportSuite")))
                self.graph.add((self.namespaces['reportSuites'][rsid], RDFS.label, Literal(row['name'],datatype=XSD.string)))
                self.graph.add((self.namespaces['reportSuites'][rsid], self.namespaces['reportSuites'].id, Literal(row['rsid'],datatype=XSD.string)))
                self.graph.add((self.namespaces['reportSuites'][rsid], self.namespaces['reportSuites'].currency, Literal(row['currency'])))
            for dimension in self.dimensions[rsid]:
                build_dimension_graph(dimension, rsid)
            for metric in self.metrics[rsid]:
                build_metric_graph(metric, rsid)
            build_marketing_channel_graph(rsid)
        def build_segment_graph(segment):
            segment_uri = URIRef(f"http://analytics.com/{self.companyId}/segment/{segment['id']}")
            self.graph.add((segment_uri, RDF.type, Literal("Segment")))
            self.graph.add((segment_uri, RDFS.label, Literal(segment['name'])))
            if 'description' in segment:
                self.graph.add((segment_uri, RDFS.comment, Literal(segment['description'])))
            self.graph.add((segment_uri, self.namespaces['segments'].id, Literal(segment['id'])))
            self.graph.add((segment_uri, self.namespaces['segments'].definition, Literal(segment['definition'])))
            self.graph.add((segment_uri, self.namespaces['segments'].rsid, self.namespaces['reportSuites'][segment['rsid']]))
            self.graph.add((self.namespaces['reportSuites'][segment['rsid']], self.namespaces['reportSuites'].segments,segment_uri))
            self.graph.add((segment_uri, self.namespaces['segments'].lastAccess, Literal(datetime.datetime.fromtimestamp(segment['lastRecordedAccess']/1000).isoformat().split(".")[0],datatype=XSD.dateTime)))
            for tag in segment['tags']:
                self.graph.add((segment_uri, self.namespaces['segments'].tag, Literal(tag['name'])))
            self.graph.add((segment_uri, self.namespaces['segments'].shares, Literal(len(segment.get('shares',[])),datatype=XSD.integer)))
            scannedSegment = self.analyticsAPI.scanSegment(segment)
            segRsid = scannedSegment['rsid']
            for dim in scannedSegment['dimensions']:
                dimRef = URIRef(f"http://analytics.com/{self.companyId}/{segRsid}/dimension/{dim}")
                if dimRef in dict_entity_usage.keys():
                    dict_entity_usage[dimRef]['segmentUsage'] += 1
                else:
                    dict_entity_usage[dimRef] = {
                        'segmentUsage' : 1,
                        'projectUsage' : 0,
                        'metricUsage':0
                    }
            for met in scannedSegment['metrics']:
                metRef = URIRef(f"http://analytics.com/{self.companyId}/{segRsid}/metric/{met}")
                if metRef in dict_entity_usage.keys():
                    dict_entity_usage[metRef]['segmentUsage'] += 1
                else:
                    dict_entity_usage[metRef] = {
                        'segmentUsage' : 1,
                        'projectUsage' : 0,
                        'metricUsage':0
                    }
            rsidRef = self.namespaces['reportSuites'][segRsid]
            if rsidRef in dict_entity_usage.keys():
                dict_entity_usage[rsidRef]['segmentUsage'] +=1
            else:
                dict_entity_usage[rsidRef] = {
                    'segmentUsage' : 1,
                    'projectUsage' : 0,
                    'metricUsage':0
                }
        for segment in self.segments:
            build_segment_graph(segment)
        def build_calculated_graph(calculated_metric):
            calculated_metric_uri = URIRef(f"http://analytics.com/{self.companyId}/calculatedMetric/{calculated_metric['id']}")
            self.graph.add((calculated_metric_uri, RDF.type, Literal("CalculatedMetric")))
            self.graph.add((calculated_metric_uri, RDFS.label, Literal(calculated_metric['name'])))
            if 'description' in calculated_metric:
                self.graph.add((calculated_metric_uri, RDFS.comment, Literal(calculated_metric['description'])))
            self.graph.add((calculated_metric_uri, self.namespaces['calculatedMetrics'].type, Literal(calculated_metric['type'])))
            self.graph.add((calculated_metric_uri, self.namespaces['calculatedMetrics'].id, Literal(calculated_metric['id'])))
            self.graph.add((calculated_metric_uri, self.namespaces['calculatedMetrics'].definition, Literal(calculated_metric['definition'])))
            self.graph.add((calculated_metric_uri, self.namespaces['calculatedMetrics'].rsid, self.namespaces['reportSuites'][calculated_metric['rsid']]))
            self.graph.add((self.namespaces['reportSuites'][calculated_metric['rsid']], self.namespaces['reportSuites'].calculatedMetrics,calculated_metric_uri))
            self.graph.add((calculated_metric_uri, self.namespaces['calculatedMetrics'].lastAccess, Literal(datetime.datetime.fromtimestamp(calculated_metric['lastRecordedAccess']/1000).isoformat().split(".")[0],datatype=XSD.dateTime)))
            self.graph.add((calculated_metric_uri, self.namespaces['calculatedMetrics'].shares, Literal(len(calculated_metric.get('shares',[])),datatype=XSD.integer)))
            self.graph.add((calculated_metric_uri, self.namespaces['calculatedMetrics'].polarity, Literal(calculated_metric.get('polarity','positive'),datatype=XSD.string)))
            for tag in calculated_metric.get('tags',[]):
                self.graph.add((calculated_metric_uri, self.namespaces['calculatedMetrics'].tag, Literal(tag['name'])))
            for reportable in calculated_metric['compatibility'].get('supported_products',[]):
                self.graph.add((calculated_metric_uri, self.namespaces['calculatedMetrics'].reportable, Literal(reportable)))
            scannedMetric = self.analyticsAPI.scanCalculatedMetric(calculated_metric)
            metRsid = scannedMetric['rsid']
            for metric in scannedMetric['metrics']:
                metRef = URIRef(f"http://analytics.com/{self.companyId}/{metRsid}/metric/{metric}")
                if metRef in dict_entity_usage.keys():
                    dict_entity_usage[metRef]['metricUsage'] += 1
                else:
                    dict_entity_usage[metRef] = {
                                'segmentUsage' : 0,
                                'projectUsage' : 0,
                                'metricUsage':1
                        }
            rsidRef = self.namespaces['reportSuites'][metRsid]
            if rsidRef in dict_entity_usage.keys():
                dict_entity_usage[rsidRef]['metricUsage'] += 1
            else:
                dict_entity_usage[rsidRef] = {
                                                'segmentUsage' : 0,
                                                'projectUsage' : 0,
                                                'metricUsage':1
                                        }
        for calculated_metric in self.calculatedMetrics:
            build_calculated_graph(calculated_metric)
        for daterange in self.dateRanges:
            drRef = URIRef(f"http://analytics.com/{self.companyId}/dateRange/{daterange['id']}")
            self.graph.add((drRef,RDF.type,Literal("DateRange")))
            self.graph.add((drRef,RDFS.label,Literal(daterange['name'])))
            self.graph.add((drRef,self.namespaces['dateRange'].id,Literal(daterange['id'])))
            self.graph.add((drRef,self.namespaces['dateRange'].description,Literal(daterange['description'])))
            self.graph.add((drRef,self.namespaces['dateRange'].definition,Literal(daterange['definition'])))
        def build_project_graph(project_detail):
            Wproject = project_detail
            project_ref = URIRef(f"http://analytics.com/{self.companyId}/projects/{Wproject.id}")
            self.graph.add((self.namespaces['projects'], self.namespaces['projects'].contains,project_ref))
            rsidRef = self.namespaces['reportSuites'][Wproject.rsid]
            self.graph.add((project_ref, self.namespaces['projects'].rsid,rsidRef))
            if rsidRef in dict_entity_usage.keys():
                dict_entity_usage[rsidRef]['projectUsage'] += 1
            else:
                dict_entity_usage[rsidRef] = {
                        'segmentUsage' : 0,
                        'projectUsage' : 1,
                        'metricUsage': 0
                }
            self.graph.add((project_ref, RDFS.label,Literal(Wproject.name)))
            self.graph.add((project_ref, RDF.type,Literal("Workspace")))
            self.graph.add((project_ref, self.namespaces['projects'].description,Literal(Wproject.description)))
            self.graph.add((project_ref, self.namespaces['projects'].created,Literal(Wproject.created,datatype=XSD.dateTime)))
            for panel in Wproject.panels:
                for element in panel.elements:
                    if element.type == "Text":
                        self.graph.add((project_ref, self.namespaces['projects'].text,Literal(element.name,datatype=XSD.string)))
                        if element.text is not None and element.text != "":
                            self.graph.add((project_ref, self.namespaces['projects'].text,Literal(element.text,datatype=XSD.string)))
                    elif element.type == "Visualization":
                        self.graph.add((project_ref, self.namespaces['projects'].visualition,Literal(element.name,datatype=XSD.string)))
                        for dimension in element.dimensions:
                            dimRef = URIRef(f"http://analytics.com/{self.companyId}/{Wproject.rsid}/dimension/{dimension['id']}")
                            self.graph.add((dimRef, self.namespaces['projects'].dimension_ref,project_ref))
                            if dimRef in dict_entity_usage.keys():
                                dict_entity_usage[dimRef]['projectUsage'] += 1
                            else:
                                dict_entity_usage[dimRef] = {
                                                        'segmentUsage' : 0,
                                                        'projectUsage' : 1,
                                                        'metricUsage': 0
                                                }
                        for metric in element.metrics:
                            metRef = URIRef(f"http://analytics.com/{self.companyId}/{Wproject.rsid}/metric/{metric['id']}")
                            self.graph.add((metRef, self.namespaces['projects'].metric_ref,project_ref))
                            if metRef in dict_entity_usage.keys():
                                dict_entity_usage[metRef]['projectUsage'] += 1
                            else:
                                dict_entity_usage[metRef] = {
                                                        'segmentUsage' : 0,
                                                        'projectUsage' : 1,
                                                        'metricUsage': 0
                                                }
                        for calc in element.calculatedMetrics:
                            calcRef = URIRef(f"http://analytics.com/{self.companyId}/calculatedMetric/{calc['id']}")
                            self.graph.add((calcRef, self.namespaces['projects'].calculated_ref,project_ref))
                            if calcRef in dict_entity_usage.keys():
                                dict_entity_usage[calcRef]['projectUsage'] += 1
                            else:
                                dict_entity_usage[calcRef] = {
                                                        'segmentUsage' : 0,
                                                        'projectUsage' : 1,
                                                        'metricUsage': 0
                                                }
                    elif element.type == "FreeForm":
                        freeformText = f"{element.name}"
                        if element.description != "":
                            freeformText += f": {element.description}"
                        self.graph.add((project_ref, self.namespaces['projects'].panelFreeForm,Literal(freeformText,datatype=XSD.string)))
                        for dimension in element.dimensions:
                            dimRef = URIRef(f"http://analytics.com/{self.companyId}/{Wproject.rsid}/dimension/{dimension['id']}")
                            self.graph.add((dimRef, self.namespaces['projects'].dimension_ref,project_ref))
                            if dimRef in dict_entity_usage.keys():
                                dict_entity_usage[dimRef]['projectUsage'] += 1
                            else:
                                dict_entity_usage[dimRef] = {
                                                        'segmentUsage' : 0,
                                                        'projectUsage' : 1,
                                                        'metricUsage': 0
                                                }
                        for metric in element.metrics:
                            metRef = URIRef(f"http://analytics.com/{self.companyId}/{Wproject.rsid}/metric/{metric['id']}")
                            self.graph.add((metRef, self.namespaces['projects'].metric_ref,project_ref))
                            if metRef in dict_entity_usage.keys():
                                dict_entity_usage[metRef]['projectUsage'] += 1
                            else:
                                dict_entity_usage[metRef] = {
                                                        'segmentUsage' : 0,
                                                        'projectUsage' : 1,
                                                        'metricUsage': 0
                                                }
                        for calc in element.calculatedMetrics:
                            calcRef = URIRef(f"http://analytics.com/{self.companyId}/calculatedMetric/{calc['id']}")
                            self.graph.add((calcRef, self.namespaces['projects'].calculated_ref,project_ref))
                            if calcRef in dict_entity_usage.keys():
                                dict_entity_usage[calcRef]['projectUsage'] += 1
                            else:
                                dict_entity_usage[calcRef] = {
                                                        'segmentUsage' : 0,
                                                        'projectUsage' : 1,
                                                        'metricUsage': 0
                                                }
        for proj in self.project_details:
            build_project_graph(proj)
        for ref, usage in dict_entity_usage.items():
            for key, value in usage.items():
                self.graph.add((ref, self.namespaces['usage'][key],Literal(value,datatype=XSD.integer)))
        if save:
            turtle = self.graph.serialize(format="turtle")
            if filename is not None:
                Path(filename).write_text(turtle, encoding="utf-8")
        return self.graph