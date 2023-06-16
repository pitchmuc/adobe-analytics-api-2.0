import json
import time
from copy import deepcopy

# Non standard libraries
import requests

from aanalytics2 import config, token_provider


class AdobeRequest:
    """
    Handle request to Audience Manager and taking care that the request have a valid token set each time.
    Attributes:
        restTime : Time to rest before sending new request when reaching too many request status code.
    """
    loggingEnabled = False
    def __init__(self,
                 config_object: dict = config.config_object,
                 header: dict = config.header,
                 verbose: bool = False,
                 retry: int = 0,
                 loggingEnabled:bool=False,
                 logger:object=None
                ) -> None:
        """
        Set the connector to be used for handling request to AAM
        Arguments:
            config_object : OPTIONAL : Require the importConfig file to have been used.
            header : OPTIONAL : header of the config modules
            verbose : OPTIONAL : display comment on the request.
            retry : OPTIONAL : If you wish to retry failed GET requests
            loggingEnabled : OPTIONAL : if the logging is enable for that instance.
            logger : OPTIONAL : instance of the logger created 
        """
        if config_object['org_id'] == '':
            raise Exception(
                'You have to upload the configuration file with importConfigFile method.')
        self.config = deepcopy(config_object)
        self.header = deepcopy(header)
        self.loggingEnabled = loggingEnabled
        self.logger = logger
        self.restTime = 30
        self.retry = retry
        if self.config['token'] == '' or time.time() > self.config['date_limit']:
            if 'scopes' in self.config.keys() and self.config.get('scopes',None) is not None:
                self.connectionType = 'oauthV2'
                token_and_expiry = token_provider.get_oauth_token_and_expiry_for_config(config=self.config, verbose=verbose)
            elif self.config.get("private_key",None) is not None or self.config.get("pathToKey",None) is not None:
                self.connectionType = 'jwt'
                token_and_expiry = token_provider.get_jwt_token_and_expiry_for_config(config=self.config, verbose=verbose)
            token = token_and_expiry['token']
            expiry = token_and_expiry['expiry']
            self.token = token
            if self.loggingEnabled:
                self.logger.info("token retrieved : {token}")
            self.config['token'] = token
            self.config['date_limit'] = time.time() + expiry - 500
            self.header.update({'Authorization': f'Bearer {token}'})

    def _checkingDate(self) -> None:
        """
        Checking if the token is still valid
        """
        now = time.time()
        if now > self.config['date_limit']:
            if self.loggingEnabled:
                self.logger.warning("token expired. Trying to retrieve a new token")
            if self.connectionType =='oauthV2':
                token_and_expiry = token_provider.get_oauth_token_and_expiry_for_config(config=self.config)
            elif self.connectionType == 'jwt':
                token_and_expiry = token_provider.get_jwt_token_and_expiry_for_config(config=self.config)
            token = token_and_expiry['token']
            if self.loggingEnabled:
                self.logger.info(f"new token retrieved : {token}")
            self.config['token'] = token
            self.config['date_limit'] = time.time() + token_and_expiry['expiry'] - 500
            self.header.update({'Authorization': f'Bearer {token}'})

    def getData(self, endpoint: str, params: dict = None, data: dict = None, headers: dict = None, *args, **kwargs):
        """
        Abstraction for getting data
        """
        internRetry = kwargs.get("retry",  self.retry)
        self._checkingDate()
        if self.loggingEnabled:
            self.logger.info(f"endpoint: {endpoint}")
            self.logger.info(f"params: {params}")
        if headers is None:
            headers = self.header
        if params is None and data is None:
            res = requests.get(
                endpoint, headers=headers)
        elif params is not None and data is None:
            res = requests.get(
                endpoint, headers=headers, params=params)
        elif params is None and data is not None:
            res = requests.get(
                endpoint, headers=headers, data=data)
        elif params is not None and data is not None:
            res = requests.get(endpoint, headers=headers, params=params, data=data)
        if kwargs.get("verbose", False):
            print(f"request URL : {res.request.url}")
            print(f"statut_code : {res.status_code}")
        try:
            while str(res.status_code) == "429":
                if kwargs.get("verbose", False):
                    print(f'Too many requests: retrying in {self.restTime} seconds')
                if self.loggingEnabled:
                    self.logger.info(f"Too many requests: retrying in {self.restTime} seconds")
                time.sleep(self.restTime)
                res = requests.get(endpoint, headers=headers, params=params, data=data)
            res_json = res.json()
        except:
            ## handling 1.4
            if self.loggingEnabled:
                self.logger.warning(f"handling exception as res.json() cannot be managed")
                self.logger.warning(f"status code: {res.status_code}")
            if kwargs.get('legacy',False):
                try:
                    return json.loads(res.text)
                except:
                    if self.loggingEnabled:
                        self.logger.error(f"GET method failed: {res.status_code}, {res.text}")
                    return res.text
            else:
                if self.loggingEnabled:
                    self.logger.error(f"text: {res.text}")
            res_json = {'error': 'Request Error'}
            while internRetry > 0:
                if self.loggingEnabled:
                    self.logger.warning(f"Trying again with internal retry")
                if kwargs.get("verbose", False):
                    print('Retry parameter activated')
                    print(f'{internRetry} retry left')
                if 'error' in res_json.keys():
                    time.sleep(30)
                    res_json = self.getData(endpoint, params=params, data=data, headers=headers, retry=internRetry-1, **kwargs)
                    return res_json
        return res_json

    def postData(self, endpoint: str, params: dict = None, data: dict = None, headers: dict = None, *args, **kwargs):
        """
        Abstraction for posting data
        """
        self._checkingDate()
        if headers is None:
            headers = self.header
        if params is None and data is None:
            res = requests.post(endpoint, headers=headers)
        elif params is not None and data is None:
            res = requests.post(endpoint, headers=headers, params=params)
        elif params is None and data is not None:
            res = requests.post(endpoint, headers=headers, data=json.dumps(data))
        elif params is not None and data is not None:
            res = requests.post(endpoint, headers=headers, params=params, data=json.dumps(data))
        try:
            res_json = res.json()
            if res.status_code == 429 or res_json.get('error_code', None) == "429050":
                res_json['status_code'] = 429
        except:
            ## handling 1.4
            if kwargs.get('legacy',False):
                try:
                    return json.loads(res.text)
                except:
                    if self.loggingEnabled:
                        self.logger.error(f"POST method failed: {res.status_code}, {res.text}")
                    return res.text
            res_json = {'error': res.get('status_code','Request Error')}
        return res_json

    def patchData(self, endpoint: str, params: dict = None, data=None, headers: dict = None, *args, **kwargs):
        """
        Abstraction for patching data
        """
        self._checkingDate()
        if headers is None:
            headers = self.header
        if params is not None and data is None:
            res = requests.patch(endpoint, headers=headers, params=params)
        elif params is None and data is not None:
            res = requests.patch(endpoint, headers=headers, data=json.dumps(data))
        elif params is not None and data is not None:
            res = requests.patch(endpoint, headers=headers, params=params, data=json.dumps(data))
        try:
            while str(res.status_code) == "429":
                if kwargs.get("verbose", False):
                    print(f'Too many requests: retrying in {self.restTime} seconds')
                time.sleep(self.restTime)
                res = requests.patch(endpoint, headers=headers, params=params,data=json.dumps(data))
            res_json = res.json()
        except:
            if self.loggingEnabled:
                self.logger.error(f"PATCH method failed: {res.status_code}, {res.text}")
            res_json = {'error': res.get('status_code','Request Error')}
        return res_json

    def putData(self, endpoint: str, params: dict = None, data=None, headers: dict = None, *args, **kwargs):
        """
        Abstraction for putting data
        """
        self._checkingDate()
        if headers is None:
            headers = self.header
        if params is not None and data is None:
            res = requests.put(endpoint, headers=headers, params=params)
        elif params is None and data is not None:
            res = requests.put(endpoint, headers=headers, data=json.dumps(data))
        elif params is not None and data is not None:
            res = requests.put(endpoint, headers=headers, params=params, data=json.dumps(data=data))
        try:
            status_code = res.json()
        except:
            if self.loggingEnabled:
                self.logger.error(f"PUT method failed: {res.status_code}, {res.text}")
            status_code = {'error': res.get('status_code','Request Error')}
        return status_code

    def deleteData(self, endpoint: str, params: dict = None, headers: dict = None, *args, **kwargs):
        """
        Abstraction for deleting data
        """
        self._checkingDate()
        if headers is None:
            headers = self.header
        if params is None:
            res = requests.delete(endpoint, headers=headers)
        elif params is not None:
            res = requests.delete(endpoint, headers=headers, params=params)
        try:
            while str(res.status_code) == "429":
                if kwargs.get("verbose", False):
                    print(f'Too many requests: retrying in {self.restTime} seconds')
                time.sleep(self.restTime)
                res = requests.delete(endpoint, headers=headers, params=params)
            status_code = res.status_code
        except:
            if self.loggingEnabled:
                self.logger.error(f"DELETE method failed: {res.status_code}, {res.text}")
            status_code = {'error': 'Request Error'}
        return status_code
