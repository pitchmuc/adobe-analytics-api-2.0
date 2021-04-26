# Created by julien piccini
# email : piccini.julien@gmail.com
import json
import os
import time
from concurrent import futures
from copy import deepcopy
from pathlib import Path
from typing import IO, Union, List
from collections import defaultdict
import re

# Non standard libraries
import pandas as pd
import requests

from aanalytics2 import config, connector, token_provider
from .projects import *

JsonOrDataFrameType = Union[pd.DataFrame, dict]
JsonListOrDataFrameType = Union[pd.DataFrame, List[dict]]


def _checkToken(func):
    """decorator that checks that the token is valid before calling the API"""

    def checking(*args, **kwargs):  # if function is not wrapped, will fire
        now = time.time()
        if now > config.config_object["date_limit"] - 1000:
            token_with_expiry = token_provider.get_token_and_expiry_for_config(config.config_object, *args,
                                                                               **kwargs)
            token = token_with_expiry['token']
            config.config_object['token'] = token
            config.config_object['date_limit'] = time.time() + token_with_expiry['expiry'] / 1000 - 500
            config.header.update({'Authorization': f'Bearer {token}'})
            if kwargs.get("headers", None) is not None:
                kwargs['headers']['Authorization'] = "Bearer " + token
            return func(*args, **kwargs)
        else:  # need to return the function for decorator to return something
            return func(*args, **kwargs)

    return checking  # return the function as object


@_checkToken
def getData(endpoint: str, params: dict = None, data: dict = None, headers: dict = None, *args, **kwargs):
    """
    Abstraction for getting data
    """
    header = headers
    if params is not None and data is None:
        res = requests.get(endpoint, headers=header, params=params)
    elif params is None and data is not None:
        res = requests.get(endpoint, headers=header, data=data)
    elif params is not None and data is not None:
        res = requests.get(endpoint, headers=header, params=params, data=data)
    try:
        result = res.json()
    except ValueError:
        result = {'error': ['Request Error']}
    if res.status_code == 429:
        result['status_code'] = 429
    return result


@_checkToken
def postData(endpoint: str, params: dict = None, data=None, headers: dict = None, file: dict = None, *args, **kwargs):
    """
    Abstraction for getting data
    """
    header = headers
    if params is not None and data is None and file is None:
        res = requests.post(endpoint, headers=header, params=params)
    elif params is None and data is not None and file is None:
        res = requests.post(
            endpoint, headers=header, data=json.dumps(data))
    elif params is not None and data is not None and file is None:
        res = requests.post(endpoint, headers=header,
                            params=params, data=json.dumps(data=data))
    elif file is not None:
        res = requests.post(endpoint, headers=header, files=file)
    try:
        result = res.json()
    except ValueError:
        result = {'error': ['Request Error']}
    if res.status_code == 429:
        result['status_code'] = 429
    return result


@_checkToken
def putData(endpoint: str, params: dict = None, data=None, headers: dict = None, *args, **kwargs):
    """
    Abstraction for getting data
    """
    header = headers
    if params is not None and data is None:
        res = requests.put(endpoint, headers=header, params=params)
    elif params is None and data is not None:
        res = requests.put(
            endpoint, headers=header, data=json.dumps(data))
    elif params is not None and data is not None:
        res = requests.put(endpoint, headers=header, params=params, data=json.dumps(data=data))
    try:
        result = res.json()
    except ValueError:
        result = {'error': ['Request Error']}
    return result


@_checkToken
def deleteData(endpoint: str, params: dict = None, data=None, headers: dict = None, *args, **kwargs):
    """
    Abstraction for getting data
    """
    header = headers
    if params is not None and data is None:
        res = requests.delete(endpoint, headers=header, params=params)
    elif params is None and data is not None:
        res = requests.delete(endpoint, headers=header, data=json.dumps(data))
    elif params is not None and data is not None:
        res = requests.delete(endpoint, headers=header, params=params, data=json.dumps(data=data))
    elif params is None and data is None:
        res = requests.delete(endpoint, headers=header)
    try:
        result = res.json()
    except:
        result = {'error': ['Request Error']}
    return result


@_checkToken
def getCompanyId(infos: str = 'all'):
    """
    Retrieve the company id for later call for the properties.
    Can return a string or a json object.
    Arguments:
        infos : OPTIONAL: returns the company id(s) specified. 
        Possible values:
            - all : returns the list of companies data (default value)
            - first : returns the first id (string returned)
            - <X> : number that gives the position of the id we want to return (string)
            You need to already know your position. 
    """
    res = requests.get(
        "https://analytics.adobe.io/discovery/me", headers=config.header)
    json_res = res.json()
    if infos == 'all':
        try:
            companies = json_res['imsOrgs'][0]['companies']
            return companies
        except:
            print("exception when trying to get companies with parameter 'all'")
            return None
    elif infos != 'all':
        try:
            if infos == 'first':
                infos = '0'  # set to first position
            position = int(infos)
            companies = json_res['imsOrgs'][0]['companies']
            config.companyid = companies[position]['globalCompanyId']
            return config.companyid
        except:
            print("exception when trying to get companies with parameter != 'all'")
            return None
    
def retrieveToken(verbose: bool = False, save: bool = False, **kwargs)->str:
    """
    LEGACY retrieve token directly following the importConfigFile or Configure method.
    """
    token_with_expiry = token_provider.get_token_and_expiry_for_config(config.config_object,**kwargs)
    token = token_with_expiry['token']
    config.config_object['token'] = token
    config.config_object['date_limit'] = time.time() + token_with_expiry['expiry'] / 1000 - 500
    config.header.update({'Authorization': f'Bearer {token}'})
    if verbose:
        print(f"token valid till : {time.ctime(time.time() + token_with_expiry['expiry'] / 1000)}")
    return token



class Login:
    """
    Class to connect to the the login company.
    """

    def __init__(self, config: dict = config.config_object, header: dict = config.header, retry: int = 0) -> None:
        """
        Instantiate the Loggin class.
        Arguments:
            config : REQUIRED : dictionary with your configuration information.
            header : REQUIRED : dictionary of your header.
            retry : OPTIONAL : if you want to retry, the number of time to retry
        """
        self.connector = connector.AdobeRequest(
            config_object=config, header=header, retry=retry)
        self.header = self.connector.header
        self.COMPANY_IDS = {}
        self.retry = retry

    def getCompanyId(self) -> dict:
        """
        Retrieve the company ids for later call for the properties.
        """
        res = self.connector.getData(
            "https://analytics.adobe.io/discovery/me", headers=self.header)
        json_res = res
        try:
            companies = json_res['imsOrgs'][0]['companies']
            self.COMPANY_IDS = json_res['imsOrgs'][0]['companies']
            return companies
        except:
            print("exception when trying to get companies with parameter 'all'")
            print(json_res)
            return None

    def createAnalyticsConnection(self, companyId: str = None) -> object:
        """
        Returns an instance of the Analytics class so you can query the different elements from that instance.
        Arguments:
            companyId: REQUIRED : The globalCompanyId that you want to use in your connection
        the retry parameter set in the previous class instantiation will be used here.
        """
        analytics = Analytics(company_id=companyId,
                              config_object=self.connector.config, header=self.header, retry=self.retry)
        return analytics


