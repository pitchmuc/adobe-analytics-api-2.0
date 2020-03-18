# Created by julien piccini
# email : piccini.julien@gmail.com
# version : 0.1


import json as _json
import time as _time
from concurrent import futures as _futures
from copy import deepcopy as _deepcopy
from pathlib import Path
from typing import Union, IO

import jwt as _jwt

# Non standard libraries
import pandas as _pd
import requests as _requests

# Set up default values
_org_id, _api_key, _tech_id, _pathToKey, _secret, _companyid = "", "", "", "", "", ""
_TokenEndpoint = "https://ims-na1.adobelogin.com/ims/exchange/jwt"
_orga_admin = {"_org_admin", "_deployment_admin", "_support_admin"}
_cwd = Path.as_posix(Path.cwd())
_date_limit = 0
_token = ""
_header = {}


def createConfigFile(verbose: object = False) -> None:
    """
    This function will create a 'config_admin.json' file where you can store your access data. 
    """
    json_data = {
        "org_id": "<orgID>",
        "api_key": "<APIkey>",
        "tech_id": "<something>@techacct.adobe.com",
        "secret": "<YourSecret>",
        "pathToKey": "<path/to/your/privatekey.key>",
    }
    with open("config_admin.json", "w") as cf:
        cf.write(_json.dumps(json_data, indent=4))
    if verbose:
        print(" file created at this location : " + _cwd + "/config_admin.json")


def importConfigFile(file: str) -> None:
    """
    This function will read the 'config_admin.json' to retrieve the information to be used by this module. 
    """
    global _org_id
    global _api_key
    global _tech_id
    global _pathToKey
    global _secret
    global _endpoint
    with open(file, "r") as file:
        f = _json.load(file)
        _org_id = f["org_id"]
        _api_key = f["api_key"]
        _tech_id = f["tech_id"]
        _secret = f["secret"]
        _pathToKey = f["pathToKey"]


# Launch API Endpoint
_endpoint = "https://analytics.adobe.io/api"
_endpoint_company = "https://analytics.adobe.io/api/{company_id}"


def retrieveToken(verbose: bool = False, save: bool = False, **kwargs) -> str:
    """ Retrieve the token by using the information provided by the user during the import importConfigFile function. 

    Argument : 
        verbose : OPTIONAL : Default False. If set to True, print information.
        save : OPTIONAL : Default False. If set to True, will save the token in a txt file (token.txt). 
    """
    global _token
    with open(_pathToKey, "r") as f:
        private_key_unencrypted = f.read()
        header_jwt = {
            "cache-control": "no-cache",
            "content-type": "application/x-www-form-urlencoded",
        }
    jwtPayload = {
        # Expiration set to 24 hours
        "exp": round(24 * 60 * 60 + int(_time.time())),
        "iss": _org_id,  # org_id
        "sub": _tech_id,  # technical_account_id
        "https://ims-na1.adobelogin.com/s/ent_analytics_bulk_ingest_sdk": True,
        "aud": "https://ims-na1.adobelogin.com/c/" + _api_key,
    }
    encoded_jwt = _jwt.encode(
        jwtPayload, private_key_unencrypted, algorithm="RS256"
    )  # working algorithm
    payload = {
        "client_id": _api_key,
        "client_secret": _secret,
        "jwt_token": encoded_jwt.decode("utf-8"),
    }
    response = _requests.post(_TokenEndpoint, headers=header_jwt, data=payload)
    json_response = response.json()
    token = json_response["access_token"]
    updateHeader(token=token)
    expire = json_response["expires_in"]
    global _date_limit  # getting the scope right
    _date_limit = _time.time() + expire / 1000 - 500  # end of time for the token
    if save:
        with open("token.txt", "w") as f:  # save the token
            f.write(token)
    if verbose:
        print("token valid till : " + _time.ctime(_time.time() + expire / 1000))
        print("token has been saved here : " + Path.as_posix(Path.cwd()))
    return token


