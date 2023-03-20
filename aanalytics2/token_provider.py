import datetime
import os
import re
import time
from datetime import timezone
from io import StringIO
from logging import Logger
from typing import Optional

import aanalytics2
import aanalytics2 as aa2
import numpy as np
import pandas as pd
from google.api_core.datetime_helpers import DatetimeWithNanoseconds

from dim28etl.config import cfg
from dim28etl.firestore import FireRef
from dim28etl.logs import get_logger

_LOGGER: Optional[Logger] = None


def log() -> Logger:
    global _LOGGER
    if not _LOGGER:
        _LOGGER = get_logger(__name__)
    return _LOGGER


def get_datesuffix(ms=False):
    current_dt = datetime.datetime.now()
    datesuffix = current_dt.strftime("%Y%m%d-%H%M%S")
    if ms:
        datesuffix = datesuffix + f"-{current_dt.microsecond}"
    return datesuffix


def generate_workspace_link(row, cid):
    row["link"] = f"https://experience.adobe.com/#/@{cid}/analytics/spa/index.html?#/workspace/edit/{row['id']}"
    return row


def merge_buffers(first, second):
    """Merges two StringIO buffers into a single buffer.

    :param first: first buffer
    :type first: StringIO
    :param second: second buffer
    :type second: StringIO
    :return: a buffer where the content of the `first` is appended with the content of the `second`
    :rtype: StringIO
    """
    result = StringIO()
    first.seek(0)
    second.seek(0)
    result.write(first.read())
    result.write(second.read())
    return result


def aa_safe_get_comp(comp_id: str = None, aa_inst: object = None, attempts: int = 10,
                     comp_type: str = "project") -> pd.DataFrame:
    """Safely gets an Adobe Analytics component (no 429 error problems). Tries up to 10 times."""
    attempt = 0
    response = None
    while attempt <= attempts:
        try:
            attempt = attempt + 1
            if comp_type == "project":
                response = aa_inst.getProject(projectId=comp_id)
            elif comp_type == "calculatedMetric":
                response = aa_inst.getCalculatedMetric(calculatedMetricId=comp_id, full=True)
            elif comp_type == "segment":
                response = aa_inst.getSegment(segment_id=comp_id, full=True)
            return response
        except Exception as e:
            log().warning(
                f"Got an error getting {comp_type} ID {comp_id}: {e} in attempt {attempt}. Will try max {attempts} times")
            time.sleep(10)
    log().error(f"Could not get {comp_type} {comp_id} after {attempt} attempts. Returning.")


def aa_safe_update_project(pid: str = None, project_obj: dict = None, aa_inst: object = None,
                           attempts: int = 10) -> object:
    """Safely updates an AA project. This is only to have another safeguard against the 429 error.
    It does not necessarily save us from update errors."""
    attempt = 0
    error = None
    while attempt <= attempts:
        try:
            attempt = attempt + 1
            response = aa_inst.updateProject(projectId=pid, projectObj=project_obj)
            return response
        except Exception as e:
            log().warning(
                f"Got an error getting project ID {pid}: {e} in attempt {attempt}. Will try max {attempts} times")
            error = e
            time.sleep(10)
    log().error(f"Could not update project {pid} after {attempt} attempts. Returning fake response with error Code")
    return {"errorCode": error}


def aa_safe_update_comp(comp_id: str = None, definition: dict = None, aa_inst: object = None,
                        attempts: int = 10, comp_type: str = "segment", meta_only=False) -> object:
    """Safely updates a segment or Calc Metrc. This is only to have another safeguard against the 429 error. It does not necessarily save us from update errors.
    :param meta_only: True if only an update to name and/or description desired. Otherwise we assume the full definition JSON is provided
    """
    attempt = 0
    response = None
    error = None
    while attempt <= attempts:
        try:
            attempt = attempt + 1
            if comp_type == "segment":
                if meta_only is False:
                    json_new = {"definition": definition}
                else:
                    json_new = definition  # in this case we only expect {"name": "new name", "description": "new desc"}
                response = aa_inst.updateSegment(segmentID=comp_id, segmentJSON=json_new)
            elif comp_type == "calculatedMetric":
                response = aa_inst.updateCalculatedMetric(calcID=comp_id, calcJSON=definition)
            elif comp_type == "dateRange":
                response = aa_inst.updateDateRange(dateRangeID=comp_id, dateRangeJSON=definition)
                # todo if date range definition is the same as before (not only then however!), "unexpected error" gets returned
            return response
        except Exception as e:
            log().warning(
                f"Got an error getting Component ID {comp_id} in attempt {attempt}: {e}. Will try max {attempts} times")
            error = e
            time.sleep(10)
    log().error(
        f"Could not update Component ID {comp_id} after {attempt} attempts. Returning fake response with error Code")
    return {"errorCode": error}


def safe_delete_comp(aa_inst=None, comp_id=None, comp_type=None, attempts: int = 10):  # id, type

    log().info(f"Deleting component {comp_id}: {comp_type}")
    attempt = 0
    error = None
    while attempt <= attempts:
        try:
            attempt = attempt + 1
            if comp_type == 'calculatedMetric':
                response = aa_inst.deleteCalculatedMetric(calcID=comp_id)
            elif comp_type == 'segment':
                response = aa_inst.deleteSegment(segmentID=comp_id)
            elif comp_type == 'dateRange':
                response = aa_inst.deleteDateRange(dateRangeID=comp_id)
            else:
                msg = f"Only Calc Metrics, Date Ranges and Segments can be deleted via API2.0. Deletion not executed."
                log().warning(msg)
                return msg
            return response

        except Exception as e:
            log().warning(
                f"Got an error getting Component ID {comp_id} in attempt {attempt}: {e}. Will try max {attempts} times")
            error = e
            time.sleep(10)
    log().error(
        f"Could not delete Component ID {comp_id} after {attempt} attempts. Returning fake response with error Code")
    return {"errorCode": error}


