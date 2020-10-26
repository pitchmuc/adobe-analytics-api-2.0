import json
import os
from pathlib import Path

from typing import Optional

from .config import config_object, header
from .paths import find_path


def create_config_file(verbose: bool = False, destination: str = 'config_analytics_template.json') -> None:
    """Creates a `config_admin.json` file with the pre-defined configuration format
    to store the access data in under the specified `destination`.
    """

    json_data = {
        'org_id': '<orgID>',
        'client_id': "<APIkey>",
        'tech_id': "<something>@techacct.adobe.com",
        'secret': "<YourSecret>",
        'pathToKey': '<path/to/your/privatekey.key>',
    }
    with open(destination, 'w') as cf:
        cf.write(json.dumps(json_data, indent=4))
    if verbose:
        print(
            f" file created at this location : {os.getcwd()}{os.sep}config_analytics.json"
        )


def createConfigFile(verbose: bool = False, destination: str = 'config_analytics_template.json') -> None:
    """Creates a `config_admin.json` file with the pre-defined configuration format
    to store the access data in under the specified `destination`.
    """

    create_config_file(verbose, destination)


def importConfigFile(path: str) -> None:
    """Reads the file denoted by the supplied `path` and retrieves the configuration information
    from it.

    Arguments:
        path: REQUIRED : path to the configuration file. Can be either a fully-qualified or relative.

    Example of path value.
    "config.json"
    "./config.json"
    "/my-folder/config.json"
    """

    import_config_file(path)


def import_config_file(path: str) -> None:
    """Reads the file denoted by the supplied `path` and retrieves the configuration information
    from it.

    Arguments:
        path: REQUIRED : path to the configuration file. Can be either a fully-qualified or relative.

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
            client_id = provided_config['api_key']
        elif 'client_id' in provided_keys:
            client_id = provided_config['client_id']
        else:
            raise RuntimeError(f"Either an `api_key` or a `client_id` should be provided.")
        configure(org_id=provided_config['org_id'],
                  tech_id=provided_config['tech_id'],
                  secret=provided_config['secret'],
                  path_to_key=provided_config['pathToKey'],
                  client_id=client_id)


def configure(org_id: str,
              tech_id: str,
              secret: str,
              path_to_key: str,
              client_id: str):
    """Performs programmatic configuration of the API using provided values."""

    if not org_id:
        raise ValueError("`org_id` must be specified in the configuration.")
    if not client_id:
        raise ValueError("`client_id` must be specified in the configuration.")
    if not tech_id:
        raise ValueError("`tech_id` must be specified in the configuration.")
    if not secret:
        raise ValueError("`secret` must be specified in the configuration.")
    if not path_to_key:
        raise ValueError("`pathToKey` must be specified in the configuration.")
    config_object["org_id"] = org_id
    config_object["client_id"] = client_id
    header["x-api-key"] = client_id
    config_object["tech_id"] = tech_id
    config_object["secret"] = secret
    config_object["pathToKey"] = path_to_key
