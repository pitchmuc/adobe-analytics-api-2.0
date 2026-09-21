import asyncio
import json
import os
import sys
import inspect

import pandas as pd
from rdflib import Graph, Literal, RDF, RDFS, URIRef, Namespace

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

    def updateSegment(self, segmentID=None, segmentJSON=None):
        return {"id": segmentID, **segmentJSON}

    def createCalculatedMetricValidate(self, metricJSON=None):
        return {"valid": True, "metric": metricJSON}

    def createCalculatedMetric(self, metricJSON=None):
        return {"id": "cm_new", **metricJSON}

    def updateCalculatedMetric(self, calcID=None, calcJSON=None):
        return {"id": calcID, **calcJSON}

    def createDateRange(self, dateRangeJSON=None):
        return {"id": "dr_new", **dateRangeJSON}

    def updateDateRange(self, dateRangeID=None, dateRangeJSON=None):
        return {"id": dateRangeID, **dateRangeJSON}

    def updateProject(self, projectId=None, projectObj=None):
        return {"id": projectId, **projectObj}

    def getSegments(self, name=None, rsids_list=None, extended_info=None, format=None):
        return [{"id": "s_live", "name": "Mobile visitors (live)", "rsid": "rs1", "description": ""}]

    def getCalculatedMetrics(self, name=None, rsids_list=None, extended_info=None, format=None):
        return [{"id": "cm_live", "name": "Bounce rate (live)", "rsid": "rs1", "description": ""}]

    def getReport2(self, request=None, n_results=None, limit=None):
        class _FakeReport:
            dataframe = pd.DataFrame({
                "itemId": ["111", "222"],
                "variables/evar3": ["Chrome", "Firefox"],
                "Visits": [10, 5],
            })
        return _FakeReport()


def _server():
    wmmod.WorkspaceManager._fetch_all_company_data = _fake_fetch_all_company_data
    return build_server(analytics=DummyAnalytics(), company_id="dummy", default_rsid="rs1")


def _build_test_kg():
    """Minimal Knowledge Graph matching the triple shapes KnowledgeGraph.buildGraph()
    produces for Segment/CalculatedMetric nodes (see knowledgeGraph.py's
    build_segment_graph/build_calculated_graph), scoped to company_id="dummy"."""
    g = Graph()
    seg_ns = Namespace("http://analytics.com/dummy/segment#")
    cm_ns = Namespace("http://analytics.com/dummy/calculatedMetric#")
    rs_ns = Namespace("http://analytics.com/dummy/reportSuite#")

    seg_uri = URIRef("http://analytics.com/dummy/segment/s_kg1")
    g.add((seg_uri, RDF.type, Literal("Segment")))
    g.add((seg_uri, RDFS.label, Literal("Mobile Visitors KG")))
    g.add((seg_uri, RDFS.comment, Literal("KG segment description")))
    g.add((seg_uri, seg_ns.id, Literal("s_kg1")))
    g.add((seg_uri, seg_ns.rsid, rs_ns["rs1"]))

    cm_uri = URIRef("http://analytics.com/dummy/calculatedMetric/cm_kg1")
    g.add((cm_uri, RDF.type, Literal("CalculatedMetric")))
    g.add((cm_uri, RDFS.label, Literal("Bounce Rate KG")))
    g.add((cm_uri, cm_ns.id, Literal("cm_kg1")))
    g.add((cm_uri, cm_ns.rsid, rs_ns["rs1"]))
    return g


def _server_with_kg():
    wmmod.WorkspaceManager._fetch_all_company_data = _fake_fetch_all_company_data
    return build_server(
        analytics=DummyAnalytics(), company_id="dummy", default_rsid="rs1", kg_graph=_build_test_kg()
    )


def _call(mcp, name, arguments):
    """Run an MCP tool call synchronously and return its decoded JSON result."""
    result = asyncio.run(mcp.call_tool(name, arguments))
    return json.loads(result.content[0].text)


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


def test_add_breakdown_resolves_dimension_id_without_name():
    """A dynamic breakdown (dimension_id with no dimension_name) must resolve its display
    name the same way add_freeform does, instead of falling back to the raw dimension_id —
    FreeForm.addBreakdown itself has no lookup table and defaults name to the id verbatim."""
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
        "dimension_id": "variables/evar3",
    })
    breakdown = project["definition"]["workspaces"][0]["panels"][-1]["subPanels"][-1]["reportlet"] \
        ["freeformTable"]["breakdowns"][0]
    assert breakdown["dimensionSettings"][0]["dimension"]["__metaData__"]["name"] == "Browser"