def aa_safe_get_vrs_components(vrsid: str = None, aa_inst: object = None, attempts=10) -> pd.DataFrame:
    attempt = 0
    error = None
    while attempt <= attempts:
        try:
            attempt = attempt + 1
            response = aa_inst.getVirtualReportSuiteComponents(vrsid=vrsid)
            if "curatedName" not in response.columns:
                response["curatedName"] = np.nan
            return response
        except Exception as error:
            log().warning(
                f"Got an error getting VRS Components for VRS ID {vrsid}: in attempt {attempt}. "
                f"Will sleep for 10 sec and again. Will try max {attempts} times. "
                f"The error was: {error}")
            time.sleep(10)
    log().error(f"Could not get VRS Components for VRS ID {vrsid} after {attempt} attempts. Returning.")
    return {"errorCode": error}


def aa_cols_readable(df, calc_metrics=None, dimensions=None, metrics=None):
    """takes a data frame export from aa v2 API (aanalytics2 module) and renames
    the columns to the names in the interface

    :param df: dataframe with the exported data
    :type df: pandas DataFrame
    :param calc_metrics: dataframe with all the calculated metrics (can be gotten via .getCalculatedMetrics())
    :type calc_metrics: pandas DataFrame
    :param dimensions: dataframe with all the dimensions
    :type dimensions: pandas DataFrame
    :param metrics: dataframe with all the metrics
    :type metrics: pandas DataFrame
    :return: columnnames as a series
    :rtype: series
    """
    cols = list(df.columns)
    colnames = []
    i = 0
    for col in cols:
        # log().info(col)
        if col.find("cm", 0, 2) != -1:  # if calc metric
            colnames.append(calc_metrics[calc_metrics['id'] == cols[i]].iloc[0]['name'])
        elif (col.find("variables", 0, 10) != -1):
            colnames.append(dimensions[dimensions['id'] == cols[i]].iloc[0]['name'])
            # standard metrics (e.g. Success events):
        elif (col.find("metrics/") != -1):
            colnames.append(metrics[metrics['id'] == cols[i]].iloc[0]['name'])
        else:
            colnames.append(col)
        i = i + 1

    return colnames


def aa_cols_descriptions(df, calc_metrics=None, dimensions=None, metrics=None):
    """NOT FINISHED, NOT WORKING! Takes a data frame export from aa v2 API (aanalytics2 module) and returns
    the interface descriptions of the columns from the interface

    :param df: dataframe with the exported data
    :type df: pandas DataFrame
    :param calc_metrics: dataframe with all the calculated metrics (can be gotten via .getCalculatedMetrics())
    :type calc_metrics: pandas DataFrame
    :param dimensions: dataframe with all the dimensions
    :type dimensions: pandas DataFrame
    :param metrics: dataframe with all the metrics
    :type metrics: pandas DataFrame
    :return: column descriptions as a series
    :rtype: series
    """
    cols = list(df.columns)
    descs = []
    i = 0
    for col in cols:
        # log().info(col)
        if col.find("cm", 0, 2) != -1:  # if calc metric
            descs.append(calc_metrics[calc_metrics['id'] == cols[i]].iloc[0]['description'])
            # TODO fails if description is nan
        elif (col.find("variables", 0, 10) != -1):
            descs.append(dimensions[dimensions['id'] == cols[i]].iloc[0]['description'])
            # standard metrics (e.g. Success events):
        elif (col.find("metrics/") != -1):
            descs.append(metrics[metrics['id'] == cols[i]].iloc[0]['description'])
        else:
            descs.append(col)
        i = i + 1

    return descs


def aa2_get_company_id_retry(cindex=0, tries=10):
    """
    tries to get companyId by trying a number of tries with a sleep time of 10 sec between each try
    :param cindex: the index of the Company to get (in case multiple company ID behind one company login), usually 0 # todo how to handle multiple company IDs!!!
    :param tries: how often should we try
    :return: company ID (which is None if none is returned)
    """
    for x in range(tries):
        r = x + 1  # x is 0-indexed
        log().info(f"trying to login to get CompanyId, round {r}")
        try:
            login = aa2.Login()
            cid = login.getCompanyId()[cindex]['globalCompanyId']
            # old method: cid = aa2.getCompanyId(param)
            if cid is not None:
                log().info("got CompanyID after " + str(r) + " tries")
                return cid
            if r == tries:
                log().critical(
                    "could not get company ID after " + str(r) + " tries. Rest of script will probably break.")
                return cid
            time.sleep(10)  # take a 10-second break before querying right away again
        except Exception as e:
            log().warning(f"Tried to get company ID, but could not login. Error: {e}")
            time.sleep(10)  # give API time to recover
            if x == range(tries):
                msg = f"max tries reached to get company ID. Quitting. Message: {e}"
                log().critical(msg)
                raise Exception(msg)


def aa2_get_report_suites(aa_instance, extended_info=False):
    """
    gets and returns all Report Suites
    :param aa_inst: Adobe Analytics API instance
    :param extended_info: True if extended info (more columns) desired
    :return: Report Suites as a pandas DataFrame
    """
    return aa_instance.getReportSuites(extended_info=extended_info)


def aa_projects_date_parser(df, cols):
    """parses columns that are returned as dates so they match the format you get when calling ags.getProjects"""
    for col in cols:
        df[col] = pd.to_datetime(df[col], format='%Y-%m-%dT%H:%M:%SZ')


