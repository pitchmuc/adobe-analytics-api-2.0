# Adobe Analytics 1.4 support

This documentation will explain you how to use the `LegacyAnalytics` class that has been added to the module.\
As there is no feature parity between Adobe Analytics 2.0 and Adobe Analytics 1.4, and there probably will never be, I made the choice to enable partial support to the Adobe Analytics 1.4 endpoints. Mostly focus on admin report.\
Why partial support ?\
Because the Adobe Analytics 1.4 is having massive amount of endpoint and my focus is more leaning towards AEP API than legacy APIs that will be discarded soon.\

Nonetheless, the API should provide you the flexibility to realize the action that you want.\
If you feel that the API doesn't provide support for a specific method, feel free to raise a github issue but it will not be prioritized over 2.0 issue.\
You can always provide a Pull Request (PR), and this will be prioritised.

## LegacyAnalytics class

You can instantiate the `LegacyAnalytics` class with your `companyName` returned from the `getCompanyId` method.\
The authentication method is the same than for the Adobe Analytics 2.0.\
It **doesn't take the globalCompanyId** like the Analytics class.

A workflow would looks like the following.

```python
import aanalytics2 as api2
api2.importConfigFile('config_analytics.json')

login = api2.Login()
login.getCompanyId()
## returns
[{'globalCompanyId': 'someId',
  'companyName': 'My Company Name',
  'apiRateLimitPolicy': 'aa_api_tier10_tp',
  'dpc': 'pnw'}]

myCompany = api2.LegacyAnalytics(company_name='My Company Name')
```

## Methods for LegacyAnalytics instance

Following the swagger documentation on the Adobe Analyics 1.4 [available here](https://adobedocs.github.io/analytics-1.4-apis/swagger-docs.html).\
The protocole used in always the POST method, the endpoint is always the same and only the methods differ.

According to that, you have access to 2 methods in the `LegacyAnalytics` instance.

### `postData`

The `postData` method will allow you to realize the action referenced in the documentation.\
It takes 4 possible arguments:

* path: in case the path you want to use is not '/'.
* method: You reference the method that you want to use.
* data: A dictionary that pass the information you want to POST.
* params: Parameters that you want to use on your request.

Example:

```python
myCompany.postData(method="Company.GetTrackingServer",data={"rsid": "myrsid"})
```

### `getData`

The getData will use the GET method to retrieve information from the 1.4 API.\
It is not reference in the documentation but I do believe it exists and there are methods supported with this protocole.\
It takes 3 possible arguments.\

* path: in case the path you want to use is not '/'.
* method: You reference the method that you want to use.
* params: Parameters that you want to use on your request.

Example:

```python
myCompany.getData(method="Company.GetReportSuites")
```

## Attributes & tips for LegacyAnalytics

### Attributes
The instance possess some attributes for your information.

`myCompany.endpoint`: This will return the current endpoint used : `'https://api.omniture.com/admin/1.4/rest/'`.\
One can imagine that if you need to use a different endpoint, you can overwrite that element.\
Just a wishful thinking for the one requesting flexibility.

```python
myCompany.endpoint
```

`header`: This will return the header used for the requests to the 1.4 API.\
One can imagine re-using it for other request to the 1.4 API.

```python
myCompany.header
```

### Connector

Because the `LegacyAnalytics` class has been built with the same architecture than the `Analytics` class, it possess the `connector` instance.\
The connector instance is capable to send more type of request type than GET and POST.\
Available methods example:\
* `myCompany.connector.putData`
* `myCompany.connector.patchData`
* `myCompany.connector.deleteData`
