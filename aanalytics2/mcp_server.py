"""
MCP server exposing Adobe Analytics (via aanalytics2) as tools for an LLM client.

See docs/mcp_plan.md for the design this implements. Covers Phase 1 + Phase 2:
Discovery, Reporting, WorkspaceManager and Knowledge Graph (local .ttl only) tool
groups. Remote SPARQL endpoints (-kg-endpoint) and KG-enhanced suggestions are
Phase 3 and not implemented here.

Run directly with `python -m aanalytics2.mcp_server`, or via the `aanalytics2-mcp`
console script once installed.
"""
import argparse
import json
import sys
from importlib import resources as importlib_resources
from pathlib import Path
from typing import Optional

from rdflib import Graph, Literal, URIRef

from aanalytics2 import Analytics, Login
from aanalytics2.configs import importConfigFile, find_path
from aanalytics2.requestCreator import RequestCreator
from aanalytics2.workspaceManager import WorkspaceManager, FreeForm

from mcp.server.fastmcp import FastMCP


def _default_ontology_md() -> str:
    """The ontology reference bundled with the package (docs/knowledgegraph.md's Ontology
    section, kept in sync by hand): entity types, predicates and namespace patterns produced
    by KnowledgeGraph.buildGraph(). Overridable at the CLI with -kg-ontology for graphs that
    add custom predicates/literals on top of this base schema."""
    return (
        importlib_resources.files("aanalytics2")
        .joinpath("resources", "kg_ontology.md")
        .read_text(encoding="utf-8")
    )


def _resolve_date_range(rc: RequestCreator, date_range: str) -> str:
    # rc.dates (preset name -> literal ISO interval) is computed from datetime.now()
    # at RequestCreator() construction time, so it must be read from the same instance
    # that will run the request rather than cached once at server startup.
    return rc.dates.get(date_range, date_range)


def _df_to_records(df) -> list:
    """Convert a pandas DataFrame to plain JSON-safe dicts (NaN -> None) via pandas' own JSON codec."""
    if df is None or len(df) == 0:
        return []
    return json.loads(df.to_json(orient="records", date_format="iso"))


def _company_id_from_config_file(path: str) -> Optional[str]:
    """The `companyId`/`company_id` field the CLI also honors (see cli/__main__.py
    _resolve_config). importConfigFile/ConfigObj drop it since it plays no part in
    authentication, so it has to be read straight from the raw JSON here too, instead
    of always falling back to the first company the credential happens to have access to."""
    config_file_path = find_path(path)
    if config_file_path is None:
        return None
    with open(config_file_path, "r", encoding="utf-8") as fh:
        raw = json.load(fh)
    return raw.get("companyId") or raw.get("company_id")


def _find_freeform_subpanel(wm: WorkspaceManager, table_title: str) -> dict:
    # wm.panels re-parses a fresh, throwaway Panel/FreeForm tree on every access (see
    # WorkspaceManager.panels), so mutating it would never reach wm.to_dict(). The raw
    # sub-panel dicts in wm._panels are what to_dict() actually serialises, so a table
    # has to be located and patched there directly to make add_breakdown stick.
    for panel in wm._panels:
        for sp in panel.get("subPanels", []):
            reportlet = sp.get("reportlet", {})
            if reportlet.get("type") == "FreeformReportlet" and sp.get("name") == table_title:
                return sp
    raise ValueError(f"No FreeForm table named {table_title!r} found in this project.")