# def delocalize_dates(row, cols):
#     from dim28etl.adobe.components.comp_editor.comp_editor_settings import not_supported_text
#     not_supported_text = "not supported"
#     for col in cols:
#         try:
#            row[col] = row[col].str.replace # pd.to_datetime(row[col], utc=True).dt.tz_localize(None)
#         except:
#             row[col] = not_supported_text
#     return row


def aa2_get_full_components(aa_inst, rsid=None, inclTypes=None, tries=10, columns=None, types=None, hash_pii=False,
                            definition_ids_only=False, copy_original_def=False, delocalize=True):
    """
    gets a dataframe with a full component list and normed columns
    :param aa_inst: aa2 adobe analytics instance
    :type aa_inst: object
    :param rsid: Report Suite ID (only needed for dimensions & metrics (evars/props/events) as these are Report-Suite-specific
    :type rsid: str
    :param inclTypes: "all", "shared", or "templates"
    :type inclTypes: list
    :param tries: how often should we try to get the data. API 2.0 is often spotty, so a default of 10 tries is used
    :type tries: int
    :param columns: which columns should be returned. Supported are : ["id", "name", "description", "modified",
                                                                      "modifiedById", "definition", "compatibility",
                                                                      "owner", "migratedIds", "rsid", "tags",
                                                                      "reportSuiteName",
                                                                      "siteTitle", "componentType"]
                                                                      (could be even more, this is the max columns for segments)
    :type columns:
    :param types: which component types should be returned? Default: all. Options: ["calculatedMetric", "dimension",
        "segment", "metric", "segment", "dateRange"]
    :type types: list
    :param hash_pii: if True, hashes "owner" column
    :type hash_pii: bool
    :param definition_ids_only: True if segments and calculated metrics definitions should be returned with the IDs used in their definitions ,id1,id2,etc,
    :type definition_ids_only: bool
    :param copy_original_def: True if there shall be a column "definition_original" which is a copy of the original definition
    before squashing the original definition to ids only via the `definition_ids_only` parameter
    :type copy_original_def: bool
    :param delocalize: True if modified date shall be without localization suffix (no "Z") -> this way, Excel / Google Sheets understands it is a date
    :type delocalize: bool
    :return: pandas DataFrame with all components and normed columns
    :rtype: DataFrame
    """
    from dim28etl.adobe.components.comp_usage.comp_usage_helpers import ids_from_comp_definition, get_owner_columns
    from dim28etl.adobe.components.comp_editor.comp_editor_settings import not_supported_text, hash_pii_text
    full_comp_df_output = None
    full_comp_dfs = []  # the data frame into which we will merge all components

    all_types = ["calculatedMetric", "dimension", "segment", "metric", "segment", "dateRange"]
    if types is None:
        types = all_types

    if columns is None:
        columns = ["id", "componentType", "name", "rsid", "description", "modified", "owner"]
        # TODO add a columns="all" option (needs further todos in norm_columns_for_all_dfs further down though!)

    # get all components by includeType
    if inclTypes is None:
        inclTypes = ["all", "templates",
                     "shared"]  # shared as the last because it is most interesting if sth is shared with all

    # if hashing PII is enabled, we write
    default_text_owner_cols = hash_pii_text
    if hash_pii is False:
        default_text_owner_cols = not_supported_text

    description = True
    for inclType in inclTypes:
        for x in range(tries):  # give each inclType the same amount of tries
            r = x + 1  # x is 0-indexed
            log().info(f"trying to get full components of inclType {inclType}, round {r}")
            try:
                dfs = {}
                # we name the df exactly like their componentType, that makes it easier later to add cols to them based on their type
                # api limit is PER PAGE OF REQUEST, not TOTAL OUTPUT! U WILL ALWAYS GET all RESULTS!
                if "calculatedMetric" in types:
                    dfs["calculatedMetric"] = aa_inst.getCalculatedMetrics(limit=1000, extended_info=True,
                                                                           inclType=inclType)

                if "dimension" in types:
                    dfs["dimension"] = aa_inst.getDimensions(rsid=rsid, limit=1000, extended_info=True,
                                                             description=description)

                if "metric" in types:
                    dfs["metric"] = aa_inst.getMetrics(rsid=rsid, limit=1000, extended_info=True
                                                       , description=description, verbose=True)

                if "segment" in types:
                    dfs["segment"] = aa_inst.getSegments(limit=1000, extended_info=True, inclType=inclType)

                if "dateRange" in types:
                    dfs["dateRange"] = aa_inst.getDateRanges(limit=1000, extended_info=True,
                                                             includeType=inclType)  # !!! for getDateRanges it's includeType, not inclType

                for df in dfs:  # add the componentType (= the name of the df) as a column
                    dfs[df]["componentType"] = df

                # create one big table with all components
                log().info("creating dataframe with all components")

                full_comp_dfs_normed_cols = norm_columns_for_all_dfs(dfs, columns, inclType,
                                                                     not_supported_text)
                full_comp_df_output = pd.concat(full_comp_dfs_normed_cols, sort=False)
                break  # we have all we need so we can exit the loop

            except Exception as e:
                log().warning("Could not get data from Adobe. Error: " + str(e))
                if (str(e).find(
                        "description") != -1):  # rare case that a report suite has no evars/props/success Events -> no description -> API throws error
                    description = False
                time.sleep(10)  # give API time to recover
                if x == tries:
                    log().error("max tries reached. Quitting.")
                    return

        full_comp_dfs.append(full_comp_df_output)  # add to output data frame

    # now build the final data frame
    full_comp_final = pd.concat(full_comp_dfs,
                                sort=False).drop_duplicates(subset='id', keep='last').sort_values(
        by=["componentType",
            "name"])  # we are keeping the last because if sth is shared with all, this is the most relevant information

    if definition_ids_only is True:
        if copy_original_def is True:  # create a column with a copy of the original definition
            full_comp_final["definition_original"] = full_comp_final["definition"]
        full_comp_final["definition"] = full_comp_final["definition"].map(
            lambda value: ids_from_comp_definition(value))

    if "owner" in full_comp_final.columns:
        full_comp_final["owner_id"], full_comp_final["owner_name"], full_comp_final["owner_login"] = [
            not_supported_text, default_text_owner_cols, default_text_owner_cols]
        if hash_pii is False:
            # fill owner_id, _name, _login
            full_comp_final = full_comp_final.apply(lambda r: get_owner_columns(r, hash=hash_pii),
                                                    axis=1)

        full_comp_final = full_comp_final.drop(columns="owner")
        full_comp_final = movecol(full_comp_final, cols_to_move=["owner_id", "owner_name", "owner_login"], ref_col='id',
                                  place='After')
    if (delocalize is True) & ("modified" in full_comp_final.columns):
        # de-localize modified date so that it can be used for filtering in GSheets
        full_comp_final["modified"] = full_comp_final["modified"].str.replace("T", " ").str.replace("Z", "")

    full_comp_final = full_comp_final.fillna("")

    return full_comp_final


