# Workspace Class

The `getReport2` method available in cjapy is returning an instance of a class by default. This class is the `Workspace` class.\
It enables storage of attributes from your report directly into that instance and attaching methods to it.\
Most important elements are attributes of the instance, we will see what are these attributes and then focus on the methods.

## Attributes of Workspace

### startDate  & endDate

The Workspace instance will possess a startDate and endDates attributes, so you can know what was the dates selection of that report.

### dataframe

Each result data of a getReport method is contained in a dataframe (from the pandas library).\
Accessing the dataframe attribute will permit the access of these data.

### dataRequest

The dataRequest attribute will provide the last status of the request sent to the CJA servers.\
This can be used to understand the query and the result returned.

### globalFilters and metricFilters

globalFilters gives the filters that have been applied at the top of your workspace report, as they apply to all of your reports.\
metricFilters gives you the list of filters and their name applied to your metrics.

### settings

The settings attribute will provide information about the setting of the dataRequest

### pageRequested

This will provide the number of pages that have been requested during the loop.

### summaryData

This attribute will provide the summary data provided by the CJA server.\
Be careful: When requesting segment as dimension reports, the summary data will not provide overall numbers.

### reportType

Define if the report requested was a "normal" report or a "static" report.\
"static" reports refer to segment as row reports.

### rowNumbers, columns

the rowNumbers provide a quick way to find the number of results returned and provided in your dataframe.\
The columns gives you the different columns that are provided in your dataframe.

## Methods

The `Workspace` class provide some methods available on your data.

### to_csv

`to_csv` is a method to save your data into a csv file format.\
It takes its concept from the pandas.DataFrame.to_csv() methods.
Arguments:

* filename: OPTIONAL : name of the file.
* delimiter: OPTIONAL : delimiter of the CSV
* index: OPTIONAL : should the index be included in the CSV (default False)

### to_json

`to_json` is a method to save your data into a JSON file format.\
It takes its concept from the pandas.DataFrame.to_json() methods.
Arguments:

* filename : OPTIONAL : name of the file
* orient : OPTIONAL : orientation of the JSON

### breakdown

`breakdown` method enables you to breakdown one of your result line in your result dataframe by any other dimension you have in your dataview.\
**NOTE**: breakdowns are possible only from normal reportType.
Arguments:

* index : REQUIRED : Value to use as filter for the breakdown or index of the dataframe to use for the breakdown.
    In the dataframe, the index is generally returned as the first column, the value is the actual value of the dimension you want to breakdown.
* dimension : REQUIRED : dimension to report on.
* n_results : OPTIONAL : number of results you want to have on your breakdown. Default 10, can use "inf" to retrieve all possible values.
