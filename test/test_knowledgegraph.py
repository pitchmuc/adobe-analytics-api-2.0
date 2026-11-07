from copy import deepcopy
import json
import logging
import threading
import time
from types import SimpleNamespace

import pandas as pd
import pytest
import requests
from rdflib import BNode, Graph, Literal, Namespace, RDF, RDFS, URIRef, XSD
from rdflib.compare import isomorphic
from rdflib.plugins.parsers.notation3 import BadSyntax
from requests.exceptions import (
    ConnectionError,
    ConnectTimeout,
    ProxyError,
    ReadTimeout,
    SSLError,
)

from aanalytics2 import Analytics, Login, WorkspaceManager, config as config_module, connector
from aanalytics2.configs import ConfigObj
from aanalytics2.knowledgegraph import KnowledgeGraph


def _segment(segment_id: str) -> dict:
    return {
        "id": segment_id,
        "name": segment_id,
        "rsid": "rs1",
        "definition": {"dimension": "variables/evar1", "metric": "metrics/visits"},
        "tags": [],
    }


def _calculated_metric(metric_id: str) -> dict:
    return {
        "id": metric_id,
        "name": metric_id,
        "rsid": "rs1",
        "type": "decimal",
        "definition": {"metric": "metrics/pageviews"},
        "compatibility": {"segments": []},
    }


@pytest.fixture
def graph_factory(monkeypatch):
    config = {
        "org_id": "test-org",
        "client_id": "test-client",
        "secret": "test-secret",
        "scopes": "test-scopes",
        "token": "test-token",
        "date_limit": time.time() + 3600,
        "proxy": "http://config-proxy.example:8080",
    }
    monkeypatch.setattr(config_module, "config_object", config)
    monkeypatch.setattr(config_module, "header", {"Authorization": "Bearer test-token"})
    monkeypatch.setattr(
        connector, "get_oauth_token_and_expiry_for_config",
        lambda **kwargs: {"token": "test-token", "expiry": 3600},
    )

    def unexpected_request(*args, **kwargs):
        raise AssertionError("Tests must not make live network requests")

    monkeypatch.setattr(requests.Session, "send", unexpected_request)
    monkeypatch.setattr(
        Login, "getCompanyId", lambda self: [{"globalCompanyId": "test-company"}],
    )
    monkeypatch.setattr(
        Analytics, "getReportSuites",
        lambda self, **kwargs: pd.DataFrame([
            {"rsid": "rs1", "name": "Test suite", "currency": "USD"},
        ]),
    )
    for method in (
        "getDimensions", "getMetrics", "getSegments", "getCalculatedMetrics",
        "getDateRanges", "getProjects", "getAnnotations",
    ):
        monkeypatch.setattr(Analytics, method, lambda self, **kwargs: [])
    monkeypatch.setattr(
        Analytics, "getMarketingChannels",
        lambda self, **kwargs: {"marketingChannels": []},
    )

    def create(config=None, **kwargs):
        return KnowledgeGraph(
            config=config, companyId="test-company", rsids="rs1", **kwargs,
        )

    return create


@pytest.mark.parametrize("config_kind", ["global", "dict", "object"])
@pytest.mark.parametrize("proxy", [
    None,
    "http://configured-proxy.example:8080",
    {"http": "http://http-proxy.example:8080", "https": "http://https-proxy.example:8080"},
])
def test_configuration_proxy_reaches_scan_requests(graph_factory, monkeypatch, config_kind, proxy):
    config = None
    if config_kind == "global":
        monkeypatch.setitem(config_module.config_object, "proxy", proxy)
    else:
        config_data = deepcopy(config_module.config_object)
        config_data["proxy"] = proxy
        config = config_data if config_kind == "dict" else ConfigObj(config_data, config_module.header)
    kg = graph_factory(config=config)
    expected = connector.normalize_proxy(proxy)
    for api in (kg.login, kg.analyticsAPI):
        assert api.connector.proxies == expected
        assert api.connector.session.proxies == (expected or {})
        assert api.connector.config["proxy"] == expected

    requests_seen = []

    def send(session, request, **kwargs):
        requests_seen.append((request.url, kwargs["proxies"], threading.get_ident()))
        response = requests.Response()
        response.status_code = 200
        response._content = json.dumps(_segment("s_missing")).encode("utf-8")
        return response

    monkeypatch.setattr(requests.Session, "send", send)
    monkeypatch.setattr(requests.sessions, "get_environ_proxies", lambda *args, **kwargs: {})
    calculated_metric = _calculated_metric("cm1")
    calculated_metric["compatibility"]["segments"] = ["s_missing"]
    kg.calculatedMetrics = [calculated_metric]

    graph = kg.buildGraph()

    assert len(requests_seen) == 1
    url, proxies, thread_id = requests_seen[0]
    assert url.partition("?")[0].endswith("/segments/s_missing")
    assert proxies == (expected or {})
    assert thread_id != threading.get_ident()
    visit_uri = URIRef("http://analytics.com/test-company/rs1/metric/metrics/visits")
    assert (visit_uri, kg.namespaces["usage"].metricUsage, Literal(1, datatype=XSD.integer)) in graph


