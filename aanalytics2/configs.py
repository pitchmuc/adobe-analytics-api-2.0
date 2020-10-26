from typing import Optional

from aanalytics2 import modules, find_path, config


def createConfigFile(verbose: object = False) -> None:
    """Creates a `config_admin.json` file with the pre-defined configuration format to store
    the access data in.
    """
    json_data = {
        'org_id': '<orgID>',
        'client_id': "<APIkey>",
        'tech_id': "<something>@techacct.adobe.com",
        'secret': "<YourSecret>",
        'pathToKey': '<path/to/your/privatekey.key>',
    }
    with open('config_analytics_template.json', 'w') as cf:
        cf.write(modules.json.dumps(json_data, indent=4))
    if verbose:
        print(
            f" file created at this location : {modules.os.getcwd()}{modules.os.sep}config_analytics.json")


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
    config_file_path: Optional[modules.Path] = find_path(path)
    if config_file_path is None:
        raise FileNotFoundError(
            f"Unable to find the configuration file under path `{path}`.")
    with open(config_file_path, 'r') as file:
        f = modules.json.load(file)
        config.config_object["org_id"] = f['org_id']
        if 'api_key' in f.keys():
            config.config_object["client_id"] = f['api_key']
            config.header["x-api-key"] = f['api_key']
        elif 'client_id' in f.keys():
            config.config_object["client_id"] = f['client_id']
            config.header["x-api-key"] = f['client_id']
        config.config_object["tech_id"] = f['tech_id']
        config.config_object["secret"] = f['secret']
        config.config_object["pathToKey"] = f['pathToKey']