def test_add_breakdown_on_dynamic_dimension_table_uses_real_item_ids():
    """When the table's own rows come from a dynamic dimension (item_id, not static items),
    a placeholder parentItemIds like "0" leaves the row with no "+" to expand in Workspace —
    Adobe only recognizes a breakdown anchored to a real itemId. add_breakdown must fetch the
    table's actual top rows via a live report and create one breakdown entry per real itemId."""
    mcp = _server()
    project = _call(mcp, "create_workspace", {"rsid": "rs1", "name": "My proj"})
    project = _call(mcp, "add_panel", {"project": project, "name": "Panel1"})
    project = _call(mcp, "add_freeform", {
        "project": project,
        "title": "Dynamic Table",
        "metrics": ["metrics/visits"],
        "item_id": "variables/evar3",
    })
    project = _call(mcp, "add_breakdown", {
        "project": project,
        "table_title": "Dynamic Table",
        "dimension_id": "variables/evar8",
    })
    breakdowns = project["definition"]["workspaces"][0]["panels"][-1]["subPanels"][-1]["reportlet"] \
        ["freeformTable"]["breakdowns"]
    assert [bd["parentItemIds"] for bd in breakdowns] == [["111"], ["222"]]
    for bd in breakdowns:
        assert bd["dimensionSettings"][0]["dimension"]["__metaData__"]["name"] == "Market Code"


def test_add_breakdown_segment_items_on_dynamic_dimension_table_uses_real_item_ids():
    """Same real-itemId requirement applies to a segment-as-breakdown-row (`items`) breakdown
    when the parent table's own rows are a dynamic dimension, not just a dimension_id breakdown."""
    mcp = _server()
    project = _call(mcp, "create_workspace", {"rsid": "rs1", "name": "My proj"})
    project = _call(mcp, "add_panel", {"project": project, "name": "Panel1"})
    project = _call(mcp, "add_freeform", {
        "project": project,
        "title": "Dynamic Table",
        "metrics": ["metrics/visits"],
        "item_id": "variables/evar3",
    })
    project = _call(mcp, "add_breakdown", {
        "project": project,
        "table_title": "Dynamic Table",
        "items": ["s1"],
    })
    breakdowns = project["definition"]["workspaces"][0]["panels"][-1]["subPanels"][-1]["reportlet"] \
        ["freeformTable"]["breakdowns"]
    assert [bd["parentItemIds"] for bd in breakdowns] == [["111"], ["222"]]
    for bd in breakdowns:
        assert bd["staticRows"][0]["component"]["__metaData__"]["name"] == "Mobile"


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


def test_add_panel_preserves_id_from_fetched_project():
    """A project dict originating from get_project (has a top-level "id") must keep that id
    through add_panel/add_freeform/etc., so it can be round-tripped to update_workspace instead
    of publish_workspace creating an unwanted duplicate. WorkspaceManager.to_dict() previously
    never surfaced self.id at all, silently dropping it on every builder-tool round trip."""
    mcp = _server()
    project = _call(mcp, "create_workspace", {"rsid": "rs1", "name": "My proj"})
    project["id"] = "existing_project_id"  # simulate a project dict fetched via get_project
    project = _call(mcp, "add_panel", {"project": project, "name": "Panel1"})
    assert project["id"] == "existing_project_id"
    result = _call(mcp, "update_workspace", {"project": project})
    assert result["id"] == "existing_project_id"


def test_create_segment_passes_definition_through():
    mcp = _server()
    segment = {"name": "Mobile visitors", "rsid": "rs1", "definition": {"container": {}}}
    result = _call(mcp, "create_segment", {"segment": segment})
    assert result["id"] == "s_new"
    assert result["name"] == "Mobile visitors"


def test_update_segment_passes_id_and_definition_through():
    mcp = _server()
    segment = {"name": "Mobile visitors v2", "rsid": "rs1", "definition": {"container": {}}}
    result = _call(mcp, "update_segment", {"segment_id": "s1", "segment": segment})
    assert result["id"] == "s1"
    assert result["name"] == "Mobile visitors v2"


def test_validate_segment_returns_api_result():
    mcp = _server()
    segment = {"name": "Mobile visitors", "rsid": "rs1", "definition": {"container": {}}}
    result = _call(mcp, "validate_segment", {"segment": segment})
    assert result["valid"] is True


