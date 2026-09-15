import asyncio
import json
import os
import sys
import inspect

current_dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

from aanalytics2 import workspaceManager as wmmod
from aanalytics2.mcp_server import build_server

# Company-wide lookup tables WorkspaceManager fetches once per instantiation to
# auto-resolve any id/name a caller omits. Faked here so tests never hit the network.
_FAKE_LOOKUPS = (
    {"s1": "Mobile"},                                                   # segments
    {"variables/evar8": "Market Code", "variables/evar3": "Browser"},   # dimensions
    {"metrics/visits": "Visits"},                                       # metrics
    {},                                                                  # calculated metrics
    {},                                                                  # date ranges
)


async def _fake_fetch_all_company_data(self):
    return _FAKE_LOOKUPS


class DummyAnalytics:
    def getUserMe(self):
        return {"loginId": 1, "name": "Test", "login": "test@example.com"}

    def getReportSuite(self, rsid):
        return {"name": "RS"}

    def createSegmentValidate(self, segmentJSON=None):
        return {"valid": True, "segment": segmentJSON}

    def createSegment(self, segmentJSON=None):
        return {"id": "s_new", **segmentJSON}

    def createCalculatedMetricValidate(self, metricJSON=None):
        return {"valid": True, "metric": metricJSON}

    def createCalculatedMetric(self, metricJSON=None):
        return {"id": "cm_new", **metricJSON}

    def createDateRange(self, dateRangeJSON=None):
        return {"id": "dr_new", **dateRangeJSON}


def _server():
    wmmod.WorkspaceManager._fetch_all_company_data = _fake_fetch_all_company_data
    return build_server(analytics=DummyAnalytics(), company_id="dummy", default_rsid="rs1")


def _call(mcp, name, arguments):
    """Run an MCP tool call synchronously and return its decoded JSON result."""
    result = asyncio.run(mcp.call_tool(name, arguments))
    return json.loads(result[0].text)


def test_add_freeform_accepts_bare_id_strings():
    """metrics/items may be given as bare ID strings (like build_report_request already
    allows for its own `metrics`), not just {"id": ..., "name": ...} dicts — and the
    missing name is auto-resolved from the report suite's components."""
    mcp = _server()
    project = _call(mcp, "create_workspace", {"rsid": "rs1", "name": "My proj"})
    project = _call(mcp, "add_panel", {"project": project, "name": "Panel1"})
    project = _call(mcp, "add_freeform", {
        "project": project,
        "title": "Device Comparison",
        "metrics": ["metrics/visits"],
        "items": ["s1"],
    })
    reportlet = project["definition"]["workspaces"][0]["panels"][-1]["subPanels"][-1]["reportlet"]
    assert reportlet["columnTree"]["nodes"][0]["component"]["__metaData__"]["name"] == "Visits"
    assert reportlet["freeformTable"]["staticRows"][0]["component"]["__metaData__"]["name"] == "Mobile"


def test_add_breakdown_accepts_bare_id_strings_and_resolves_names():
    """add_breakdown's `items` goes through FreeForm.addBreakdown directly, which (unlike
    WorkspaceManager.addFreeform) does not auto-resolve id/name pairs on its own — the MCP
    tool has to run it through the WorkspaceManager's lookup tables itself."""
    mcp = _server()
    project = _call(mcp, "create_workspace", {"rsid": "rs1", "name": "My proj"})
    project = _call(mcp, "add_panel", {"project": project, "name": "Panel1"})
    project = _call(mcp, "add_freeform", {
        "project": project,
        "title": "Device Comparison",
        "metrics": [{"id": "metrics/visits", "name": "Visits"}],
        "items": [{"id": "s1", "name": "Mobile", "type": "Segment"}],
    })
    project = _call(mcp, "add_breakdown", {
        "project": project,
        "table_title": "Device Comparison",
        "items": ["variables/evar8"],
    })
    breakdown = project["definition"]["workspaces"][0]["panels"][-1]["subPanels"][-1]["reportlet"] \
        ["freeformTable"]["breakdowns"][0]
    assert breakdown["staticRows"][0]["component"]["__metaData__"]["name"] == "Market Code"


def test_add_breakdown_unknown_title_lists_available_tables():
    mcp = _server()
    project = _call(mcp, "create_workspace", {"rsid": "rs1", "name": "My proj"})
    project = _call(mcp, "add_panel", {"project": project, "name": "Panel1"})
    project = _call(mcp, "add_freeform", {
        "project": project,
        "title": "Device Comparison",
        "metrics": [{"id": "metrics/visits", "name": "Visits"}],
        "items": [{"id": "s1", "name": "Mobile", "type": "Segment"}],
    })
    try:
        _call(mcp, "add_breakdown", {
            "project": project, "table_title": "wrong title", "items": ["variables/evar8"],
        })
        assert False, "expected a ToolError"
    except Exception as exc:
        assert "Device Comparison" in str(exc)


def test_update_workspace_requires_project_id():
    mcp = _server()
    project = _call(mcp, "create_workspace", {"rsid": "rs1", "name": "My proj"})
    assert "id" not in project
    try:
        _call(mcp, "update_workspace", {"project": project})
        assert False, "expected a ToolError"
    except Exception as exc:
        assert "get_project" in str(exc)


def test_create_segment_passes_definition_through():
    mcp = _server()
    segment = {"name": "Mobile visitors", "rsid": "rs1", "definition": {"container": {}}}
    result = _call(mcp, "create_segment", {"segment": segment})
    assert result["id"] == "s_new"
    assert result["name"] == "Mobile visitors"


def test_validate_segment_returns_api_result():
    mcp = _server()
    segment = {"name": "Mobile visitors", "rsid": "rs1", "definition": {"container": {}}}
    result = _call(mcp, "validate_segment", {"segment": segment})
    assert result["valid"] is True


def test_create_calculated_metric_passes_definition_through():
    mcp = _server()
    metric = {"name": "Bounce rate", "rsid": "rs1", "definition": {"func": "divide"}}
    result = _call(mcp, "create_calculated_metric", {"calculated_metric": metric})
    assert result["id"] == "cm_new"
    assert result["name"] == "Bounce rate"


def test_validate_calculated_metric_returns_api_result():
    mcp = _server()
    metric = {"name": "Bounce rate", "rsid": "rs1", "definition": {"func": "divide"}}
    result = _call(mcp, "validate_calculated_metric", {"calculated_metric": metric})
    assert result["valid"] is True


def test_create_date_range_passes_definition_through():
    mcp = _server()
    date_range = {"name": "Last quarter", "definition": {"dateRangeType": "Fixed"}}
    result = _call(mcp, "create_date_range", {"date_range": date_range})
    assert result["id"] == "dr_new"
    assert result["name"] == "Last quarter"