def test_scan_token_refresh_keeps_proxy(graph_factory, monkeypatch):
    kg = graph_factory()
    configs_seen = []

    def refresh(config):
        configs_seen.append(deepcopy(config))
        return {"token": "refreshed-token", "expiry": 3600}

    monkeypatch.setattr(connector, "get_oauth_token_and_expiry_for_config", refresh)
    monkeypatch.setattr(
        kg.analyticsAPI.connector.session, "get",
        lambda *args, **kwargs: SimpleNamespace(json=lambda: _segment("s1")),
    )
    kg.analyticsAPI.connector.config["date_limit"] = 0

    kg.analyticsAPI.scanSegment("s1")

    assert len(configs_seen) == 1
    assert configs_seen[0]["proxy"] == kg.login.connector.proxies


@pytest.mark.parametrize("error_type", [
    ProxyError, ConnectionError, ConnectTimeout, ReadTimeout, SSLError,
])
@pytest.mark.parametrize("component_kind", ["segment", "calculated_metric"])
def test_scan_network_failure_keeps_metadata_and_continues(
    graph_factory, monkeypatch, caplog, tmp_path, error_type, component_kind,
):
    kg = graph_factory()
    if component_kind == "segment":
        kg.segments = [_segment("failed"), _segment("healthy")]
        scan_name = "scanSegment"
        node_type = "Segment"
        node_path = "segment"
        usage_field = "segmentUsage"
        metric_id = "metrics/visits"
    else:
        kg.calculatedMetrics = [_calculated_metric("failed"), _calculated_metric("healthy")]
        scan_name = "scanCalculatedMetric"
        node_type = "CalculatedMetric"
        node_path = "calculatedMetric"
        usage_field = "metricUsage"
        metric_id = "metrics/pageviews"
    original_scan = getattr(kg.analyticsAPI, scan_name)

    def scan(component, **kwargs):
        if component["id"] == "failed":
            raise error_type("synthetic network failure")
        return original_scan(component, **kwargs)

    monkeypatch.setattr(kg.analyticsAPI, scan_name, scan)
    filename = tmp_path / "graph.ttl"
    with caplog.at_level(logging.WARNING, logger="aanalytics2.knowledgegraph"):
        graph = kg.buildGraph(save=True, filename=str(filename), calculatedMetricWorkers=2)

    assert filename.is_file()
    assert set(Graph().parse(str(filename), format="turtle")) == set(graph)
    for component_id in ("failed", "healthy"):
        uri = URIRef(f"http://analytics.com/test-company/{node_path}/{component_id}")
        assert (uri, RDF.type, Literal(node_type)) in graph
        assert (uri, RDFS.label, Literal(component_id)) in graph
    metric_uri = URIRef(f"http://analytics.com/test-company/rs1/metric/{metric_id}")
    assert graph.value(metric_uri, kg.namespaces["usage"][usage_field]) == Literal(1, datatype=XSD.integer)
    assert len(caplog.records) == 1
    assert "failed" in caplog.text
    assert error_type.__name__ in caplog.text
    assert "usage counts" in caplog.text


def test_calculated_metric_segment_fetch_failure_does_not_abort_graph(
    graph_factory, monkeypatch, caplog,
):
    kg = graph_factory()
    failed_metric = _calculated_metric("failed")
    failed_metric["compatibility"]["segments"] = ["s_missing"]
    kg.calculatedMetrics = [failed_metric, _calculated_metric("healthy")]
    requests_seen = []

    def get(endpoint, **kwargs):
        requests_seen.append(endpoint)
        raise ProxyError("synthetic proxy failure")

    monkeypatch.setattr(kg.analyticsAPI.connector.session, "get", get)
    with caplog.at_level(logging.WARNING, logger="aanalytics2.knowledgegraph"):
        graph = kg.buildGraph()

    assert len(requests_seen) == 1
    assert requests_seen[0].endswith("/segments/s_missing")
    for metric_id in ("failed", "healthy"):
        uri = URIRef(f"http://analytics.com/test-company/calculatedMetric/{metric_id}")
        assert (uri, RDF.type, Literal("CalculatedMetric")) in graph
    metric_uri = URIRef("http://analytics.com/test-company/rs1/metric/metrics/pageviews")
    assert graph.value(metric_uri, kg.namespaces["usage"].metricUsage) == Literal(1, datatype=XSD.integer)
    assert len(caplog.records) == 1
    assert "failed (ProxyError)" in caplog.text


@pytest.mark.parametrize("scan_name", ["scanSegment", "scanCalculatedMetric"])
def test_scan_programming_errors_are_not_suppressed(graph_factory, monkeypatch, scan_name):
    kg = graph_factory()
    kg.segments = [_segment("s1")]
    kg.calculatedMetrics = [_calculated_metric("cm1")]

    def scan(*args, **kwargs):
        raise KeyError("malformed definition")

    monkeypatch.setattr(kg.analyticsAPI, scan_name, scan)
    with pytest.raises(KeyError, match="malformed definition"):
        kg.buildGraph()


