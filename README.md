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
* Retrieve Users
* Retrieve Segments
* Retrieve Metrics
* Retrieve Dimensions
* Retrieve Calculated Metrics
* Retrieve Virtual Report Suites
* Retrieve Virtual Report Suite Curated Components
* Retrieve Tags
* Retrieve Usage Logs from users
* Retrieve Projects
* Retrieve Scheduled Jobs / Projects
* Update Segment
* Update Calculated Metric
* Update Tags
* Update Project
* Delete Segment
* Delete CalculatedMetric
* Delete VirtualReportSuite
* Delete Project
* Delete DateRange
* createProject

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

## Project Data

There is a BETA feature to retrieve the Workspace projects and the components used.\
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
