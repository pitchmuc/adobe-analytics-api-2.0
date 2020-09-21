# Created by julien piccini
# email : piccini.julien@gmail.com
# version : 0.0.9

import json as _json
import os
import time as _time
from concurrent import futures as _futures
from pathlib import Path as _Path

# Non standard libraries
import jwt as _jwt
import pandas as _pd
import requests as _requests
from copy import deepcopy as _deepcopy
from typing import IO as _IO, Optional
from typing import Union as _Union

from aanalytics2 import config


def createConfigFile(verbose: object = False) -> None:
    """Creates a `config_admin.json` file with the pre-defined configuration format to store
    the access data in.
    """
    json_data = {
        'org_id': '<orgID>',
        'api_key': "<APIkey>",
        'tech_id': "<something>@techacct.adobe.com",
        'secret': "<YourSecret>",
        'pathToKey': '<path/to/your/privatekey.key>',
    }
    with open('config_admin.json', 'w') as cf:
        cf.write(_json.dumps(json_data, indent=4))
    if verbose:
        print(
            f" file created at this location : {os.getcwd()}{os.sep}config_admin.json")


def _find_path(path: str) -> Optional[_Path]:
    """Checks if the file denoted by the specified `path` exists and returns the Path object
    for the file.

    If the file under the `path` does not exist and the path denotes an absolute path, tries
    to find the file by converting the absolute path to a relative path.

    If the file does not exist with either the absolute and the relative path, returns `None`.
    """
    if _Path(path).exists():
        return _Path(path)
    elif path.startswith('/') and _Path('.' + path).exists():
        return _Path('.' + path)
    elif path.startswith('\\') and _Path('.' + path).exists():
        return _Path('.' + path)
    else:
        return None


def importConfigFile(path: str) -> None:
    """Reads the file denoted by the supplied `path` and retrieves the configuration information
    from it.

    Arguments:
        path: REQUIRED : path to the configuration file. Can be either a fully-qualified or relative.

    Example of file value.
    "config.json"
    "./config.json"
    "/my-folder/config.json"
    """
    config_file_path: Optional[_Path] = _find_path(path)
    if config_file_path is None:
        raise FileNotFoundError(
            f"Unable to find the configuration file under path `{path}`.")
    with open(config_file_path, 'r') as file:
        f = _json.load(file)
        config.org_id = f['org_id']
        config.api_key = f['api_key']
        config.header["X-Api-Key"] = f['api_key']
        config.tech_id = f['tech_id']
        config.secret = f['secret']
        config.pathToKey = f['pathToKey']


def retrieveToken(verbose: bool = False, save: bool = False, **kwargs) -> str:
    """Retrieves the token by using the information provided by the user during
    the import importConfigFile function.

    Argument : 
        verbose : OPTIONAL : Default False. If set to True, print information.
        save : OPTIONAL : Default False. If set to True, will save the token in a txt file (token.txt). 
    """
    private_key_path: Optional[_Path] = _find_path(config.pathToKey)
    if private_key_path is None:
        raise FileNotFoundError(
            f"Unable to find the private key under the path `{config.pathToKey}`.")
    with open(private_key_path, 'r') as f:
        private_key_unencrypted = f.read()
    header_jwt = {
        'cache-control': 'no-cache',
        'content-type': 'application/x-www-form-urlencoded'
    }
    jwt_payload = {
        # Expiration set to 24 hours
        "exp": round(24 * 60 * 60 + int(_time.time())),
        "iss": config.org_id,  # org_id
        "sub": config.tech_id,  # technical_account_id
        "https://ims-na1.adobelogin.com/s/ent_analytics_bulk_ingest_sdk": True,
        "aud": "https://ims-na1.adobelogin.com/c/" + config.api_key
    }
    encoded_jwt = _jwt.encode(
        jwt_payload, private_key_unencrypted, algorithm='RS256')
    payload = {
        "client_id": config.api_key,
        "client_secret": config.secret,
        "jwt_token": encoded_jwt.decode("utf-8")
    }
    token_endpoint = "https://ims-na1.adobelogin.com/ims/exchange/jwt"
    response = _requests.post(token_endpoint, headers=header_jwt, data=payload)
    json_response = response.json()
    token = json_response['access_token']
    config.header["Authorization"] = "Bearer " + token
    expire = json_response['expires_in']
    config.date_limit = _time.time() + expire / 1000 - \
        500  # end of time for the token
    if save:
        with open('token.txt', 'w') as f:  # save the token
            f.write(token)
        if verbose:
            print(
                f"token valid till : {_time.ctime(_time.time() + expire / 1000)}")
            print(f"token has been saved here: {os.getcwd()}{os.sep}token.txt")
    return token


