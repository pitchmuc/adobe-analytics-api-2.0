# Non standard libraries
import pandas as pd
from aanalytics2 import config, connector
from typing import Union
from copy import deepcopy
import pandas as pd
import json
import time

class Report:

    def __init__(self,df:pd.DataFrame,reportType:str,rsid:str,period:str)->None:
        """
        Build a class to return the report with additional information.
        Arguments:
            df : REQUIRED : The dataframe build out of the report
            reportType : REQUIRED : The type of report used
            rsid : REQUIRED : The reportSuite ID used
            period : OPTIONAL : if a ranked report        
        """
        self.DataFrame = df.copy()
        self.columns = df.columns.to_list()
        self.reportType = reportType
        self.rsid = rsid
        if period is not None:
            self.period = period

    def __str__(self):
        """Returns the definition"""
        return f"""Report from {self.rsid}. Type: {self.reportType}. Columns:{self.columns} """
    
    def __repr__(self):
        return self.DataFrame.to_string()
    
    def getDataFrame(self):
        return self.DataFrame

class LegacyAnalytics:
    """
    Class that will help you realize basic requests to the old API 1.4 endpoints
    """

    def __init__(self,company_name:str=None,config:dict=config.config_object)->None:
        """
        Instancialize the Legacy Analytics wrapper.
        """
        if company_name is None:
            raise Exception("Require a company name")
        self.connector = connector.AdobeRequest(config_object=config)
        self.token = self.connector.token
        self.endpoint = "https://api.omniture.com/admin/1.4/rest"
        self.header = header = {
            'Accept': 'application/json',
            'Authorization': f'Bearer {self.token}',
            'X-ADOBE-DMA-COMPANY': company_name
        }

    
    def getData(self,path:str="/",method:str=None,params:dict=None)->dict:
        """
        Use the GET method to the parameter used.
        Arguments:
            path : REQUIRED : If you need a specific path (default "/")
            method : OPTIONAL : if you want to pass the method directly there for the parameter.
            params : OPTIONAL : If you need to pass parameter to your url, use dictionary i.e. : {"param":"value"} 
        """
        if params is not None and type(params) != dict:
            raise TypeError("Require a dictionary")
        myParams = {}
        myParams.update(**params or {})
        if method is not None:
            myParams['method'] = method
        path = path
        res = self.connector.getData(self.endpoint + path,params=myParams,headers=self.header,legacy=True)
        return res

    def postData(self,path:str="/",method:str=None,params:dict=None,data:Union[dict,list]=None)->dict:
        """
        Use the POST method to the parameter used.
        Arguments:
            path : REQUIRED : If you need a specific path (default "/")
            method : OPTIONAL : if you want to pass the method directly there for the parameter.
            params : OPTIONAL : If you need to pass parameter to your url, use dictionary i.e. : {"param":"value"}
            data : OPTIONAL : Usually required to pass the dictionary or list to the request
        """
        if params is not None and type(params) != dict:
            raise TypeError("Require a dictionary")
        if data is not None and (type(data) != dict and type(data) != list):
            raise TypeError("data should be dictionary or list")
        myParams = {}
        myParams.update(**params or {})
        if method is not None:
            myParams['method'] = method
        path = path
        res = self.connector.postData(self.endpoint + path,params=myParams, data=data,headers=self.header,legacy=True)
        return res

    def getReportWait(self,reportDescription:Union[dict,'ReportBuilder14']=None,wait:int=60)->pd.DataFrame:
        """
        Take a report description, send it to the queue and wait for the data in a loop.
        Returns a dataframe
        Argument:
            reportDescription : REQUIRED : The data report definition needed (dictionary or a ReportBuilder instance)
            wait : OPTIONAL : How long in seconds to wait before next request to get data
        """
        if reportDescription is None:
            raise Exception("Require a reportDescription")
        if hasattr(reportDescription,'to_dict'):
            reportDescription = reportDescription.to_dict()
        methodQueue = "Report.Queue"
        res = self.postData(method=methodQueue,data=reportDescription)
        if 'reportID' not in res.keys():
            raise Exception(res)
        data = pd.DataFrame
        while data.empty:
            methodGet = "Report.Get"
            mydata = self.postData(method=methodGet,data=res)
            if 'report' in mydata.keys():
                data = self.transformReportToDataFrame(mydata)
                return data
            time.sleep(wait)


    def __recursiveBuild__(self,row,context:list=None,level:int=0,targetLevel:int=0) -> list:
        """
        Recursive function to build the pandas data frame.
        Arguments:
            row : row of data contain in hte ['report']['data'] object.
            context : list of elements to append to each row
            level : level at which the recursion is
            targetLevel : level expected to reach the recursion.
        """
        level +=1
        if type(row) == dict:
            if context is None:
                context = [row['name']]
            else:
                context.append(row['name'])
            if 'breakdown' in row.keys():   
                data = self.__recursiveBuild__(row['breakdown'],context,level,targetLevel)
            else:
                data = []
                if level != targetLevel: ## if level is different it means we have empty rows and missing elements. Feeling with none
                    new_row = context + [None]*(targetLevel-level) + row["counts"]
                else:
                    new_row = [context  + row["counts"]]
                data += new_row
        elif type(row) == list:
            data = []
            for r in row:
                if 'breakdown' in r.keys():
                    row_context = deepcopy(context)
                    if row_context is None:
                        row_context = [r['name']]
                    else:
                        row_context.append(r['name'])
                    data += self.__recursiveBuild__(r['breakdown'],row_context,level,targetLevel)
                else:
                    row_context = deepcopy(context)
                    if level != targetLevel:
                        new_row = row_context + [r["name"]] + [None]*(targetLevel-level) + r["counts"]
                    else:
                        if row_context is None:
                            new_row = [r["name"]] + r["counts"]
                        else:
                            new_row = row_context + [r["name"]] + r["counts"]
                    data.append(new_row)
        return data
    
    def transformReportToDataFrame(self,data:dict,reportClass:bool=False)->pd.DataFrame:
        """
        Function to pass the response from the "Report.Get" methods when data has been received.
        It will output a dataframe
        Arguments:
            data : REQUIRED : The data response from the request "Report.Get".
            reportClass : OPTIONAL : If you want more context of the data.
        """
        if data is None:
            raise ValueError('Require data to be passed')
        reportType = data.get("report",{}).get("type")
        if reportType is not None:
            dimNames = [el['name'] if 'classification' not in el.keys() else el['classification'] for el in data.get("report",{}).get("elements",[])]
            metrics = [el['name'] for el in data.get("report",{}).get("metrics",[])]
            if reportType=="trended":
                cols = ['date']+dimNames+metrics
                levelsTarget = len(dimNames) +1
            else:
                cols = dimNames+metrics
                levelsTarget = len(dimNames)
            results = []
            for row in data['report']['data']:
                results += self.__recursiveBuild__(row,targetLevel=levelsTarget)
            df = pd.DataFrame(results)
            df.columns = cols
            if reportClass:
                class_data = Report(df,
                                    reportType,
                                    data.get('report').get('reportSuite').get('id'),
                                    data.get('report').get('period'))
                return class_data
            return df