def build_server(
    analytics: Analytics,
    company_id: str,
    default_rsid: Optional[str] = None,
    kg_graph: Optional[Graph] = None,
    ontology_md: Optional[str] = None,
) -> FastMCP:
    mcp = FastMCP(
        "aanalytics2",
        instructions=(
            "Adobe Analytics tools (Discovery, Reporting, Workspace building) plus, when a "
            "Knowledge Graph is connected (server started with -kg), read-only access to usage "
            "and co-occurrence relationships between components. Before calling sparql_query or "
            "the get_related_*/get_popular_combinations/get_component_context tools, read the "
            "'ontology://knowledge-graph' resource for the entity types, predicates and namespace "
            "patterns the graph uses."
        ),
    )

    ns = {
        "dim": f"http://analytics.com/{company_id}/dimension#",
        "met": f"http://analytics.com/{company_id}/metric#",
        "seg": f"http://analytics.com/{company_id}/segment#",
        "cm": f"http://analytics.com/{company_id}/calculatedMetric#",
        "usage": f"http://analytics.com/{company_id}/usage#",
    }
    prefix_header = (
        "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\n"
        f"PREFIX dim: <{ns['dim']}>\n"
        f"PREFIX met: <{ns['met']}>\n"
        f"PREFIX seg: <{ns['seg']}>\n"
        f"PREFIX cm: <{ns['cm']}>\n"
        f"PREFIX usage: <{ns['usage']}>\n"
    )

    def _dim_uri(rsid: str, dimension_id: str) -> URIRef:
        return URIRef(f"http://analytics.com/{company_id}/{rsid}/dimension/{dimension_id}")

    def _met_uri(rsid: str, metric_id: str) -> URIRef:
        return URIRef(f"http://analytics.com/{company_id}/{rsid}/metric/{metric_id}")

    def _rsid_uri(rsid: str) -> URIRef:
        return URIRef(f"http://analytics.com/{company_id}/reportSuite#{rsid}")

    def _require_rsid(rsid: Optional[str]) -> str:
        rsid = rsid or default_rsid
        if not rsid:
            raise ValueError("rsid is required (no default report suite was configured with -rsid).")
        return rsid

    def _require_kg() -> Graph:
        if kg_graph is None:
            raise ValueError("Knowledge Graph not connected. Restart the server with -kg <file.ttl>.")
        return kg_graph

    def _local_id(uri) -> str:
        return str(uri).rsplit("/", 1)[-1]

    def _apply_filter(records: list, filter: Optional[str], key: str = "name") -> list:
        if not filter:
            return records
        needle = filter.lower()
        return [r for r in records if needle in str(r.get(key, "")).lower()]

    # ── Group 1 — Discovery ──────────────────────────────────────────────

    @mcp.tool()
    def list_report_suites(filter: str = None) -> list:
        """List report suites available to this connection. Optional case-insensitive
        substring `filter` on the report suite name."""
        df = analytics.getReportSuites(extended_info=True)
        return _apply_filter(_df_to_records(df), filter)

    @mcp.tool()
    def list_dimensions(rsid: str = None, filter: str = None) -> list:
        """List dimensions available in a report suite (id, name, type, description).
        Optional case-insensitive substring `filter` on the dimension name."""
        rsid = _require_rsid(rsid)
        records = analytics.getDimensions(rsid=rsid, description=True, format="raw")
        return _apply_filter(records, filter)

    @mcp.tool()
    def list_metrics(rsid: str = None, filter: str = None) -> list:
        """List metrics available in a report suite (id, name, type, description).
        Optional case-insensitive substring `filter` on the metric name."""
        rsid = _require_rsid(rsid)
        records = analytics.getMetrics(rsid=rsid, description=True, format="raw")
        return _apply_filter(records, filter)

    @mcp.tool()
    def list_segments(rsid: str = None, filter: str = None) -> list:
        """List segments (id, name, description). Scoped to `rsid` if provided,
        otherwise all segments visible to this connection. Optional case-insensitive
        substring `filter` on the segment name."""
        records = analytics.getSegments(
            rsids_list=[rsid] if rsid else None, extended_info=True, format="raw"
        )
        return _apply_filter(records, filter)

    @mcp.tool()
    def list_calculated_metrics(filter: str = None) -> list:
        """List calculated metrics (id, name, description). Optional case-insensitive
        substring `filter` on the name."""
        records = analytics.getCalculatedMetrics(extended_info=True, format="raw")
        return _apply_filter(records, filter)

    @mcp.tool()
    def list_date_ranges(filter: str = None) -> list:
        """List saved date ranges (id, name). Optional case-insensitive substring
        `filter` on the name."""
        records = analytics.getDateRanges(extended_info=True, format="raw")
        return _apply_filter(records, filter)

    @mcp.tool()
    def list_projects(filter: str = None) -> list:
        """List Workspace projects (id, name, rsid, owner). Optional case-insensitive
        substring `filter` on the project name."""
        records = analytics.getProjects(format="raw")
        return _apply_filter(records, filter)

    @mcp.tool()
    def get_segment(segment_id: str) -> dict:
        """Return the full definition of a single segment by ID."""
        return analytics.getSegment(segment_id, full=True)

    @mcp.tool()
    def get_project(project_id: str) -> dict:
        """Return the full definition of a single Workspace project by ID."""
        return analytics.getProject(projectId=project_id)

    # ── Group 2 — Reporting ──────────────────────────────────────────────

    @mcp.tool()
    def build_report_request(
        dimension_id: str,
        metrics: list,
        date_range: str,
        rsid: str = None,
        segment_ids: list = None,
        limit: int = 100,
    ) -> dict:
        """Build a report request dict (compatible with run_report) from high-level
        parameters. Does not call the API — inspect or hand-edit the returned dict
        before passing it to run_report.

        Arguments:
            dimension_id : Dimension ID, e.g. "variables/eVar1".
            metrics      : List of {"id": "metrics/visits", ...} dicts (only "id" is used).
            date_range   : ISO 8601 interval ("2024-01-01/2024-03-31") or a preset name
                           ("thisMonth", "untilToday", "todayIncluded", "last30daysTillToday",
                           "last30daysTodayIncluded", "last7daysTillToday", "last7daysTodayIncluded").
            rsid         : Report suite ID. Falls back to the server's default -rsid if omitted.
            segment_ids  : Optional list of segment IDs added as global filters.
            limit        : Row limit (default 100).
        """
        rsid = _require_rsid(rsid)
        rc = RequestCreator()
        rc.setRSID(rsid)
        rc.setDimension(dimension_id)
        for m in metrics:
            rc.addMetric(m["id"] if isinstance(m, dict) else m)
        for sid in segment_ids or []:
            rc.addGlobalFilter(sid)
        rc.setDateRange(dateRange=_resolve_date_range(rc, date_range))
        rc.setLimit(limit)
        return rc.to_dict()

    @mcp.tool()
    def run_report(request: dict, n_results: int = 50) -> dict:
        """Run a report request (from build_report_request or hand-built) and return
        the top rows. `n_results` caps returned rows (default 50) to avoid overflowing
        the LLM context on wide/long reports."""
        workspace = analytics.getReport2(request=request, n_results=n_results)
        if not hasattr(workspace, "dataframe"):
            return {"raw": workspace}
        return {
            "rows": _df_to_records(workspace.dataframe),
            "row_count": workspace.row_numbers,
            "columns": list(workspace.columns),
        }

    @mcp.tool()
    def get_top_items(
        dimension_id: str,
        rsid: str = None,
        date_range: str = "last30daysTillToday",
        metric_id: str = "metrics/visits",
        limit: int = 10,
    ) -> list:
        """Quick look-up of the top values for a dimension, without building a full
        report. Defaults to ranking by `metrics/visits` over the last 30 days."""
        rsid = _require_rsid(rsid)
        rc = RequestCreator()
        rc.setRSID(rsid)
        rc.setDimension(dimension_id)
        rc.addMetric(metric_id)
        rc.setDateRange(dateRange=_resolve_date_range(rc, date_range))
        rc.setLimit(limit)
        workspace = analytics.getReport2(request=rc.to_dict(), n_results=limit)
        if not hasattr(workspace, "dataframe"):
            return []
        records = _df_to_records(workspace.dataframe)
        label_col = workspace.columns[0]
        return [{"value": r.get(label_col), "itemId": r.get("itemId")} for r in records]

    # ── Group 3 — WorkspaceManager (stateless: project dict in, project dict out) ──

    @mcp.tool()
    def create_workspace(rsid: str, name: str, description: str = "") -> dict:
        """Start a new Workspace project definition. Returns a project dict — pass it
        to add_panel/add_freeform/etc., then publish_workspace to save it."""
        wm = WorkspaceManager(rsid=rsid, name=name, description=description, analytics=analytics)
        return wm.to_dict()

    @mcp.tool()
    def add_panel(project: dict, name: str, date_range: str = "thisMonth", description: str = "") -> dict:
        """Add a new panel to the project. Subsequent add_* calls target this panel."""
        wm = WorkspaceManager(data=project, analytics=analytics)
        wm.addPanel(name=name, date_range=date_range, description=description)
        return wm.to_dict()

    @mcp.tool()
    def add_segment_filter(project: dict, segment: str) -> dict:
        """Add a global segment filter (ID or name) to the current panel."""
        wm = WorkspaceManager(data=project, analytics=analytics)
        wm.addSegmentFilter(segment=segment)
        return wm.to_dict()

    @mcp.tool()
    def add_dropdown_filter(project: dict, group_name: str, components: list, has_no_filter: bool = True) -> dict:
        """Add a dropdown filter group to the current panel. Each item in `components`
        needs "id"/"name", optional "type" ("Segment" default, or "DimensionItem") and
        "isActive"."""
        wm = WorkspaceManager(data=project, analytics=analytics)
        wm.addDropdownFilter(group_name=group_name, components=components, has_no_filter=has_no_filter)
        return wm.to_dict()

    @mcp.tool()
    def add_text(project: dict, title: str, content: str) -> dict:
        """Add a free-text panel element."""
        wm = WorkspaceManager(data=project, analytics=analytics)
        wm.addTextFreeform(title=title, content=content)
        return wm.to_dict()

    @mcp.tool()
    def add_freeform(
        project: dict,
        title: str,
        metrics: list,
        item_id: str = None,
        item_name: str = "",
        items: list = None,
        rows: int = 10,
    ) -> dict:
        """Add a freeform table to the current panel. Provide either a single dynamic
        row dimension (`item_id` + optional `item_name`) or static rows (`items`, a list
        of {"id", "name", "type"?} dicts — "type" is "Segment" or "DimensionItem").
        `metrics` is a list of {"id", "name"} dicts; each may include a "filters" list
        for column-level splitting."""
        wm = WorkspaceManager(data=project, analytics=analytics)
        wm.addFreeform(title=title, item_id=item_id, item_name=item_name, items=items,
                        metrics=metrics, rows=rows)
        return wm.to_dict()

    @mcp.tool()
    def add_breakdown(
        project: dict,
        table_title: str,
        dimension_id: str = None,
        dimension_name: str = None,
        items: list = None,
        rows: int = 5,
    ) -> dict:
        """Nest a breakdown under an existing freeform table (matched by its title).
        Provide either `dimension_id` (+ optional `dimension_name`) for a dynamic
        breakdown, or `items` (list of {"id", "name", "type"?} dicts) for static rows."""
        wm = WorkspaceManager(data=project, analytics=analytics)
        subpanel = _find_freeform_subpanel(wm, table_title)
        ff = FreeForm.from_dict(subpanel["reportlet"])
        ff.addBreakdown(dimension_id=dimension_id, dimension_name=dimension_name, items=items, rows=rows)
        subpanel["reportlet"] = ff.to_dict()
        return wm.to_dict()

    @mcp.tool()
    def add_chart(project: dict, viz_type: str, source=None, title: str = "") -> dict:
        """Add a chart visualization linked to a freeform table in the current panel.
        `viz_type`: line, bar, bar_horizontal, bar_stacked, area, area_stacked, donut,
        scatter, treemap, histogram, bullet, venn. `source` (table name or index)
        defaults to the most recently added freeform table."""
        wm = WorkspaceManager(data=project, analytics=analytics)
        wm.addChart(viz_type=viz_type, source=source, title=title)
        return wm.to_dict()

    @mcp.tool()
    def add_segment_comparison_table(
        project: dict,
        title: str,
        segments: list,
        metrics: list,
        breakdown_dim_id: str = None,
        breakdown_dim_name: str = "",
        breakdown_segments: list = None,
        rows: int = 50,
        breakdown_rows: int = 5,
    ) -> dict:
        """Add a freeform table where each row is a segment (side-by-side segment
        comparison), optionally broken down further by a dimension or nested segments."""
        wm = WorkspaceManager(data=project, analytics=analytics)
        wm.addSegmentAsDimensionFreeform(
            title=title, segments=segments, metrics=metrics,
            breakdown_dim_id=breakdown_dim_id, breakdown_dim_name=breakdown_dim_name,
            breakdown_segments=breakdown_segments, breakdown_rows=breakdown_rows, rows=rows,
        )
        return wm.to_dict()

    @mcp.tool()
    def publish_workspace(project: dict) -> dict:
        """Save a project dict as a new Workspace project via the Analytics API."""
        return analytics.createProject(project)

    # ── Group 4 — Knowledge Graph (read-only; local .ttl only, no remote endpoint yet) ──

    @mcp.resource(
        "ontology://knowledge-graph",
        name="kg_ontology",
        description="Knowledge Graph ontology reference: entity types, predicates and namespace "
                    "patterns used by the KG tools and sparql_query. Defaults to the schema produced "
                    "by KnowledgeGraph.buildGraph(); a server started with -kg-ontology <file.md> "
                    "serves a custom ontology here instead (e.g. one extended with extra predicates).",
        mime_type="text/markdown",
    )
    def kg_ontology() -> str:
        return ontology_md or "No Knowledge Graph ontology available."

    @mcp.tool()
    def get_related_metrics(dimension_id: str, rsid: str = None, limit: int = 10) -> list:
        """Metrics most frequently used with this dimension across loaded projects,
        ordered by co-occurrence count."""
        graph = _require_kg()
        rsid = _require_rsid(rsid)
        q = prefix_header + f"""
        SELECT ?metric ?label ?count WHERE {{
            ?node usage:dimension ?dim ; usage:metric ?metric ; usage:cooccurrenceCount ?count .
            OPTIONAL {{ ?metric rdfs:label ?label }}
        }} ORDER BY DESC(?count) LIMIT {int(limit)}
        """
        rows = graph.query(q, initBindings={"dim": _dim_uri(rsid, dimension_id)})
        return [{"metric_id": _local_id(r.metric), "name": str(r.label) if r.label else None,
                 "count": int(r.count)} for r in rows]

    @mcp.tool()
    def get_related_dimensions(metric_id: str, rsid: str = None, limit: int = 10) -> list:
        """Dimensions most frequently used with this metric across loaded projects,
        ordered by co-occurrence count."""
        graph = _require_kg()
        rsid = _require_rsid(rsid)
        q = prefix_header + f"""
        SELECT ?dimension ?label ?count WHERE {{
            ?node usage:metric ?met ; usage:dimension ?dimension ; usage:cooccurrenceCount ?count .
            OPTIONAL {{ ?dimension rdfs:label ?label }}
        }} ORDER BY DESC(?count) LIMIT {int(limit)}
        """
        rows = graph.query(q, initBindings={"met": _met_uri(rsid, metric_id)})
        return [{"dimension_id": _local_id(r.dimension), "name": str(r.label) if r.label else None,
                 "count": int(r.count)} for r in rows]

    @mcp.tool()
    def get_related_segments(dimension_id: str = None, rsid: str = None, limit: int = 10) -> list:
        """Segments most commonly applied alongside this dimension across loaded
        projects. Only dimension-based lookup is supported today — the Knowledge Graph
        does not track a direct metric<->segment co-occurrence."""
        graph = _require_kg()
        if not dimension_id:
            return []
        rsid = _require_rsid(rsid)
        q = prefix_header + f"""
        SELECT ?segment ?label ?count WHERE {{
            ?node usage:dimension ?dim ; usage:segment ?segment ; usage:cooccurrenceCount ?count .
            OPTIONAL {{ ?segment rdfs:label ?label }}
        }} ORDER BY DESC(?count) LIMIT {int(limit)}
        """
        rows = graph.query(q, initBindings={"dim": _dim_uri(rsid, dimension_id)})
        return [{"segment_id": _local_id(r.segment), "name": str(r.label) if r.label else None,
                 "count": int(r.count)} for r in rows]

    @mcp.tool()
    def get_popular_combinations(rsid: str = None, limit: int = 10) -> list:
        """Top dimension+metric pairs by co-occurrence count in this report suite."""
        graph = _require_kg()
        rsid = _require_rsid(rsid)
        q = prefix_header + f"""
        SELECT ?dim ?dimLabel ?metric ?metLabel ?count WHERE {{
            ?node usage:dimension ?dim ; usage:metric ?metric ; usage:cooccurrenceCount ?count ; usage:rsid ?rs .
            OPTIONAL {{ ?dim rdfs:label ?dimLabel }}
            OPTIONAL {{ ?metric rdfs:label ?metLabel }}
        }} ORDER BY DESC(?count) LIMIT {int(limit)}
        """
        rows = graph.query(q, initBindings={"rs": _rsid_uri(rsid)})
        return [{"dimension_id": _local_id(r.dim), "dimension_name": str(r.dimLabel) if r.dimLabel else None,
                 "metric_id": _local_id(r.metric), "metric_name": str(r.metLabel) if r.metLabel else None,
                 "count": int(r.count)} for r in rows]

    @mcp.tool()
    def get_component_context(component_id: str) -> dict:
        """All Knowledge Graph facts about a single component (dimension, metric,
        segment or calculated metric), looked up by its raw ID: name, description,
        which report suite(s) it belongs to, usage counters, and its top co-occurring
        partners. Returns one entry per matching component (an ID can match more than
        one entity if it is reused across report suites)."""
        graph = _require_kg()
        find_q = prefix_header + """
        SELECT ?s ?kind ?label ?comment ?rs WHERE {
            { ?s dim:id ?cid . BIND("dimension" AS ?kind) }
            UNION { ?s met:id ?cid . BIND("metric" AS ?kind) }
            UNION { ?s seg:id ?cid . BIND("segment" AS ?kind) }
            UNION { ?s cm:id ?cid . BIND("calculatedMetric" AS ?kind) }
            OPTIONAL { ?s rdfs:label ?label }
            OPTIONAL { ?s rdfs:comment ?comment }
            OPTIONAL { ?s dim:rsid ?rs }
            OPTIONAL { ?s met:rsid ?rs }
        }
        """
        matches = list(graph.query(find_q, initBindings={"cid": Literal(component_id)}))
        partners_q = prefix_header + """
        SELECT ?other ?otherLabel ?count WHERE {
            { ?node usage:dimension ?s ; usage:metric ?other ; usage:cooccurrenceCount ?count }
            UNION { ?node usage:metric ?s ; usage:dimension ?other ; usage:cooccurrenceCount ?count }
            UNION { ?node usage:dimension ?s ; usage:segment ?other ; usage:cooccurrenceCount ?count }
            UNION { ?node usage:segment ?s ; usage:dimension ?other ; usage:cooccurrenceCount ?count }
            OPTIONAL { ?other rdfs:label ?otherLabel }
        } ORDER BY DESC(?count) LIMIT 5
        """
        results = []
        for m in matches:
            partners = graph.query(partners_q, initBindings={"s": m.s})
            results.append({
                "id": component_id,
                "kind": str(m.kind),
                "name": str(m.label) if m.label else None,
                "description": str(m.comment) if m.comment else None,
                "rsid": _local_id(m.rs) if m.rs else None,
                "top_related": [
                    {"id": _local_id(p.other), "name": str(p.otherLabel) if p.otherLabel else None,
                     "count": int(p.count)} for p in partners
                ],
            })
        return {"matches": results}

    # sparql_query's docstring bakes in the resolved namespace IRIs for this company,
    # which the decorator would otherwise capture before company_id is known — so it
    # is registered by hand instead of via the @mcp.tool() decorator used above.
    def sparql_query(query: str) -> list:
        if kg_graph is None:
            raise ValueError("Knowledge Graph not connected. Restart the server with -kg <file.ttl>.")
        results = kg_graph.query(query)
        return [
            {str(v): (row[v].toPython() if row[v] is not None else None) for v in results.vars}
            for row in results
        ]

    sparql_query.__doc__ = f"""Execute a read-only SPARQL 1.1 SELECT query against the Knowledge Graph
        and return one dict per result row. Prefer the get_related_*/get_popular_combinations/
        get_component_context tools for common lookups; use this for anything more specific.

        Namespaces (company {company_id}):
          PREFIX rdfs:  <http://www.w3.org/2000/01/rdf-schema#>
          PREFIX dim:   <{ns['dim']}>
          PREFIX met:   <{ns['met']}>
          PREFIX seg:   <{ns['seg']}>
          PREFIX cm:    <{ns['cm']}>
          PREFIX usage: <{ns['usage']}>

        Entity IRIs:
          Dimension     : http://analytics.com/{company_id}/{{rsid}}/dimension/{{dimensionId}}
          Metric        : http://analytics.com/{company_id}/{{rsid}}/metric/{{metricId}}
          Segment       : http://analytics.com/{company_id}/segment/{{segmentId}}
          CalcMetric    : http://analytics.com/{company_id}/calculatedMetric/{{calcId}}
          Project       : http://analytics.com/{company_id}/projects/{{projectId}}
          ReportSuite   : http://analytics.com/{company_id}/reportSuite#{{rsid}}

        Key predicates:
          rdfs:label / rdfs:comment       -> display name / description
          dim:id / met:id / seg:id / cm:id -> the original component ID string
          dim:rsid / met:rsid              -> owning ReportSuite entity
          usage:usedWithMetric / usage:usedWithDimension / usage:usedWithSegment
                                            -> direct co-occurrence edges between two entities
          usage:dimension / usage:metric / usage:segment / usage:cooccurrenceCount / usage:rsid
                                            -> properties on a blank-node co-occurrence record
          usage:segmentUsage / usage:projectUsage / usage:metricUsage
                                            -> raw usage counters on a component
        """
    mcp.tool()(sparql_query)

    return mcp