def _checkToken(func):
    """decorator that checks that the token is valid before calling the API"""

    def checking(*args, **kwargs):  # if function is not wrapped, will fire
        now = _time.time()
        if now > config.date_limit - 1000:
            config.token = retrieveToken(*args, **kwargs)
            if kwargs.get("headers", None) is not None:
                kwargs['headers']['Authorization'] = "Bearer " + config.token
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
        res = _requests.get(endpoint, headers=header, params=params)
    elif params is None and data is not None:
        res = _requests.get(endpoint, headers=header, data=data)
    elif params is not None and data is not None:
        res = _requests.get(endpoint, headers=header,
                            params=params, data=data)
    try:
        json = res.json()
    except ValueError:
        json = {'error': ['Request Error']}
    if res.status_code == 429:
        json['status_code'] = 429
    return json


@_checkToken
def postData(endpoint: str, params: dict = None, data=None, headers: dict = None, file: dict = None, *args, **kwargs):
    """
    Abstraction for getting data
    """
    header = headers
    if params is not None and data is None and file is None:
        res = _requests.post(endpoint, headers=header, params=params)
    elif params is None and data is not None and file is None:
        res = _requests.post(endpoint, headers=header, data=_json.dumps(data))
    elif params is not None and data is not None and file is None:
        res = _requests.post(endpoint, headers=header,
                             params=params, data=_json.dumps(data=data))
    elif file is not None:
        res = _requests.post(endpoint, headers=header, files=file)
    try:
        json = res.json()
    except ValueError:
        json = {'error': ['Request Error']}
    if res.status_code == 429:
        json['status_code'] = 429
    return json


@_checkToken
def putData(endpoint: str, params: dict = None, data=None, headers: dict = None, *args, **kwargs):
    """
    Abstraction for getting data
    """
    header = headers
    if params is not None and data is None:
        res = _requests.put(endpoint, headers=header, params=params)
    elif params is None and data is not None:
        res = _requests.put(endpoint, headers=header, data=_json.dumps(data))
    elif params is not None and data is not None:
        res = _requests.put(endpoint, headers=header,
                            params=params, data=_json.dumps(data=data))
    try:
        json = res.json()
    except ValueError:
        json = {'error': ['Request Error']}
    return json


@_checkToken
def deleteData(endpoint: str, params: dict = None, data=None, headers: dict = None, *args, **kwargs):
    """
    Abstraction for getting data
    """
    header = headers
    if params is not None and data is None:
        res = _requests.delete(endpoint, headers=header, params=params)
    elif params is None and data is not None:
        res = _requests.delete(endpoint, headers=header,
                               data=_json.dumps(data))
    elif params is not None and data is not None:
        res = _requests.delete(endpoint, headers=header,
                               params=params, data=_json.dumps(data=data))
    elif params is None and data is None:
        res = _requests.delete(endpoint, headers=header)
    try:
        json = res.json()
    except:
        json = {'error': ['Request Error']}
    return json


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
    res = _requests.get(
        "https://analytics.adobe.io/discovery/me", headers=config.header)
    json_res = res.json()
    if infos == 'all':
        companies = json_res['imsOrgs'][0]['companies']
        return companies
    elif infos != 'all':
        if infos == 'first':
            infos = '0'  # set to first position
        position = int(infos)
        companies = json_res['imsOrgs'][0]['companies']
        config.companyid = companies[position]['globalCompanyId']
        return config.companyid