def test_known_segments_are_scanned_without_network_requests(graph_factory):
    kg = graph_factory()
    kg.segments = [_segment("s1")]
    kg._segmentsById = {"s1": kg.segments[0]}
    calculated_metric = _calculated_metric("cm1")
    calculated_metric["compatibility"]["segments"] = ["s1"]
    kg.calculatedMetrics = [calculated_metric]

    graph = kg.buildGraph()

    metric_uri = URIRef("http://analytics.com/test-company/rs1/metric/metrics/visits")
    assert graph.value(metric_uri, kg.namespaces["usage"].segmentUsage) == Literal(1, datatype=XSD.integer)
    assert graph.value(metric_uri, kg.namespaces["usage"].metricUsage) == Literal(1, datatype=XSD.integer)


@pytest.mark.parametrize("path_as_string", [True, False])
def test_load_graph_round_trip_supports_query_and_export(graph_factory, tmp_path, path_as_string):
    source = graph_factory()
    custom = Namespace("http://example.com/custom#")
    source.graph.bind("custom", custom)
    source.graph.add((custom.dimension, RDFS.label, Literal("Caf\u00e9")))
    source.graph.add((custom.dimension, custom["count"], Literal(3, datatype=XSD.integer)))
    source.graph.add((custom.dimension, custom.details, BNode()))
    filename = tmp_path / "saved graph.ttl"
    source.exportGraph(str(filename))

    kg = graph_factory()
    graph = kg.loadGraph(str(filename) if path_as_string else filename)

    assert graph is kg.graph
    assert isomorphic(graph, source.graph)
    assert dict(graph.namespaces())["custom"] == URIRef(custom)
    assert kg.query(
        "SELECT ?label WHERE { <http://example.com/custom#dimension> "
        "<http://www.w3.org/2000/01/rdf-schema#label> ?label }"
    ) == [{"label": "Caf\u00e9"}]
    exported = tmp_path / "exported.ttl"
    kg.exportGraph(str(exported))
    assert isomorphic(Graph().parse(str(exported), format="turtle"), source.graph)


@pytest.mark.parametrize("merge", [None, True, False])
def test_load_graph_merges_or_replaces_existing_graph(graph_factory, tmp_path, merge):
    kg = graph_factory()
    custom = Namespace("http://example.com/custom#")
    existing = (custom.existing, RDFS.label, Literal("Existing"))
    shared = (custom.shared, RDFS.label, Literal("Shared"))
    added = (custom.added, RDFS.label, Literal("Added"))
    kg.graph.add(existing)
    kg.graph.add(shared)
    previous_graph = kg.graph
    incoming = Graph()
    incoming.bind("custom", custom)
    incoming.add(shared)
    incoming.add(added)
    filename = tmp_path / "incoming.ttl"
    incoming.serialize(destination=str(filename), format="turtle")

    graph = kg.loadGraph(filename) if merge is None else kg.loadGraph(filename, merge=merge)

    assert graph is kg.graph
    assert set(graph) == ({existing, shared, added} if merge is True else {shared, added})
    assert (graph is previous_graph) == (merge is True)
    assert dict(graph.namespaces())["custom"] == URIRef(custom)


@pytest.mark.parametrize("merge", [True, False])
@pytest.mark.parametrize("failure", ["missing", "invalid"])
def test_load_graph_failure_preserves_current_graph(graph_factory, tmp_path, merge, failure):
    kg = graph_factory()
    custom = Namespace("http://example.com/custom#")
    kg.graph.bind("custom", custom)
    kg.graph.add((custom.existing, RDFS.label, Literal("Existing")))
    previous_graph = kg.graph
    triples = set(kg.graph)
    namespaces = dict(kg.graph.namespaces())
    filename = tmp_path / "broken.ttl"
    if failure == "invalid":
        filename.write_text(
            '@prefix broken: <http://example.com/broken#> .\n'
            'broken:item broken:label "Parsed before failure" .\n'
            'undefined:item broken:label "Undefined prefix" .\n',
            encoding="utf-8",
        )
    error_type = FileNotFoundError if failure == "missing" else BadSyntax

    with pytest.raises(error_type):
        kg.loadGraph(filename, merge=merge)

    assert kg.graph is previous_graph
    assert set(kg.graph) == triples
    assert dict(kg.graph.namespaces()) == namespaces