def aa2_get_report_retry(req: str, aa_instance: aanalytics2.Analytics, tries: int = 10, n_res: int = 100,
                         verbose: bool = False,
                         limit: int = 1000) -> pd.DataFrame:
    """uses the AA v2 API (aanalytics2 module) and returns
    the requested report. Retries several times ("tries" parameter) if output is empty (happens often due to API V2.0 instabilities)

    :param limit: row limit per request
    :param verbose: for debugging
    :param req: request as JSON string
    :param tries: number of tries
    :param aa_instance: aanalytics API instance
    :type aa_instance: aanalytics object
    :param n_res: n_result parameter (number of results) for aa v2 request
    :return: dataframe with report data
    """
    result_df = []
    i = 0
    while (len(result_df) == 0) & (i < tries):
        try:
            if i > 0:
                time.sleep(10)  # take a 10-second break before querying right away again
            log().info(f"trying to get data, round {i + 1}")
            result_raw = aa_instance.getReport(req, n_result=n_res, verbose=verbose, limit=limit)
            result_df = result_raw["data"]
            i = i + 1
        except Exception as e:
            log().warning("AA2 API wrapper caused error getting report data: " + str(e))
            i = i + 1
            time.sleep(10)  # give API time to recover
            if i >= tries:
                log().error("max tries reached. Quitting.")
                return result_df
    if i >= tries:
        log().error("Could not get data from Adobe after " + str(i) + " tries. Won't try anymore.")
        return result_df
    else:
        log().info("Successfully got data from Adobe after " + str(i) + " tries.")
        return result_df


def aa2_get_report_retry2(req: dict, aa_instance: aanalytics2.Analytics, tries: int = 10, n_res: int = 100,
                          verbose: bool = False,
                          limit: int = 1000, resolveColumns: bool = False) -> pd.DataFrame:
    """uses the AA v2 API (aanalytics2 module) new getReport2 method and returns
    the requested report. Retries several times ("tries" parameter) if output is empty (happens often due to API V2.0 instabilities)

    :param limit: row limit per request
    :param verbose: for debugging
    :param req: request as JSON string
    :param tries: number of tries
    :param aa_instance: aanalytics API instance
    :param resolveColumns: if True, the column IDs will be resolved to their interface names
    :param n_res: n_result parameter (number of results) for aa v2 request

    :return: dataframe with report data
    """
    result_df = []
    i = 0
    if n_res < limit:
        limit = n_res
    while (len(result_df) == 0) & (i < tries):
        try:
            if i > 0:
                time.sleep(10)  # take a 10-second break before querying right away again
            log().info(f"trying to get data, round {i + 1}")
            result_raw = aa_instance.getReport2(req, n_results=n_res, limit=limit, resolveColumns=resolveColumns)
            result_df = result_raw.dataframe
            if "itemId" in result_df.columns:
                result_df = result_df.drop(columns="itemId")
            i = i + 1
        except Exception as e:
            log().warning("AA2 API wrapper caused error getting report data: " + str(e))
            i = i + 1
            time.sleep(10)  # give API time to recover
            if i >= tries:
                log().error("max tries reached. Quitting.")
                return result_df
    if i >= tries:
        log().error("Could not get data from Adobe after " + str(i) + " tries. Won't try anymore.")
        return result_df
    else:
        log().info("Successfully got data from Adobe after " + str(i) + " tries.")
        return result_df


def is_populated(var):
    if var is None:
        return False
    elif var == "":
        return False
    elif type(
            var) == str:  # previous condition is already enough: If it is not "" and it is a string, it cannot be empty
        return True
    elif type(var) == list:
        if len(var) == 0:
            return False


def isnan(val):
    if val != val:  # nan is the only value that is not equal to itself, apparently safest method, see https://towardsdatascience.com/5-methods-to-check-for-nan-values-in-in-python-3f21ddd17eed
        return True
    return False


def norm_columns_for_all_dfs(dfs, cols, incl, default_val):
    output_dfs = []
    for df in dfs:
        for col in cols:
            if col not in dfs[df].columns:
                dfs[df][col] = default_val
        dfs[df] = dfs[df][cols]  # limit the df to the "norm" cols
        dfs[df]["includeType"] = incl
        output_dfs.append(dfs[df])
    return output_dfs


def col2str(col, sep=";", maxlen=20000):
    """
    joins a column's values with a separator and crops to a maximum length
    :param col: pandas Series, e.g. a column, e.g. my_df["mycolumn"]
    :param sep: separator between row values
    :param maxlen: maximum length to output to
    :return: string with joined and cropped values
    """
    return sep.join(col.tolist())[:maxlen]