def _checkToken(func):
    """decorator that checks that the token is valid before calling the API"""

    def checking(*args, **kwargs):  # if function is not wrapped, will fire
        global _date_limit
        now = _time.time()
        if now > _date_limit - 1000:
            global _token
            _token = retrieveToken(*args, **kwargs)
            return func(*args, **kwargs)
        else:  # need to return the function for decorator to return something
            return func(*args, **kwargs)

    return checking  # return the function as object


@_checkToken
def _getData(endpoint: str, params: dict = None, data=None, *args, **kwargs):
    """
    Abstraction for getting data
    """
    global _header
    if params is not None and data is None:
        res = _requests.get(endpoint, headers=_header, params=params)
    elif params is None and data is not None:
        res = _requests.get(endpoint, headers=_header, data=data)
    elif params is not None and data is not None:
        res = _requests.get(endpoint, headers=_header, params=params, data=data)
    try:
        json = res.json()
    except ValueError:
        json = {"error": ["Request Error"]}
    if res.status_code == 429:
        json["status_code"] = 429
    return json


@_checkToken
def _postData(endpoint: str, params: dict = None, data=None, *args, **kwargs):
    """
    Abstraction for getting data
    """
    global _header
    if params is not None and data is None:
        res = _requests.post(endpoint, headers=_header, params=params)
    elif params is None and data is not None:
        res = _requests.post(endpoint, headers=_header, data=_json.dumps(data))
    elif params is not None and data is not None:
        res = _requests.post(
            endpoint, headers=_header, params=params, data=_json.dumps(data=data)
        )
    try:
        json = res.json()
    except ValueError:
        json = {"error": ["Request Error"]}
    if res.status_code == 429:
        json["status_code"] = 429
    return json


@_checkToken
def _putData(endpoint: str, params: dict = None, data=None, *args, **kwargs):
    """
    Abstraction for getting data
    """
    global _header
    if params is not None and data is None:
        res = _requests.put(endpoint, headers=_header, params=params)
    elif params is None and data is not None:
        res = _requests.put(endpoint, headers=_header, data=_json.dumps(data))
    elif params is not None and data is not None:
        res = _requests.put(
            endpoint, headers=_header, params=params, data=_json.dumps(data=data)
        )
    try:
        json = res.json()
    except ValueError:
        json = {"error": ["Request Error"]}
    return json


@_checkToken
def _deleteData(endpoint: str, params: dict = None, data=None, *args, **kwargs):
    """
    Abstraction for getting data
    """
    global _header
    if params is not None and data is None:
        res = _requests.delete(endpoint, headers=_header, params=params)
    elif params is None and data is not None:
        res = _requests.delete(endpoint, headers=_header, data=_json.dumps(data))
    elif params is not None and data is not None:
        res = _requests.delete(
            endpoint, headers=_header, params=params, data=_json.dumps(data=data)
        )
    elif params is None and data is None:
        res = _requests.delete(endpoint, headers=_header)
    try:
        json = res.json()
    except:
        json = {"error": ["Request Error"]}
    return json


def updateHeader(companyid: str = None, token: str = _token, **kwargs) -> None:
    """Updates the header when new token is generated.

    This would be mandatory id you retrieved the company ID with the option "all". 
    Retrieving the company ID with option first or with a given position 
    will automatically call this method. 
    """
    global _header
    global _api_key
    global _companyid
    global _token
    global _endpoint_company
    if token:
        _token = token
    _header = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": "Bearer " + _token,
        "X-Api-Key": _api_key,
    }
    if companyid is not None:
        _header["x-proxy-global-company-id"] = companyid
        _endpoint_company = _endpoint_company.format(company_id=companyid)


@_checkToken
def getCompanyId(infos: str = "all"):
    """
    Retrieve the company id for later call for the properties.
    Can return a string or a json object.
    Arguments:
        infos : OPTIONAL: returns the amount information provided.
        Possible values:
            - all : returns the list of companies data (default value)
            - first : returns the first id (string returned)
            - <X> : number that gives the position of the id we want to return (string)
            You need to already know your position. 
    """
    res = _requests.get("https://analytics.adobe.io/discovery/me", headers=_header)
    json_res = res.json()
    if infos == "all":
        companies = json_res["imsOrgs"][0]["companies"]
        return companies
    elif infos != "all":
        if infos == "first":
            infos = "0"  # set to first position
        position = int(infos)
        companies = json_res["imsOrgs"][0]["companies"]
        global _companyid
        _companyid = companies[position]["globalCompanyId"]
        global _token
        updateHeader(companyid=_companyid, token=_token)
        return _companyid


