# Release info

This page will give you the change that are occuring when a new version has been published on pypi.
The changes have been tracked starting version 0.1.0

## version 0.5.5
* Migrate the MCP server from `FastMCP` to `MCPServer` and require `mcp>=2.0`. Expected tool errors now return actionable messages to the client.
* Add MCP tools to update existing segments, calculated metrics, and date ranges: `update_segment`, `update_calculated_metric`, and `update_date_range`. [Documentation](./mcp_server.md#available-tools)
* Add MCP lookup tools `find_segment` and `find_calculated_metric`. These search the local Knowledge Graph first and explicitly identify when results fall back to the live API.
* Add the CLI command `create_report_request` to generate a report request JSON file, with optional dimension, metrics, segment, date range, and output filename. Omitted report components are selected from accessible report suite data. [Documentation](./cli.md#create_report_request)

Patches:
* Fix `Workspace` parsing of report requests that reference a saved date range via `dateRangeId`.
* Normalize Knowledge Graph dimension IDs by removing item-specific `::` suffixes, so dimension metadata and usage references point to the same component.
* Initialize Knowledge Graph project details even when `loadProjects` has not been called, allowing `buildGraph` to run without loading Workspace projects.
* Add `KnowledgeGraph.loadGraph` to restore local Turtle snapshots, including namespace bindings and usage/co-occurrence counters. Loading replaces the current graph by default; `merge=True` explicitly combines graphs. File and parsing errors leave the current graph unchanged. [Documentation](./knowledgegraph.md#loadgraph)
* Add `buildGraph(incremental=True)` to reuse an existing component graph and add only newly loaded Workspace projects, without rescanning segments or calculated metrics. Previously counted project IDs are skipped, including after saving and reloading a Turtle snapshot. Use a full build to refresh an existing project's changed definition. [Documentation](./knowledgegraph.md#buildgraph)
* Add `getUsageCounts` and per-instance `entity_usage`, `dim_metric_cooccurrence`, and `dim_segment_cooccurrence` dictionaries to inspect counters as Python integers. The dictionaries are restored on load and synchronized after builds; editing them does not change the RDF graph. [Documentation](./knowledgegraph.md#getusagecounts)
* Validate stored usage and co-occurrence counters before incremental updates, rejecting negative, non-integer, conflicting, or malformed values and duplicate co-occurrence records. Loading a graph with invalid counters logs a warning and leaves the counter dictionaries unavailable until the data is corrected or rebuilt.
* Preserve existing Knowledge Graph metadata during full builds by default, while replacing generated usage counters, co-occurrence records, and project registrations with a fresh snapshot to avoid stale or duplicate counts. Use `buildGraph(merge=False)` to rebuild the entire graph from scratch.
* Allow repeated `loadProjects` calls to accumulate project details without narrowing the available project catalogue. Match project-owner filters case-insensitively. [Documentation](./knowledgegraph.md#loadprojects)
* Reuse the resolved login configuration for Knowledge Graph connections, including the proxy configured in that configuration. Continue building after scan connection errors or timeouts, retaining component metadata and warning that usage counts are incomplete.

## version 0.5.4
* Add `getMarketingChannels` to retrieve marketing channel configurations for one or more report suites. [Documentation](./main.md#getMarketingChannels)
* Replace the earlier Workspace creator with the `workspaceManager` module and its `WorkspaceManager`, `TextBuilder`, `FreeForm`, and `Panel` classes. Build and parse Workspace projects with panels, rich text, freeform tables, metric filters, breakdowns, segment filters, dropdowns, summary numbers, and charts. [Documentation](./workspaceManager.md)
* Add the interactive `aanalytics2` CLI, including non-interactive commands, CSV exports, and a `RequestCreator` sub-shell for building and running reports. [Documentation](./cli.md)
* Add the `KnowledgeGraph` class to build RDF graphs of report suites and components, track usage and co-occurrence, export Turtle files, and query with SPARQL. Workspace project loading is optional. [Documentation](./knowledgegraph.md)
* Add the `aanalytics2-mcp` server with tools for component discovery, reporting, Workspace creation, and optional Knowledge Graph queries, plus an ontology resource for MCP clients. [Documentation](./mcp_server.md)
* Add `format="raw"` support to `getDimensions` and `getDateRanges`, and allow `scanCalculatedMetric` to reuse segment definitions through `knownSegments`.
* Extend `RequestCreator.setDateRange` to support saved date range IDs and named date presets.\
Patches:
* Fix MCP connection startup and remove obsolete JWT configuration references.
* Respect the company ID in the configuration file when starting the MCP server, unless explicitly overridden.
* Fix parsing of existing Workspace/freeform data and add the MCP `update_workspace` tool to save changes to an existing project.
* Add MCP tools to list classification datasets and retrieve dataset metadata.
* Add `shares` to `getSegment` extended information, and MCP tools to validate/create segments and calculated metrics and create saved date ranges.
* Fix Workspace breakdown creation through MCP by resolving actual row item IDs.
* Add optional proxy support for API requests and OAuth token generation, configurable through the library and CLI.


## version 0.5.3 
* fix limitation regarding dateRanges
* Replicate the configuration file to local storage when using the `return_object` paramater.
* Fix issue on logging to `LegacyAnalytics`\
Patches:
* Fix issue related to `getClassificationTemplate` method that was not working with the new system.
* Fix issue related to JWT import
* remove the token_provider module and move the methods to connector.py for better handling of the token generation and refreshing.
* Better handling of segments in RequestCreator class when using the `getReport2` method.

## version 0.5.0 
* refactor of the connector.py file to better handle the token generation, refreshing token and retries.
* refactor of the `getReport2` method to better handle the filters and breakdowns. Also being more robust on the parsing of the data returned by Adobe Analytics API 2.0. 
* Allow a configObject to be generated from the `configure` method and use it to generate the token for better flexibility.

## version 0.4.4
* adding the data feed API capabilities
  * getDataFeeds
  * getDataFeed
  * getDataFeedRequests
  * updateDataFeed
  * createDataFeed
  * reprocessDataFeedRequest
  * resendDataFeedRequest
  * getDataFeedColumnNames
  * createColumnPreset
  * getColumnPreset
* adding `createDateRange` method\
Patch: 
* improving classification methods

## version 0.4.3
* adding the `datarepair` module and `DataRepair` class [documentation](./datarepair.md)
* adding the `DataRepairJobCreator` class in `datarepair` module, [documentation](./datarepair.md#DataRepairJobCreator)
* adding annotationCreator module and class [documentation](./annotationCreator.md)
* refactor of the documentation to allow id of the method for better shareability
* simplify header creation for requests
* adding new share management methods:
  * getShares
  * getShare
  * getShareComponents
  * deleteShare
  * updateShare
* adding `getReportSuiteTimeZones` method
* adding methods on data sources:
  * getDataSourceAccounts
  * getDataSourceAccount
  * getDataSourceJobs
  * getDataSourceJob
  * sendDataToDataSource
  * createDataSourceAccount
  * deleteDataSourceAccount
* improve datawarehouse requests
* create the `dwhCreator` module with the `DwhCreator` class [documentation](./dwhCreator.md)
* add Cloud methods:
  * getCloudAccounts
  * getCloudAccountProperties
  * getCloudLocations
  * getCloudLocation
  * createCloudLocation
  * updateCloudLocation
  * deleteCloudLocation
  * updateCloudAccount
* improve `getUsers`
* improving test scenarios\
Patch: 
* fix `datetime` reference in datarepair API
* adding `getReportWait` method in Legacy API [documentation](./legacyAnalytics.md#getReportWait)
* adding `getReportSuite`
* adding `createReportSuite` 
* fixing `getUsers`

## version 0.4.2

* adding `getAlerts` method
* adding `classifications` methods.
  * getClassificationDatasets
  * getClassificationDataset
  * getClassificationJobs
  * getClassificationJob
  * deleteClassification
  * importClassification
  * createExportClassification
  * getExportClassificationFile
  * getClassificationTemplate
* adding `datawarehouse` methods.
  * getDataWarehouseReports
  * getDataWarehouseReport
  * resendDataWarehouseReport
  * getDataWarehouseScheduledRequests
  * getDataWarehouseScheduledRequest\
Patch :
* fixing issue on getClassificationDatasets method
* adding more methods to classication
* improving standard for `retry` parameters.
* adding capability for reading reports (`summary`, `trended` and `ranked`) out of the 1.4 Reporting API via `transformReportToDataFrame` (see [LegacyAnalytics](./legacyAnalytics.md))
* adding the `createDataWarehouseScheduledRequest` method
* adding the `ReportBuilder14` class for building query on legacy API (see [LegacyAnalytics](./legacyAnalytics.md))
* adding `publishingStatus` in the getSegments `extendedInfo` capability
* adding `complexity` and `lastRecordedAccess` in `extendInfo` in `getProjects`

## version 0.4.1

* updating legacy methods to support new system
* migrating to V3 auth token generation
* fixing the `Project` class for dynamic dimensions
* supporting pandas 2.0.0 for concatenation\
Patch:
* fix on full extract for `dimensions` and `metrics`.
* fix on save to `getReport2`
* adding support for other folder location for ingestion files.

## version 0.4.0

* supporting Oauth Token V2 
* Oauth Token V2 is the new default support when creating a config file
* better respecting existing parameter via getReport2
* raising exception on error for generating token
* deepcopying the request made to `getReport2` method to avoid modification on original variable.
* supporting passing the `format` parameter to be a `logger.setFormatter()` instance when passing the logger object.\
PATCH:
* adding the `validateProject` method
* Supporting the old version for the legacy `retrieveToken` method with the new method for JWT.
* changing some methods to support new pandas version

## version 0.3.3

* adding the width parameter on scheduling report.
* parameterization of the logger generation + add new info for logging info on GET requests
Patch: \
* adding `shareComponent` method (from @loldenburg)
* resolving metrics name (from @loldenburg)
* fixing issue when using dynamic filter on report for `getReport2` method.
* supporting requests for getReport2 for static row and resolve column
* fix issue that getReport2 does not respect the JSON configure option for none-behavior and countRepeatInstances

## version 0.3.2

* Adding annotation methods
  * getAnnotations
  * getAnnotation
  * createAnnotation
  * updateAnnotation
  * deleteAnnotation
* Add a `getDateRange` method

## version 0.3.1

* adding the `workspace` module that allow more dynamic and better presentation of the data. [Documentation](https://github.com/pitchmuc/adobe-analytics-api-2.0/blob/master/docs/workspace.md)
* adding the getReport2 method and [documentation](./main.md#getreport2)
* Improving the RequestCreator class by adding 
  * easy load of JSON files
  * capability to setSearch
  * remove all metrics
* Support RequestCreator instance in the getReport methods
* adding more scheduleJob methods:
  * getScheduledJob for specific job
  * createScheduledJob
  * deleteScheduledJob
  * updateScheduledJob
  * getDeliverySettings
  * getDeliverySetting
  * createDeliverySetting
  * updateDeliverySetting
  * deleteDeliverySetting
* adding [update methods documentation](https://github.com/pitchmuc/adobe-analytics-api-2.0/blob/master/docs/main.md#update-methods)
* Fixing references of the EventType for Audit Log `LOGS_EVENT_TYPE` attribute.\
Patch: 
* renaming some scheduleReport method typo.
* supporting old report request without statistics info

## version 0.3.0

* Fix an issue where segments were not considered in findComponentUsage when they were used in columns
* adding `RequestCreator` class ([documentation](https://github.com/pitchmuc/adobe-analytics-api-2.0/blob/master/docs/requestCreator.md))
* fix issue when logging object error the output of failed calls.\
Patch : 
* adding encoding capability for `validation` and `sendFiles` method in the `Bulkapi` class.
* Improving consistency for reading project dictionaries on `Project` class instanciation

## version 0.2.9

* Adding the `getScheduledJobs` endpoint
* Adding logging capability ([documentation](./logging.md))
* Fixing some typo on regex used for `findComponentUsage`
* Adding better docstring for some methods.
Patches:
* Fix issue on `getScheduleJobs`
* improve `createConfigFile` method
* improving Documentation
* adding better log from the GET requests

## version 0.2.8

* adding the `decodeAArequests` method ([documentation](https://github.com/pitchmuc/adobe-analytics-api-2.0/blob/master/docs/main.md#decode-aa-requests)).
* upgrading requirement libraries
* cleaning legacy methods not supported anymore (getData,postData,putData,deleteData,getCompanyId)
Patch:
* adding `deleteDateRange` method
* changing requirements back for pandas to 0.25.3

## version 0.2.7

* adding `compareReportSuites` method. ([documentation](https://github.com/pitchmuc/adobe-analytics-api-2.0/blob/master/docs/main.md#compare-reportsuite))
* adding `reportType` as attribute from projects. Either `desktop` or `mobile`
* adding `version` and `curation` attributes by default on dict version of `project`
* adding `scanSegment` and `scanCalculatedMetric` methods. ([documentation](https://github.com/pitchmuc/adobe-analytics-api-2.0/blob/master/docs/main.md#the-scan-methods))
* adding `rsidSuffix` parameter for `Project` class ([documentation](https://github.com/pitchmuc/adobe-analytics-api-2.0/blob/master/docs/projects.md#project-class)), `findComponentUsage` ([documentation](https://github.com/pitchmuc/adobe-analytics-api-2.0/blob/master/docs/projects.md#find-the-components-used)) and `getAllProjectDetails` ([documentation](https://github.com/pitchmuc/adobe-analytics-api-2.0/blob/master/docs/projects.md#getting-all-projects-details))\
*Patch*:
* Adding description parameter option in `getMetrics`
* Most of `save` parameter will get timestamp
* Fix `rsidPrefix` as `rsidSuffix` parameter for `findComponentUsage` method.
* Fix generator exhausted when trying to use recursive mode in `findComponentUsage`.
* Change default comparison to retrieve all columns from dimensions and metrics.
* Change search for elements to support rsidSuffix in `findComponentUsage`
* fixed scan when no segment are used.

## version 0.2.6

* `getSegments` and `getMetrics` return now shares information
* adding `429` status code handling for *delete* and *patch* requests.
* adding `cache` option parameter for `getProjects`, `getProject` and `getAllProjectDetails`
* Fixing `Project` class that was expecting global filters to be used.

## version 0.2.5

* adding limited capability for 1.4 API [see documentation](./legacyAnalytics.md)
* Sepearating the Project Class to its own submodule
* Improve classes representation
* Adding `getAllProjectDetails` method
* Adding `projectsDetails` attributes on the Analytics instance that stores the projectDetail in a dictionary.
* Adding `listProjectIds` attributes that stores the result of `getProjects` method in a `raw` format.
* Adding the `getCalculatedMetric` method in the module.
* Adding *validate* methods for calculatedMetric and Segment
* Update documentation for [Projects elements](./projects.md)

## version 0.2.4

* adding missing dependency file
* adding the `getTopItems` method

## version 0.2.3

* Better error description when receiving report without `lastPage` key.
* Adding the User Logs Usage endpoint.
* Adding attribute `restTime` on Connector class to modify the waiting time when reaching error 429 (Too many requests)
* Better handling of the 429 error for the GET method. Not required to have a the *retry* parameter.

## version 0.2.2

* fix issue when token needed to be updated after 24h.

## version 0.2.1

* fix issue on `_checkingDate` method in `AdobeRequest`

## version 0.2.0

* Upgrade compatibility for PyJWT 2.0.0.
* Fix return element for `sendFiles` method on the Bulkapi class for ingestion method.
* Improve management of throttle limit for getReport.  

## version 0.1.9

* Fix default statement for `getVirtualReportSuite` that save the result automatically.
* Improve return type statement

## version 0.1.8

* Fix legacy method to retrieve token that was broken by the new capability.

## version 0.1.7

* Adding an optional parameter to pass directly the private.key as a string to the `configure` method
* Update documentation [get-started](./getting_started.md) & docstring for `configure` method.

## version 0.1.6

* Improving documentation
* Fixing duplication for Project class analyzer.\
  Now elementsUsed & nbElementsUsed are using deduplicated values.
* Adding updateProject and createProject methods (beta - not tested)

## version 0.1.5

* Improving retry parameter behavior on GET methods
* Improving Project class consistency

## version 0.1.4

* Dropping usage of modules.py for handling dependency
* Fix updateDateRanges and updateVirtualReportSuite
* Adding Projects endpoints (getProjects, getProject, deleteProject)
* Adding Project Data class to easily extract information of project

## version 0.1.3

* adding support for the Tags components
* adding new API for connecting without a config file
* update documentation for server connection

## version 0.1.2

* adding the updateVirtualReportSuite method
* adding the updateCalculatedMetrics method
* update deleteCalculatedMetrics to deleteCalculatedMetric
* update getCalculatedMetrics to respect the inclType as parameter.
* update getVirtualReportSuites to add the inclType parameter
* fix modules importing in the ingestion module
* fix header on Bulk Ingestion API class.

## version 0.1.1

* update the getReport method with limit parameter
* rename "Loggin" class to "Login" class.
* update documentation

## Version 0.1.0

* Changing Architecture on the requests to Adobe Analytics API for the main class.
  This add the following functionalities:
  * retry parameter : a parameter that set the number of time you want to retry a GET method if the first one fails.
  * independance between Analytics instances : possibility to use the same script for 2 loggins company or even 2 experiences clouds API access.
  * Possibility to start directly with Analytics class if you already know you companyId.
* Adding a new class Loggin that enables you to retrive the companyId
* Ensuring that legacy methods (getCompanyId) is still available from the main module.
* Adding test for GET methods of the core library (Analytics class)
* Adding test documentation for setting tests
* Adding release information
