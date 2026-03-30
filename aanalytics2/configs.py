import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Optional
import time

# Non standard libraries
from .config import config_object, header


class ConfigObj:
    """
    Isolated configuration object returned by importConfigFile / configure when
    ``return_object=True``. Each instance owns its own independent copies of
    the config dict and header dict so multiple instances never share memory.

    Usage with Login (** unpacking matches Login's ``config`` + ``header`` parameters)::

        cfg = importConfigFile("creds.json", return_object=True)
        login = Login(**cfg)
        analytics = login.createAnalyticsConnection(companyId="my_company")

    Usage directly with Analytics (``config_object`` is a property alias for ``config``)::

        cfg = importConfigFile("creds.json", return_object=True)
        analytics = Analytics(company_id="my_company",
                              config_object=cfg.config_object,
                              header=cfg.header)

    Multiple credentials in parallel::

        cfg1 = importConfigFile("creds1.json", return_object=True)
        cfg2 = importConfigFile("creds2.json", return_object=True)
        login1, login2 = Login(**cfg1), Login(**cfg2)
        a1 = login1.createAnalyticsConnection("company_A")
        a2 = login2.createAnalyticsConnection("company_B")
    """

    def __init__(self, config: dict, header: dict) -> None:
        self.config = deepcopy(config)
        self.header = deepcopy(header)

    @property
    def config_object(self) -> dict:
        """Alias for ``config``; matches the ``config_object`` parameter name of Analytics.__init__."""
        return self.config

    # Support ** unpacking — matches Login.__init__(config, header)
    def keys(self):
        return ("config", "header")

    def __getitem__(self, key: str):
        return getattr(self, key)

    def __repr__(self) -> str:
        return f"ConfigObj(org_id={self.config.get('org_id')!r}, client_id={self.config.get('client_id')!r})"


def find_path(path: str) -> Optional[Path]:
    """Checks if the file denoted by the specified `path` exists and returns the Path object
    for the file.

    If the file under the `path` does not exist and the path denotes an absolute path, tries
    to find the file by converting the absolute path to a relative path.

    If the file does not exist with either the absolute and the relative path, returns `None`.
    """
    if Path(path).exists():
        return Path(path)
    elif path.startswith('/') and Path('.' + path).exists():
        return Path('.' + path)
    elif path.startswith('\\') and Path('.' + path).exists():
        return Path('.' + path)
    else:
        return None
   

def createConfigFile(destination: str = 'config_analytics_template.json',auth_type: str = "oauthV2",verbose: bool = False) -> None:
    """Creates a `config_admin.json` file with the pre-defined configuration format
    to store the access data in under the specified `destination`.
    Arguments:
        destination : OPTIONAL : the name of the file + path if you want
        auth_type : OPTIONAL : The type of Oauth type you want to use for your config file. Possible value: "jwt" or "oauthV2"
    """
    json_data = {
        'org_id': '<orgID>',
        'client_id': "<APIkey>",
        'secret': "<YourSecret>",
    }
    if auth_type == 'oauthV2':
        json_data['scopes'] = "<scopes>"
    elif auth_type == 'jwt':
        json_data["tech_id"] = "<something>@techacct.adobe.com"
        json_data["pathToKey"] = "<path/to/your/privatekey.key>"
    if '.json' not in destination:
        destination += '.json'
    with open(destination, 'w') as cf:
        cf.write(json.dumps(json_data, indent=4))
    if verbose:
        print(f" file created at this location : {os.getcwd()}{os.sep}{destination}.json")

def importConfigFile(path: str = None, auth_type: str = None, return_object: bool = False) -> Optional["ConfigObj"]:
    """Reads the file denoted by the supplied `path` and retrieves the configuration information
    from it.

    Arguments:
        path: REQUIRED : path to the configuration file. Can be either a fully-qualified or relative.
        auth_type : OPTIONAL : The type of Auth to be used by default. Detected if none is passed, OauthV2 takes precedence.
                        Possible values: "jwt" or "oauthV2"
        return_object : OPTIONAL : If True, returns an isolated config bundle dict with 'config' and 'header'
                        keys that can be passed directly to Login or Analytics via **bundle.
                        Does NOT update the global config state, enabling multiple credentials to coexist.
                        Default False (updates global state, returns None — backward-compatible behaviour).
    Example of path value.
    "config.json"
    "./config.json"
    "/my-folder/config.json"
    """

    config_file_path: Optional[Path] = find_path(path)
    if config_file_path is None:
        raise FileNotFoundError(
            f"Unable to find the configuration file under path `{path}`."
        )
    with open(config_file_path, 'r') as file:
        provided_config = json.load(file)
        provided_keys = provided_config.keys()
        if 'api_key' in provided_keys:
            ## old naming for client_id
            client_id = provided_config['api_key']
        elif 'client_id' in provided_keys:
            client_id = provided_config['client_id']
        else:
            raise RuntimeError(f"Either an `api_key` or a `client_id` should be provided.")
        if auth_type is None:
            if 'scopes' in provided_keys:
                auth_type = 'oauthV2'
            elif 'tech_id' in provided_keys and "pathToKey" in provided_keys:
                auth_type = 'jwt'
        args = {
            "org_id" : provided_config['org_id'],
            "secret" : provided_config['secret'],
            "client_id" : client_id
        }
        if auth_type == 'oauthV2':
            args["scopes"] = provided_config["scopes"].replace(' ','')
        if auth_type == 'jwt':
            args["tech_id"] = provided_config["tech_id"]
            args["path_to_key"] = provided_config["pathToKey"]
        return configure(**args, return_object=return_object)



