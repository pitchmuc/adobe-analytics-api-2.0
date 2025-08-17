# Data Warehouse Creator

The Data Warehouse requests are a huge part of the Adobe Analytics eco-system. However the creation of these reports can be difficult to realize.\
In order to help supporting the data warehouse request, I have created a builder that is called `dwhCreator`.\
This is based on the different documentation and requests extracted over time as the official API documentation is not really complete.\

In case the official API documentation get better over time, you can find it here: <https://developer.adobe.com/analytics-apis/docs/2.0/guides/endpoints/data-warehouse/>


## Instantiating the Data Warehouse Creator

The `DwhCreator` class is contained in the `dwhCreator` module. It is independent from any other module.

```py
import aanalytics2 
from aanalytics2 import dwhCreator

myrequest = dwhCreator.DwhCreator()

```

The instatiation can take one argument: 
* data : OPTIONAL : It can be either a dictionary that represents an existing template or a JSON file to load as template.


## Data Warehouse Creator Methods

#### setName
Set the name for the Data Warehouse.\
Arguments:
* name: REQUIRED : Name to be used for the Data Warehouse.

#### setRSID
Set the report suite ID for the Data Warehouse.\
Arguments:
* rsid: REQUIRED : Report suite ID to be used for the Data Warehouse.

#### setReportRange
Set the report range for the Data Warehouse.\
Arguments:
* preset: OPTIONAL : Preset for the report range, possible values: "Yesterday", "Today", "last_7_days", "last_30_days", "last_90_days", "last_365_days".
* startDateTime: REQUIRED : Start date and time in ISO format (YYYY-MM-DDTHH:MM:SSZ).
* endDateTime: REQUIRED : End date and time in ISO format (YYYY-MM-DDTHH:MM:SSZ).

#### addDimension
Add a dimension to the Data Warehouse request.\
Arguments:
* dimensionId: REQUIRED : The ID of the dimension to be added.\
    Example: "variables/geocity", "variables/prop1", "s0_000000000000000000000000"\
possible kwargs:
* additionalProperties

#### addMetric
Add a metric to the Data Warehouse request.\
Arguments:
* metricId: REQUIRED : The ID of the metric to be added.\
    Example: "metrics/visitors", "metrics/pageviews"\
possible kwargs:
* additionalProperties, ex: {"isParticipation": True}

#### addSegment
Add a segment to the Data Warehouse request.\
Arguments:
* segmentId: REQUIRED : The ID of the segment to be added.\
    Example: "s1234567890abcdef"\
possible kwargs:
* additionalProperties

#### addGranularity
Set the granularity for the Data Warehouse request.\
Arguments:
* granularity: REQUIRED : Granularity of the report, possible values: "hourly", "daily", "weekly", "monthly", "yearly".

#### setMaxNumberOfRows
Set the maximum number of rows for the Data Warehouse request.\
Arguments:
* maxRows: REQUIRED : Maximum number of rows to be returned in the report.

#### setOutputFile
Set the output format for the Data Warehouse request.\
Arguments:
* compression: OPTIONAL : Compression type for the output file, possible values: "gzip", "zip".
* fileFormat: OPTIONAL : Format of the output file, possible values: "csv", "tsv", "json".
* sendEmptyFile: OPTIONAL : Whether to send an empty file if no data is available (default True).
* reportComments: OPTIONAL : Comments to be included in the report.
* manifestFile: OPTIONAL : Whether to send a manifest file (default True).

#### setSchedule
Set the schedule for the Data Warehouse.\
Arguments:
* frequency: OPTIONAL : Frequency of the schedule, possible values: "hourly", "daily", "weekly", "monthly", "yearly".
* every: OPTIONAL : Interval for the frequency, e.g., every 2 days.
* dayOfMonth: OPTIONAL : Day of the month for the schedule (1-31).
* dayOfWeek: OPTIONAL : Day of the week for the schedule (0-6, where 0 is Sunday).
* month: OPTIONAL : Month for the schedule (1-12).
* weekOfMonth: OPTIONAL : Week of the month for the schedule (1-5).
* cancelMethod: OPTIONAL : Method to cancel the schedule, possible values "afterOccurrences", "end_of_period".
* occurrences: OPTIONAL : Number of occurrences for the schedule before it ends.
* scheduleAt : OPTIONAL : Timestamp of when the request is scheduled.
* cancelDate : OPTIONAL : Date when the schedule should be cancelled.

#### setDelivery
Set the delivery method for the Data Warehouse request.\
Arguments:
* exportLocationUUID: OPTIONAL : UUID of the export location.
* emailNotificationTo: OPTIONAL : Email address to send notifications to.
* emailNotificationFrom: OPTIONAL : Email address to send notifications from.
* emailNotificationSubject: OPTIONAL : Subject of the email notification.
* emailNotificationNote: OPTIONAL : Note to include in the email notification.
* legacyEmail: OPTIONAL : Whether to use legacy email delivery (default True).
* legacyFTP_username: OPTIONAL : Username for legacy FTP delivery.
* legacyFTP_host: OPTIONAL : Host for legacy FTP delivery.
* legacyFTP_port: OPTIONAL : Port for legacy FTP delivery.
* legacyFTP_directory: OPTIONAL : Directory for legacy FTP delivery.
* legacyAzure_account: OPTIONAL : Account for legacy Azure delivery.
* legacyAzure_container: OPTIONAL : Container for legacy Azure delivery.
* legacyAzure_prefix: OPTIONAL : Prefix for legacy Azure delivery.
* leggacyS3_bucket: OPTIONAL : Bucket for legacy S3 delivery.
* legacyS3_accessKey: OPTIONAL : Access key for legacy S3 delivery.
* legacyS3_awsPath: OPTIONAL : AWS path for legacy S3 delivery.

#### to_dict
Convert the Data Warehouse data to a dictionary.\
Returns:
* dict: The Data Warehouse data as a dictionary.