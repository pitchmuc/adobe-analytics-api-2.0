"""Offline tests for getProjects (no network, no credentials needed). See issue #112."""
import os
import sys
import inspect

import pandas as pd
import pytest

current_dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)
from aanalytics2.aanalytics2 import Analytics

ERROR_BODY = {
    "errorCode": "forbidden",
    "errorDescription": "User does not have access to projects",
    "errorId": "abc-123",
}

PROJECTS = [
    {"id": "p1", "name": "Project 1", "created": "2026-01-01T00:00:00Z", "modified": "2026-01-02T00:00:00Z"},
]


class FakeConnector:
    def __init__(self, response):
        self.response = response

    def getData(self, url, params=None, headers=None, **kwargs):
        return self.response


def make_analytics(response) -> Analytics:
    """Builds an Analytics instance without running __init__ (which would need a real token)."""
    ags = Analytics.__new__(Analytics)
    ags.endpoint_company = "https://analytics.adobe.io/api/comp1"
    ags.header = {}
    ags.loggingEnabled = False
    ags.connector = FakeConnector(response)
    return ags


def test_error_body_raises_a_clear_error():
    with pytest.raises(ValueError, match="forbidden: User does not have access to projects"):
        make_analytics(ERROR_BODY).getProjects()


def test_error_body_is_returned_unchanged_in_raw_format():
    assert make_analytics(ERROR_BODY).getProjects(format="raw") == ERROR_BODY


def test_project_list_still_returns_a_dataframe():
    df = make_analytics(PROJECTS).getProjects()
    assert isinstance(df, pd.DataFrame)
    assert df["id"].tolist() == ["p1"]
    assert str(df["created"].dtype).startswith("datetime64")


def test_empty_project_list_returns_an_empty_dataframe():
    assert make_analytics([]).getProjects().empty