@pytest.mark.parametrize("merge", [None, True, False])
def test_build_graph_preserves_metadata_and_refreshes_counts(graph_factory, tmp_path, merge):
    kg = graph_factory()
    kg.segments = [_segment("s1")]
    metric_uri = URIRef("http://analytics.com/test-company/rs1/metric/metrics/visits")
    legacy_uri = URIRef("http://example.com/legacy")
    legacy_label = (legacy_uri, RDFS.label, Literal("Saved entity"))
    old_usage = (metric_uri, kg.namespaces["usage"].segmentUsage, Literal(10, datatype=XSD.integer))
    saved = Graph()
    saved.add(legacy_label)
    saved.add(old_usage)
    saved.add((legacy_uri, URIRef("http://example.com/details"), BNode()))
    filename = tmp_path / "existing.ttl"
    saved.serialize(destination=str(filename), format="turtle")
    loaded_triples = set(kg.loadGraph(filename))
    exported = tmp_path / "extended.ttl"
    kwargs = {} if merge is None else {"merge": merge}

    graph = kg.buildGraph(save=True, filename=str(exported), **kwargs)

    assert graph is kg.graph
    segment_uri = URIRef("http://analytics.com/test-company/segment/s1")
    assert (segment_uri, RDF.type, Literal("Segment")) in graph
    counts = set(graph.objects(metric_uri, kg.namespaces["usage"].segmentUsage))
    if merge is False:
        assert legacy_label not in graph
    else:
        assert loaded_triples - {old_usage} <= set(graph)
    assert old_usage not in graph
    assert counts == {Literal(1, datatype=XSD.integer)}
    assert isomorphic(Graph().parse(str(exported), format="turtle"), graph)


def test_build_graph_preserves_previous_build_without_duplicating_identical_triples(graph_factory):
    kg = graph_factory()
    kg.segments = [_segment("first")]
    first_triples = set(kg.buildGraph())
    kg.segments = [_segment("second")]

    graph = kg.buildGraph()

    assert first_triples <= set(graph)
    for segment_id in ("first", "second"):
        uri = URIRef(f"http://analytics.com/test-company/segment/{segment_id}")
        assert (uri, RDF.type, Literal("Segment")) in graph
    triples = set(graph)
    assert set(kg.buildGraph()) == triples


def _project(project_id: str, repetitions: int = 1, dimension_id: str = "variables/evar1") -> dict:
    return {
        "id": project_id, "name": project_id, "rsid": "rs1",
        "definition": {"workspaces": [{"panels": [{
            "id": "panel", "name": "Panel", "position": {},
            "subPanels": [{
                "id": f"table-{index}", "name": "Table", "position": {},
                "reportlet": {
                    "type": "FreeformReportlet",
                    "columnTree": {"nodes": [
                        {"id": "metric", "component": {
                            "id": "metrics/visits", "type": "Metric",
                        }, "nodes": [{
                            "id": "segment", "component": {"id": "s1", "type": "Segment"},
                            "nodes": [],
                        }]},
                        {"id": "calculated", "component": {
                            "id": "cm1", "type": "CalculatedMetric",
                        }, "nodes": []},
                    ]},
                    "freeformTable": {
                        "dimension": {"id": dimension_id, "type": "Dimension"},
                        "staticRows": [], "breakdowns": [],
                    },
                },
            } for index in range(repetitions)],
        }]}]},
    }


@pytest.fixture
def project_graph_factory(graph_factory, monkeypatch):
    projects = {
        "old": _project("old"),
        "new": _project("new", repetitions=2),
        "third": _project("third"),
        "new_pair": _project("new_pair", dimension_id="variables/evar2"),
    }

    def create():
        kg = graph_factory()
        kg.dimensions["rs1"] = [{
            "id": "variables/evar1", "name": "Dimension", "type": "string",
            "reportable": ["oberon"], "segmentable": True,
        }]
        kg.metrics["rs1"] = [{
            "id": "metrics/visits", "name": "Visits", "type": "int",
            "support": ["oberon"], "segmentable": True, "polarity": "positive",
        }]
        kg.segments = [_segment("s1")]
        kg._segmentsById = {"s1": kg.segments[0]}
        kg.calculatedMetrics = [_calculated_metric("cm1")]
        kg.projects = list(projects.values())
        monkeypatch.setattr(
            kg.analyticsAPI, "getProject", lambda projectId: deepcopy(projects[projectId]),
        )
        return kg

    return create


@pytest.mark.parametrize("incremental", [False, True])
@pytest.mark.parametrize("flag_value", [None, False, True])
def test_project_metadata_is_added_to_graph(graph_factory, incremental, flag_value):
    kg = graph_factory()
    if incremental:
        kg.buildGraph()
    project = _project("metadata")
    project.update({
        "owner": {"id": 1, "name": "Test Owner", "login": "owner@example.test"},
        "tags": [{"id": 1, "name": "Team"}, {"id": 2, "name": ""}, {"id": 3}],
        "shares": [{"shareToType": "user", "shareToId": 2}, {"shareToType": "group", "shareToId": 3}],
    })
    fields = ("approved", "companyTemplate", "organizationTemplate")
    if flag_value is not None:
        project.update({field: flag_value for field in fields})
    kg.project_details = [WorkspaceManager(data=project)]

    graph = kg.buildGraph(incremental=incremental)

    project_ref = URIRef("http://analytics.com/test-company/projects/metadata")
    projects = kg.namespaces["projects"]
    assert graph.value(project_ref, projects.ownername) == Literal("Test Owner", datatype=XSD.string)
    assert graph.value(project_ref, projects.ownerlogin) == Literal("owner@example.test", datatype=XSD.string)
    assert set(graph.objects(project_ref, projects.tag)) == {Literal("Team")}
    assert graph.value(project_ref, projects.shares) == Literal(2, datatype=XSD.integer)
    for field in fields:
        expected = None if flag_value is None else Literal(flag_value, datatype=XSD.boolean)
        assert graph.value(project_ref, projects[field]) == expected


