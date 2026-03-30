import json
import time
from copy import deepcopy

# Non standard libraries
import requests
import io
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from aanalytics2 import config, token_provider


class AdobeRequest:
    """
    Handle requests to the Adobe Analytics API, ensuring a valid OAuth v2 token
    is present on every call.

    Uses a requests.Session backed by an HTTPAdapter with automatic retry logic
    (exponential back-off) for 429 and common 5xx transient errors.
    """

    loggingEnabled = False

    def __init__(self,
                 config_object: dict = config.config_object,
                 header: dict = config.header,
                 verbose: bool = False,
                 retry: int = 0,
                 loggingEnabled: bool = False,
                 logger: object = None,
                 company_id: str = None
                 ) -> None:
        """
        Set the connector to be used for handling requests to Adobe Analytics.
        Arguments:
            config_object : OPTIONAL : Require the importConfig file to have been used.
            header        : OPTIONAL : header dict from the config module.
            verbose       : OPTIONAL : print request details.
            retry         : OPTIONAL : minimum number of retries (floor is 3).
            loggingEnabled: OPTIONAL : enable logging for this instance.
            logger        : OPTIONAL : logger instance.
            company_id    : OPTIONAL : global company id header value.
        """
        if config_object['org_id'] == '':
            raise Exception(
                'You have to upload the configuration file with importConfigFile method.')
        self.config = deepcopy(config_object)
        self.header = deepcopy(header)
        self.loggingEnabled = loggingEnabled
        self.logger = logger
        self.retry = retry

        if self.config['token'] == '' or time.time() > self.config['date_limit']:
            token_and_expiry = token_provider.get_oauth_token_and_expiry_for_config(
                config=self.config, verbose=verbose)
            token = token_and_expiry['token']
            expiry = token_and_expiry['expiry']
            self.token = token
            if self.loggingEnabled:
                self.logger.info(f"token retrieved : {self.token}")
            self.config['token'] = token
            self.config['date_limit'] = time.time() + expiry - 500
            self.header.update({'Authorization': f'Bearer {token}'})
            self.header.update({'x-proxy-global-company-id': company_id})
            if self.loggingEnabled:
                self.logger.info("OAuth v2 token retrieved")

        self.session = self._build_session(retry)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_session(self, max_retries: int) -> requests.Session:
        """
        Build a requests.Session with an HTTPAdapter configured for retrying
        on 429 and common 5xx server errors with exponential back-off.

        The adapter honours the ``Retry-After`` response header so the wait
        time advertised by the server is respected automatically.
        """
        session = requests.Session()
        retry_strategy = Retry(
            total=max(max_retries, 3),
            status_forcelist=[429, 500, 502, 503, 504],
            # Include POST and PATCH so retries apply to all HTTP methods used here
            allowed_methods={"DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT", "TRACE"},
            backoff_factor=1,               # waits 0 s, 2 s, 4 s, 8 s … between attempts
            respect_retry_after_header=True,  # honour Retry-After on 429
            raise_on_status=False,          # return the last response instead of raising
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        session.headers.update(self.header)
        return session

    def _checkingDate(self) -> None:
        """
        Verify the OAuth v2 token is still valid; refresh it if it has expired.
        Also syncs the updated Authorization header into the active session.
        """
        if time.time() > self.config['date_limit']:
            if self.loggingEnabled:
                self.logger.warning("OAuth v2 token expired — retrieving a new one")
            token_and_expiry = token_provider.get_oauth_token_and_expiry_for_config(
                config=self.config)
            token = token_and_expiry['token']
            self.config['token'] = token
            self.token = token
            self.config['date_limit'] = time.time() + token_and_expiry['expiry'] - 500
            updated_auth = {'Authorization': f'Bearer {token}'}
            self.header.update(updated_auth)
            self.session.headers.update(updated_auth)
            if self.loggingEnabled:
                self.logger.info("New OAuth v2 token applied")

    # ------------------------------------------------------------------
    # HTTP verb abstractions
    # ------------------------------------------------------------------

    def getData(self, endpoint: str, params: dict = None, data: dict = None, headers: dict = None, *args, **kwargs):
        """
        Abstraction for GET requests.
        """
        self._checkingDate()
        if self.loggingEnabled:
            self.logger.info(f"GET endpoint: {endpoint}")
            self.logger.info(f"params: {params}")
        request_headers = headers if headers is not None else self.header
        res = self.session.get(endpoint, headers=request_headers, params=params, data=data)
        if kwargs.get("verbose", False):
            print(f"request URL : {res.request.url}")
            print(f"status_code : {res.status_code}")
        try:
            res_json = res.json()
        except Exception:
            if self.loggingEnabled:
                self.logger.warning("res.json() could not be parsed")
                self.logger.warning(f"status code: {res.status_code}")
            if kwargs.get('classFile'):  # reading newline-delimited JSON classification files
                text = res.text
                result = []
                for line in io.StringIO(text).readlines():
                    result.append(json.loads(line.strip()))
                return result
            elif kwargs.get('legacy', False):  # handling Analytics 1.4
                try:
                    return json.loads(res.text)
                except Exception:
                    if self.loggingEnabled:
                        self.logger.error(f"GET method failed: {res.status_code}, {res.text}")
                    return res.text
            else:
                if self.loggingEnabled:
                    self.logger.error(f"GET response text: {res.text}")
            res_json = {'error': 'Request Error'}
        return res_json

    def postData(self, endpoint: str, params: dict = None, data: dict = None, headers: dict = None, files: dict = None, *args, **kwargs):
        """
        Abstraction for POST requests.
        """
        self._checkingDate()
        if params is None:
            params = {}
        request_headers = headers if headers is not None else self.header
        if data is None and files is None:
            res = self.session.post(endpoint, headers=request_headers, params=params)
        elif data is not None and files is None:
            res = self.session.post(endpoint, headers=request_headers, data=json.dumps(data), params=params)
        elif data is None and files is not None:
            res = self.session.post(endpoint, headers=request_headers, params=params, files=files)
        else:
            res = self.session.post(endpoint, headers=request_headers, params=params, data=json.dumps(data), files=files)
        try:
            res_json = res.json()
            if res.status_code == 429 or res_json.get('error_code') == "429050":
                res_json['status_code'] = 429
        except Exception:
            if kwargs.get('legacy', False):  # handling Analytics 1.4
                try:
                    return json.loads(res.text)
                except Exception:
                    if self.loggingEnabled:
                        self.logger.error(f"POST method failed: {res.status_code}, {res.text}")
                    return res.text
            res_json = {'error': 'Request Error'}
        return res_json

    def patchData(self, endpoint: str, params: dict = None, data: dict = None, headers: dict = None, files: dict = None, *args, **kwargs):
        """
        Abstraction for PATCH requests.
        """
        self._checkingDate()
        request_headers = headers if headers is not None else self.header
        if params is not None and data is None and files is None:
            res = self.session.patch(endpoint, headers=request_headers, params=params)
        elif params is None and data is not None and files is None:
            res = self.session.patch(endpoint, headers=request_headers, data=json.dumps(data))
        elif params is not None and data is not None and files is None:
            res = self.session.patch(endpoint, headers=request_headers, params=params, data=json.dumps(data))
        else:
            res = self.session.patch(endpoint, headers=request_headers, params=params, files=files)
        try:
            res_json = res.json()
        except Exception:
            if self.loggingEnabled:
                self.logger.error(f"PATCH method failed: {res.status_code}, {res.text}")
            res_json = {'error': 'Request Error'}
        return res_json

    def putData(self, endpoint: str, params: dict = None, data=None, headers: dict = None, files: dict = None, *args, **kwargs):
        """
        Abstraction for PUT requests.
        """
        self._checkingDate()
        request_headers = headers if headers is not None else self.header
        if params is not None and data is None and files is None:
            res = self.session.put(endpoint, headers=request_headers, params=params)
        elif params is None and data is not None and files is None:
            res = self.session.put(endpoint, headers=request_headers, data=json.dumps(data))
        elif params is not None and data is not None and files is None:
            res = self.session.put(endpoint, headers=request_headers, params=params, data=json.dumps(data))
        else:
            res = self.session.put(endpoint, headers=request_headers, params=params, files=files)
        try:
            status_code = res.json()
        except Exception:
            if self.loggingEnabled:
                self.logger.error(f"PUT method failed: {res.status_code}, {res.text}")
            status_code = {'error': 'Request Error'}
        return status_code

    def deleteData(self, endpoint: str, params: dict = None, headers: dict = None, *args, **kwargs):
        """
        Abstraction for DELETE requests.
        """
        self._checkingDate()
        request_headers = headers if headers is not None else self.header
        if params is None:
            res = self.session.delete(endpoint, headers=request_headers)
        else:
            res = self.session.delete(endpoint, headers=request_headers, params=params)
        try:
            status_code = res.status_code
        except Exception:
            if self.loggingEnabled:
                self.logger.error(f"DELETE method failed: {res.status_code}, {res.text}")
            status_code = {'error': 'Request Error'}
        return status_code
