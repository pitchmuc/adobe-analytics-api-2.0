import json
import os
from pathlib import Path

from typing import Optional

from .config import config_object, header
from .paths import find_path


def createConfigFile(verbose: bool = False, destination: str = 'config_analytics_template.json') -> None:
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
    config_file_path: Optional[Path] = find_path(path)
    if config_file_path is None:
        raise FileNotFoundError(
            f"Unable to find the configuration file under path `{path}`."
        )
    with open(config_file_path, 'r') as file:
        provided_config = json.load(file)
        provided_keys = provided_config.keys()
        config_object["org_id"] = provided_config['org_id']
        if 'api_key' in provided_keys:
            config_object["client_id"] = provided_config['api_key']
            header["x-api-key"] = provided_config['api_key']
        elif 'client_id' in provided_keys:
            config_object["client_id"] = provided_config['client_id']
            header["x-api-key"] = provided_config['client_id']
        config_object["tech_id"] = provided_config['tech_id']
        config_object["secret"] = provided_config['secret']
        config_object["pathToKey"] = provided_config['pathToKey']