def test_project_metadata_refresh_replaces_previous_values(graph_factory):
    kg = graph_factory()
    project = _project("metadata")
    project.update({
        "owner": {"name": "Old Owner", "login": "old@example.test"},
        "tags": [{"id": 1, "name": "Old Tag"}],
        "shares": [{"shareToType": "all"}],
        "approved": True, "companyTemplate": True, "organizationTemplate": True,
    })
    workspace = WorkspaceManager(data=project)
    kg.project_details = [workspace]
    kg.buildGraph()
    project_ref = URIRef("http://analytics.com/test-company/projects/metadata")
    projects = kg.namespaces["projects"]
    custom = (project_ref, projects.customMetadata, Literal("Preserved"))
    kg.graph.add(custom)
    workspace.owner = {"name": "New Owner"}
    workspace.tags = []
    workspace.shares = []
    workspace.approved = False
    workspace.companyTemplate = None
    workspace.organizationTemplate = False

    graph = kg.buildGraph()

    assert set(graph.objects(project_ref, projects.ownername)) == {Literal("New Owner", datatype=XSD.string)}
    assert graph.value(project_ref, projects.ownerlogin) is None
    assert graph.value(project_ref, projects.tag) is None
    assert set(graph.objects(project_ref, projects.shares)) == {Literal(0, datatype=XSD.integer)}
    assert set(graph.objects(project_ref, projects.approved)) == {Literal(False, datatype=XSD.boolean)}
    assert graph.value(project_ref, projects.companyTemplate) is None
    assert set(graph.objects(project_ref, projects.organizationTemplate)) == {Literal(False, datatype=XSD.boolean)}
    assert custom in graph


def test_missing_project_metadata_is_not_invented(graph_factory):
    kg = graph_factory()
    kg.project_details = [WorkspaceManager(data=_project("metadata"))]

    graph = kg.buildGraph()

    project_ref = URIRef("http://analytics.com/test-company/projects/metadata")
    projects = kg.namespaces["projects"]
    for field in ("ownername", "ownerlogin", "tag", "approved", "companyTemplate", "organizationTemplate"):
        assert graph.value(project_ref, projects[field]) is None
    assert graph.value(project_ref, projects.shares) == Literal(0, datatype=XSD.integer)


@pytest.mark.parametrize("serialized", [False, True])
def test_incremental_build_matches_full_build_and_skips_component_work(
    project_graph_factory, monkeypatch, tmp_path, serialized,
):
    source = project_graph_factory()
    source.loadProjects(["old"])
    source.buildGraph()
    if serialized:
        filename = tmp_path / "base.ttl"
        source.exportGraph(str(filename))
        kg = project_graph_factory()
        kg.loadGraph(filename)
    else:
        kg = source
    graph = kg.graph
    usage = kg.namespaces["usage"]
    previous_nodes = set(graph.subjects(usage.cooccurrenceCount, None))
    kg.loadProjects(["old", "new"])
    kg.loadProjects(["new"])

    for attribute in (
        "dimensions", "metrics", "marketingChannels", "segments",
        "calculatedMetrics", "dateRanges",
    ):
        monkeypatch.setattr(kg, attribute, None)

    assert kg.buildGraph(incremental=True) is graph

    reference = project_graph_factory()
    reference.loadProjects(["old", "new"])
    assert isomorphic(graph, reference.buildGraph())
    assert set(graph.subjects(usage.cooccurrenceCount, None)) == previous_nodes
    for node in previous_nodes:
        assert list(graph.objects(node, usage.cooccurrenceCount)) == [
            Literal(3, datatype=XSD.integer),
        ]
    triples = set(graph)
    assert set(kg.buildGraph(incremental=True)) == triples


def test_incremental_counts_survive_multiple_turtle_round_trips(project_graph_factory, tmp_path):
    source = project_graph_factory()
    source.loadProjects(["old"])
    source.buildGraph(save=True, filename=str(tmp_path / "base.ttl"))
    kg = project_graph_factory()
    kg.loadGraph(tmp_path / "base.ttl")
    kg.loadProjects(["old", "new"])
    kg.buildGraph(incremental=True, save=True, filename=str(tmp_path / "extended.ttl"))

    restored = project_graph_factory()
    restored.loadGraph(tmp_path / "extended.ttl")
    restored.loadProjects(["old", "new", "third"])
    graph = restored.buildGraph(incremental=True)

    reference = project_graph_factory()
    reference.loadProjects(["old", "new", "third"])
    assert isomorphic(graph, reference.buildGraph())
    metric = URIRef("http://analytics.com/test-company/rs1/metric/metrics/visits")
    assert restored.getUsageCounts()[metric] == {
        "segmentUsage": 1, "metricUsage": 0, "projectUsage": 4,
    }


