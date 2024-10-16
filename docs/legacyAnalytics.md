# Adobe Analytics 1.4 support

This documentation will explain you how to use the `LegacyAnalytics` class that has been added to the module.\
As there is no feature parity between Adobe Analytics 2.0 and Adobe Analytics 1.4, and there probably will never be, I made the choice to enable partial support to the Adobe Analytics 1.4 endpoints. Mostly focus on admin report.\
Why partial support ?\
Because the Adobe Analytics 1.4 is having massive amount of endpoint and my focus is more leaning towards AEP API than legacy APIs that will be discarded soon.\

Nonetheless, the API should provide you the flexibility to realize the action that you want.\
If you feel that the API doesn't provide support for a specific method, feel free to raise a github issue but it will not be prioritized over 2.0 issue.\
You can always provide a Pull Request (PR), and this will be prioritised.

## LegacyAnalytics class

You can instantiate the `LegacyAnalytics` class with your `companyName` returned from the `getCompanyId` method.\
The authentication method is the same than for the Adobe Analytics 2.0.\
It **doesn't take the globalCompanyId** like the Analytics class.

A workflow would looks like the following.

```python
import aanalytics2 as api2
api2.importConfigFile('config_analytics.json')

login = api2.Login()
login.getCompanyId()
## returns
[{'globalCompanyId': 'someId',
  'companyName': 'My Company Name',
  'apiRateLimitPolicy': 'aa_api_tier10_tp',
  'dpc': 'pnw'}]

myCompany = api2.LegacyAnalytics(company_name='My Company Name')
```

## Methods for LegacyAnalytics instance

