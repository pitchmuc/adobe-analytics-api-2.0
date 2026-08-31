import os
import sys
import inspect
import json

## changing current_dir to ensure you are running test on your version of the aanalytics2 module.
current_dir = os.path.dirname(os.path.abspath(
    inspect.getfile(inspect.currentframe())))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)
import aanalytics2 as api2

# All fixtures below are synthetic (no real project data) so these tests never
# depend on any locally-downloaded Workspace exports.


def _minimal_project(panels):
    return {
        "id": "test-project", "name": "Test Project", "rsid": "rsid1",
        "reportSuiteName": "RS", "owner": {"id": 1, "name": "A", "login": "a@b.com"},
        "created": "2024-01-01T00:00:00Z", "modified": "2024-01-02T00:00:00Z",
        "definition": {"version": "50", "workspaces": [{"id": "ws1", "name": "", "panels": panels}]},
    }


def _subpanel(id_, name, reportlet, linked_source_id=""):
    return {
        "id": id_, "name": name, "type": "genericSubPanel", "linkedSourceId": linked_source_id,
        "position": {"x": 0, "y": 0, "width": 100, "autoHeight": 10, "autoSize": True},
        "reportlet": reportlet,
    }


def _panel(id_, name, sub_panels):
    return {
        "id": id_, "name": name, "type": "panel",
        "position": {"x": 0, "y": 0, "width": 100, "autoHeight": 10, "autoSize": True},
        "dateRange": {}, "segmentGroups": [], "description": "", "collapsed": False,
        "subPanels": sub_panels,
    }


FREEFORM_REPORTLET = {
    "type": "FreeformReportlet", "name": "Table",
    "columnTree": {"nodes": [
        {
            "id": "metric-node", "name": "Visits",
            "component": {"id": "metrics/visits", "type": "Metric", "__metaData__": {"name": "Visits"}},
            "nodes": [
                {"id": "seg-node-mobile", "name": "Mobile",
                 "component": {"id": "s4222_mobile", "type": "Segment", "__metaData__": {"name": "Mobile"}},
                 "nodes": [
                     {"id": "dr-node", "name": "7 days before",
                      "component": {"id": "dr-7days", "type": "DateRange", "__metaData__": {"name": "7 days before"}},
                      "nodes": []},
                 ]},
            ],
        },
        {
            "id": "calc-node", "name": "Bounce Rate",
            "component": {"id": "cm4222_abc", "type": "CalculatedMetric", "__metaData__": {"name": "Bounce Rate"}},
            "nodes": [],
        },
    ]},
    "freeformTable": {
        "dimension": {"id": "variables/evar8", "type": "Dimension", "__metaData__": {"name": "Market Code"}},
        "staticRows": [],
        "breakdowns": [
            {
                "parentItemId": "0", "breakdowns": [],
                "dimension": {"id": "variables/evar3", "type": "Dimension", "__metaData__": {"name": "Browser"}},
                "staticRows": [], "settings": {"breakdownByPosition": True},
            }
        ],
    },
}

TEXT_REPORTLET = {"type": "TextReportlet", "name": "Note", "textContent": json.dumps({"ops": [{"insert": "hello"}]})}

DONUT_REPORTLET = {
    "type": "DonutReportlet", "name": "Device split",
    "lockedSelection": {"breakdowns": [{
        "breakdowns": [],
        "selectedDataPoints": [
            {"columnId": "seg-node-mobile", "rowPosition": 0,
             "rowItem": {"id": "s4222_mobile", "type": "Segment", "__metaData__": {"name": "Mobile"}}},
        ],
    }]},
}

HISTOGRAM_REPORTLET = {
    "type": "HistogramReportlet", "name": "Histogram",
    "component": {"id": "metrics/event1", "type": "Metric", "__metaData__": {"name": "Custom Event"}},
}

FLOW_REPORTLET = {"type": "Flow", "name": "Flow viz", "flowContainer": {}}


def _sample_project():
    return _minimal_project([
        _panel("p1", "Panel 1", [
            _subpanel("sp1", "Table", FREEFORM_REPORTLET),
            _subpanel("sp2", "Note", TEXT_REPORTLET),
            _subpanel("sp3", "Donut", DONUT_REPORTLET, linked_source_id="sp1"),
            _subpanel("sp4", "Histogram", HISTOGRAM_REPORTLET, linked_source_id="sp1"),
            _subpanel("sp5", "Flow", FLOW_REPORTLET),
        ]),
    ])


def test_parses_panel_tree_and_types():
    wm = api2.WorkspaceManager(data=_sample_project())
    assert wm.version == "50"
    assert wm.created == "2024-01-01T00:00:00Z"
    assert wm.modified == "2024-01-02T00:00:00Z"
    assert wm.owner == {"id": 1, "name": "A", "login": "a@b.com"}

    panel = wm.panels[0]
    assert panel.type == "SubPanel"
    table, note, donut, histogram, flow = panel.elements
    assert [table.type, note.type, donut.type, histogram.type, flow.type] == \
        ["FreeForm", "Text", "Visualization", "Visualization", "Visualization"]
    assert note.text == "hello"