@pytest.mark.parametrize("incremental", [False, True])
def test_build_records_all_freeform_components_without_project_json(
    project_graph_factory, monkeypatch, tmp_path, incremental,
):
    kg = project_graph_factory()
    if incremental:
        kg.loadProjects(["old"])
        kg.buildGraph(save=True, filename=str(tmp_path / "base.ttl"))
        kg = project_graph_factory()
        kg.loadGraph(tmp_path / "base.ttl")
    project_data = _project("new", repetitions=2)
    primary, secondary = project_data["definition"]["workspaces"][0]["panels"][0]["subPanels"]
    primary.update({"name": "Primary table", "description": "First freeform"})
    primary["reportlet"]["freeformTable"]["dimension"]["id"] = "variables/evar1::item"
    primary["reportlet"]["freeformTable"]["breakdowns"] = [{
        "dimension": {"id": "variables/evar3", "type": "Dimension"},
        "breakdowns": [],
    }]
    secondary["name"] = "Secondary table"
    secondary["reportlet"]["freeformTable"]["dimension"]["id"] = "variables/evar2"
    columns = secondary["reportlet"]["columnTree"]["nodes"]
    columns[0]["component"]["id"] = "metrics/pageviews"
    columns[0]["nodes"][0]["component"]["id"] = "s2"
    columns[1]["component"]["id"] = "cm2"
    monkeypatch.setattr(
        kg.analyticsAPI, "getProject", lambda projectId: deepcopy(project_data),
    )
    kg.loadProjects(["new"])

    graph = kg.buildGraph(incremental=incremental)

    projects = kg.namespaces["projects"]
    project = URIRef("http://analytics.com/test-company/projects/new")
    expected_components = {
        ("dimension_ref", "dimensions"): {
            URIRef(f"http://analytics.com/test-company/rs1/dimension/variables/evar{index}")
            for index in (1, 2, 3)
        },
        ("metric_ref", "metrics"): {
            URIRef(f"http://analytics.com/test-company/rs1/metric/metrics/{metric}")
            for metric in ("visits", "pageviews")
        },
        ("calculated_ref", "calculatedMetrics"): {
            URIRef(f"http://analytics.com/test-company/calculatedMetric/cm{index}")
            for index in (1, 2)
        },
        ("segment_ref", "segments"): {
            URIRef(f"http://analytics.com/test-company/segment/s{index}")
            for index in (1, 2)
        },
    }
    filename = tmp_path / "components.ttl"
    kg.exportGraph(str(filename))
    for snapshot in (graph, Graph().parse(str(filename), format="turtle")):
        assert set(snapshot.objects(project, projects.panelFreeForm)) == {
            Literal("Primary table: First freeform", datatype=XSD.string),
            Literal("Secondary table", datatype=XSD.string),
        }
        for (backlink, forward_link), components in expected_components.items():
            assert set(snapshot.subjects(projects[backlink], project)) == components
            assert set(snapshot.objects(project, projects[forward_link])) == components
        assert not list(snapshot.triples((None, projects.definition, None)))
    visits = URIRef("http://analytics.com/test-company/rs1/metric/metrics/visits")
    assert kg.getUsageCounts()[visits]["projectUsage"] == (2 if incremental else 1)


def test_incremental_build_restores_project_links_from_legacy_backlinks(
    project_graph_factory, tmp_path,
):
    source = project_graph_factory()
    source.loadProjects(["old"])
    source.buildGraph()
    projects = source.namespaces["projects"]
    for field in ("dimensions", "metrics", "calculatedMetrics", "segments"):
        source.graph.remove((None, projects[field], None))
    source.graph.remove((None, projects.segment_ref, None))
    source.graph.add((
        URIRef("http://analytics.com/test-company/projects/old"),
        projects.definition, Literal('{"legacy": "project JSON"}', datatype=XSD.string),
    ))
    source.exportGraph(str(tmp_path / "legacy.ttl"))
    kg = project_graph_factory()
    kg.loadGraph(tmp_path / "legacy.ttl")
    counts = kg.getUsageCounts()
    cooccurrences = dict(kg.dim_metric_cooccurrence)
    assert kg.project_details == []

    graph = kg.buildGraph(incremental=True)

    project = URIRef("http://analytics.com/test-company/projects/old")
    assert set(graph.objects(project, projects.dimensions)) == {
        URIRef("http://analytics.com/test-company/rs1/dimension/variables/evar1"),
    }
    assert set(graph.objects(project, projects.metrics)) == {
        URIRef("http://analytics.com/test-company/rs1/metric/metrics/visits"),
    }
    assert set(graph.objects(project, projects.calculatedMetrics)) == {
        URIRef("http://analytics.com/test-company/calculatedMetric/cm1"),
    }
    assert list(graph.objects(project, projects.panelFreeForm)) == [
        Literal("Table", datatype=XSD.string),
    ]
    assert not list(graph.triples((None, projects.definition, None)))
    assert kg.getUsageCounts() == counts
    assert kg.dim_metric_cooccurrence == cooccurrences
    triples = set(graph)
    assert set(kg.buildGraph(incremental=True)) == triples


