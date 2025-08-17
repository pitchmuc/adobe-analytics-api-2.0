import json
from copy import deepcopy
from typing import Union

class DwhCreator:

    def __init__(self, data: Union[str, dict] = None):
        """
        Initialize the Data Warehouse Creator with data.
        Arguments:
            data: OPTIONAL :  can be a JSON file path or a dictionary containing Data Warehouse data.
        """
        self.__data__ = {'request':{'reportParameters':{'dimensionList':[],'metricList':[],'segmentList':[]}},'delivery':{}}
        if isinstance(data, str):
            if data.endswith('.json'):
                with open(data, 'r') as file:
                    self.__data__ = json.load(file)
        elif isinstance(data, dict):
            self.__data__ = deepcopy(data)

    def __str__(self):
        return json.dumps(self.__data__, indent=4)
    
    def __repr__(self):
        return json.dumps(self.__data__, indent=2)
    
    def to_dict(self):
        """
        Convert the Data Warehouse data to a dictionary.
        Returns:
            dict: The Data Warehouse data as a dictionary.
        """
        return deepcopy(self.__data__)
    
    def setName(self, name: str):
        """
        Set the name for the Data Warehouse.
        Arguments:
            name: REQUIRED : Name to be used for the Data Warehouse.
        """
        if not name:
            raise ValueError("Name cannot be empty")
        self.__data__['request']['name'] = name
    
    def setRSID(self, rsid: str):
        """
        Set the report suite ID for the Data Warehouse.
        Arguments:
            rsid: REQUIRED : Report suite ID to be used for the Data Warehouse.
        """
        if not rsid:
            raise ValueError("Report suite ID cannot be empty")
        self.__data__['request']['rsid'] = rsid

    def setReportRange(self,preset:str=None,startDateTime: str=None, endDateTime: str=None):
        """
        Set the report range for the Data Warehouse.
        Arguments:
            preset: OPTIONAL : Preset for the report range, possible values: "Yesterday", "Today", "last_7_days", "last_30_days", "last_90_days", "last_365_days".
            startDateTime: REQUIRED : Start date and time in ISO format (YYYY-MM-DDTHH:MM:SSZ).
            endDateTime: REQUIRED : End date and time in ISO format (YYYY-MM-DDTHH:MM:SSZ).
        """
        if not startDateTime or not endDateTime:
            raise ValueError("Start and end date times cannot be empty")
        if preset:
            self.__data__['request']['reportParameters']['reportRange'] = {'preset': preset}
        else:       
            self.__data__['request']['reportParameters']['reportRange'] = {
                'startDateTime': startDateTime,
                'endDateTime': endDateTime
            }
    
    def addDimension(self, dimensionId: str,**kwargs):
        """
        Add a dimension to the Data Warehouse request.
        Arguments:
            dimensionId: REQUIRED : The ID of the dimension to be added.
                Example: "variables/geocity", "variables/prop1", "s0_000000000000000000000000"
        possible kwargs:
            additionalProperties
        """
        if not dimensionId:
            raise ValueError("Dimension ID cannot be empty")
        element = {'id': dimensionId}
        if dimensionId.startswith('s'):
            element['namespace'] = "Segment Service"
        if len(kwargs) > 0:
            element['properties'] = {}
            for key, value in kwargs.items():
                element['properties'][key] = value
        self.__data__['request']['reportParameters']['dimensionList'].append(element)

    def addMetric(self, metricId: str,**kwargs):
        """
        Add a metric to the Data Warehouse request.
        Arguments:
            metricId: REQUIRED : The ID of the metric to be added.
                Example: "metrics/visitors", "metrics/pageviews"
        possible kwargs:
            additionalProperties, ex: {"isParticipation": True}
        """
        if not metricId:
            raise ValueError("Metric ID cannot be empty")
        element = {'id': metricId}
        if len(kwargs) > 0:
            element['properties'] = {}
            for key, value in kwargs.items():
                element['properties'][key] = value
        self.__data__['request']['reportParameters']['metricList'].append(element)
    
    def addSegment(self, segmentId: str,**kwargs):
        """
        Add a segment to the Data Warehouse request.
        Arguments:
            segmentId: REQUIRED : The ID of the segment to be added.
                Example: "s1234567890abcdef"
        possible kwargs:
            additionalProperties
        """
        if not segmentId:
            raise ValueError("Segment ID cannot be empty")
        element = {'id': segmentId}
        if len(kwargs) > 0:
            element['properties'] = {}
            for key, value in kwargs.items():
                element['properties'][key] = value
        self.__data__['request']['reportParameters']['segmentList'].append(element)

    def addGranularity(self, granularity: str=None):
        """
        Set the granularity for the Data Warehouse request.
        Arguments:
            granularity: REQUIRED : Granularity of the report, possible values: "hourly", "daily", "weekly", "monthly", "yearly".
        """
        if not granularity:
            raise ValueError("Granularity cannot be empty")
        self.__data__['request']['reportParameters']['dateGranularity'] = granularity
    
    def setMaxNumberOfRows(self, maxRows: int):
        """
        Set the maximum number of rows for the Data Warehouse request.
        Arguments:
            maxRows: REQUIRED : Maximum number of rows to be returned in the report.
        """
        if maxRows <= 0:
            raise ValueError("Maximum number of rows must be greater than 0")
        self.__data__['request']['reportParameters']['numberOfRowsInTable'] = maxRows

    def setOutputFile(self, 
                      compression: str = None,
                      fileFormat: str = None,
                      sendEmptyFile: bool = True,
                      reportComments: str = None,
                      manifestFile: bool = True
                      ):
                      
        """
        Set the output format for the Data Warehouse request.
        Arguments:
            compression: OPTIONAL : Compression type for the output file, possible values: "gzip", "zip".
            fileFormat: OPTIONAL : Format of the output file, possible values: "csv", "tsv", "json".
            sendEmptyFile: OPTIONAL : Whether to send an empty file if no data is available (default True).
            reportComments: OPTIONAL : Comments to be included in the report.
            manifestFile: OPTIONAL : Whether to send a manifest file (default True).
        """
        self.__data__['request']['reportParameters']['outputFile'] = {}
        if compression:
            self.__data__['request']['reportParameters']['outputFile']['compressionFormat'] = compression
        if fileFormat:
            self.__data__['request']['reportParameters']['outputFile']['fileFormat'] = fileFormat
        self.__data__['request']['reportParameters']['outputFile']['sendEmptyFileForNoDataReport'] = sendEmptyFile
        if reportComments:
            self.__data__['request']['reportParameters']['outputFile']['beginningOfReportComments'] = reportComments
        self.__data__['request']['reportParameters']['outputFile']['sendManifestFile'] = manifestFile


    def setSchedule(self, 
                    frequency:str=None,
                    every:int=None,
                    dayOfMonth:int=None,
                    dayOfWeek:str=None,
                    month:str=None,
                    weekOfMonth:str=None,
                    cancelMethod:str=None,
                    end_occurrences:int=None,
                    scheduleAt:str=None,
                    cancelDate:str=None):
        """
        Set the schedule for the Data Warehouse.
        Arguments:
            frequency: OPTIONAL : Frequency of the schedule, possible values: "hourly", "daily", "weekly", "monthly", "yearly".
            every: OPTIONAL : Interval for the frequency, e.g., every 2 days.
            dayOfMonth: OPTIONAL : Day of the month for the schedule (1-31).
            dayOfWeek: OPTIONAL : Day of the week for the schedule (0-6, where 0 is Sunday).
            month: OPTIONAL : Month for the schedule (1-12).
            weekOfMonth: OPTIONAL : Week of the month for the schedule (1-5).
            cancelMethod: OPTIONAL : Method to cancel the schedule, possible values "afterOccurrences", "end_of_period".
            occurrences: OPTIONAL : Number of occurrences for the schedule before it ends.
            scheduleAt : OPTIONAL : Timestamp of when the request is scheduled.
            cancelDate : OPTIONAL : Date when the schedule should be cancelled.
        """
        schedule = {"periodSettings":{},"cancelSettings":{}}
        if frequency is not None:
            schedule['periodSettings']['frequency'] = frequency
        if every is not None:
            schedule['periodSettings']['every'] = every
        if dayOfMonth is not None:
            schedule['periodSettings']['dayOfMonth'] = dayOfMonth
        if dayOfWeek is not None:
            schedule['periodSettings']['dayOfWeek'] = dayOfWeek
        if month is not None:
            schedule['periodSettings']['month'] = month
        if weekOfMonth is not None:
            schedule['periodSettings']['weekOfMonth'] = weekOfMonth
        if scheduleAt is not None:
            schedule['periodSettings']['scheduleAt'] = scheduleAt
        if cancelMethod:
            schedule['cancelSettings']['cancelMethod'] = cancelMethod
        if end_occurrences is not None:
            schedule['cancelSettings']['endAfterNumOccurrences']  = end_occurrences
        if cancelDate is not None:
            schedule['cancelSettings']['cancelDate'] = cancelDate
        self.__data__['schedule'] = schedule
    
    def setDelivery(self,
                    exportLocationUUID: str = None,
                    emailNotificationTo: str = False,
                    emailNotificationFrom: str = None,
                    emailNotificationSubject: str = None,
                    emailNotificationNote: str = None,
                    legacyEmail: bool = True,
                    legacyFTP_username: str = None,
                    legacyFTP_host: str = None,
                    legacyFTP_port: int = None,
                    legacyFTP_directory: str = None,
                    legacyAzure_account:str=None,
                    legacyAzure_container:str=None,
                    legacyAzure_prefix:str=None,
                    leggacyS3_bucket:str=None,
                    legacyS3_accessKey:str=None,
                    legacyS3_awsPath:str=None,
                    ):
        """
        Set the delivery method for the Data Warehouse request.
        Arguments:
            exportLocationUUID: OPTIONAL : UUID of the export location.
            emailNotificationTo: OPTIONAL : Email address to send notifications to.
            emailNotificationFrom: OPTIONAL : Email address to send notifications from.
            emailNotificationSubject: OPTIONAL : Subject of the email notification.
            emailNotificationNote: OPTIONAL : Note to include in the email notification.
            legacyEmail: OPTIONAL : Whether to use legacy email delivery (default True).
            legacyFTP_username: OPTIONAL : Username for legacy FTP delivery.
            legacyFTP_host: OPTIONAL : Host for legacy FTP delivery.
            legacyFTP_port: OPTIONAL : Port for legacy FTP delivery.
            legacyFTP_directory: OPTIONAL : Directory for legacy FTP delivery.
            legacyAzure_account: OPTIONAL : Account for legacy Azure delivery.
            legacyAzure_container: OPTIONAL : Container for legacy Azure delivery.
            legacyAzure_prefix: OPTIONAL : Prefix for legacy Azure delivery.
            leggacyS3_bucket: OPTIONAL : Bucket for legacy S3 delivery.
            legacyS3_accessKey: OPTIONAL : Access key for legacy S3 delivery.
            legacyS3_awsPath: OPTIONAL : AWS path for legacy S3 delivery.
        """
        delivery = {}
        if exportLocationUUID:
            delivery['exportLocationUUID'] = exportLocationUUID
        if emailNotificationTo:
            if 'email' not in delivery.keys():
                delivery['email'] = {}
            delivery['email']['notificationEmailTo'] = emailNotificationTo
            if emailNotificationFrom:
                delivery['email']['notificationEmailFrom'] = emailNotificationFrom
            if emailNotificationSubject:
                delivery['email']['notificationEmailSubject'] = emailNotificationSubject
            if emailNotificationNote:
                delivery['email']['notificationEmailNotes'] = emailNotificationNote
        if legacyEmail:
            delivery['legacyEmail'] = True
        if legacyFTP_username:
            if 'legacyFTP' not in delivery.keys():
                delivery['legacyFTP'] = {}
            delivery['legacyFTP']['username'] = legacyFTP_username
            if legacyFTP_host:
                delivery['legacyFTP']['host'] = legacyFTP_host
            if legacyFTP_port:
                delivery['legacyFTP']['port'] = legacyFTP_port
            if legacyFTP_directory:
                delivery['legacyFTP']['directory'] = legacyFTP_directory
        if legacyAzure_account:
            if 'legacyAzure' not in delivery.keys():
                delivery['legacyAzure'] = {}
            delivery['legacyAzure']['account'] = legacyAzure_account
            if legacyAzure_container:
                delivery['legacyAzure']['container'] = legacyAzure_container
            if legacyAzure_prefix:
                delivery['legacyAzure']['prefix'] = legacyAzure_prefix
        if leggacyS3_bucket:
            if 'legacyS3' not in delivery.keys():
                delivery['legacyS3'] = {}
            delivery['legacyS3']['bucket'] = leggacyS3_bucket
            if legacyS3_accessKey:
                delivery['legacyS3']['accessKey'] = legacyS3_accessKey
            if legacyS3_awsPath:
                delivery['legacyS3']['awsPath'] = legacyS3_awsPath
        self.__data__['delivery'] = delivery

    