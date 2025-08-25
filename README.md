# Adobe Analytics API v2.0

-----------------------

This is a python wrapper for the adobe analytics API 2.0.

## Documentation

Most of the documentation for this API will be hosted at [datanalyst.info][1].\
[Getting Started details on Github](./docs/getting_started.md).

[Appendix for running on a server](./docs/authenticating_without_config_json.md)

## Versions

A documentation about the releases information can be found here : [aanalytics2 releases](./docs/releases.md)

## Functionalities

Functionalities that are covered :

### Reporting API

* Run a report statement
* Retrieve Users, Segments, Metrics, Dimensions, Calculated Metrics, DateRange ,Virtual Report Suites, Tags, Projects, Annotations
* Update Segment, Calculated Metric, Tags, Project, DateRange, Annotation, 
* Delete Segment, CalculatedMetric, VirtualReportSuite, Project, DateRange, Annotation
* Create a Project
* Create a Scheduling job for a Workspace Project
* Retrieve Usage Logs from users
* Manage Data Source
* Manage Data Warehouse Requests 

documentation on reporting [here](./docs/main.md)

### Data Ingestion APIs

* Data Ingestion API from API 1.4
* Bulk Data Insertion API

documentation on ingestion APIs [here](./docs/ingestion.md)

## Legacy Analytics API 1.4

This module provide limited support for the 1.4 API.
It basically wrapped your request with some internal module and you can pass your request path, method, parameters and / or data.
More information in the [dedicated documentation for 1.4](./docs/legacyAnalytics.md)

## RequestCreator class

The `aanalytics2` module enables you to generate request dictionary for the getReport method easily.\
You will have no need to go to the UI in order to create a report template JSON anymore.\
Do it automatically from the python interface.
More information on the [`RequestCreator` documentation](./docs/requestCreator.md)

## AnnotationCreator

The `aanalytics2` module simplifies the creation of annotation definition via a specific module and class.\
The `annotationCreator` module contains the `AnnotationCreator` class.\
It is a builder that helps you create your annotation programmatically.\
More information on the [`AnnotationCreator` documentation](./docs/annotationCreator.md)

## Data Warehouse Creator

The `aanalytics2` module tries to simplify the creation of the data warehouse request definitions.\
A builder has been provided in an additional module: `dwhCreator`.\
The module contains a class `DwhCreator` that should provide helpful functionalities to define your report requests.\
More information on the [`DwhCreator` class](./docs/dwhCreator.md)

## Data Repair API

The data repair API allows to delete or transform data that has been already ingested in Adobe Analytics.\
The Data Repair API is an additional SKU in the Adobe Analytics licence, make sure you are provisionned before trying to use the module and API.\
More information on the [data repair module](./docs/datarepair.md)

## Project Data

There is a feature to retrieve the Workspace projects and the components used.\
Refer to this [documentation on Project](./docs/projects.md) for more information.

## Logging capability

In case you want to use the logging capability for your script.\
You can look at the reference for this on the [logging documentation page](./docs/logging.md)

## Getting Started

To install the library with PIP use:

```cli
pip install aanalytics2
```

or

```cli
python -m pip install --upgrade git+<https://github.com/pitchmuc/adobe_analytics_api_2.0.git#egg=aanalytics2>
```

## Dependencies

In order to use this API in python, you would need to have those libraries installed :

* pandas
* requests
* json
* PyJWT
* PyJWT[crypto]
* pathlib
* dicttoxml
* pytest

## Test

A test support has been added with pytest.
The complete documentation to run the test can be found here : [testing aanalytics2](./docs/test.md)

## Others Sources

You can find information about the Adobe Analytics API 2.0 here :

* [https://adobedocs.github.io/analytics-2.0-apis][2]
* [https://github.com/AdobeDocs/analytics-2.0-apis/blob/master/reporting-guide.md][3]

[1]: https://www.datanalyst.info
[2]: https://adobedocs.github.io/analytics-2.0-apis
[3]: https://github.com/AdobeDocs/analytics-2.0-apis/blob/master/reporting-guide.md
