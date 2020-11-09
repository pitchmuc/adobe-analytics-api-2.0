# Tests

The library does provide a test folder since the version 0.1.0\
The tests require the pytest module to be installed.

## Test Setup

The tests are set within the trait folder in the "test_core_analytics.py" file.\
They will automatically run the following checks:

* create a config file
* import a wrong file
* import a good file
* create an Analytics instance from logger
* test the GET methods:
  * getUsers
  * getReportSuites
  * getDimensions
  * getMetrics
  * getSegments
  * getCalculatedMetrics

## Test Requirements

In order for the test to run correctly, you would need to set several elements.

### Adding CONFIG file in the folder

You would be required to add a config file and the private.key in the test folder in order to load them up.

**TIP**: Ensure that you are using the following path by default as prefix "/test/<your-config-file.json>" and "/test/<your-private-key-path.key>" in the script and in your configuration file.
In order to ensure that we are testing the new version of the library, I change the default folder location to the one on top.

### Check that first reportSuite returned

By default, the getMetrics and getDimensions are checking the elements for the first reportSuite returned by the getReportSuites method.
If you want to ensure that you are looking for the correct reportSuite, feel free to modify the script, do not push the changes in your pull request.

## Running tests

In order to run the test, you can go to the "test" folder and run pytest directly there.\
It will automatically take the "test_core_analytics.py" file. 

Possible commandes:

```shell
pytest
## short traceback
pytest --tb=short
## long traceback
pytest --tb=long
```

## Helping developing tests

If you are willing to help building tests in order to make the library more robust. Don't hesitate to realize pull requests.

Any tips on using pytest for that purpose is also appreciated. 