class ReportBuilder14:

    """
    Build a report for the Legacy Analytics 1.4 API Report capability. 
    """

    def __init__(self,template:Union[dict,'ReportBuilder14']=None)->None:
        """
        Construct a report based information.
        Arguments:
            template : OPTIONAL : If you want to use a template of a report to not start from scratch.
        """
        report = {'reportDescription':{'reportSuiteID':None,'elements':[],'metrics':[]}}
        if template is not None:
            if type(template) == ReportBuilder14:
                report = template.to_dict()
            elif type(template) == dict:
                if 'reportDescription' in template.keys():
                    template = template['reportDescription']
                for key in template.keys():
                    report['reportDescription'][key] = template[key]
                if 'metrics' not in report['reportDescription'].keys():
                    report['metrics'] = []
                if 'elements' not in report['reportDescription'].keys():
                    report['elements'] = []
        self.report = report
    
    def __str__(self):
        return json.dumps(self.report,indent=2)
    
    def __repr__(self):
        return json.dumps(self.report,indent=2)
    
    def to_dict(self):
        """
        Return the report as dictionary
        """
        return deepcopy(self.report)

    def setReportSuite(self,rsid:str):
        """
        Add a reportSuite
        Argument:
            rside : REQUIRED : The reportSuite ID
        """
        self.report["reportDescription"]['reportSuiteID'] = rsid
    
    def setSource(self,source:str="warehouse"):
        """
        In case yu want to define data warehouse report per example
        Argument: 
            source : REQUIRED : The source, by default "warehouse"
        """
        self.report["reportDescription"]["source"] = source
    
    def removeSource(self):
        """
        remove the source key in the report.
        """
        if 'source' in self.report['reportDescription'].keys():
            del self.report['reportDescription']['source']
    
    def setDate(self,date:str=None,dateFrom:str=None,dateTo:str=None):
        """
        Set the date for the report. You can use either date or the dateFrom and dateTo parameter.
        Arguments:
            date : OPTIONAL : If requesting a report for a single period, the day/month/year that you want to run the report for. If you use this field, do not use dateFrom or dateTo. If all date fields are omitted, defaults to the current day. This field supports the following formats:
                    Use YYYY for the desired year.
                    Use YYYY-MM for the desired month.
                    Use YYYY-MM-DD for the desired day.
            dateFrom : OPTIONAL : The starting date range. If you use this field, also include dateTo and do not use date. The date format is YYYY-MM-DD. The month and day designators can be omitted if you want a monthly or yearly report
            dateTo : OPTIONAL : The ending date range (inclusive). If you use this field, also include dateFrom and do not use date. The date format is YYYY-MM-DD. The month and day designators can be omitted if you want a monthly or yearly report
        """
        
        if date is not None:
            if 'dateTo' in self.report['reportDescription'].keys():
                del self.report['reportDescription']["dateTo"]
            if 'dateFrom' in self.report['reportDescription'].keys():
                del self.report['reportDescription']["dateFrom"]
            self.report['reportDescription']['date'] = date
        else:
            if dateTo is None or dateFrom is None:
                raise Exception("Require a date parameter to be used")
            else:
                if "date" in self.report['reportDescription'].keys():
                    del self.report['reportDescription']["date"]
                self.report['reportDescription']['dateFrom'] = dateFrom
                self.report['reportDescription']['dateTo'] = dateTo

    def setGranularity(self,dateGranularity:str=None):
        """
        Specifies the date granularity used to display report data (trended reports). If this field is omitted, data is aggregated across the entire date range (ranked reports).
        Argument:
            dateGranularity : REQUIRED : Supported values are:
                minute: Real-Time reports only. Displays report data by minute. Include an integer between 1 - 60 after a semicolon to increase the minute interval. For example, use minute:3 to aggregate data in 3-minute intervals.
                hour: Displays report data by hour.
                day: Displays report data by day.
                week: Displays report data by week.
                month: Displays report data by month.
                quarter: Displays report data by quarter.
                year: Displays report data by year.
        """
        self.report['reportDescription']['dateGranularity'] = dateGranularity

    def removeGranularity(self):
        """
        Remove the granularity component
        """
        if 'dateGranularity' in self.report['reportDescription'].keys():
            del self.report['reportDescription']['dateGranularity']
    
    def addMetric(self,metricId:str=None,**kwargs):
        """
        Add a specific metric
        Argument: 
            metricId : REQUIRED : The metric ID to be used
            kwargs : OPTIONAL : any additional attribute you want to add
        """
        dict_metrics = {
            "id":metricId
        }
        if len(kwargs)>0:
            dict_metrics.update(**kwargs)
        self.report['reportDescription']['metrics'].append(dict_metrics)

    def addElement(self,elementId:str=None,**kwargs):
        """
        Add a specific metric
        Argument: 
            elementId : REQUIRED : The element ID to be used
            kwargs : OPTIONAL : any additional attribute you want to add
        """
        dict_element = {
            "id":elementId
        }
        if len(kwargs)>0:
            dict_element.update(**kwargs)
        self.report['reportDescription']['elements'].append(dict_element)


    def setEncoding(self,encoding:str="utf8"):
        """
        Supported values include utf8 or base64.
        Arguments:
            encodning : OPTIONAL : either utf-8 or bas64.
                utf8: Filters out invalid UTF-8 characters in the request and response.
                base64: Treats the entire request, including element names, search/pathing filters, special keywords, and dates, as if they are base64 encoded.
        """
        self.report['reportDescription']['elementDataEncoding'] = encoding

    def addSegment(self,segment:dict=None):
        """
        Require you to pass the segment object definition to add it on the request.
        Arguments
            segment : REQUIRED : A dictionary that provides some information on the segment depending the type.
        
        Example: 
            segment = {
                "id" : "segmentID"
            }
            or 
            segment = {
                "element": "page",
                "selected": ["Home Page", "Shopping Cart"]
            }
            or 
            segment = {
                "element": "eVar1",
                "classification": "Group Name",
                "search": { "type": "OR", "keywords": ["Administrator", "Manager", "Director"]
            }
        """
        if 'segments' not in self.report['reportDescription'].keys():
            self.report['reportDescription']['segments'] = []
        self.report['reportDescription']['segments'].append(segment)

    def removeSegment(self):
        """
        Remove the segment from the report request.
        """
        if 'segments' in self.report['reportDescription'].keys():
           del self.report['reportDescription']['segments']