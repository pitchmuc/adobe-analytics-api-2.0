# Data Repair API

The Data Repair API provides you with a way to delete or edit your existing Adobe Analytics data. The API offers you the ability to delete columns of data. Filters provide options for you to target specific values within a data column to make precise adjustments to your data. If you use Adobe Experience Platform, repairs made to your Adobe Analytics data are also reflected in any data you send to the Adobe Experience Platform Data Lake through the Analytics Data Connector.

The data repair API requires an additional license from the normal Adobe Analytics licence.

Complete API documentation: <https://developer.adobe.com/analytics-apis/docs/2.0/guides/endpoints/data-repair/>

## datarepair module

The data repair jobs are specific to an additional SKU, therefore it is contain in an additional module, named `datarepair`.\
You can import the module from the `aanalytics2` library, such as: 

```py
import aanalytics2
from aanalytics2 import datarepair
```

The datarepair module contains 2 main classes: 
* `DataRepair` : Connect to the API and provide access to API methods
* `DataRepairJobCreator` : A helper to build data repair job request.


### DataRepair Class

The `DataRepair` class requires 1 argument, and can take additional parameters.\
Arguments: 
* company_id : REQUIRED : the company id to be used for the request.
* config_object : OPTIONAL : the configuration object to be used for the request. (by default take the configuration loaded)
* header : OPTIONAL : the header to be used for the request. (a default is provided)
* retry : OPTIONAL : If you wish to retry failed GET requests (by default 0)

Once the `DataRepair` class has been instantiated, it provides access to all the methods available in the API.\
It also contains some attributes that you can use: 
* `companyId` : The company ID used for instantiated the class
* `endpoint` : The default endpoint used for data repair API requests
* `header` : The header uses for the requests
* `VARIABLES` : A dictionaries showing all possible dimensions that can be used and their possible actions

### DataRepair Methods

#### getEstimate
Calculates the number of Server Calls for the given Report Suite and date range provided.\
It also returns a validationToken, which is required to use the Job endpoint.\
Arguments:
* dateStart: REQUIRED : The start date for the estimate in ISO format (YYYY-MM-DD).
* dateEnd: REQUIRED : The end date for the estimate in ISO format (YYYY-MM-DD).
* rsid: OPTIONAL : The report suite ID to be used for the estimate.\
Returns:
* dict: The estimate data as a dictionary.


#### createJob
Create a job for data repair.\
Arguments:
* rsid: REQUIRED : The report suite ID to be used for the job.
* data: REQUIRED : DataRepairJobCreator instance or dictionary containing the job data or JSON file path.\
Returns:
* dict: The response from the API as a dictionary.


#### getJobs
Get all jobs for the given report suite ID.\
Arguments:
* rsid: REQUIRED : The report suite ID to be used for fetching jobs.\
Returns:
* list: the list of jobs.

#### getJob
Get a specific job by its ID for the given report suite ID.\
Arguments:
* rsid: REQUIRED : The report suite ID to be used for fetching the job.
* jobId: REQUIRED : The job ID to be fetched.\
Returns:
* dict: The job data as a dictionary.

#### getUsage
Get the usage, possibly for the given report suite ID.\
If no start and end dates are provided, it will return the usage for last 30 days.\
If only one of the dates is provided, it will take 30 days from the provided date\
Arguments:
* dateStart: REQUIRED : The start date for the usage in ISO format (YYYY-MM-DD).
* dateEnd: REQUIRED : The end date for the usage in ISO format (YYYY-MM-DD).
* rsid: OPTIONAL : If you want to see the usage for a single report suite ID.
Returns:
* dict: The usage data as a dictionary.


### DataRepairJobCreator

In order to simplify the creation of job request for the data repair API, a builder capability is provided in the module.\
You don't have to use it, it is here in case you prefer to use its functionality, but the `createJob` method will also take a dictionary or a JSON file path as data argument.

The `DataRepairJobCreator` can take one argument for the instantiation, it would be either a dictionary that serves as a template or JSON file that can be used as a Template.
Arguments:
* data: OPTIONAL : A dictionary or a JSON string containing the job data.

It also provides one attribute once instantiated: 
* `VARIABLES` : A dictionaries showing all possible dimensions that can be used and their possible actions


### DataRepairJobCreator methods

The creator only contains 2 methods: 

#### addVariable
Add a variable to the job.\
Arguments:
* variableId: REQUIRED : The variable ID to be added.
* action: REQUIRED : The action to be performed. Choose from "set", "delete", "deleteQueryString", "deleteQueryStringParameters"
* value: REQUIRED if action is "set" : The value to be set for the variable.
* filterCondition: OPTIONAL : The filter condition to be applied. 
    Choose from "inList", "isEmpty", "contains", "doesNotContain", "startsWith",doesNotStartWith", "endsWith", "doesNotEndWith", "isURL", "isNotURL","isNumeric","isNotNumeric".
* matchValues: OPTIONAL : The list of values to be matched for the filter condition.
* filterVariable: OPTIONAL : The variable to be used for the filtering of the original variable.

#### to_dict
Convert the job data to a dictionary.
Returns:
* dict: The job data as a dictionary.