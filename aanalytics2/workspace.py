import pandas as pd
import json
from typing import Union, IO
import time
from .requestCreator import RequestCreator
from copy import deepcopy


class Workspace:
    """
    A class to return data from the getReport method.
    """

    startDate = None
    endDate = None
    settings = None

    def __init__(
        self,
        responseData: dict,
        dataRequest: dict = None,
        columns: dict = None,
        summaryData: dict = None,
        analyticsConnector: object = None,
        reportType: str = "normal",
        metrics: Union[dict, list] = None,  ## for normal type, static report
        metricFilters: dict = None,
        resolveColumns: bool = True,
    ) -> None:
        """
        Setup the different values from the response of the getReport
        Argument:
            responseData : REQUIRED : data returned & predigested by the getReport method.
            dataRequest : REQUIRED : dataRequest containing the request
            columns : REQUIRED : the columns element of the response.
            summaryData : REQUIRED : summary data containing total calculated by CJA
            analyticsConnector : REQUIRED : analytics object connector.
            reportType : OPTIONAL : define type of report retrieved.(normal, static, multi)
            metrics : OPTIONAL : dictionary of the columns Id for normal report and list of columns name for Static report
            metricFilters : OPTIONAL : Filter name for the id of the filter
            resolveColumns : OPTIONAL : If you want to resolve the column name and returning ID instead of name
        """
        for filter in dataRequest["globalFilters"]:
            if filter["type"] == "dateRange":
                self.startDate = filter["dateRange"].split("/")[0]
                self.endDate = filter["dateRange"].split("/")[1]
        self.dataRequest = RequestCreator(dataRequest)
        self.requestSize = dataRequest["settings"]["limit"]
        self.settings = dataRequest["settings"]
        self.pageRequested = dataRequest["settings"]["page"] + 1
        self.summaryData = summaryData
        self.reportType = reportType
        self.analyticsObject = analyticsConnector
        ## global filters resolution
        filters = []
        for filter in dataRequest["globalFilters"]:
            if filter["type"] == "segment":
                segmentId = filter.get("segmentId",None)
                if segmentId is not None:
                    seg = self.analyticsObject.getSegment(filter["segmentId"])
                    filter["segmentName"] = seg["name"]
                else:
                    context = filter.get('segmentDefinition',{}).get('container',{}).get('context')
                    description = filter.get('segmentDefinition',{}).get('container',{}).get('pred',{}).get('description')
                    listName = ','.join(filter.get('segmentDefinition',{}).get('container',{}).get('pred',{}).get('list',[]))
                    function = filter.get('segmentDefinition',{}).get('container',{}).get('pred',{}).get('func')
                    filter["segmentId"] = f"Dynamic: {context} {description} {function} {listName}"
                    filter["segmentName"] = f"{context} {description} {listName}"
            filters.append(filter)
        self.globalFilters = filters
        self.metricFilters = metricFilters
        if reportType == "normal" or reportType == "static":
            df_init = pd.DataFrame(responseData).T
            df_init = df_init.reset_index()
        elif reportType == "multi":
            df_init = responseData
        if reportType == "normal":
            columns_data = ["itemId"]
        elif reportType == "static":
            columns_data = ["SegmentName"]
        ### adding dimensions & metrics in columns names when reportType is "normal"
        if "dimension" in dataRequest.keys() and reportType == "normal":
            columns_data.append(dataRequest["dimension"])
            ### adding metrics in columns names
            columnIds = columns["columnIds"]
            # To get readable names of template metrics and Success Events, we need to get the full list of metrics for the Report Suite first. 
            # But we won't do this if there are no such metrics in the report.
            if (resolveColumns is True) & (
                    len([metric for metric in metrics.values() if metric.startswith("metrics/")]) > 0):
                rsMetricsList = self.analyticsObject.getMetrics(rsid=dataRequest["rsid"])
            for col in columnIds:
                metrics: dict = metrics  ## case when dict is used
                metricListName: list = metrics[col].split(":::")
                if resolveColumns:
                    metricResolvedName = []
                    for metric in metricListName:
                        if metric.startswith("cm"):
                            cm = self.analyticsObject.getCalculatedMetric(metric)
                            metricName = cm.get("name",metric)
                            metricResolvedName.append(metricName)
                        elif metric.startswith("s"):
                            seg = self.analyticsObject.getSegment(metric)
                            segName = seg.get("name",metric)
                            metricResolvedName.append(segName)
                        elif metric.startswith("metrics/"):
                            metricName = rsMetricsList[rsMetricsList["id"] == metric]["name"].iloc[0]
                            metricResolvedName.append(metricName)
                        else:
                            metricResolvedName.append(metric)
                    colName = ":::".join(metricResolvedName)
                    columns_data.append(colName)
                else:
                    columns_data.append(metrics[col])
        elif reportType == "static":
            metrics: list = metrics  ## case when a list is used
            columns_data.append("SegmentId")
            columns_data += metrics
        if df_init.empty == False and (
            reportType == "static" or reportType == "normal"
        ):
            df_init.columns = columns_data
            self.columns = list(df_init.columns)
        elif reportType == "multi":
            self.columns = list(df_init.columns)
        else:
            self.columns = list(df_init.columns)
        self.row_numbers = len(df_init)
        self.dataframe = df_init

    def __str__(self):
        return json.dumps(
            {
                "startDate": self.startDate,
                "endDate": self.endDate,
                "globalFilters": self.globalFilters,
                "totalRows": self.row_numbers,
                "columns": self.columns,
            },
            indent=4,
        )

    def __repr__(self):
        return json.dumps(
            {
                "startDate": self.startDate,
                "endDate": self.endDate,
                "globalFilters": self.globalFilters,
                "totalRows": self.row_numbers,
                "columns": self.columns,
            },
            indent=4,
        )

    def to_csv(
        self,
        filename: str = None,
        delimiter: str = ",",
        index: bool = False,
    ) -> IO:
        """
        Save the result in a CSV
        Arguments:
            filename : OPTIONAL : name of the file
            delimiter : OPTIONAL : delimiter of the CSV
            index : OPTIONAL : should the index be included in the CSV (default False)
        """
        if filename is None:
            filename = f"cjapy_{int(time.time())}.csv"
        self.df_init.to_csv(filename, delimiter=delimiter, index=index)

    def to_json(self, filename: str = None, orient: str = "index") -> IO:
        """
        Save the result to JSON
        Arguments:
            filename : OPTIONAL : name of the file
            orient : OPTIONAL : orientation of the JSON
        """
        if filename is None:
            filename = f"cjapy_{int(time.time())}.json"
        self.df_init.to_json(filename, orient=orient)

    def breakdown(
        self,
        index: Union[int, str] = None,
        dimension: str = None,
        n_results: Union[int, str] = 10,
    ) -> object:
        """
        Breakdown a specific index or value of the dataframe, by another dimension.
        NOTE: breakdowns are possible only from normal reportType.
        Return a workspace instance.
        Arguments:
            index : REQUIRED : Value to use as filter for the breakdown or index of the dataframe to use for the breakdown.
            dimension : REQUIRED : dimension to report.
            n_results : OPTIONAL : number of results you want to have on your breakdown. Default 10, can use "inf"
        """
        if index is None or dimension is None:
            raise ValueError(
                "Require a value to use as breakdown and dimension to request"
            )
        breadown_dimension = list(self.dataframe.columns)[1]
        if type(index) == str:
            row: pd.Series = self.dataframe[self.dataframe.iloc[:, 1] == index]
            itemValue: str = row["itemId"].values[0]
        elif type(index) == int:
            itemValue = self.dataframe.loc[index, "itemId"]
        breakdown = f"{breadown_dimension}:::{itemValue}"
        new_request = RequestCreator(self.dataRequest.to_dict())
        new_request.setDimension(dimension)
        metrics = new_request.getMetrics()
        for metric in metrics:
            new_request.addMetricFilter(metricId=metric, filterId=breakdown)
        if n_results < 20000:
            new_request.setLimit(n_results)
            report = self.analyticsObject.getReport2(
                new_request.to_dict(), n_results=n_results
            )
        if n_results == "inf" or n_results > 20000:
            report = self.analyticsObject.getReport2(
                new_request.to_dict(), n_results=n_results
            )
        return report
