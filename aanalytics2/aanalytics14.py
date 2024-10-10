# Non standard libraries
import pandas as pd
from aanalytics2 import config, connector
from typing import Union
from copy import deepcopy
import pandas as pd

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
            