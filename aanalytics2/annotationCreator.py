import json
from copy import deepcopy
from typing import Union
from datetime import datetime

class AnnotationCreator:

    def __init__(self, data:Union[str,dict]=None):
        self.__data__ = {}
        self.__data__['applyToAllReports'] = False
        self.__data__['scope'] = {'metrics': [], 'filters': []}
        self.__data__['tags'] = []
        if isinstance(data, str):
            if data.endswith('.json'):
                with open(data, 'r') as file:
                    self.__data__ = json.load(file)
        elif isinstance(data, dict):
            self.__data__ = deepcopy(data)

    def __str__(self):
        return json.dumps(self.__data__, indent=4)
    
    def __repr__(self):
        return json.dumps(self.__data__, indent=2)
    
    def to_dict(self):
        """
        Convert the annotation data to a dictionary.
        Returns:
            dict: The annotation data as a dictionary.
        """
        return deepcopy(self.__data__)


    def setName(self, name: str):
        """
        Set the name for the annotation.
        Arguments:
            name: REQUIRED : Name to be used for the annotation.
        """
        if not name:
            raise ValueError("Name cannot be empty")
        self.__data__['name'] = name
    
    def setDescription(self, description: str):
        """
        Set the description for the annotation.
        Arguments:
            description: REQUIRED : Description to be used for the annotation.
        """
        self.__data__['description'] = description
    
    def setColor(self, color: str):
        """
        Set the color for the annotation.
        Arguments:
            color: Color to be used, from "STANDARD1" to "STANDARD9"
        """
        if color not in ["STANDARD1", "STANDARD2", "STANDARD3", "STANDARD4", "STANDARD5","STANDARD6","STANDARD7","STANDARD8","STANDARD9"]:
            raise ValueError("Invalid color. Choose from STANDARD1, STANDARD2, STANDARD3, STANDARD4, STANDARD5,STANDARD6,STANDARD7,STANDARD8,STANDARD9")
        self.__data__['color'] = color

    def setReportSuiteName(self, reportSuiteName: str):
        """
        Set the report suite Name for the annotation.
        Arguments:
            reportSuiteName: REQUIRED : Report suite Name to be used.
        """
        self.__data__['reportSuiteName'] = reportSuiteName

    def setReportSuiteId(self, reportSuiteId: str):
        """
        Set the report suite ID for the annotation.
        Arguments:
            reportSuiteId: REQUIRED : Report suite ID to be used.
        """
        self.__data__['reportSuiteId'] = reportSuiteId
    
    def applyToAllReports(self, apply: bool):
        """
        Set whether the annotation applies to all reports.
        Arguments:
            apply: REQUIRED : Boolean indicating if the annotation applies to all reports.
        """
        self.__data__['applyToAllReports'] = apply

    def setDateRange(self, dateRange: str = None,start: str=None, end: str=None):
        """
        Set the date range for the annotation.
        There are two ways to set the date range:
        1. Using a direct date range in ISO format (YYYY-MM-DDT00:00:00/YYYY-MM-DDT00:00:00).
        2. Using start and end dates in ISO format (YYYY-MM-DD). The wrapper will create the date range automatically.
        if both are provided, the dateRange will be used.
        Arguments:
            dateRange: OPTIONAL : Direct date range in ISO format (YYYY-MM-DDT00:00:00/YYYY-MM-DDT00:00:00).
            start: OPTIONAL : Start date in ISO format (YYYY-MM-DD).
            end: OPTIONAL : End date in ISO format (YYYY-MM-DD).
        """
        if dateRange:
            self.__data__['dateRange'] = dateRange
        else:
            if start is None or end is None:
                raise ValueError("Either dateRange or both start and end must be provided")
            start = datetime.fromisoformat(start)
            end = datetime.fromisoformat(end)
            if start > end:
                raise ValueError("Start date cannot be after end date")
            self.__data__['dateRange'] = f"{start.isoformat()}/{end.isoformat()}"

    def addMetric(self, metricId: str):
        """
        Add a single metric to the annotation.
        Arguments:
            metricId: REQUIRED : ID of the metric to be added.
        """
        if 'scope' not in self.__data__.keys():
            self.__data__['scope'] = {'metrics': [],'filters': []}
        self.__data__['scope']['metrics'].append({"id": metricId,"componentType": "metric"})
    
    def addMetrics(self, metricIds: list):
        """
        Add multiple metrics to the annotation.
        Arguments:
            metricIds: REQUIRED : List of metric IDs to be added.
        """
        if not isinstance(metricIds, list):
            raise TypeError("metricIds must be a list")
        if 'scope' not in self.__data__.keys():
            self.__data__['scope'] = {'metrics': [],"filters": []}
        for metricId in metricIds:
            self.__data__['scope']['metrics'].append({"id": metricId,"componentType": "metric"})

    def addFilter(self, filterId: str,operator:str=None,dimensionType:str=None,terms:list=None,componentType:str=None):
        """
        Add a filter to the annotation.
        Arguments:
            filterId: ID of the filter to be added.
            operator: Optional operator for the filter.
            dimensionType: Optional dimension type for the filter.
            terms: Optional list of terms for the filter.
            componentType: Optional component type for the filter.
        """
        if 'scope' not in self.__data__.keys():
            self.__data__['scope'] = {'metrics': [],"filters": []}
        if 'filters' not in self.__data__['scope']:
            self.__data__['scope']['filters'] = []
        filter_data = {"id": filterId}
        if operator:
            filter_data['operator'] = operator
        if dimensionType:
            filter_data['dimensionType'] = dimensionType
        if terms:
            filter_data['terms'] = terms
        if componentType:
            filter_data['componentType'] = componentType
        elif filterId.startswith('s'):
            filter_data['componentType'] = 'segment'
        self.__data__['scope']['filters'].append(filter_data)
    
    def addTag(self, tagId: str,name:str=None):
        """
        Add a tag to the annotation.
        Arguments:
            tag: REQUIRED : Tag to be added.
            name: REQUIRED : name for the tag.
        """
        if tagId is None or tagId == "":
            raise ValueError("Tag ID cannot be None or empty")
        if name is None or name == "":
            raise ValueError("Tag name cannot be None or empty")
        if 'tags' not in self.__data__.keys():
            self.__data__['tags'] = []
        self.__data__['tags'].append({tagId: tagId, "name": name})

    
