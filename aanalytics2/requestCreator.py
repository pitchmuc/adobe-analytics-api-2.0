from copy import deepcopy
import datetime
import json
from time import time


class RequestCreator:
    """
    A class to help build a request for Adobe Analytics API 2.0 getReport
    """

    template = {
        "globalFilters": [],
        "metricContainer": {
            "metrics": [],
            "metricFilters": [],
        },
        "settings": {
            "countRepeatInstances": True,
            "limit": 20000,
            "page": 0,
            "nonesBehavior": "exclude-nones",
        },
        "statistics": {"functions": ["col-max", "col-min"]},
        "rsid": "",
    }

    def __init__(self, request: dict = None) -> None:
        """
        Instanciate the constructor.
        Arguments:
            request : OPTIONAL : overwrite the template with the definition provided.
        """
        if request is not None:
            if '.json' in request and type(request) == str:
                with open(request,'r') as f:
                    request = json.load(f)
        self.__request = deepcopy(request) or deepcopy(self.template)
        self.__metricCount = len(self.__request["metricContainer"]["metrics"])
        self.__metricFilterCount = len(
            self.__request["metricContainer"].get("metricFilters", [])
        )
        self.__globalFiltersCount = len(self.__request["globalFilters"])
        ### Preparing some time statement.
        today = datetime.datetime.now()
        today_date_iso = today.isoformat().split("T")[0]
        ## should give '20XX-XX-XX'
        tomorrow_date_iso = (
            (today + datetime.timedelta(days=1)).isoformat().split("T")[0]
        )
        time_start = "T00:00:00.000"
        time_end = "T23:59:59.999"
        startToday_iso = today_date_iso + time_start
        endToday_iso = today_date_iso + time_end
        startMonth_iso = f"{today_date_iso[:-2]}01{time_start}"
        tomorrow_iso = tomorrow_date_iso + time_start
        next_month = today.replace(day=28) + datetime.timedelta(days=4)
        last_day_month = next_month - datetime.timedelta(days=next_month.day)
        last_day_month_date_iso = last_day_month.isoformat().split("T")[0]
        last_day_month_iso = last_day_month_date_iso + time_end
        thirty_days_prior_date_iso = (
            (today - datetime.timedelta(days=30)).isoformat().split("T")[0]
        )
        thirty_days_prior_iso = thirty_days_prior_date_iso + time_start
        seven_days_prior_iso_date = (
            (today - datetime.timedelta(days=7)).isoformat().split("T")[0]
        )
        seven_days_prior_iso = seven_days_prior_iso_date + time_start
        ### assigning predefined dates:
        self.dates = {
            "thisMonth": f"{startMonth_iso}/{last_day_month_iso}",
            "untilToday": f"{startMonth_iso}/{startToday_iso}",
            "todayIncluded": f"{startMonth_iso}/{endToday_iso}",
            "last30daysTillToday": f"{thirty_days_prior_iso}/{startToday_iso}",
            "last30daysTodayIncluded": f"{thirty_days_prior_iso}/{tomorrow_iso}",
            "last7daysTillToday": f"{seven_days_prior_iso}/{startToday_iso}",
            "last7daysTodayIncluded": f"{seven_days_prior_iso}/{endToday_iso}",
        }
        self.today = today

    def __repr__(self):
        return json.dumps(self.__request, indent=4)

    def __str__(self):
        return json.dumps(self.__request, indent=4)

    def addMetric(self, metricId: str = None) -> None:
        """
        Add a metric to the template.
        Arguments:
            metricId : REQUIRED : The metric to add
        """
        if metricId is None:
            raise ValueError("Require a metric ID")
        columnId = self.__metricCount
        addMetric = {"columnId": str(columnId), "id": metricId}
        if columnId == 0:
            addMetric["sort"] = "desc"
        self.__request["metricContainer"]["metrics"].append(addMetric)
        self.__metricCount += 1
    
    def removeMetrics(self) -> None:
        """
        Remove all metrics.
        """
        self.__request["metricContainer"]["metrics"] = []
        self.__metricCount = 0
    
    def getMetrics(self) -> list:
        """
        return a list of the metrics used
        """
        return [metric["id"] for metric in self.__request["metricContainer"]["metrics"]]
    
    def setSearch(self,clause:str=None)->None:
        """
        Add a search clause in the Analytics request.
        Arguments:
            clause : REQUIRED : String to tell what search clause to add.
                Examples: 
                "( CONTAINS 'unspecified' ) OR ( CONTAINS 'none' ) OR ( CONTAINS '' )"
                "( MATCH 'undefined' )"
                "( NOT CONTAINS 'undefined' )"
                "( BEGINS-WITH 'undefined' )"
                "( BEGINS-WITH 'undefined' ) AND ( BEGINS-WITH 'none' )"
        """
        if clause is None:
            raise ValueError("Require a clause to add to the request")
        self.__request["search"] = {
            "clause" : clause
        }


    def removeSearch(self)->None:
        """
        Remove the search associated with the request.
        """
        del self.__request["search"]

    def addMetricFilter(
        self, metricId: str = None, filterId: str = None, metricIndex: int = None
    ) -> None:
        """
        Add a filter to a metric.
        Arguments:
            metricId : REQUIRED : metric where the filter is added
            filterId : REQUIRED : The filter to add.
                when breakdown, use the following format for the value "dimension:::itemId"
            metricIndex : OPTIONAL : If used, set the filter to the metric located on that index.
        """
        if metricId is None:
            raise ValueError("Require a metric ID")
        if filterId is None:
            raise ValueError("Require a filter ID")
        filterIdCount = self.__metricFilterCount
        if filterId.startswith("s") and "@AdobeOrg" in filterId:
            filterType = "segment"
            filter = {
                "id": str(filterIdCount),
                "type": filterType,
                "segmentId": filterId,
            }
        elif filterId.startswith("20") and "/20" in filterId:
            filterType = "dateRange"
            filter = {
                "id": str(filterIdCount),
                "type": filterType,
                "dateRange": filterId,
            }
        elif ":::" in filterId:
            filterType = "breakdown"
            dimension, itemId = filterId.split(":::")
            filter = {
                "id": str(filterIdCount),
                "type": filterType,
                "dimension": dimension,
                "itemId": itemId,
            }
        else:  ### case when it is predefined segments like "All_Visits"
            filterType = "segment"
            filter = {
                "id": str(filterIdCount),
                "type": filterType,
                "segmentId": filterId,
            }
        if filterIdCount == 0:
            self.__request["metricContainer"]["metricFilters"] = [filter]
        else:
            self.__request["metricContainer"]["metricFilters"].append(filter)
        ### adding filter to the metric
        if metricIndex is None:
            for metric in self.__request["metricContainer"]["metrics"]:
                if metric["id"] == metricId:
                    if "filters" in metric.keys():
                        metric["filters"].append(str(filterIdCount))
                    else:
                        metric["filters"] = [str(filterIdCount)]
        else:
            metric = self.__request["metricContainer"]["metrics"][metricIndex]
            if "filters" in metric.keys():
                metric["filters"].append(str(filterIdCount))
            else:
                metric["filters"] = [str(filterIdCount)]
        ### incrementing the filter counter
        self.__metricFilterCount += 1

    def removeMetricFilter(self, filterId: str = None) -> None:
        """
        remove a filter from a metric
        Arguments:
            filterId : REQUIRED : The filter to add.
                when breakdown, use the following format for the value "dimension:::itemId"
        """
        found = False  ## flag
        if filterId is None:
            raise ValueError("Require a filter ID")
        if ":::" in filterId:
            filterId = filterId.split(":::")[1]
        list_index = []
        for metricFilter in self.__request["metricContainer"]["metricFilters"]:
            if filterId in str(metricFilter):
                list_index.append(metricFilter["id"])
                found = True
        ## decrementing the filter counter
        if found:
            for metricFilterId in reversed(list_index):
                del self.__request["metricContainer"]["metricFilters"][
                    int(metricFilterId)
                ]
                for metric in self.__request["metricContainer"]["metrics"]:
                    if metricFilterId in metric.get("filters", []):
                        metric["filters"].remove(metricFilterId)
                self.__metricFilterCount -= 1

    def setLimit(self, limit: int = 100) -> None:
        """
        Specific the number of element to retrieve. Default is 10.
        Arguments:
            limit : OPTIONAL : number of elements to return
        """
        self.__request["settings"]["limit"] = limit

    def setRepeatInstance(self, repeat: bool = True) -> None:
        """
        Specify if repeated instances should be counted.
        Arguments:
            repeat : OPTIONAL : True or False (True by default)
        """
        self.__request["settings"]["countRepeatInstances"] = repeat

    def setNoneBehavior(self, returnNones: bool = True) -> None:
        """
        Set the behavior of the None values in that request.
        Arguments:
            returnNones : OPTIONAL : True or False (True by default)
        """
        if returnNones:
            self.__request["settings"]["nonesBehavior"] = "return-nones"
        else:
            self.__request["settings"]["nonesBehavior"] = "exclude-nones"

    def setDimension(self, dimension: str = None) -> None:
        """
        Set the dimension to be used for reporting.
        Arguments:
            dimension : REQUIRED : the dimension to build your report on
        """
        if dimension is None:
            raise ValueError("A dimension must be passed")
        self.__request["dimension"] = dimension

    def setRSID(self, rsid: str = None) -> None:
        """
        Set the reportSuite ID to be used for the reporting.
        Arguments:
            rsid : REQUIRED : The Data View ID to be passed.
        """
        if rsid is None:
            raise ValueError("A reportSuite ID must be passed")
        self.__request["rsid"] = rsid

    def addGlobalFilter(self, filterId: str = None) -> None:
        """
        Add a global filter to the report.
        NOTE : You need to have a dateRange filter at least in the global report.
        Arguments:
            filterId : REQUIRED : The filter to add to the global filter.
                example :
                "s2120430124uf03102jd8021" -> segment
                "2020-01-01T00:00:00.000/2020-02-01T00:00:00.000" -> dateRange
        """
        if filterId.startswith("s") and "@AdobeOrg" in filterId:
            filterType = "segment"
            filter = {
                "type": filterType,
                "segmentId": filterId,
            }
        elif filterId.startswith("20") and "/20" in filterId:
            filterType = "dateRange"
            filter = {
                "type": filterType,
                "dateRange": filterId,
            }
        elif ":::" in filterId:
            filterType = "breakdown"
            dimension, itemId = filterId.split(":::")
            filter = {
                "type": filterType,
                "dimension": dimension,
                "itemId": itemId,
            }
        else:  ### case when it is predefined segments like "All_Visits"
            filterType = "segment"
            filter = {
                "type": filterType,
                "segmentId": filterId,
            }
        ### incrementing the count for globalFilter
        self.__globalFiltersCount += 1
        ### adding to the globalFilter list
        self.__request["globalFilters"].append(filter)

    def updateDateRange(
        self,
        dateRange: str = None,
        shiftingDays: int = None,
        shiftingDaysEnd: int = None,
        shiftingDaysStart: int = None,
    ) -> None:
        """
        Update the dateRange filter on the globalFilter list
        One of the 3 elements specified below is required.
        Arguments:
            dateRange : OPTIONAL : string representing the new dateRange string, such as: 2020-01-01T00:00:00.000/2020-02-01T00:00:00.000
            shiftingDays : OPTIONAL : An integer, if you want to add or remove days from the current dateRange provided. Apply to end and beginning of dateRange.
                So 2020-01-01T00:00:00.000/2020-02-01T00:00:00.000 with +2 will give 2020-01-03T00:00:00.000/2020-02-03T00:00:00.000
            shiftingDaysEnd : : OPTIONAL : An integer, if you want to add or remove days from the last part of the current dateRange. Apply only to end of the dateRange.
                So 2020-01-01T00:00:00.000/2020-02-01T00:00:00.000 with +2 will give 2020-01-01T00:00:00.000/2020-02-03T00:00:00.000
            shiftingDaysStart : OPTIONAL : An integer, if you want to add or remove days from the last first part of the current dateRange. Apply only to beginning of the dateRange.
                So 2020-01-01T00:00:00.000/2020-02-01T00:00:00.000 with +2 will give 2020-01-03T00:00:00.000/2020-02-01T00:00:00.000
        """
        pos = -1
        for index, filter in enumerate(self.__request["globalFilters"]):
            if filter["type"] == "dateRange":
                pos = index
                curDateRange = filter["dateRange"]
                start, end = curDateRange.split("/")
                start = datetime.datetime.fromisoformat(start)
                end = datetime.datetime.fromisoformat(end)
        if dateRange is not None and type(dateRange) == str:
            for index, filter in enumerate(self.__request["globalFilters"]):
                if filter["type"] == "dateRange":
                    pos = index
                    curDateRange = filter["dateRange"]
            newDef = {
                "type": "dateRange",
                "dateRange": dateRange,
            }
        if shiftingDays is not None and type(shiftingDays) == int:
            newStart = (start + datetime.timedelta(shiftingDays)).isoformat(
                timespec="milliseconds"
            )
            newEnd = (end + datetime.timedelta(shiftingDays)).isoformat(
                timespec="milliseconds"
            )
            newDef = {
                "type": "dateRange",
                "dateRange": f"{newStart}/{newEnd}",
            }
        elif shiftingDaysEnd is not None and type(shiftingDaysEnd) == int:
            newEnd = (end + datetime.timedelta(shiftingDaysEnd)).isoformat(
                timespec="milliseconds"
            )
            newDef = {
                "type": "dateRange",
                "dateRange": f"{start}/{newEnd}",
            }
        elif shiftingDaysStart is not None and type(shiftingDaysStart) == int:
            newStart = (start + datetime.timedelta(shiftingDaysStart)).isoformat(
                timespec="milliseconds"
            )
            newDef = {
                "type": "dateRange",
                "dateRange": f"{newStart}/{end}",
            }
        if pos > -1:
            self.__request["globalFilters"][pos] = newDef
        else:  ## in case there is no dateRange already
            self.__request["globalFilters"][pos].append(newDef)

    def removeGlobalFilter(self, index: int = None, filterId: str = None) -> None:
        """
        Remove a specific filter from the globalFilter list.
        You can use either the index of the list or the specific Id of the filter used.
        Arguments:
            index : REQUIRED : index in the list return
            filterId : REQUIRED : the id of the filter to be removed (ex: filterId, dateRange)
        """
        pos = -1
        if index is not None:
            del self.__request["globalFilters"][index]
        elif filterId is not None:
            for index, filter in enumerate(self.__request["globalFilters"]):
                if filterId in str(filter):
                    pos = index
            if pos > -1:
                del self.__request["globalFilters"][pos]
                ### decrementing the count for globalFilter
                self.__globalFiltersCount -= 1

    def to_dict(self) -> None:
        """
        Return the request definition
        """
        return deepcopy(self.__request)

    def save(self, fileName: str = None) -> None:
        """
        save the request definition in a JSON file.
        Argument:
            filename : OPTIONAL : Name of the file. (default cjapy_request_<timestamp>.json)
        """
        fileName = fileName or f"aa_request_{int(time())}.json"
        with open(fileName, "w") as f:
            f.write(json.dumps(self.to_dict(), indent=4))
