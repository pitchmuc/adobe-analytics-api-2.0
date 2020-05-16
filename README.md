# Adobe Analytics API v2.0

-----------------------

This is a python wrapper for the adobe analytics API 2.0.

## Documentation

Most of the documentation for this API will be hosted at [datanalyst.info][1].

## Functionality

Basic Functionality that are covered :

* Run a report statement
* Retrieve Users
* Retrieve Segments
* Retrieve Metrics
* Retrieve Dimensions
* Retrieve Calculated Metrics

## Getting Started

To install the library with PIP use:

```cli
pip install aanalytics2
```

or

```cli
python -m pip install --upgrade git+<https://github.com/pitchmuc/adobe_analytics_api_2.0.git#egg=aanalytics2>
```

[Getting Started details on how to use it](./docs/getting_started.md).

Complete documentation [here](./docs/main.md) (kind of)

## Dependencies

In order to use this API in python, you would need to have those libraries installed :

* pandas
* requests
* json
* PyJWT
* PyJWT[crypto]
* pathlib

## Others Sources

You can find information about the Adobe Analytics API 2.0 here :

* [https://adobedocs.github.io/analytics-2.0-apis][2]
* [https://github.com/AdobeDocs/analytics-2.0-apis/blob/master/reporting-guide.md][3]

[1]: https://www.datanalyst.info
[2]: https://adobedocs.github.io/analytics-2.0-apis
[3]: https://github.com/AdobeDocs/analytics-2.0-apis/blob/master/reporting-guide.md
