import gzip
import io
from concurrent import futures
from pathlib import Path
from typing import IO, Union

# Non standard libraries
import pandas as pd
import requests

from aanalytics2 import config, connector


class DIAPI:
    """
    This class provide an easy way to use the Data Insertion API.
    You can initialize it with the required information to be present in the request and then select to send POST or GET request.
    Arguments to instantiate:
        rsid : REQUIRED : Report Suite ID
        tracking_server : REQUIRED : tracking server for tracking.
        example : "xxxx.sc.omtrdc.net"
    """

    def __init__(self, rsid: str = None, tracking_server: str = None):
        """
        Arguments:
            rsid : REQUIRED : Report Suite ID
            tracking_server : REQUIRED : tracking server for tracking.
        """
        if rsid is None:
            raise Exception("Expecting a ReportSuite ID (rsid)")
        self.rsid = rsid
        if tracking_server is None:
            raise Exception("Expecting a tracking server")
        self.tracking_server = tracking_server
        try:
            import importlib.resources as pkg_resources
            path = pkg_resources.path("aanalytics2", "supported_tags.pickle")
        except ImportError:
            # Try backported to PY<37 with pkg_resources.
            try:
                import pkg_resources
                path = pkg_resources.resource_filename(
                    "aanalytics2", "supported_tags.pickle")
            except:
                print('no supported_tags file')
        try:
            with path as f:
                self.REFERENCE = pd.read_pickle(f)
        except:
            self.REFERENCE = None

    def getMethod(self, pageName: str = None, g: str = None, pe: str = None, pev1: str = None, pev2: str = None, events: str = None, **kwargs):
        """
        Use the GET method to send information to Adobe Analytics
        Arguments:
            pageName : REQUIRED : The Web page name.
            g : REQUIRED  : The Web page URL
            pe : OPTIONAL : For custom link tracking (Type of link ("d", "e", or "o"))
            if selected, require "pev1" or "pev2", additionally pageName is set to Null
            pev1 : OPTIONAL : The link's HREF. For custom links, page values are ignored.
            pev2 : OPTIONAL : Name of link.
            events : OPTIONAL : If you want to pass some events
        Possible kwargs:
            - see the SUPPORTED_TAGS attributes. Tags should be in the supported format.
        """
        if pageName is None and g is None:
            raise Exception("Expecting a pageName or g arguments")
        if pe is not None and pe not in ["d", "e", "o"]:
            raise Exception('Expecting pe argument to be ("d", "e", or "o")')
        header = {'Content-Type': 'application/json'}
        endpoint = f"https://{self.tracking_server}/b/ss/{self.rsid}/0"
        params = {"pageName": pageName, "g": g,
                  "pe": pe, "pev1": pev1, "pev2": pev2, "events": events, **kwargs}
        res = requests.get(endpoint, params=params, headers=header)
        return res

    def postMethod(self, pageName: str = None, pageURL: str = None, linkType: str = None, linkURL: str = None, linkName: str = None, events: str = None, **kwargs):
        """
        Use the POST method to send information to Adobe Analytics
        Arguments:
            pageName : REQUIRED : The Web page name.
            pageURL : REQUIRED  : The Web page URL
            linkType : OPTIONAL : For custom link tracking (Type of link ("d", "e", or "o"))
            if selected, require "pev1" or "pev2", additionally pageName is set to Null
            linkURL : OPTIONAL : The link's HREF. For custom links, page values are ignored.
            linkName : OPTIONAL : Name of link.
            events : OPTIONAL : If you want to pass some events
        Possible kwargs:
            - see the SUPPORTED_TAGS attributes. Tags should be in the supported format.
        """
        if pageName is None and pageURL is None:
            raise Exception("Expecting a pageName or pageURL argument")
        if linkType is not None and linkType not in ["d", "e", "o"]:
            raise Exception('Expecting pe argument to be ("d", "e", or "o")')
        header = {'Content-Type': 'application/xml'}
        endpoint = f"https://{self.tracking_server}/b/ss//6"
        dictionary = {"pageName": pageName, "pageURL": pageURL,
                      "linkType": linkType, "linkURL": linkURL, "linkName": linkName, "events": events, "reportSuite": self.rsid, **kwargs}
        import dicttoxml as dxml
        myxml = dxml.dicttoxml(
            dictionary, custom_root='request', attr_type=False)
        xml_data = myxml.decode()
        res = requests.post(endpoint, data=xml_data, headers=header)
        return res