# Endpoints
_endpoint_report = "/companies/"
_getRS = "/collections/suites"
_getDimensions = "/dimensions"
_getMetrics = "/metrics"
_getSegments = "/segments"
_getCalcMetrics = "/calculatedmetrics"
_getUsers = "/users"
_getDateRanges = "/dateranges"
_getReport = "/reports"


def getReportSuites(
    txt: str = None,
    rsid_list: str = None,
    limit: int = 100,
    extended_info: bool = False,
    save: bool = False,
) -> list:
    """
    Get the reportSuite IDs data. Returns a dataframe of reportSuite name and report suite id.
    Arguments: 
        txt : OPTIONAL : returns the reportSuites that matches a speific text field
        rsid_list : OPTIONAL : returns the reportSuites that matches the list of rsids set
        limit : OPTIONAL : How many reportSuite retrieves per serverCall 
        save : OPTIONAL : if set to True, it will save the list in a file. (Default False)

    """
    global _companyid
    params = {}
    params.update({"limit": str(limit)})
    params.update({"page": "0"})
    if txt is not None:
        params.update({"rsidContains": str(txt)})
    if rsid_list is not None:
        params.update({"rsids": str(rsid_list)})
    params.update(
        {"expansion": "name,parentRsid,currency,calendarType,timezoneZoneinfo"}
    )
    rsids = _getData(_endpoint_company + _getRS, params=params)
    content = rsids["content"]
    if not extended_info:
        list_content = [
            {"name": item["name"], "rsid": item["rsid"]} for item in content
        ]
        df_rsids = _pd.DataFrame(list_content)
    else:
        df_rsids = _pd.DataFrame(content)
    total_page = rsids["totalPages"]
    last_page = rsids["lastPage"]
    if not last_page:  # if last_page =False
        callsToMake = total_page
        list_params = [{**params, "page": page} for page in range(1, callsToMake)]
        list_urls = [_endpoint_company + _getRS for x in range(1, callsToMake)]
        workers = min(10, total_page)
        with _futures.ThreadPoolExecutor(workers) as executor:
            res = executor.map(_getData, list_urls, list_params)
        res = list(res)
        list_data = [val for sublist in [r["content"] for r in res] for val in sublist]
        if not extended_info:
            list_append = [
                {"name": item["name"], "rsid": item["rsid"]} for item in list_data
            ]
            df_append = _pd.DataFrame(list_append)
        else:
            df_append = _pd.DataFrame(list_data)
        df_rsids = df_rsids.append(df_append, ignore_index=True)
    if save:
        df_rsids.to_csv("RSIDS.csv", sep="\t")
    return df_rsids


def getDimensions(rsid: str, tags: bool = False, save=False, **kwargs) -> object:
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
        params.update({"expansion": "tags"})
    params.update({"rsid": rsid})
    dims = _getData(_endpoint_company + _getDimensions, params=params)
    df_dims = _pd.DataFrame(dims)
    columns = ["id", "name", "category", "type", "parent", "pathable", "description"]
    if kwargs.get("full", False):
        new_cols = _pd.DataFrame(
            df_dims.support.values.tolist(), columns=["support_oberon", "support_dw"]
        )  # extract list in column
        new_df = df_dims.merge(new_cols, right_index=True, left_index=True)
        new_df.drop(["reportable", "support"], axis=1, inplace=True)
        df_dims = new_df
    else:
        df_dims = df_dims[columns]
    df_dims.to_csv(f"dimensions_{rsid}.csv")
    return df_dims


