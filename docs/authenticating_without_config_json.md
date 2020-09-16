# How to authenticate without using a config.json file

This is necessary when you run scripts with the aanalytics2 library on certain server environments (e.g. Google Cloud) instead of locally (e.g. in a Jupyter Notebook).
In such environments, referring to config.json may not work.


1. Create a configuration module (a folder) within your repository, e.g. `config/cfg.py`: \
There you write something like this:
```
from os import path

import aanalytics2 as aa2

# Needed so the path to the private key works wherever your repository is hosted.
# In this case, it is in the same folder as this cfg.py module: 'config/private.key'
AA_PRIVATE_KEY_PATH = path.dirname(__file__) + path.sep + 'private.key'

def aaconfig2():
    aa2.config.org_id = 'YOUR_ORGID@AdobeOrg'
    aa2.config.tech_id = 'YOUR_TECH_ID@techacct.adobe.com'
    aa2.config.api_key = 'YOUR_API_KEY-aka-CLIENT_KEY'
    aa2.config.header["X-Api-Key"] = aa2.config.api_key
    aa2.config.secret = 'YOUR-CLIENT-SECRET'
    aa2.config.pathToKey = AA_PRIVATE_KEY_PATH
    return aa2

```

2. Include this in whatever Python script that uses the aanalytics2 API: \
```
from config import cfg
cfg.aaconfig2()
```

3. Now you can work with the Adobe Analytics API V2 Wrapper exactly like in the demo videos at datanalyst.info.
