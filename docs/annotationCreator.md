## Annotation in Adobe Analytics

In Adobe Analytics, the workspace supports the capability to add annotation to the different metrics and filters and these annotation will be displayed on the user reports.\
Annotations are tied to calendar events and may be used with specific dimensions and metrics.\
A complete guide to annotation is available here: <https://experienceleague.adobe.com/en/docs/analytics/analyze/analysis-workspace/components/annotations/overview>

## annotationCreator Module and Class

In order to simplify the creation of annotation, an `annotationCreator` module has been added.\
It allows you to create programmatically annotation based on the different methods supported to build an annotation definition.\
In the end, an annotation definition should look like the following: 

```JSON
{
  "id": "string",
  "name": "string",
  "description": "string",
  "dateRange": "string",
  "color": "STANDARD1",
  "applyToAllReports": true,
  "scope": {
    "metrics": [
      {
        "id": "string",
        "componentType": "string"
      }
    ],
    "filters": [
      {
        "id": "string",
        "operator": "string",
        "dimensionType": "string",
        "terms": [
          "string"
        ],
        "componentType": "string"
      }
    ]
  },
  "createdDate": "YYYY-03-23T01:51:28.686Z",
  "modifiedDate": "YYYY-03-23T01:51:28.686Z",
  "modifiedById": "string",
  "tags": [
    {
      "additionalProp1": {},
      "additionalProp2": {},
      "additionalProp3": {}
    }
  ],
  "shares": [
    {
      "additionalProp1": {},
      "additionalProp2": {},
      "additionalProp3": {}
    }
  ],
  "approved": true,
  "favorite": true,
  "usageSummary": {
    "additionalProp1": {},
    "additionalProp2": {},
    "additionalProp3": {}
  },
  "owner": {
    "id": 0,
    "imsUserId": "string"
  },
  "companyId": 0,
  "reportSuiteName": "string",
  "rsid": "string"
}

```

### Instantiation of annotationCreator

The `AnnotationCreator` class exists in a specific module called `annotationCreator`.\
Example:

```py

import aanalytics2 as api2
from aanalytics2 import annotationCreator

myAnnot = annotationCreator.AnnotationCreator()

```

You can pass an already existing definition as a JSON file via the `data` parameter, such as:

`myAnnot = annotationCreator.AnnotationCreator('myAnnotationTemplate.json')`

Arguments: 
* data : OPTIONAL : Either a dictionary with a definition or a JSON file path to be used


### annotationCreator Methods

#### setName
Set the name for the annotation.\
Arguments:
* name: REQUIRED : Name to be used for the annotation.


#### setDescription
Set the description for the annotation.\
Arguments:
* description: REQUIRED : Description to be used for the annotation.


#### setColor
Set the color for the annotation.\
Arguments:
* color: Color to be used, from "STANDARD1" to "STANDARD9"

#### setReportSuiteName
Set the report suite Name for the annotation.\
Arguments:
* reportSuiteName: REQUIRED : Report suite Name to be used.

#### setReportSuiteId
Set the report suite ID for the annotation.\
Arguments:
* reportSuiteId: REQUIRED : Report suite ID to be used.

#### applyToAllReports
Set whether the annotation applies to all reports.\
Arguments:
* apply: REQUIRED : Boolean indicating if the annotation applies to all reports.

#### setDateRange
Set the date range for the annotation.\
There are two ways to set the date range:
1. Using a direct date range in ISO format (YYYY-MM-DDT00:00:00/YYYY-MM-DDT00:00:00).
2. Using start and end dates in ISO format (YYYY-MM-DD). The wrapper will create the date range automatically.\
if both are provided, the dateRange will be used.
Arguments:
* dateRange: OPTIONAL : Direct date range in ISO format (YYYY-MM-DDT00:00:00/YYYY-MM-DDT00:00:00).
* start: OPTIONAL : Start date in ISO format (YYYY-MM-DD).
* end: OPTIONAL : End date in ISO format (YYYY-MM-DD).

#### addMetric
Add a single metric to the annotation.\
Arguments:
* metricId: REQUIRED : ID of the metric to be added.

#### addMetrics
Add multiple metrics to the annotation.\
Arguments:
* metricIds: REQUIRED : List of metric IDs to be added.

#### addFilter
Add a filter to the annotation.\
Arguments:
* filterId: ID of the filter to be added.
* operator: Optional operator for the filter.
* dimensionType: Optional dimension type for the filter.
* terms: Optional list of terms for the filter.
* componentType: Optional component type for the filter.

#### addTag
Add a tag to the annotation.\
Arguments:
* tag: REQUIRED : Tag to be added.
* name: REQUIRED : name for the tag.

#### to_dict
Convert the annotation data to a dictionary.\
Returns:
* dict: The annotation data as a dictionary.