def test_build_registers_manual_workspace_without_serializing_json(
    project_graph_factory, monkeypatch,
):
    kg = project_graph_factory()
    workspace = WorkspaceManager(_project("manual"))
    kg.project_details.append(workspace)

    def unexpected_serialization():
        raise AssertionError("Project JSON must not be serialized")

    monkeypatch.setattr(workspace, "to_dict", unexpected_serialization)

    graph = kg.buildGraph()

    project = URIRef("http://analytics.com/test-company/projects/manual")
    assert set(graph.objects(project, kg.namespaces["projects"].dimensions)) == {
        URIRef("http://analytics.com/test-company/rs1/dimension/variables/evar1"),
    }
    assert not list(graph.triples((None, kg.namespaces["projects"].definition, None)))


def test_incremental_build_creates_new_cooccurrence_pairs(project_graph_factory):
    kg = project_graph_factory()
    kg.loadProjects(["old"])
    kg.buildGraph()
    kg.loadProjects(["new_pair"])

    graph = kg.buildGraph(incremental=True)

    reference = project_graph_factory()
    reference.loadProjects(["old", "new_pair"])
    assert isomorphic(graph, reference.buildGraph())
    counts = [
        int(count) for count in graph.objects(None, kg.namespaces["usage"].cooccurrenceCount)
    ]
    assert sorted(counts) == [1] * 6


def test_usage_counts_returns_independent_python_dictionary(project_graph_factory):
    kg = project_graph_factory()
    assert kg.getUsageCounts() == {}
    kg.loadProjects(["old"])
    kg.buildGraph()
    counts = kg.getUsageCounts()
    assert all(type(count) is int for fields in counts.values() for count in fields.values())
    metric = URIRef("http://analytics.com/test-company/rs1/metric/metrics/visits")
    counts[metric]["projectUsage"] = 99

    assert kg.getUsageCounts()[metric]["projectUsage"] == 1


def test_incremental_build_without_new_projects_is_no_op(project_graph_factory):
    kg = project_graph_factory()
    kg.buildGraph()
    triples = set(kg.graph)

    assert set(kg.buildGraph(incremental=True)) == triples


@pytest.mark.parametrize("invalid_count", [
    Literal(-1), Literal(True), Literal("invalid"), Literal(1.5),
])
def test_incremental_build_rejects_invalid_usage_counts_without_mutation(
    project_graph_factory, invalid_count,
):
    kg = project_graph_factory()
    kg.loadProjects(["old"])
    kg.buildGraph()
    metric = URIRef("http://analytics.com/test-company/rs1/metric/metrics/visits")
    kg.graph.set((metric, kg.namespaces["usage"].projectUsage, invalid_count))
    kg.loadProjects(["new"])
    triples = set(kg.graph)

    with pytest.raises(ValueError, match="non-negative integer"):
        kg.buildGraph(incremental=True)

    assert set(kg.graph) == triples


def test_incremental_build_rejects_ambiguous_usage_counts(project_graph_factory):
    kg = project_graph_factory()
    kg.loadProjects(["old"])
    kg.buildGraph()
    metric = URIRef("http://analytics.com/test-company/rs1/metric/metrics/visits")
    kg.graph.add((metric, kg.namespaces["usage"].projectUsage, Literal(10)))
    kg.loadProjects(["new"])
    triples = set(kg.graph)

    with pytest.raises(ValueError, match="exactly one"):
        kg.buildGraph(incremental=True)

    assert set(kg.graph) == triples


@pytest.mark.parametrize("problem", ["invalid_count", "missing_dimension", "duplicate_pair"])
def test_incremental_build_rejects_invalid_cooccurrences_without_mutation(
    project_graph_factory, problem,
):
    kg = project_graph_factory()
    kg.loadProjects(["old"])
    kg.buildGraph()
    usage = kg.namespaces["usage"]
    node = next(kg.graph.subjects(RDF.type, Literal("MetricCooccurrence")))
    if problem == "invalid_count":
        kg.graph.set((node, usage.cooccurrenceCount, Literal(-1)))
    elif problem == "missing_dimension":
        kg.graph.remove((node, usage.dimension, None))
    else:
        duplicate = BNode()
        for predicate, value in list(kg.graph.predicate_objects(node)):
            kg.graph.add((duplicate, predicate, value))
    kg.loadProjects(["new"])
    triples = set(kg.graph)

    with pytest.raises(ValueError):
        kg.buildGraph(incremental=True)

    assert set(kg.graph) == triples


@pytest.mark.parametrize("empty_graph", [True, False])
def test_incremental_build_requires_existing_graph_and_merge(project_graph_factory, empty_graph):
    kg = project_graph_factory()
    if not empty_graph:
        kg.buildGraph()
    triples = set(kg.graph)
    kwargs = {} if empty_graph else {"merge": False}

    with pytest.raises(ValueError, match="existing graph" if empty_graph else "merge=True"):
        kg.buildGraph(incremental=True, **kwargs)

    assert set(kg.graph) == triples


