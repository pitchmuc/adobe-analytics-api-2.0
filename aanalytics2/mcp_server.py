"""
MCP server exposing Adobe Analytics (via aanalytics2) as tools for an LLM client.

See docs/mcp_plan.md for the design this implements. Covers Phase 1 + Phase 2:
Discovery, Reporting, Segment/CalculatedMetric/DateRange authoring, WorkspaceManager,
Classifications and Knowledge Graph (local .ttl only) tool groups. Remote SPARQL
endpoints (-kg-endpoint) and KG-enhanced suggestions are Phase 3 and not implemented
here.

Run directly with `python -m aanalytics2.mcp_server`, or via the `aanalytics2-mcp`
console script once installed.
"""
import argparse
from copy import deepcopy
import datetime
from decimal import Decimal
from importlib import resources as importlib_resources
import json
from pathlib import Path
import re
import sys
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, TypeVar, Union

from aanalytics2 import Analytics, Login
from aanalytics2.configs import importConfigFile, find_path
from aanalytics2.requestCreator import RequestCreator
from aanalytics2.workspaceManager import WorkspaceManager, FreeForm

try:
    from mcp.server.mcpserver import MCPServer
    from mcp.server.mcpserver.exceptions import ToolError
except ModuleNotFoundError as exc:
    if exc.name is None or exc.name.split(".")[0] != "mcp":
        raise
    raise ModuleNotFoundError(
        "The aanalytics2 MCP server needs the optional 'mcp' package. "
        "Install it with: pip install \"aanalytics2[mcp]\"",
        name=exc.name,
    ) from exc

if TYPE_CHECKING:
    from rdflib import Graph

_ApiResult = TypeVar("_ApiResult")


def _check_api_result(result: _ApiResult) -> _ApiResult:
    if isinstance(result, dict) and ("errorCode" in result or "error" in result):
        code = result.get("errorCode") or result.get("error")
        message = result.get("errorDescription") or result.get("message") or str(code)
        raise ToolError(f"Analytics API error {code}: {message}")
    return result


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


def _find_freeform_subpanel(wm: WorkspaceManager, table_title: str) -> tuple:
    # wm.panels re-parses a fresh, throwaway Panel/FreeForm tree on every access (see
    # WorkspaceManager.panels), so mutating it would never reach wm.to_dict(). The raw
    # sub-panel dicts in wm._panels are what to_dict() actually serialises, so a table
    # has to be located and patched there directly to make add_breakdown stick.
    available = []
    for panel in wm._panels:
        for sp in panel.get("subPanels", []):
            reportlet = sp.get("reportlet", {})
            if reportlet.get("type") == "FreeformReportlet":
                available.append(sp.get("name"))
                if sp.get("name") == table_title:
                    return panel, sp
    # ToolError (not ValueError) so MCPServer surfaces this message to the caller as
    # an anticipated tool failure instead of swallowing it into a generic
    # "Error executing tool" UnexpectedToolError.
    raise ToolError(
        f"No FreeForm table named {table_title!r} found in this project "
        f"(title match is case-sensitive and exact). Available FreeForm tables: {available!r}"
    )


# Accepted shape for a metric/dimension-item/segment/component reference: either a bare
# ID string or the full {"id": ..., "name"?: ..., "type"?: ...} dict. Declaring the Union
# (rather than bare `list`/`dict`) both documents the shorthand in the tool's JSON schema
# and — importantly — is required for it to work at all: MCPServer validates arguments
# against the annotation via pydantic before the tool body runs, so a plain `List[dict]`
# would reject a bare string with a validation error before _coerce_component_list ever saw it.
ComponentSpec = Union[str, dict]


def _dimension_key(dimension_id: str) -> str:
    """Normalize a dimension ID for comparison against the classification compatibility
    endpoint, which returns bare names (e.g. "evar5") regardless of whether the caller
    used the "variables/evar5" form used elsewhere in this server's tools."""
    return dimension_id.rsplit("/", 1)[-1].lower()


def _coerce_component_list(components: Optional[List[ComponentSpec]]) -> Optional[List[dict]]:
    """Turn any bare ID strings in `components` into {"id": ...} dicts. build_report_request
    already accepted bare metric ID strings for its own `metrics` list; without this, the
    same shorthand crashes the WorkspaceManager builder tools (add_freeform, add_breakdown,
    add_dropdown_filter, add_segment_comparison_table) with a raw `'str' object has no
    attribute 'get'` instead of resolving or failing clearly."""
    if not components:
        return components
    return [{"id": c} if isinstance(c, str) else c for c in components]


_SPARQL_UPDATE_KEYWORDS = frozenset(
    {"INSERT", "DELETE", "LOAD", "CLEAR", "DROP", "CREATE", "COPY", "MOVE", "ADD", "WITH"}
)


def _mask_sparql_literals_and_comments(query: str) -> str:
    """Replace comments with spaces and mask IRI/string contents with spaces while keeping
    delimiters and length intact, so prolog/keyword regexes never trip on `#` inside `<...#>`
    IRIs or keywords inside string literals."""
    out: List[str] = []
    i = 0
    n = len(query)
    while i < n:
        ch = query[i]
        if ch == "<":
            out.append("<")
            i += 1
            while i < n and query[i] != ">":
                out.append(" ")
                i += 1
            if i < n:
                out.append(">")
                i += 1
        elif query.startswith('"""', i) or query.startswith("'''", i):
            quote = query[i : i + 3]
            out.append(quote)
            i += 3
            while i < n and not query.startswith(quote, i):
                if query[i] == "\\" and i + 1 < n:
                    out.append("  ")
                    i += 2
                else:
                    out.append("\n" if query[i] == "\n" else " ")
                    i += 1
            if i < n:
                out.append(quote)
                i += 3
        elif ch in ('"', "'"):
            quote = ch
            out.append(quote)
            i += 1
            while i < n and query[i] != quote:
                if query[i] == "\\" and i + 1 < n:
                    out.append("  ")
                    i += 2
                else:
                    out.append("\n" if query[i] == "\n" else " ")
                    i += 1
            if i < n:
                out.append(quote)
                i += 1
        elif ch == "#":
            while i < n and query[i] != "\n":
                out.append(" ")
                i += 1
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def _prepare_sparql_query(query: str, namespaces: Dict[str, str]) -> str:
    """Validate that `query` is a non-empty, read-only SPARQL query and auto-inject any
    standard ontology PREFIX declarations not already declared by the caller."""
    if not isinstance(query, str) or not query.strip():
        raise ToolError("SPARQL query must not be empty.")
    masked = _mask_sparql_literals_and_comments(query)
    if not masked.strip():
        raise ToolError("SPARQL query contains only comments/whitespace.")

    prolog_re = re.compile(
        r"^\s*(?:(?:BASE\s*<[^>]*>|PREFIX\s+[A-Za-z_][\w.-]*\s*:\s*<[^>]*>|PREFIX\s*:\s*<[^>]*>)\s*)*",
        re.IGNORECASE,
    )
    prolog_match = prolog_re.match(masked)
    body_start = prolog_match.end() if prolog_match else 0
    first_word_match = re.match(r"([A-Za-z_]\w*)", masked[body_start:])
    if first_word_match:
        keyword = first_word_match.group(1).upper()
        if keyword in _SPARQL_UPDATE_KEYWORDS:
            raise ToolError(
                f"sparql_query is read-only; SPARQL Update operation {keyword!r} is not allowed."
            )

    declared = {
        m.group(1)
        for m in re.finditer(r"(?i)\bPREFIX\s+([A-Za-z_][\w.-]*)\s*:\s*<[^>]*>", masked)
    }
    missing_prefixes = "".join(
        f"PREFIX {prefix}: <{uri}>\n"
        for prefix, uri in namespaces.items()
        if prefix not in declared
    )
    if not missing_prefixes:
        return query

    base_match = re.match(r"^\s*BASE\s*<[^>]*>\s*", masked, re.IGNORECASE)
    if base_match:
        insert_at = base_match.end()
        return query[:insert_at] + "\n" + missing_prefixes + query[insert_at:]
    return missing_prefixes + query


def _rdf_term_to_json(term: Any) -> Any:
    """Convert an rdflib Node (URIRef, Literal, BNode) or None into a JSON-safe scalar."""
    if term is None:
        return None
    term_cls = type(term).__name__
    if term_cls == "BNode":
        return f"_:{term}"
    if term_cls == "URIRef":
        return str(term)
    if hasattr(term, "toPython"):
        value = term.toPython()
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
            return value.isoformat()
        return str(value)
    return str(term)


