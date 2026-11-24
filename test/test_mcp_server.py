import asyncio
import json
import os
import sys
import inspect
import io
from unittest.mock import Mock

import pandas as pd
import pytest
from rdflib import Graph, Literal, RDF, RDFS, URIRef, Namespace
from rdflib.plugins.parsers.notation3 import BadSyntax

current_dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

from aanalytics2 import workspaceManager as wmmod
from aanalytics2 import mcp_server
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


@pytest.fixture
def startup(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["aanalytics2-mcp", "-cid", "dummy", "-rsid", "rs1"])
    monkeypatch.setattr(mcp_server, "importConfigFile", Mock(return_value=object()))
    monkeypatch.setattr(mcp_server, "Login", Mock())
    monkeypatch.setattr(mcp_server, "Analytics", Mock(return_value=DummyAnalytics()))
    server_builder = Mock()
    monkeypatch.setattr(mcp_server, "build_server", server_builder)
    return server_builder


def test_main_legacy_stdio_relays_arguments_without_recursing(startup, monkeypatch):
    from aanalytics2 import mcp_compat

    relay = Mock(return_value=7)
    monkeypatch.setattr(mcp_compat, "relay_legacy_stdio", relay)
    stdin = io.TextIOWrapper(io.BytesIO())
    stdout = io.TextIOWrapper(io.BytesIO())
    monkeypatch.setattr(sys, "stdin", stdin)
    monkeypatch.setattr(sys, "stdout", stdout)
    monkeypatch.setattr(
        sys, "argv",
        [*sys.argv, "--legacy-stdio", "-cf", "config with spaces.json",
         "-kg", "graph.ttl", "-kg-ontology", "ontology.md"],
    )

    with pytest.raises(SystemExit) as error:
        mcp_server.main()

    assert error.value.code == 7
    relay.assert_called_once_with(
        [sys.executable, "-u", "-m", "aanalytics2.mcp_server",
         "-cf", "config with spaces.json", "-cid", "dummy", "-rsid", "rs1",
         "-kg", "graph.ttl", "-kg-ontology", "ontology.md"],
        stdin.buffer,
        stdout.buffer,
    )
    startup.assert_not_called()
    mcp_server.importConfigFile.assert_not_called()


@pytest.mark.parametrize("flag", ["-kg", "--knowledge_graph"])
@pytest.mark.parametrize("path_kind", ["relative", "absolute", "missing_parent"])
def test_main_missing_knowledge_graph_warns_and_starts(
    startup, monkeypatch, tmp_path, capsys, flag, path_kind
):
    graph_path = "missing graph.ttl"
    if path_kind == "absolute":
        graph_path = str(tmp_path / graph_path)
    elif path_kind == "missing_parent":
        graph_path = str(tmp_path / "missing directory" / graph_path)
    monkeypatch.setattr(sys, "argv", [*sys.argv, flag, graph_path])

    mcp_server.main()

    startup.assert_called_once()
    assert startup.call_args.kwargs["kg_graph"] is None
    startup.return_value.run.assert_called_once_with(transport="stdio")
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Warning:" in captured.err
    assert graph_path in captured.err
    assert "Continuing without a Knowledge Graph" in captured.err
    assert "Knowledge Graph loaded:" not in captured.err


def test_main_without_knowledge_graph_starts_without_warning(startup, capsys):
    mcp_server.main()

    assert startup.call_args.kwargs["kg_graph"] is None
    startup.return_value.run.assert_called_once_with(transport="stdio")
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


@pytest.mark.parametrize("empty", [False, True])
def test_main_loads_existing_knowledge_graph(startup, monkeypatch, tmp_path, capsys, caplog, empty):
    expected = Graph() if empty else _build_test_kg()
    graph_path = tmp_path / "knowledge graph.ttl"
    expected.serialize(destination=graph_path, format="turtle")
    monkeypatch.setattr(sys, "argv", [*sys.argv, "-kg", str(graph_path)])

    mcp_server.main()

    loaded = startup.call_args.kwargs["kg_graph"]
    assert isinstance(loaded, Graph)
    assert set(loaded) == set(expected)
    startup.return_value.run.assert_called_once_with(transport="stdio")
    captured = capsys.readouterr()
    assert captured.out == ""
    assert f"Knowledge Graph loaded: {len(expected)} triples." in captured.err
    assert "Warning:" not in captured.err
    assert "does not look like a valid URI" not in caplog.text


