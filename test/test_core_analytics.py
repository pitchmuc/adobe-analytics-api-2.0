import pytest
import os
import sys
import inspect
## changing current_dir to ensure you are running test on your version of the aanalytics2 module.
current_dir = os.path.dirname(os.path.abspath(
    inspect.getfile(inspect.currentframe())))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)
import aanalytics2 as api2
import pandas as pd

def test_createFile():
    files = os.listdir()
    if 'config_analytics_template.json' in files:
        os.remove("config_analytics_template.json")
    api2.createConfigFile()
    files = os.listdir()
    assert 'config_analytics_template.json' in files

def test_importingWrongFile():
    filename = 'test.json'
    with pytest.raises(FileNotFoundError):
        api2.importConfigFile('config_analyticsFail.json')

def test_loading():
    """
    Require to set a config_analytics.json to realize the next tests.
    """
    api2.importConfigFile('./test/config_analytics.json')
    assert api2.config.config_object['org_id'] != ""
    assert api2.config.config_object['client_id'] != ""
    assert api2.config.config_object['scopes'] != ""
    assert api2.config.config_object['secret'] != ""

def test_core_elements():
    api2.importConfigFile('./test/config_analytics.json')
    logger = api2.Login()
    assert len(logger.COMPANY_IDS) == 0
    logger.getCompanyId()
    assert len(logger.COMPANY_IDS) >= 0
    indexCompany = 0
    myCompany = logger.createAnalyticsConnection(logger.COMPANY_IDS[indexCompany]['globalCompanyId'])
    assert isinstance(myCompany,api2.Analytics)
    users = myCompany.getUsers()
    while users.empty:
        indexCompany += 1
        myCompany = logger.createAnalyticsConnection(logger.COMPANY_IDS[indexCompany]['globalCompanyId'])
        users = myCompany.getUsers()
    assert isinstance(users,pd.DataFrame)
    assert len(users)>0
    rsids = myCompany.getReportSuites()
    assert isinstance(rsids,pd.DataFrame)
    singleRSID = rsids.loc[1,'rsid']
    print(f"reportSuite selected : {singleRSID}")
    dims = myCompany.getDimensions(singleRSID)
    assert isinstance(dims,pd.DataFrame)
    assert len(dims)>0
    metrics = myCompany.getMetrics(singleRSID)
    assert isinstance(metrics,pd.DataFrame)
    assert len(metrics)>0
    segs = myCompany.getSegments()
    assert isinstance(segs,pd.DataFrame)
    calcs = myCompany.getCalculatedMetrics()
    assert isinstance(calcs,pd.DataFrame)