def test_load_graph_restores_per_instance_counter_dictionaries(project_graph_factory, tmp_path):
    source = project_graph_factory()
    source.loadProjects(["old"])
    source.buildGraph(save=True, filename=str(tmp_path / "base.ttl"))
    restored = project_graph_factory()

    restored.loadGraph(tmp_path / "base.ttl")

    assert restored.entity_usage == source.entity_usage == restored.getUsageCounts()
    assert restored.dim_metric_cooccurrence == source.dim_metric_cooccurrence
    assert restored.dim_segment_cooccurrence == source.dim_segment_cooccurrence
    assert restored.dim_metric_cooccurrence is not source.dim_metric_cooccurrence
    assert restored.dim_segment_cooccurrence is not source.dim_segment_cooccurrence
    assert restored.dim_metric_cooccurrence is not None
    assert restored.dim_segment_cooccurrence is not None
    assert source.dim_metric_cooccurrence is not None
    assert source.dim_segment_cooccurrence is not None
    assert list(restored.dim_metric_cooccurrence.values()) == [1, 1]
    assert list(restored.dim_segment_cooccurrence.values()) == [1]

    restored.loadProjects(["new"])
    restored.buildGraph(incremental=True)

    assert restored.entity_usage == restored.getUsageCounts()
    assert list(restored.dim_metric_cooccurrence.values()) == [3, 3]
    assert list(restored.dim_segment_cooccurrence.values()) == [3]
    assert list(source.dim_metric_cooccurrence.values()) == [1, 1]
    assert list(source.dim_segment_cooccurrence.values()) == [1]


def test_replacing_loaded_graph_replaces_counter_state(project_graph_factory, tmp_path):
    kg = project_graph_factory()
    kg.loadProjects(["old"])
    kg.buildGraph()
    filename = tmp_path / "empty.ttl"
    filename.write_text("", encoding="utf-8")

    kg.loadGraph(filename, merge=False)

    assert kg.entity_usage == {}
    assert kg.dim_metric_cooccurrence == {}
    assert kg.dim_segment_cooccurrence == {}


def test_ambiguous_loaded_counters_warn_without_changing_union_behavior(
    project_graph_factory, tmp_path, caplog,
):
    kg = project_graph_factory()
    kg.loadProjects(["old"])
    kg.buildGraph()
    metric = URIRef("http://analytics.com/test-company/rs1/metric/metrics/visits")
    extra = Graph()
    extra.add((metric, kg.namespaces["usage"].projectUsage, Literal(10)))
    filename = tmp_path / "extra.ttl"
    extra.serialize(destination=str(filename), format="turtle")

    with caplog.at_level(logging.WARNING, logger="aanalytics2.knowledgegraph"):
        kg.loadGraph(filename, merge=True)

    assert kg.entity_usage is None
    assert kg.dim_metric_cooccurrence is None
    assert kg.dim_segment_cooccurrence is None
    assert "counters cannot be initialized" in caplog.text
    assert set(kg.graph.objects(metric, kg.namespaces["usage"].projectUsage)) == {
        Literal(1), Literal(10),
    }
    with pytest.raises(ValueError, match="exactly one"):
        kg.buildGraph(incremental=True)

    kg.buildGraph()
    assert kg.entity_usage == kg.getUsageCounts()
    assert kg.entity_usage is not None
    assert kg.entity_usage[metric]["projectUsage"] == 1


def test_full_build_replaces_counter_snapshot_before_incremental_build(project_graph_factory):
    kg = project_graph_factory()
    kg.loadProjects(["old", "new"])
    kg.buildGraph()
    metric = URIRef("http://analytics.com/test-company/rs1/metric/metrics/visits")
    assert kg.getUsageCounts()[metric]["projectUsage"] == 3
    kg.project_details = []

    kg.buildGraph()

    assert kg.getUsageCounts()[metric].get("projectUsage", 0) == 0
    assert kg.dim_metric_cooccurrence == {}
    assert kg.dim_segment_cooccurrence == {}
    kg.loadProjects(["old"])
    kg.buildGraph(incremental=True)
    assert kg.getUsageCounts()[metric]["projectUsage"] == 1
    assert list(kg.graph.objects(metric, kg.namespaces["usage"].projectUsage)) == [Literal(1)]


def test_incremental_save_preserves_original_turtle_snapshot(project_graph_factory, tmp_path):
    source = project_graph_factory()
    source.loadProjects(["old"])
    original = tmp_path / "original.ttl"
    source.buildGraph(save=True, filename=str(original))
    original_bytes = original.read_bytes()
    kg = project_graph_factory()
    kg.loadGraph(original)
    kg.loadProjects(["new"])

    kg.buildGraph(incremental=True, save=True, filename=str(tmp_path / "new_snapshot.ttl"))

    assert original.read_bytes() == original_bytes
    assert isomorphic(Graph().parse(str(original), format="turtle"), source.graph)
    assert isomorphic(Graph().parse(str(tmp_path / "new_snapshot.ttl"), format="turtle"), kg.graph)