class Bulkapi:
    """
    This is the bulk API from Adobe Analytics.
    By default, the file are sent to the global endpoints for auto-routing.
    If you wish to select a specific endpoint, you can modify it during instantiation.
    It requires you to upload some adobeio configuration file through the main aanalytics2 module.
    Arguments:
        endpoint : OPTIONAL : by default using https://analytics-collection.adobe.io
    """

    def __init__(self, endpoint: str = "https://analytics-collection.adobe.io", config_object: dict = config.config_object):
        """
        Initialize the Bulk API connection. Returns an object with methods to send data to Analytics.
        Arguments:
            endpoint : REQUIRED : Endpoint to send data to. Default to analytics-collection.adobe.io
                possible values, on top of the default choice are:
                    - https://analytics-collection-va7.adobe.io	(US)
                    - https://analytics-collection-nld2.adobe.io (EU)
            config_object : REQUIRED : config object containing the different information to send data.
        """
        self.endpoint = endpoint
        try:
            import importlib.resources as pkg_resources
            path = pkg_resources.path(
                "aanalytics2", "CSV_Column_and_Query_String_Reference.pickle")
        except ImportError:
            try:
                # Try backported to PY<37 `importlib_resources`.
                import pkg_resources
                path = pkg_resources.resource_filename(
                    "aanalytics2", "CSV_Column_and_Query_String_Reference.pickle")
            except:
                print('no CSV_Column_and_Query_string_Reference file')
        try:
            with path as f:
                self.REFERENCE = pd.read_pickle(f)
        except:
            self.REFERENCE = None
        # if no token has been generated.
        self.connector = connector.AdobeRequest()
        self.header = self.connector.header
        self.header["x-adobe-vgid"] = "ingestion"
        del self.header["Content-Type"]
        self._createdFiles = []

    def validation(self, file: IO = None,encoding:str='utf-8', **kwargs):
        """
        Send the file to a validation endpoint. Return the response object from requests.
        Argument:
            file : REQUIRED : File in a string of byte format.
            encoding : OPTIONAL : type of encoding used for the file.
        Possible kwargs:
            compress_level : handle the compression level, from 0 (no compression) to 9 (slow but more compressed). default 5.
        """
        compress_level = kwargs.get("compress_level", 5)
        if file is None:
            raise Exception("Expecting a file")
        path = "/aa/collect/v1/events/validate"
        if file.endswith(".gz") == False:
            with open(file, "r",encoding=encoding) as f:
                content = f.read()
            data = gzip.compress(content.encode('utf-8'),
                                 compresslevel=compress_level)
            filename = f"{file}.gz"
        elif file.endswith(".gz"):
            filename = file
            with open(file, "rb") as f:
                data = f.read()
        res = requests.post(self.endpoint + path, files={"file": (None, data)},
                            headers=self.header)
        return res

    def generateTemplate(self, includeAdv: bool = False, returnDF: bool = False, save: bool = True):
        """
        Generate a CSV file with minimum fields.
        Arguments:
            includeAdv : OPTIONAL : Include advanced fields in the csv (pe & queryString). Not included by default to avoid confusion for new users. (Default False)
            returnDF : OPTIONAL : Return a pandas dataFrame if you want to work directly with a data frame.(default False)
            save : OPTIONAL : Save the file created directly in your working folder.
        """
        ## 2 rows being created
        string = """timestamp,marketingCloudVisitorID,events,pageName,pageURL,reportSuiteID,userAgent,pe,queryString\ntimestampValuePOSIX/Epoch Time (e.g. 1486769029) or ISO-8601 (e.g. 2017-02-10T16:23:49-07:00),marketingCloudVisitorIDValue,eventsValue,pageNameValue,pageURLValue,reportSuiteIDValue,userAgentValue,peValue,queryStringValue
        """
        data = io.StringIO(string)
        df = pd.read_csv(data, sep=',')
        if includeAdv == False:
            df.drop(["pe", "queryString"], axis=1, inplace=True)
        if save:
            df.to_csv('template.csv', index=False)
        if returnDF:
            return df

    def _checkFiles(self, file: str = None,encoding:str = "utf-8"):
        """
        Internal method that check content and format of the file
        """
        if file.endswith(".gz"):
            return file
        else:  # if sending not gzipped file.
            new_folder = Path('tmp/')
            new_folder.mkdir(exist_ok=True)
            with open(file, "r",encoding=encoding) as f:
                content = f.read()
                new_path = new_folder / f"{file}.gz"
                with gzip.open(Path(new_path), 'wb') as f:
                    f.write(content.encode('utf-8'))
                # save the filename to delete
                self._createdFiles.append(new_path)
            return new_path

    def sendFiles(self, files: Union[list, IO] = None,encoding:str='utf-8',**kwargs):
        """
        Method to send the file(s) through the Bulk API. Returns a list with the different status file sent.
        Arguments:
            files : REQUIRED : file to be send to the aalytics collection server. It can be a list or the name of the file to be send.
                If list is being send, we assume that each file are to be sent in different visitor groups.
                If file are not gzipped, we will compress the file and saved it as gz in the folder.
            encoding : OPTIONAL : if encoding is different that default utf-8.
        possible kwargs:
            workers : maximum amount of worker for parallele processing. (default 4)
        """
        path = "/aa/collect/v1/events"
        if files is None:
            raise Exception("Expecting a file")
        compress_level = kwargs.get("compress_level", 5)
        files_gz = list()
        if type(files) == list:
            for file in files:
                fileName = self._checkFiles(file,encoding=encoding)
                files_gz.append(fileName)
        elif type(files) == str:
            fileName = self._checkFiles(files,encoding=encoding)
            files_gz.append(fileName)
        vgid_headers = [f"ingestion_{x}" for x in range(len(files_gz))]
        list_headers = [{**self.header, 'x-adobe-vgid': vgid}
                        for vgid in vgid_headers]
        list_urls = [self.endpoint + path for x in range(len(files_gz))]
        list_files = ({"file": (None, open(Path(file), "rb").read())}
                      for file in files_gz)  # generator for files
        workers_input = kwargs.get("workers", 4)
        workers = max(1, workers_input)
        with futures.ThreadPoolExecutor(workers) as executor:
            res = executor.map(lambda x, y, z: requests.post(
                x, headers=y, files=z), list_urls, list_headers, list_files)
            list_res = [response.json() for response in res]
        # cleaning temp folder
        if len(self._createdFiles) > 0:
            for file in self._createdFiles:
                file_path = Path(file)
                file_path.unlink()
            self._createdFiles = []
            tmp = Path('tmp/')
            tmp.rmdir()
        return list_res
