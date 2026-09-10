# aanalytics2 : RequestCreator class

The `aanalytics2` module provide a way for you to create request dictionary to Adobe Analytics servers, it is done via the usage of the `RequestCreator`class.\
This class will provide you an instance that contains methods to modify your request definition.\
In this documentation, we will review the different methods available.

## RequestCreator instanciation

In order to generate an instance of the `RequestCreator`, once you have loaded the aanalytics2 module, you can either directly call the class or pass an existing request definition.\

### Creating an empty request

```python
import aanalytics2
### creating an empty request 
myRequest = aanalytics2.RequestCreator()
```

The `myRequest` object will contain the following definition:

```python
{
        "globalFilters": [],
        "metricContainer": {
            "metrics": [],
            "metricFilters": [],
        },
        "dimension": "",
        "settings": {
            "countRepeatInstances": True,
            "limit": 20000,
            "page": 0,
            "nonesBehavior": "exclude-nones",
        },
        "statistics": {"functions": ["col-max", "col-min"]},
        "dataId": "",
    }
```

### Uploading a template request

```python
import aanalytics2, json
### loading your existing request, downloaded from Adobe Analytics interface
with open('mySavedRequest.json','r') as f:
    saveRequest = json.load(f)
### passing the definition to the RequestCreator
myRequest = aanalytics2.RequestCreator(saveRequest)
```

In this case, `myRequest` will contain the definition that you have passed on the initiation of the RequestCreator instance.

## Methods availables on RequestCreator instance

Once your instance has been created, example: `myRequest`, several methods are available to you.\
We will review the different methods available via the object.

* `to_dict()`
  This method returns the current request definition, in a dictionary.

* `save()`
  This method saves the current request definition in a JSON file.
  Arguments:
  * filename : OPTIONAL : Name of the file. (default aa_request_<_timestamp_>.json)

* `setDimension()`
  Set the dimension to be used for reporting.
  Arguments:
  * dimension : REQUIRED : the dimension to build your report on

* `setRSID()`
  Set the reportSuite ID to be used for the reporting.
  Arguments:
  * rsid : REQUIRED : The reportSuite ID to be passed.

* `addMetric()`
  Add a metric to the Request.

* `addGlobalFilter()`
  Add a global filter to the report.
  **NOTE** : You need to have a dateRange filter at least in the global report.
  Arguments:
  * filterId : REQUIRED : The filter to add to the global filter.\
        example:\
        "s293120jf3q9jf38301jd029f030128z482s" -> segment ID\
        "2020-01-01T00:00:00.000/2020-02-01T00:00:00.000" -> dateRange
        "dimension:::itemId" -> dimension value

* `removeGlobalFilter()`
  Remove a specific filter from the globalFilter list.
  You can use either the index of the list or the specific Id of the filter used.
  Arguments:
  * index : REQUIRED : index in the list return
  * filterId : REQUIRED : the id of the filter to be removed (ex: filterId, dateRange)

* `setNoneBehavior()`
  Set the behavior of the None values in that request.
  Arguments:
  * returnNones : OPTIONAL : True or False (True by default)

* `setRepeatInstance()`
  Specify if repeated instances should be counted.
  Arguments:
  * repeat : OPTIONAL : True or False (True by default)

* `setLimit()`
  Specific the number of element to retrieve. Default is 10.
  Arguments:
  * limit : OPTIONAL : number of elements to return

* `addMetricFilter()`
  Add a filter to a metric.
  Arguments:
  * metricId : REQUIRED : metric where the filter is added
  * filterId : REQUIRED : The filter to add.
    When breakdown, use the following format for the value "dimension:::itemId"
  * metricIndex : OPTIONAL : If used, set the filter to the metric located on that index.

* `removeMetricFilter()`
  remove a filter from a metric
  Arguments:
  * filterId : REQUIRED : The filter to add.
        when breakdown, use the following format for the value "dimension:::itemId"

* `setDateRange()`
  Set the dateRange global filter for the request, adding it if none exists yet or replacing the
  existing one otherwise. This is the only method for this — it replaces the old `updateDateRange()`.
  One of `dateRange`, `dateRangeId`, `last`, or both `start` and `end`, is required.
  Arguments:
  * dateRange : OPTIONAL : The date range to set. Accepts either the full timeframe
        ("2026-03-01T00:00:00.000/2026-03-31T23:59:59.999") or a simplified date-only version
        ("2026-03-01/2026-03-31"), which is automatically expanded to the full timeframe
        (00:00:00.000 for the start date, 23:59:59.999 for the end date). Cannot be combined with
        last, start, end or dateRangeId.
  * last : OPTIONAL : Number of days to set the range to. Ends today unless start or end is also
        provided to anchor the window on a specific date instead (e.g. last=7 alone sets the range
        to today and the 6 days before it).
  * start : OPTIONAL : Start date ("YYYY-MM-DD"). Combine with last to compute the end date
        (start + last - 1 days). Cannot be combined with end and last together.
  * end : OPTIONAL : End date ("YYYY-MM-DD"). Combine with last to compute the start date
        (end - last + 1 days). Cannot be combined with start and last together.
  * dateRangeId : OPTIONAL : The id of a saved/custom Date Range component (see
        `Analytics.getDateRanges` / `createDateRange`) to reference instead of a literal date
        range. Cannot be combined with dateRange, last, start or end.

## Instance attributes

At the moment, there are only limited attributes available on the instance of the `RequestCreator` class.

### dates

In order to help build the main date request for your global filter, I have prepared some predefined `dates` available to you.\
The different timeframe available through the `dates` attributes are the following:

* thisMonth : full month date
* untilToday : start of the month till yesterday midnight
* todayIncluded : start of the month, today included
* last30daysTillToday
* last30daysTodayIncluded
* last7daysTillToday
* last7daysTodayIncluded

### today

`today`attribute is a datetime object, with today timestamp.\
This can help you derive other dates if needed.
