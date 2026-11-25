"""Offline tests for getSegments (no network, no credentials needed)."""
import os
import sys
import inspect

current_dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)
from aanalytics2.aanalytics2 import Analytics


class RecordingConnector:
    """Returns one empty last page and records the params of each request."""

    def __init__(self):
        self.calls = []

    def getData(self, url, params=None, headers=None, **kwargs):
        self.calls.append(dict(params or {}))
        return {"content": [], "lastPage": True}


def make_analytics() -> Analytics:
    """Builds an Analytics instance without running __init__ (which would need a real token)."""
    ags = Analytics.__new__(Analytics)
    ags.endpoint_company = "https://analytics.adobe.io/api/comp1"
    ags.header = {}
    ags.loggingEnabled = False
    ags.connector = RecordingConnector()
    return ags


def test_sidFilter_is_sent_as_segmentFilter():
    ags = make_analytics()
    ags.getSegments(sidFilter=["s1", "s2"], format="raw")
    params = ags.connector.calls[0]
    assert params["segmentFilter"] == "s1,s2"
    assert "rsids" not in params


def test_sidFilter_does_not_replace_rsids_list():
    ags = make_analytics()
    ags.getSegments(rsids_list=["rs1"], sidFilter="s1", format="raw")
    params = ags.connector.calls[0]
    assert params["rsids"] == "rs1"
    assert params["segmentFilter"] == "s1"
