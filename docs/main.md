# aanalytics2

The aanalytics2 python library stands for Adobe Analytics API 2.0 support.
It is set to wrap the different endpoints from the documentation.
You can find the swagger documentation [here](https://adobedocs.github.io/analytics-2.0-apis/).

The different section will quickly explain the methods available in the different part of this API.

## Core components

The methods available directly from the module are the following:

### createConfigFile

This methods allows you to create JSON file that will host the different information required for your connection to Adobe IO and to retrieve the token.
It usually is like this.

```python
import aanalytics2 as api2
api2.createConfigFile()
```

As you can see, it takes no argument and the output of the file will look like this :

```javaScript
{
    'org_id': '<orgID>',
    'api_key': "<APIkey>",
    'tech_id': "<something>@techacct.adobe.com",
    'secret': "<YourSecret>",
    'pathToKey': '<path/to/your/privatekey.key>',
}
```

You update the information from the Adobe IO account that you have setup.

### importConfigFile

As you have created your JSON config file, you will need to import it before realizing any request to the Analytics API.
The method takes the file name as an argument, or the path where your file exist.

```python
import aanalytics2 as api2
api2.importConfigFile('config.json')
```

or

```python
import aanalytics2 as api2
myfilePath = './myCredential/config.json'
api2.importConfigFile(myfilePath)
```

### retrieveToken (OPTIONAL)

This method is not mandatory because each of your requests will be taken care by a wrapping function that will generate a token if you don't have one.
However, at some point, you may want to generate a token for a reason X or Y, so this function is available for that use-case.
This function takes no argument as long as you have imported the config file.
It returns the token.

```python
import aanalytics2 as api2
api2.importConfigFile('config.json')

token = api2.retrieveToken()
```

This method also caches the time limit of the token usage in the config_object in config module.
It can be accessed like this:

```python
aanalytics2.config.config_object
## your token
aanalytics2.config.config_object['token']
```

You can review when this token expire through the time module:

```python
import time
time.ctime(aanalytics2.config.config_object['date_limit'])

## returns something like : 'Mon May 17 18:08:42 2023'
```

## Login class

The `Login` class is the capability to get the different Login Company ID to create your conneciton later on.\
The class can be instanciated **after** you have imported the configuration JSON file.

```python
import aanalytics2 as api2
api2.importConfigFile('myconfig.json')
## Here instanciating the Login class
login = api2.Login()

## Here retrieving the cids
cids = login.getCompanyId()
```

From this implementation, you can then retrieve the list of loginCompanyId from your __cids__ variable or the **__COMPANY_IDS__** attributes.

```python
## login company Id is kept in that attribute after the usage of the getCompanyId()
login.COMPANY_IDS

## returns (example):
[
 {'globalCompanyId': 'comp1',
  'companyName': 'Company1',
  'apiRateLimitPolicy': 'aa_api_tier10_tp',
  'dpc': 'lon'},
 {'globalCompanyId': 'comp2',
  'companyName': 'Company2',
  'apiRateLimitPolicy': 'aa_api_tier10_tp',
  'dpc': 'lon'}
]

```

After selecting your `globalCompanyId`, you can generate your connection to the Login company by calling the **__createAnalyticsConnection__**.

```python
mycompany1 = loggin.createAnalyticsConnection('comp1')
```

We will see later that you can also directly use the `Analytics` class.

**Note**: you can enable logging capability for the class by passing an object in the `loggingObject` parameter. More information [here](./logging.md)

### Retry Parameter

The latest version of the aanalytics2 module also provides a **retry** parameter.\
This parameter will be used to resend the query in case an error occurs in the response.\
Several reason an error can occur:

* connectivity issue
* server issue from Adobe Analytics API
* inconsistent behavior from Adobe Analytics API

The retry parameter is going to be attached to every GET method available in your `Analytics` class.\
**Note**
The `getReport` is in fact a POST method. \
From my point of view, you want to get data so I called it that way. \
From Adobe API you are generating a report, therefore it requires a POST method with data attached (your report config).\
Consequently, the `getReport` method doesn't support the **retry** parameter at the moment.\
This is also a design decision because it is based on data you are providing. If the data is corrupted or non-conformed, I do not realize a check but I expect Adobe Analytics API to return an error.\
Following this error, I do not want to __retry__ sending that data again.

You can instantiate the `Analytics` class and the `Login` class with the **retry** parameter.\
The parameter takes the number of time you would like to retry in case of error.\
If you create the `Analytics` class from the `Login` instance, the retry parameter value is passed (except if you override it).

## Analytics class

Adobe Analytics API 2.0 requires you to send the companyID you have selected in the header of each request you do in that company.
There used to be a method in this API to update the header accordingly.
I changed this logic to create a class that encapsulate this choice directly.
Therefore it is possible to use 2 instances of the class at the same time and therefore 2 companyID can be used almost at the same time.

As seen in the previous example, you instantiate the class by passing the companyID.

```python
import aanalytics2 as api2
#...
mycompany = api2.Analytics(cid)

## or with retry parameter
mycompany = api2.Analytics(cid,retry=2)
```

You instance will have all of the Analytics endpoint wrapped.
At any point in time, you can use the docstring that have been set in this module by using the help function.

```python
help(mycompany.getSegments)
## returns:
##getSegments(name: str = None, tagNames: str = None, inclType: str = 'all', rsids_list: list = None, sidFilter: list = None, extended_info: bool = False, format: str = 'df', save: bool = False, verbose: bool = False, **kwargs) -> object method of aanalytics2.Analytics instance
#    Retrieve the list of segments. Returns a data frame.
#    Arguments:
#        name : OPTIONAL : Filter to only include segments that contains the name (str)
#        tagNames : OPTIONAL : Filter list to only include segments that contains one of the tags (string delimited with comma, can be list as well)
#...
```

One of the specific functionality for this class, is that you can update the token with a new one by using the _refreshToken_ method.
It takes one argument (the token string) and requires you to run the retrieveToken method beforehand.

```python
import aanalytics2 as api2
#...
token = api2.retrieveToken()
mycompany.refreshToken(token)

```

With all of my API wrappers, I ususall separate the methody by the GET (fetching information), the CREATE methods (posting information), the DELETE methods, the UPDATE mehthods.
This API is no exception.

**Note**: you can enable logging capability for the class by passing an object in the `loggingObject` parameter. More information [here](./logging.md)

## The Project class

There is a way to retrieve projects and especially project definition.\
The information returns is a dictionary (JSON) that may not be easy to decipher for analysts.\
Therefore, I have created a class that can ease the understanding of the data in the project dictionary.\
The instance of that class will provide some information directly from class attributes.

The different attributes are:

* "id" of the project
* "name" of the project
* "description" of the project
* "rsid" attached to the project (can be a Virtual Report Suite ID)
* "ownerName" of the project owner
* "ownerId" of the project owner
* "ownerEmail" of the project owner
* "template" is a boolean if the project is a template or not
* "curation" is a boolean if the project has been curated or not
* "version" of the project
* "nbPanels" gives the number of Panels there is in your projects
* "nbSubPanels" gives the number of subPanels that exist in your project
* "nbElementsUsed" gives you how many different dimensions, metrics, segments and calcuated are being used in your projects. Elements have been deduplicated.
* "elementsUsed" is a dictionary to gives you the different elements used such as:
  * rsids
  * dimensions
  * metrics
  * segments
  * calculatedMetrics

A method "to_dict()" also exists on this instance so you can flatten these information and later use them in a pandas dataframe if you wish.

### The get methods

There are several get methods.

* getReportSuites : Get the list of reportSuites.Returns a data frame.
  Arguments:
  * txt : OPTIONAL : returns the reportSuites that matches a speific text field
  * rsid_list : OPTIONAL : returns the reportSuites that matches the list of rsids set
  * limit : OPTIONAL : How many reportSuite retrieves per serverCall
  * save : OPTIONAL : if set to True, it will save the list in a file. (Default False)

* getVirtualReportSuites : Retrieve all the Virtual reportSuite for a login company.
  Arguments:
  * extended_info : OPTIONAL : boolean to retrieve the maximum of information.
  * limit : OPTIONAL : How many reportSuite retrieves per serverCall
  * filterIds : OPTIONAL : comma delimited list of virtual reportSuite ID  to be retrieved.
  * idContains : OPTIONAL : element that should be contained in the Virtual ReportSuite Id
  * segmentIds : OPTIONAL : comma delimited list of segmentId contained in the VRSID
  * save : OPTIONAL : if set to True, it will save the list in a file. (Default False)

* getVirtualReportSuite : Get a specific reportSuite based on the id.
  Arguments:
  * vrsid : REQUIRED : The virtual reportSuite to be retrieved
  * extended_info : OPTIONAL : boolean to add more information
  * format : OPTIONAL : format of the output. 2 values "df" for dataframe and "raw" for raw json.

* getVirtualReportSuiteComponents: Get the curated components for a VRS (needs Curation enabled in this VRS) and returns them as a DataFrame
  Arguments:
  * vrsid: Virtual Report Suite ID
  * nan_value: how to treat missing values. Default: ""

* getSegments: Retrieve the list of segments. Returns a data frame.
    Arguments:
  * name : OPTIONAL : Filter to only include segments that contains the name (str)
  * tagNames : OPTIONAL : Filter list to only include segments that contains one of the tags (string delimited with comma, can be list as well)
  inclType : OPTIONAL : type of segments to be retrieved.(str) Possible values:
    * all : Default value (all segments possibles)
    * shared : shared segments
    * template : template segments
    * deleted : deleted segments
    * internal : internal segments
    * curatedItem : curated segments
  * rsid_list : OPTIONAL : Filter list to only include segments tied to specified RSID list (list)
  * sidFilter : OPTIONAL : Filter list to only include segments in the specified list (list)
  * extended_info : OPTIONAL : additional segment metadata fields to include on response (bool : default False)
  if set to true, returns reportSuiteName, ownerFullName, modified, tags, compatibility, definition
  * format : OPTIONAL : defined the format returned by the query. (Default df)
    possibe values :
    * "df" : default value that return a dataframe
    * "raw": return a list of value. More or less what is return from server.
  * save : OPTIONAL : If set to True, it will save the info in a csv file (bool : default False)
  * verbose : OPTIONAL : If set to True, print some information
  Possible kwargs:
  * limit : number of segments retrieved by request. default 500: Limited to 1000 by the AnalyticsAPI.

* getDimensions: Retrieve the list of dimensions from a specific reportSuite.Shrink columns to simplify output. Returns the data frame of available dimensions.
  Arguments:
  * rsid : REQUIRED : Report Suite ID from which you want the dimensions
  * tags : OPTIONAL : If you would like to have additional information, such as tags. (bool : default False)
  * description : OPTIONAL : Trying to add the description column. It may break the method.
  * save : OPTIONAL : If set to True, it will save the info in a csv file (bool : default False)
  Possible kwargs:
  * full : Boolean : Doesn't shrink the number of columns if set to true
  example : getDimensions(rsid,full=True)

* getMetrics: Retrieve the list of metrics from a specific reportSuite. Shrink columns to simplify output. Returns the data frame of available metrics.
  Arguments:
  * rsid : REQUIRED : Report Suite ID from which you want the dimensions
  * tags : OPTIONAL : If you would like to have additional information, such as tags. (bool : default False)
  * dataGroup : OPTIONAL : Adding dataGroups to the column exported. Default False.
                May break the report.
  * save : OPTIONAL : If set to True, it will save the info in a csv file (bool : default False)
  Possible kwargs:
  * full : Boolean : Doesn't shrink the number of columns if set to true
  example : getMetrics(rsid,full=True)

* getUsers: Retrieve the list of users for a login company.Returns a data frame.
  Arguments:
  * save : OPTIONAL : Save the data in a file (bool : default False).
  Possible kwargs:
  * limit : OPTIONAL : Nummber of results per requests. Default 100.

* getDateRanges: Get the list of date ranges available for the user.
  Arguments:
  * extended_info : OPTIONAL : additional segment metadata fields to include on response
        additional infos: reportSuiteName, ownerFullName, modified, tags, compatibility, definition
  * save : OPTIONAL : If set to True, it will save the info in a csv file (Default False)
  Possible kwargs:
  * limit : number of segments retrieved by request. default 500: Limited to 1000 by the Analytics API.
  * full : Boolean : Doesn't shrink the number of columns if set to true

* getCalculatedMetrics : Return the calculated metrics of your login company (dataframe by default).
  Arguments:
  * name : OPTIONAL : Filter to only include calculated metrics that contains the name (str)
  * tagNames : OPTIONAL : Filter list to only include calculated metrics that contains one of the tags (string delimited with comma, can be list as well)
  * inclType : OPTIONAL : type of calculated Metrics to be retrieved. (str) Possible values:
    * all : Default value (all calculated metrics possibles)
    * shared : shared calculated metrics
    * template : template calculated metrics
  * rsid_list : OPTIONAL : Filter list to only include segments tied to specified RSID list (list)
  * extended_info : OPTIONAL : additional segment metadata fields to include on response (list)
      additional infos: reportSuiteName,definition, ownerFullName, modified, tags, compatibility
  * save : OPTIONAL : If set to True, it will save the info in a csv file (Default False)
  * format : OPTIONAL : format of the output. 2 values "df" for dataframe and "raw" for raw json.
Possible kwargs:
  limit : number of segments retrieved by request. default 500: Limited to 1000 by the AnalyticsAPI.(int)

* getSegment : retrieve a specific segment by its ID.
  Arguments:
  * segment_id : REQUIRED : the segment id to retrieve.
  * full : OPTIONAL : Add all possible information. bool, default False

* getCalculatedMetric : Return a dictionary on the calculated metrics requested.
  Arguments:
  * calculatedMetricId : REQUIRED : The calculated metric ID to be retrieved.
  * full : OPTIONAL : additional segment metadata fields to include on response (list)
      additional infos: reportSuiteName,definition, ownerFullName, modified, tags, compatibility

* getTags : Retrieve the list of Tags used on the company Login.
  Arguments:
  * limit : OPTIONAL : Amount of tag to be returned by request. Default 100

* getScheduledJobs: Retrieve the list of scheduled Jobs for your login company.
  Arguments:
  * includeType : OPTIONAL : By default gets all non-expired or deleted projects. (default "all")
      You can specify e.g. "all,shared,expired,deleted" to get more. 
      Active schedules always get exported,so you need to use the `rsLocalExpirationTime` parameter in the `schedule` column to e.g. see which schedules are expired
  * full : OPTIONAL : By default True. It returns the following additional information "ownerFullName,groups,tags,sharesFullName,modified,favorite,approved,scheduledItemName,scheduledUsersFullNames,deletedReason"
  * limit : OPTIONAL : Number of element retrieved by request (default max 1000)
  * format : OPTIONAL : Define the format you want to output the result. Default "df" for dataframe, other option "raw"
  * verbose: OPTIONAL : set to True for debug output

* getComponentTagName : Given a comma separated list of tag names, return component ids associated with them
  Arguments:
  * tagNames : REQUIRED : Comma separated list of tag names.
  * componentType : REQUIRED : The component type to operate on.\
      Available values : segment, dashboard, bookmark, calculatedMetric, project, dateRange, metric, dimension, virtualReportSuite, scheduledJob, alert, classificationSet

* getComponentTags : Given a componentId, return all tags associated with that component.
  Arguments:
  * componentId : REQUIRED : The componentId to operate on. Currently this is just the segmentId.
  * componentType : REQUIRED : The component type to operate on.

* getUsageLogs : Retrieve the usage logs from the users of a login company:
  Arguments:
  * startDate : REQUIRED : Start date, format : 2020-12-01T00:00:00-07.(default 3 month prior today)
  * endDate : REQUIRED : End date, format : 2020-12-15T14:32:33-07. (default today)
      Should be a maximum of a 3 month period between startDate and endDate.
  * eventType : OPTIONAL : The numeric id for the event type you want to filter logs by.
      Please reference the lookup table in the LOGS_EVENT_TYPE
  * event : OPTIONAL : The event description you want to filter logs by.
      No wildcards are permitted, but this filter is case insensitive and supports partial matches.
  * rsid : OPTIONAL : ReportSuite ID to filter on.
  * login : OPTIONAL : The login value of the user you want to filter logs by. This filter functions as an exact match.
  * ip : OPTIONAL : The IP address you want to filter logs by. This filter supports a partial match.
  * limit : OPTIONAL : Number of results per page.
  * max_result : OPTIONAL : Number of maximum amount of results if you want. If you want to cap the process. Ex : max_result=1000
  * format : OPTIONAL : If you wish to have a DataFrame ("df" - default) or list("raw") as output.
  * verbose : OPTIONAL : Set it to True if you want to have console info.
possible kwargs:
  * page : page number (default 0)


* getScheduledJob: Return a scheduled project definition.
  Arguments:
  * scheduleId : REQUIRED : Schedule project ID


* getDeliverySettings: Retrieve the delivery setting from a scheduled project.
  Argument
  * deliverySettingId : REQUIRED : The delivery setting ID of the scheduled project.

Example of getSegments usage:

```python
mysegments = mycompany.getSegments(extended_info=True,save=True)
```

Example of getDimensions usage:

```python
mydims = mycompany.getDimensions('rsid')
```

#### Project Methods

I have implemented a `getProjects`, `getProject`, `updateProject` and `createProject` methods.

From these methods, I have created other supported methods that are explained in the [Project documentation](./projects.md).

### Create

The Adobe Analytics API 2.0 provides some endpoint to create elements in your Analytics setup.
Here is the list of the possible create options.

* createVirtualReportSuite: Create a new virtual report suite based on the information provided.
  Arguments:
  * name : REQUIRED : name of the virtual reportSuite
  * parentRsid : REQUIRED : Parent reportSuite ID for the VRS
  * segmentLists : REQUIRED : list of segment id to be applied on the ReportSuite.
  * dataSchema : REQUIRED : Type of schema used for the VRSID. (default : "Cache")
  * data_dict : OPTIONAL : you can pass directly the dictionary.
  In this case, you dictionary should looks like this:

  ```python
  data_dict = {
    'name' : 'xxxx',
    'parentRsid':'',
    'segmentLists':'',
    'dataSchema':'Cache',
  }
  ```

* createSegment: This method create segment based on the information provided in the dictionary passed as parameter.
  Arguments:
  * segmentJSON : REQUIRED : the dictionary that represents the JSON statement for the segment.
  The segmentJSON is referenced on this [Swagger reference](https://adobedocs.github.io/analytics-2.0-apis/#/segments/segments_createSegment)

* createCalculatedMetrics: This method create a calculated metrics within your Login Company with the provided dictionary.
  Arguments:
  * metricJSON : REQUIRED : Calculated Metrics information to create. Required :  name, definition, rsid
    more information can be found on the [Swagger refrence](https://adobedocs.github.io/analytics-2.0-apis/#/calculatedmetrics/calculatedmetrics_createCalculatedMetric)
  
* createCalculatedMetricValidate: Validate a calculated metrics definition or object passed.
  Arguments:
  * metricJSON : REQUIRED : Calculated Metrics information to create. (Required: name, definition, rsid)
      More information can be found at this address https://adobedocs.github.io/analytics-2.0-apis/#/calculatedmetrics/calculatedmetrics_createCalculatedMetric

* createTags : This method creates a tag and associate it with a component.
  Arguments:
  * data : REQUIRED : The list of the tag to be created with their component relation.
  It looks like the following:

  ```JSON
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
  ```

* createScheduledJob : 
  Creates a schedule job based on the information provided as arguments.
  Expiration will be in one year by default.
  Arguments:
    * projectId : REQUIRED : The workspace project ID to send.
    * type : REQUIRED : how to send the project, default "pdf"
    * schedule : REQUIRED : object to specify the schedule used.
        example: {  
                  "hour": 10,
                  "minute": 45,
                  "second": 25,
                  "interval": 1,
                  "type": "daily"
                }
                {
                  'type': 'weekly',
                  'second': 53,
                  'minute': 0,
                  'hour': 8,
                  'daysOfWeek': [2],
                  'interval': 1
                }
                {
                  'type': 'monthly',
                  'second': 53,
                  'minute': 30,
                  'hour': 16,
                  'dayOfMonth': 21,
                  'interval': 1
                }
    * loginIds : REQUIRED : A list of login ID of the users that are recipient of the report. It can be retrieved by the getUsers method.
    * emails : OPTIONAL : If users are not registered in AA, you can specify a list of email addresses.
    * groupIds : OPTIONAL : Group Id to send the report to.

* createDeliverySetting : Create a delivery setting for a specific scheduled project. Automatically used when using `createScheduleJob`.
  Arguments:
  * loginIds : REQUIRED : List of login ID to send the scheduled project to.   Can be retrieved by the getUsers method.
  * emails : OPTIONAL : In case the recipient are not in the analytics interface. 
  * groupIds : OPTIONAL : List of group ID to send the scheduled project to.

### Update methods

* updateVirtualReportSuite : Updates a Virtual Report Suite based on a JSON-like dictionary (same structure as createVirtualReportSuite)
  Note that to update components, you need to supply ALL components currently associated with this suite.
  Supplying only the components you want to change will remove all others from the VR Suite!
  Arguments:
  * vrsid : REQUIRED : The id of the virtual report suite to update
  * data_dict : a json-like dictionary of the vrs data to update

* updateSegment : Method that updates a specific segment based on the dictionary passed to it.
  Arguments:
  * segmentID : REQUIRED : Segment ID to be updated
  * segmentJSON : REQUIRED : the dictionary that represents the JSON statement for the segment.

* updateCalculatedMetric: Method that updates a specific Calculated Metrics based on the dictionary passed to it.
  Arguments:
  * calcID : REQUIRED : Calculated Metric ID to be updated
  * calcJSON : REQUIRED : the dictionary that represents the JSON statement for the calculated metric.

* updateDateRange : Method that updates a specific Date Range based on the dictionary passed to it.
  Arguments:
  * dateRangeID : REQUIRED : Date Range ID to be updated
  * dateRangeJSON : REQUIRED : the dictionary that represents the JSON statement for the date Range.

* updateComponentTags : Overwrite the component Tags with the list send.
  Arguments:
  * data : REQUIRED : list of the components to be udpated with their respective list of tag names.

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

* updateScheduledJob : Update a schedule Job based on its id and the definition attached to it.
  Arguments:
  * scheduleId : REQUIRED : the jobs to be updated.
  * scheduleObj : REQUIRED : The object to replace the current definition.

* updateDeliverySetting : Create a delivery setting for a specific scheduled project.
  Automatically created for email setting.
  Arguments:
  * deliveryId : REQUIRED : the delivery setting ID to be updated
  * loginIds : REQUIRED : List of login ID to send the scheduled project to.   Can be retrieved by the getUsers method.
  * emails : OPTIONAL : In case the recipient are not in the analytics interface. 
  * groupIds : OPTIONAL : List of group ID to send the scheduled project to.

* updateProject : Update your project with the new object placed as parameter.
  Arguments:
  * projectId : REQUIRED : the project ID to be updated.
  * projectObj : REQUIRED : the dictionary to replace the previous Workspace.
      requires the following elements: name,description,rsid, definition, owner


### Delete methods

There is a possibility to delete some elements with the Adobe Analytics API 2.0. Please find below the different options that you can delete.

* deleteVirtualReportSuite: delete a Virtual reportSuite based on its ID.
  Arguments:
  * vrsid : REQUIRED : The id of the virtual reportSuite to delete.

* deleteSegment: delete a segment based on the ID.
  Arguments:
  * segmentID : the ID of the segment to be deleted.

* deleteCalculatedMetrics: Delete a calculated metrics based on its ID.
  Arguments:
  * calcID : REQUIRED : Calculated Metrics ID to be deleted

* deleteTags: Delete all tags from the component Type and the component ids specified.
  Arguments:
  * componentIds : REQUIRED : the Comma-separated list of componentIds to operate on.
  * componentType : REQUIRED : The component type to operate on.\
    Available values : segment, dashboard, bookmark, calculatedMetric, project, dateRange, metric, dimension, virtualReportSuite, scheduledJob, alert, classificationSet

* deleteTag : Delete a Tag based on its id.
  Arguments:
  * tagId : REQUIRED : The tag ID to be deleted.

* deleteProject : Delete a Project basede on its id.
  Arguments:
  * projectId : REQUIRED : The project ID to be deleted.

* deleteScheduledJob : Delete a schedule project based on its ID.
  Arguments:
  * scheduleId : REQUIRED : the schedule ID to be deleted.

* deleteDeliverySetting : Delete a delivery setting based on the ID passed.
  Arguments:
  * deliveryId : REQUIRED : The delivery setting ID to be deleted.

### Get report

The get report from Adobe Analytics, I will recommend you to watch the [video](https://youtu.be/j1kI3peSXhY) that explains how you can generate the JSON file for requesting the report through API.
This getReport methods is a bit special because it is mostly what users would have liked to have from this API, so it is a separate part.

First of all, you need to understand that this API is a replicate of Adobe Analytics Workspace interface.
There is no additional feautres or way to bypass the limitation of Analytics Workspace from this API.
It means that the (low traffic) will still appear and also the filters are different requests.
Also, there is a limit of 120 requests per minute, and a limit threshold of 12 requests for 6 seconds.
Therefore, requesting large amount of data is not the use-case for the API 2.0.

When you have generated your request through the UI interface you can directly saved it in a json file.
You can then either directly use it with the aanalytics2 module or rework it in python.

Before going with examples, I will explain the method and its arguments:

* getReport : Retrieve data from a JSON request.Returns an object containing meta info and dataframe.
  Arguments:
  * json_request: REQUIRED : JSON statement that contains your request for Analytics API 2.0.
  The argument can be :
    * a dictionary : It will be used as it is.
    * a string that is a dictionary : It will be transformed to a dictionary / JSON.
    * a path to a JSON file that contains the statement (must end with ".json").
  * n_result : OPTIONAL : Number of result that you would like to retrieve. (default 1000)
    if you want to have all possible data, use "inf".
  * item_id : OPTIONAL : Boolean to define if you want to return the item id for sub requests (default False)
  * save : OPTIONAL : If you would like to save the data within a CSV file. (default False)
  * verbose : OPTIONAL : If you want to have comment display (default False)

As you can see, you can use the getReport with different variable types (string, path or dictionary).

The object that is being returned is hosting the information about your request. In case you need to have the context during your usage of the data.
Example of the object being returned :

```python
{'dimension': 'variables/eVarX',
    'filters': {'globalFilters': ['2019-11-01T00:00:00.000/2019-12-01T00:00:00.000'],
    'metricsFilters': {}},##if any filters have been applied.
    'rsid': 'my.rsid',
    'metrics': ['metrics/visits'],
    'data': #pandas DataFrame.
}
```

As you can see it returns the actual data of your request in the "data" key, as a dataframe.
Therefore, you can use the data by doing the extraction of the data.
Example:

```python
myreport = mycompany.getReport('myReport.json')
mydata = myreport['data']
```

**Note** : It can be that some data are not returned by the API (unknown reason for me). The exception is then handle by setting "missing_value" to these items.\
Because a dictionary is being built before returning the dataframe, it means that all missing value will be set as "missing_value" and only the last key will remain.

**Handling Throttle** : The throttle limit of 12 requests per 6 seconds or 120 requests per minute is handle automatically. It automatically pause the requests for 50 seconds when the limit is reached.

### The create methods

Adobe Analytics API 2.0 currently, limiting number of creation.
You can only create Calculated Metrics and Segments so far.

* createSegment:
  Arguments:
  * segmentJSON : REQUIRED : the dictionary that represents the JSON statement for the segment.

* createCalculatedMetrics:
  Arguments:
  * metricJSON : REQUIRED : the dictionary that represents the JSON statement for the  Calculated Metrics.
    Required in the dictionary :  name, definition, rsid

### The scan methods

The scan methods allow to search for the elements used in a Segment or a Calculated Metric.\
You can `scanSegment` or `scanCalculatedMetric` with either:

* the id of the Segment or the Calculated Metric.
* the dictionary result of the segment or calculated metric retrieved from `getSegment` or `getCalculatedMetric` methods.

The result will be a dictionary with the different information.\
Results for Segment:

```python
{
'dimensions' : {"variables/referringdomain","variables/evar3"},
'metrics' : {"metrics/bouncerate","metrics/visits"},
'rsid' : "rsid",
'scope' : "hits"
}
```

Results for Calculated Metric:

```python
{
'dimensions' : {"variables/referringdomain","variables/evar3"},
'metrics' : {"metrics/bouncerate","metrics/visits"},
'rsid' : "rsid",
}
```

## Decode AA requests

The `decodeAArequests` method allows you to pass requests directly and get a dataframe back with the information held in these requests.\
The `decodeAArequests` method can take either the request directly in a list of strings via the `url` parameter or by passing a file to open, via the `file` parameter.

* decodeAArequests
  Decode the urls requests from the list pass down via either file or list of string.
  Returns a dataframe.
  Arguments:
  * file : OPTIONAL : file referencing the different requests saved (excel or txt)
  * urls : OPTIONAL : list of requests (or a single request) that you want to decode.
  * save : OPTIONAL : parameter to save your decode list into a csv file.
possible kwargs:
  * encoding : the type of encoding to decode the file

## Compare ReportSuite

The `compareReportSuites` method allows you to compare the setup between reportSuites for either dimensions and metrics.\
It also has several parameters that would allow for extensive comparison (with attribution) or just names.

* compareReportSuites
  Compare reportSuite on dimensions (default) or metrics based on the comparison selected.
  Returns a dataframe with multi-index and a column telling which elements are differents
  Arguments:
  * listRsids : REQUIRED : list of report suite ID to compare
  * element : REQUIRED : Elements to compare. 2 possible choices:
    * dimensions (default)
    * metrics
  * comparison : REQUIRED : Type of comparison to do:
    * full (default) : compare name and settings
    * name : compare only names
* save : OPTIONAL : if you want to save in a csv.

## GetReport2

The `getReport2` is a more advanced version of the getReport method that was originally provided.\
Compared to `getReport`, the `getReport2` method offers the possibility to return a `Workspace` class instance.[workspace documentation](./workspace.md)\
It also provides capability to access more information on `summaryData` or do `breakdown`.

First of all, you need to understand that this API is a replication of the Workspace interface.
There is no additional features or way to bypass the limitation of Analytics Workspace by using this API.

Some limitations:

* A limit of 120 requests per minute is set, on top of a limit threshold of 12 requests for 6 seconds.\
  Because of that limit, I didn't parallelize the report requests, as the report as the threshold can be hit quite rapidly.\
  Therefore, requesting large amount of data is not the use-case for the Adobe Analytics API. It would infer a important waiting time.
* There is no automatic breakdown for dimensions. As for the Workspace reporting, you can only request one dimension at a time.
* Adobe Analytics reporting server usually allows 5 reports to be processed at the same time for your organization.\
  The AA API will compete with the others users of your organization, so be careful on its (extensive) usage.

Before going with examples, I will explain the method and its arguments:

* getReport : Retrieve data from a JSON request.
              Returns an dictionary of data or a `Workspace` instance containing the data in the dataframe attribute.
  Arguments:
  * request : REQUIRED : either a dictionary of a JSON file that contains the request information.
  * limit : OPTIONAL : number of results per request (default 1000)
  * n_results : OPTIONAL : total number of results returns. Use "inf" to return everything (default "inf")
  * useCache : OPTIONAL : Use caching for faster requests (Do not do any report caching)
  * useResultsCache : OPTIONAL : Use results caching for faster reporting times (This is a pass through to Oberon which manages the Cache)
  * includePredictiveObjects : OPTIONAL : Controls if platform Predictive Objects should be returned in the response. Only available when using Anomaly Detection or Forecasting- DEBUG ONLY
  * returnsNone : OPTIONAL: Overwritte the request setting to return None values.
  * countRepeatInstance : OPTIONAL: Overwritte the request setting to count repeatInstances values.
  * ignoreZeroes : OPTIONAL : Ignore zeros in the results
  * rsid : OPTIONAL : Overwrite the reportSuite ID used for report. Only works if the same components are presents.
  * resolveColumns: OPTIONAL : automatically resolve columns from ID to name for calculated metrics & segments. Default True. (works on returnClass only)
  * save : OPTIONAL : If you want to save the data (in JSON or CSV, depending the class is used or not)
  * returnClass : OPTIONAL : return the class building dataframe and better comprehension of data. (default yes)

I am recommending to try using the `getReport2` instead of the `getReport` method, with returning the `Workspace` class as often as possible (default method).
This will provide the more intelligible report for you.
