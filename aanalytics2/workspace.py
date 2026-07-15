import math
import pandas as pd
import json
from typing import Union, IO
import time
from .requestCreator import RequestCreator
from .workspaceManager import WorkspaceManager, TextBuilder
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
        self.requestSize = dataRequest.get("settings", {}).get("limit")
        self.settings = dataRequest.get("settings", {})
        self.pageRequested = dataRequest.get("settings", {}).get("page", 0) + 1
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
                            matched = rsMetricsList[rsMetricsList["id"] == metric]["name"]
                            metricName = matched.iloc[0] if not matched.empty else metric
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
        self.dataframe.to_csv(filename, sep=delimiter, index=index)

    def to_json(self, filename: str = None, orient: str = "index") -> IO:
        """
        Save the result to JSON
        Arguments:
            filename : OPTIONAL : name of the file
            orient : OPTIONAL : orientation of the JSON
        """
        if filename is None:
            filename = f"cjapy_{int(time.time())}.json"
        self.dataframe.to_json(filename, orient=orient)

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
        n_results = float(n_results) ## transforming n_result in float
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
        new_request.setLimit(n_results)
        report = self.analyticsObject.getReport2(
            new_request, n_results=n_results
        )
        return report


class TargetWorkspace(Workspace):
    """
    A class extending Workspace for Adobe Target A/B testing activity reports.
    Shares the same __init__ signature as Workspace and adds Target-specific analysis.

    Attributes:
        activityName      : Name of the Target activity being reported.
        controlGroup      : Name of the control/default experience (resolved from data if not provided).
        metrics           : Ordered list of metric column names used for statistical analysis.
                            The first entry is the base (exposure) count; subsequent entries are
                            conversion counts.
        baseMetric        : First metric in `metrics`, used as the exposure/visitor count denominator.
        conversionMetrics : Remaining metrics after the first, each treated as a conversion count.
        confidenceLevel   : Threshold for statistical significance (default 0.95).
        evaluation        : Hypothesis test directionality ('2sides', 'leftOneSided', 'rightOneSided').
        method            : Statistical test used ('z-test' or 't-test').
        apiCalls          : Number of API calls made to build this report.
        rawDataframe      : Dataframe before experience filtering (after column renaming).
        dataframe         : Filtered dataframe with experience rows only — no confidence columns.
        confidenceDataframe : Filtered dataframe extended with confidence and significance columns
                              for each conversion metric.
    """

    def __init__(
        self,
        responseData: dict,
        dataRequest: dict = None,
        columns: dict = None,
        summaryData: dict = None,
        analyticsConnector: object = None,
        reportType: str = "normal",
        metrics: Union[dict, list] = None,
        metricFilters: dict = None,
        resolveColumns: bool = True,
        # Target-specific parameters
        activityName: str = None,
        list_items: list = None,
        controlGroup: str = None,
        targetMetrics: list = None,
        confidenceLevel: float = 0.95,
        evaluation: str = '2sides',
        method: str = 'z-test',
        apiCalls: int = 0,
        activityFilter: str = None,
    ) -> None:
        """
        Build a TargetWorkspace directly from raw report API response data.
        Calls Workspace.__init__ with the standard parameters, then applies
        Target-specific column renaming, experience filtering, control-group
        detection, and computes a second dataframe (confidenceDataframe) with
        confidence and significance values for each conversion metric.

        Arguments:
            responseData    : REQUIRED : data returned & predigested by the getReport method.
            dataRequest     : REQUIRED : dataRequest containing the request.
            columns         : REQUIRED : the columns element of the response.
            summaryData     : REQUIRED : summary data containing totals calculated by CJA.
            analyticsConnector : REQUIRED : analytics object connector.
            reportType      : OPTIONAL : type of report ('normal', 'static', 'multi').
            metrics         : OPTIONAL : column mapping dict (normal) or list (static).
            metricFilters   : OPTIONAL : filter name mapping for metric filter IDs.
            resolveColumns  : OPTIONAL : resolve column IDs to display names (default True).
            activityName    : OPTIONAL : name of the Target activity.
            list_items      : OPTIONAL : list of experience names to keep (filters the dataframe).
            controlGroup    : OPTIONAL : name of the control experience. Defaults to the experience
                              whose name contains 'default' (case-insensitive).
            targetMetrics   : OPTIONAL : ordered list of column names / metric IDs present in the
                              dataframe after construction. The first entry is the base (exposure)
                              count; subsequent entries are conversion counts used for statistics.
            confidenceLevel : OPTIONAL : significance threshold (default 0.95).
            evaluation      : OPTIONAL : '2sides', 'leftOneSided', or 'rightOneSided' (default '2sides').
            method          : OPTIONAL : 'z-test' (default) or 't-test'.
            apiCalls        : OPTIONAL : number of upstream API calls used to produce the workspace.
            activityFilter  : OPTIONAL : dimension item filter string for the Target activity
                              (e.g. 'variables/targetraw.activity:::itemId'). Used as a dropdown
                              filter on Workspace panels created by linkToWorkspace.
        """
        super().__init__(
            responseData=responseData,
            dataRequest=dataRequest,
            columns=columns,
            summaryData=summaryData,
            analyticsConnector=analyticsConnector,
            reportType=reportType,
            metrics=metrics,
            metricFilters=metricFilters,
            resolveColumns=resolveColumns,
        )

        # Target-specific metadata
        self.activityName = activityName
        self.metrics = list(targetMetrics) if targetMetrics else []
        self.baseMetric = self.metrics[0] if self.metrics else None
        self.conversionMetrics = self.metrics[1:] if len(self.metrics) > 1 else []
        self.confidenceLevel = confidenceLevel
        self.evaluation = evaluation
        self.method:str = method
        self.apiCalls:int = apiCalls
        self.analyticsObject = analyticsConnector
        self.activityFilter:str = activityFilter
        self.segments:list = self.analyticsObject.getSegments(format="raw")

        # Rename dimension column to 'Target Experience' and metric columns to targetMetrics
        if self.metrics:
            all_cols = list(self.dataframe.columns)
            rename_map = {}
            if len(all_cols) > 1:
                rename_map[all_cols[1]] = 'Target Experience'
            for i, tm in enumerate(self.metrics):
                if 2 + i < len(all_cols):
                    rename_map[all_cols[2 + i]] = tm
            if rename_map:
                self.dataframe = self.dataframe.rename(columns=rename_map)
                self.columns = list(self.dataframe.columns)

        # Detect the experience dimension column (second column, after 'itemId')
        all_cols = list(self.dataframe.columns)
        self._experience_col = all_cols[1] if len(all_cols) > 1 else None

        # Filter to the experiences belonging to this activity
        df = self.dataframe.copy()
        if list_items is not None and self._experience_col is not None:
            df = df[df[self._experience_col].isin(list_items)].copy()

        # Resolve and validate the control group
        if self._experience_col is not None:
            if controlGroup is not None:
                control_mask = df[self._experience_col] == controlGroup
                if not control_mask.any():
                    raise ValueError(f"controlGroup '{controlGroup}' not found in the results")
                self.controlGroup = controlGroup
            else:
                control_mask = df[self._experience_col].str.contains('default', case=False, na=False)
                if not control_mask.any():
                    raise ValueError(
                        "No experience containing 'default' found; please specify controlGroup explicitly"
                    )
                self.controlGroup = df.loc[df.index[control_mask][0], self._experience_col]
        else:
            self.controlGroup = controlGroup

        # Set the main dataframe to the filtered version (no confidence columns)
        self.raw_dataframe = df
        self.row_numbers = len(self.raw_dataframe)
        self.columns = list(self.raw_dataframe.columns)

        # Compute the second dataframe with confidence and significance columns
        try:
            self.dataframe = self._compute_confidence(df.copy())
        except Exception as e:
            print(f"Error computing confidence. The data returned may not be suitable for confidence computation: {e}")
            self.dataframe = df.copy()

    def _betacf(self, a: float, b: float, x: float, max_iter: int = 200, eps: float = 3e-7) -> float:
        """Lentz continued-fraction evaluation of the incomplete beta function."""
        qab = a + b
        qap = a + 1.0
        qam = a - 1.0
        c = 1.0
        d = 1.0 - qab * x / qap
        if abs(d) < 1e-30:
            d = 1e-30
        d = 1.0 / d
        h = d
        for m in range(1, max_iter + 1):
            m2 = 2 * m
            aa = m * (b - m) * x / ((qam + m2) * (a + m2))
            d = 1.0 + aa * d
            if abs(d) < 1e-30:
                d = 1e-30
            c = 1.0 + aa / c
            if abs(c) < 1e-30:
                c = 1e-30
            d = 1.0 / d
            h *= d * c
            aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
            d = 1.0 + aa * d
            if abs(d) < 1e-30:
                d = 1e-30
            c = 1.0 + aa / c
            if abs(c) < 1e-30:
                c = 1e-30
            d = 1.0 / d
            delta = d * c
            h *= delta
            if abs(delta - 1.0) < eps:
                break
        return h


    def _betai(self, a: float, b: float, x: float) -> float:
        """Regularized incomplete beta function I_x(a, b)."""
        if x <= 0.0:
            return 0.0
        if x >= 1.0:
            return 1.0
        lbeta = math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)
        if x < (a + 1.0) / (a + b + 2.0):
            front = math.exp(a * math.log(x) + b * math.log(1.0 - x) - lbeta) / a
            return front * self._betacf(a, b, x)
        else:
            front = math.exp(b * math.log(1.0 - x) + a * math.log(x) - lbeta) / b
            return 1.0 - front * self._betacf(b, a, 1.0 - x)


    def _t_pvalue(self,t: float, df: float, evaluation: str) -> float:
        """P-value of Welch's t-statistic using the regularized incomplete beta function."""
        x = df / (df + t * t)
        two_tail = self._betai(df / 2.0, 0.5, x)
        if evaluation == '2sides':
            return two_tail
        elif evaluation == 'rightOneSided':
            return two_tail / 2.0 if t <= 0 else 1.0 - two_tail / 2.0
        elif evaluation == 'leftOneSided':
            return two_tail / 2.0 if t >= 0 else 1.0 - two_tail / 2.0
        else:
            raise ValueError("evaluation must be '2sides', 'leftOneSided', or 'rightOneSided'")

    def _compute_confidence(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Append confidence and significance columns for each conversion metric.
        Uses self.baseMetric as the exposure count and self.conversionMetrics as conversion counts.
        """
        if len(self.metrics) < 2 or self._experience_col is None:
            return df

        control_mask = df[self._experience_col] == self.controlGroup
        if not control_mask.any():
            return df

        control_idx = df.index[control_mask][0]
        n_control = float(df.loc[control_idx, self.baseMetric])

        for metric in self.conversionMetrics:
            x_control = float(df.loc[control_idx, metric])
            confidences = []
            for idx, row in df.iterrows():
                if idx == control_idx:
                    confidences.append(float('nan'))
                    continue
                n_variant = float(row[self.baseMetric])
                x_variant = float(row[metric])
                total = n_control + n_variant
                if total == 0 or n_control == 0 or n_variant == 0:
                    confidences.append(float('nan'))
                    continue
                p_pool = (x_control + x_variant) / total
                if p_pool == 0 or p_pool == 1:
                    confidences.append(float('nan'))
                    continue
                if self.method == 't-test':
                    p_control = x_control / n_control
                    p_variant = x_variant / n_variant
                    v1 = p_control * (1 - p_control) / n_control
                    v2 = p_variant * (1 - p_variant) / n_variant
                    se = math.sqrt(v1 + v2)
                    if se == 0:
                        confidences.append(float('nan'))
                        continue
                    t_stat = (p_variant - p_control) / se
                    df_welch = (v1 + v2) ** 2 / (
                        v1 ** 2 / max(n_control - 1, 1) + v2 ** 2 / max(n_variant - 1, 1)
                    )
                    p_value = self._t_pvalue(t_stat, df_welch, self.evaluation)
                else:  # z-test (default)
                    se = math.sqrt(p_pool * (1 - p_pool) * (1 / n_control + 1 / n_variant))
                    if se == 0:
                        confidences.append(float('nan'))
                        continue
                    z = (x_variant / n_variant - x_control / n_control) / se
                    if self.evaluation == '2sides':
                        p_value = math.erfc(abs(z) / math.sqrt(2))
                    elif self.evaluation == 'rightOneSided':
                        p_value = 0.5 * math.erfc(z / math.sqrt(2))
                    elif self.evaluation == 'leftOneSided':
                        p_value = 0.5 * math.erfc(-z / math.sqrt(2))
                    else:
                        raise ValueError(
                            "evaluation must be '2sides', 'leftOneSided', or 'rightOneSided'"
                        )
                confidences.append(round(1 - p_value, 4))
            df[f'{metric}_confidence'] = confidences
            df[f'{metric}_is_significant'] = df[f'{metric}_confidence'] >= self.confidenceLevel

        return df
    
    def __single_breakdown__(
        self,
        index: Union[int, str] = None,
        dimension: str = None,
        n_results: Union[int, str] = 10,
        focusMetricId: str = None,
    ) -> object:
        """
        Breakdown a specific index or value of the dataframe, by another dimension.
        NOTE: breakdowns are possible only from normal reportType.
        Return a workspace instance.
        Arguments:
            index : REQUIRED : Value to use as filter for the breakdown or index of the dataframe to use for the breakdown.
            dimension : REQUIRED : dimension to report.
            n_results : OPTIONAL : number of results you want to have on your breakdown. Default 10, can use "inf"
            focusMetricId : OPTIONAL : If you want to focus on a specific metric for the breakdown, provide its column name here. Default None, which means all metrics will be included in the breakdown request.
        """
        n_results = float(n_results) ## transforming n_result in float
        if index is None or dimension is None:
            raise ValueError(
                "Require a value to use as breakdown and dimension to request"
            )
        breadown_dimension = "variables/targetraw.experience" ## hardcoded for Target workspaces, can be made dynamic if needed
        if type(index) == str:
            row: pd.Series = self.dataframe[self.dataframe.iloc[:, 1] == index]
            itemValue: str = row["itemId"].values[0]
        elif type(index) == int:
            itemValue = self.dataframe.loc[index, "itemId"]
        breakdown = f"{breadown_dimension}:::{itemValue}"
        new_request = RequestCreator(self.dataRequest.to_dict())
        new_request.setDimension(dimension)
        if focusMetricId is not None:
            new_request.removeMetrics()
            new_request.addMetric(focusMetricId)
        metrics = new_request.getMetrics()
        for metric in metrics:
            new_request.addMetricFilter(metricId=metric, filterId=breakdown)
        new_request.setLimit(n_results)
        report = self.analyticsObject.getReport2(
            new_request, n_results=n_results
        )
        return report

    def breakdown(
        self,
        dimension: str = None,
        n_results: Union[int, str] = 10,
        focusMetric : str | None = None,
    ) -> pd.DataFrame:
        """
        Breakdown every experience row by the given dimension and return a single combined DataFrame.
        For each experience, one API call is made and the resulting metric columns are suffixed with
        the experience name: '{metric} ({experience})'.
        All per-experience DataFrames are then merged on the dimension key columns (itemId + dimension).
        self.apiCalls is incremented by the number of rows processed.
        Arguments:
            dimension : REQUIRED : Dimension to break down each experience by.
            n_results : OPTIONAL : Number of results per breakdown request. Default 10, can use "inf".
            focusMetric : OPTIONAL : Metric to focus on for the breakdown. Default None. If provided, the request will only contain that single metric.
        Returns a merged DataFrame with the breakdown dimension and one set of metric columns per experience.
        """
        if dimension is None:
            raise ValueError("Require a dimension for the breakdown")
        combined = None
        focusMetricId = None
        if focusMetric is not None:
            if focusMetric.startswith("metrics/") == False and focusMetric.startswith("cm") == False:
                metricsList:list = self.analyticsObject.getMetrics(rsid=self.dataRequest.rsid,format="raw")
                cmList:list = self.analyticsObject.getCalculatedMetrics(format="raw")
                self.apiCalls += 2
                completeList= metricsList + cmList
                matched = [m for m in completeList if m["name"] == focusMetric]
                if not matched:
                    raise ValueError(f"focusMetric '{focusMetric}' not found in the report suite metrics or calculated metrics")
                focusMetricId= matched[0]['id']
            else:
                focusMetricId = focusMetric
        for exp in self.dataframe['Target Experience'].to_list():
            sub_report = self.__single_breakdown__(index=exp, dimension=dimension, n_results=n_results, focusMetricId=focusMetricId)
            self.apiCalls += 1
            sub_df = sub_report.dataframe.copy()
            # Second column is the breakdown dimension; first is itemId
            dim_col = list(sub_df.columns)[1]
            key_cols = ["itemId", dim_col]
            metric_cols = [c for c in sub_df.columns if c not in key_cols]
            sub_df = sub_df.rename(columns={col: f"{col.split(':::')[0]} ({exp})" for col in metric_cols})
            if combined is None:
                combined = sub_df
            else:
                combined = combined.merge(sub_df, on=key_cols, how="outer")
        combined = combined.drop(columns=["itemId"])
        return combined

    def upliftCalculation(self, metric: str = None) -> pd.DataFrame:
        """
        Compute conversion rate and relative uplift vs the control group for each experience.
        Rate   = conversion metric / baseMetric (first metric, the exposure count).
        Uplift = (variant_rate - control_rate) / control_rate.
        The control group row has NaN for uplift.
        Arguments:
            metric : OPTIONAL : A single conversion metric column name to compute rate and uplift for.
                If not provided, all conversion metrics (all metrics after the first) are used.
        Returns a DataFrame with the experience column, the base metric column, and for each
        targeted conversion metric: '{metric}_rate' and '{metric}_uplift' columns.
        """
        if len(self.metrics) < 2:
            raise ValueError("Need at least 2 metrics to compute conversion rate and uplift")
        if metric is not None:
            if metric not in self.dataframe.columns:
                raise ValueError(f"Column '{metric}' not found in the dataframe")
            target_metrics = [metric]
        else:
            target_metrics = self.conversionMetrics
        df = self.dataframe.copy()
        result = df[[self._experience_col, self.baseMetric]].copy()
        control_mask = result[self._experience_col] == self.controlGroup
        if not control_mask.any():
            raise ValueError("Control group not found for uplift calculation")
        control_idx = result.index[control_mask][0]
        for col in target_metrics:
            if col not in df.columns:
                raise ValueError(f"Metric column '{col}' not found in the dataframe")
            result[f'{col}_rate'] = df[col] / df[self.baseMetric]
            control_rate = float(result.loc[control_idx, f'{col}_rate'])
            uplifts = []
            for idx, row in result.iterrows():
                if idx == control_idx:
                    uplifts.append(float('nan'))
                    continue
                if control_rate == 0:
                    uplifts.append(float('nan'))
                    continue
                uplifts.append(round((float(row[f'{col}_rate']) - control_rate) / control_rate, 4))
            result[f'{col}_uplift'] = uplifts
        return result

    def __str__(self) -> str:
        return json.dumps(
            {
                "activityName": self.activityName,
                "controlGroup": self.controlGroup,
                "startDate": self.startDate,
                "endDate": self.endDate,
                "metrics": self.metrics,
                "baseMetric": self.baseMetric,
                "conversionMetrics": self.conversionMetrics,
                "confidenceLevel": self.confidenceLevel,
                "evaluation": self.evaluation,
                "method": self.method,
                "apiCalls": self.apiCalls,
                "totalRows": self.row_numbers,
            },
            indent=4,
        )

    def __repr__(self) -> str:
        return self.__str__()

    def linkToWorkspace(
        self,
        workspaceName: str,
        globalFilters: list = None,
        segmentsSplit: list = None,
    ) -> dict:
        """
        Link this Target activity to an Adobe Analytics Workspace project.

        If a project named `workspaceName` already exists, the method loads its
        definition via WorkspaceManager, prepends new 'Target Results' panels
        (containing a Text visualisation summarising confidence scores and
        significance per experience), and calls updateProject to save the change.

        If no such project exists, the method creates a brand-new Workspace with
        one 'Target Results' panel per entry in `segments` (plus one unsegmented
        panel), each containing a Text visualisation and a freeform data table.

        All panels are scoped to the same date range as the original report.
        Segments from the original request are always applied. Additional filters
        from `globalFilters` are applied to every panel on top of those.

        Arguments:
            workspaceName : REQUIRED : Name of the Workspace project to find or create.
            globalFilters : OPTIONAL : List of segment IDs or names applied to every panel
                            in addition to the segments from the original report request.
            segmentsSplit : OPTIONAL : List of segment IDs or names. When provided, the
                            'Target Results' panel is replicated once per entry plus one
                            panel with no extra segment. E.g. passing ['Mobile', 'Desktop']
                            creates 3 panels: one unsegmented, one for Mobile, one for Desktop.
            
        Returns the raw API response dict from createProject or updateProject.
        """
        rsid = self.dataRequest.rsid
        metric_ids = self.dataRequest.getMetrics()
        owner = self.analyticsObject.getUserMe()
        existing_segmentIds = [el['segmentId'] for el in self.globalFilters if el['type'] == 'segment']
        # Resolve display names for standard metrics (e.g. 'metrics/visits' → 'Visits')
        _std_metrics_cache = None
        resolved_metric_names = []
        for mid, mname in zip(metric_ids, self.metrics):
            if mid.startswith("metrics/") and mid == mname:
                # Name was never resolved — fetch the metric list once
                if _std_metrics_cache is None:
                    _std_metrics_cache = self.analyticsObject.getMetrics(rsid=rsid, format="raw")
                    self.apiCalls += 1
                matched = next((m for m in _std_metrics_cache if m["id"] == mid), None)
                resolved_metric_names.append(matched["name"] if matched else mname)
            else:
                resolved_metric_names.append(mname)
        # Pair original metric IDs with their display names
        metrics_spec = [
            {"id": mid, "name": mname}
            for mid, mname in zip(metric_ids, resolved_metric_names)
        ]
        # Resolve Segment names for segmentsSplit
        resolved_segments = {}
        for seg in segmentsSplit or []:
            tmp_seg = next((s for s in self.segments if s.get("id") == seg), None) or next((s for s in self.segments if s.get("name") == seg), None)
            if tmp_seg:
                resolved_segments[tmp_seg["id"]] = tmp_seg["name"]

        # ── Build text summary ──────────────────────────────────────────────
        start_display = (self.startDate or "").split("T")[0]
        end_display = (self.endDate or "").split("T")[0]

        tb = TextBuilder()
        tb.addTitle(f"Target A/B Test: {self.activityName or 'Activity'}", level=2)
        tb.addNewline()
        tb.addBold("Report period: ")
        tb.addText(f"{start_display} \u2192 {end_display}")
        tb.addNewline()
        tb.addBold("Control group: ")
        tb.addText(self.controlGroup or "N/A")
        tb.addNewline()
        tb.addBold("Statistical test: ")
        tb.addText(self.method)
        tb.addNewline()
        tb.addNewline()

        # Map internal metric column names to their display names
        metric_display = dict(zip(self.metrics, resolved_metric_names))
        df = self.dataframe

        # Control group block — raw counts only
        ctrl_rows = df[df[self._experience_col] == self.controlGroup]
        if not ctrl_rows.empty:
            ctrl = ctrl_rows.iloc[0]
            tb.addBold(f"Experience: {self.controlGroup} (Control)")
            tb.addNewline()
            for metric in self.metrics:
                raw_val = ctrl.get(metric, float("nan"))
                display_name = metric_display.get(metric, metric)
                if pd.isna(raw_val):
                    tb.addText(f"  {display_name}: N/A")
                else:
                    try:
                        tb.addText(f"  {display_name}: {int(raw_val):,}")
                    except (ValueError, OverflowError):
                        tb.addText(f"  {display_name}: {raw_val}")
                tb.addNewline()
            tb.addNewline()

        # Non-control experience blocks — counts + confidence + significance
        for _, row in df.iterrows():
            exp_name = row.get(self._experience_col, "")
            if exp_name == self.controlGroup:
                continue
            tb.addBold(f"Experience: {exp_name}")
            tb.addNewline()
            # Base metric (exposure count)
            base_val = row.get(self.baseMetric, float("nan"))
            base_display = metric_display.get(self.baseMetric, self.baseMetric)
            if not pd.isna(base_val):
                try:
                    tb.addText(f"  {base_display}: {int(base_val):,}")
                except (ValueError, OverflowError):
                    tb.addText(f"  {base_display}: {base_val}")
                tb.addNewline()
            # Conversion metrics — count + confidence
            for metric in self.conversionMetrics:
                conf_col = f"{metric}_confidence"
                sig_col = f"{metric}_is_significant"
                conf_val = row.get(conf_col, float("nan"))
                is_sig = bool(row.get(sig_col, False))
                raw_val = row.get(metric, float("nan"))
                display_name = metric_display.get(metric, metric)
                try:
                    count_str = f"{int(raw_val):,}" if not pd.isna(raw_val) else "N/A"
                except (ValueError, OverflowError):
                    count_str = str(raw_val)
                if pd.isna(conf_val):
                    tb.addText(f"  {display_name}: {count_str} | confidence: N/A")
                else:
                    conf_pct = f"{conf_val * 100:.1f}%"
                    if is_sig:
                        tb.addText(f"  {display_name}: {count_str} | confidence ")
                        tb.addColor(conf_pct, "var(--spectrum-celery-600)")
                        tb.addText(" \u2713 Significant")
                    else:
                        tb.addText(f"  {display_name}: {count_str} | confidence ")
                        tb.addColor(conf_pct, "var(--spectrum-red-800)")
                        tb.addText(" \u2717 Not significant")
                tb.addNewline()
            tb.addNewline()

        # ── Date range for panels ───────────────────────────────────────────
        if self.startDate and self.endDate:
            date_range_id = f"{self.startDate}/{self.endDate}"
        else:
            date_range_id = "thisMonth"

        # ── Activity freeform config ──────────────────────────────────────────
        dim_item_id = self.activityFilter.replace(":::", "::") if self.activityFilter else None

        # ── Panel name helper ─────────────────────────────────────────────────
        def _panel_name(extra_segment):
            return f"Target Results ({extra_segment})" if extra_segment else "Target Results"

        # ── Helper: add the text summary visualisation to the current panel ────
        def _add_text_summary(wc):
            wc.addTextFreeform("Experiment Results", tb)

        # ── Helper: add the freeform data table visualisation to the current panel ─
        def _add_data_table(wc):
            if dim_item_id:
                wc.addActivityBreakdownFreeform(
                    title=self.activityName or "Target Experiences",
                    activity_dim_item_id=dim_item_id,
                    activity_name=self.activityName or "",
                    breakdown_dim_id="variables/targetraw.experience",
                    breakdown_dim_name="Target Experiences",
                    metrics=metrics_spec,
                    rows=50,
                    breakdown_rows=10,
                )
            else:
                wc.addSimpleFreeform(
                    title=self.activityName or "Target Experiences",
                    item_id="variables/targetraw.experience",
                    item_name="Target Experience",
                    metrics=metrics_spec,
                    rows=50,
                )

        # ── Helper: create one full "Target Results" panel with all filters ────
        def _add_results_panel(wc, extra_segment=None, position=None, include_text=True, include_freeform=True):
            kwargs = {"name": _panel_name(extra_segment), "date_range": date_range_id}
            if position is not None:
                kwargs["position"] = position
            wc.addPanel(**kwargs)
            if globalFilters:
                for gf in globalFilters:
                    wc.addSegmentFilter(gf)
            if extra_segment is not None:
                wc.addSegmentFilter(extra_segment)
            if include_text:
                _add_text_summary(wc)
            if include_freeform:
                _add_data_table(wc)

        # ── Normalise owner for new projects ────────────────────────────────
        owner_dict = {"id": owner['loginId'], "name": owner['fullName'], "login": owner['login']}

        # ── Find existing workspace by name ─────────────────────────────────
        self.apiCalls += 1
        all_projects = self.analyticsObject.getProjects(format="raw")
        existing = next(
            (p for p in all_projects if p.get("name") == workspaceName), None
        )

        if existing is not None:
            # ── Update path: load existing definition, prepend results panels ─
            self.apiCalls += 1
            project_dict = self.analyticsObject.getProject(existing["id"])
            wc = WorkspaceManager(data=project_dict, analytics=self.analyticsObject)
            wc.addPanel(name=_panel_name(None), date_range=date_range_id, position=0)
            _add_text_summary(wc, extra_segment=None, position=0, include_text=True, include_freeform=True)
            for i, (segId, segName) in enumerate(resolved_segments.items() or []):
                wc.addPanel(name=_panel_name(segName), date_range=date_range_id, position=i)
                for sf in existing_segmentIds:
                    wc.addSegmentFilter(sf)
                wc.addSegmentFilter(segId)
                _add_data_table(wc)
            updated_obj = wc.to_dict()
            self.apiCalls += 1
            return self.analyticsObject.updateProject(
                projectId=existing["id"], projectObj=updated_obj
            )
        else:
            # ── Create path: one panel per segment (+1 unsegmented) ───────────
            wc = WorkspaceManager(rsid=rsid, name=workspaceName)
            wc.setOwner(owner_dict) if owner_dict else None
            wc.addPanel(name=_panel_name(None), date_range=date_range_id, position=0)
            _add_text_summary(wc, extra_segment=None, position=0, include_text=True, include_freeform=True)
            for i, (segId, segName) in enumerate(resolved_segments.items() or []):
                wc.addPanel(name=_panel_name(segName), date_range=date_range_id, position=i+1)
                for sf in existing_segmentIds:
                    wc.addSegmentFilter(sf)
                wc.addSegmentFilter(segId)
                _add_data_table(wc)
            project_obj = wc.to_dict()
            # Ensure owner key is always present (required by createProject)
            if "owner" not in project_obj:
                project_obj["owner"] = owner_dict
            self.apiCalls += 1
            return self.analyticsObject.createProject(projectObj=project_obj)
