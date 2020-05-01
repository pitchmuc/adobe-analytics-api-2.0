# Getting Started with the python wrapper for Adobe Analytics API 2.0

On this page, a quick example on how to start with the wrapper.

## 1. Create an Adobe IO console account

First you should create an Adobe IO account and connect to a Product Profile.
You can also create an Adobe IO account and then go to the product Profile in Adobe Admin Console to contect to your Adobe IO account.

When you create your Adobe IO account, you need to set a certificate, keep the key nearby because you will need it.

## 2. Download the library

You can directly install the library from here:
python -m pip install --upgrade git+<https://github.com/pitchmuc/adobe_analytics_api_2.0.git#egg=adobe_analytics_2>

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

## 5. Get Company ID(s) & create your instance

Once all of these setup steps are completed, you can start using the methods attached to Analytics API.
The first method is the _getCompanyId_, that will return you the different company ID attached to your account.
you will extract the *globalCompanyId* and use it to create your instance and use the other methods...

```python
import aanalytics2 as api2
api2.importConfigFile('myconfig.json')
cids = api2.getCompanyId()
cid = cids[0]['globalCompanyId'] ## using the first one
mycompany = api2.Analytics(cid)
```

## 6. Use the methods

Once you have the instance created, you can use the different methods available to them.
Don't hesitate to use the _help()_ function in order to have more details on the different possible parameters.
Example :

```python
segments = mycompany.getSegments()
```