class Analytics:
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

    def __init__(self, company_id: str = None):
        if company_id is None:
            raise AttributeError(
                'Expected "company_id" to be referenced.\nPlease ensure you pass the globalCompanyId when instantiating this class.')
        self.header = _deepcopy(config.header)
        self.header['x-proxy-global-company-id'] = company_id
        self._endpoint_company = f"{self._endpoint}/{company_id}"

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
        rsids = getData(self._endpoint_company + self._getRS,
                        params=params, headers=self.header)
        content = rsids['content']
        if not extended_info:
            list_content = [{'name': item['name'], 'rsid': item['rsid']}
                            for item in content]
            df_rsids = _pd.DataFrame(list_content)
        else:
            df_rsids = _pd.DataFrame(content)
        total_page = rsids['totalPages']
        last_page = rsids['lastPage']
        if not last_page:  # if last_page =False
            callsToMake = total_page
            list_params = [{**params, 'page': page}
                           for page in range(1, callsToMake)]
            list_urls = [self._endpoint_company +
                         self._getRS for x in range(1, callsToMake)]
            listheaders = [self.header for x in range(1, callsToMake)]
            workers = min(10, total_page)
            with _futures.ThreadPoolExecutor(workers) as executor:
                res = executor.map(lambda x, y, z: getData(
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
                df_append = _pd.DataFrame(list_append)
            else:
                df_append = _pd.DataFrame(list_data)
            df_rsids = df_rsids.append(df_append, ignore_index=True)
        if save:
            df_rsids.to_csv('RSIDS.csv', sep='\t')
        if nb_error > 0 or nb_empty > 0:
            print(
                f'WARNING : Retrieved data are partial.\n{nb_error}/{len(list_urls) + 1} requests returned an error.\n{nb_empty}/{len(list_urls)} requests returned an empty response. \nTry to use filter to retrieve reportSuite or increase limit per request')
        return df_rsids

    def getVirtualReportSuites(self, extended_info: bool = False, limit: int = 100, filterIds: str = None, idContains: str = None, segmentIds: str = None, save: bool = True)->list:
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
        if extended_info:
            params['expansion'] = expansion_values
        if filterIds is not None:
            params['filterByIds'] = filterIds
        if idContains is not None:
            params['idContains'] = idContains
        if segmentIds is not None:
            params['segmentIds'] = segmentIds
        path = f"{self._endpoint_company}/reportsuites/virtualreportsuites"
        vrsid = getData(path, params=params, headers=self.header)
        content = vrsid['content']
        if not extended_info:
            list_content = [{'name': item['name'], 'vrsid': item['id']}
                            for item in content]
            df_vrsids = _pd.DataFrame(list_content)
        else:
            df_vrsids = _pd.DataFrame(content)
        total_page = vrsid['totalPages']
        last_page = vrsid['lastPage']
        if not last_page:  # if last_page =False
            callsToMake = total_page
            list_params = [{**params, 'page': page}
                           for page in range(1, callsToMake)]
            list_urls = [path for x in range(1, callsToMake)]
            listheaders = [self.header for x in range(1, callsToMake)]
            workers = min(10, total_page)
            with _futures.ThreadPoolExecutor(workers) as executor:
                res = executor.map(lambda x, y, z: getData(
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
                df_append = _pd.DataFrame(list_append)
            else:
                df_append = _pd.DataFrame(list_data)
            df_vrsids = df_vrsids.append(df_append, ignore_index=True)
        if save:
            df_vrsids.to_csv('VRSIDS.csv', sep='\t')
        if nb_error > 0 or nb_empty > 0:
            print(
                f'WARNING : Retrieved data are partial.\n{nb_error}/{len(list_urls)+1} requests returned an error.\n{nb_empty}/{len(list_urls)} requests returned an empty response. \nTry to use filter to retrieve reportSuite or increase limit per request')
        return df_vrsids

    def getVirtualReportSuite(self, vrsid: str = None, extended_info: bool = False, format: str = 'df')->object:
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
        path = f"{self._endpoint_company}/reportsuites/virtualreportsuites/{vrsid}"
        data = getData(path, params=params, headers=self.header)
        if format == "df":
            data = _pd.DataFrame({vrsid: data})
        return data

    def createVirtualReportSuite(self, name: str = None, parentRsid: str = None, segmentList: list = None, dataSchema: str = "Cache", data_dict: dict = None, **kwargs)->dict:
        """
        Create a new virtual report suite based on the information provided.
        Arguments:
            name : REQUIRED : name of the virtual reportSuite
            parentRsid : REQUIRED : Parent reportSuite ID for the VRS
            segmentLists : REQUIRED : list of segment id to be applied on the ReportSuite.
            dataSchema : REQUIRED : Type of schema used for the VRSID. (default "Cache")
            data_dict : OPTIONAL : you can pass directly the dictionary.
        """
        path = f"{self._endpoint_company}/reportsuites/virtualreportsuites"
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
        res = postData(path, params=params, data=body, headers=self.header)
        return res

    def deleteVirtualReportSuite(self, vrsid: str = None)->str:
        """
        Delete a Virtual Report Suite based on the id passed.
        Arguments:
            vrsid : REQUIRED : The id of the virtual reportSuite to delete.
        """
        if vrsid is None:
            raise Exception("require a Virtual ReportSuite ID")
        path = f"{self._endpoint_company}/reportsuites/virtualreportsuites/{vrsid}"
        res = deleteData(path, headers=self.header)
        return res

    def validateVirtualReportSuite(self, name: str = None, parentRsid: str = None, segmentList: list = None,  dataSchema: str = "Cache", data_dict: dict = None, **kwargs)->dict:
        """
        Validate the object to create a new virtual report suite based on the information provided.
        Arguments:
            name : REQUIRED : name of the virtual reportSuite
            parentRsid : REQUIRED : Parent reportSuite ID for the VRS
            segmentLists : REQUIRED : list of segment ids to be applied on the ReportSuite.
            dataSchema : REQUIRED : Type of schema used for the VRSID (default : Cache).
            data_dict : OPTIONAL : you can pass directly the dictionary.
        """
        path = f"{self._endpoint_company}/reportsuites/virtualreportsuites/validate"
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
        res = postData(path, data=body, headers=self.header)
        return res

    def getDimensions(self, rsid: str, tags: bool = False, save=False, **kwargs) -> object:
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
        dims = getData(self._endpoint_company +
                       self._getDimensions, params=params, headers=self.header)
        df_dims = _pd.DataFrame(dims)
        columns = ['id', 'name', 'category', 'type',
                   'parent', 'pathable', 'description']
        if kwargs.get('full', False):
            new_cols = _pd.DataFrame(df_dims.support.values.tolist(),
                                     columns=['support_oberon', 'support_dw'])  # extract list in column
            new_df = df_dims.merge(new_cols, right_index=True, left_index=True)
            new_df.drop(['reportable', 'support'], axis=1, inplace=True)
            df_dims = new_df
        else:
            df_dims = df_dims[columns]
        df_dims.to_csv(f'dimensions_{rsid}.csv')
        return df_dims

    def getMetrics(self, rsid: str, tags: bool = False, save=False, **kwargs) -> object:
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
        metrics = getData(self._endpoint_company +
                          self._getMetrics, params=params, headers=self.header)
        df_metrics = _pd.DataFrame(metrics)
        columns = ['id', 'name', 'category', 'type',
                   'dataGroup', 'precision', 'segmentable']
        if kwargs.get('full', False):
            new_cols = _pd.DataFrame(df_metrics.support.values.tolist(), columns=[
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

    def getUsers(self, save: bool = False, **kwargs) -> object:
        """
        Retrieve the list of users for a login company.Returns a data frame.
        Arguments:
            save : OPTIONAL : Save the data in a file (bool : default False). 
        Possible kwargs: 
            limit :  Nummber of results per requests. Default 100.
            expansion : string list such as "lastAccess,createDate"  
        """
        nb_error, nb_empty = 0, 0  # use for multi-thread loop
        params = {'limit': kwargs.get('limit', 100)}
        if kwargs.get("expansion", None) is not None:
            params["expansion"] = kwargs.get("expansion", None)
        users = getData(self._endpoint_company +
                        self._getUsers, params=params, headers=self.header)
        data = users['content']
        lastPage = users['lastPage']
        if not lastPage:  # check if lastpage is inversed of False
            callsToMake = users['totalPages']
            list_params = [{'limit': params['limit'], 'page': page}
                           for page in range(1, callsToMake)]
            list_urls = [self._endpoint_company +
                         self._getUsers for x in range(1, callsToMake)]
            listheaders = [self.header
                           for x in range(1, callsToMake)]
            workers = min(10, len(list_params))
            with _futures.ThreadPoolExecutor(workers) as executor:
                res = executor.map(lambda x, y, z: getData(x, y, headers=z), list_urls,
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
        df_users = _pd.DataFrame(data)
        columns = ['email', 'login', 'fullName', 'firstName', 'lastName', 'admin', 'loginId', 'imsUserId', 'login',
                   'createDate', 'lastAccess', 'title', 'disabled', 'phoneNumber', 'companyid']
        df_users = df_users[columns]
        df_users['createDate'] = _pd.to_datetime(df_users['createDate'])
        df_users['lastAccess'] = _pd.to_datetime(df_users['lastAccess'])
        if save:
            df_users.to_csv('users.csv', sep='\t')
        if nb_error > 0 or nb_empty > 0:
            print(
                f'WARNING : Retrieved data are partial.\n{nb_error}/{len(list_urls) + 1} requests returned an error.\n{nb_empty}/{len(list_urls)} requests returned an empty response. \nTry to use filter to retrieve users or increase limit')
        return df_users

    def getSegments(self, name: str = None, tagNames: str = None, inclType: str = 'all', rsids_list: list = None,
                    sidFilter: list = None, extended_info: bool = False, format: str = "df", save: bool = False,
                    verbose: bool = False, **kwargs) -> object:
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
            segs = getData(self._endpoint_company +
                           self._getSegments, params=params, headers=self.header)
            data += segs['content']
            lastPage = segs['lastPage']
            page_nb += 1
            if verbose and page_nb % 10 == 0:
                print(f"request #{page_nb / 10}")
        if format == "df":
            segments = _pd.DataFrame(data)
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
        res = getData(self._endpoint_company + path,
                      params=params, headers=self.header)
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
        data = _deepcopy(segmentJSON)
        seg = postData(self._endpoint_company +
                       self._getSegments, data=data, headers=self.header)
        return seg

    def updateSegment(self, segmentID: str = None, segmentJSON: dict = None) -> object:
        """
        Method that update a specific segment based on the dictionary passed to it.
        Arguments:
            segmentID : REQUIRED : Segment ID to be deleted
            segmentJSON : REQUIRED : the dictionary that represents the JSON statement for the segment. 
        """
        if segmentJSON is None or segmentID is None:
            print('No segment or segementID data has been pushed')
            return None
        data = _deepcopy(segmentJSON)
        seg = putData(self._endpoint_company + self._getSegments +
                      '/' + segmentID, data=data, headers=self.header)
        return seg

    def deleteSegment(self, segmentID: str = None) -> object:
        """
        Method that update a specific segment based on the dictionary passed to it.
        Arguments:
            segmentID : REQUIRED : Segment ID to be deleted
        """
        if segmentID is None:
            print('No segementID data has been pushed')
            return None
        seg = deleteData(self._endpoint_company +
                         self._getSegments + '/' + segmentID, headers=self.header)
        return seg

    def getCalculatedMetrics(self, name: str = None, tagNames: str = None, inclType: str = 'all',
                             rsids_list: list = None,
                             extended_info: bool = False, save=False, **kwargs) -> object:
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
        params = {'includeType': 'all', 'limit': limit}
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
        metrics = getData(self._endpoint_company +
                          self._getCalcMetrics, params=params, headers=self.header)
        data = metrics['content']
        lastPage = metrics['lastPage']
        if not lastPage:  # check if lastpage is inversed of False
            page_nb = 0
            while not lastPage:
                page_nb += 1
                params['page'] = page_nb
                metrics = getData(self._endpoint_company +
                                  self._getCalcMetrics, params=params, headers=self.header)
                data += metrics['content']
                lastPage = metrics['lastPage']
        df_calc_metrics = _pd.DataFrame(data)
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
        cm = postData(self._endpoint_company +
                      self._getCalcMetrics, headers=self.header, data=metricJSON)
        return cm

    def deleteCalculatedMetrics(self, calcID: str = None) -> object:
        """
        Method that delete a specific calculated metrics based on the id passed..
        Arguments:
            calcID : REQUIRED : Calculated Metrics ID to be deleted
        """
        if calcID is None:
            print('No calculated metrics data has been pushed')
            return None
        cm = deleteData(self._endpoint_company +
                        self._getCalcMetrics + '/' + calcID, headers=self.header)
        return cm

    def getDateRanges(self, extended_info: bool = False, save: bool = False, **kwargs) -> object:
        """
        Get the list of date ranges available for the user.
        Arguments:
            extended_info : OPTIONAL : additional segment metadata fields to include on response
                additional infos: reportSuiteName, ownerFullName, modified, tags, compatibility, definition
            save : OPTIONAL : If set to True, it will save the info in a csv file (Default False)
        Possible kwargs:
            limit : number of segments retrieved by request. default 500: Limited to 1000 by the AnalyticsAPI.
            full : Boolean : Doesn't shrink the number of columns if set to true
        """
        limit = int(kwargs.get('limit', 500))
        params = {'limit': limit, 'includeType': ['all']}
        if extended_info:
            params.update(
                {'expansion': 'definition,ownerFullName,modified,tags'})
        dateRanges = getData(self._endpoint_company +
                             self._getDateRanges, params=params, headers=self.header)
        data = dateRanges['content']
        df_dates = _pd.DataFrame(data)
        return df_dates

    def getCalculatedFunctions(self, **kwargs):
        """
        Returns the calculated metrics functions.
        """
        path = "/calculatedmetrics/functions"
        limit = int(kwargs.get('limit', 500))
        params = {'limit': limit}
        funcs = getData(self._endpoint_company + path,
                        params=params, headers=self.header)
        df = _pd.DataFrame(funcs)
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

    def _readData(self, data_rows: list, anomaly: bool = False, cols: list = None, item_id: bool = False):
        """
        read the data from the requests and returns a dataframe. 
        Parameters:
            data_rows : REQUIRED : Rows that have been returned by the request.
            anomaly : OPTIONAL : Boolean to tell if the anomaly detection has been used. 
            cols : OPTIONAL : list of columns names
        """
        data_rows = _deepcopy(data_rows)
        dict_data = {}
        dict_data = {row.get('value', 'missing_value')
                             : row['data'] for row in data_rows}
        if cols is not None:
            n_metrics = len(cols) - 1
        if item_id:  # adding the itemId in the data returned
            cols.append('item_id')
            for row in data_rows:
                dict_data[row.get('value', 'missing_value')
                          ].append(row['itemId'])
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
        df = _pd.DataFrame(dict_data).T  # require to transform the data
        df.reset_index(inplace=True, )
        df.columns = cols
        return df

    def getReport(self, json_request: _Union[dict, str, _IO], n_result: _Union[int, str] = 1000, save: bool = False,
                  item_id: bool = False, verbose: bool = False, debug=False) -> object:
        """
        Retrieve data from a JSON request.Returns an object containing meta info and dataframe. 
        Arguments:
            json_request: REQUIRED : JSON statement that contains your request for Analytics API 2.0.
            The argument can be : 
                - a dictionary : It will be used as it is.
                - a string that is a dictionary : It will be transformed to a dictionary / JSON.
                - a path to a JSON file that contains the statement (must end with ".json"). 
            n_result : OPTIONAL : Number of result that you would like to retrieve. (default 1000)
                if you want to have all possible data, use "inf".
            item_id : OPTIONAL : Boolean to define if you want to return the item id for sub requests (default False)
            save : OPTIONAL : If you would like to save the data within a CSV file. (default False)
            verbose : OPTIONAL : If you want to have comment display (default False)
        """
        obj = {}
        if type(json_request) == str and '.json' not in json_request:
            try:
                request = _json.loads(json_request)
            except:
                raise TypeError("expected a parsable string")
        elif type(json_request) == dict:
            request = json_request
        elif '.json' in json_request:
            try:
                with open(_Path(json_request), 'r') as file:
                    file_string = file.read()
                request = _json.loads(file_string)
            except:
                raise TypeError("expected a parsable string")
        request['settings']['limit'] = 1000
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
        while last_page == False:
            timestamp = round(_time.time())
            request['settings']['page'] = page_nb
            report = postData(self._endpoint_company +
                              self._getReport, data=request, headers=self.header)
            if verbose:
                print('Data received.')
            # Recursion to take care of throttling limit
            if report.get('status_code', 200) == 429:
                if verbose:
                    print('reaching the limit : pause for 60 s and entering recursion.')
                if debug:
                    with open(f'limit_reach_{timestamp}.json', 'w') as f:
                        f.write(_json.dumps(report, indent=4))
                _time.sleep(50)
                obj = self.getReport(json_request=request, n_result=n_result,
                                     save=save, item_id=item_id, verbose=verbose)
                return obj
            if 'lastPage' not in report:  # checking error when no lastPage key in report
                if verbose:
                    print(_json.dumps(report, indent=2))
                print('Warning : Server Error - no save file & empty dataframe.')
                if debug:
                    with open(f'server_failure_request_{timestamp}.json', 'w') as f:
                        f.write(_json.dumps(request, indent=4))
                    with open(f'server_failure_response_{timestamp}.json', 'w') as f:
                        f.write(_json.dumps(report, indent=4))
                    print(
                        f'Warning : Save JSON request : server_failure_request_{timestamp}.json')
                    print(
                        f'Warning : Save JSON response : server_failure_response_{timestamp}.json')
                obj['data'] = _pd.DataFrame()
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
                obj['data'] = _pd.DataFrame()
                print(
                    'Warning : No data returned & lastPage is False.\nExit the loop - no save file & empty dataframe.')
                if debug:
                    with open(f'report_no_element_{timestamp}.json', 'w') as f:
                        f.write(_json.dumps(report, indent=4))
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
            data_list += _deepcopy(data)  # do a deepcopy
            page_nb += 1
            if verbose:
                print(f'# of requests : {page_nb}')
        # return report
        df = self._readData(data_list, anomaly=anomaly,
                            cols=columns, item_id=item_id)
        if save:
            df.to_csv(f'report-{timestamp}.csv', index=False)
            if verbose:
                print(
                    f'Saving data in file : {os.getcwd()}{os.sep}report-{timestamp}.csv')
        obj['data'] = df
        if verbose:
            print(
                f'Report contains {(count_elements / total_elements) * 100} % of the available dimensions')
        return obj
