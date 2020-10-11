import pytest
import os
import sys
import inspect
current_dir = os.path.dirname(os.path.abspath(
    inspect.getfile(inspect.currentframe())))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)
import aanalytics2
import pandas as pd

def test_createFile():
    files = os.listdir()
    if 'config_analytics_template.json' in files:
        os.remove("config_analytics_template.json")
    aanalytics2.createConfigFile()
    files = os.listdir()
    assert 'config_analytics_template.json' in files

def test_importingWrongFile():
    filename = 'test.json'
    with pytest.raises(FileNotFoundError):
        aanalytics2.importConfigFile('config_analytics.json')

def test_loading():
    """
    Require to set a config_analytics.json to realize the next tests.
    """
    aanalytics2.importConfigFile('/test/config_analytics.json')
    assert aanalytics2.config.config_object['org_id'] != ""
    assert aanalytics2.config.config_object['client_id'] != ""
    assert aanalytics2.config.config_object['tech_id'] != ""
    assert aanalytics2.config.config_object['pathToKey'] != ""
    assert aanalytics2.config.config_object['secret'] != ""

def test_token():
    """
    Test that the config set in the test folder is working
    """
    connector = aanalytics2.connector.AdobeRequest()
    assert connector.token != ""

global logger
global myCompany
global singleRSID

def test_Logger():
    global logger
    logger = aanalytics2.Loggin()
    assert len(logger.COMPANY_IDS) == 0

def test_LoggerConnect():
    logger.getCompanyId()
    assert len(logger.COMPANY_IDS) >= 0

def test_createFromLogger():
    """
    Test to create a company connection from Logger
    """
    global logger
    global myCompany
    myCompany = logger.createAnalyticsConnection(logger.COMPANY_IDS[0]['globalCompanyId'])
    assert isinstance(myCompany,aanalytics2.Analytics)

def test_users():
    users = myCompany.getUsers()
    assert isinstance(users,pd.DataFrame)
    assert len(users)>0

def test_reportSuites():
    global singleRSID
    rsids = myCompany.getReportSuites()
    assert isinstance(rsids,pd.DataFrame)
    singleRSID = rsids.loc[0,'rsid']
    print(f"reportSuite selected : {singleRSID}")

def test_dimensions():
    global singleRSID
    dims = myCompany.getDimensions(singleRSID)
    assert isinstance(dims,pd.DataFrame)
    assert len(dims)>0

def test_metrics():
    global singleRSID
    metrics = myCompany.getMetrics(singleRSID)
    assert isinstance(metrics,pd.DataFrame)
    assert len(metrics)>0

def test_segments():
    segs = myCompany.getSegments()
    assert isinstance(segs,pd.DataFrame)

def test_calcMetrics():
    calcs = myCompany.getCalculatedMetrics()
    assert isinstance(calcs,pd.DataFrame)