def configure(org_id: str = None,
              tech_id: str = None,
              secret: str = None,
              client_id: str = None,
              path_to_key: str = None,
              private_key: str = None,
              oauth: bool = False,
              token: str = None,
              scopes: str = None,
              return_object: bool = False
              ) -> Optional["ConfigObj"]:
    """Performs programmatic configuration of the API using provided values.
    Arguments:
        org_id : REQUIRED : Organization ID
        tech_id : REQUIRED : Technical Account ID
        secret : REQUIRED : secret generated for your connection
        client_id : REQUIRED : The client_id (old api_key) provided by the JWT connection. 
        path_to_key : REQUIRED : If you have a file containing your private key value.
        private_key : REQUIRED : If you do not use a file but pass a variable directly.
        oauth : OPTIONAL : If you wish to pass the token generated by oauth
        token : OPTIONAL : If oauth set to True, you need to pass the token
        scopes : OPTIONAL : If you use Oauth, you need to pass the scopes
        return_object : OPTIONAL : If True, returns an isolated config bundle dict with 'config' and 'header'
                        keys that can be passed directly to Login or Analytics via **bundle.
                        Does NOT update the global config state, enabling multiple credentials to coexist.
                        Default False (updates global state, returns None — backward-compatible behaviour).
    """
    if not org_id:
        raise ValueError("`org_id` must be specified in the configuration.")
    if not client_id:
        raise ValueError("`client_id` must be specified in the configuration.")
    if not tech_id and oauth == False and not scopes:
        raise ValueError("`tech_id` must be specified in the configuration.")
    if not secret and oauth == False:
        raise ValueError("`secret` must be specified in the configuration.")
    if (not path_to_key and not private_key and oauth == False) and not scopes:
        raise ValueError("scopes must be specified if Oauth setup.\n `pathToKey` or `private_key` must be specified in the configuration if JWT setup.")
    if return_object:
        local_config = {
            "org_id": org_id,
            "client_id": client_id,
            "tech_id": tech_id,
            "pathToKey": path_to_key,
            "secret": secret,
            "scopes": scopes,
            "private_key": private_key,
            "date_limit": 0,
            "token": "",
            "jwtTokenEndpoint": "https://ims-na1.adobelogin.com/ims/exchange/jwt",
            "oauthTokenEndpointV2": "https://ims-na1.adobelogin.com/ims/token/v3",
        }
        local_header = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": "Bearer ",
            "x-api-key": client_id,
        }
        if oauth:
            date_limit = int(time.time()) + (22 * 60 * 60)
            local_config["date_limit"] = date_limit
            local_config["token"] = token
            local_header["Authorization"] = f"Bearer {token}"
        return ConfigObj(config=local_config, header=local_header)
    config_object["org_id"] = org_id
    config_object["client_id"] = client_id
    header["x-api-key"] = client_id
    config_object["tech_id"] = tech_id
    config_object["secret"] = secret
    config_object["pathToKey"] = path_to_key
    config_object["private_key"] = private_key
    config_object["scopes"] = scopes
    # ensure the reset of the state by overwriting possible values from previous import.
    config_object["date_limit"] = 0
    config_object["token"] = ""
    if oauth:
        date_limit = int(time.time()) + (22 * 60 * 60)
        config_object["date_limit"] = date_limit
        config_object["token"] = token
        header["Authorization"] = f"Bearer {token}"

def get_private_key_from_config(config: dict) -> str:
    """
    Returns the private key directly or read a file to return the private key.
    """
    private_key = config.get('private_key')
    if private_key is not None:
        return private_key
    private_key_path = find_path(config['pathToKey'])
    if private_key_path is None:
        raise FileNotFoundError(f'Unable to find the private key under path `{config["pathToKey"]}`.')
    with open(Path(private_key_path), 'r') as f:
        private_key = f.read()
    return private_key

def generateLoggingObject(
        level:str="WARNING",
        stream:bool=True,
        file:bool=False,
        filename:str="aanalytics2.log",
        format:str="%(asctime)s::%(name)s::%(funcName)s::%(levelname)s::%(message)s::%(lineno)d"
        )->dict:
    """
    Generates a dictionary for the logging object with basic configuration.
    You can find the information for the different possible values on the logging documentation.
        https://docs.python.org/3/library/logging.html
    Arguments:
        level : Level of the logger to display information (NOTSET, DEBUG,INFO,WARNING,EROR,CRITICAL)
        stream : If the logger should display print statements
        file : If the logger should write the messages to a file
        filename : name of the file where log are written
        format : format of the log to be written.
    """
    myObject = {
        "level" : level,
        "stream" : stream,
        "file" : file,
        "format" : format,
        "filename":filename
    }
    return myObject