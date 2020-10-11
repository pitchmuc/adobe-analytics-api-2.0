# Release info

This page will give you the change that are occuring when a new version has been published on pypi.
The changes have been tracked starting version 0.1.0

## Version 0.1.0

* Changing Architecture on the requests to Adobe Analytics API for the main class.
  This add the following functionalities:
  * retry parameter : a parameter that set the number of time you want to retry a GET method if the first one fails.
  * independance between Analytics instances : possibility to use the same script for 2 loggins company or even 2 experiences clouds API access.
  * Possibility to start directly with Analytics class if you already know you companyId.
* Adding a new class Logger that enables you to retrive the companyId
* Ensuring that legacy methods (getCompanyId) is still available from the main module.
* Adding test for GET methods of the core library (Analytics class)
* Adding test documentation for setting tests
* Adding release information