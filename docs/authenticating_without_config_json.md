[Back to README](../README.md)

# How to authenticate without using a config.json file

This is necessary when you run scripts with the aanalytics2 library on certain server environments (e.g. Google Cloud) instead of locally (e.g. in a Jupyter Notebook).
In such environments, referring to config.json may not work.

In that case, you can pass the variables to the configure method available.

## 1. Create your different environment variables

In windows command line:

```shell
setx NEWVAR SOMETHING
```

In Powershell:

```shell
$Env:<variable-name> = "<new-value>"
```

Linux / Unix / iOS shells:

```shell
export NAME=VALUE
```

## 2. Accessing the variable in your python script

You can then access the different values in your python script by realizing the following command:

```python
import os

USER = os.getenv('API_USER')
PASSWORD = os.environ.get('API_PASSWORD')
```

## 3. using the configure method

The aanalytics2 module provide a configure method that will set the correct value to be used in the module.

**Note** : Be careful there is a possibility to pass the `path_to_key` or `private_key` to the configure method.\
Select the correct method:

* path_to_key : the element is a path to a file containing your key.
* private_key : the element is the key as a string directly.

```python
import os

my_org_id = os.getenv('org_id')
my_tech_id = os.environ.get('tech_id')
my_secret = os.environ.get('secret')
my_path_to_key = os.environ.get('path_to_key')
my_client_id = os.environ.get('client_id')


import aanalytics2 as api2

api2.configure(org_id=my_org_id,tech_id=my_tech_id, secret=my_secret,path_to_key=my_path_to_key,client_id=my_client_id)

```

Starting this point, you can use the aanalytics2 module as explained in the documentation.
