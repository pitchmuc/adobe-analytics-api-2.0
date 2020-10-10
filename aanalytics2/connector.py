import aanalytics2 as api2


class AdobeRequest:
    """
    Handle request to Audience Manager and taking care that the request have a valid token set each time.
    """

    def __init__(self, config_object: dict = api2.config.config_object, header: dict = api2.config.header, verbose: bool = False, retry: int = 0)->None:
        """
        Set the connector to be used for handling request to AAM
        Arguments:
            config_object : OPTIONAL : Require the importConfig file to have been used.
            config_object : OPTIONAL : Require the importConfig file to have been used.
        """
        if config_object['org_id'] == "":
            raise Exception(
                'You have to upload the configuration file with importConfigFile method.')
        self.config = api2.modules.deepcopy(config_object)
        self.header = api2.modules.deepcopy(header)
        self.retry = retry
        if self.config['token'] == "" or api2.modules.time.time() > self.config['date_limit']:
            token = self.retrieveToken(verbose=verbose)

    def retrieveToken(self, verbose: bool = False, **kwargs)->str:
        """ Retrieve the token by using the information provided by the user during the import importConfigFile function. 
        Argument : 
            verbose : OPTIONAL : Default False. If set to True, print information.
        """
        private_key_path = api2._find_path(self.config['pathToKey'])
        if private_key_path is None:
            raise FileNotFoundError(
                f"Unable to find the configuration file under path `{self.config['pathToKey']}`.")
        with open(api2.modules.Path(private_key_path), 'r') as f:
            private_key_unencrypted = f.read()
            header_jwt = {'cache-control': 'no-cache',
                          'content-type': 'application/x-www-form-urlencoded'}
        jwtPayload = {
            # Expiration set to 24 hours
            "exp": round(24*60*60 + int(api2.modules.time.time())),
            "iss": self.config['org_id'],  # org_id
            # technical_account_id
            "sub": self.config['tech_id'],
            "https://ims-na1.adobelogin.com/s/ent_analytics_bulk_ingest_sdk": True,
            "aud": "https://ims-na1.adobelogin.com/c/"+self.config['client_id']
        }
        encoded_jwt = api2.modules.jwt.encode(
            jwtPayload, private_key_unencrypted, algorithm='RS256')  # working algorithm
        payload = {
            "client_id": self.config['client_id'],
            "client_secret": self.config['secret'],
            "jwt_token": encoded_jwt.decode("utf-8")
        }
        response = api2.modules.requests.post(self.config['tokenEndpoint'],
                                              headers=header_jwt, data=payload)
        json_response = response.json()
        token = json_response['access_token']
        self.config['token'] = token
        self.header.update(
            {"Authorization": f"Bearer {token}"})
        expire = json_response['expires_in']
        self.config["date_limit"] = api2.modules.time.time() + expire/1000 - \
            500  # end of time for the token
        if verbose:
            print('token valid till : ' +
                  api2.modules.time.ctime(api2.modules.time.time() + expire/1000))
            print('token has been saved here : ' +
                  api2.modules.Path.as_posix(api2.modules.Path.cwd()))
        return token

    def _checkingDate(self)->None:
        """
        Checking if the token is still valid
        """
        now = api2.modules.time.time()
        if now > self.config['date_limit']:
            self.retrieveToken()

    def getData(self, endpoint: str, params: dict = None, data: dict = None, headers: dict = None, *args, **kwargs):
        """
        Abstraction for getting data
        """
        self._checkingDate()
        if headers is None:
            headers = self.header
        if params == None and data == None:
            res = api2.modules.requests.get(
                endpoint, headers=headers)
        elif params != None and data == None:
            res = api2.modules.requests.get(
                endpoint, headers=headers, params=params)
        elif params == None and data != None:
            res = api2.modules.requests.get(
                endpoint, headers=headers, data=data)
        elif params != None and data != None:
            res = api2.modules.requests.get(endpoint, headers=headers,
                                            params=params, data=data)
        try:
            res_json = res.json()
        except:
            res_json = {'error': 'Request Error'}
            if self.retry > 0:
                for each in range(self.retry):
                    if 'error' in res_json.keys():
                        api2.modules.time.sleep(30)
                        res_json = self.getData(endpoint,params,data,headers,**kwargs)
        return res_json

    def postData(self, endpoint: str, params: dict = None, data: dict = None, headers: dict = None, * args, **kwargs):
        """
        Abstraction for posting data
        """
        self._checkingDate()
        if headers is None:
            headers = self.header
        if params == None and data == None:
            res = api2.modules.requests.post(
                endpoint, headers=headers)
        elif params != None and data == None:
            res = api2.modules.requests.post(
                endpoint, headers=headers, params=params)
        elif params == None and data != None:
            res = api2.modules.requests.post(endpoint, headers=headers,
                                             data=api2.modules.json.dumps(data))
        elif params != None and data != None:
            res = api2.modules.requests.post(endpoint, headers=headers,
                                             params=params, data=api2.modules.json.dumps(data))
        try:
            res_json = res.json()
        except:
            res_json = {'error': 'Request Error'}
        return res_json

    def patchData(self, endpoint: str, params: dict = None, data=None, headers: dict = None, *args, **kwargs):
        """
        Abstraction for deleting data
        """
        self._checkingDate()
        if headers is None:
            headers = self.header
        if params != None and data == None:
            res = api2.modules.requests.patch(
                endpoint, headers=headers, params=params)
        elif params == None and data != None:
            res = api2.modules.requests.patch(endpoint, headers=headers,
                                              data=api2.modules.json.dumps(data))
        elif params != None and data != None:
            res = api2.modules.requests.patch(endpoint, headers=headers,
                                              params=params, data=api2.modules.json.dumps(data=data))
        try:
            status_code = res.json()
        except:
            status_code = {'error': 'Request Error'}
        return status_code

    def putData(self, endpoint: str, params: dict = None, data=None, headers: dict = None, *args, **kwargs):
        """
        Abstraction for deleting data
        """
        self._checkingDate()
        if headers is None:
            headers = self.header
        if params != None and data == None:
            res = api2.modules.requests.put(
                endpoint, headers=headers, params=params)
        elif params == None and data != None:
            res = api2.modules.requests.put(endpoint, headers=headers,
                                            data=api2.modules.json.dumps(data))
        elif params != None and data != None:
            res = api2.modules.requests.put(endpoint, headers=headers,
                                            params=params, data=api2.modules.json.dumps(data=data))
        try:
            status_code = res.json()
        except:
            status_code = {'error': 'Request Error'}
        return status_code

    def deleteData(self, endpoint: str, params: dict = None, headers: dict = None, *args, **kwargs):
        """
        Abstraction for deleting data
        """
        self._checkingDate()
        if headers is None:
            headers = self.header
        if params == None:
            res = api2.modules.requests.delete(
                endpoint, headers=headers)
        elif params != None:
            res = api2.modules.requests.delete(
                endpoint, headers=headers, params=params)
        try:
            status_code = res.status_code
        except:
            status_code = {'error': 'Request Error'}
        return status_code
