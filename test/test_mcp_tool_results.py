import asyncio
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pandas as pd
import pytest
from rdflib import BNode, Graph, Literal, Namespace, RDFS, URIRef

from aanalytics2 import Analytics
from aanalytics2.mcp_server import build_server
from mcp.server.mcpserver.exceptions import ToolError


def call_tool(server, name, arguments, as_list=False):
    result = asyncio.run(server.call_tool(name, arguments))
    values = [json.loads(block.text) for block in result.content]
    return values if as_list else values[0]


@pytest.fixture
def graph_server():
    graph = Graph()
    base = "http://analytics.com/dummy/"
    usage = Namespace(base + "usage#")
    rsid = URIRef(base + "reportSuite#rs1")
    nodes = {
        "dimension": (base + "rs1/dimension/variables/page", "dim", "variables/page"),
        "metric": (base + "rs1/metric/metrics/visits", "met", "metrics/visits"),
        "segment": (base + "segment/s1", "seg", "s1"),
        "calculatedMetric": (base + "calculatedMetric/cm1", "cm", "cm1"),
    }
    for kind, (uri, _, component_id) in nodes.items():
        namespace = Namespace(base + kind + "#")
        node = URIRef(uri)
        graph.add((node, namespace.id, Literal(component_id)))
        graph.add((node, namespace.rsid, rsid))
        graph.add((node, RDFS.label, Literal(kind.title())))
    for partner in ("metric", "segment"):
        record = BNode()
        graph.add((record, usage.dimension, URIRef(nodes["dimension"][0])))
        graph.add((record, usage[partner], URIRef(nodes[partner][0])))
        graph.add((record, usage.cooccurrenceCount, Literal(9)))
        graph.add((record, usage.rsid, rsid))
    server = build_server(Mock(spec=Analytics), "dummy", "rs1", graph)
    return server


@pytest.mark.parametrize(
    ("name", "arguments", "id_key", "component_id"),
    [
        ("get_related_metrics", {"dimension_id": "variables/page"}, "metric_id", "metrics/visits"),
        ("get_related_dimensions", {"metric_id": "metrics/visits"}, "dimension_id", "variables/page"),
        ("get_related_segments", {"dimension_id": "variables/page"}, "segment_id", "s1"),
        ("get_popular_combinations", {}, "dimension_id", "variables/page"),
    ],
)
def test_graph_relationship_results_have_integer_counts_and_full_ids(
    graph_server, name, arguments, id_key, component_id
):
    rows = call_tool(graph_server, name, arguments, as_list=True)
    assert rows[0][id_key] == component_id
    assert rows[0]["count"] == 9
    if name == "get_popular_combinations":
        assert rows[0]["metric_id"] == "metrics/visits"


@pytest.mark.parametrize("component_id", ["variables/page", "metrics/visits", "s1", "cm1"])
def test_component_context_uses_bare_report_suite_id_for_every_component(graph_server, component_id):
    result = call_tool(graph_server, "get_component_context", {"component_id": component_id})
    assert result["matches"][0]["rsid"] == "rs1"
    if component_id == "variables/page":
        assert result["matches"][0]["top_related"][0]["count"] == 9
        assert {r["id"] for r in result["matches"][0]["top_related"]} == {"metrics/visits", "s1"}


def test_get_top_items_returns_dimension_values_not_item_ids():
    analytics = Mock(spec=Analytics)
    analytics.getReport2.return_value = SimpleNamespace(
        dataframe=pd.DataFrame(
            {"itemId": ["123"], "variables/page": ["Home page"], "Visits": [10]}
        ),
        columns=["itemId", "variables/page", "Visits"],
    )
    server = build_server(analytics, "dummy", "rs1")
    rows = call_tool(server, "get_top_items", {"dimension_id": "variables/page"}, as_list=True)
    assert rows == [{"value": "Home page", "itemId": "123"}]


@pytest.mark.parametrize(
    ("name", "method", "arguments"),
    [
        ("list_report_suites", "getReportSuites", {}),
        ("list_dimensions", "getDimensions", {}),
        ("list_metrics", "getMetrics", {}),
        ("list_segments", "getSegments", {}),
        ("find_segment", "getSegments", {}),
        ("list_calculated_metrics", "getCalculatedMetrics", {}),
        ("find_calculated_metric", "getCalculatedMetrics", {}),
        ("list_date_ranges", "getDateRanges", {}),
        ("list_projects", "getProjects", {}),
        ("get_segment", "getSegment", {"segment_id": "missing"}),
        ("get_project", "getProject", {"project_id": "missing"}),
        ("run_report", "getReport2", {"request": {}}),
        ("get_top_items", "getReport2", {"dimension_id": "variables/page"}),
        ("validate_segment", "createSegmentValidate", {"segment": {}}),
        ("create_segment", "createSegment", {"segment": {}}),
        ("update_segment", "updateSegment", {"segment_id": "s1", "segment": {}}),
        ("validate_calculated_metric", "createCalculatedMetricValidate", {"calculated_metric": {}}),
        ("create_calculated_metric", "createCalculatedMetric", {"calculated_metric": {}}),
        (
            "update_calculated_metric", "updateCalculatedMetric",
            {"calculated_metric_id": "cm1", "calculated_metric": {}},
        ),
        ("create_date_range", "createDateRange", {"date_range": {}}),
        ("update_date_range", "updateDateRange", {"date_range_id": "dr1", "date_range": {}}),
        ("publish_workspace", "createProject", {"project": {}}),
        ("update_workspace", "updateProject", {"project": {"id": "p1"}}),
        ("list_classification_datasets", "getClassificationDatasets", {}),
        ("get_classification_dataset_id", "getClassificationDatasets", {"dimension_id": "evar1"}),
        ("get_classification_dataset", "getClassificationDataset", {"dataset_id": "missing"}),
    ],
)
def test_api_error_dictionaries_are_reported_as_tool_errors(name, method, arguments):
    analytics = Mock(spec=Analytics)
    getattr(analytics, method).return_value = {
        "errorCode": "resource_not_found", "errorDescription": "Test resource does not exist",
    }
    server = build_server(analytics, "dummy", "rs1")
    with pytest.raises(ToolError, match="resource_not_found.*Test resource does not exist"):
        call_tool(server, name, arguments)
