"""Offline tests for the DPC-specific Scheduler endpoint resolution (no network, no credentials needed)."""
import os
import sys
import inspect
import warnings

import pytest

current_dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)
from aanalytics2.aanalytics2 import Analytics

DISCOVERY_URL = "https://analytics.adobe.io/discovery/me"
DISCOVERY_RESPONSE = {
    "imsOrgs": [
        {"imsOrgId": "ORG1@AdobeOrg",
         "companies": [{"globalCompanyId": "other1", "companyName": "Other", "dpc": "sin"}]},
        {"imsOrgId": "ORG2@AdobeOrg",
         "companies": [{"globalCompanyId": "comp1", "companyName": "Company 1", "dpc": "pnw"},
                       {"globalCompanyId": "comp2", "companyName": "Company 2", "dpc": "lon"}]},
    ]
}


class FakeConnector:
    """Records all request URLs and returns canned responses per URL."""

    def __init__(self, responses: dict):
        self.responses = responses
        self.calls = []

    def getData(self, url, params=None, headers=None, **kwargs):
        self.calls.append(url)
        return self.responses[url]

    def postData(self, url, data=None):
        return self.getData(url)

    def putData(self, url, data=None):
        return self.getData(url)

    def deleteData(self, url):
        return self.getData(url)


def make_analytics(company_id: str, responses: dict) -> Analytics:
    """Builds an Analytics instance without running __init__ (which would need a real token)."""
    ags = Analytics.__new__(Analytics)
    ags.company_id = company_id
    ags.endpoint_company = f"{Analytics._endpoint}/{company_id}"
    ags.schedulerEndpoint = None
    ags.header = {}
    ags.loggingEnabled = False
    ags.connector = FakeConnector(responses)
    return ags


def test_resolves_dpc_of_matching_company():
    ags = make_analytics("comp2", {DISCOVERY_URL: DISCOVERY_RESPONSE})
    assert ags._getSchedulerEndpoint() == "https://analytics.lon.appsvc.an.adobe.com/analytics/1.0/scheduler"
    ags = make_analytics("comp1", {DISCOVERY_URL: DISCOVERY_RESPONSE})
    assert ags._getSchedulerEndpoint() == "https://analytics.pnw.appsvc.an.adobe.com/analytics/1.0/scheduler"
    ags = make_analytics("other1", {DISCOVERY_URL: DISCOVERY_RESPONSE})
    assert ags._getSchedulerEndpoint() == "https://analytics.sin.appsvc.an.adobe.com/analytics/1.0/scheduler"


def test_endpoint_is_cached_and_discovery_called_once():
    ags = make_analytics("comp1", {DISCOVERY_URL: DISCOVERY_RESPONSE})
    first = ags._getSchedulerEndpoint()
    second = ags._getSchedulerEndpoint()
    assert first == second
    assert ags.schedulerEndpoint == first
    assert ags.connector.calls == [DISCOVERY_URL]


def test_manual_override_skips_discovery():
    ags = make_analytics("comp1", {})
    ags.schedulerEndpoint = "https://example.test/scheduler"
    assert ags._getSchedulerEndpoint() == "https://example.test/scheduler"
    assert ags.connector.calls == []


@pytest.mark.parametrize("response", [
    DISCOVERY_RESPONSE,  # company not in response
    {"imsOrgs": [{"companies": [{"globalCompanyId": "unknown"}]}]},  # company without dpc
    {"error_code": "401013", "message": "Oauth token is not valid"},  # error response
])
def test_raises_if_dpc_cannot_be_determined(response):
    ags = make_analytics("unknown", {DISCOVERY_URL: response})
    with pytest.raises(Exception, match="dpc"):
        ags._getSchedulerEndpoint()
    assert ags.schedulerEndpoint is None