def _normalize_report_request_key(request: dict) -> str:
    """Canonical JSON cache key for a report request dict, ignoring transient pagination
    fields (`page`/`limit`) so row-count slicing can decide cache reuse separately."""
    cleaned = deepcopy(request)
    settings = cleaned.get("settings")
    if isinstance(settings, dict):
        settings.pop("page", None)
        settings.pop("limit", None)
    return json.dumps(cleaned, sort_keys=True, default=str)


def _workspace_cache_key(project: dict) -> Optional[str]:
    """Stable identifier for a Workspace project dict: real top-level `id` when present,
    otherwise the internal workspace UUID under `definition.workspaces[0].id`."""
    if not isinstance(project, dict):
        return None
    if project.get("id"):
        return str(project["id"])
    workspaces = (project.get("definition") or {}).get("workspaces") or []
    if workspaces and isinstance(workspaces[0], dict) and workspaces[0].get("id"):
        return str(workspaces[0]["id"])
    return None


def build_server(
    analytics: Analytics,
    company_id: str,
    default_rsid: Optional[str] = None,
    kg_graph: Optional["Graph"] = None,
    ontology_md: Optional[str] = None,
) -> MCPServer:
    kg_instructions = (
        " A Knowledge Graph is connected: read the 'ontology://knowledge-graph' resource "
        "before calling sparql_query or the get_related_*/get_popular_combinations/"
        "get_component_context tools."
        if kg_graph is not None
        else ""
    )
    mcp = MCPServer(
        "aanalytics2",
        instructions=(
            "Adobe Analytics tools (Discovery, Reporting with cached report reuse & breakdowns, "
            "Segment/CalculatedMetric/DateRange authoring, cached Workspace building, and "
            "Classifications)."
            + kg_instructions
            + " For a single segment or calculated metric lookup by name, prefer "
            "find_segment/find_calculated_metric over list_segments/list_calculated_metrics. "
            "Report results from run_report/breakdown_report return a `report_id` that can be "
            "reused across multiple breakdown_report calls (with different dimensions or rows) "
            "without rebuilding or re-executing the original report. Workspace builder tools "
            "cache the active WorkspaceManager instance, so `project` can be omitted on "
            "chained add_* / publish_workspace / update_workspace calls."
        ),
    )

    ns: Dict[str, str] = {}
    prefix_header = ""
    if kg_graph is not None:
        from rdflib import Literal, URIRef

        if ontology_md is None:
            ontology_md = _default_ontology_md()
        ns = {
            "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
            "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
            "xsd": "http://www.w3.org/2001/XMLSchema#",
            "rs": f"http://analytics.com/{company_id}/reportSuite#",
            "dim": f"http://analytics.com/{company_id}/dimension#",
            "met": f"http://analytics.com/{company_id}/metric#",
            "mc": f"http://analytics.com/{company_id}/marketingChannel#",
            "seg": f"http://analytics.com/{company_id}/segment#",
            "cm": f"http://analytics.com/{company_id}/calculatedMetric#",
            "dr": f"http://analytics.com/{company_id}/dateRange#",
            "proj": f"http://analytics.com/{company_id}/projects#",
            "usage": f"http://analytics.com/{company_id}/usage#",
        }
        prefix_header = (
            f"PREFIX rdfs: <{ns['rdfs']}>\n"
            f"PREFIX dim: <{ns['dim']}>\n"
            f"PREFIX met: <{ns['met']}>\n"
            f"PREFIX seg: <{ns['seg']}>\n"
            f"PREFIX cm: <{ns['cm']}>\n"
            f"PREFIX usage: <{ns['usage']}>\n"
        )

        def _dim_uri(rsid: str, dimension_id: str):
            return URIRef(f"http://analytics.com/{company_id}/{rsid}/dimension/{dimension_id}")

        def _met_uri(rsid: str, metric_id: str):
            return URIRef(f"http://analytics.com/{company_id}/{rsid}/metric/{metric_id}")

        def _rsid_uri(rsid: str):
            return URIRef(f"http://analytics.com/{company_id}/reportSuite#{rsid}")

    def _require_rsid(rsid: Optional[str]) -> str:
        rsid = rsid or default_rsid
        if not rsid:
            raise ToolError("rsid is required (no default report suite was configured with -rsid).")
        return rsid

    def _local_id(uri) -> str:
        value = str(uri)
        for kind in ("dimension", "metric", "segment", "calculatedMetric"):
            marker = f"/{kind}/"
            if marker in value:
                return value.split(marker, 1)[1]
        return value.rsplit("/", 1)[-1]

    def _rsid_from_uri(uri) -> str:
        # rsid nodes are fragment-based (.../reportSuite#{rsid}), not path-based like
        # dimension/metric/segment/calculatedMetric nodes, so _local_id's "/" split
        # would return "reportSuite#{rsid}" instead of the bare rsid.
        return str(uri).rsplit("#", 1)[-1]

    def _apply_filter(records: list, filter: Optional[str], key: str = "name") -> list:
        if not filter:
            return records
        needle = filter.lower()
        return [r for r in records if needle in str(r.get(key, "")).lower()]

    # ── Session caches for Reports & WorkspaceManager ────────────────────
    _report_seq = 0
    _report_cache: Dict[str, dict] = {}
    _request_key_to_report_id: Dict[str, str] = {}
    _breakdown_key_to_report_id: Dict[Tuple[str, str, str], str] = {}
    _last_built_request: Optional[dict] = None

    _wm_rsid_context_cache: Dict[str, Tuple[dict, str, tuple]] = {}
    _workspace_cache: Dict[str, Tuple[WorkspaceManager, dict]] = {}
    _fetched_projects_raw: Dict[str, dict] = {}
    _active_workspace_key: Optional[str] = None

    def _next_report_id() -> str:
        nonlocal _report_seq
        _report_seq += 1
        return f"report_{_report_seq}"

    def _format_report_response(
        workspace: Any,
        n_results: int,
        report_id: str,
        cached: bool,
        parent_report_id: Optional[str] = None,
        breakdown_filter: Optional[str] = None,
        breakdown_value: Optional[str] = None,
    ) -> dict:
        df = workspace.dataframe
        row_count = getattr(workspace, "row_numbers", len(df))
        columns = list(getattr(workspace, "columns", df.columns))
        payload = {
            "report_id": report_id,
            "cached": cached,
            "rows": _df_to_records(df)[:n_results],
            "row_count": row_count,
            "columns": columns,
        }
        if parent_report_id is not None:
            payload["parent_report_id"] = parent_report_id
        if breakdown_filter is not None:
            payload["breakdown_filter"] = breakdown_filter
        if breakdown_value is not None:
            payload["breakdown_value"] = breakdown_value
        return payload

    def _build_or_hydrate_wm(
        *,
        data: Optional[dict] = None,
        rsid: Optional[str] = None,
        name: Optional[str] = None,
        description: str = "",
    ) -> WorkspaceManager:
        target_rsid = rsid or (data.get("rsid", "") if isinstance(data, dict) else "")
        cached_ctx = _wm_rsid_context_cache.get(target_rsid) if target_rsid else None
        if cached_ctx is not None:
            owner_info, rsid_name, lookups = cached_ctx
            wm = WorkspaceManager(
                data=data,
                rsid=rsid,
                name=name,
                description=description,
                analytics=analytics,
                component_lookups=lookups,
                owner_info=owner_info,
                rsid_name=rsid_name,
            )
        else:
            wm = WorkspaceManager(
                data=data,
                rsid=rsid,
                name=name,
                description=description,
                analytics=analytics,
            )
            if wm.rsid:
                _wm_rsid_context_cache[wm.rsid] = (
                    dict(wm.owner) if wm.owner else {"id": None, "name": "", "login": ""},
                    wm.rsid_name,
                    (
                        wm._segments_id_name,
                        wm._dim_id_name,
                        wm._metric_id_name,
                        wm._calc_metric_id_name,
                        wm._date_ranges_id_name,
                    ),
                )
        return wm

    def _save_workspace(wm: WorkspaceManager) -> dict:
        nonlocal _active_workspace_key
        snapshot = wm.to_dict()
        key = _workspace_cache_key(snapshot) or wm.id
        stored_snapshot = deepcopy(snapshot)
        _workspace_cache[key] = (wm, stored_snapshot)
        if wm.id and wm.id != key:
            _workspace_cache[wm.id] = (wm, stored_snapshot)
        _active_workspace_key = key
        return snapshot

    def _resolve_workspace(project: Optional[Union[dict, str]]) -> WorkspaceManager:
        nonlocal _active_workspace_key
        if project is None:
            if _active_workspace_key and _active_workspace_key in _workspace_cache:
                return _workspace_cache[_active_workspace_key][0]
            raise ToolError(
                "No active cached Workspace project in this session. Pass `project` "
                "(a project dict or cached workspace ID) or call create_workspace / get_project first."
            )
        if isinstance(project, str):
            if project in _workspace_cache:
                _active_workspace_key = project
                return _workspace_cache[project][0]
            if project in _fetched_projects_raw:
                wm = _build_or_hydrate_wm(data=_fetched_projects_raw[project])
                _save_workspace(wm)
                return wm
            raise ToolError(
                f"Unknown workspace ID {project!r}. Available cached workspaces: "
                f"{sorted(set(_workspace_cache) | set(_fetched_projects_raw))!r}"
            )
        if isinstance(project, dict):
            key = _workspace_cache_key(project)
            if key and key in _workspace_cache:
                cached_wm, cached_snapshot = _workspace_cache[key]
                if project == cached_snapshot:
                    _active_workspace_key = key
                    return cached_wm
            wm = _build_or_hydrate_wm(data=project)
            _save_workspace(wm)
            return wm
        raise ToolError(f"Unsupported project argument type: {type(project).__name__}.")

    # ── Group 1 — Discovery ──────────────────────────────────────────────

    @mcp.tool()
    def list_report_suites(filter: Optional[str] = None) -> list:
        """List report suites available to this connection. Optional case-insensitive
        substring `filter` on the report suite name."""
        df = _check_api_result(analytics.getReportSuites(extended_info=True))
        return _apply_filter(_df_to_records(df), filter)

    @mcp.tool()
    def list_dimensions(rsid: Optional[str] = None, filter: Optional[str] = None) -> list:
        """List dimensions available in a report suite (id, name, type, description).
        Optional case-insensitive substring `filter` on the dimension name."""
        rsid = _require_rsid(rsid)
        records = _check_api_result(analytics.getDimensions(rsid=rsid, description=True, format="raw"))
        return _apply_filter(records, filter)

    @mcp.tool()
    def list_metrics(rsid: Optional[str] = None, filter: Optional[str] = None) -> list:
        """List metrics available in a report suite (id, name, type, description).
        Optional case-insensitive substring `filter` on the metric name."""
        rsid = _require_rsid(rsid)
        records = _check_api_result(analytics.getMetrics(rsid=rsid, description=True, format="raw"))
        return _apply_filter(records, filter)

    @mcp.tool()
    def list_segments(rsid: Optional[str] = None, filter: Optional[str] = None) -> list:
        """List segments (id, name, description). Scoped to `rsid` if provided,
        otherwise all segments visible to this connection. Optional case-insensitive
        substring `filter` on the segment name. This always hits the live API and
        returns everything that matches, which can be very large on accounts with
        thousands of segments -- for a single lookup by name, prefer find_segment,
        which checks the local Knowledge Graph first and is much cheaper."""
        records = _check_api_result(analytics.getSegments(
            rsids_list=[rsid] if rsid else None, extended_info=True, format="raw"
        ))
        return _apply_filter(records, filter)

    @mcp.tool()
    def find_segment(
        name: Optional[str] = None, rsid: Optional[str] = None, limit: int = 20, force_live: bool = False
    ) -> dict:
        """Look up segments by case-insensitive substring on `name` and/or `rsid`.
        Prefers the local Knowledge Graph (-kg) over a live list_segments call, which
        is far cheaper on accounts with thousands of segments. Falls back to a live
        API call -- and always says so via the result's "source"/"note" fields, so
        you know when an answer is NOT based on the Knowledge Graph -- when: no
        Knowledge Graph is connected; the Knowledge Graph has no match (it can be
        stale for segments created/renamed since it was last built); or `force_live`
        is explicitly set to True. Result shape: {"source": "knowledge_graph" |
        "live_api", "note": str | None, "results": [...]}. `note` is only set when
        `source` is "live_api". Call list_segments directly if you need the full,
        unfiltered, always-live list instead of a targeted lookup."""
        if not force_live and kg_graph is not None:
            q = prefix_header + """
            SELECT ?id ?label ?comment ?rsUri WHERE {
                ?s seg:id ?id ; rdfs:label ?label .
                OPTIONAL { ?s rdfs:comment ?comment }
                OPTIONAL { ?s seg:rsid ?rsUri }
            }
            """
            records = []
            for r in kg_graph.query(q):
                row_rsid = _rsid_from_uri(r.rsUri) if r.rsUri else None
                if rsid and row_rsid != rsid:
                    continue
                if name and name.lower() not in str(r.label).lower():
                    continue
                records.append({
                    "id": str(r.id), "name": str(r.label),
                    "description": str(r.comment) if r.comment else None,
                    "rsid": row_rsid,
                })
            if records:
                return {"source": "knowledge_graph", "note": None, "results": records[:limit]}
            note = (
                "No matching segment found in the Knowledge Graph"
                + (f" for rsid={rsid!r}" if rsid else "")
                + (f", name filter {name!r}" if name else "")
                + " -- falling back to a live list_segments API call. This is NOT a "
                  "Knowledge Graph answer; it can also find segments created or "
                  "renamed since the Knowledge Graph was last built."
            )
        elif force_live:
            note = ("force_live=True was passed -- this is NOT a Knowledge Graph answer; "
                     "results come directly from a live list_segments API call.")
        else:
            note = ("No Knowledge Graph connected (server not started with -kg) -- this is "
                     "NOT a Knowledge Graph answer; results come from a live list_segments API call.")
        records = _check_api_result(analytics.getSegments(
            name=name, rsids_list=[rsid] if rsid else None, extended_info=True, format="raw"
        ))
        return {"source": "live_api", "note": note, "results": records[:limit]}

    @mcp.tool()
    def list_calculated_metrics(filter: Optional[str] = None) -> list:
        """List calculated metrics (id, name, description). Optional case-insensitive
        substring `filter` on the name. This always hits the live API and returns
        everything that matches, which can be very large -- for a single lookup by
        name, prefer find_calculated_metric, which checks the local Knowledge Graph
        first and is much cheaper."""
        records = _check_api_result(analytics.getCalculatedMetrics(extended_info=True, format="raw"))
        return _apply_filter(records, filter)

    @mcp.tool()
    def find_calculated_metric(
        name: Optional[str] = None, rsid: Optional[str] = None, limit: int = 20, force_live: bool = False
    ) -> dict:
        """Look up calculated metrics by case-insensitive substring on `name` and/or
        `rsid`. Prefers the local Knowledge Graph (-kg) over a live
        list_calculated_metrics call, which is far cheaper on accounts with thousands
        of calculated metrics. Falls back to a live API call -- and always says so via
        the result's "source"/"note" fields, so you know when an answer is NOT based
        on the Knowledge Graph -- when: no Knowledge Graph is connected; the Knowledge
        Graph has no match (it can be stale for calculated metrics created/renamed
        since it was last built); or `force_live` is explicitly set to True. Result
        shape: {"source": "knowledge_graph" | "live_api", "note": str | None,
        "results": [...]}. `note` is only set when `source` is "live_api". Call
        list_calculated_metrics directly if you need the full, unfiltered, always-live
        list instead of a targeted lookup."""
        if not force_live and kg_graph is not None:
            q = prefix_header + """
            SELECT ?id ?label ?comment ?rsUri WHERE {
                ?s cm:id ?id ; rdfs:label ?label .
                OPTIONAL { ?s rdfs:comment ?comment }
                OPTIONAL { ?s cm:rsid ?rsUri }
            }
            """
            records = []
            for r in kg_graph.query(q):
                row_rsid = _rsid_from_uri(r.rsUri) if r.rsUri else None
                if rsid and row_rsid != rsid:
                    continue
                if name and name.lower() not in str(r.label).lower():
                    continue
                records.append({
                    "id": str(r.id), "name": str(r.label),
                    "description": str(r.comment) if r.comment else None,
                    "rsid": row_rsid,
                })
            if records:
                return {"source": "knowledge_graph", "note": None, "results": records[:limit]}
            note = (
                "No matching calculated metric found in the Knowledge Graph"
                + (f" for rsid={rsid!r}" if rsid else "")
                + (f", name filter {name!r}" if name else "")
                + " -- falling back to a live list_calculated_metrics API call. This is "
                  "NOT a Knowledge Graph answer; it can also find calculated metrics "
                  "created or renamed since the Knowledge Graph was last built."
            )
        elif force_live:
            note = ("force_live=True was passed -- this is NOT a Knowledge Graph answer; "
                     "results come directly from a live list_calculated_metrics API call.")
        else:
            note = ("No Knowledge Graph connected (server not started with -kg) -- this is "
                     "NOT a Knowledge Graph answer; results come from a live "
                     "list_calculated_metrics API call.")
        records = _check_api_result(analytics.getCalculatedMetrics(
            name=name, rsids_list=[rsid] if rsid else None, extended_info=True, format="raw"
        ))
        return {"source": "live_api", "note": note, "results": records[:limit]}

    @mcp.tool()
    def list_date_ranges(filter: Optional[str] = None) -> list:
        """List saved date ranges (id, name). Optional case-insensitive substring
        `filter` on the name."""
        records = _check_api_result(analytics.getDateRanges(extended_info=True, format="raw"))
        return _apply_filter(records, filter)

    @mcp.tool()
    def list_projects(filter: Optional[str] = None) -> list:
        """List Workspace projects (id, name, rsid, owner). Optional case-insensitive
        substring `filter` on the project name."""
        records = _check_api_result(analytics.getProjects(format="raw"))
        return _apply_filter(records, filter)

    @mcp.tool()
    def get_segment(segment_id: str) -> dict:
        """Return the full definition of a single segment by ID."""
        return _check_api_result(analytics.getSegment(segment_id, full=True))

    @mcp.tool()
    def get_project(project_id: str) -> dict:
        """Return the full definition of a single Workspace project by ID. Also caches
        the fetched definition in memory under `project_id`, so subsequent Workspace
        builder calls (`add_panel`, `add_freeform`, ..., `update_workspace`) can pass
        `project=project_id` instead of resending the full JSON dict."""
        result = _check_api_result(analytics.getProject(projectId=project_id))
        if isinstance(result, dict):
            _fetched_projects_raw[project_id] = deepcopy(result)
        return result

    # ── Group 2 — Reporting (with response caching & reusable breakdowns) ──

    @mcp.tool()
    def build_report_request(
        dimension_id: str,
        metrics: List[ComponentSpec],
        date_range: str,
        rsid: Optional[str] = None,
        segment_ids: Optional[List[str]] = None,
        limit: int = 100,
    ) -> dict:
        """Build a report request dict (compatible with run_report) from high-level
        parameters. Does not call the API — inspect or hand-edit the returned dict
        before passing it to run_report (or call run_report() with `request` omitted
        to run the most recently built request directly).

        Arguments:
            dimension_id : Dimension ID, e.g. "variables/eVar1".
            metrics      : List of {"id": "metrics/visits", ...} dicts or bare ID strings.
            date_range   : ISO 8601 interval ("2024-01-01/2024-03-31") or a preset name
                           ("thisMonth", "untilToday", "todayIncluded", "last30daysTillToday",
                           "last30daysTodayIncluded", "last7daysTillToday", "last7daysTodayIncluded").
            rsid         : Report suite ID. Falls back to the server's default -rsid if omitted.
            segment_ids  : Optional list of segment IDs added as global filters.
            limit        : Row limit (default 100).
        """
        nonlocal _last_built_request
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
        built = rc.to_dict()
        _last_built_request = deepcopy(built)
        return built

    @mcp.tool()
    def run_report(
        request: Optional[Union[dict, str]] = None,
        n_results: int = 50,
        force_refresh: bool = False,
    ) -> dict:
        """Run a report request and return the top rows along with a `report_id` handle.
        The underlying `Workspace` response is cached in memory so you can run multiple
        `breakdown_report` calls against that `report_id` (using different dimensions or
        rows) without rebuilding or re-running the original request.

        `request` accepts:
          - a request dict (from `build_report_request` or hand-built),
          - a cached `report_id` string (e.g. "report_1") to re-read/re-slice a cached report,
          - `None` to run the most recently created `build_report_request`.
        Set `force_refresh=True` to bypass the cache and re-query the Analytics API."""
        if n_results <= 0:
            raise ToolError("n_results must be a positive integer.")

        if isinstance(request, str):
            entry = _report_cache.get(request)
            if entry is None:
                raise ToolError(
                    f"Unknown report_id {request!r}. Available cached reports: {sorted(_report_cache)!r}"
                )
            if not force_refresh and (n_results <= entry["fetched_limit"] or not entry["request"]):
                return _format_report_response(
                    entry["workspace"],
                    n_results=n_results,
                    report_id=entry["report_id"],
                    cached=True,
                    parent_report_id=entry.get("parent_report_id"),
                    breakdown_filter=entry.get("breakdown_filter"),
                    breakdown_value=entry.get("breakdown_value"),
                )
            req_dict = deepcopy(entry["request"])
            report_id = entry["report_id"]
        else:
            if request is None:
                if _last_built_request is None:
                    raise ToolError(
                        "request is required (no prior build_report_request was created in this session)."
                    )
                req_dict = deepcopy(_last_built_request)
            elif isinstance(request, dict):
                req_dict = deepcopy(request)
            else:
                raise ToolError(f"Unsupported request type: {type(request).__name__}.")

            req_key = _normalize_report_request_key(req_dict)
            existing_id = _request_key_to_report_id.get(req_key)
            if existing_id and not force_refresh:
                existing_entry = _report_cache[existing_id]
                if n_results <= existing_entry["fetched_limit"]:
                    return _format_report_response(
                        existing_entry["workspace"],
                        n_results=n_results,
                        report_id=existing_id,
                        cached=True,
                    )
            report_id = existing_id or _next_report_id()

        # getReport2's own `limit` kwarg (default 20000) overwrites request["settings"]["limit"]
        # otherwise, fetching far more than n_results asked for.
        try:
            workspace = _check_api_result(
                analytics.getReport2(request=req_dict, n_results=n_results, limit=n_results)
            )
        except (RuntimeError, ValueError) as exc:
            raise ToolError(str(exc)) from exc

        if not hasattr(workspace, "dataframe"):
            return {"raw": workspace}

        req_key = _normalize_report_request_key(req_dict)
        prior_entry = _report_cache.get(report_id) or {}
        _report_cache[report_id] = {
            "report_id": report_id,
            "workspace": workspace,
            "request": deepcopy(req_dict),
            "fetched_limit": n_results,
            "parent_report_id": prior_entry.get("parent_report_id"),
            "breakdown_filter": prior_entry.get("breakdown_filter"),
            "breakdown_value": prior_entry.get("breakdown_value"),
        }
        _request_key_to_report_id[req_key] = report_id
        return _format_report_response(
            workspace,
            n_results=n_results,
            report_id=report_id,
            cached=False,
            parent_report_id=prior_entry.get("parent_report_id"),
            breakdown_filter=prior_entry.get("breakdown_filter"),
            breakdown_value=prior_entry.get("breakdown_value"),
        )

    @mcp.tool()
    def breakdown_report(
        report_id: str,
        dimension_id: str,
        row: Union[int, str] = 0,
        n_results: int = 10,
        force_refresh: bool = False,
    ) -> dict:
        """Break down a specific row of a cached report (`report_id` from `run_report` or
        an earlier `breakdown_report`) by another dimension (`dimension_id`).

        Does NOT mutate or consume the original cached report: you can call
        `breakdown_report` repeatedly on the same `report_id` with different dimensions
        or different rows without rebuilding or re-running the base report. The breakdown
        result is itself cached under a new `report_id`, enabling multi-level drill-downs.

        Arguments:
            report_id     : Cached report ID returned by `run_report` or `breakdown_report`.
            dimension_id  : Dimension ID to break down by, e.g. "variables/browser".
            row           : Target row in `report_id` — 0-based integer row index, exact
                            dimension display value, or `itemId` string (default 0).
            n_results     : Maximum breakdown rows to return (default 10).
            force_refresh : Set True to bypass any cached breakdown for the same arguments.
        """
        if n_results <= 0:
            raise ToolError("n_results must be a positive integer.")
        parent_entry = _report_cache.get(report_id)
        if parent_entry is None:
            raise ToolError(
                f"Unknown report_id {report_id!r}. Available cached reports: {sorted(_report_cache)!r}"
            )
        parent_ws = parent_entry["workspace"]
        df = getattr(parent_ws, "dataframe", None)
        if df is None or df.empty or len(df.columns) < 2 or "itemId" not in df.columns:
            raise ToolError(
                f"Cached report {report_id!r} has no dimension rows with itemIds to break down."
            )

        parent_req = parent_entry.get("request") or (
            parent_ws.dataRequest.to_dict()
            if hasattr(parent_ws, "dataRequest") and hasattr(parent_ws.dataRequest, "to_dict")
            else {}
        )
        parent_dim = str(parent_req.get("dimension") or df.columns[1])
        if isinstance(row, str):
            matched = df[df.iloc[:, 1] == row]
            if matched.empty:
                matched = df[df["itemId"].astype(str) == row]
            if matched.empty:
                raise ToolError(
                    f"Row value or itemId {row!r} not found in cached report {report_id!r} "
                    f"(dimension {parent_dim!r})."
                )
            item_id = str(matched["itemId"].iloc[0])
            item_label = str(matched.iloc[0, 1])
        elif isinstance(row, int) and not isinstance(row, bool):
            if row < 0 or row >= len(df):
                raise ToolError(
                    f"Row index {row} out of range for cached report {report_id!r} "
                    f"(has {len(df)} rows)."
                )
            item_id = str(df.iloc[row]["itemId"])
            item_label = str(df.iloc[row, 1])
        else:
            raise ToolError("row must be a 0-based row index integer or a dimension value/itemId string.")

        breakdown_filter = f"{parent_dim}:::{item_id}"
        bd_key = (report_id, item_id, dimension_id)
        existing_bd_id = _breakdown_key_to_report_id.get(bd_key)
        if existing_bd_id and not force_refresh:
            existing_bd = _report_cache[existing_bd_id]
            if n_results <= existing_bd["fetched_limit"]:
                return _format_report_response(
                    existing_bd["workspace"],
                    n_results=n_results,
                    report_id=existing_bd_id,
                    cached=True,
                    parent_report_id=report_id,
                    breakdown_filter=breakdown_filter,
                    breakdown_value=item_label,
                )

        try:
            if hasattr(parent_ws, "breakdown"):
                child_ws = _check_api_result(
                    parent_ws.breakdown(index=row, dimension=dimension_id, n_results=n_results)
                )
                child_req = (
                    child_ws.dataRequest.to_dict()
                    if hasattr(child_ws, "dataRequest") and hasattr(child_ws.dataRequest, "to_dict")
                    else {}
                )
            else:
                base_req = deepcopy(parent_entry.get("request") or {})
                rc = RequestCreator(base_req or None)
                if base_req.get("rsid") or default_rsid:
                    rc.setRSID(base_req.get("rsid") or default_rsid)
                rc.setDimension(dimension_id)
                rc.addMetricFilter(metricId="all", filterId=breakdown_filter)
                rc.setLimit(n_results)
                child_req = rc.to_dict()
                child_ws = _check_api_result(
                    analytics.getReport2(request=child_req, n_results=n_results, limit=n_results)
                )
        except (RuntimeError, ValueError) as exc:
            raise ToolError(str(exc)) from exc

        if not hasattr(child_ws, "dataframe"):
            return {"raw": child_ws}

        child_id = existing_bd_id or _next_report_id()
        _report_cache[child_id] = {
            "report_id": child_id,
            "workspace": child_ws,
            "request": deepcopy(child_req),
            "fetched_limit": n_results,
            "parent_report_id": report_id,
            "breakdown_filter": breakdown_filter,
            "breakdown_value": item_label,
        }
        _breakdown_key_to_report_id[bd_key] = child_id
        return _format_report_response(
            child_ws,
            n_results=n_results,
            report_id=child_id,
            cached=False,
            parent_report_id=report_id,
            breakdown_filter=breakdown_filter,
            breakdown_value=item_label,
        )

    @mcp.tool()
    def list_cached_reports() -> list:
        """List metadata for all cached report responses in this session (`report_id`,
        `dimension`, `metrics`, `rsid`, `row_count`, `parent_report_id`, `breakdown_filter`),
        ready to be passed to `breakdown_report` or `run_report(request=report_id)`."""
        summaries = []
        for rid, entry in _report_cache.items():
            req = entry.get("request") or {}
            ws = entry["workspace"]
            df = getattr(ws, "dataframe", None)
            dimension = req.get("dimension") or (
                str(df.columns[1]) if df is not None and len(df.columns) > 1 else None
            )
            metrics = [
                m.get("id")
                for m in (req.get("metricContainer") or {}).get("metrics", [])
                if isinstance(m, dict) and m.get("id")
            ]
            summaries.append({
                "report_id": rid,
                "rsid": req.get("rsid"),
                "dimension": dimension,
                "metrics": metrics,
                "row_count": getattr(ws, "row_numbers", len(df) if df is not None else 0),
                "fetched_limit": entry["fetched_limit"],
                "parent_report_id": entry.get("parent_report_id"),
                "breakdown_filter": entry.get("breakdown_filter"),
                "breakdown_value": entry.get("breakdown_value"),
            })
        return summaries

    @mcp.tool()
    def get_top_items(
        dimension_id: str,
        rsid: Optional[str] = None,
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
        # getReport2's own `limit` kwarg (default 20000) overwrites request["settings"]["limit"]
        # set above otherwise, fetching (and, since never truncated below, returning) far more
        # rows than the caller's `limit` asked for.
        workspace = _check_api_result(analytics.getReport2(request=rc.to_dict(), n_results=limit, limit=limit))
        if not hasattr(workspace, "dataframe"):
            return []
        records = _df_to_records(workspace.dataframe)[:limit]
        return [{"value": r.get(dimension_id), "itemId": r.get("itemId")} for r in records]

    # ── Group 3 — Segment / Calculated Metric / Date Range authoring ───────
    # No builder class exists for these (unlike RequestCreator/WorkspaceManager for
    # reports/workspaces), so the tools take/return the same raw dict shape as the
    # underlying API. get_segment/list_calculated_metrics/list_date_ranges already
    # return full metadata (including "definition") for existing components in this
    # account — use one as a starting shape, cheaper and more reliable for an LLM to
    # adapt than to construct from scratch. Full definition syntax:
    # https://developer.adobe.com/analytics-apis/docs/2.0/guides/endpoints/segments/definition/
    # https://developer.adobe.com/analytics-apis/docs/2.0/guides/endpoints/calculatedmetrics/

    @mcp.tool()
    def validate_segment(segment: dict) -> dict:
        """Dry-run a segment definition against the API without saving it. `segment`
        needs "name" and "definition" (a rule container — see get_segment on an
        existing segment for the shape) and "rsid". Returns the API's validation
        result, including any definition errors — check this before create_segment."""
        return _check_api_result(analytics.createSegmentValidate(segmentJSON=segment))

    def _record_component_in_wm_caches(bucket_index: int, result: Any, fallback_name: Optional[str] = None) -> None:
        """Keep cached WorkspaceManager lookup tables fresh when segments, calculated
        metrics, or date ranges are created/updated mid-session."""
        if not isinstance(result, dict):
            return
        comp_id = result.get("id")
        comp_name = result.get("name") or fallback_name
        if not comp_id or not comp_name:
            return
        for _, _, lookups in _wm_rsid_context_cache.values():
            lookups[bucket_index][comp_id] = comp_name

    @mcp.tool()
    def create_segment(segment: dict) -> dict:
        """Create a new segment. `segment` needs "name" and "definition" (a rule
        container — see get_segment on an existing segment for the shape) and "rsid".
        Consider calling validate_segment first to catch definition errors before
        saving."""
        res = _check_api_result(analytics.createSegment(segmentJSON=segment))
        _record_component_in_wm_caches(0, res, segment.get("name"))
        return res

    @mcp.tool()
    def update_segment(segment_id: str, segment: dict) -> dict:
        """Update an existing segment in place. `segment_id` is the segment to
        overwrite; `segment` is the full replacement definition — start from
        get_segment(segment_id) and edit that dict rather than building one from
        scratch, since this replaces the whole definition, not just the fields you
        set. Consider calling validate_segment first to catch definition errors
        before saving."""
        res = _check_api_result(analytics.updateSegment(segmentID=segment_id, segmentJSON=segment))
        _record_component_in_wm_caches(0, res, segment.get("name"))
        return res

    @mcp.tool()
    def validate_calculated_metric(calculated_metric: dict) -> dict:
        """Dry-run a calculated metric definition against the API without saving it.
        `calculated_metric` needs "name", "definition" and "rsid" — see
        list_calculated_metrics on an existing one for the "definition" shape.
        Returns the API's validation result, including any definition errors —
        check this before create_calculated_metric."""
        return _check_api_result(analytics.createCalculatedMetricValidate(metricJSON=calculated_metric))

    @mcp.tool()
    def create_calculated_metric(calculated_metric: dict) -> dict:
        """Create a new calculated metric. `calculated_metric` needs "name",
        "definition" and "rsid" — see list_calculated_metrics on an existing one for
        the "definition" shape. Consider calling validate_calculated_metric first to
        catch definition errors before saving."""
        res = _check_api_result(analytics.createCalculatedMetric(metricJSON=calculated_metric))
        _record_component_in_wm_caches(3, res, calculated_metric.get("name"))
        return res

    @mcp.tool()
    def update_calculated_metric(calculated_metric_id: str, calculated_metric: dict) -> dict:
        """Update an existing calculated metric in place. `calculated_metric_id` is
        the metric to overwrite; `calculated_metric` is the full replacement
        definition — start from an entry in list_calculated_metrics and edit that
        dict rather than building one from scratch, since this replaces the whole
        definition, not just the fields you set. Consider calling
        validate_calculated_metric first to catch definition errors before saving."""
        res = _check_api_result(analytics.updateCalculatedMetric(calcID=calculated_metric_id, calcJSON=calculated_metric))
        _record_component_in_wm_caches(3, res, calculated_metric.get("name"))
        return res

    @mcp.tool()
    def create_date_range(date_range: dict) -> dict:
        """Create a new saved date range. `date_range` needs "name" and "definition"
        — see list_date_ranges on an existing one for the exact shape used by this
        account. There is no validate endpoint for date ranges; this saves directly."""
        res = _check_api_result(analytics.createDateRange(dateRangeJSON=date_range))
        _record_component_in_wm_caches(4, res, date_range.get("name"))
        return res

    @mcp.tool()
    def update_date_range(date_range_id: str, date_range: dict) -> dict:
        """Update an existing saved date range in place. `date_range_id` is the date
        range to overwrite; `date_range` is the full replacement definition — start
        from an entry in list_date_ranges and edit that dict rather than building one
        from scratch, since this replaces the whole definition, not just the fields
        you set. There is no validate endpoint for date ranges; this saves directly."""
        res = _check_api_result(analytics.updateDateRange(dateRangeID=date_range_id, dateRangeJSON=date_range))
        _record_component_in_wm_caches(4, res, date_range.get("name"))
        return res

    # ── Group 4 — WorkspaceManager (single cached instance + optional project dict/ID) ──

    @mcp.tool()
    def create_workspace(rsid: str, name: str, description: str = "") -> dict:
        """Start a new Workspace project definition and cache the `WorkspaceManager`
        instance in memory as the active workspace. Subsequent `add_*` and
        `publish_workspace` calls can omit `project` (or pass the workspace ID /
        returned project dict) to mutate the cached instance without re-fetching
        company lookup tables."""
        wm = _build_or_hydrate_wm(rsid=rsid, name=name, description=description)
        return _save_workspace(wm)

    @mcp.tool()
    def add_panel(
        name: str,
        project: Optional[Union[dict, str]] = None,
        date_range: str = "thisMonth",
        description: str = "",
    ) -> dict:
        """Add a new panel to the project (defaults to the active cached workspace when
        `project` is omitted). Subsequent add_* calls target this panel."""
        wm = _resolve_workspace(project)
        wm.addPanel(name=name, date_range=date_range, description=description)
        return _save_workspace(wm)

    @mcp.tool()
    def add_segment_filter(segment: str, project: Optional[Union[dict, str]] = None) -> dict:
        """Add a global segment filter (ID or name) to the current panel (defaults to
        the active cached workspace when `project` is omitted)."""
        wm = _resolve_workspace(project)
        wm.addSegmentFilter(segment=segment)
        return _save_workspace(wm)

    @mcp.tool()
    def add_dropdown_filter(
        group_name: str,
        components: List[ComponentSpec],
        project: Optional[Union[dict, str]] = None,
        has_no_filter: bool = True,
    ) -> dict:
        """Add a dropdown filter group to the current panel (defaults to the active
        cached workspace when `project` is omitted). Each item in `components` needs
        "id"/"name" (or is a bare ID string — the name is then auto-resolved), optional
        "type" ("Segment" default, or "DimensionItem") and "isActive"."""
        wm = _resolve_workspace(project)
        wm.addDropdownFilter(group_name=group_name, components=_coerce_component_list(components), has_no_filter=has_no_filter)
        return _save_workspace(wm)

    @mcp.tool()
    def add_text(title: str, content: str, project: Optional[Union[dict, str]] = None) -> dict:
        """Add a free-text panel element (defaults to the active cached workspace when
        `project` is omitted)."""
        wm = _resolve_workspace(project)
        wm.addTextFreeform(title=title, content=content)
        return _save_workspace(wm)

    @mcp.tool()
    def add_freeform(
        title: str,
        metrics: List[ComponentSpec],
        project: Optional[Union[dict, str]] = None,
        item_id: Optional[str] = None,
        item_name: str = "",
        items: Optional[List[ComponentSpec]] = None,
        rows: int = 10,
    ) -> dict:
        """Add a freeform table to the current panel (defaults to the active cached
        workspace when `project` is omitted). Provide either a single dynamic row
        dimension (`item_id` + optional `item_name`) or static rows (`items`, a list
        of {"id", "name", "type"?} dicts — "type" is "Segment" or "DimensionItem").
        `metrics` is a list of {"id", "name"} dicts; each may include a "filters" list
        for column-level splitting. Both `metrics` and `items` also accept bare ID
        strings instead of dicts (e.g. "metrics/visits") — the display name is then
        auto-resolved from the report suite."""
        wm = _resolve_workspace(project)
        wm.addFreeform(title=title, item_id=item_id, item_name=item_name,
                        items=_coerce_component_list(items),
                        metrics=_coerce_component_list(metrics), rows=rows)
        return _save_workspace(wm)

    @mcp.tool()
    def add_breakdown(
        table_title: str,
        project: Optional[Union[dict, str]] = None,
        dimension_id: Optional[str] = None,
        dimension_name: Optional[str] = None,
        items: Optional[List[ComponentSpec]] = None,
        rows: int = 5,
    ) -> dict:
        """Nest a breakdown under an existing freeform table (matched by its title,
        case-sensitive and exact; defaults to the active cached workspace when `project`
        is omitted). Provide either `dimension_id` (+ optional `dimension_name`) for a
        dynamic breakdown, or `items` (list of {"id", "name", "type"?} dicts, or bare ID
        strings — the display name is then auto-resolved) for static rows.

        When the table's own rows come from a dynamic dimension (not static `items`),
        Adobe only shows a row as expandable if the breakdown is anchored to that row's
        real `itemId` — a placeholder does not work. This is looked up automatically
        with a live report request against the table's row dimension (same rsid/date
        range/row count as the table), one breakdown entry per currently-visible row."""
        wm = _resolve_workspace(project)
        panel, subpanel = _find_freeform_subpanel(wm, table_title)
        ff = FreeForm.from_dict(subpanel["reportlet"])
        # Unlike WorkspaceManager.addFreeform, FreeForm.addBreakdown does not resolve
        # missing id/name pairs itself — reuse wm's already-loaded company lookup
        # tables so a dimension_id/dimension_name pair or an items entry with only
        # "id" (or only "name") still resolves, same as it would if passed to
        # add_freeform instead.
        if dimension_id or dimension_name:
            dimension_id, dimension_name = wm._resolve_dim_pair(dimension_id or "", dimension_name or "")
        normalized_items = wm._normalize_items(_coerce_component_list(items)) if items else None
        if ff.dimension is not None:
            date_range_obj = panel.get("dateRange", {}) or {}
            date_range = date_range_obj.get("id") or (date_range_obj.get("__metaData__") or {}).get("definition")
            if not date_range:
                raise ToolError(
                    f"Could not determine the date range of panel {panel.get('name')!r} to look "
                    "up real row itemIds for this breakdown."
                )
            metric_id = "metrics/visits"
            if ff.metrics:
                metric_id = ff.metrics[0]["id"]
            elif ff.calculatedMetrics:
                metric_id = ff.calculatedMetrics[0]["id"]
            page_size = ((subpanel["reportlet"].get("freeformTable") or {}).get("pagination") or {}).get("viewBy", 10)
            rc = RequestCreator()
            rc.setRSID(wm.rsid)
            rc.setDimension(ff.dimension["id"])
            rc.addMetric(metric_id)
            rc.setDateRange(dateRange=_resolve_date_range(rc, date_range))
            rc.setLimit(page_size)
            # getReport2's own `limit` kwarg (default 20000) overwrites the request's own
            # settings.limit set by rc.setLimit() above — pass it explicitly, or this fetches
            # (and embeds itemIds for) every row of the dimension instead of just page_size,
            # which blew a two-table test project up to 36MB and failed on Adobe's 16MB cap.
            report = _check_api_result(analytics.getReport2(request=rc.to_dict(), n_results=page_size, limit=page_size))
            item_ids = []
            if hasattr(report, "dataframe") and "itemId" in report.dataframe.columns:
                item_ids = [str(v) for v in report.dataframe["itemId"].tolist()][:page_size]
            if not item_ids:
                raise ToolError(
                    f"Could not fetch real row itemIds for dimension {ff.dimension['id']!r} "
                    f"(rsid={wm.rsid!r}, date_range={date_range!r}) — Workspace would "
                    "not show this breakdown as expandable without them."
                )
            for item_id in item_ids:
                ff.addBreakdown(dimension_id=dimension_id, dimension_name=dimension_name,
                                 items=normalized_items, rows=rows, parent_item_id=item_id)
        else:
            ff.addBreakdown(dimension_id=dimension_id, dimension_name=dimension_name,
                             items=normalized_items, rows=rows)
        subpanel["reportlet"] = ff.to_dict()
        return _save_workspace(wm)

    @mcp.tool()
    def add_chart(
        viz_type: str,
        project: Optional[Union[dict, str]] = None,
        source: Optional[Union[str, int]] = None,
        title: str = "",
    ) -> dict:
        """Add a chart visualization linked to a freeform table in the current panel
        (defaults to the active cached workspace when `project` is omitted).
        `viz_type`: line, bar, bar_horizontal, bar_stacked, area, area_stacked, donut,
        scatter, treemap, histogram, bullet, venn. `source` (table name or index)
        defaults to the most recently added freeform table."""
        wm = _resolve_workspace(project)
        wm.addChart(viz_type=viz_type, source=source, title=title)
        return _save_workspace(wm)

    @mcp.tool()
    def add_segment_comparison_table(
        title: str,
        segments: List[ComponentSpec],
        metrics: List[ComponentSpec],
        project: Optional[Union[dict, str]] = None,
        breakdown_dim_id: Optional[str] = None,
        breakdown_dim_name: str = "",
        breakdown_segments: Optional[List[ComponentSpec]] = None,
        rows: int = 50,
        breakdown_rows: int = 5,
    ) -> dict:
        """Add a freeform table where each row is a segment (side-by-side segment
        comparison), optionally broken down further by a dimension or nested segments
        (defaults to the active cached workspace when `project` is omitted).
        `segments`, `metrics` and `breakdown_segments` each accept {"id", "name"} dicts
        or bare ID strings — the display name is then auto-resolved."""
        wm = _resolve_workspace(project)
        wm.addSegmentAsDimensionFreeform(
            title=title, segments=_coerce_component_list(segments), metrics=_coerce_component_list(metrics),
            breakdown_dim_id=breakdown_dim_id, breakdown_dim_name=breakdown_dim_name,
            breakdown_segments=_coerce_component_list(breakdown_segments), breakdown_rows=breakdown_rows, rows=rows,
        )
        return _save_workspace(wm)

    @mcp.tool()
    def publish_workspace(project: Optional[Union[dict, str]] = None) -> dict:
        """Save a project (defaults to the active cached workspace when `project` is
        omitted) as a new Workspace project via the Analytics API."""
        cached_wm: Optional[WorkspaceManager] = None
        if isinstance(project, dict):
            payload = project
            key = _workspace_cache_key(project)
            if key and key in _workspace_cache and project == _workspace_cache[key][1]:
                cached_wm = _workspace_cache[key][0]
        else:
            cached_wm = _resolve_workspace(project)
            payload = cached_wm.to_dict()
        result = _check_api_result(analytics.createProject(payload))
        if cached_wm is not None and isinstance(result, dict) and result.get("id"):
            cached_wm.id = result["id"]
            cached_wm._has_real_id = True
            _save_workspace(cached_wm)
        return result

    @mcp.tool()
    def update_workspace(project: Optional[Union[dict, str]] = None) -> dict:
        """Save changes to an EXISTING Workspace project (matched by its "id"; defaults
        to the active cached workspace when `project` is omitted). Use this instead of
        publish_workspace when `project` originated from get_project — possibly then
        modified via add_panel/add_freeform/add_chart/etc. — rather than from
        create_workspace; publish_workspace would create a duplicate instead of updating
        the original."""
        if isinstance(project, dict):
            payload = project
        else:
            wm = _resolve_workspace(project)
            payload = wm.to_dict()
        project_id = payload.get("id")
        if not project_id:
            raise ToolError(
                "project has no \"id\" — it must come from get_project (a project created "
                "with create_workspace has no id until it is first published). Use "
                "publish_workspace to create a new project instead."
            )
        return _check_api_result(analytics.updateProject(project_id, payload))

    # ── Group 5 — Classifications ────────────────────────────────────────

    @mcp.tool()
    def list_classification_datasets(rsid: Optional[str] = None) -> list:
        """List classification dataset associations for a report suite: one entry per
        dimension that has at least one classification dataset attached, each with the
        linked dataset ID(s). Use get_classification_dataset_id to look up a single
        dimension, or get_classification_dataset for a dataset's full metadata."""
        rsid = _require_rsid(rsid)
        data = _check_api_result(analytics.getClassificationDatasets(rsid=rsid))
        return [
            {"dimension_id": dim_id, "dataset_ids": entry.get("datasets", [])}
            for entry in data.get("metrics", [])
            for dim_id in entry.get("id", [])
        ]

    @mcp.tool()
    def get_classification_dataset_id(dimension_id: str, rsid: Optional[str] = None) -> list:
        """Return the classification dataset ID(s) linked to a dimension in a report
        suite (dimension_id accepts either "evar5" or "variables/evar5"). Empty list if
        that dimension has no classification dataset attached."""
        rsid = _require_rsid(rsid)
        data = _check_api_result(analytics.getClassificationDatasets(rsid=rsid))
        target = _dimension_key(dimension_id)
        dataset_ids: list = []
        for entry in data.get("metrics", []):
            if target in (_dimension_key(i) for i in entry.get("id", [])):
                dataset_ids.extend(entry.get("datasets", []))
        return dataset_ids

    @mcp.tool()
    def get_classification_dataset(dataset_id: str) -> dict:
        """Return the full metadata (name, description, columns, report suite
        subscriptions) for a single classification dataset by ID."""
        return _check_api_result(analytics.getClassificationDataset(datasetId=dataset_id))

    # ── Group 6 — Knowledge Graph (registered only when a .ttl graph is connected) ──

    if kg_graph is not None:

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
        def get_related_metrics(
            dimension_id: str, rsid: Optional[str] = None, limit: int = 10
        ) -> list:
            """Metrics most frequently used with this dimension across loaded projects,
            ordered by co-occurrence count."""
            rsid = _require_rsid(rsid)
            q = prefix_header + f"""
            SELECT ?metric ?label ?count WHERE {{
                ?node usage:dimension ?dim ; usage:metric ?metric ; usage:cooccurrenceCount ?count .
                OPTIONAL {{ ?metric rdfs:label ?label }}
            }} ORDER BY DESC(?count) LIMIT {int(limit)}
            """
            rows = kg_graph.query(q, initBindings={"dim": _dim_uri(rsid, dimension_id)})
            return [{"metric_id": _local_id(r.metric), "name": str(r.label) if r.label else None,
                     "count": int(r["count"])} for r in rows]

        @mcp.tool()
        def get_related_dimensions(
            metric_id: str, rsid: Optional[str] = None, limit: int = 10
        ) -> list:
            """Dimensions most frequently used with this metric across loaded projects,
            ordered by co-occurrence count."""
            rsid = _require_rsid(rsid)
            q = prefix_header + f"""
            SELECT ?dimension ?label ?count WHERE {{
                ?node usage:metric ?met ; usage:dimension ?dimension ; usage:cooccurrenceCount ?count .
                OPTIONAL {{ ?dimension rdfs:label ?label }}
            }} ORDER BY DESC(?count) LIMIT {int(limit)}
            """
            rows = kg_graph.query(q, initBindings={"met": _met_uri(rsid, metric_id)})
            return [{"dimension_id": _local_id(r.dimension), "name": str(r.label) if r.label else None,
                     "count": int(r["count"])} for r in rows]

        @mcp.tool()
        def get_related_segments(
            dimension_id: Optional[str] = None, rsid: Optional[str] = None, limit: int = 10
        ) -> list:
            """Segments most commonly applied alongside this dimension across loaded
            projects. Only dimension-based lookup is supported today — the Knowledge Graph
            does not track a direct metric<->segment co-occurrence."""
            if not dimension_id:
                return []
            rsid = _require_rsid(rsid)
            q = prefix_header + f"""
            SELECT ?segment ?label ?count WHERE {{
                ?node usage:dimension ?dim ; usage:segment ?segment ; usage:cooccurrenceCount ?count .
                OPTIONAL {{ ?segment rdfs:label ?label }}
            }} ORDER BY DESC(?count) LIMIT {int(limit)}
            """
            rows = kg_graph.query(q, initBindings={"dim": _dim_uri(rsid, dimension_id)})
            return [{"segment_id": _local_id(r.segment), "name": str(r.label) if r.label else None,
                     "count": int(r["count"])} for r in rows]

        @mcp.tool()
        def get_popular_combinations(rsid: Optional[str] = None, limit: int = 10) -> list:
            """Top dimension+metric pairs by co-occurrence count in this report suite."""
            rsid = _require_rsid(rsid)
            q = prefix_header + f"""
            SELECT ?dim ?dimLabel ?metric ?metLabel ?count WHERE {{
                ?node usage:dimension ?dim ; usage:metric ?metric ; usage:cooccurrenceCount ?count ; usage:rsid ?rs .
                OPTIONAL {{ ?dim rdfs:label ?dimLabel }}
                OPTIONAL {{ ?metric rdfs:label ?metLabel }}
            }} ORDER BY DESC(?count) LIMIT {int(limit)}
            """
            rows = kg_graph.query(q, initBindings={"rs": _rsid_uri(rsid)})
            return [{"dimension_id": _local_id(r.dim), "dimension_name": str(r.dimLabel) if r.dimLabel else None,
                     "metric_id": _local_id(r.metric), "metric_name": str(r.metLabel) if r.metLabel else None,
                     "count": int(r["count"])} for r in rows]

        @mcp.tool()
        def get_component_context(component_id: str) -> dict:
            """All Knowledge Graph facts about a single component (dimension, metric,
            segment or calculated metric), looked up by its raw ID: name, description,
            which report suite(s) it belongs to, usage counters, and its top co-occurring
            partners. Returns one entry per matching component (an ID can match more than
            one entity if it is reused across report suites)."""
            find_q = prefix_header + """
            SELECT ?s ?kind ?label ?comment ?rs WHERE {
                { ?s dim:id ?cid . BIND("dimension" AS ?kind) }
                UNION { ?s met:id ?cid . BIND("metric" AS ?kind) }
                UNION { ?s seg:id ?cid . BIND("segment" AS ?kind) }
                UNION { ?s cm:id ?cid . BIND("calculatedMetric" AS ?kind) }
                OPTIONAL { ?s rdfs:label ?label }
                OPTIONAL { ?s rdfs:comment ?comment }
                OPTIONAL {
                    VALUES ?rsPredicate { dim:rsid met:rsid seg:rsid cm:rsid }
                    ?s ?rsPredicate ?rs
                }
            }
            """
            matches = list(kg_graph.query(find_q, initBindings={"cid": Literal(component_id)}))
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
                partners = kg_graph.query(partners_q, initBindings={"s": m.s})
                results.append({
                    "id": component_id,
                    "kind": str(m.kind),
                    "name": str(m.label) if m.label else None,
                    "description": str(m.comment) if m.comment else None,
                    "rsid": _rsid_from_uri(m.rs) if m.rs else None,
                    "top_related": [
                        {"id": _local_id(p.other), "name": str(p.otherLabel) if p.otherLabel else None,
                         "count": int(p["count"])} for p in partners
                    ],
                })
            return {"matches": results}

        # sparql_query's docstring bakes in the resolved namespace IRIs for this company,
        # which the decorator would otherwise capture before company_id is known — so it
        # is registered by hand instead of via the @mcp.tool() decorator used above.
        def sparql_query(query: str, limit: int = 200) -> dict:
            if limit <= 0:
                raise ToolError("limit must be a positive integer.")
            prepared_query = _prepare_sparql_query(query, ns)
            try:
                results = kg_graph.query(prepared_query)
            except Exception as exc:
                raise ToolError(
                    f"Invalid SPARQL query: {exc}. Standard prefixes "
                    f"({', '.join(sorted(ns))}) are injected automatically when omitted."
                ) from exc

            query_type = getattr(results, "type", "SELECT") or "SELECT"
            if query_type == "ASK":
                return {"query_type": "ASK", "boolean": bool(results.askAnswer)}
            if query_type in ("CONSTRUCT", "DESCRIBE"):
                all_triples = list(results)
                truncated = len(all_triples) > limit
                triples = [
                    {
                        "subject": _rdf_term_to_json(s),
                        "predicate": _rdf_term_to_json(p),
                        "object": _rdf_term_to_json(o),
                    }
                    for s, p, o in all_triples[:limit]
                ]
                return {
                    "query_type": query_type,
                    "triples": triples,
                    "triple_count": len(triples),
                    "total_triples": len(all_triples),
                    "truncated": truncated,
                }
            variables = [str(v) for v in (results.vars or [])]
            all_rows = list(results)
            truncated = len(all_rows) > limit
            rows = [
                {var: _rdf_term_to_json(row[var]) for var in variables}
                for row in all_rows[:limit]
            ]
            return {
                "query_type": "SELECT",
                "variables": variables,
                "rows": rows,
                "row_count": len(rows),
                "total_rows": len(all_rows),
                "truncated": truncated,
            }

        sparql_query.__doc__ = f"""Execute a read-only SPARQL 1.1 query (`SELECT`, `ASK`, `CONSTRUCT`, or
            `DESCRIBE`) against the Knowledge Graph. Standard ontology prefixes below are
            injected automatically if omitted from `query`. `limit` (default 200) caps
            returned rows/triples and sets `truncated=True` when more results matched.
            Prefer `get_related_*` / `get_popular_combinations` / `get_component_context`
            for common lookups; use this for custom graph queries.

            Auto-injected namespaces (company {company_id}):
              PREFIX rdf:   <{ns['rdf']}>
              PREFIX rdfs:  <{ns['rdfs']}>
              PREFIX xsd:   <{ns['xsd']}>
              PREFIX rs:    <{ns['rs']}>
              PREFIX dim:   <{ns['dim']}>
              PREFIX met:   <{ns['met']}>
              PREFIX mc:    <{ns['mc']}>
              PREFIX seg:   <{ns['seg']}>
              PREFIX cm:    <{ns['cm']}>
              PREFIX dr:    <{ns['dr']}>
              PREFIX proj:  <{ns['proj']}>
              PREFIX usage: <{ns['usage']}>

            Entity IRIs:
              Dimension     : http://analytics.com/{company_id}/{{rsid}}/dimension/{{dimensionId}}
              Metric        : http://analytics.com/{company_id}/{{rsid}}/metric/{{metricId}}
              Segment       : http://analytics.com/{company_id}/segment/{{segmentId}}
              CalcMetric    : http://analytics.com/{company_id}/calculatedMetric/{{calcId}}
              DateRange     : http://analytics.com/{company_id}/dateRange/{{dateRangeId}}
              Project       : http://analytics.com/{company_id}/projects/{{projectId}}
              ReportSuite   : http://analytics.com/{company_id}/reportSuite#{{rsid}}

            Key predicates:
              rdfs:label / rdfs:comment       -> display name / description
              dim:id / met:id / seg:id / cm:id -> the original component ID string
              dim:rsid / met:rsid / seg:rsid / cm:rsid -> owning ReportSuite entity
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
                         help="Path to a local Knowledge Graph .ttl file, enabling Group 4 KG tools. "
                              "If missing, warn and continue without a Knowledge Graph.")
    parser.add_argument("-kg-endpoint", "--kg_endpoint", default=None, metavar="URL",
                         help="Remote SPARQL endpoint URL (not yet implemented — Phase 3)")
    parser.add_argument("-kg-ontology", "--kg_ontology", default=None, metavar="FILE.md",
                         help="Path to a markdown file describing a custom Knowledge Graph ontology, "
                              "served to the LLM client via the 'ontology://knowledge-graph' resource. "
                              "Defaults to the ontology produced by KnowledgeGraph.buildGraph() (see "
                              "docs/knowledgegraph.md). Use this to document extra predicates/literals "
                              "added on top of that base schema.")
    parser.add_argument("--legacy-stdio", action="store_true",
                        help="Use a compatibility bridge for clients whose discovery probe "
                             "prevents fallback to the legacy initialize handshake. Keeps SDK 2.x.")
    args = parser.parse_args()

    if args.knowledge_graph and args.kg_endpoint:
        parser.error("-kg and -kg-endpoint are mutually exclusive.")
    if args.kg_endpoint:
        parser.error(
            "-kg-endpoint (remote SPARQL endpoint) is not implemented yet. Use -kg with a local .ttl file."
        )

    if args.legacy_stdio:
        from aanalytics2.mcp_compat import relay_legacy_stdio

        child_args = ["-cf", args.config_file]
        for flag, value in (
            ("-cid", args.company_id),
            ("-rsid", args.report_suite_id),
            ("-kg", args.knowledge_graph),
            ("-kg-ontology", args.kg_ontology),
        ):
            if value is not None:
                child_args.extend([flag, value])
        sys.exit(relay_legacy_stdio(
            [sys.executable, "-u", "-m", "aanalytics2.mcp_server", *child_args],
            sys.stdin.buffer,
            sys.stdout.buffer,
        ))

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
        from rdflib import Graph

        print(f"Loading Knowledge Graph from {args.knowledge_graph} ...", file=sys.stderr)
        kg_graph = Graph()
        try:
            with Path(args.knowledge_graph).open("rb") as source:
                kg_graph.parse(
                    source=source,
                    publicID=Path(args.knowledge_graph).resolve().as_uri(),
                    format="turtle",
                )
        except FileNotFoundError:
            print(
                f"Warning: Knowledge Graph file not found: {args.knowledge_graph}. "
                "Continuing without a Knowledge Graph.",
                file=sys.stderr,
            )
            kg_graph = None
        else:
            print(f"Knowledge Graph loaded: {len(kg_graph)} triples.", file=sys.stderr)

    ontology_md = None
    if kg_graph is not None:
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
