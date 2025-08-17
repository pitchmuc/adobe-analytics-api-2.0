import json
from copy import deepcopy
from aanalytics2 import config, connector
from typing import Union

class DataRepair:

    def __init__(self, 
                 company_id:str=None,
                 config_object: dict = config.config_object,
                 header: dict = config.header,
                 retry: int = 0,):
        """
        Instantiate the DataRepair class.
        Once instantiateed, the class will be connected to the Data Repair API and has generated a token.
        Arguments:
            company_id : REQUIRED : the company id to be used for the request.
            config_object : OPTIONAL : the configuration object to be used for the request.
            header : OPTIONAL : the header to be used for the request.
            retry : OPTIONAL : If you wish to retry failed GET requests
        
        """
        self.companyId = company_id
        self.endpoint = f"https://analytics.adobe.io/api/{company_id}/datarepair/v1"
        self.connector = connector.AdobeRequest(
            config_object=config_object, header=header, retry=retry,company_id=company_id)
        self.header = self.connector.header
        self.VARIABLES = {
            "activitymap": ["delete"],
            "campaign": ["set","delete","deleteQueryString","deleteQueryStringParameters"],
            "entrypage": ["set","delete","deleteQueryString","deleteQueryStringParameters"],
            "entrypageoriginal": ["set","delete","deleteQueryString","deleteQueryStringParameters"],
            "evar1 - evar250": ["set","delete","deleteQueryString","deleteQueryStringParameters"],
            "geodma": ["delete"],
            "geocity": ["delete"],
            "geocountry": ["delete"],
            "geolatitude":["delete"],
            "geolongitude": ["delete"],
            "georegion": ["delete"],
            "geozip": ["delete"],
            "ipaddress": ["delete"],
            "latitude": ["delete"],
            "longitude": ["delete"],
            "latlon1":["delete"],
            "latlon23":["delete"],
            "latlon45":["delete"],
            "pointofinterest":["delete"],
            "pointofinterestdistance": ["delete"],
            "mobileaction": ["delete"],
            "mobileappid":["set","delete","deleteQueryString","deleteQueryStringParameters"],
            "mobilemessagebuttonname":["set","delete","deleteQueryString","deleteQueryStringParameters"],
            "mobilemessageid":["set","delete","deleteQueryString","deleteQueryStringParameters"],
            "mobilerelaunchcampaigncontent":["set","delete","deleteQueryString","deleteQueryStringParameters"],
            "mobilerelaunchcampaignmedium":["set","delete","deleteQueryString","deleteQueryStringParameters"],
            "mobilerelaunchcampaignsource":["set","delete","deleteQueryString","deleteQueryStringParameters"],
            "mobilerelaunchcampaignterm":["set","delete","deleteQueryString","deleteQueryStringParameters"],
            "mobilerelaunchcampaigntrackingcode":["set","delete","deleteQueryString","deleteQueryStringParameters"],
            "page": ["set","deleteQueryString","deleteQueryStringParameters"],
            "pageeventvar1": ["set","deleteQueryString","deleteQueryStringParameters"],
            "pageeventvar2": ["set","deleteQueryString","deleteQueryStringParameters"],
            "pageurl": ["deleteQueryString","deleteQueryStringParameters"],
            "pageurlfirsthit":["deleteQueryString","deleteQueryStringParameters"],
            "pageurlvisitstart": ["deleteQueryString","deleteQueryStringParameters"],
            "prop1 - prop75": ["set","delete","deleteQueryString","deleteQueryStringParameters"],
            "referrer": ["deleteQueryString","deleteQueryStringParameters"],
            "referrerfirsthit": ["deleteQueryString","deleteQueryStringParameters"],
            "referrervisit": ["deleteQueryString","deleteQueryStringParameters"],
            "sitesections": ["set","delete","deleteQueryString","deleteQueryStringParameters"],
            "video": ["set","deleteQueryString","deleteQueryStringParameters"],
            "videoad": ["set","deleteQueryString","deleteQueryStringParameters"],
            "videoadname": ["set","delete","deleteQueryString","deleteQueryStringParameters"],
            "videoadplayername": ["set","delete","deleteQueryString","deleteQueryStringParameters"],
            "videoadadvertiser": ["set","delete","deleteQueryString","deleteQueryStringParameters"],
            "videoaudioalbum": ["set","delete","deleteQueryString","deleteQueryStringParameters"],
            "videoaudioartist": ["set","delete","deleteQueryString","deleteQueryStringParameters"],
            "videoaudioauthor": ["set","delete","deleteQueryString","deleteQueryStringParameters"],
            "videoaudiolabel": ["set","delete","deleteQueryString","deleteQueryStringParameters"],
            "videoaudiopublisher": ["set","delete","deleteQueryString","deleteQueryStringParameters"],
            "videoaudiostation": ["set","delete","deleteQueryString","deleteQueryStringParameters"],
            "videoadcampaign": ["set","delete","deleteQueryString","deleteQueryStringParameters"],
            "videochannel": ["set","delete","deleteQueryString","deleteQueryStringParameters"],
            "videochapter": ["set","delete","deleteQueryString","deleteQueryStringParameters"],
            "videocontenttype": ["set","delete","deleteQueryString","deleteQueryStringParameters"],
            "videoepisode": ["set","delete","deleteQueryString","deleteQueryStringParameters"],
            "videofeedtype": ["set","delete","deleteQueryString","deleteQueryStringParameters"],
            "videomvpd": ["set","delete","deleteQueryString","deleteQueryStringParameters"],
            "videoname": ["set","delete","deleteQueryString","deleteQueryStringParameters"],
            "videonetwork": ["set","delete","deleteQueryString","deleteQueryStringParameters"],
            "videopath": ["set","delete","deleteQueryString","deleteQueryStringParameters"],
            "videoplayername": ["set","delete","deleteQueryString","deleteQueryStringParameters"],
            "videoseason": ["set","delete","deleteQueryString","deleteQueryStringParameters"],
            "videoshow": ["set","delete","deleteQueryString","deleteQueryStringParameters"],
            "videoshowtype": ["set","delete","deleteQueryString","deleteQueryStringParameters"],
            "videostreamtype": ["set","delete","deleteQueryString","deleteQueryStringParameters"],
            "zip": ["delete"]
            }

    
    def getEstimate(self,
                    dateStart:str=None,
                    dateEnd:str=None, 
                    rsid:str=None) -> dict:
        """
        Calculates the number of Server Calls for the given Report Suite and date range provided.
        It also returns a validationToken, which is required to use the Job endpoint.
        Arguments:
            dateStart: REQUIRED : The start date for the estimate in ISO format (YYYY-MM-DD).
            dateEnd: REQUIRED : The end date for the estimate in ISO format (YYYY-MM-DD).
            rsid: OPTIONAL : The report suite ID to be used for the estimate.
        Returns:
            dict: The estimate data as a dictionary.
        """
        if not dateStart or not dateEnd:
            raise ValueError("Both dateStart and dateEnd are required")
        
        params = {
            'dateRangeEnd': dateStart,
            'dateRangeStart': dateEnd
        }
        path = f"/{rsid}/serverCallEstimate"
        response = self.connector.getData(self.endpoint + path, params=params)
        return response
    
    def createJob(self,rsid:str=None,data:Union[dict,'DataRepairJobCreator',str]=None) -> dict:
        """
        Create a job for data repair.
        Arguments:
            rsid: REQUIRED : The report suite ID to be used for the job.
            data: REQUIRED : DataRepairJobCreator instance or dictionary containing the job data or JSON file path.
        Returns:
            dict: The response from the API as a dictionary.
        """
        if isinstance(data, DataRepairJobCreator):
            data = data.to_dict()
        elif isinstance(data, dict):
            data = deepcopy(data)
        elif isinstance(data, str):
            if data.endswith('.json'):
                try:
                    with open(data, 'r') as f:
                        data = json.load(f)
                except FileNotFoundError as e:
                    raise ValueError(f"File not found: {e}")
                except json.JSONDecodeError as e:
                    raise ValueError(f"Invalid JSON file: {e}")
            else:
                raise ValueError("String data must be a path to a JSON file")
        else:
            raise TypeError("Data must be a DataRepairJobCreator instance or a dictionary")
        path = f"/{rsid}/job"
        response = self.connector.postData(self.endpoint + path, json=data)
        return response
    
    def getJobs(self, rsid: str = None) -> list:
        """
        Get all jobs for the given report suite ID.
        Arguments:
            rsid: REQUIRED : The report suite ID to be used for fetching jobs.
        Returns:
            list: the list of jobs.
        """
        path = f"/{rsid}/job"
        response = self.connector.getData(self.endpoint + path)
        return response
    
    def getJob(self, rsid: str = None, jobId: str = None) -> dict:
        """
        Get a specific job by its ID for the given report suite ID.
        Arguments:
            rsid: REQUIRED : The report suite ID to be used for fetching the job.
            jobId: REQUIRED : The job ID to be fetched.
        Returns:
            dict: The job data as a dictionary.
        """
        if not jobId:
            raise ValueError("jobId is required")
        path = f"/{rsid}/job/{jobId}"
        response = self.connector.getData(self.endpoint + path)
        return response
    
    def getUsage(self, dateStart:str=None, dateEnd:str=None,rsid: str = None) -> dict:
        """
        Get the usage for the given report suite ID.
        If no start and end dates are provided, it will return the usage for last 30 days.
        If only one of the dates is provided, it will take 30 days from the provided date
        Arguments:
            dateStart: REQUIRED : The start date for the usage in ISO format (YYYY-MM-DD).
            dateEnd: REQUIRED : The end date for the usage in ISO format (YYYY-MM-DD).
            rsid: OPTIONAL : If you want to see the usage for a single report suite ID.
        Returns:
            dict: The usage data as a dictionary.
        """
        if dateStart is None or dateEnd is None:
            dateStart = (datetime.now() - timedelta(days=30)).date().isoformat()
            dateEnd = datetime.now().date().isoformat()
        elif dateStart is None and dateEnd is not None:
            dateStart = (datetime.fromisoformat(dateEnd) - timedelta(days=30)).date().isoformat()
        elif dateStart is not None and dateEnd is None:
            dateEnd = (datetime.fromisoformat(dateStart) + timedelta(days=30)).date().isoformat()
        if rsid is None:
            path = f"/usage"
        else:
            path = f"/{rsid}/usage"
        params = {
            'dateRangeEnd': dateEnd,
            'dateRangeStart': dateStart
        }
        response = self.connector.getData(self.endpoint + path,params=params)
        return response