def test_scheduler_methods_use_resolved_endpoint():
    base = "https://analytics.pnw.appsvc.an.adobe.com/analytics/1.0/scheduler"
    ags = make_analytics("comp1", {
        DISCOVERY_URL: DISCOVERY_RESPONSE,
        base + "/scheduledjobs/": {"content": [{"id": "job1"}], "lastPage": True},
        base + "/deliverysettings/": {"content": [{"id": "ds1"}]},
    })
    with pytest.warns(UserWarning, match="Unofficial endpoints"):
        assert ags.getScheduledJobs(format="raw") == [{"id": "job1"}]
    with pytest.warns(UserWarning, match="Unofficial endpoints"):
        assert ags.getDeliverySettings() == [{"id": "ds1"}]
    assert ags.connector.calls == [DISCOVERY_URL, base + "/scheduledjobs/", base + "/deliverysettings/"]


@pytest.mark.parametrize("method_name, method_kwargs, path", [
    ("getScheduledJobs", {"format": "raw"}, "/scheduledjobs/"),
    ("getScheduledJob", {"scheduleId": "job1"}, "/scheduledjobs/job1"),
    ("createScheduledJob", {"projectId": "project1", "schedule": {"type": "daily"}}, "/scheduledjobs/"),
    ("updateScheduledJob", {"scheduleId": "job1", "scheduleObj": {}}, "/scheduledjobs/job1"),
    ("deleteScheduledJob", {"scheduleId": "job1"}, "/scheduledjobs/job1"),
    ("getDeliverySettings", {}, "/deliverysettings/"),
    ("getDeliverySetting", {"deliverySettingId": "ds1"}, "/deliverysettings/ds1/"),
    ("createDeliverySetting", {}, "/deliverysettings/"),
    ("updateDeliverySetting", {"deliveryId": "ds1"}, "/deliverysettings/ds1"),
    ("deleteDeliverySetting", {"deliveryId": "ds1"}, "/deliverysettings/ds1"),
])
@pytest.mark.parametrize("warning_kwargs, expected_count", [({}, 1), ({"showWarning": False}, 0)])
def test_scheduler_warning_and_opt_out(method_name, method_kwargs, path, warning_kwargs, expected_count, monkeypatch):
    base = "https://example.test/scheduler"
    response = {"id": "job1", "content": [{"id": "job1"}], "lastPage": True}
    ags = make_analytics("comp1", {
        base + path: response,
        base + "/deliverysettings/": {"id": "ds1", "content": [{"id": "ds1"}]},
    })
    ags.schedulerEndpoint = base
    if method_name == "createScheduledJob":
        ags.connector.config = {"org_id": "ORG2@AdobeOrg"}
        monkeypatch.setattr(ags, "getUserMe", lambda: {"imsUserId": "user1"})
        monkeypatch.setattr(ags, "getProject", lambda project_id: {"id": project_id, "name": "Project 1"})
    method = getattr(ags, method_name)
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        caller_line = inspect.currentframe().f_lineno + 1
        method(**method_kwargs, **warning_kwargs)
    assert len(captured) == expected_count
    if expected_count:
        assert str(captured[0].message) == "Unofficial endpoints and may change or break at any moment."
        assert captured[0].category is UserWarning
        assert captured[0].filename == __file__
        assert captured[0].lineno == caller_line
    expected_calls = [base + path]
    if method_name == "createScheduledJob":
        expected_calls.insert(0, base + "/deliverysettings/")
    assert ags.connector.calls == expected_calls


@pytest.mark.parametrize("method_name, path", [
    ("getScheduledJobs", "/scheduledjobs/"),
    ("getDeliverySettings", "/deliverysettings/"),
])
@pytest.mark.parametrize("warning_kwargs, expected_count", [({}, 1), ({"showWarning": False}, 0)])
def test_paginated_scheduler_warning_is_emitted_once(method_name, path, warning_kwargs, expected_count, monkeypatch):
    base = "https://example.test/scheduler"
    ags = make_analytics("comp1", {})
    ags.schedulerEndpoint = base

    def get_page(url, params=None, headers=None):
        ags.connector.calls.append(url)
        if params["page"] == 0:
            return {"content": [{"id": "first"}] * 1000, "lastPage": False}
        return {"content": [{"id": "last"}], "lastPage": True}

    monkeypatch.setattr(ags.connector, "getData", get_page)
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        result = getattr(ags, method_name)(**warning_kwargs)
    assert len(captured) == expected_count
    assert len(result) == 1001
    assert ags.connector.calls == [base + path, base + path]
