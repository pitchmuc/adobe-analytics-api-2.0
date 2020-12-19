# Release info

This page will give you the change that are occuring when a new version has been published on pypi.
The changes have been tracked starting version 0.1.0

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
