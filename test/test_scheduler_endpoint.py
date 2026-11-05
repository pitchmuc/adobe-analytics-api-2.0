"""Offline tests for the DPC-specific Scheduler endpoint resolution (no network, no credentials needed)."""
import os
import sys
import inspect

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
    """Records all getData calls and returns canned responses per URL."""

    def __init__(self, responses: dict):
        self.responses = responses
        self.calls = []

    def getData(self, url, params=None, headers=None, **kwargs):
        self.calls.append(url)
        return self.responses[url]


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
    assert ags.getScheduledJobs(format="raw") == [{"id": "job1"}]
    assert ags.getDeliverySettings() == [{"id": "ds1"}]
    assert ags.connector.calls == [DISCOVERY_URL, base + "/scheduledjobs/", base + "/deliverysettings/"]
