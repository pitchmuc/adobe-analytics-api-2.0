# Created by julien piccini
# email : piccini.julien@gmail.com
# version : 0.1.4
import json
import os
import time
from concurrent import futures
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Union, List

# Non standard libraries
import pandas as pd
import requests

from aanalytics2 import config, connector, token_provider

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


@dataclass
class Project:
    """
    This dataclass extract the information retrieved from the getProjet method.
    It flatten the elements and gives you insights on what your project contains.
    """

    def __init__(self, projectDict: dict = None):
        if projectDict is None:
            raise Exception("require a dictionary")
        self.id: str = projectDict.get('id', '')
        self.name: str = projectDict.get('name', '')
        self.description: str = projectDict.get('description', '')
        self.rsid: str = projectDict.get('rsid', '')
        self.ownerName: str = projectDict['owner'].get('name', '')
        self.ownerId: int = projectDict['owner'].get('id', '')
        self.ownerEmail: int = projectDict['owner'].get('login', '')
        self.template: bool = projectDict.get('companyTemplate', False)
        self.version: str = None
        if 'definition' in projectDict.keys():
            definition: dict = projectDict['definition']
            self.version: str = definition['version']
            self.curation: bool = definition.get('isCurated', False)
            if definition.get('device', 'desktop') != 'cell':
                infos = self._findPanelsInfos(definition['workspaces'][0])
                self.nbPanels: int = infos["nb_Panels"]
                self.nbSubPanels: int = 0
                self.subPanelsTypes: list = []
                for panel in infos["panels"]:
                    self.nbSubPanels += infos["panels"][panel]['nb_subPanels']
                    self.subPanelsTypes += infos["panels"][panel]['subPanels_types']
                self.elementsUsed: dict = self._findElements(definition['workspaces'][0])
                self.nbElementsUsed: int = len(self.elementsUsed['dimensions']) + len(
                    self.elementsUsed['metrics']) + len(self.elementsUsed['segments']) + len(
                    self.elementsUsed['calculatedMetrics'])

    def _findPanelsInfos(self, workspace: dict = None) -> dict:
        """
        Return a dict of the different information for each Panel.
        Arguments:
            workspace : REQUIRED : the workspace dictionary. 
        """
        dict_data = {'workspace_id': workspace['id']}
        dict_data['nb_Panels'] = len(workspace['panels'])
        dict_data['panels'] = {}
        for panel in workspace['panels']:
            dict_data["panels"][panel['id']] = {}
            dict_data["panels"][panel['id']]['name'] = panel.get('name', 'Default Name')
            dict_data["panels"][panel['id']]['nb_subPanels'] = len(panel['subPanels'])
            dict_data["panels"][panel['id']]['subPanels_types'] = [subPanel['reportlet']['type'] for subPanel in
                                                                   panel['subPanels']]
        return dict_data

    def _findElements(self, workspace: dict) -> list:
        """
        Returns the list of dimensions used in the FreeformReportlet. 
        Arguments :
            workspace : REQUIRED : the workspace dictionary.
        """
        dict_elements: dict = {'dimensions': [], "metrics": [], 'segments': [], "reportSuites": [],
                               'calculatedMetrics': []}
        for panel in workspace['panels']:
            if "reportSuite" in panel.keys():
                dict_elements['reportSuites'].append(panel['reportSuite']['id'])
            elif "rsid" in panel.keys():
                dict_elements['reportSuites'].append(panel['rsid'])
            filters: list = panel['segmentGroups']
            if len(filters) > 0:
                for element in filters:
                    typeElement = element['componentOptions'][0]['component']['type']
                    idElement = element['componentOptions'][0]['component']['id']
                    if typeElement == "Segment":
                        dict_elements['segments'].append(idElement)
                    if typeElement == "DimensionItem":
                        clean_id: str = idElement[:idElement.find(
                            '::')]  ## cleaning this type of element : 'variables/evar7.6::3000623228'
                        dict_elements['dimensions'].append(clean_id)
            for subPanel in panel['subPanels']:
                if subPanel['reportlet']['type'] == "FreeformReportlet":
                    reportlet = subPanel['reportlet']
                    rows = reportlet['freeformTable']
                    if 'dimension' in rows.keys():
                        dict_elements['dimensions'].append(rows['dimension']['id'])
                    if len(rows["staticRows"]) > 0:
                        for row in rows["staticRows"]:
                            ## I have to get a temp dimension to clean them before loading them in order to avoid counting them multiple time for each rows.
                            temp_list_dim = []
                            componentType: str = row['component']['type']
                            if componentType == "DimensionItem":
                                temp_list_dim.append(row['component']['id'])
                            elif componentType == "Segments":
                                dict_elements['segments'].append(row['component']['id'])
                            elif componentType == "Metric":
                                dict_elements['metrics'].append(row['component']['id'])
                            elif componentType == "CalculatedMetric":
                                dict_elements['calculatedMetrics'].append(row['component']['id'])
                        if len(temp_list_dim) > 0:
                            temp_list_dim = list(set([el[:el.find('::')] for el in temp_list_dim]))
                        for dim in temp_list_dim:
                            dict_elements['dimensions'].append(dim)
                    columns = reportlet['columnTree']
                    for node in columns['nodes']:
                        temp_data = self._recursiveColumn(node)
                        dict_elements['calculatedMetrics'] += temp_data['calculatedMetrics']
                        dict_elements['segments'] += temp_data['segments']
                        dict_elements['metrics'] += temp_data['metrics']
                        if len(temp_data['dimensions']) > 0:
                            for dim in set(temp_data['dimensions']):
                                dict_elements['dimensions'].append(dim)
        dict_elements['metrics'] = list(set(dict_elements['metrics']))
        dict_elements['segments'] = list(set(dict_elements['segments']))
        dict_elements['dimensions'] = list(set(dict_elements['dimensions']))
        dict_elements['calculatedMetrics'] = list(set(dict_elements['calculatedMetrics']))
        return dict_elements

    def _recursiveColumn(self, node: dict = None, temp_data: dict = None):
        """
        recursive function to fetch elements in column stack
        """
        if temp_data is None:
            temp_data: dict = {'dimensions': [], "metrics": [], 'segments': [], "reportSuites": [],
                               'calculatedMetrics': []}
        componentType: str = node['component']['type']
        if componentType == "Metric":
            temp_data['metrics'].append(node['component']['id'])
        elif componentType == "CalculatedMetric":
            temp_data['calculatedMetrics'].append(node['component']['id'])
        elif componentType == "Segments":
            temp_data['segments'].append(node['component']['id'])
        elif componentType == "DimensionItem":
            old_id: str = node['component']['id']
            new_id: str = old_id[:old_id.find('::')]
            temp_data['dimensions'].append(new_id)
        if len(node['nodes']) > 0:
            for new_node in node['nodes']:
                temp_data = self._recursiveColumn(new_node, temp_data=temp_data)
        return temp_data

    def to_dict(self) -> dict:
        """
        transform the class into a dictionary
        """
        obj = {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'rsid': self.rsid,
            'ownerName': self.ownerName,
            'ownerId': self.ownerId,
            'ownerEmail': self.ownerEmail,
            'template': self.template,
        }
        add_object = {}
        if hasattr(self, 'nbPanels'):
            add_object = {
                'curation': self.curation,
                'version': self.version,
                'nbPanels': self.nbPanels,
                'nbSubPanels': self.nbSubPanels,
                'subPanelsTypes': self.subPanelsTypes,
                'nbElementsUsed': self.nbElementsUsed,
                'dimensions': self.elementsUsed['dimensions'],
                'metrics': self.elementsUsed['metrics'],
                'segments': self.elementsUsed['segments'],
                'calculatedMetrics': self.elementsUsed['calculatedMetrics'],
                'rsids': self.elementsUsed['reportSuites'],
            }
        full_obj = {**obj, **add_object}
        return full_obj


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
        try:
            import importlib.resources as pkg_resources
            pathLOGS = pkg_resources.path(
                "aanalytics2", "eventType_usageLogs.pickle")
        except ImportError:
            # Try backported to PY<37 `importlib_resources`.
            import pkg_resources
            pathLOGS = pkg_resources.resource_filename(
                "aanalytics2", "eventType_usageLogs.pickle")
        with pathLOGS as f:
            self.LOGS_EVENT_TYPE = pd.read_pickle(f)

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

    def getDimensions(self, rsid: str, tags: bool = False, save=False, **kwargs) -> pd.DataFrame:
        """
        Retrieve the list of dimensions from a specific reportSuite.Shrink columns to simplify output.
        Returns the data frame of available dimensions.
        Arguments:
            rsid : REQUIRED : Report Suite ID from which you want the dimensions
            tags : OPTIONAL : If you would like to have additional information, such as tags. (bool : default False)
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
                   'parent', 'pathable', 'description']
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

    def getMetrics(self, rsid: str, tags: bool = False, save=False, **kwargs) -> pd.DataFrame:
        """
        Retrieve the list of metrics from a specific reportSuite. Shrink columns to simplify output.
        Returns the data frame of available metrics.
        Arguments:
            rsid : REQUIRED : Report Suite ID from which you want the dimensions (str)
            tags : OPTIONAL : If you would like to have additional information, such as tags.(bool : default False)
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
                   'dataGroup', 'precision', 'segmentable']
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
                {'expansion': 'reportSuiteName,ownerFullName,modified,tags,compatibility,definition'})
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

    def getSegment(self, segment_id: str = None, *args):
        """
        Get a specific segment from the ID. Returns the object of the segment.
        Arguments:
            segment_id : REQUIRED : the segment id to retrieve.
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
        res = self.connector.getData(self.endpoint_company + path, params=params, headers=self.header)
        return res

    def createSegment(self, segmentJSON: dict = None) -> object:
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
                {'expansion': 'reportSuiteName,definition,ownerFullName,modified,tags,categories,compatibility'})
        metrics = self.connector.getData(self.endpoint_company +
                                         self._getCalcMetrics, params=params, headers=self.header)
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
        df_calc_metrics = pd.DataFrame(data)
        if save:
            df_calc_metrics.to_csv('calculated_metrics.csv', sep='\t')
        return df_calc_metrics

    def createCalculatedMetrics(self, metricJSON: dict = None) -> object:
        """
        Method that create a specific calculated based on the dictionary passed to it.
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

    def getDateRanges(self, extended_info: bool = False, save: bool = False, includeType: str = 'all',
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
            headers=self.header
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
                    includeTemplate: bool = False, format: str = 'df', save: bool = False) -> JsonListOrDataFrameType:
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

    def getProject(self, projectId: str = None, projectClass: bool = False, retry: int = 0,verbose: bool = False) -> dict:
        """
        Return the dictionary of the project information and its definition.
        Arguments:
            projectId : REQUIRED : the project ID to be retrieved.
            projectClass : OPTIONAL : if set to True. Returns a class of the project with prefiltered information
            retry : OPTIONAL : If you want to retry the request if it fails. Specify number of retry (0 default)
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
            myProject = Project(res)
            return myProject
        return res

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
            verbose : OPTIONAL : If you want to have comment display (default False)
            
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