def main():
    parser = argparse.ArgumentParser(
        prog="aanalytics2-mcp", description="MCP server for Adobe Analytics (aanalytics2)"
    )
    parser.add_argument("-cf", "--config_file", default="config_analytics.json", metavar="FILE",
                         help="Path to the JSON config file (default: config_analytics.json in cwd)")
    parser.add_argument("-cid", "--company_id", default=None, metavar="COMPANY_ID",
                         help="Adobe Analytics globalCompanyId (overrides config file)")
    parser.add_argument("-rsid", "--report_suite_id", default=None, metavar="RSID",
                         help="Default report suite ID used when a tool call omits rsid")
    parser.add_argument("-kg", "--knowledge_graph", default=None, metavar="FILE.ttl",
                         help="Path to a local Knowledge Graph .ttl file, enabling Group 4 KG tools")
    parser.add_argument("-kg-endpoint", "--kg_endpoint", default=None, metavar="URL",
                         help="Remote SPARQL endpoint URL (not yet implemented — Phase 3)")
    parser.add_argument("-kg-ontology", "--kg_ontology", default=None, metavar="FILE.md",
                         help="Path to a markdown file describing a custom Knowledge Graph ontology, "
                              "served to the LLM client via the 'ontology://knowledge-graph' resource. "
                              "Defaults to the ontology produced by KnowledgeGraph.buildGraph() (see "
                              "docs/knowledgegraph.md). Use this to document extra predicates/literals "
                              "added on top of that base schema.")
    args = parser.parse_args()

    if args.knowledge_graph and args.kg_endpoint:
        parser.error("-kg and -kg-endpoint are mutually exclusive.")
    if args.kg_endpoint:
        parser.error(
            "-kg-endpoint (remote SPARQL endpoint) is not implemented yet. Use -kg with a local .ttl file."
        )

    cfg = importConfigFile(args.config_file, return_object=True)
    login = Login(config=cfg)
    company_id = args.company_id or _company_id_from_config_file(args.config_file)
    if company_id is None:
        companies = login.getCompanyId()
        if not companies:
            print("No company IDs found for this config file.", file=sys.stderr)
            sys.exit(1)
        if len(companies) > 1:
            print(
                "Multiple companies available for this credential; no -cid was passed and no "
                "\"companyId\" was set in the config file, so defaulting to the first one below. "
                "This may not be the report suite scope you expect — pass -cid <globalCompanyId>, "
                "or add \"companyId\" to the config file, to pin one explicitly:",
                file=sys.stderr,
            )
            for c in companies:
                print(f"  {c.get('globalCompanyId')}  ({c.get('companyName')})", file=sys.stderr)
        company_id = companies[0]["globalCompanyId"]
    analytics = Analytics(company_id=company_id, config=cfg)

    kg_graph = None
    if args.knowledge_graph:
        print(f"Loading Knowledge Graph from {args.knowledge_graph} ...", file=sys.stderr)
        kg_graph = Graph()
        kg_graph.parse(args.knowledge_graph, format="turtle")
        print(f"Knowledge Graph loaded: {len(kg_graph)} triples.", file=sys.stderr)

    if args.kg_ontology:
        ontology_md = Path(args.kg_ontology).read_text(encoding="utf-8")
    else:
        ontology_md = _default_ontology_md()

    server = build_server(
        analytics=analytics,
        company_id=company_id,
        default_rsid=args.report_suite_id,
        kg_graph=kg_graph,
        ontology_md=ontology_md,
    )
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