def movecol(df, cols_to_move=None, ref_col='', place='Before'):
    """Moves a column before or after another column
    @param df: DataFrame to operate on
    @type df: pd.DataFrame
    @param cols_to_move: columns to move
    @type cols_to_move: list
    @param ref_col: reference column name before or after which to move the column (default: to the beginning)
    @type ref_col: str
    @param place: "Before" or "After"
    @type place: str
    @return: DataFrame with reordered columns
    @rtype: pd.DataFrame
    """
    global seg1, seg2
    if cols_to_move is None:
        cols_to_move = []
    tp_colname = ""
    if ref_col == "":  # if nothing is submitted, we add the columns to the very left
        tp_colname = "___tp_col"
        df.insert(0, tp_colname, 0)  # insert right after the index
        ref_col = tp_colname
    cols = df.columns.tolist()
    if place == 'Before':
        seg1 = cols[:list(cols).index(ref_col)]
        seg2 = cols_to_move + [ref_col]
    elif place == 'After':
        seg1 = cols[:list(cols).index(ref_col) + 1]
        seg2 = cols_to_move

    seg1 = [i for i in seg1 if i not in seg2]
    seg3 = [i for i in cols if i not in seg1 + seg2]
    df = df[seg1 + seg2 + seg3]
    if tp_colname != "":  # if we created a temp column because we wanted to add to the very left, we delete it again
        cols = df.columns.tolist()  # reflect the new order
        cols.pop(cols.index(tp_colname))  # actually pop(0) would be enough
        df = df[cols]
    return df


def log_component_editor_error(filename="no filename passed", err=None, gsheets_id=None):
    """
    logs errors for the component editor to StackDriver Logs and to the Google Sheet that called the function
    :param filename: filename where the error occurred
    :param err: error object (Exception)
    :type err: object
    :param gsheets_id: Google Sheets ID to where log the error
    :return: the error object with the message and the timestamp (a format required by monitor_component_editor
    :rtype: dict
    """
    if gsheets_id is None:
        gsheets_id = "no_sheet_id_provided"
    if err is None:
        err = "undefined error"
    fname = os.path.basename(filename)
    err_str = str(err)
    msg = "Component Manager Error in " + fname + ": " + err_str
    log().error(msg)
    ts = get_datesuffix()
    if gsheets_id != "no_sheet_id_provided":
        from dim28etl.sheets.gsheets_comp_editor import update_status
        update_status(sheet_id=gsheets_id, text=msg)
    return {"err": err, "msg": msg, "ts": ts}


def safe_cast_list(obj: dict, key: str, value: object, prepend=False, trim=0, uniques=False,
                   reverse_sort_uniques=False):
    """
    safely updates or creates a list within a dictionary with some options.
    If list does not exist yet, creates a list as a key of a dictionary, then sets the first value
    :param obj: dictionary object for which to set / update the list
    :type obj: dict
    :param key: the key for the list within the dict we want to set or update
    :type key: str
    :param value: value to add to the the list
    :type value: any
    :param prepend: whether to prepend the value to the list
    :type prepend: bool
    :param trim: 50 trims the array to the first 50 elements, 0 does not trim
    :type trim: int
    :param uniques: returns a unique list (in case an element is added twice)
    :type uniques: bool
    :param reverse_sort_uniques: if True, the uniques (see param uniques) will be sorted in reverse order, otherwise in alphanumerical order
    :type reverse_sort_uniques: bool
    :returns: the updated object
    :rtype: dict
    """
    if key not in obj.keys():
        obj[key] = []
    elif type(obj[key]) != list:
        obj[key] = []
    if prepend:
        obj[key].insert(0, value)
    else:
        obj[key].append(value)
    if trim:
        obj[key] = obj[key][:trim]
    if uniques:
        obj[key] = unique_list(obj[key])
        obj[key].sort(reverse=reverse_sort_uniques)
    return obj


def unique_list(li):
    """
    Takes a list and returns only the unique values of that list
    @param li: list to uniquify
    @type li: list
    @return: uniquified list
    @rtype: list
    """
    return list(set(li))


def safe_get_dict(d: dict = None, key: str = None, default: object = None):
    """
    safely returns a value from a dictionary, if the key does not exist, returns the default value
    :param d: dictionary to get the value from
    :type d: dict
    :param key: key to get the value from
    :type key: str
    :param default: default value to return if key does not exist
    :type default: object
    :returns: the value or the default value
    :rtype: object
    """
    if type(d) is not dict:
        return default
    return d.get(key, default)


def safe_get_index(l, idx, default=None):
    """Safely gets a list index, e.g. listname[4] and returns the default if not found.
    :param l: list to check
    :type l: list
    :param idx: index to check
    :param default: Default value to return if index doesn't exist
    :return: value of index or default
    """
    try:
        return l[idx]
    except IndexError:
        return default