def getMetrics(rsid: str, tags: bool = False, save=False, **kwargs) -> object:
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
        params.update({"expansion": "tags"})
    params.update({"rsid": rsid})
    metrics = _getData(_endpoint_company + _getMetrics, params=params)
    df_metrics = _pd.DataFrame(metrics)
    columns = [
        "id",
        "name",
        "category",
        "type",
        "dataGroup",
        "precision",
        "segmentable",
    ]
    if kwargs.get("full", False):
        new_cols = _pd.DataFrame(
            df_metrics.support.values.tolist(), columns=["support_oberon", "support_dw"]
        )
        new_df = df_metrics.merge(new_cols, right_index=True, left_index=True)
        new_df.drop("support", axis=1, inplace=True)
        df_metrics = new_df
    else:
        df_metrics = df_metrics[columns]
    if save:
        df_metrics.to_csv(f"metrics_{rsid}.csv", sep="\t")
    return df_metrics


def getUsers(save: bool = False, **kwargs) -> object:
    """
    Retrieve the list of users for a login company.Returns a data frame.
    Arguments:
        save : OPTIONAL : Save the data in a file (bool : default False). 
    Possible kwargs: 
        limit : OPTIONAL : Nummber of results per requests. Default 100. 
    """
    nb_error, nb_empty = 0, 0  # use for multi-thread loop
    params = {"limit": 100}
    if kwargs.get("limit", False):
        if type(kwargs.get("limit")) == str:
            limit = int(kwargs.get("limit"))
        else:
            limit = kwargs.get("limit")
        params.update({"limit": limit})
    users = _getData(_endpoint_company + _getUsers, params=params)
    data = users["content"]
    lastPage = users["lastPage"]
    if not lastPage:  # check if lastpage is inversed of False
        callsToMake = users["totalPages"]
        list_params = [{"limit": 100, "page": page} for page in range(1, callsToMake)]
        list_urls = [_endpoint_company + _getUsers for x in range(1, callsToMake)]
        workers = min(10, len(list_params))
        with _futures.ThreadPoolExecutor(workers) as executor:
            res = executor.map(_getData, list_urls, list_params)
        res = list(res)
        users_lists = [elem["content"] for elem in res if "content" in elem.keys()]
        nb_error = sum(1 for elem in res if "error_code" in elem.keys())
        nb_empty = sum(
            1 for elem in res if "content" in elem.keys() and len(elem["content"]) == 0
        )
        append_data = [
            val for sublist in [data for data in users_lists] for val in sublist
        ]  # flatten list of list
        data = data + append_data
    df_users = _pd.DataFrame(data)
    columns = [
        "email",
        "login",
        "fullName",
        "firstName",
        "lastName",
        "admin",
        "loginId",
        "imsUserId",
        "login",
        "createDate",
        "lastAccess",
        "title",
        "disabled",
        "phoneNumber",
        "companyid",
    ]
    df_users = df_users[columns]
    df_users["createDate"] = _pd.to_datetime(df_users["createDate"])
    df_users["lastAccess"] = _pd.to_datetime(df_users["lastAccess"])
    if save:
        df_users.to_csv("users.csv", sep="\t")
    if nb_error > 0 or nb_empty > 0:
        print(
            f"WARNING : Retrieved data are partial.\n{nb_error}/{len(list_urls)} requests returned an error.\n{nb_empty}/{len(list_urls)} requests returned an empty response. \nTry to use filter to retrieve segments"
        )
    return df_users