def test_freeform_component_lists_include_breakdowns():
    wm = api2.WorkspaceManager(data=_sample_project())
    table = wm.panels[0].elements[0]
    assert table.freeform.metrics == [{"id": "metrics/visits", "name": "Visits"}]
    assert table.freeform.calculatedMetrics == [{"id": "cm4222_abc", "name": "Bounce Rate"}]
    assert table.freeform.segments == [{"id": "s4222_mobile", "name": "Mobile"}]
    assert table.freeform.dateRanges == [{"id": "dr-7days", "name": "7 days before"}]

    # Element-level aggregate must include the nested breakdown's own dimension
    # (Browser), not just the table's top-level dynamic dimension (Market Code).
    dim_ids = {d["id"] for d in table.dimensions}
    assert dim_ids == {"variables/evar8", "variables/evar3"}


def test_visualization_resolves_via_linked_table():
    wm = api2.WorkspaceManager(data=_sample_project())
    _, _, donut, histogram, flow = wm.panels[0].elements

    # Donut selects specific segment rows via lockedSelection.breakdowns[].selectedDataPoints.
    assert donut.segments == [{"id": "s4222_mobile", "name": "Mobile"}]

    # Histogram carries a direct "component" key instead of lockedSelection.
    assert histogram.metrics == [{"id": "metrics/event1", "name": "Custom Event"}]

    # Flow has no linkedSourceId and a bespoke schema — must degrade to empty, not crash.
    assert flow.dimensions == flow.metrics == flow.segments == flow.dateRanges == []


def test_panel_and_project_wide_aggregates():
    wm = api2.WorkspaceManager(data=_sample_project())
    panel = wm.panels[0]

    assert {d["id"] for d in panel.dimensions} == {"variables/evar8", "variables/evar3"}
    assert {s["id"] for s in panel.segments} == {"s4222_mobile"}

    assert {d["id"] for d in wm.dimensions} == {"variables/evar8", "variables/evar3"}
    assert {s["id"] for s in wm.segments} == {"s4222_mobile"}
    assert {m["id"] for m in wm.metrics} == {"metrics/visits", "metrics/event1"}
    assert {c["id"] for c in wm.calculatedMetrics} == {"cm4222_abc"}
    assert {d["id"] for d in wm.dateRanges} == {"dr-7days"}


def test_build_path_round_trip():
    """addPanel -> addFreeform -> nested addBreakdown -> to_dict() -> re-parsed."""
    wm = api2.WorkspaceManager(data=_sample_project())
    wm.addPanel("Built Panel", date_range="thisMonth")
    ff = wm.addFreeform(
        "Device Comparison",
        items=[{"id": "s4222_mobile", "name": "Mobile", "type": "Segment"},
               {"id": "s4222_desktop", "name": "Desktop", "type": "Segment"}],
        metrics=[{"id": "metrics/visits", "name": "Visits"}],
    )
    assert isinstance(ff, api2.FreeForm)
    level1 = ff.addBreakdown(dimension_id="variables/evar8", dimension_name="Market Code")
    assert isinstance(level1, api2.FreeForm) and level1 is not ff
    level1.addBreakdown(dimension_id="variables/evar3", dimension_name="Browser")

    d = wm.to_dict()
    json.dumps(d)  # must be JSON-serializable

    new_panel = d["definition"]["workspaces"][0]["panels"][-1]
    table_dict = new_panel["subPanels"][0]["reportlet"]["freeformTable"]
    assert table_dict["columnWidths"] == [100.0, 100.0]

    bd1 = table_dict["breakdowns"][0]
    assert bd1["parentItemId"] == table_dict["staticRows"][0]["id"]
    bd2 = bd1["breakdowns"][0]
    assert bd2["parentItemId"] == "0"
    assert bd2["settings"]["breakdownByPosition"] is True

    # The built project must itself parse back correctly (write/read symmetry).
    wm2 = api2.WorkspaceManager(data=d)
    reparsed = wm2.panels[-1].elements[0].freeform
    assert reparsed.segments == [{"id": "s4222_mobile", "name": "Mobile"}, {"id": "s4222_desktop", "name": "Desktop"}]
    assert len(reparsed.breakdowns) == 1
    assert len(reparsed.breakdowns[0].breakdowns) == 1
    assert reparsed.breakdowns[0].dimensions == [{"id": "variables/evar8", "name": "Market Code"}]
    assert reparsed.breakdowns[0].breakdowns[0].dimensions == [{"id": "variables/evar3", "name": "Browser"}]