def monitor_script(script: str = None, start: bool = False, stop: bool = False, completed: bool = False,
                   run_id: str = "n_a", type: str = "n_a", result: str = "n_a",
                   error: bool = False, comp_mgr_info: dict = None) -> None:
    """sets script monitoring variables depending on whether the script has started, stopped (incl logic for fails),
     or completed"""

    log().info("starting monitor of scheduled scripts with arguments: ")
    log().info(locals())
    # create a document for this script if it does not exist yet
    now = DatetimeWithNanoseconds.now(timezone.utc)
    # get the scripts/globalStatus doc

    # removed from dim28-comp-mgr project
    # status_doc = FireRef.scripts().document("globalStatus")
    # status_dict = status_doc.get().to_dict()
    # end removed

    if start:
        # create a doc for the run id
        # get the template to make sure all fields are there in case the default changes in the future
        running_doc = FireRef.scriptRuns().document("template").get().to_dict()
        running_doc["started"] = now
        running_doc["id"] = run_id
        running_doc["scriptType"] = type
        running_doc["scriptName"] = script
        running_doc["running"] = True
        if comp_mgr_info is not None:
            running_doc["company"] = comp_mgr_info["company"]
            running_doc["sheetId"] = comp_mgr_info["sheet"]

        FireRef.scriptRuns().document(run_id).create(running_doc)

        # removed from dim28-comp-mgr
        # safe_cast_list(status_dict, "running", script, prepend=True)
        # safe_cast_list(status_dict, "lastStarted", {"script": script, "timestamp": now, "runId": run_id}, prepend=True,
        #               trim=200)
        # end removed

    elif stop:
        # get the running doc by id
        running_doc = FireRef.scriptRuns().document(run_id).get().to_dict()
        running_doc["running"] = False
        running_doc["stopped"] = now
        running_doc["result"] = str(result)
        if error:
            running_doc["error"] = True

        # removed from dim28-comp-mgr
        # safe_cast_list(status_dict, "lastStopped", {"script": script, "timestamp": now, "runId": run_id}, prepend=True,
        #                trim=200)

        # # remove from running scripts
        # status_dict["running"] = list_rembyval(status_dict["running"], script)
        # end removed

        if completed:
            # sets the last complete run to the first Array element
            running_doc["completed"] = now
            duration = now - running_doc["started"]
            running_doc[
                "durationSeconds"] = duration.total_seconds()  # to have sth as a number for calculation (will give eg 42.432)
            running_doc["duration"] = str(
                duration)  # duration as string ("00:00:42.090") because firestore cannot save datetype timedelta

            # removed from dim28-comp-mgr
            # safe_cast_list(status_dict, "lastCompleted", {"script": script, "timestamp": now, "runId": run_id},
            #                prepend=True,
            #                trim=200)  # save last 200 completions for the overview
            # end removed

        # update document with this ID (only on stop, because on start, we create the doc!)
        FireRef.scriptRuns().document(run_id).update(running_doc)

    # removed from dim28-comp-mgr
    # status_doc.set(status_dict)
    # removed end

    log().info(f"Updated firestore script monitoring data for run id {run_id}")
    return


def firedocs_to_df(reference, top=1000, order="id", direction="DESCENDING"):
    stream = reference.limit(top).order_by(order, direction=direction).stream()
    arr = []
    for doc in stream:
        arr.append(doc.to_dict())
    return pd.DataFrame(arr)  # .set_index("id")


def increment_counter(script_obj, type, increment_by=1):
    if "counter" not in script_obj.keys():
        script_obj["counter"] = {type: 0}
    if type not in script_obj["counter"].keys():
        script_obj["counter"][type] = 0
    script_obj["counter"][type] = script_obj["counter"][type] + 1
    return script_obj


def get_alphanum_index(ind):
    """takes a variable name (e.g. "variables/evar18.2") and turns it into an alphanumeric sortable value
    (e.g. "evar0018.0002")
    @param ind: variable id (usually index)
    @type ind: str
    @return alphanumerically sortable string
    @rtype: str
    """
    type_numvar = re.compile("evar|prop|list|event")
    num_var = True
    regex = re.compile('\/([a-z]+)(|(\d+)(|\.(\d+)))$')
    if len(re.findall(type_numvar, ind)) == 0:
        num_var = False
        regex = re.compile('\/([a-z]+)(|\.(\d+))$')

    extracts = re.findall(regex, ind)[0]
    new_ind = extracts[0]
    if num_var is True:
        if extracts[2] != '':
            new_ind += f"{int(extracts[2]):05d}"
        if extracts[4] != '':
            new_ind += "." + f"{int(extracts[4]):04d}"
    else:
        if extracts[2] != '':
            new_ind += "." + f"{int(extracts[2]):04d}"
    return new_ind