Following the swagger documentation on the Adobe Analyics 1.4 [available here](https://adobedocs.github.io/analytics-1.4-apis/).\
The protocole used in always the POST method, the endpoint is always the same and only the methods differ.

According to that, you have access to 2 methods in the `LegacyAnalytics` instance.

### `postData`

The `postData` method will allow you to realize the action referenced in the documentation.\
It takes 4 possible arguments:

* path: in case the path you want to use is not '/'.
* method: You reference the method that you want to use.
* data: A dictionary that pass the information you want to POST.
* params: Parameters that you want to use on your request.

Example:

```python
myCompany.postData(method="Company.GetTrackingServer",data={"rsid": "myrsid"})
```

### `getData`

The getData will use the GET method to retrieve information from the 1.4 API.\
It is not reference in the documentation but I do believe it exists and there are methods supported with this protocole.\
It takes 3 possible arguments.\

* path: in case the path you want to use is not '/'.
* method: You reference the method that you want to use.
* params: Parameters that you want to use on your request.

Example:

```python
myCompany.getData(method="Company.GetReportSuites")
```

## Attributes & tips for LegacyAnalytics

### Attributes
The instance possess some attributes for your information.

`myCompany.endpoint`: This will return the current endpoint used : `'https://api.omniture.com/admin/1.4/rest/'`.\
One can imagine that if you need to use a different endpoint, you can overwrite that element.\
Just a wishful thinking for the one requesting flexibility.

```python
myCompany.endpoint
```

`header`: This will return the header used for the requests to the 1.4 API.\
One can imagine re-using it for other request to the 1.4 API.

```python
myCompany.header
```

### Connector

Because the `LegacyAnalytics` class has been built with the same architecture than the `Analytics` class, it possess the `connector` instance.\
The connector instance is capable to send more type of request type than GET and POST.\
Available methods example:\
* `myCompany.connector.putData`
* `myCompany.connector.patchData`
* `myCompany.connector.deleteData`

### Report Creation

When using the old Reporting API, with the following methods:

* `Report.Queue`
* `Report.Get`
* `Report.GetQueue`

You can return data that are already broke down by different dimensions and with metrics.\
In order to simplify the creation of reports based on these 1.4 report setup, I have built a new method: 

`transformReportToDataFrame``

Its name is pretty self-explanatory.\
It will return a dataframe based on the result returned from a `Report.Get` for the following type of reports:

* `summary`
* `trended`
* `ranked`


example: 

```py
import aanalytics2

org = aanalytics2.LegacyAnalytics("companyName")

myReport = {}## report definition
res = org.postData(method="Report.Queue",data=myReport)

### res is  {'reportID': XXXXXX}

mydata = org.postData(method="Report.Get",data=res)

mydf = ags.transformReportToDataFrame(mydata)

```

## ReportBuilder14

The reportBuilder14 class is a helper capability to build the query for your reporting using the 1.4 API.

### Instantiation

You can instantiate the ReportBuilder14 class with or without any previous request type.

Example:

```py
import aanalytics2 as api2
myreport1 = api2.ReportBuilder14()
### it will create an empty report

template = {
  {'reportDescription': {'reportSuiteID': 'myreportsuite',
  'dateFrom': '2024-10-15',
  'dateTo': '2024-10-16',
  'metrics': [{'id': 'visits'}],
  'elements': [{'id': 'mobiledevicetype', 'top': 50000},
   {'id': 'evar4', 'top': 50000}]}}
}
myreport2 = api2.ReportBuilder14(template)
### it will create a report based on the value passed

myreport3 = api2.ReportBuilder14(myreport2)
### it will create a report based on the previous instance passed
```

### Methods

The following methods are available from the instance once setup.

#### setReportSuite
Set a reportSuite
Argument:
* rside : REQUIRED : The reportSuite ID

example: 
```py
import aanalytics2 as api2
myreport1 = api2.ReportBuilder14()

myreport1.setReportSuite('myrsid')

```

#### setSource
In case yu want to define data warehouse report per example
Argument: 
* source : REQUIRED : The source, by default "warehouse"


#### removeSource
remove the source key in the report.

#### setDate
Set the date for the report. You can use either date or the dateFrom and dateTo parameter.\
Arguments:
* date : OPTIONAL : If requesting a report for a single period, the day/month/year that you want to run the report for. If you use this field, do not use dateFrom or dateTo. If all date fields are omitted, defaults to the current day. This field supports the following formats:\
  Use YYYY for the desired year.\
  Use YYYY-MM for the desired month.\
  Use YYYY-MM-DD for the desired day.\
* dateFrom : OPTIONAL : The starting date range. If you use this field, also include dateTo and do not use date. The date format is YYYY-MM-DD. The month and day designators can be omitted if you want a monthly or yearly report
* dateTo : OPTIONAL : The ending date range (inclusive). If you use this field, also include dateFrom and do not use date. The date format is YYYY-MM-DD. The month and day designators can be omitted if you want a monthly or yearly report

#### setGranularity
Specifies the date granularity used to display report data (trended reports). If this field is omitted, data is aggregated across the entire date range (ranked reports).\
Argument:
* dateGranularity : REQUIRED : Supported values are:
  * minute: Real-Time reports only. Displays report data by minute. Include an integer between 1 - 60 after a semicolon to increase the minute interval. For example, use minute:3 to aggregate data in 3-minute intervals.
  * hour: Displays report data by hour.
  * day: Displays report data by day.
  * week: Displays report data by week.
  * month: Displays report data by month.
  * quarter: Displays report data by quarter.
  * year: Displays report data by year.

#### removeGranularity
Remove the granularity component

#### addMetric
Add a specific metric\
Argument: 
* metricId : REQUIRED : The metric ID to be used
* kwargs : OPTIONAL : any additional attribute you want to add


#### addElement
Add a specific metric\
Argument: 
* elementId : REQUIRED : The element ID to be used
* kwargs : OPTIONAL : any additional attribute you want to add

#### addSegment
Require you to pass the segment object definition to add it on the request.
Arguments
    segment : REQUIRED : A dictionary that provides some information on the segment depending the type.

Example: 
  ```py
  segment = {
      "id" : "segmentID"
  }
  ```
  or
  ```py
  segment = {
      "element": "page",
      "selected": ["Home Page", "Shopping Cart"]
  }
  ```
  or 
  ```py
  segment = {
      "element": "eVar1",
      "classification": "Group Name",
      "search": { "type": "OR", "keywords": ["Administrator", "Manager", "Director"]
    }
  }
  ```

#### removeSegment
Remove the segment from the report

#### setEncoding
Supported values include utf8 or base64.\
Arguments:
* encoding : OPTIONAL : either utf-8 or bas64.
  * utf8: Filters out invalid UTF-8 characters in the request and response.
  * base64: Treats the entire request, including element names, search/pathing filters, special keywords, and dates, as if they are base64 encoded.

#### to_dict
Return the report as a dictionary.\
Usually use to pass it in the request.