class Analytics:
    """
    Class that instantiate a connection to a single login company.
    """
    # Endpoints
    header = {"Accept": "application/json",
              "Content-Type": "application/json",
              "Authorization": "Bearer ",
              "X-Api-Key": ""
              }
    _endpoint = 'https://analytics.adobe.io/api'
    _getRS = '/collections/suites'
    _getDimensions = '/dimensions'
    _getMetrics = '/metrics'
    _getSegments = '/segments'
    _getCalcMetrics = '/calculatedmetrics'
    _getUsers = '/users'
    _getDateRanges = '/dateranges'
    _getReport = '/reports'

    def __init__(self, company_id: str = None, config_object: dict = config.config_object, header: dict = config.header,
                 retry: int = 0):
        """
        Instantiate the 
        """
        if company_id is None:
            raise AttributeError(
                'Expected "company_id" to be referenced.\nPlease ensure you pass the globalCompanyId when instantiating this class.')
        self.connector = connector.AdobeRequest(
            config_object=config_object, header=header, retry=retry)
        self.header = self.connector.header
        self.connector.header['x-proxy-global-company-id'] = company_id
        self.header['x-proxy-global-company-id'] = company_id
        self.endpoint_company = f"{self._endpoint}/{company_id}"
        self.company_id = company_id
        self.listProjectIds = []
        self.projectsDetails = {}
        self.segments = []
        self.calculatedMetrics = []
        try:
            import importlib.resources as pkg_resources
            pathLOGS = pkg_resources.path(
                "aanalytics2", "eventType_usageLogs.pickle")
        except ImportError:
            try:
                # Try backported to PY<37 `importlib_resources`.
                import pkg_resources
                pathLOGS = pkg_resources.resource_filename(
                    "aanalytics2", "eventType_usageLogs.pickle")
            except:
                print('Empty LOGS_EVENT_TYPE attribute')
        try:
            with pathLOGS as f:
                self.LOGS_EVENT_TYPE = pd.read_pickle(f)
        except:
            self.LOGS_EVENT_TYPE = "no data"

    def __str__(self)->str:
        obj = {
            "endpoint" : self.endpoint_company,
            "companyId" : self.company_id,
            "header" : self.header,
            "token" : self.connector.config['token']
        }
        return json.dumps(obj,indent=4)
    
    def __repr__(self)->str:
        obj = {
            "endpoint" : self.endpoint_company,
            "companyId" : self.company_id,
            "header" : self.header,
            "token" : self.connector.config['token']
        }
        return json.dumps(obj,indent=4)

    def refreshToken(self, token: str = None):
        if token is None:
            raise AttributeError(
                'Expected "token" to be referenced.\nPlease ensure you pass the token.')
        self.header['Authorization'] = "Bearer " + token

    def getReportSuites(self, txt: str = None, rsid_list: str = None, limit: int = 100, extended_info: bool = False,
                        save: bool = False) -> list:
        """
        Get the reportSuite IDs data. Returns a dataframe of reportSuite name and report suite id.
        Arguments: 
            txt : OPTIONAL : returns the reportSuites that matches a speific text field
            rsid_list : OPTIONAL : returns the reportSuites that matches the list of rsids set
            limit : OPTIONAL : How many reportSuite retrieves per serverCall 
            save : OPTIONAL : if set to True, it will save the list in a file. (Default False)

        """
        nb_error, nb_empty = 0, 0  # use for multi-thread loop
        params = {}
        params.update({'limit': str(limit)})
        params.update({'page': '0'})
        if txt is not None:
            params.update({'rsidContains': str(txt)})
        if rsid_list is not None:
            params.update({'rsids': str(rsid_list)})
        params.update(
            {"expansion": "name,parentRsid,currency,calendarType,timezoneZoneinfo"})
        rsids = self.connector.getData(self.endpoint_company + self._getRS,
                                       params=params, headers=self.header)
        content = rsids['content']
        if not extended_info:
            list_content = [{'name': item['name'], 'rsid': item['rsid']}
                            for item in content]
            df_rsids = pd.DataFrame(list_content)
        else:
            df_rsids = pd.DataFrame(content)
        total_page = rsids['totalPages']
        last_page = rsids['lastPage']
        if not last_page:  # if last_page =False
            callsToMake = total_page
            list_params = [{**params, 'page': page}
                           for page in range(1, callsToMake)]
            list_urls = [self.endpoint_company +
                         self._getRS for x in range(1, callsToMake)]
            listheaders = [self.header for x in range(1, callsToMake)]
            workers = min(10, total_page)
            with futures.ThreadPoolExecutor(workers) as executor:
                res = executor.map(lambda x, y, z: self.connector.getData(
                    x, y, headers=z), list_urls, list_params, listheaders)
            res = list(res)
            list_data = [val for sublist in [r['content']
                                             for r in res if 'content' in r.keys()] for val in sublist]
            nb_error = sum(1 for elem in res if 'error_code' in elem.keys())
            nb_empty = sum(1 for elem in res if 'content' in elem.keys() and len(
                elem['content']) == 0)
            if not extended_info:
                list_append = [{'name': item['name'], 'rsid': item['rsid']}
                               for item in list_data]
                df_append = pd.DataFrame(list_append)
            else:
                df_append = pd.DataFrame(list_data)
            df_rsids = df_rsids.append(df_append, ignore_index=True)
        if save:
            df_rsids.to_csv('RSIDS.csv', sep='\t')
        if nb_error > 0 or nb_empty > 0:
            print(
                f'WARNING : Retrieved data are partial.\n{nb_error}/{len(list_urls) + 1} requests returned an error.\n{nb_empty}/{len(list_urls)} requests returned an empty response. \nTry to use filter to retrieve reportSuite or increase limit per request')
        return df_rsids

    def getVirtualReportSuites(self, extended_info: bool = False, limit: int = 100, filterIds: str = None,
                               idContains: str = None, segmentIds: str = None, save: bool = False) -> list:
        """
        return a lit of virtual reportSuites and their id. It can contain more information if expansion is selected.
        Arguments:
            extended_info : OPTIONAL : boolean to retrieve the maximum of information.
            limit : OPTIONAL : How many reportSuite retrieves per serverCall
            filterIds : OPTIONAL : comma delimited list of virtual reportSuite ID  to be retrieved.
            idContains : OPTIONAL : element that should be contained in the Virtual ReportSuite Id
            segmentIds : OPTIONAL : comma delimited list of segmentId contained in the VRSID
            save : OPTIONAL : if set to True, it will save the list in a file. (Default False)
        """
        expansion_values = "globalCompanyKey,parentRsid,parentRsidName,timezone,timezoneZoneinfo,currentTimezoneOffset,segmentList,description,modified,isDeleted,dataCurrentAsOf,compatibility,dataSchema,sessionDefinition,curatedComponents,type"
        params = {"limit": limit}
        nb_error = 0
        nb_empty = 0
        list_urls = []
        if extended_info:
            params['expansion'] = expansion_values
        if filterIds is not None:
            params['filterByIds'] = filterIds
        if idContains is not None:
            params['idContains'] = idContains
        if segmentIds is not None:
            params['segmentIds'] = segmentIds
        path = f"{self.endpoint_company}/reportsuites/virtualreportsuites"
        vrsid = self.connector.getData(
            path, params=params, headers=self.header)
        content = vrsid['content']
        if not extended_info:
            list_content = [{'name': item['name'], 'vrsid': item['id']}
                            for item in content]
            df_vrsids = pd.DataFrame(list_content)
        else:
            df_vrsids = pd.DataFrame(content)
        total_page = vrsid['totalPages']
        last_page = vrsid['lastPage']
        if not last_page:  # if last_page =False
            callsToMake = total_page
            list_params = [{**params, 'page': page}
                           for page in range(1, callsToMake)]
            list_urls = [path for x in range(1, callsToMake)]
            listheaders = [self.header for x in range(1, callsToMake)]
            workers = min(10, total_page)
            with futures.ThreadPoolExecutor(workers) as executor:
                res = executor.map(lambda x, y, z: self.connector.getData(
                    x, y, headers=z), list_urls, list_params, listheaders)
            res = list(res)
            list_data = [val for sublist in [r['content']
                                             for r in res if 'content' in r.keys()] for val in sublist]
            nb_error = sum(1 for elem in res if 'error_code' in elem.keys())
            nb_empty = sum(1 for elem in res if 'content' in elem.keys() and len(
                elem['content']) == 0)
            if not extended_info:
                list_append = [{'name': item['name'], 'vrsid': item['id']}
                               for item in list_data]
                df_append = pd.DataFrame(list_append)
            else:
                df_append = pd.DataFrame(list_data)
            df_vrsids = df_vrsids.append(df_append, ignore_index=True)
        if save:
            df_vrsids.to_csv('VRSIDS.csv', sep='\t')
        if nb_error > 0 or nb_empty > 0:
            print(
                f'WARNING : Retrieved data are partial.\n{nb_error}/{len(list_urls) + 1} requests returned an error.\n{nb_empty}/{len(list_urls)} requests returned an empty response. \nTry to use filter to retrieve reportSuite or increase limit per request')
        return df_vrsids

    def getVirtualReportSuite(self, vrsid: str = None, extended_info: bool = False,
                              format: str = 'df') -> JsonOrDataFrameType:
        """
        return a single virtual report suite ID information as dataframe.
        Arguments:
            vrsid : REQUIRED : The virtual reportSuite to be retrieved
            extended_info : OPTIONAL : boolean to add more information
            format : OPTIONAL : format of the output. 2 values "df" for dataframe and "raw" for raw json.
        """
        if vrsid is None:
            raise Exception("require a Virtual ReportSuite ID")
        expansion_values = "globalCompanyKey,parentRsid,parentRsidName,timezone,timezoneZoneinfo,currentTimezoneOffset,segmentList,description,modified,isDeleted,dataCurrentAsOf,compatibility,dataSchema,sessionDefinition,curatedComponents,type"
        params = {}
        if extended_info:
            params['expansion'] = expansion_values
        path = f"{self.endpoint_company}/reportsuites/virtualreportsuites/{vrsid}"
        data = self.connector.getData(path, params=params, headers=self.header)
        if format == "df":
            data = pd.DataFrame({vrsid: data})
        return data

    def getVirtualReportSuiteComponents(self, vrsid: str = None, nan_value=""):
        """
        Uses the getVirtualReportSuite function to get a VRS and returns
        the VRS components for a VRS as a dataframe. VRS must have Component Curation enabled.
        Arguments:
            vrsid : REQUIRED : Virtual Report Suite ID
            nan_value : OPTIONAL : how to handle empty cells, default = ""
        """
        vrs_data = self.getVirtualReportSuite(extended_info=True, vrsid=vrsid)
        if "curatedComponents" not in vrs_data.index:
            return pd.DataFrame()
        components_cell = vrs_data[vrs_data.index ==
                                   "curatedComponents"].iloc[0, 0]
        return pd.DataFrame(components_cell).fillna(value=nan_value)

    def createVirtualReportSuite(self, name: str = None, parentRsid: str = None, segmentList: list = None,
                                 dataSchema: str = "Cache", data_dict: dict = None, **kwargs) -> dict:
        """
        Create a new virtual report suite based on the information provided.
        Arguments:
            name : REQUIRED : name of the virtual reportSuite
            parentRsid : REQUIRED : Parent reportSuite ID for the VRS
            segmentLists : REQUIRED : list of segment id to be applied on the ReportSuite.
            dataSchema : REQUIRED : Type of schema used for the VRSID. (default "Cache")
            data_dict : OPTIONAL : you can pass directly the dictionary.
        """
        path = f"{self.endpoint_company}/reportsuites/virtualreportsuites"
        expansion_values = "globalCompanyKey,parentRsid,parentRsidName,timezone,timezoneZoneinfo,currentTimezoneOffset,segmentList,description,modified,isDeleted,dataCurrentAsOf,compatibility,dataSchema,sessionDefinition,curatedComponents,type"
        params = {'expansion': expansion_values}
        if data_dict is None:
            body = {
                "name": name,
                "parentRsid": parentRsid,
                "segmentList": segmentList,
                "dataSchema": dataSchema,
                "description": kwargs.get('description', '')
            }
        else:
            if 'name' not in data_dict.keys() or 'parentRsid' not in data_dict.keys() or 'segmentList' not in data_dict.keys() or 'dataSchema' not in data_dict.keys():
                raise Exception(
                    "Missing one or more fundamental keys : name, parentRsid, segmentList, dataSchema")
            body = data_dict
        res = self.connector.postData(
            path, params=params, data=body, headers=self.header)
        return res

    def updateVirtualReportSuite(self, vrsid: str = None, data_dict: dict = None, **kwargs) -> dict:
        """
        Updates a Virtual Report Suite based on a JSON-like dictionary (same structure as createVirtualReportSuite)
        Note that to update components, you need to supply ALL components currently associated with this suite.
        Supplying only the components you want to change will remove all others from the VR Suite!
        Arguments:
            vrsid : REQUIRED : The id of the virtual report suite to update
            data_dict : a json-like dictionary of the vrs data to update
        """
        path = f"{self.endpoint_company}/reportsuites/virtualreportsuites/{vrsid}"
        body = data_dict
        res = self.connector.putData(path, data=body, headers=self.header)
        return res

    def deleteVirtualReportSuite(self, vrsid: str = None) -> str:
        """
        Delete a Virtual Report Suite based on the id passed.
        Arguments:
            vrsid : REQUIRED : The id of the virtual reportSuite to delete.
        """
        if vrsid is None:
            raise Exception("require a Virtual ReportSuite ID")
        path = f"{self.endpoint_company}/reportsuites/virtualreportsuites/{vrsid}"
        res = self.connector.deleteData(path, headers=self.header)
        return res

    def validateVirtualReportSuite(self, name: str = None, parentRsid: str = None, segmentList: list = None,
                                   dataSchema: str = "Cache", data_dict: dict = None, **kwargs) -> dict:
        """
        Validate the object to create a new virtual report suite based on the information provided.
        Arguments:
            name : REQUIRED : name of the virtual reportSuite
            parentRsid : REQUIRED : Parent reportSuite ID for the VRS
            segmentLists : REQUIRED : list of segment ids to be applied on the ReportSuite.
            dataSchema : REQUIRED : Type of schema used for the VRSID (default : Cache).
            data_dict : OPTIONAL : you can pass directly the dictionary.
        """
        path = f"{self.endpoint_company}/reportsuites/virtualreportsuites/validate"
        expansion_values = "globalCompanyKey, parentRsid, parentRsidName, timezone, timezoneZoneinfo, currentTimezoneOffset, segmentList, description, modified, isDeleted, dataCurrentAsOf, compatibility, dataSchema, sessionDefinition, curatedComponents, type"
        if data_dict is None:
            body = {
                "name": name,
                "parentRsid": parentRsid,
                "segmentList": segmentList,
                "dataSchema": dataSchema,
                "description": kwargs.get('description', '')
            }
        else:
            if 'name' not in data_dict.keys() or 'parentRsid' not in data_dict.keys() or 'segmentList' not in data_dict.keys() or 'dataSchema' not in data_dict.keys():
                raise Exception(
                    "Missing one or more fundamental keys : name, parentRsid, segmentList, dataSchema")
            body = data_dict
        res = self.connector.postData(path, data=body, headers=self.header)
        return res

    def getDimensions(self, rsid: str, tags: bool = False, description:bool=False, save=False, **kwargs) -> pd.DataFrame:
        """
        Retrieve the list of dimensions from a specific reportSuite.Shrink columns to simplify output.
        Returns the data frame of available dimensions.
        Arguments:
            rsid : REQUIRED : Report Suite ID from which you want the dimensions
            tags : OPTIONAL : If you would like to have additional information, such as tags. (bool : default False)
            description : OPTIONAL : Trying to add the description column. It may break the method.
            save : OPTIONAL : If set to True, it will save the info in a csv file (bool : default False)
        Possible kwargs:
            full : Boolean : Doesn't shrink the number of columns if set to true
            example : getDimensions(rsid,full=True)
        """
        params = {}
        if tags:
            params.update({'expansion': 'tags'})
        params.update({'rsid': rsid})
        dims = self.connector.getData(self.endpoint_company +
                                      self._getDimensions, params=params, headers=self.header)
        df_dims = pd.DataFrame(dims)
        columns = ['id', 'name', 'category', 'type',
                   'parent', 'pathable']
        if description:
            columns.append('description')
        if kwargs.get('full', False):
            new_cols = pd.DataFrame(df_dims.support.values.tolist(),
                                    columns=['support_oberon', 'support_dw'])  # extract list in column
            new_df = df_dims.merge(new_cols, right_index=True, left_index=True)
            new_df.drop(['reportable', 'support'], axis=1, inplace=True)
            df_dims = new_df
        else:
            df_dims = df_dims[columns]
        if save:
            df_dims.to_csv(f'dimensions_{rsid}.csv')
        return df_dims

    def getMetrics(self, rsid: str, tags: bool = False, save=False, dataGroup:bool=False, **kwargs) -> pd.DataFrame:
        """
        Retrieve the list of metrics from a specific reportSuite. Shrink columns to simplify output.
        Returns the data frame of available metrics.
        Arguments:
            rsid : REQUIRED : Report Suite ID from which you want the dimensions (str)
            tags : OPTIONAL : If you would like to have additional information, such as tags.(bool : default False)
            dataGroup : OPTIONAL : Adding dataGroups to the column exported. Default False. 
                May break the report.
            save : OPTIONAL : If set to True, it will save the info in a csv file (bool : default False)
        Possible kwargs:
            full : Boolean : Doesn't shrink the number of columns if set to true.
        """
        params = {}
        if tags:
            params.update({'expansion': 'tags'})
        params.update({'rsid': rsid})
        metrics = self.connector.getData(self.endpoint_company +
                                         self._getMetrics, params=params, headers=self.header)
        df_metrics = pd.DataFrame(metrics)
        columns = ['id', 'name', 'category', 'type',
                   'precision', 'segmentable']
        if dataGroup:
            columns.append('dataGroup')
        if kwargs.get('full', False):
            new_cols = pd.DataFrame(df_metrics.support.values.tolist(), columns=[
                'support_oberon', 'support_dw'])
            new_df = df_metrics.merge(
                new_cols, right_index=True, left_index=True)
            new_df.drop('support', axis=1, inplace=True)
            df_metrics = new_df
        else:
            df_metrics = df_metrics[columns]
        if save:
            df_metrics.to_csv(f'metrics_{rsid}.csv', sep='\t')
        return df_metrics

    def getUsers(self, save: bool = False, **kwargs) -> pd.DataFrame:
        """
        Retrieve the list of users for a login company.Returns a data frame.
        Arguments:
            save : OPTIONAL : Save the data in a file (bool : default False). 
        Possible kwargs: 
            limit :  Nummber of results per requests. Default 100.
            expansion : string list such as "lastAccess,createDate"  
        """
        list_urls = []
        nb_error, nb_empty = 0, 0  # use for multi-thread loop
        params = {'limit': kwargs.get('limit', 100)}
        if kwargs.get("expansion", None) is not None:
            params["expansion"] = kwargs.get("expansion", None)
        users = self.connector.getData(self.endpoint_company +
                                       self._getUsers, params=params, headers=self.header)
        data = users['content']
        lastPage = users['lastPage']
        if not lastPage:  # check if lastpage is inversed of False
            callsToMake = users['totalPages']
            list_params = [{'limit': params['limit'], 'page': page}
                           for page in range(1, callsToMake)]
            list_urls = [self.endpoint_company +
                         self._getUsers for x in range(1, callsToMake)]
            listheaders = [self.header
                           for x in range(1, callsToMake)]
            workers = min(10, len(list_params))
            with futures.ThreadPoolExecutor(workers) as executor:
                res = executor.map(lambda x, y, z: self.connector.getData(x, y, headers=z), list_urls,
                                   list_params, listheaders)
            res = list(res)
            users_lists = [elem['content']
                           for elem in res if 'content' in elem.keys()]
            nb_error = sum(1 for elem in res if 'error_code' in elem.keys())
            nb_empty = sum(1 for elem in res if 'content' in elem.keys()
                           and len(elem['content']) == 0)
            append_data = [val for sublist in [data for data in users_lists]
                           for val in sublist]  # flatten list of list
            data = data + append_data
        df_users = pd.DataFrame(data)
        columns = ['email', 'login', 'fullName', 'firstName', 'lastName', 'admin', 'loginId', 'imsUserId', 'login',
                   'createDate', 'lastAccess', 'title', 'disabled', 'phoneNumber', 'companyid']
        df_users = df_users[columns]
        df_users['createDate'] = pd.to_datetime(df_users['createDate'])
        df_users['lastAccess'] = pd.to_datetime(df_users['lastAccess'])
        if save:
            df_users.to_csv('users.csv', sep='\t')
        if nb_error > 0 or nb_empty > 0:
            print(
                f'WARNING : Retrieved data are partial.\n{nb_error}/{len(list_urls) + 1} requests returned an error.\n{nb_empty}/{len(list_urls)} requests returned an empty response. \nTry to use filter to retrieve users or increase limit')
        return df_users

    def getSegments(self, name: str = None, tagNames: str = None, inclType: str = 'all', rsids_list: list = None,
                    sidFilter: list = None, extended_info: bool = False, format: str = "df", save: bool = False,
                    verbose: bool = False, **kwargs) -> JsonListOrDataFrameType:
        """
        Retrieve the list of segments. Returns a data frame. 
        Arguments:
            name : OPTIONAL : Filter to only include segments that contains the name (str)
            tagNames : OPTIONAL : Filter list to only include segments that contains one of the tags (string delimited with comma, can be list as well)
            inclType : OPTIONAL : type of segments to be retrieved.(str) Possible values: 
                - all : Default value (all segments possibles)
                - shared : shared segments
                - template : template segments
                - deleted : deleted segments
                - internal : internal segments
                - curatedItem : curated segments
            rsid_list : OPTIONAL : Filter list to only include segments tied to specified RSID list (list)
            sidFilter : OPTIONAL : Filter list to only include segments in the specified list (list)
            extended_info : OPTIONAL : additional segment metadata fields to include on response (bool : default False)
                if set to true, returns reportSuiteName, ownerFullName, modified, tags, compatibility, definition
            format : OPTIONAL : defined the format returned by the query. (Default df)
                possibe values : 
                    "df" : default value that return a dataframe
                    "raw": return a list of value. More or less what is return from server.
            save : OPTIONAL : If set to True, it will save the info in a csv file (bool : default False)
            verbose : OPTIONAL : If set to True, print some information

        Possible kwargs:
            limit : number of segments retrieved by request. default 500: Limited to 1000 by the AnalyticsAPI.

        NOTE : Segment Endpoint doesn't support multi-threading. Default to 500. 
        """
        limit = int(kwargs.get('limit', 500))
        params = {'includeType': 'all', 'limit': limit}
        if extended_info:
            params.update(
                {'expansion': 'reportSuiteName,ownerFullName,modified,tags,compatibility,definition,shares'})
        if name is not None:
            params.update({'name': str(name)})
        if tagNames is not None:
            if type(tagNames) == list:
                tagNames = ','.join(tagNames)
            params.update({'tagNames': tagNames})
        if inclType != 'all':
            params['includeType'] = inclType
        if rsids_list is not None:
            if type(rsids_list) == list:
                rsids_list = ','.join(rsids_list)
            params.update({'rsids': rsids_list})
        if sidFilter is not None:
            if type(sidFilter) == list:
                sidFilter = ','.join(sidFilter)
            params.update({'rsids': sidFilter})
        data = []
        lastPage = False
        page_nb = 0
        if verbose:
            print("Starting requesting segments")
        while not lastPage:
            params['page'] = page_nb
            segs = self.connector.getData(self.endpoint_company +
                                          self._getSegments, params=params, headers=self.header)
            data += segs['content']
            lastPage = segs['lastPage']
            page_nb += 1
            if verbose and page_nb % 10 == 0:
                print(f"request #{page_nb / 10}")
        if format == "df":
            segments = pd.DataFrame(data)
        else:
            segments = data
        if save and format == "df":
            segments.to_csv('segments.csv', sep='\t')
            if verbose:
                print(
                    f'Saving data in file : {os.getcwd()}{os.sep}segments.csv')
        return segments

    def getSegment(self, segment_id: str = None,full:bool=False, *args) -> dict:
        """
        Get a specific segment from the ID. Returns the object of the segment.
        Arguments:
            segment_id : REQUIRED : the segment id to retrieve.
            full : OPTIONAL : Add all possible options
        Possible args:
            - "reportSuiteName" : string : to retrieve reportSuite attached to the segment
            - "ownerFullName" : string : to retrieve ownerFullName attached to the segment
            - "modified" : string : to retrieve when segment was modified
            - "tags" : string : to retrieve tags attached to the segment
            - "compatibility" : string : to retrieve which tool is compatible
            - "definition" : string : definition of the segment
            - "publishingStatus" : string : status for the segment
            - "definitionLastModified" : string : last definition of the segment
            - "categories" : string : categories of the segment
        """
        ValidArgs = ["reportSuiteName", "ownerFullName", "modified", "tags", "compatibility",
                     "definition", "publishingStatus", "publishingStatus", "definitionLastModified", "categories"]
        if segment_id is None:
            raise Exception("Expected a segment id")
        path = f"/segments/{segment_id}"
        for element in args:
            if element not in ValidArgs:
                args.remove(element)
        params = {'expansion': ','.join(args)}
        if full:
            params = {'expansion': ','.join(ValidArgs)}
        res = self.connector.getData(self.endpoint_company + path, params=params, headers=self.header)
        return res
    
    def scanSegment(self,segment:Union[str,dict],verbose:bool=False)->dict:
        """
        Return the dimensions, metrics and reportSuite used and the main scope of the segment.
        Arguments:
            segment : REQUIRED : either the ID of the segment or the full definition.
            verbose : OPTIONAL : print some comment.
        """
        if type(segment) == str:
            if verbose:
                print('retrieving segment definition')
            defSegment = self.getSegment(segment,full=True)
        elif type(segment) == dict:
            defSegment = deepcopy(segment)
            if 'definition' not in defSegment.keys():
                raise KeyError('missing "definition" key ')
            if verbose:
                print('copied segment definition')
        mydef = str(defSegment['definition'])
        dimensions : list = re.findall("'(variables/.+?)'",mydef)
        metrics : list = re.findall("'(metrics/.+?)'",mydef)
        reportSuite = defSegment['rsid']
        scope = re.search("'context': '(.+)'}[^'context']+",mydef)
        res = {
            'dimensions' : set(dimensions) if len(dimensions)>0 else {},
            'metrics' : set(metrics) if len(metrics)>0 else {},
            'rsid' : reportSuite,
            'scope' : scope.group(1)
        }
        return res

    def createSegment(self, segmentJSON: dict = None) -> dict:
        """
        Method that creates a new segment based on the dictionary passed to it.
        Arguments:
            segmentJSON : REQUIRED : the dictionary that represents the JSON statement for the segment.
            More information at this address <https://adobedocs.github.io/analytics-2.0-apis/#/segments/segments_createSegment>
        """
        if segmentJSON is None:
            print('No segment data has been pushed')
            return None
        data = deepcopy(segmentJSON)
        seg = self.connector.postData(
            self.endpoint_company + self._getSegments,
            data=data,
            headers=self.header
        )
        return seg
    
    def createSegmentValidate(self, segmentJSON: dict = None) -> object:
        """
        Method that validate a new segment based on the dictionary passed to it.
        Arguments:
            segmentJSON : REQUIRED : the dictionary that represents the JSON statement for the segment.
            More information at this address <https://adobedocs.github.io/analytics-2.0-apis/#/segments/segments_createSegment>
        """
        if segmentJSON is None:
            print('No segment data has been pushed')
            return None
        data = deepcopy(segmentJSON)
        path = "/segments/validate"
        seg = self.connector.postData(self.endpoint_company +path,data=data)
        return seg

    def updateSegment(self, segmentID: str = None, segmentJSON: dict = None) -> object:
        """
        Method that updates a specific segment based on the dictionary passed to it.
        Arguments:
            segmentID : REQUIRED : Segment ID to be updated
            segmentJSON : REQUIRED : the dictionary that represents the JSON statement for the segment. 
        """
        if segmentJSON is None or segmentID is None:
            print('No segment or segmentID data has been pushed')
            return None
        data = deepcopy(segmentJSON)
        seg = self.connector.putData(
            self.endpoint_company + self._getSegments + '/' + segmentID,
            data=data,
            headers=self.header
        )
        return seg

    def deleteSegment(self, segmentID: str = None) -> object:
        """
        Method that updates a specific segment based on the dictionary passed to it.
        Arguments:
            segmentID : REQUIRED : Segment ID to be deleted
        """
        if segmentID is None:
            print('No segmentID data has been pushed')
            return None
        seg = self.connector.deleteData(self.endpoint_company +
                                        self._getSegments + '/' + segmentID, headers=self.header)
        return seg

    def getCalculatedMetrics(
            self,
            name: str = None,
            tagNames: str = None,
            inclType: str = 'all',
            rsids_list: list = None,
            extended_info: bool = False,
            save=False,
            format:str='df',
            **kwargs
    ) -> pd.DataFrame:
        """
        Retrieve the list of calculated metrics. Returns a data frame. 
        Arguments:
            name : OPTIONAL : Filter to only include calculated metrics that contains the name (str)
            tagNames : OPTIONAL : Filter list to only include calculated metrics that contains one of the tags (string delimited with comma, can be list as well)
            inclType : OPTIONAL : type of calculated Metrics to be retrieved. (str) Possible values: 
                - all : Default value (all calculated metrics possibles)
                - shared : shared calculated metrics
                - template : template calculated metrics
            rsid_list : OPTIONAL : Filter list to only include segments tied to specified RSID list (list)
            extended_info : OPTIONAL : additional segment metadata fields to include on response (list)
                additional infos: reportSuiteName,definition, ownerFullName, modified, tags, compatibility
            save : OPTIONAL : If set to True, it will save the info in a csv file (Default False)
            format : OPTIONAL : format of the output. 2 values "df" for dataframe and "raw" for raw json.
        Possible kwargs:
            limit : number of segments retrieved by request. default 500: Limited to 1000 by the AnalyticsAPI.(int)
        """
        limit = int(kwargs.get('limit', 500))
        params = {'includeType': inclType, 'limit': limit}
        if name is not None:
            params.update({'name': str(name)})
        if tagNames is not None:
            if type(tagNames) == list:
                tagNames = ','.join(tagNames)
            params.update({'tagNames': tagNames})
        if inclType != 'all':
            params['includeType'] = inclType
        if rsids_list is not None:
            if type(rsids_list) == list:
                rsids_list = ','.join(rsids_list)
            params.update({'rsids': rsids_list})
        if extended_info:
            params.update(
                {'expansion': 'reportSuiteName,definition,ownerFullName,modified,tags,categories,compatibility,shares'})
        metrics = self.connector.getData(self.endpoint_company +
                                         self._getCalcMetrics, params=params)
        data = metrics['content']
        lastPage = metrics['lastPage']
        if not lastPage:  # check if lastpage is inversed of False
            page_nb = 0
            while not lastPage:
                page_nb += 1
                params['page'] = page_nb
                metrics = self.connector.getData(self.endpoint_company +
                                                 self._getCalcMetrics, params=params, headers=self.header)
                data += metrics['content']
                lastPage = metrics['lastPage']
        if format == "raw":
            if save:
                with open('calculated_metrics.json','w') as f:
                    f.write(json.dumps(data,indent=4))
            return data
        df_calc_metrics = pd.DataFrame(data)
        if save:
            df_calc_metrics.to_csv('calculated_metrics.csv', sep='\t')
        return df_calc_metrics

    def getCalculatedMetric(self,calculatedMetricId:str=None,full:bool=True)->dict:
        """
        Return a dictionary on the calculated metrics requested.
        Arguments:
            calculatedMetricId : REQUIRED : The calculated metric ID to be retrieved.
            full : OPTIONAL : additional segment metadata fields to include on response (list)
                additional infos: reportSuiteName,definition, ownerFullName, modified, tags, compatibility
        """
        if calculatedMetricId is None:
            raise ValueError("Require a calculated metrics ID")
        params = {}
        if full:
            params.update({'expansion': 'reportSuiteName,definition,ownerFullName,modified,tags,categories,compatibility'})
        path = f"/calculatedmetrics/{calculatedMetricId}"
        res = self.connector.getData(self.endpoint_company+path,params=params)
        return res
    
    def scanCalculatedMetric(self,calculatedMetric:Union[str,dict],verbose:bool=False)->dict:
        """
        Return a dictionary of metrics and dimensions used in the calculated metrics.
        """
        if type(calculatedMetric) == str:
            if verbose:
                print('retrieving calculated metrics definition')
            cm = self.getCalculatedMetric(calculatedMetric,full=True)
        elif type(calculatedMetric) == dict:
            cm = deepcopy(calculatedMetric)
            if 'definition' not in cm.keys():
                raise KeyError('missing "definition" key')
            if verbose:
                print('copied calculated metrics definition')
        mydef = str(cm['definition'])
        segments:list = cm['compatibility']['segments']
        res = {"dimensions":[],'metrics':[]}
        for segment in segments:
            if verbose:
                print(f"retrieving segment {segment} definition")
            tmp:dict = self.scanSegment(segment)
            res['dimensions'] += [dim for dim in tmp['dimensions']]
            res['metrics'] += [met for met in tmp['metrics']]
        metrics : list = re.findall("'(metrics/.+?)'",mydef)
        res['metrics'] += metrics
        res['rsid'] = cm['rsid']
        res['metrics'] = set(res['metrics']) if len(res['metrics'])>0 else {}
        res['dimensions'] = set(res['dimensions']) if len(res['dimensions'])>0 else {}
        return res


    def createCalculatedMetric(self, metricJSON: dict = None) -> dict:
        """
        Method that create a specific calculated metric based on the dictionary passed to it.
        Arguments:
            metricJSON : REQUIRED : Calculated Metrics information to create. (Required: name, definition, rsid)
            More information can be found at this address https://adobedocs.github.io/analytics-2.0-apis/#/calculatedmetrics/calculatedmetrics_createCalculatedMetric
        """
        if metricJSON is None or type(metricJSON) != dict:
            raise Exception(
                "Expected a dictionary to create the calculated metrics")
        if 'name' not in metricJSON.keys() or 'definition' not in metricJSON.keys() or 'rsid' not in metricJSON.keys():
            raise KeyError(
                'Expected "name", "definition" and "rsid" in the data')
        cm = self.connector.postData(self.endpoint_company +
                                     self._getCalcMetrics, headers=self.header, data=metricJSON)
        return cm
    
    def createCalculatedMetricValidate(self,metricJSON: dict=None)->dict:
        """
        Method that validate a specific calculated metrics definition based on the dictionary passed to it.
        Arguments:
            metricJSON : REQUIRED : Calculated Metrics information to create. (Required: name, definition, rsid)
            More information can be found at this address https://adobedocs.github.io/analytics-2.0-apis/#/calculatedmetrics/calculatedmetrics_createCalculatedMetric
        """
        if metricJSON is None or type(metricJSON) != dict:
            raise Exception(
                "Expected a dictionary to create the calculated metrics")
        if 'name' not in metricJSON.keys() or 'definition' not in metricJSON.keys() or 'rsid' not in metricJSON.keys():
            raise KeyError(
                'Expected "name", "definition" and "rsid" in the data')
        path = "/calculatedmetrics/validate"
        cm = self.connector.postData(self.endpoint_company+path, data=metricJSON)
        return cm

    def updateCalculatedMetric(self, calcID: str = None, calcJSON: dict = None) -> object:
        """
        Method that updates a specific Calculated Metrics based on the dictionary passed to it.
        Arguments:
            calcID : REQUIRED : Calculated Metric ID to be updated
            calcJSON : REQUIRED : the dictionary that represents the JSON statement for the calculated metric.
        """
        if calcJSON is None or calcID is None:
            print('No calcMetric or calcMetric JSON data has been pushed')
            return None
        data = deepcopy(calcJSON)
        cm = self.connector.putData(
            self.endpoint_company + self._getCalcMetrics + '/' + calcID,
            data=data,
            headers=self.header
        )
        return cm

    def deleteCalculatedMetric(self, calcID: str = None) -> object:
        """
        Method that delete a specific calculated metrics based on the id passed..
        Arguments:
            calcID : REQUIRED : Calculated Metrics ID to be deleted
        """
        if calcID is None:
            print('No calculated metrics data has been pushed')
            return None
        cm = self.connector.deleteData(
            self.endpoint_company + self._getCalcMetrics + '/' + calcID,
            headers=self.header
        )
        return cm

    def getDateRanges(self, extended_info: bool = False, save: bool = False, includeType: str = 'all',verbose:bool=False,
                      **kwargs) -> pd.DataFrame:
        """
        Get the list of date ranges available for the user.
        Arguments:
            extended_info : OPTIONAL : additional segment metadata fields to include on response
                additional infos: reportSuiteName, ownerFullName, modified, tags, compatibility, definition
            save : OPTIONAL : If set to True, it will save the info in a csv file (Default False)
            includeType : Include additional date ranges not owned by user. The "all" option takes precedence over "shared"
                Possible values are all, shared, templates. You can add all of them as comma separated string. 
        Possible kwargs:
            limit : number of segments retrieved by request. default 500: Limited to 1000 by the AnalyticsAPI.
            full : Boolean : Doesn't shrink the number of columns if set to true
        """
        limit = int(kwargs.get('limit', 500))
        includeType = includeType.split(',')
        params = {'limit': limit, 'includeType': includeType}
        if extended_info:
            params.update(
                {'expansion': 'definition,ownerFullName,modified,tags'})
        dateRanges = self.connector.getData(
            self.endpoint_company + self._getDateRanges,
            params=params,
            headers=self.header,
            verbose=verbose
        )
        data = dateRanges['content']
        df_dates = pd.DataFrame(data)
        if save:
            df_dates.to_csv('date_range.csv', index=False)
        return df_dates

    def updateDateRange(self, dateRangeID: str = None, dateRangeJSON: dict = None) -> object:
        """
        Method that updates a specific Date Range based on the dictionary passed to it.
        Arguments:
            dateRangeID : REQUIRED : Calculated Metric ID to be updated
            dateRangeJSON : REQUIRED : the dictionary that represents the JSON statement for the calculated metric.
        """
        if dateRangeJSON is None or dateRangeID is None:
            print('No calcMetric or calcMetric JSON data has been pushed')
            return None
        data = deepcopy(dateRangeJSON)
        dr = self.connector.putData(
            self.endpoint_company + self._getDateRanges + '/' + dateRangeID,
            data=data,
            headers=self.header
        )
        return dr

    def getCalculatedFunctions(self, **kwargs) -> pd.DataFrame:
        """
        Returns the calculated metrics functions.
        """
        path = "/calculatedmetrics/functions"
        limit = int(kwargs.get('limit', 500))
        params = {'limit': limit}
        funcs = self.connector.getData(
            self.endpoint_company + path,
            params=params,
            headers=self.header
        )
        df = pd.DataFrame(funcs)
        return df

    def getTags(self, limit: int = 100, **kwargs) -> list:
        """
        Return the list of tags
        Arguments:
            limit : OPTIONAL : Amount of tag to be returned by request. Default 100
        """
        path = "/componentmetadata/tags"
        params = {'limit': limit}
        if kwargs.get('page', False):
            params['page'] = kwargs.get('page', 0)
        res = self.connector.getData(self.endpoint_company + path, params=params, headers=self.header)
        data = res['content']
        if not res['lastPage']:
            page = res['number'] + 1
            data += self.getTags(limit=limit, page=page)
        return data

    def getTag(self, tagId: str = None) -> dict:
        """
        Return the a tag by its ID.
        Arguments:
            tagId : REQUIRED : the Tag ID to be retrieved.
        """
        if tagId is None:
            raise Exception("Require a tag ID for this method.")
        path = f"/componentmetadata/tags/{tagId}"
        res = self.connector.getData(self.endpoint_company + path, headers=self.header)
        return res

    def getComponentTagName(self, tagNames: str = None, componentType: str = None) -> dict:
        """
        Given a comma separated list of tag names, return component ids associated with them.
        Arguments:
            tagNames : REQUIRED : Comma separated list of tag names.
            componentType : REQUIRED : The component type to operate on.
                Available values : segment, dashboard, bookmark, calculatedMetric, project, dateRange, metric, dimension, virtualReportSuite, scheduledJob, alert, classificationSet
        """
        path = "/componentmetadata/tags/tagnames"
        if tagNames is None:
            raise Exception("Requires tag names to be provided")
        if componentType is None:
            raise Exception("Requires a Component Type to be provided")
        params = {
            "tagNames": tagNames,
            "componentType": componentType
        }
        res = self.connector.getData(self.endpoint_company + path, params=params, headers=self.header)
        return res

    def searchComponentsTags(self, componentType: str = None, componentIds: list = None) -> dict:
        """
        Search for the tags of a list of component by their ids.
        Arguments:
            componentType : REQUIRED : The component type to use in the search.
                Available values : segment, dashboard, bookmark, calculatedMetric, project, dateRange, metric, dimension, virtualReportSuite, scheduledJob, alert, classificationSet
            componentIds : REQUIRED : List of components Ids to use.
        """
        if componentType is None:
            raise Exception("ComponentType is required")
        if componentIds is None or type(componentIds) != list:
            raise Exception("componentIds is required as a list of ids")
        path = "/componentmetadata/tags/component/search"
        obj = {
            "componentType": componentType,
            "componentIds": componentIds
        }
        res = self.connector.postData(self.endpoint_company + path, data=obj, headers=self.header)
        return res

    def createTags(self, data: list = None) -> dict:
        """
        Create a new tag and applies that new tag to the passed components.
        Arguments:
            data : REQUIRED : list of the tag to be created with their component relation.
        
        Example of data :
        [
            {
                "id": 0,
                "name": "string",
                "description": "string",
                "components": [
                {
                    "componentType": "string",
                    "componentId": "string",
                    "tags": [
                    "Unknown Type: Tag"
                    ]
                }
                ]
            }
        ]

        """
        if data is None:
            raise Exception("Requires a list of tags to be created")
        path = "​/componentmetadata​/tags"
        res = self.connector.postData(self.endpoint_company + path, data=data, headers=self.header)
        return res

    def deleteTags(self, componentType: str = None, componentIds: str = None) -> str:
        """
        Delete all tags from the component Type and the component ids specified.
        Arguments:
            componentIds : REQUIRED : the Comma-separated list of componentIds to operate on.
            componentType : REQUIRED : The component type to operate on.
                Available values : segment, dashboard, bookmark, calculatedMetric, project, dateRange, metric, dimension, virtualReportSuite, scheduledJob, alert, classificationSet
        """
        if componentType is None:
            raise Exception("require a component type")
        if componentIds is None:
            raise Exception("require component ID(s)")
        path = "/componentmetadata/tags"
        params = {
            "componentType": componentType,
            "componentIds": componentIds
        }
        res = self.connector.deleteData(self.endpoint_company + path, params=params, headers=self.header)
        return res

    def deleteTag(self, tagId: str = None) -> str:
        """
        Delete a Tag based on its id.
        Arguments:
            tagId : REQUIRED : The tag ID to be deleted.
        """
        if tagId is None:
            raise Exception("A tag ID is required")
        path = "​/componentmetadata​/tags​/{tagId}"
        res = self.connector.deleteData(self.endpoint_company + path, headers=self.header)
        return res

    def getComponentTags(self, componentId: str = None, componentType: str = None) -> list:
        """
        Given a componentId, return all tags associated with that component.
        Arguments:
            componentId : REQUIRED : The componentId to operate on. Currently this is just the segmentId.
            componentType : REQUIRED : The component type to operate on.
                segment, dashboard, bookmark, calculatedMetric, project, dateRange, metric, dimension, virtualReportSuite, scheduledJob, alert, classificationSet
        """
        path = "/componentmetadata/tags/search"
        if componentType is None:
            raise Exception("require a component type")
        if componentId is None:
            raise Exception("require a component ID")
        params = {"componentId": componentId, "componentType": componentType}
        res = self.connector.getData(self.endpoint_company + path, params=params, headers=self.header)
        return res

    def updateComponentTags(self, data: list = None):
        """
        Overwrite the component Tags with the list send.
        Arguments:
            data : REQUIRED : list of the components to be udpated with their respective list of tag names.

        Object looks like the following:
        [
            {
                "componentType": "string",
                "componentId": "string",
                "tags": [
                    "Unknown Type: Tag"
                ]
            }
        ]
        """
        if data is None or type(data) != list:
            raise Exception("require list of update to be sent.")
        path = "/componentmetadata/tags/tagitems"
        res = self.connector.putData(self.endpoint_company + path, data=data, headers=self.header)
        return res

    def getProjects(self, includeType: str = 'all', full: bool = False, limit: int = None, includeShared: bool = False,
                    includeTemplate: bool = False, format: str = 'df', cache:bool=False, save: bool = False) -> JsonListOrDataFrameType:
        """
        Returns the list of projects through either a dataframe or a list.
        Arguments:
            includeType : OPTIONAL : type of projects to be retrieved.(str) Possible values: 
                - all : Default value (all projects possibles)
                - shared : shared projects
            full : OPTIONAL : if set to True, returns all information about projects.
            limit : OPTIONAL : Limit the number of result returned.
            includeShared : OPTIONAL : If full is set to False, you can retrieve only information about sharing.
            includeTemplate: OPTIONAL : If full is set to False, you can add information about template here.
            format : OPTIONAL : format : OPTIONAL : format of the output. 2 values "df" for dataframe (default) and "raw" for raw json.
            cache : OPTIONAL : Boolean in case you want to cache the result in the "listProjectIds" attribute.
            save : OPTIONAL : If set to True, it will save the info in a csv file (bool : default False)
        """
        path = "/projects"
        params = {"includeType": includeType}
        if full:
            params[
                "expansion"] = 'reportSuiteName,ownerFullName,tags,shares,sharesFullName,modified,favorite,approved,companyTemplate,externalReferences,accessLevel'
        else:
            params["expansion"] = "ownerFullName,modified"
            if includeShared:
                params["expansion"] += ',shares,sharesFullName'
            if includeTemplate:
                params["expansion"] += ',companyTemplate'
        if limit is not None:
            params['limit'] = limit
        res = self.connector.getData(self.endpoint_company + path, params=params, headers=self.header)
        if cache:
            self.listProjectIds = res
        if format == "raw":
            if save:
                with open('projects.json', 'w') as f:
                    f.write(json.dumps(res, indent=2))
            return res
        df = pd.DataFrame(res)
        if df.empty == False:
            df['created'] = pd.to_datetime(df['created'], format='%Y-%m-%dT%H:%M:%SZ')
            df['modified'] = pd.to_datetime(df['modified'], format='%Y-%m-%dT%H:%M:%SZ')
        if save:
            df.to_csv('projects.csv', index=False)
        return df

    def getProject(self, projectId: str = None, projectClass: bool = False, rsidSuffix: bool = False, retry: int = 0, cache:bool=False, verbose: bool = False) -> Union[dict,Project]:
        """
        Return the dictionary of the project information and its definition.
        It will return a dictionary or a Project class.
        The project detail will be saved as Project class in the projectsDetails class attribute.
        Arguments:
            projectId : REQUIRED : the project ID to be retrieved.
            projectClass : OPTIONAL : if set to True. Returns a class of the project with prefiltered information
            rsidSuffix : OPTIONAL : if set to True, returns project class with rsid as suffic to dimensions and metrics.
            retry : OPTIONAL : If you want to retry the request if it fails. Specify number of retry (0 default)
            cache : OPTIONAL : If you want to cache the result as Project class in the "projectsDetails" attribute.
            verbose : OPTIONAL : If you wish to have logs of status
        """
        if projectId is None:
            raise Exception("Requires a projectId parameter")
        params = {
            'expansion': 'definition,ownerFullName,modified,favorite,approved,tags,shares,sharesFullName,reportSuiteName,companyTemplate,accessLevel'}
        path = f"/projects/{projectId}"
        res = self.connector.getData(self.endpoint_company + path, params=params, headers=self.header,retry=retry, verbose=verbose)
        if projectClass:
            if verbose:
                print('building an instance of Project class')
            myProject = Project(res,rsidSuffix=rsidSuffix)
            return myProject
        if cache:
            try:
                self.projectsDetails[projectId] = Project(res)
            except:
                if verbose:
                    print('WARNING : Cannot convert Project to Project class')
        return res
    
    def getAllProjectDetails(self, projects:JsonListOrDataFrameType=None, filterNameProject:str=None, filterNameOwner:str=None, useAttribute:bool=True, cache:bool=False, rsidSuffix:bool=False, verbose:bool=False)->dict:
        """
        Retrieve all projects details. You can either pass the list of dataframe returned from the getProjects methods and some filters.
        Returns a dict of ProjectId and the value is the Project class for analysis.
        Arguments:
            projects : OPTIONAL : Takes the type of object returned from the getProjects (all data - not only the ID).
                    If None is provided and you never ran the getProjects method, we will call the getProjects method and retrieve the elements.
                    Otherwise you can pass either a limited list of elements that you want to check details for.
            filterNameProject : OPTIONAL : If you want to retrieve project details for project with a specific string in their name.
            filterNameOwner : OPTIONAL : If you want to retrieve project details for project with an owner having a specific name.
            useAttribute : OPTIONAL : True by default, it will use the projectList saved in the listProjectIds attribute.
                If you want to start from scratch on the retrieval process of your projects.
            rsidSuffix : OPTIONAL : If you want to add rsid as suffix of metrics and dimension (::rsid)
            cache : OPTIONAL : If you want to cache the different elements retrieved for future usage.
            verbose : OPTIONAL : Set to True to print information.
        Not using filter may end up taking a while to retrieve the information.
        """
        ## if no project data
        if projects is None:
            if len(self.listProjectIds)>0 and useAttribute:
                fullProjectIds = self.listProjectIds
            else:
                fullProjectIds = self.getProjects(format='raw',cache=cache)
        ## if project data is passed
        elif projects is not None:
            if isinstance(projects,pd.DataFrame):
                fullProjectIds = projects.to_dict(orient='records')
            elif isinstance(projects,list):
                fullProjectIds = (proj['id'] for proj in projects)
        if filterNameProject is not None:
                fullProjectIds = [project for project in fullProjectIds if filterNameProject in project['name']]
        if filterNameOwner is not None:
                fullProjectIds = [project for project in fullProjectIds if filterNameOwner in project['owner'].get('name','')]
        if verbose:
            print(f'{len(fullProjectIds)} project details to retrieve')
            print(f"estimated time required : {int(len(fullProjectIds)/60)} minutes")
        projectIds = (project['id'] for project in fullProjectIds)
        projectsDetails = {projectId:self.getProject(projectId,projectClass=True,rsidSuffix=rsidSuffix) for projectId in projectIds}
        if filterNameProject is None and filterNameOwner is None:
            self.projectsDetails = projectsDetails
        return projectsDetails

    def deleteProject(self, projectId: str = None) -> dict:
        """
        Delete the project specified by its ID.
        Arguments:
            projectId : REQUIRED : the project ID to be deleted.
        """
        if projectId is None:
            raise Exception("Requires a projectId parameter")
        path = f"/projects/{projectId}"
        res = self.connector.deleteData(self.endpoint_company + path, headers=self.header)
        return res

    def updateProject(self, projectId: str = None, projectObj: dict = None) -> dict:
        """
        Update your project with the new object placed as parameter.
        Arguments:
            projectId : REQUIRED : the project ID to be updated.
            projectObj : REQUIRED : the dictionary to replace the previous Workspace.
                requires the following elements: name,description,rsid, definition, owner
        """
        if projectId is None:
            raise Exception("Requires a projectId parameter")
        path = f"/projects/{projectId}"
        if projectObj is None:
            raise Exception("Requires a projectId parameter")
        if 'name' not in projectObj.keys():
            raise KeyError("Requires name key in the project object")
        if 'description' not in projectObj.keys():
            raise KeyError("Requires description key in the project object")
        if 'rsid' not in projectObj.keys():
            raise KeyError("Requires rsid key in the project object")
        if 'owner' not in projectObj.keys():
            raise KeyError("Requires owner key in the project object")
        if type(projectObj['owner']) != dict:
            raise ValueError("Requires owner key to be a dictionary")
        if 'definition' not in projectObj.keys():
            raise KeyError("Requires definition key in the project object")
        if type(projectObj['definition']) != dict:
            raise ValueError("Requires definition key to be a dictionary")
        res = self.connector.putData(self.endpoint_company + path, data=projectObj, headers=self.header)
        return res


    def createProject(self, projectObj: dict = None) -> dict:
        """
        Create a project based on the definition you have set.
        Arguments:
            projectObj : REQUIRED : the dictionary to create a new Workspace.
                requires the following elements: name,description,rsid, definition, owner
        """
        path = "/projects/"
        if projectObj is None:
            raise Exception("Requires a projectId parameter")
        if 'name' not in projectObj.keys():
            raise KeyError("Requires name key in the project object")
        if 'description' not in projectObj.keys():
            raise KeyError("Requires description key in the project object")
        if 'rsid' not in projectObj.keys():
            raise KeyError("Requires rsid key in the project object")
        if 'owner' not in projectObj.keys():
            raise KeyError("Requires owner key in the project object")
        if type(projectObj['owner']) != dict:
            raise ValueError("Requires owner key to be a dictionary")
        if 'definition' not in projectObj.keys():
            raise KeyError("Requires definition key in the project object")
        if type(projectObj['definition']) != dict:
            raise ValueError("Requires definition key to be a dictionary")
        res = self.connector.postData(self.endpoint_company + path, data=projectObj, headers=self.header)
        return res
    
    def findComponentsUsage(self,components:list=None,
                            projectDetails:list=None,
                            segments:Union[list,pd.DataFrame]=None,
                            calculatedMetrics:Union[list,pd.DataFrame]=None,
                            recursive:bool=False,
                            regexUsed:bool=False,
                            verbose:bool=False,
                            resetProjectDetails:bool=False,
                            rsidPrefix:bool=False,
                            )->dict:
        """
        Find the usage of components in the different part of Adobe Analytics setup.
        Projects, Segment, Calculated metrics.
        Arguments:
            components : REQUIRED : list of component to look for.
                        Example : evar10,event1,prop3,segmentId, calculatedMetricsId
            ProjectDetails: OPTIONAL : list of project details.
            segments : OPTIONAL : If you wish to pass the segments to look for. (should contain definition)
            calculatedMetrics : OPTIONAL : If you wish to pass the segments to look for. (should contain definition)
            recursive : OPTIONAL : if set to True, will also find the reference where the meta component are used.
                segments based on your elements will also be searched to see where they are located.
            regexUsed : OPTIONAL : If set to True, the element are definied as a regex and some default setup is turned off.
            resetProjectDetails : OPTIONAL : Set to false by default. If set to True, it will NOT use the cache.
            rsidPrefix : OPTIONAL : If you do not give projectDetails and you want to look for rsid usage in report for dimensions and metrics.
        """
        listComponentProp = [comp for comp in components if 'prop' in comp]
        listComponentVar = [comp for comp in components if 'evar' in comp]
        listComponentEvent = [comp for comp in components if 'event' in comp]
        listComponentSegs = [comp for comp in components if comp.startswith('s')]
        listComponentCalcs = [comp for comp in components if comp.startswith('cm')]
        restComponents = set(components) - set(listComponentProp+listComponentVar+listComponentEvent+listComponentSegs+listComponentCalcs)
        listDefaultElements = [comp for comp in restComponents]
        listRecusion = []
        ## adding unregular ones
        regPartSeg = "('|\.)" ## ensure to not catch evar100 for evar10
        regPartPro = "($|\.)" ## ensure to not catch evar100 for evar10
        if regexUsed:
            regPartSeg = ""
            regPartPro = ""
        if verbose:
            print('retrieving segments')
        if len(self.segments) == 0 and segments is None:
            self.segments = self.getSegments(extended_info=True)
            mySegments = self.segments
        elif len(self.segments) > 0 and segments is None:
            mySegments = self.segments
        elif segments is not None:
            if type(segments) == list:
                mySegments = pd.DataFrame(segments)
        else:
            mySegments = segments
        if verbose:
            print('retrieving calculated metrics')
        if len(self.calculatedMetrics) == 0 and calculatedMetrics is None:
            self.calculatedMetrics = self.getCalculatedMetrics(extended_info=True)
            myMetrics = self.calculatedMetrics
        elif len(self.segments) > 0 and calculatedMetrics is None:
            myMetrics = self.calculatedMetrics
        elif calculatedMetrics is not None:
            if type(calculatedMetrics) == list:
                myMetrics = pd.DataFrame(calculatedMetrics)
        else:
            myMetrics = calculatedMetrics
        if (len(self.projectsDetails) == 0 and projectDetails is None) or resetProjectDetails:
            if verbose:
                print('retrieving projects details - long process')
            self.projectDetails = self.getAllProjectDetails(verbose=verbose,rsidPrefix=rsidPrefix)
            myProjectDetails = (self.projectsDetails[key].to_dict() for key in self.projectsDetails)
        elif len(self.projectsDetails) > 0 and projectDetails is None and resetProjectDetails==False:
            if verbose:
                print('transforming projects details')
            myProjectDetails = (self.projectsDetails[key].to_dict() for key in self.projectsDetails)
        elif projectDetails is not None:
            if verbose:
                print('setting the project details')
            if isinstance(projectDetails[0],Project):
                myProjectDetails = (item.to_dict() for item in projectDetails)
            elif isinstance(projectDetails[0],dict):
                myProjectDetails = (Project(item).to_dict() for item in projectDetails)
        else:
            raise Exception("Project details were not able to be processed")
        returnObj = {element : {'segments':[],'calculatedMetrics':[],'projects':[]} for element in components}
        recurseObj = defaultdict(list)
        if verbose:
            print('search started')
            print(f'recursive option : {recursive}')
            print('start looking into segments')
        for _,seg in mySegments.iterrows():
            for prop in listComponentProp:
                if re.search(f"{prop+regPartSeg}",str(seg['definition'])):
                    returnObj[prop]['segments'].append({seg['name']:seg['id']})
                    if recursive:
                        listRecusion.append(seg['id'])
            for var in listComponentVar:
                if re.search(f"{var+regPartSeg}",str(seg['definition'])):
                    returnObj[var]['segments'].append({seg['name']:seg['id']})
                    if recursive:
                        listRecusion.append(seg['id'])
            for event in listComponentEvent:
                if re.search(f"{event}'",str(seg['definition'])):
                    returnObj[event]['segments'].append({seg['name']:seg['id']})
                    if recursive:
                        listRecusion.append(seg['id'])
            for element in listDefaultElements:
                if re.search(f"{element}",str(seg['definition'])):
                    returnObj[element]['segments'].append({seg['name']:seg['id']})
                    if recursive:
                        listRecusion.append(seg['id'])
        if verbose:
            print('start looking into calculated metrics')
        for _,met in myMetrics.iterrows():
            for prop in listComponentProp:
                if re.search(f"{prop+regPartSeg}",str(met['definition'])):
                    returnObj[prop]['calculatedMetrics'].append({met['name']:met['id']})
                    if recursive:
                        listRecusion.append(met['id'])
            for var in listComponentVar:
                if re.search(f"{var+regPartSeg}",str(met['definition'])):
                    returnObj[var]['calculatedMetrics'].append({met['name']:met['id']})
                    if recursive:
                        listRecusion.append(met['id'])
            for event in listComponentEvent:
                if re.search(f"{event}'",str(met['definition'])):
                    returnObj[event]['calculatedMetrics'].append({met['name']:met['id']})
                    if recursive:
                        listRecusion.append(met['id'])
            for element in listDefaultElements:
                if re.search(f"{element}'",str(met['definition'])):
                    returnObj[element]['calculatedMetrics'].append({met['name']:met['id']})
                    if recursive:
                        listRecusion.append(met['id'])
        if verbose:
            print('start looking into projects')
        for proj in myProjectDetails:
            ## mobile reports don't have dimensions.
            if proj['reportType'] == "desktop":
                for prop in listComponentProp:
                    for element in proj['dimensions']:
                        if re.search(f"{prop+regPartPro}",element):
                            returnObj[prop]['projects'].append({proj['name']:proj['id']})
                for var in listComponentVar:
                    for element in proj['dimensions']:
                        if re.search(f"{var+regPartPro}",element):
                            returnObj[var]['projects'].append({proj['name']:proj['id']})
                for event in listComponentEvent:
                    for element in proj['metrics']:
                        if re.search(f"{event}",element):
                            returnObj[event]['projects'].append({proj['name']:proj['id']})
                for seg in listComponentSegs:
                    for element in proj['segments']:
                        if re.search(f"{seg}",element):
                            returnObj[seg]['projects'].append({proj['name']:proj['id']})
                for met in listComponentCalcs:
                    for element in proj['calculatedMetrics']:
                        if re.search(f"{met}",element):
                            returnObj[met]['projects'].append({proj['name']:proj['id']})
                for element in listDefaultElements:
                    for met in proj['calculatedMetrics']:
                        if re.search(f"{element}",met):
                            returnObj[element]['projects'].append({proj['name']:proj['id']})
                    for dim in proj['dimensions']:
                        if re.search(f"{element}",dim):
                            returnObj[element]['projects'].append({proj['name']:proj['id']})
                    for rsid in proj['rsids']:
                        if re.search(f"{element}",rsid):
                            returnObj[element]['projects'].append({proj['name']:proj['id']})
                    for event in proj['metrics']:
                        if re.search(f"{element}",event):
                            returnObj[element]['projects'].append({proj['name']:proj['id']})
            if recursive:
                for rec in listRecusion:
                    for element in proj['segments']:
                        if re.search(f"{rec}",element):
                            recurseObj[rec].append({proj['name']:proj['id']})
                    for element in proj['calculatedMetrics']:
                        if re.search(f"{rec}",element):
                            recurseObj[rec].append({proj['name']:proj['id']})
        if recursive:
            returnObj['recursion'] = recurseObj
        if verbose:
            print('done')
        return returnObj
    
    def getUsageLogs(self,
        startDate:str=None,
        endDate:str=None,
        eventType:str=None,
        event:str=None,
        rsid:str=None,
        login:str=None,
        ip:str=None,
        limit:int=100,
        max_result:int=None,
        format:str="df",
        verbose:bool=False,
        **kwargs)->dict:
        """
        Returns the Audit Usage Logs from your company analytics setup.
        Arguments:
            startDate : REQUIRED : Start date, format : 2020-12-01T00:00:00-07.(default 3 month prior today)	
            endDate : REQUIRED : End date, format : 2020-12-15T14:32:33-07. (default today)
                Should be a maximum of a 3 month period between startDate and endDate.
            eventType : OPTIONAL : The numeric id for the event type you want to filter logs by. 
                Please reference the lookup table in the LOGS_EVENT_TYPE
            event : OPTIONAL : The event description you want to filter logs by. 
                No wildcards are permitted, but this filter is case insensitive and supports partial matches.
            rsid : OPTIONAL : ReportSuite ID to filter on.
            login : OPTIONAL : The login value of the user you want to filter logs by. This filter functions as an exact match.	
            ip : OPTIONAL : The IP address you want to filter logs by. This filter supports a partial match.	
            limit : OPTIONAL : Number of results per page.
            max_result : OPTIONAL : Number of maximum amount of results if you want. If you want to cap the process. Ex : max_result=1000
            format : OPTIONAL : If you wish to have a DataFrame ("df" - default) or list("raw") as output.
            verbose : OPTIONAL : Set it to True if you want to have console info.
        possible kwargs:
            page : page number (default 0)
        """
        import datetime
        now =  datetime.datetime.now()
        if startDate is None:
            startDate = datetime.datetime.isoformat(now - datetime.timedelta(weeks=4*3)).split('.')[0]
        if endDate is None:
            endDate = datetime.datetime.isoformat(now).split('.')[0]
        path = "/auditlogs/usage"
        params = {"page":kwargs.get('page',0),"limit":limit,"startDate":startDate,"endDate":endDate}
        if eventType is not None:
            params['eventType'] = eventType
        if event is not None:
            params['event'] = event
        if rsid is not None:
            params['rsid'] = rsid
        if login is not None:
            params['login'] = login
        if ip is not None:
            params['ip'] = ip
        if verbose:
            print("retrieving data with these parameters")
            print(json.dumps(params,indent=2))
        res = self.connector.getData(self.endpoint_company + path, params=params,verbose=verbose)
        data = res['content']
        lastPage = res['lastPage']
        while lastPage == False:
            params["page"] += 1
            print(f"fetching page{params['page']}")
            res = self.connector.getData(self.endpoint_company + path, params=params,verbose=verbose)
            data += res['content']
            lastPage = res['lastPage']
            if max_result is not None:
                if len(data) >= max_result:
                    lastPage = True
        if format == "df":
            df = pd.DataFrame(data)
            return df
        return data


    def getTopItems(self,rsid:str=None,dimension:str=None,dateRange:str=None,searchClause:str=None,lookupNoneValues:bool = True,limit:int=10,verbose:bool=False,**kwargs)->object:
        """
        Returns the top items of a request.
        Arguments:
            rsid : REQUIRED : ReportSuite ID of the data
            dimension : REQUIRED : The dimension to retrieve
            dateRange : OPTIONAL : Format YYYY-MM-DD/YYYY-MM-DD (default 90 days)
            searchClause : OPTIONAL : General search string; wrap with single quotes. Example: 'PageABC'
            lookupNoneValues : OPTIONAL : None values to be included (default True)
            limit : OPTIONAL : Number of items to be returned per page.
            verbose : OPTIONAL : If you want to have comments displayed (default False)
        possible kwargs:
            page : page to look for
            startDate : start date with format YYYY-MM-DD
            endDate : end date with format YYYY-MM-DD
            searchAnd, searchOr, searchNot, searchPhrase : Search element to be included (or not), partial match or not.
        """
        path = "/reports/topItems"
        page = kwargs.get("page",0)
        if rsid is None:
            raise ValueError("Require a reportSuite ID")
        if dimension is None:
            raise ValueError("Require a dimension")
        params = {"rsid" : rsid, "dimension":dimension,"lookupNoneValues":lookupNoneValues,"limit":limit,"page":page}
        if searchClause is not None:
            params["search-clause"] = searchClause
        if dateRange is not None and '/' in dateRange:
            params["dateRange"] = dateRange
        if kwargs.get('page',None) is not None:
            params["page"] = kwargs.get('page')
        if kwargs.get("startDate",None) is not None:
            params["startDate"] = kwargs.get("startDate")
        if kwargs.get("endDate",None) is not None:
            params["endDate"] = kwargs.get("endDate")
        if kwargs.get("searchAnd", None) is not None:
            params["searchAnd"] = kwargs.get("searchAnd")
        if kwargs.get("searchOr",None) is not None:
            params["searchOr"] = kwargs.get("searchOr")
        if kwargs.get("searchNot",None) is not None:
            params["searchNot"] = kwargs.get("searchNot")
        if kwargs.get("searchPhrase",None) is not None:
            params["searchPhrase"] = kwargs.get("searchPhrase")
        last_page = False
        if verbose:
            print('Starting to fetch the data...')
        data = []
        while not last_page:
            if verbose:
                print(f'request page : {page}')
            res = self.connector.getData(self.endpoint_company+path,params=params)
            last_page = res.get("lastPage",True)
            data += res["rows"]
            page += 1
            params["page"] = page
        df = pd.DataFrame(data)
        return df
    
    def compareReportSuites(self,listRsids:list=None,element:str='dimensions',comparison:str="full",save: bool=False)->pd.DataFrame:
        """
        Compare reportSuite on dimensions (default) or metrics based on the comparison selected.
        Returns a dataframe with multi-index and a column telling which elements are differents
        Arguments:
            listRsids : REQUIRED : list of report suite ID to compare
            element : REQUIRED : Elements to compare. 2 possible choices:
                dimensions (default)
                metrics
            comparison : REQUIRED : Type of comparison to do:
                full (default) : compare name and settings
                name : compare only names
            save : OPTIONAL : if you want to save in a csv.
        """
        if listRsids is None or type(listRsids) != list:
            raise ValueError("Require a list of rsids")
        if element=="dimensions":
            listDFs = [self.getDimensions(rsid) for rsid in listRsids]
        elif element == "metrics":
            listDFs = [self.getMetrics(rsid) for rsid in listRsids]
        for df,rsid in zip(listDFs, listRsids):
            df['rsid']=rsid
            df.set_index('id',inplace=True)
            df.set_index('rsid',append=True,inplace=True)
        df = pd.concat(listDFs)
        df = df.unstack()
        if comparison=='name':
            df_name = df['name'].copy()
            ## transforming to a new df with boolean value comparison to col 0
            temp_df = df_name.eq(df_name.iloc[:, 0], axis=0)
            ## now doing a complete comparison of all boolean with all
            df_name['different'] = ~temp_df.eq(temp_df.iloc[:,0],axis=0).all(1)
            if save:
                df_name.to_csv('comparison_name.csv')
            return df_name
        ## retrieve main indexes from multi level indexes
        mainIndex = set([val[0] for val in list(df.columns)])
        dict_temp = {}
        for index in mainIndex:
            temp_df = df[index].copy()
            temp_df.fillna('',inplace=True)
            ## transforming to a new df with boolean value comparison to col 0
            temp_df.eq(temp_df.iloc[:, 0], axis=0)
            ## now doing a complete comparison of all boolean with all
            dict_temp[index] = list(temp_df.eq(temp_df.iloc[:,0],axis=0).all(1))
        df_bool = pd.DataFrame(dict_temp)
        df['different'] = list(~df_bool.eq(df_bool.iloc[:,0],axis=0).all(1))
        if save:
            df.to_csv('comparison_full.csv')
        return df
        

    def _dataDescriptor(self, json_request: dict):
        """
        read the request and returns an object with information about the request.
        It will be used in order to build the dataclass and the dataframe.
        """
        obj = {}
        obj['dimension'] = json_request['dimension']
        obj['filters'] = {'globalFilters': [], 'metricsFilters': {}}
        obj['rsid'] = json_request['rsid']
        metrics_info = json_request['metricContainer']
        obj['metrics'] = [metric['id'] for metric in metrics_info['metrics']]
        if 'metricFilters' in metrics_info.keys():
            metricsFilter = {metric['id']: metric['filters'] for metric in metrics_info['metrics'] if
                             len(metric.get('filters', [])) > 0}
            filters = []
            for metric in metricsFilter:
                for item in metricsFilter[metric]:
                    if 'segmentId' in metrics_info['metricFilters'][int(item)].keys():
                        filters.append(
                            metrics_info['metricFilters'][int(item)]['segmentId'])
                    if 'dimension' in metrics_info['metricFilters'][int(item)].keys():
                        filters.append(
                            metrics_info['metricFilters'][int(item)]['dimension'])
                    obj['filters']['metricsFilters'][metric] = set(filters)
        for fil in json_request['globalFilters']:
            if 'dateRange' in fil.keys():
                obj['filters']['globalFilters'].append(fil['dateRange'])
            if 'dimension' in fil.keys():
                obj['filters']['globalFilters'].append(fil['dimension'])
            if 'segmentId' in fil.keys():
                obj['filters']['globalFilters'].append(fil['segmentId'])
        return obj

    def _readData(
            self,
            data_rows: list,
            anomaly: bool = False,
            cols: list = None,
            item_id: bool = False
    ) -> pd.DataFrame:
        """
        read the data from the requests and returns a dataframe. 
        Parameters:
            data_rows : REQUIRED : Rows that have been returned by the request.
            anomaly : OPTIONAL : Boolean to tell if the anomaly detection has been used. 
            cols : OPTIONAL : list of columns names
        """
        if cols is None:
            raise ValueError("list of columns must be specified")
        data_rows = deepcopy(data_rows)
        dict_data = {row.get('value', 'missing_value'): row['data'] for row in data_rows}
        if cols is not None:
            n_metrics = len(cols) - 1
        if item_id:  # adding the itemId in the data returned
            cols.append('item_id')
            for row in data_rows:
                dict_data[row.get('value', 'missing_value')].append(row['itemId'])
        if anomaly:
            # set full columns
            cols = cols + [f'{metric}-{suffix}' for metric in cols[1:] for suffix in
                           ['expected', 'UpperBound', 'LowerBound']]
            # add data to the dictionary
            for row in data_rows:
                for item in range(n_metrics):
                    dict_data[row['value']].append(
                        row.get('dataExpected', [0 for i in range(n_metrics)])[item])
                    dict_data[row['value']].append(
                        row.get('dataUpperBound', [0 for i in range(n_metrics)])[item])
                    dict_data[row['value']].append(
                        row.get('dataLowerBound', [0 for i in range(n_metrics)])[item])
        df = pd.DataFrame(dict_data).T  # require to transform the data
        df.reset_index(inplace=True, )
        df.columns = cols
        return df

    def getReport(
            self,
            json_request: Union[dict, str, IO],
            limit: int = 1000,
            n_result: Union[int, str] = 1000,
            save: bool = False,
            item_id: bool = False,
            unsafe: bool = False,
            verbose: bool = False,
            debug=False
    ) -> object:
        """
        Retrieve data from a JSON request.Returns an object containing meta info and dataframe. 
        Arguments:
            json_request: REQUIRED : JSON statement that contains your request for Analytics API 2.0.
            limit : OPTIONAL : number of result per request (defaut 1000)
            The argument can be : 
                - a dictionary : It will be used as it is.
                - a string that is a dictionary : It will be transformed to a dictionary / JSON.
                - a path to a JSON file that contains the statement (must end with ".json"). 
            n_result : OPTIONAL : Number of result that you would like to retrieve. (default 1000)
                if you want to have all possible data, use "inf".
            item_id : OPTIONAL : Boolean to define if you want to return the item id for sub requests (default False)
            unsafe : OPTIONAL : If set to True, it will not check "lastPage" parameter and assume first request is complete. 
                This may break the script or return incomplete data. (default False).
            save : OPTIONAL : If you would like to save the data within a CSV file. (default False)
            verbose : OPTIONAL : If you want to have comments displayed (default False)
            
        """
        if unsafe and verbose:
            print('---- running the getReport in "unsafe" mode ----')
        obj = {}
        if type(json_request) == str and '.json' not in json_request:
            try:
                request = json.loads(json_request)
            except:
                raise TypeError("expected a parsable string")
        elif type(json_request) == dict:
            request = json_request
        elif '.json' in json_request:
            try:
                with open(Path(json_request), 'r') as file:
                    file_string = file.read()
                request = json.loads(file_string)
            except:
                raise TypeError("expected a parsable string")
        request['settings']['limit'] = limit
        # info for creating report
        data_info = self._dataDescriptor(request)
        if verbose:
            print('Request decrypted')
        obj.update(data_info)
        anomaly = request['settings'].get('includeAnomalyDetection', False)
        columns = [data_info['dimension']] + data_info['metrics']
        # preparing for the loop
        # in case "inf" has been used. Turn it to a number
        n_result = float(n_result)
        if n_result != float('inf') and n_result < request['settings']['limit']:
            # making sure we don't call more than set in wrapper
            request['settings']['limit'] = n_result
        data_list = []
        last_page = False
        page_nb, count_elements, total_elements = 0, 0, 0
        if verbose:
            print('Starting to fetch the data...')
        while not last_page:
            timestamp = round(time.time())
            request['settings']['page'] = page_nb
            report = self.connector.postData(self.endpoint_company +
                                             self._getReport, data=request, headers=self.header)
            if verbose:
                print('Data received.')
            # Recursion to take care of throttling limit
            while report.get('status_code', 200) == 429 or report.get('error_code',None) == "429050":
                if verbose:
                    print('reaching the limit : pause for 50 s and entering recursion.')
                if debug:
                    with open(f'limit_reach_{timestamp}.json', 'w') as f:
                        f.write(json.dumps(report, indent=4))
                time.sleep(50)
                report = self.connector.postData(self.endpoint_company +
                                             self._getReport, data=request, headers=self.header)
            if 'lastPage' not in report and unsafe == False:  # checking error when no lastPage key in report
                if verbose:
                    print(json.dumps(report, indent=2))
                print('Warning : Server Error')
                print(json.dumps(report))
                if debug:
                    with open(f'server_failure_request_{timestamp}.json', 'w') as f:
                        f.write(json.dumps(request, indent=4))
                    with open(f'server_failure_response_{timestamp}.json', 'w') as f:
                        f.write(json.dumps(report, indent=4))
                    print(
                        f'Warning : Save JSON request : server_failure_request_{timestamp}.json')
                    print(
                        f'Warning : Save JSON response : server_failure_response_{timestamp}.json')
                obj['data'] = pd.DataFrame()
                return obj
            # fallback when no lastPage in report
            last_page = report.get('lastPage', True)
            if verbose:
                print(f'last page status : {last_page}')
            if 'errorCode' in report.keys():
                print('Error with your statement \n' +
                      report['errorDescription'])
                return {report['errorCode']: report['errorDescription']}
            count_elements += report.get('numberOfElements', 0)
            total_elements = report.get(
                'totalElements', request['settings']['limit'])
            if total_elements == 0:
                obj['data'] = pd.DataFrame()
                print(
                    'Warning : No data returned & lastPage is False.\nExit the loop - no save file & empty dataframe.')
                if debug:
                    with open(f'report_no_element_{timestamp}.json', 'w') as f:
                        f.write(json.dumps(report, indent=4))
                if verbose:
                    print(
                        f'% of total elements retrieved. TotalElements: {report.get("totalElements", "no data")}')
                return obj  # in case loop happening with empty data, returns empty data
            if verbose and total_elements != 0:
                print(
                    f'% of total elements retrieved: {round((count_elements / total_elements) * 100, 2)} %')
            if last_page == False and n_result != float('inf'):
                if count_elements >= n_result:
                    last_page = True
            data = report['rows']
            data_list += deepcopy(data)  # do a deepcopy
            page_nb += 1
            if verbose:
                print(f'# of requests : {page_nb}')
        # return report
        df = self._readData(data_list, anomaly=anomaly,
                            cols=columns, item_id=item_id)
        if save:
            timestampReport = round(time.time())
            df.to_csv(f'report-{timestampReport}.csv', index=False)
            if verbose:
                print(
                    f'Saving data in file : {os.getcwd()}{os.sep}report-{timestampReport}.csv')
        obj['data'] = df
        if verbose:
            print(
                f'Report contains {(count_elements / total_elements) * 100} % of the available dimensions')
        return obj