def monitor_comp_manager(company=None, script=None, sheet='not_provided', start=False, stop=False, completed=False,
                         script_result=None, run_id="n_a"):
    """sets script monitoring variables for component manager scripts
    :param start: True if before start of script
    :param end: True if after script
    :returns: config object for monitoring
    """
    log().info(f"starting monitor of component manager with arguments:\n{locals()}")

    unmonitored_scripts = ["update_components_usage", "monitor_update_comp_usage", "monitor_delete_workspaces",
                           "workspaces_delete", "update_account_usage"]
    now = DatetimeWithNanoseconds.now(timezone.utc)
    update_contract_info = False
    # get the script document
    company_ref = FireRef.cmc_company(company)
    company_dict = company_ref.get().to_dict()
    error = False
    if script_result is not None:
        if script_result == "done":
            completed = True
        elif type(script_result) == dict:
            if "err" in script_result.keys():
                error = script_result
        else:  # if script result is e.g. simply an error
            log().warning(f"Unexpected Script Result: {script_result}")

    if start:
        if script not in company_dict["scripts"]:
            # create scripts dict if non-existent yet for company
            company_dict["scripts"][script] = {
                "runs": [],
                "errors": [],
                "counter": {
                    "completions": 0,
                    "starts": 0,
                    "stops": 0,
                    "duration": 0
                }
            }

        company_dict["scripts"][script]["runs"] = [{
            "sheetId": sheet,
            "started": now,
            "runId": run_id
        }] + company_dict["scripts"][script]["runs"]  # prepend new run to runs array
        increment_counter(company_dict["scripts"][script], "starts")
        scr_dict = {
            "timestamp": now,
            "sheetId": sheet,
            "scriptName": script,
            "runId": run_id
        }
        contract = company_dict.get("contract")
        if now > contract["end"]:
            log().error(f"Contract of company {company} has expired!")
            end_formatted = contract["end"].strftime('%b %d %Y, %H:%M')
            update_contract_info = True  # updates Gsheet with updated contract info after the run
            company_dict["contract"]["expired"] = True
        safe_cast_list(company_dict, "runningScripts", scr_dict, prepend=True)
        if script not in unmonitored_scripts:  # to not spam the "last started scripts" with all those monitor runs
            safe_cast_list(company_dict, "lastStartedScripts", scr_dict, prepend=True, trim=50)

    if stop:
        increment_counter(company_dict["scripts"][script], "stops")
        rs = company_dict["runningScripts"]
        y = 0
        for x in range(len(rs)):
            if rs[y]['scriptName'] == script:
                log().info(f"Removing script {script} from runningScripts because it is not running anymore")
                del rs[y]
            else:
                y = y + 1

        company_dict["runningScripts"] = rs
        log().info(f"runningScripts after update (before push to firestore): {rs}")

        if completed:
            log().info(f"Script {script} was completed. Now updating Firestore with this info.")
            increment_counter(company_dict["scripts"][script], "completions")
            # todo this can be problematic as it assumes the first element in runs ([0]) is always the current run.
            #  Another run could have happened in the meantime and completed faster
            #  Better get the currently running script by searching for the element for the script run ID.
            company_dict["scripts"][script]["runs"][0]["completed"] = now
            # duration in minutes
            last_start = company_dict["scripts"][script]["runs"][0]["started"]
            last_completed = company_dict["scripts"][script]["runs"][0]["completed"]
            duration = round((last_completed - last_start).seconds / 60,
                             2)
            increment_counter(company_dict["scripts"][script], "duration", increment_by=duration)
            company_dict["scripts"][script]["runs"][0]["duration"] = duration
            company_dict["scripts"][script]["runs"][0]["runId"] = run_id
            company_dict["scripts"][script]["runs"] = company_dict["scripts"][script]["runs"][:50]
    if error:
        log().info(
            f"Error in payload. Storing in Firestore in errors array for script {script} as first element.")
        increment_counter(company_dict["scripts"][script], "errors")
        msg = str(error)
        if "msg" in error.keys():
            msg = str(error["msg"])
        safe_cast_list(company_dict["scripts"][script], "errors",
                       {"timestamp": now, "message": msg, "sheetId": sheet, "runId": run_id},
                       prepend=True, trim=10)

    # update company data
    company_ref.set(company_dict)
    if update_contract_info is True:
        from dim28etl.config.update_contract_info import run_script as update_contract_info
        update_contract_info(company=company, gsheets_id=sheet)  # write contract info to sheet
    log().info(
        f"Updated firestore script monitoring data for company {company}, script {script}")
    return company_dict


def verify_sheet_id(company_dict: dict = None, sheet: str = None, company: str = None,
                    update_firestore: bool = False) -> dict:
    """
    Verifies that the sheet ID provided actually belongs to the company.
    If it is verified successfully, but the sheet ID does not yet exist in the company dict in Firestore, it is added.
    :param company_dict: dict of company data from Firestore
    :param sheet: sheet ID to verify
    :param company: company name
    :param update_firestore: if True, the company dict in Firestore is updated with the sheet ID
    :return: updated company_dict
    """
    existing_sheets = company_dict.get("sheets", [])
    if sheet in existing_sheets:
        log().info(f"Sheet ID {sheet} is already in Firestore for company {company}")
        return company_dict

    # otherwise:
    log().info(f"Sheet {sheet} not yet in company dict for {company}. Checking if we shall add it now.")
    # check if sheet has the same company id (it may accidentally happen during testing that we send payloads
    # with the ID of another sheet)
    from dim28etl.sheets.gsheets_comp_editor import get_config
    sheet_company = get_config(sheet_id=sheet, key="company")
    if sheet_company == company:
        safe_cast_list(company_dict, "sheets", sheet, prepend=False, uniques=True)
        if update_firestore is True:
            log().info(f"Sheet ID {sheet} not yet in list of sheets for company ({existing_sheets}). Adding it.")
            FireRef.cmc_company(company).set(company_dict)
        return company_dict
    raise Exception(
        f"Sheet ID {sheet} provided in payload is of another company ID ({sheet_company} instead of {company})!")


def aa_verify_admin_rights(ags=None) -> bool:
    """Verifies that the user has Admin rights for the company. Throws Exception if not."""
    log().info("Getting my own user")
    me = ags.getUserMe()
    my_id = me["loginId"]
    my_email = me["email"]
    # fail this already bc probably normal users cannot get a list of all users
    log().info("Trying to get list of all users in company")
    users = ags.getUsers()
    if len(users) == 0:
        raise Exception(f"Cannot get user list, user {my_email} probably has insufficient (=no Admin) rights")

    my_user = users[users['loginId'] == my_id]
    if str(my_user["admin"].iloc[0]) == "True":
        log().info(f"User {my_email} was successfully verified as an Admin")
        return True

    raise Exception(f"User {my_email} has no Admin rights to Adobe Analytics.")


