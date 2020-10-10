import pytest
import os
import sys
import inspect
current_dir = os.path.dirname(os.path.abspath(
    inspect.getfile(inspect.currentframe())))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)
import aanalytics2

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
    aanalytics2.importConfigFile('/test/config_analytics.json')
    assert aanalytics2.config.config_object['org_id'] != ""
    assert aanalytics2.config.config_object['api_key'] != ""
    assert aanalytics2.config.config_object['tech_id'] != ""
    assert aanalytics2.config.config_object['pathToKey'] != ""
    assert aanalytics2.config.config_object['secret'] != ""


def test_token():
    connector = aanalytics2.connector.AdobeRequest()
    assert connector.token != ""
    