def getSegments(
    name: str = None,
    tagNames: str = None,
    inclType: str = "all",
    rsids_list: list = None,
    sidFilter: list = None,
    extended_info: bool = False,
    json_format=False,
    save: bool = False,
    **kwargs,
) -> object:
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
            additional infos: reportSuiteName, ownerFullName, modified, tags, compatibility, definition
        json_format : OPTIONAL : Define the output format for the object returned. Save will always be a dataframe. 
        save : OPTIONAL : If set to True, it will save the info in a csv file (bool : default False)

    Possible kwargs:
        limit : number of segments retrieved by request. default 500: Limited to 1000 by the AnalyticsAPI.

    NOTE : Segment Endpoint doesn't support multi-threading. Default to 500. 
    """
    limit = int(kwargs.get("limit", 500))
    params = {"includeType": "all", "limit": limit}
    if extended_info:
        params.update(
            {
                "expansion": "reportSuiteName,ownerFullName,modified,tags,compatibility,definition"
            }
        )
    if name is not None:
        params.update({"name": str(name)})
    if tagNames is not None:
        if type(tagNames) == list:
            tagNames = ",".join(tagNames)
        params.update({"tagNames": tagNames})
    if inclType != "all":
        params["includeType"] = inclType
    if rsids_list is not None:
        if type(rsids_list) == list:
            rsids_list = ",".join(rsids_list)
        params.update({"rsids": rsids_list})
    if sidFilter is not None:
        if type(sidFilter) == list:
            sidFilter = ",".join(sidFilter)
        params.update({"rsids": sidFilter})
    data = []
    lastPage = False
    page_nb = 0
    while not lastPage:
        params["page"] = page_nb
        segs = _getData(_endpoint_company + _getSegments, params=params)
        data += segs["content"]
        lastPage = segs["lastPage"]
        page_nb += 1
    df_segments = _pd.DataFrame(data)
    if save:
        df_segments.to_csv("segments.csv", sep="\t")
    if not json_format:
        return data
    else:
        return df_segments


def createSegment(segmentJSON: dict = None) -> object:
    """
    Method that creates a new segment based on the dictionary passed to it.
    Arguments:
        segmentJSON : REQUIRED : the dictionary that represents the JSON statement for the segment. 
    """
    if segmentJSON is None:
        print("No segment data has been pushed")
        return None
    data = _deepcopy(segmentJSON)
    seg = _postData(_endpoint_company + _getSegments, data=data)
    return seg


def updateSegment(segmentID: str = None, segmentJSON: dict = None) -> object:
    """
    Method that update a specific segment based on the dictionary passed to it.
    Arguments:
        segmentID : REQUIRED : Segment ID to be deleted
        segmentJSON : REQUIRED : the dictionary that represents the JSON statement for the segment. 
    """
    if segmentJSON is None or segmentID is None:
        print("No segment or segementID data has been pushed")
        return None
    data = _deepcopy(segmentJSON)
    seg = _putData(_endpoint_company + _getSegments + "/" + segmentID, data=data)
    return seg


def deleteSegment(segmentID: str = None) -> object:
    """
    Method that update a specific segment based on the dictionary passed to it.
    Arguments:
        segmentID : REQUIRED : Segment ID to be deleted
    """
    if segmentID is None:
        print("No segementID data has been pushed")
        return None
    seg = _deleteData(_endpoint_company + _getSegments + "/" + segmentID)
    return seg


def getCalculatedMetrics(
    name: str = None,
    tagNames: str = None,
    inclType: str = "all",
    rsids_list: list = None,
    extended_info: bool = False,
    save=False,
    **kwargs,
) -> object:
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
    limit = int(kwargs.get("limit", 500))
    params = {"includeType": "all", "limit": limit}
    if name is not None:
        params.update({"name": str(name)})
    if tagNames is not None:
        if type(tagNames) == list:
            tagNames = ",".join(tagNames)
        params.update({"tagNames": tagNames})
    if inclType != "all":
        params["includeType"] = inclType
    if rsids_list is not None:
        if type(rsids_list) == list:
            rsids_list = ",".join(rsids_list)
        params.update({"rsids": rsids_list})
    if extended_info:
        params.update(
            {
                "expansion": "reportSuiteName,definition,ownerFullName,modified,tags,categories,compatibility"
            }
        )
    metrics = _getData(_endpoint_company + _getCalcMetrics, params=params)
    data = metrics["content"]
    lastPage = metrics["lastPage"]
    if not lastPage:  # check if lastpage is inversed of False
        page_nb = 0
        while not lastPage:
            page_nb += 1
            params["page"] = page_nb
            metrics = _getData(_endpoint_company + _getCalcMetrics, params=params)
            data += metrics["content"]
            lastPage = metrics["lastPage"]
    df_calc_metrics = _pd.DataFrame(data)
    if save:
        df_calc_metrics.to_csv("calculated_metrics.csv", sep="\t")
    return df_calc_metrics


def deleteCalculatedMetrics(calcID: str = None) -> object:
    """
    Method that update a specific segment based on the dictionary passed to it.
    Arguments:
        calcID : REQUIRED : Calculated Metrics ID to be deleted
    """
    if calcID is None:
        print("No calculated metrics data has been pushed")
        return None
    cm = _deleteData(_endpoint_company + _getCalcMetrics + "/" + calcID)
    return cm


def getDateRanges(extended_info: bool = False, save: bool = False, **kwargs) -> object:
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
    limit = int(kwargs.get("limit", 500))
    params = {"limit": limit, "includeType": ["all"]}
    if extended_info:
        params.update({"expansion": "definition,ownerFullName,modified,tags"})
    dateRanges = _getData(_endpoint_company + _getDateRanges, params=params)
    data = dateRanges["content"]
    df_dates = _pd.DataFrame(data)
    return df_dates


def _dataDescriptor(json_request: dict):
    """
    read the request and returns an object with information about the request.
    It will be used in order to build the dataclass and the dataframe.
    """
    obj = {}
    obj["dimension"] = json_request["dimension"]
    obj["filters"] = {"globalFilters": [], "metricsFilters": {}}
    obj["rsid"] = json_request["rsid"]
    metrics_info = json_request["metricContainer"]
    obj["metrics"] = [metric["id"] for metric in metrics_info["metrics"]]
    if "metricFilters" in metrics_info.keys():
        metricsFilter = {
            metric["id"]: metric["filters"]
            for metric in metrics_info["metrics"]
            if len(metric.get("filters", [])) > 0
        }
        filters = []
        for metric in metricsFilter:
            for item in metricsFilter[metric]:
                if "segmentId" in metrics_info["metricFilters"][int(item)].keys():
                    filters.append(
                        metrics_info["metricFilters"][int(item)]["segmentId"]
                    )
                if "dimension" in metrics_info["metricFilters"][int(item)].keys():
                    filters.append(
                        metrics_info["metricFilters"][int(item)]["dimension"]
                    )
                obj["filters"]["metricsFilters"][metric] = set(filters)
    for fil in json_request["globalFilters"]:
        if "dateRange" in fil.keys():
            obj["filters"]["globalFilters"].append(fil["dateRange"])
        if "dimension" in fil.keys():
            obj["filters"]["globalFilters"].append(fil["dimension"])
        if "segmentId" in fil.keys():
            obj["filters"]["globalFilters"].append(fil["segmentId"])
    return obj


def _readData(
    data_rows: list, anomaly: bool = False, cols: list = None, item_id: bool = False
):
    """
    read the data from the requests and returns a dataframe. 
    Parameters:
        data_rows : REQUIRED : Rows that have been returned by the request.
        anomaly : OPTIONAL : Boolean to tell if the anomaly detection has been used. 
        cols : OPTIONAL : list of columns names
    """
    data_rows = _deepcopy(data_rows)
    dict_data = {}
    dict_data = {row["value"]: row["data"] for row in data_rows}
    if cols is not None:
        n_metrics = len(cols) - 1
    if item_id:  # adding the itemId in the data returned
        cols.append("item_id")
        for row in data_rows:
            dict_data[row["value"]].append(row["itemId"])
    if anomaly:
        # set full columns
        cols = cols + [
            f"{metric}-{suffix}"
            for metric in cols[1:]
            for suffix in ["expected", "UpperBound", "LowerBound"]
        ]
        # add data to the dictionary
        for row in data_rows:
            for item in range(n_metrics):
                dict_data[row["value"]].append(
                    row.get("dataExpected", [0 for i in range(n_metrics)])[item]
                )
                dict_data[row["value"]].append(
                    row.get("dataUpperBound", [0 for i in range(n_metrics)])[item]
                )
                dict_data[row["value"]].append(
                    row.get("dataLowerBound", [0 for i in range(n_metrics)])[item]
                )
    df = _pd.DataFrame(dict_data).T  # require to transform the data
    df.reset_index(inplace=True,)
    df.columns = cols
    return df


def getReport(
    json_request: Union[dict, str, IO],
    n_result: Union[int, str] = 1000,
    save: bool = False,
    item_id: bool = False,
    verbose: bool = False,
    debug=False,
) -> object:
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
    if type(json_request) == str and ".json" not in json_request:
        try:
            request = _json.loads(json_request)
        except:
            raise TypeError("expected a parsable string")
    elif type(json_request) == dict:
        request = json_request
    elif ".json" in json_request:
        try:
            with open(json_request, "r") as file:
                file_string = file.read()
            request = _json.loads(file_string)
        except:
            raise TypeError("expected a parsable string")
    request["settings"]["limit"] = 1000
    # info for creating report
    data_info = _dataDescriptor(request)
    if verbose:
        print("Request decrypted")
    obj.update(data_info)
    anomaly = request["settings"].get("includeAnomalyDetection", False)
    columns = [data_info["dimension"]] + data_info["metrics"]
    # preparing for the loop
    # in case "inf" has been used. Turn it to a number
    n_result = float(n_result)
    if n_result != float("inf") and n_result < request["settings"]["limit"]:
        # making sure we don't call more than set in wrapper
        request["settings"]["limit"] = n_result
    data_list = []
    last_page = False
    page_nb, count_elements, total_elements = 0, 0, 0
    if verbose:
        print("Starting to fetch the data...")
    while last_page == False:
        timestamp = round(_time.time())
        request["settings"]["page"] = page_nb
        report = _postData(_endpoint_company + _getReport, data=request)
        if verbose:
            print("Data received.")
        # Recursion to take care of throttling limit
        if report.get("status_code", 200) == 429:
            if verbose:
                print("reaching the limit : pause for 60 s and entering recursion.")
            if debug:
                with open(f"limit_reach_{timestamp}.json", "w") as f:
                    f.write(_json.dumps(report, indent=4))
            _time.sleep(50)
            obj = getReport(
                json_request=request,
                n_result=n_result,
                save=save,
                item_id=item_id,
                verbose=verbose,
            )
            return obj
        if "lastPage" not in report:  # checking error when no lastPage key in report
            if verbose:
                print(_json.dumps(report, indent=2))
            print("Warning : Server Error - no save file & empty dataframe.")
            if debug:
                with open(f"server_failure_request_{timestamp}.json", "w") as f:
                    f.write(_json.dumps(request, indent=4))
                with open(f"server_failure_response_{timestamp}.json", "w") as f:
                    f.write(_json.dumps(report, indent=4))
                print(
                    f"Warning : Save JSON request : server_failure_request_{timestamp}.json"
                )
                print(
                    f"Warning : Save JSON response : server_failure_response_{timestamp}.json"
                )
            obj["data"] = _pd.DataFrame()
            return obj
        # fallback when no lastPage in report
        last_page = report.get("lastPage", True)
        if verbose:
            print(f"last page status : {last_page}")
        if "errorCode" in report.keys():
            print("Error with your statement \n" + report["errorDescription"])
            return {report["errorCode"]: report["errorDescription"]}
        count_elements += report.get("numberOfElements", 0)
        total_elements = report.get("totalElements", request["settings"]["limit"])
        if total_elements == 0:
            obj["data"] = _pd.DataFrame()
            print(
                "Warning : No data returned & lastPage is False.\nExit the loop - no save file & empty dataframe."
            )
            if debug:
                with open(f"report_no_element_{timestamp}.json", "w") as f:
                    f.write(_json.dumps(report, indent=4))
            if verbose:
                print(
                    f'% of total elements retrieved. TotalElements: {report.get("totalElements","no data")}'
                )
            return obj  # in case loop happening with empty data, returns empty data
        if verbose and total_elements != 0:
            print(
                f"% of total elements retrieved: {round((count_elements/total_elements)*100,2)} %"
            )
        if last_page == False and n_result != float("inf"):
            if count_elements >= n_result:
                last_page = True
        data = report["rows"]
        data_list += _deepcopy(data)  # do a deepcopy
        page_nb += 1
        if verbose:
            print(f"# of requests : {page_nb}")
    # return report
    df = _readData(data_list, anomaly=anomaly, cols=columns, item_id=item_id)
    if save:
        df.to_csv(f"report-{timestamp}.csv", index=False)
        if verbose:
            print(f"Saving data in file : report-{timestamp}.csv")
    obj["data"] = df
    if verbose:
        print(
            f"Report contains {(count_elements / total_elements) * 100} % of the available dimensions"
        )
    return obj