def handle_comp_mgr_scripts(script: str = None, payload: dict = None, run_id: str = None):
    """Monitors Component Manager Scripts"""
    script_result = None
    # scripts that should  have such frequent runs
    # that monitoring them just spams the firedoc. They have their own monitoring documents (e.g. longScriptsMonitor)
    unmonitored_scripts = ["update_components_usage", "monitor_update_comp_usage", "monitor_delete_workspaces",
                           "workspaces_delete", "update_account_usage"]
    free_scripts = ["workspaces_refresh", "comp_refresh", "update_contract_info", "edit_report_suite_vars",
                    "refresh_report_suites", "update_account_usage", "report_builder_delete_schedule",
                    "report_builder_run_report", "report_builder_create_schedule"]
    # todo add logic that only max 3 reports are allowed for free clients
    # generate the script run id out of script name + run id
    script_type = "comp_mgr"
    run_id = run_id + "-" + payload['script']
    cfg.SCRIPT_RUN_ID = run_id
    company = payload.get("company", "n_a")
    sheet = payload.get("gsheets_id", "n_a")
    comp_mgr_info = {"sheet": sheet, "company": company}
    if script not in unmonitored_scripts:
        monitor_script(start=True, script=script, run_id=run_id, type=script_type, comp_mgr_info=comp_mgr_info)
    else:
        log().info(f"{script} among unmonitored scripts. Will not show up among Firestore 'scriptRuns' documents.")

    company_dict = monitor_comp_manager(company=company, sheet=sheet, script=script, start=True, run_id=run_id)
    # check if sheet ID is not among already existing sheets in company dict
    company_dict = verify_sheet_id(company_dict=company_dict, sheet=sheet, company=company, update_firestore=True)

    # check if contract expired
    payload["is_paid_contract"] = cfg.is_paid_contract(
        company_dict)  # to enable certain functionality in scripts that is for paid contracts only
    if payload["is_paid_contract"] is False:
        if script not in free_scripts:
            log().error(f"Stopping execution because contract expired and script {script} not among free scripts.")
            from dim28etl.sheets.gsheets_comp_editor import update_status
            update_status(sheet_id=sheet, cats="all",
                          text="You tried to run a feature that is not part of the free version. "
                               "Please contact component-manager@datacroft.de to upgrade.")
            monitor_script(stop=True, completed=False, script=script, run_id=run_id, result="not a free feature",
                           type=script_type, error=False,
                           comp_mgr_info=comp_mgr_info)
            return
    # for scripts that require Virtual Report Suite IDs
    vrsids = []
    if 'vrsids' in payload.keys():
        vrsids = payload['vrsids']

    script_started = False
    # generic (same payload structure) component manager scripts
    if script == "update_contract_info":
        from dim28etl.config.update_contract_info import run_script
    elif script == "edit_report_suite_vars":
        from dim28etl.adobe.components.report_suites.edit_report_suite_vars import run_script
    elif script == "update_components_usage":
        from dim28etl.adobe.components.comp_usage.update_component_usage import run_script
    elif script == "monitor_update_comp_usage":
        from dim28etl.adobe.components.comp_usage.monitor_update_comp_usage import run_script
    elif script == "workspaces_refresh":
        from dim28etl.adobe.components.workspaces.get_upload_projects import run_script
    elif script == "workspaces_delete":
        from dim28etl.adobe.components.workspaces.delete_workspaces import run_script
    elif script == "monitor_delete_workspaces":
        from dim28etl.adobe.components.workspaces.monitor_delete_workspaces import run_script
    elif script == "replace_components":
        from dim28etl.adobe.components.comp_replacer.replace_components import run_script
    elif script == "refresh_report_suites":
        from dim28etl.adobe.components.report_suites.refresh_report_suites import run_script
    elif script == "update_account_usage":
        from dim28etl.adobe.components.account_usage.update_account_usage import run_script
    elif script == "compare_report_suites":
        from dim28etl.adobe.components.report_suites.compare_report_suites import run_script
    elif script == "suggest_duplicates_to_harmonize":
        from dim28etl.adobe.components.comp_replacer.suggest_duplicates_to_harmonize import run_script
    elif script == "report_builder_delete_schedule":
        from dim28etl.adobe.components.report_builder.report_builder_delete_schedule import run_script
    elif script == "report_builder_create_schedule":
        from dim28etl.adobe.components.report_builder.report_builder_create_schedule import run_script
    elif script == "report_builder_run_schedules":
        from dim28etl.adobe.components.report_builder.report_builder_run_schedules import run_script
    elif script == "report_builder_run_report":
        from dim28etl.adobe.components.report_builder.report_builder_run_report import run_script
    if "run_script" in locals():  # generic script with the same parameters every time
        script_result = run_script(company=company,
                                   gsheets_id=sheet,
                                   payload=payload,
                                   force_run=False)  # todo unify with other script call (switch to use args/kwargs)
        script_started = True
    # component "editor" scripts
    if script_started is False:
        if script == "comp_update":
            from dim28etl.adobe.components.comp_editor.update_components import run_script
        elif script == "comp_refresh":
            from dim28etl.adobe.components.comp_editor.orchestrator_get_upload_comp import run_script
        if "run_script" in locals():  # generic script with the same parameters always
            script_result: object = run_script(vrsids=vrsids, company=company, gsheets_id=sheet, payload=payload)
            script_started = True

    if script_started is False:
        log().error("unknown script name:" + script)
        return

    completed = False
    result_msg = script_result
    err = False
    if script_result is not None:
        if script_result == "done":
            completed = True
        elif type(script_result) == dict:
            # if we want to return completion ("done") PLUS a certain message (e.g. to show in the UI via synch gcf),
            # we expect a dict with keys "result": "done" and "message": "message text"
            if script_result.get("result", None) == "done":
                completed = True
                result_msg = script_result.get("message", "done")
            # caught errors are expected to be returned as { "err": error, "msg": "error_message" }
            elif "err" in script_result.keys():
                result_msg = script_result.get("msg")
                err = True
    if script not in unmonitored_scripts:
        monitor_script(stop=True, completed=completed, script=script, run_id=run_id, result=result_msg,
                       type=script_type, error=err,
                       comp_mgr_info=comp_mgr_info)  # todo improve handling of returned errors

    monitor_comp_manager(company=company, sheet=sheet, stop=True, script=script,
                         script_result=script_result, run_id=run_id)

    return result_msg


def dashdate(date):
    return date.strftime("%Y-%m-%d")


def nownano():
    return DatetimeWithNanoseconds.now(timezone.utc)