def test_find_segment_uses_knowledge_graph_when_available():
    mcp = _server_with_kg()
    result = _call(mcp, "find_segment", {"name": "Mobile"})
    assert result["source"] == "knowledge_graph"
    assert result["note"] is None
    assert result["results"] == [
        {"id": "s_kg1", "name": "Mobile Visitors KG", "description": "KG segment description", "rsid": "rs1"}
    ]


def test_find_segment_falls_back_when_no_kg_connected():
    mcp = _server()  # built without kg_graph
    result = _call(mcp, "find_segment", {"name": "Mobile"})
    assert result["source"] == "live_api"
    assert "No Knowledge Graph connected" in result["note"]
    assert result["results"][0]["id"] == "s_live"


def test_find_segment_falls_back_when_kg_has_no_match():
    mcp = _server_with_kg()
    result = _call(mcp, "find_segment", {"name": "Nonexistent Segment Name"})
    assert result["source"] == "live_api"
    assert "No matching segment found in the Knowledge Graph" in result["note"]
    assert result["results"][0]["id"] == "s_live"


def test_find_segment_force_live_bypasses_knowledge_graph():
    mcp = _server_with_kg()  # KG would otherwise match "Mobile"
    result = _call(mcp, "find_segment", {"name": "Mobile", "force_live": True})
    assert result["source"] == "live_api"
    assert "force_live=True" in result["note"]
    assert result["results"][0]["id"] == "s_live"


def test_create_calculated_metric_passes_definition_through():
    mcp = _server()
    metric = {"name": "Bounce rate", "rsid": "rs1", "definition": {"func": "divide"}}
    result = _call(mcp, "create_calculated_metric", {"calculated_metric": metric})
    assert result["id"] == "cm_new"
    assert result["name"] == "Bounce rate"


def test_update_calculated_metric_passes_id_and_definition_through():
    mcp = _server()
    metric = {"name": "Bounce rate v2", "rsid": "rs1", "definition": {"func": "divide"}}
    result = _call(mcp, "update_calculated_metric", {"calculated_metric_id": "cm1", "calculated_metric": metric})
    assert result["id"] == "cm1"
    assert result["name"] == "Bounce rate v2"


def test_validate_calculated_metric_returns_api_result():
    mcp = _server()
    metric = {"name": "Bounce rate", "rsid": "rs1", "definition": {"func": "divide"}}
    result = _call(mcp, "validate_calculated_metric", {"calculated_metric": metric})
    assert result["valid"] is True


def test_find_calculated_metric_uses_knowledge_graph_when_available():
    mcp = _server_with_kg()
    result = _call(mcp, "find_calculated_metric", {"name": "Bounce"})
    assert result["source"] == "knowledge_graph"
    assert result["note"] is None
    assert result["results"] == [
        {"id": "cm_kg1", "name": "Bounce Rate KG", "description": None, "rsid": "rs1"}
    ]


def test_find_calculated_metric_falls_back_when_no_kg_connected():
    mcp = _server()  # built without kg_graph
    result = _call(mcp, "find_calculated_metric", {"name": "Bounce"})
    assert result["source"] == "live_api"
    assert "No Knowledge Graph connected" in result["note"]
    assert result["results"][0]["id"] == "cm_live"


def test_find_calculated_metric_falls_back_when_kg_has_no_match():
    mcp = _server_with_kg()
    result = _call(mcp, "find_calculated_metric", {"name": "Nonexistent Metric Name"})
    assert result["source"] == "live_api"
    assert "No matching calculated metric found in the Knowledge Graph" in result["note"]
    assert result["results"][0]["id"] == "cm_live"


def test_find_calculated_metric_force_live_bypasses_knowledge_graph():
    mcp = _server_with_kg()  # KG would otherwise match "Bounce"
    result = _call(mcp, "find_calculated_metric", {"name": "Bounce", "force_live": True})
    assert result["source"] == "live_api"
    assert "force_live=True" in result["note"]
    assert result["results"][0]["id"] == "cm_live"


def test_create_date_range_passes_definition_through():
    mcp = _server()
    date_range = {"name": "Last quarter", "definition": {"dateRangeType": "Fixed"}}
    result = _call(mcp, "create_date_range", {"date_range": date_range})
    assert result["id"] == "dr_new"
    assert result["name"] == "Last quarter"


def test_update_date_range_passes_id_and_definition_through():
    mcp = _server()
    date_range = {"name": "Last quarter v2", "definition": {"dateRangeType": "Fixed"}}
    result = _call(mcp, "update_date_range", {"date_range_id": "dr1", "date_range": date_range})
    assert result["id"] == "dr1"
    assert result["name"] == "Last quarter v2"
