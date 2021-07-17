# Getting Started with the python wrapper for Adobe Analytics API 2.0

On this page, a quick example on how to start with the wrapper.
More details explanation are available in the [main file](./main.md) or one the [datanalyst.info website](https://www.datanalyst.info/category/python/adobe-analytics-api-2-0/)

## 1. Create an Adobe IO console account

First you should create an Adobe IO account and connect to a Product Profile.
You can also create an Adobe IO account and then go to the product Profile in Adobe Admin Console to contect to your Adobe IO account.

When you create your Adobe IO account, you need to set a certificate, keep the key nearby because you will need it.
You can follow this [tutorial](https://www.datanalyst.info/python/adobe-io-user-management/adobe-io-jwt-authentication-with-python/)

## 2. Download the library

You can directly install the library from the command line:

```cli
pip install aanalytics2
```

or

```cli
python -m pip install --upgrade git+<https://github.com/pitchmuc/adobe_analytics_api_2.0.git#egg=aanalytics2>
```

or you can copy paste the aanalytics2.py file in your Lib/ folder in your Python installation.

## 3. Setup a JSON with your information

Starting with the wrapper, you can import it and create a template for the JSON file that will store your credential to your Adobe IO account.

```python
import aanalytics2 as api2
api2.createConfigFile()
```

This will create a JSON and you will need to fill it with the information available in your adobe io account.

## 4. Import the configuration file

Once this is done, you can import the configuration file.
I would recommend to store the config file and the key in the folder that you are using, however, the element will work if you are using correct path.

```python
import aanalytics2 as api2
api2.importConfigFile('myconfig.json')
```

### Alternative 1 : Using the configure method

When you want to connect to the Analytics API from a server application, you may want to use the `configure` method and passing the element directly.
You can see more details on that connection method on the [authentication without config json page](./authenticating_without_config_json.md)

### Alternative 2 : Using Oauth Token

It may be the case that you only have information from Oauth authentication.\
In that case, you usually ends up with the following information:

* orgId
* clientId
* token

In that case, you can use the configure `method` as well with some specific parameters.
* oauth
* token

```python
import aanalytics2 as api2

api2.configure(oauth=True,org_id='XXXXXX@AdobeOrg',client_id='ysfn28d938z2een27z4',token='myToken')
```

*NOTE*: The token will be valid for 22 hours and will not be refresh afterwards.

## 5. Get Company ID(s) & create your instance

Once all of these setup steps are completed, you can instantiate the `Login` class.\
Starting version 0.1.1 a new class (Login) is avalabile in order to retrieve the login company.\
This is the default path that you should use to retrieve your companyId.

```python
import aanalytics2 as api2
api2.importConfigFile('myconfig.json')

login = api2.Login()
cids = login.getCompanyId()

#you can also access the login return through the instance
login.COMPANY_IDS
## returns the same result that cids.
```

The legacy method is the _getCompanyId_, that will return you the different company ID attached to your account.\
You will extract the *globalCompanyId* and use it to create your instance and use it later in the `Analytics` class . \
This method **will be deprecated** some time in the future.

```python
import aanalytics2 as api2
api2.importConfigFile('myconfig.json')
cids = api2.getCompanyId()
cid = cids[0]['globalCompanyId'] ## using the first one
mycompany = api2.Analytics(cid)
```

From there, 2 methods can be used to create the Analytics class instance.

```python
mycompany = api2.Analytics(cid)

# method directly in the Login class
mycompany = login.createAnalyticsConnection(cid)

```

Note that for both methods you can use the **retry** parameter to set the number of times the request can be retry in case of Adobe Analytics server not responding.\
This option will be set for every GET method in your instance.

```python

mycompany = api2.Analytics(cid,retry=3)

# new method directly in the Login class
mycompany = loggin.createAnalyticsConnection(cid,retry=3)

```

## 6. Use the methods in your instance

Once you have the instance created, you can use the different methods available to them.
Don't hesitate to use the _help()_ function in order to have more details on the different possible parameters.
Example :

```python
segments = mycompany.getSegments()
```

or

```python
myreport = mycompany.getReport('myRequest.json')
```

The response that is given is a dictionary with the relevant information from your request (timeframe, segments used, etc...)\
You can access the data directly with the "data" keyword.

```python
data = myreport['data']
```
