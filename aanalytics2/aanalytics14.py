# Non standard libraries
import pandas as pd
from aanalytics2 import config, connector
from typing import Union

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