class DataRepairJobCreator:

    def __init__(self,data:Union[dict,str]=None):
        """
        Initialize the DataRepairJobCreator class.
        This class is used to create a job for data repair.
        Arguments:
            data: OPTIONAL : A dictionary or a JSON string containing the job data.
        """
        self.__data__ = {
            "variables":{

            }
        }
        if data is not None:
            if isinstance(data, str):
                if data.endswith('.json'):
                    try:
                        self.__data__ = json.loads(data)
                    except json.JSONDecodeError as e:
                        raise ValueError(f"Invalid JSON string: {e}")
            elif isinstance(data, dict):
                self.__data__ = deepcopy(data)
            else:
                raise TypeError("Data must be a dictionary or a JSON string")
        self.VARIABLES = {
            "activitymap": ["delete"],
            "campaign": ["set","delete","deleteQueryString","deleteQueryStringParameters"],
            "entrypage": ["set","delete","deleteQueryString","deleteQueryStringParameters"],
            "entrypageoriginal": ["set","delete","deleteQueryString","deleteQueryStringParameters"],
            "evar1 - evar250": ["set","delete","deleteQueryString","deleteQueryStringParameters"],
            "geodma": ["delete"],
            "geocity": ["delete"],
            "geocountry": ["delete"],
            "geolatitude":["delete"],
            "geolongitude": ["delete"],
            "georegion": ["delete"],
            "geozip": ["delete"],
            "ipaddress": ["delete"],
            "latitude": ["delete"],
            "longitude": ["delete"],
            "latlon1":["delete"],
            "latlon23":["delete"],
            "latlon45":["delete"],
            "pointofinterest":["delete"],
            "pointofinterestdistance": ["delete"],
            "mobileaction": ["delete"],
            "mobileappid":["set","delete","deleteQueryString","deleteQueryStringParameters"],
            "mobilemessagebuttonname":["set","delete","deleteQueryString","deleteQueryStringParameters"],
            "mobilemessageid":["set","delete","deleteQueryString","deleteQueryStringParameters"],
            "mobilerelaunchcampaigncontent":["set","delete","deleteQueryString","deleteQueryStringParameters"],
            "mobilerelaunchcampaignmedium":["set","delete","deleteQueryString","deleteQueryStringParameters"],
            "mobilerelaunchcampaignsource":["set","delete","deleteQueryString","deleteQueryStringParameters"],
            "mobilerelaunchcampaignterm":["set","delete","deleteQueryString","deleteQueryStringParameters"],
            "mobilerelaunchcampaigntrackingcode":["set","delete","deleteQueryString","deleteQueryStringParameters"],
            "page": ["set","deleteQueryString","deleteQueryStringParameters"],
            "pageeventvar1": ["set","deleteQueryString","deleteQueryStringParameters"],
            "pageeventvar2": ["set","deleteQueryString","deleteQueryStringParameters"],
            "pageurl": ["deleteQueryString","deleteQueryStringParameters"],
            "pageurlfirsthit":["deleteQueryString","deleteQueryStringParameters"],
            "pageurlvisitstart": ["deleteQueryString","deleteQueryStringParameters"],
            "prop1 - prop75": ["set","delete","deleteQueryString","deleteQueryStringParameters"],
            "referrer": ["deleteQueryString","deleteQueryStringParameters"],
            "referrerfirsthit": ["deleteQueryString","deleteQueryStringParameters"],
            "referrervisit": ["deleteQueryString","deleteQueryStringParameters"],
            "sitesections": ["set","delete","deleteQueryString","deleteQueryStringParameters"],
            "video": ["set","deleteQueryString","deleteQueryStringParameters"],
            "videoad": ["set","deleteQueryString","deleteQueryStringParameters"],
            "videoadname": ["set","delete","deleteQueryString","deleteQueryStringParameters"],
            "videoadplayername": ["set","delete","deleteQueryString","deleteQueryStringParameters"],
            "videoadadvertiser": ["set","delete","deleteQueryString","deleteQueryStringParameters"],
            "videoaudioalbum": ["set","delete","deleteQueryString","deleteQueryStringParameters"],
            "videoaudioartist": ["set","delete","deleteQueryString","deleteQueryStringParameters"],
            "videoaudioauthor": ["set","delete","deleteQueryString","deleteQueryStringParameters"],
            "videoaudiolabel": ["set","delete","deleteQueryString","deleteQueryStringParameters"],
            "videoaudiopublisher": ["set","delete","deleteQueryString","deleteQueryStringParameters"],
            "videoaudiostation": ["set","delete","deleteQueryString","deleteQueryStringParameters"],
            "videoadcampaign": ["set","delete","deleteQueryString","deleteQueryStringParameters"],
            "videochannel": ["set","delete","deleteQueryString","deleteQueryStringParameters"],
            "videochapter": ["set","delete","deleteQueryString","deleteQueryStringParameters"],
            "videocontenttype": ["set","delete","deleteQueryString","deleteQueryStringParameters"],
            "videoepisode": ["set","delete","deleteQueryString","deleteQueryStringParameters"],
            "videofeedtype": ["set","delete","deleteQueryString","deleteQueryStringParameters"],
            "videomvpd": ["set","delete","deleteQueryString","deleteQueryStringParameters"],
            "videoname": ["set","delete","deleteQueryString","deleteQueryStringParameters"],
            "videonetwork": ["set","delete","deleteQueryString","deleteQueryStringParameters"],
            "videopath": ["set","delete","deleteQueryString","deleteQueryStringParameters"],
            "videoplayername": ["set","delete","deleteQueryString","deleteQueryStringParameters"],
            "videoseason": ["set","delete","deleteQueryString","deleteQueryStringParameters"],
            "videoshow": ["set","delete","deleteQueryString","deleteQueryStringParameters"],
            "videoshowtype": ["set","delete","deleteQueryString","deleteQueryStringParameters"],
            "videostreamtype": ["set","delete","deleteQueryString","deleteQueryStringParameters"],
            "zip": ["delete"]
            }
    
    def __str__(self):
        return json.dumps(self.__data__, indent=4)
    
    def __repr__(self):
        return json.dumps(self.__data__, indent=2)
    
    def addVariable(self,variableId:str=None,action:str=None,value:str=None,filterCondition:str=None,matchValues:Union[list,str]=None,filterVariable:str=None):
        """
        Add a variable to the job.
        Arguments:
            variableId: REQUIRED : The variable ID to be added.
            action: REQUIRED : The action to be performed. Choose from "set", "delete", "deleteQueryString", "deleteQueryStringParameters"
            value: REQUIRED if action is "set" : The value to be set for the variable.
            filterCondition: OPTIONAL : The filter condition to be applied. 
                Choose from "inList", "isEmpty", "contains", "doesNotContain", "startsWith",doesNotStartWith", "endsWith", "doesNotEndWith", "isURL", "isNotURL","isNumeric","isNotNumeric".
            matchValues: OPTIONAL : The list of values to be matched for the filter condition.
            filterVariable: OPTIONAL : The variable to be used for the filtering of the original variable.
        """
        var = {"action":action}
        if value:
            var['setValue'] = value
        if filterCondition:
            if 'filter' not in var.keys():
                var['filter'] = {}
            var['filter']['condition'] = filterCondition
        if matchValues:
            if 'filter' not in var.keys():
                var['filter'] = {}
            if isinstance(matchValues, str):
                var['filter']['matchValue'] = matchValues
            elif isinstance(matchValues, list):
                var['filter']['matchValues'] = matchValues
        if filterVariable:
            if 'filter' not in var.keys():
                var['filter'] = {}
            var['filter']['variable'] = filterVariable
        self.__data__['variables'][variableId] = deepcopy(var)
    
    def to_dict(self):
        """
        Convert the job data to a dictionary.
        Returns:
            dict: The job data as a dictionary.
        """
        return deepcopy(self.__data__)
    
    