def test_main_invalid_knowledge_graph_still_raises(startup, monkeypatch, tmp_path):
    graph_path = tmp_path / "invalid.ttl"
    graph_path.write_text("not valid Turtle", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", [*sys.argv, "-kg", str(graph_path)])

    with pytest.raises(BadSyntax):
        mcp_server.main()

    startup.assert_not_called()


def test_main_unreadable_knowledge_graph_still_raises(startup, monkeypatch, tmp_path):
    graph_path = tmp_path / "unreadable.ttl"
    monkeypatch.setattr(sys, "argv", [*sys.argv, "-kg", str(graph_path)])
    monkeypatch.setattr(mcp_server.Path, "open", Mock(side_effect=PermissionError("Access denied")))

    with pytest.raises(PermissionError, match="Access denied"):
        mcp_server.main()

    startup.assert_not_called()


# ── Workspace builder caching ────────────────────────────────────────────────


def test_workspace_builder_caches_single_instance_and_lookup_tables(monkeypatch):
    fetch_calls = 0
    user_calls = 0
    rs_calls = 0

    async def counting_fetch(self):
        nonlocal fetch_calls
        fetch_calls += 1
        return (
            dict(_FAKE_LOOKUPS[0]),
            dict(_FAKE_LOOKUPS[1]),
            dict(_FAKE_LOOKUPS[2]),
            dict(_FAKE_LOOKUPS[3]),
            dict(_FAKE_LOOKUPS[4]),
        )

    class CountingAnalytics(DummyAnalytics):
        def getUserMe(self):
            nonlocal user_calls
            user_calls += 1
            return super().getUserMe()

        def getReportSuite(self, rsid):
            nonlocal rs_calls
            rs_calls += 1
            return super().getReportSuite(rsid)

        def createProject(self, project):
            return {"id": "p_published", **project}

        def getProject(self, projectId=None):
            return {
                "id": projectId,
                "name": "Existing Proj",
                "description": "",
                "rsid": "rs1",
                "type": "project",
                "definition": {"version": "98", "workspaces": [{"id": "ws_ext", "name": "Existing Proj", "panels": []}]},
            }

    monkeypatch.setattr(wmmod.WorkspaceManager, "_fetch_all_company_data", counting_fetch)
    mcp = build_server(analytics=CountingAnalytics(), company_id="dummy", default_rsid="rs1")

    # Chain builder calls omitting `project` — mutates the single cached WorkspaceManager instance.
    _call(mcp, "create_workspace", {"rsid": "rs1", "name": "Cached Proj"})
    _call(mcp, "add_panel", {"name": "Overview"})
    _call(mcp, "add_text", {"title": "Note", "content": "Hello"})
    _call(mcp, "add_freeform", {"title": "Browser Table", "metrics": ["metrics/visits"], "item_id": "variables/evar3"})
    _call(mcp, "add_chart", {"viz_type": "bar", "source": 0, "title": "Visits Bar"})
    # Newly created segment mid-session is immediately resolvable in the cached lookup table.
    _call(mcp, "create_segment", {"segment": {"name": "VIP Visitors", "rsid": "rs1", "definition": {}}})
    _call(mcp, "add_freeform", {"title": "VIP Table", "metrics": ["metrics/visits"], "items": ["s_new"]})
    published = _call(mcp, "publish_workspace", {})

    assert fetch_calls == 1
    assert user_calls == 1
    assert rs_calls == 1
    assert published["id"] == "p_published"
    vip_rows = published["definition"]["workspaces"][0]["panels"][-1]["subPanels"][-1]["reportlet"]["freeformTable"]["staticRows"]
    assert vip_rows[0]["component"]["__metaData__"]["name"] == "VIP Visitors"

    # Creating a second workspace on the same rsid OR editing a fetched get_project by ID
    # also reuses the cached company/rsid lookups without hitting the network again.
    _call(mcp, "create_workspace", {"rsid": "rs1", "name": "Second Proj"})
    _call(mcp, "get_project", {"project_id": "p_existing"})
    _call(mcp, "add_panel", {"project": "p_existing", "name": "Added Panel"})
    updated = _call(mcp, "update_workspace", {})
    assert updated["id"] == "p_existing"
    assert fetch_calls == 1
    assert user_calls == 1
    assert rs_calls == 1


# ── Report response caching & reusable breakdowns ────────────────────────────


def test_run_report_caches_workspace_and_allows_multiple_independent_breakdowns():
    from aanalytics2.workspace import Workspace

    calls = []

    class ReportAnalytics(DummyAnalytics):
        def getMetrics(self, rsid=None, **kwargs):
            return pd.DataFrame([{"id": "metrics/visits", "name": "Visits"}])

        def getReport2(self, request=None, n_results=None, limit=None):
            req_dict = request.to_dict() if hasattr(request, "to_dict") else dict(request)
            calls.append(req_dict)
            dim = req_dict["dimension"]
            if dim == "variables/page":
                rows = {"home_id": ["Home", 100], "cart_id": ["Cart", 40]}
            elif dim == "variables/evar3":
                rows = {"br_1": ["Chrome", 70], "br_2": ["Safari", 30]}
            elif dim == "variables/evar8":
                rows = {"mkt_1": ["US", 60], "mkt_2": ["DE", 40]}
            else:
                rows = {"sub_1": ["SubVal", 25]}
            return Workspace(
                responseData=rows,
                dataRequest=req_dict,
                columns={"columnIds": ["0"]},
                summaryData={},
                analyticsConnector=self,
                reportType="normal",
                metrics={"0": "metrics/visits"},
                resolveColumns=True,
            )

    mcp = build_server(analytics=ReportAnalytics(), company_id="dummy", default_rsid="rs1")

    req = _call(mcp, "build_report_request", {
        "dimension_id": "variables/page",
        "metrics": ["metrics/visits"],
        "date_range": "2024-01-01/2024-01-31",
    })
    first = _call(mcp, "run_report", {"request": req, "n_results": 20})
    assert first["report_id"] == "report_1"
    assert first["cached"] is False
    assert len(calls) == 1

    # Re-running the same request dict or by report_id returns from cache without calling getReport2.
    second = _call(mcp, "run_report", {"request": req, "n_results": 20})
    by_id = _call(mcp, "run_report", {"request": "report_1", "n_results": 1})
    assert second["cached"] is True
    assert by_id["cached"] is True
    assert len(by_id["rows"]) == 1
    assert len(calls) == 1

    # Breakdown #1 on report_1 by variables/evar3.
    bd_browser = _call(mcp, "breakdown_report", {
        "report_id": "report_1",
        "row": "Home",
        "dimension_id": "variables/evar3",
        "n_results": 10,
    })
    assert bd_browser["report_id"] == "report_2"
    assert bd_browser["parent_report_id"] == "report_1"
    assert bd_browser["breakdown_filter"] == "variables/page:::home_id"
    assert bd_browser["cached"] is False
    assert len(calls) == 2

    # Breakdown #2 on the SAME original report_1 using a DIFFERENT dimension (variables/evar8):
    # original report_1 is not re-executed and does NOT carry variables/evar3's filter.
    bd_market = _call(mcp, "breakdown_report", {
        "report_id": "report_1",
        "row": 0,
        "dimension_id": "variables/evar8",
        "n_results": 10,
    })
    assert bd_market["report_id"] == "report_3"
    assert bd_market["parent_report_id"] == "report_1"
    assert bd_market["breakdown_filter"] == "variables/page:::home_id"
    assert len(calls) == 3
    market_filters = calls[-1]["metricContainer"]["metricFilters"]
    assert len(market_filters) == 1
    assert market_filters[0]["dimension"] == "variables/page"
    assert market_filters[0]["itemId"] == "home_id"

    # Repeating an identical breakdown reuses the breakdown cache.
    bd_browser_cached = _call(mcp, "breakdown_report", {
        "report_id": "report_1",
        "row": 0,
        "dimension_id": "variables/evar3",
        "n_results": 10,
    })
    assert bd_browser_cached["cached"] is True
    assert bd_browser_cached["report_id"] == "report_2"
    assert len(calls) == 3

    # Multi-level breakdown on report_2 stacks both breakdown filters cleanly.
    bd_nested = _call(mcp, "breakdown_report", {
        "report_id": "report_2",
        "row": "Chrome",
        "dimension_id": "variables/geocountry",
        "n_results": 5,
    })
    assert bd_nested["parent_report_id"] == "report_2"
    nested_filters = calls[-1]["metricContainer"]["metricFilters"]
    assert [(f["dimension"], f["itemId"]) for f in nested_filters] == [
        ("variables/page", "home_id"),
        ("variables/evar3", "br_1"),
    ]

    cached_list = asyncio.run(mcp.call_tool("list_cached_reports", {}))
    cached_ids = [json.loads(b.text)["report_id"] for b in cached_list.content]
    assert cached_ids == ["report_1", "report_2", "report_3", "report_4"]


# ── Knowledge Graph lazy loading & SPARQL improvements ───────────────────────


def test_server_without_kg_omits_kg_tools_and_skips_ontology_read(startup, monkeypatch):
    import subprocess

    # Importing mcp_server in a clean process does not eagerly import rdflib.
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            f"import sys; sys.path.insert(0, {parent_dir!r}); import aanalytics2.mcp_server; assert 'rdflib' not in sys.modules",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr

    mcp_no_kg = _server()
    tool_names_no_kg = {t.name for t in asyncio.run(mcp_no_kg.list_tools())}
    resources_no_kg = asyncio.run(mcp_no_kg.list_resources())
    assert "sparql_query" not in tool_names_no_kg
    assert "get_related_metrics" not in tool_names_no_kg
    assert len(resources_no_kg) == 0

    mcp_with_kg = _server_with_kg()
    tool_names_with_kg = {t.name for t in asyncio.run(mcp_with_kg.list_tools())}
    resources_with_kg = asyncio.run(mcp_with_kg.list_resources())
    assert "sparql_query" in tool_names_with_kg
    assert "get_related_metrics" in tool_names_with_kg
    assert len(resources_with_kg) == 1

    # main() without -kg skips reading the bundled ontology file altogether.
    ontology_spy = Mock(side_effect=AssertionError("should not read ontology without -kg"))
    monkeypatch.setattr(mcp_server, "_default_ontology_md", ontology_spy)
    mcp_server.main()
    ontology_spy.assert_not_called()


def test_sparql_query_auto_prefixes_query_forms_types_and_errors():
    from rdflib import BNode, XSD
    from mcp.server.mcpserver.exceptions import ToolError

    kg = _build_test_kg()
    seg_ns = Namespace("http://analytics.com/dummy/segment#")
    seg_uri = URIRef("http://analytics.com/dummy/segment/s_kg1")
    kg.add((seg_uri, seg_ns.lastAccess, Literal("2026-03-01T12:00:00", datatype=XSD.dateTime)))
    kg.add((seg_uri, seg_ns.shares, Literal(5, datatype=XSD.integer)))
    kg.add((seg_uri, seg_ns.bnodeRef, BNode("node1")))

    mcp = build_server(analytics=DummyAnalytics(), company_id="dummy", default_rsid="rs1", kg_graph=kg)

    # SELECT without explicit PREFIX lines (auto-injected) + datetime/int/BNode JSON serialization.
    select_res = _call(mcp, "sparql_query", {
        "query": "SELECT ?id ?label ?dt ?shares ?bn WHERE { ?s seg:id ?id ; rdfs:label ?label ; seg:lastAccess ?dt ; seg:shares ?shares ; seg:bnodeRef ?bn }",
    })
    assert select_res["query_type"] == "SELECT"
    assert select_res["truncated"] is False
    assert select_res["rows"] == [{
        "id": "s_kg1",
        "label": "Mobile Visitors KG",
        "dt": "2026-03-01T12:00:00",
        "shares": 5,
        "bn": "_:node1",
    }]

    # Explicit PREFIX containing `#` in IRI is preserved, and `limit` truncates cleanly.
    trunc_res = _call(mcp, "sparql_query", {
        "query": "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\nSELECT ?s ?p ?o WHERE { ?s ?p ?o }",
        "limit": 2,
    })
    assert trunc_res["row_count"] == 2
    assert trunc_res["total_rows"] > 2
    assert trunc_res["truncated"] is True

    # ASK and CONSTRUCT are handled cleanly without crashing on results.vars == None.
    ask_res = _call(mcp, "sparql_query", {"query": "ASK { ?s seg:id 's_kg1' }"})
    assert ask_res == {"query_type": "ASK", "boolean": True}

    construct_res = _call(mcp, "sparql_query", {
        "query": "CONSTRUCT { ?s rdfs:label ?label } WHERE { ?s seg:id 's_kg1' ; rdfs:label ?label }",
    })
    assert construct_res["query_type"] == "CONSTRUCT"
    assert construct_res["triple_count"] == 1
    assert construct_res["triples"][0]["object"] == "Mobile Visitors KG"

    # Read-only guard rejects SPARQL Update statements, and syntax errors become ToolError.
    with pytest.raises(ToolError, match="read-only"):
        _call(mcp, "sparql_query", {"query": "INSERT DATA { <urn:a> <urn:b> 'c' }"})
    with pytest.raises(ToolError, match="Invalid SPARQL query"):
        _call(mcp, "sparql_query", {"query": "SELECT ?s WHERE { ?s ?p"})


def test_core_methods_silence_stdout_unless_verbose_true(capsys):
    from aanalytics2.aanalytics2 import Analytics

    dummy = Analytics.__new__(Analytics)
    dummy.loggingEnabled = False
    dummy.logger = None

    assert dummy.createSegment(None) is None
    assert dummy.createSegmentValidate(None) is None
    assert dummy.updateSegment(None, None) is None
    assert dummy.deleteSegment(None) is None
    assert dummy.updateCalculatedMetric(None, None) is None
    assert dummy.deleteCalculatedMetric(None) is None
    assert dummy.createDateRange(None) is None
    assert dummy.deleteDateRange(None) is None
    assert capsys.readouterr().out == ""

    assert dummy.createSegment(None, verbose=True) is None
    assert "No segment data has been pushed" in capsys.readouterr().out

