import json
import uuid
from copy import deepcopy
from typing import Union, List, Dict, Optional
import httpx, asyncio
from concurrent import futures

# ── Module-level constants ───────────────────────────────────────────────────

_SWATCH_COLORS = [
    "#26C0C7", "#5151D3", "#E68619", "#D83790", "#908DFA", "#58E06F",
    "#2780EB", "#6F38B1", "#DFBF03", "#CB6F10", "#268D6C", "#9BEC54",
]

# Maps user-facing shorthand to the Workspace reportlet type string.
_VIZ_TYPE_MAP: Dict[str, str] = {
    "line":           "LineReportlet",
    "bar":            "BarReportlet",
    "bar_horizontal": "HorizontalBarReportlet",
    "bar_stacked":    "BarStackReportlet",
    "area":           "AreaReportlet",
    "area_stacked":   "AreaStackReportlet",
    "donut":          "DonutReportlet",
    "scatter":        "ScatterReportlet",
    "treemap":        "TreemapReportlet",
    "histogram":      "HistogramReportlet",
    "bullet":         "BulletReportlet",
    "venn":           "VennReportlet",
}

# Reportlet types whose content is plain/rich text rather than tabular or chart data.
_TEXT_REPORTLET_TYPES = ("TextReportlet", "SectionHeaderReportlet")

# The four categories a parsed Panel can report via its `.type` attribute.
_TYPE_SUBPANEL = "SubPanel"
_TYPE_FREEFORM = "FreeForm"
_TYPE_TEXT = "Text"
_TYPE_VISUALIZATION = "Visualization"


# ── Module-level helpers (stateless — safe to call without an instance) ──────

def _upper_uuid() -> str:
    return str(uuid.uuid4()).upper()


def _lower_uuid() -> str:
    return str(uuid.uuid4())


def _short_hex_id() -> str:
    return uuid.uuid4().hex[:6]


def _detect_component_type(item_id: str) -> str:
    """Infer component type from an ID string.

    * ``variables/...::hash`` → ``"DimensionItem"``
    * ``variables/...`` (no ``"::"``) → ``"Dimension"``
    * anything else → ``"Segment"``
    """
    if "::" in item_id:
        return "DimensionItem"
    if item_id.startswith("variables/"):
        return "Dimension"
    return "Segment"


def _default_table_cell_display() -> dict:
    return {
        "conditionalFormattingOpts": {
            "autoGenerate": True,
            "colorPalette": "#ffa48c,#ffcb94,#fff19b,#cadf7d,#95cc5f",
            "usePercentLimits": False,
        },
        "location": "behindNumber",
        "type": {
            "background": True,
            "backgroundType": "bar",
            "comparison": "none",
            "interpretZeroAsNoValue": False,
            "number": True,
            "percent": True,
            "showAnomaly": False,
            "showForecasting": False,
            "showGrandTotal": True,
            "showSparklines": True,
            "showTotals": True,
            "wrapHeaderText": True,
        },
    }


def _default_data_settings() -> dict:
    return {
        "advancedItemLimit": 5,
        "advancedItemSearch": {
            "alwaysExcludedItems": [],
            "operator": "AND",
            "rules": [],
        },
    }


def _default_search() -> dict:
    return {"alwaysExcludedItems": [], "operator": "AND", "rules": []}


def _intelligent_captions() -> dict:
    return {"captions": [], "hasLoaded": False, "hiddenCaptions": [], "isExpanded": False}


def _make_static_row(item_id: str, item_name: str, item_type: str = None) -> tuple:
    """Build a static row dict for any component type, returning ``(row_dict, row_id)``.

    *item_type* defaults to auto-detection via :func:`_detect_component_type`.
    Arguments:
        item_id   : REQUIRED : The component ID, e.g. ``"s1234_abc"``, ``"variables/evar8::581609802"``, or ``"variables/targetraw.activity"``.
        item_name : REQUIRED : The human-readable name for the component.
        item_type : OPTIONAL : The component type, e.g. ``"Segment"``, ``"Dimension"``, or ``"DimensionItem"``.  When not supplied, the type is inferred from the ID string.
    """
    comp_type = item_type or _detect_component_type(item_id)
    row_id = f"{_short_hex_id()}-{_short_hex_id()[:3]}"
    return {
        "component": {
            "id": item_id,
            "__entity__": True,
            "type": comp_type,
            "__metaData__": {"name": item_name},
        },
        "dataSettings": _default_data_settings(),
        "id": row_id,
    }, row_id


def _chart_reportlet(reportlet_type: str, title: str) -> dict:
    return {
        "hideTitle": False,
        "name": title,
        "showAnnotations": True,
        "showControls": True,
        "type": reportlet_type,
    }


def _text_reportlet(title: str, text_content: str) -> dict:
    return {
        "disabled": False,
        "hideTitle": False,
        "intelligentCaptions": _intelligent_captions(),
        "isConfigVisible": True,
        "name": title,
        "readOnly": False,
        "showAnnotations": True,
        "showControls": True,
        "showVizSelectorOnSubPanel": False,
        "textContent": text_content,
        "type": "TextReportlet",
        "useRowBasedPercentages": False,
    }


def _summary_number_reportlet(title: str, column_id: str, row_position: int = -1) -> dict:
    """Build a SummaryNumberReportlet linked to *column_id* in a backing FreeformReportlet.

    The ``column_id`` must match the ``id`` field of the metric node inside the
    backing table's ``columnTree``.  Row position ``-1`` selects the grand-total row.
    """
    return {
        "abbreviatePrecision": 0,
        "abbreviateValue": False,
        "isConfigVisible": True,
        "legendVisible": False,
        "lockedSelection": {
            "breakdowns": [],
            "selectedDataPoints": [{"columnId": column_id, "rowPosition": row_position}],
            "type": "FreeformBreakdownSelection",
        },
        "lockType": "positions",
        "name": title,
        "showVizSelectorOnSubPanel": False,
        "sourceCoords": "",
        "summarizeValue": False,
        "summarizeValueBy": "max",
        "type": "SummaryNumberReportlet",
        "usePercentage": False,
        "useRowBasedPercentages": False,
    }


def _sub_panel(
    name: str,
    reportlet: dict,
    y_position: int = 0,
    auto_height: int = 400,
    swatch_color: str = "#26C0C7",
    viz_index: int = 1,
    collapsed: bool = False,
    description: str = "",
) -> dict:
    return {
        "collapsed": collapsed,
        "description": description,
        "id": _upper_uuid(),
        "isQuickInsightsSubPanel": False,
        "linkedSourceId": "",
        "name": name,
        "position": {
            "autoHeight": auto_height,
            "autoSize": True,
            "width": 100,
            "x": 0,
            "y": y_position,
        },
        "reportlet": reportlet,
        "swatchColor": swatch_color,
        "type": "genericSubPanel",
        "visible": True,
        "visualizationIndex": viz_index,
    }


def _next_swatch(panel: dict) -> str:
    if panel.get("_opaque"):
        raise ValueError(
            "The current panel has an unrecognised structure and cannot be modified. "
            "Call addPanel() to create a new panel first."
        )
    return _SWATCH_COLORS[len(panel["subPanels"]) % len(_SWATCH_COLORS)]


def _append_subpanel(panel: dict, name: str, reportlet: dict, auto_height: int,
                      collapsed: bool = False, description: str = "") -> dict:
    """Wrap *reportlet* in a new sub-panel, append it to *panel*, and return the sub-panel dict."""
    sub = _sub_panel(
        name=name,
        reportlet=reportlet,
        y_position=panel["_yOffset"],
        auto_height=auto_height,
        swatch_color=_next_swatch(panel),
        viz_index=panel["_vizIndex"],
        collapsed=collapsed,
        description=description,
    )
    panel["subPanels"].append(sub)
    panel["_yOffset"] += auto_height
    panel["_vizIndex"] += 1
    return sub


# ── Public classes ─────────────────────────────────────────────────────────────

class TextBuilder:
    """
    Helper to build rich-text content in Quill Delta format for TextReportlets.

    Usage::

        tb = (
            TextBuilder()
            .addTitle("My Title")
            .addText("\\nSome plain text.\\n")
            .addBold("Important")
            .addNewline()
            .addColor("danger", "var(--spectrum-red-800)")
            .addNewline()
        )
        creator.addTextFreeform("My Panel", tb)
    """

    def __init__(self):
        self._ops: list = []

    # ── Builder methods ────────────────────────────────────────────────────

    def addTitle(self, text: str, level: int = 2) -> "TextBuilder":
        """
        Add a heading line.
        Arguments:
            text  : REQUIRED : Heading text.
            level : OPTIONAL : Heading level (1-6, default 2).
        """
        self._ops.append({"insert": text})
        self._ops.append({"attributes": {"header": level}, "insert": "\n"})
        return self

    def addText(self, text: str) -> "TextBuilder":
        """Add plain text."""
        self._ops.append({"insert": text})
        return self

    def addBold(self, text: str) -> "TextBuilder":
        """Add bold text."""
        self._ops.append({"attributes": {"bold": True}, "insert": text})
        return self

    def addItalic(self, text: str) -> "TextBuilder":
        """Add italic text."""
        self._ops.append({"attributes": {"italic": True}, "insert": text})
        return self

    def addUnderline(self, text: str) -> "TextBuilder":
        """Add underlined text."""
        self._ops.append({"attributes": {"underline": True}, "insert": text})
        return self

    def addColor(self, text: str, color: str) -> "TextBuilder":
        """
        Add colored text.
        Arguments:
            text  : REQUIRED : Text to colorize.
            color : REQUIRED : CSS color or variable, e.g. 'var(--spectrum-red-800)',
                    'var(--spectrum-celery-500)', 'var(--spectrum-blue-800)', or any hex/named color.
        """
        self._ops.append({"attributes": {"color": color}, "insert": text})
        return self

    def addLink(self, text: str, url: str) -> "TextBuilder":
        """
        Add a hyperlink.
        Arguments:
            text : REQUIRED : Display text.
            url  : REQUIRED : URL the link points to.
        """
        self._ops.append({"attributes": {"link": url}, "insert": text})
        return self

    def addNewline(self) -> "TextBuilder":
        """Add a newline character."""
        self._ops.append({"insert": "\n"})
        return self

    # ── Serialisation ──────────────────────────────────────────────────────

    def to_json(self) -> str:
        """Return Quill Delta JSON string (for the textContent field)."""
        return json.dumps({"ops": self._ops})

    def to_dict(self) -> dict:
        """Return Quill Delta as a dict."""
        return {"ops": deepcopy(self._ops)}

    def __str__(self) -> str:
        return self.to_json()

    def __repr__(self) -> str:
        return self.to_json()


class FreeForm:
    """
    Composable representation of a Free Form (table) visualization.

    A ``FreeForm`` can be built up from scratch — see :meth:`build`, used
    internally by :meth:`WorkspaceManager.addFreeform` — or parsed from an
    existing ``FreeformReportlet`` definition via :meth:`from_dict`.  In both
    cases the same public attributes are populated, and breakdowns are modeled
    as nested ``FreeForm`` children (:attr:`breakdowns`), mirroring how
    Workspace itself nests ``freeformTable.breakdowns[].breakdowns[]``.

    Attributes:
        title             : Table / sub-panel title.
        metrics           : Standard ``Metric`` columns, as ``{"id", "name"}`` dicts.
        calculatedMetrics : ``CalculatedMetric`` columns, as ``{"id", "name"}`` dicts.
        segments          : ``Segment`` components referenced by this table (column-splitting
                            filters or static rows).
        dimensions        : ``Dimension``/``DimensionItem`` components referenced by this table
                            (the row dimension, static rows, or column dimension-item filters).
        dateRanges        : ``DateRange`` components referenced by this table (period-comparison
                            columns, or date ranges used as static rows).
        dimension         : The dynamic row dimension component, or ``None`` if the table uses
                            static rows instead.
        staticRows        : Explicit static row entries (``Segment``/``DimensionItem``/``DateRange``
                            components, or raw ``advancedSettings`` row entries).
        breakdowns        : Nested breakdown levels, as child ``FreeForm`` instances.
        columnTree        : Raw ``columnTree`` dict (escape hatch).
        raw               : Raw source reportlet dict when parsed via :meth:`from_dict` (escape hatch).
    """

    def __init__(self, title: str = ""):
        self.title: str = title
        self.metrics: List[dict] = []
        self.calculatedMetrics: List[dict] = []
        self.segments: List[dict] = []
        self.dimensions: List[dict] = []
        self.dateRanges: List[dict] = []
        self.dimension: Optional[dict] = None
        self.staticRows: List[dict] = []
        self.breakdowns: List["FreeForm"] = []
        self.columnTree: dict = {}
        self.raw: dict = {}
        self.parentItemId: Optional[str] = None
        self.breakdownByPosition: bool = False
        self._n_columns: int = 1
        self._rows: int = 10
        self._first_metric_id: str = ""
        self._sync = None  # optional zero-arg callback; write-through to a live subPanel dict

    # ── Building ─────────────────────────────────────────────────────────

    @classmethod
    def build(
        cls,
        title: str,
        metrics: List[dict],
        dim_id: str = None,
        dim_name: str = None,
        items: List[dict] = None,
        rows: int = 10,
    ) -> "FreeForm":
        """
        Build a new ``FreeForm`` from metric/dimension/item specs.

        Arguments:
            title    : REQUIRED : Table title.
            metrics  : REQUIRED : List of metric dicts (``"id"``/``"name"``, optional ``"filters"``
                       — see :meth:`_build_column_nodes`).
            dim_id   : OPTIONAL : Dynamic row dimension ID (mutually exclusive with ``items``).
            dim_name : OPTIONAL : Dynamic row dimension name.
            items    : OPTIONAL : List of ``{"id", "name", "type"?}`` dicts for static rows.
            rows     : OPTIONAL : Pagination page size (default ``10``).
        """
        ff = cls(title=title)
        metric_nodes, first_metric_id = ff._build_column_nodes(metrics)
        ff.columnTree = ff._column_tree(metric_nodes)
        ff._first_metric_id = first_metric_id
        ff._n_columns = len(metric_nodes) + 1
        ff._rows = rows
        if dim_id:
            ff.dimension = {
                "id": dim_id, "__entity__": True, "type": "Dimension",
                "__metaData__": {"name": dim_name},
            }
        elif items:
            ff.staticRows = [_make_static_row(it["id"], it["name"], it.get("type"))[0] for it in items]
        ff._recompute_summaries()
        return ff

    def addBreakdown(
        self,
        dimension_id: str = None,
        dimension_name: str = None,
        items: List[dict] = None,
        rows: int = 5,
        parent_item_id: str = None,
    ) -> "FreeForm":
        """
        Add a breakdown nested under this table (or under this breakdown level,
        for further nesting).

        Not fluent on ``self`` — returns the **new** ``FreeForm`` representing the
        breakdown.  Call ``addBreakdown`` again on the returned object to nest
        another level; call it again on the original object to add a sibling
        breakdown instead. If this ``FreeForm`` was returned by
        :meth:`WorkspaceManager.addFreeform`, the owning project is updated
        immediately — no further action needed.

        Arguments:
            dimension_id   : OPTIONAL : Breakdown dimension ID (mutually exclusive with ``items``).
            dimension_name : OPTIONAL : Breakdown dimension name.
            items          : OPTIONAL : List of ``{"id", "name", "type"?}`` dicts for static
                             breakdown rows (segments or dimension items).
            rows           : OPTIONAL : Pagination page size for the breakdown (default ``5``).
            parent_item_id : OPTIONAL : The real Adobe Analytics ``itemId`` (as returned by a
                             report request against this table's own row dimension — see
                             Analytics.getReport2 / the "itemId" column) of the specific row
                             this breakdown attaches to. Required for Workspace to actually
                             show the row as expandable when this table's rows come from a
                             dynamic dimension (no ``items``/static rows): Adobe does not accept
                             a placeholder here, and a table with no static rows has no other
                             row identity to fall back on. Ignored (and unnecessary) when this
                             table already has static rows, whose own row ``id`` is used instead.
        """
        if not dimension_id and not items:
            raise ValueError("Either dimension_id or items must be provided.")
        child = FreeForm(title=self.title)
        child.columnTree = self.columnTree
        child._rows = rows
        child._n_columns = self._n_columns
        # Verified against 3 independent real BMW-built breakdowns (both static-row and
        # dynamic-dimension parents, single- and double-nested) — every one has
        # breakdownByPosition: false. The previous `not bool(self.staticRows)` heuristic
        # only happened to match the static-row case; it predicted `true` for a dynamic
        # parent, which doesn't match any observed example.
        child.breakdownByPosition = False
        if self.staticRows:
            child.parentItemId = self.staticRows[0]["id"]
        elif parent_item_id:
            child.parentItemId = parent_item_id
        else:
            child.parentItemId = "0"
        if dimension_id:
            child.dimension = {
                "id": dimension_id, "__entity__": True, "type": "Dimension",
                "__metaData__": {"name": dimension_name or dimension_id},
            }
        else:
            child.staticRows = [_make_static_row(it["id"], it["name"], it.get("type"))[0] for it in items]
        child._recompute_summaries()
        child._sync = self._sync
        self.breakdowns.append(child)
        if self._sync:
            self._sync()
        return child

    def _recompute_summaries(self) -> None:
        self.metrics = []
        self.calculatedMetrics = []
        self.segments = []
        self.dimensions = []
        self.dateRanges = []
        self._walk_column_nodes(self.columnTree.get("nodes", []) or [])
        if self.dimension is not None:
            self._register_component(self.dimension)
        for row in self.staticRows:
            comp = row.get("component")
            if comp:
                self._register_component(comp)
            else:
                for c in row.get("components", []) or []:
                    self._register_component(c)

    # ── Internal column-tree builders (build path) ─────────────────────────

    def _metric_node(self, metric_id: str, metric_name: str) -> dict:
        component_type = "CalculatedMetric" if metric_id.startswith("cm") else "Metric"
        return {
            "_computedValues": [],
            "component": {
                "id": metric_id, "__entity__": True, "type": component_type,
                "__metaData__": {"name": metric_name},
            },
            "dataSettings": _default_data_settings(),
            "id": _lower_uuid(),
            "name": metric_name,
            "nodes": [],
            "selectionCoordinates": [],
            "tableCellDisplay": _default_table_cell_display(),
            "visible": True,
        }

    def _filter_node(self, filter_id: str, filter_type: str, filter_name: str) -> dict:
        return {
            "_computedValues": [],
            "component": {
                "id": filter_id, "__entity__": True, "type": filter_type,
                "__metaData__": {"name": filter_name},
            },
            "dataSettings": _default_data_settings(),
            "id": _lower_uuid(),
            "name": filter_name,
            "nodes": [],
            "selectionCoordinates": [],
            "tableCellDisplay": _default_table_cell_display(),
            "visible": True,
        }

    def _get_leaf_metric_id(self, node: dict) -> str:
        comp_type = node.get("component", {}).get("type", "")
        if comp_type in ("Metric", "CalculatedMetric"):
            return node["id"]
        for child in node.get("nodes", []):
            result = self._get_leaf_metric_id(child)
            if result:
                return result
        return node["id"]

    def _build_column_nodes(self, metrics: List[dict]) -> tuple:
        """
        Build the list of columnTree nodes from a list of metric dicts.

        Each metric dict may carry an optional ``"filters"`` list.  Each filter
        must have ``"id"``, ``"name"``, and optionally ``"type"``
        (``"DimensionItem"`` or ``"Segment"``; defaults to ``"Segment"``).

        Rules:

        * No filters → plain metric node.
        * Segment filters only → metric node whose ``nodes`` are the segments
          (the metric appears as one column, split by segment sub-columns).
        * DimensionItem filters only → one outer DimensionItem node per filter
          item, each containing a copy of the metric node as its child (each
          dim-item value becomes its own column).
        * Both → one DimensionItem node per dim-item filter, each containing
          the metric node which itself has the segment nodes as children.

        Returns ``(nodes, first_sort_id)`` where *first_sort_id* is the node id
        of the first leaf metric, suitable for ``freeformTable.sort.columnId``.
        """
        all_nodes: List[dict] = []
        first_sort_id: str = ""

        for m in metrics:
            filters = m.get("filters", [])
            dim_filters = [f for f in filters if f.get("type") == "DimensionItem"]
            seg_filters = [f for f in filters if f.get("type") != "DimensionItem"]

            base_metric = self._metric_node(m["id"], m["name"])

            if seg_filters:
                base_metric["nodes"] = [
                    self._filter_node(f["id"], f.get("type", "Segment"), f["name"])
                    for f in seg_filters
                ]

            if not dim_filters:
                all_nodes.append(base_metric)
                if not first_sort_id:
                    first_sort_id = self._get_leaf_metric_id(base_metric)
            else:
                for dim_f in dim_filters:
                    outer = self._filter_node(dim_f["id"], "DimensionItem", dim_f["name"])
                    inner = deepcopy(base_metric)
                    inner["id"] = _lower_uuid()
                    outer["nodes"] = [inner]
                    all_nodes.append(outer)
                    if not first_sort_id:
                        first_sort_id = inner["id"]

        return all_nodes, first_sort_id or (all_nodes[0]["id"] if all_nodes else "")

    def _column_tree(self, metric_nodes: List[dict]) -> dict:
        return {
            "_computedValues": [],
            "dataSettings": _default_data_settings(),
            "id": f"{_short_hex_id()}-0",
            "name": "",
            "nodes": metric_nodes,
            "selectionCoordinates": [],
            "tableCellDisplay": _default_table_cell_display(),
            "visible": True,
        }

    # ── Serialisation (build path → dict) ──────────────────────────────────

    def _to_freeform_table(self) -> dict:
        first_metric_id = self._first_metric_id
        if not first_metric_id and self.columnTree.get("nodes"):
            first_metric_id = self._get_leaf_metric_id(self.columnTree["nodes"][0])
        use_dimension = self.dimension is not None
        table: dict = {
            "alignDatesForTimeDimension": True,
            "attributionSettings": [],
            "breakdowns": [bd._to_breakdown_entry() for bd in self.breakdowns],
            "collapsed": False,
            "columnWidths": [100.0] * max(self._n_columns, 1),
            "hyperlinks": [],
            "pagination": {"currentPage": 0, "viewBy": self._rows},
            "parentItemIds": [],
            "selectionCoordinates": [],
            "settings": {
                "breakdownByPosition": False,
                "rowBasedPercentages": False,
                "showThumbnails": False,
                "totalsType": "allVisits" if use_dimension else "columnSum",
            },
            "sort": {
                "advancedSortRules": [], "asc": False,
                "columnId": first_metric_id, "labelColumn": False,
            },
            "staticRows": deepcopy(self.staticRows),
            "staticSearch": _default_search(),
            "statistics": {"functions": [], "ignoreZeros": True},
        }
        if use_dimension:
            # Adobe migrated the wire format for a table's dynamic row dimension from a bare
            # `dimension` key to a `dimensionSettings` array sometime around 2025 — real 2026
            # exports never contain `dimension` any more (verified against the local Workspaces/
            # corpus by file-timestamp), and `createProject`/`updateProject` reject it outright
            # with an "unwanted" schema-validation error. `_parse_table_rows` already reads
            # `dimensionSettings` first for exactly this reason; this is its write-path counterpart.
            table["dimensionSettings"] = [{
                "id": _short_hex_id(),
                "dimension": deepcopy(self.dimension),
                "search": _default_search(),
            }]
        return table

    def _to_breakdown_entry(self) -> dict:
        # A breakdown entry is wire-identical to a top-level freeformTable — Adobe migrated
        # both away from the bare `dimension`/`parentItemId`/`search` keys to
        # `dimensionSettings`/`parentItemIds`/`staticSearch` (see _to_freeform_table), but only
        # the top-level table serializer was updated to match; this one kept emitting the old
        # shape, which createProject/updateProject now reject outright (verified against a real
        # BMW project export using the current shape, and against createProject's actual "unwanted
        # properties: dimension, parentItemId, search" validation error on the old shape).
        entry = self._to_freeform_table()
        entry["settings"]["breakdownByPosition"] = self.breakdownByPosition
        entry["parentItemIds"] = [self.parentItemId] if self.parentItemId else []
        return entry

    def to_dict(self) -> dict:
        """Serialize back to a ``FreeformReportlet`` dict, ready to embed in a sub-panel."""
        return {
            "advancedMode": False,
            "advancedSettings": {"rows": [], "tableState": "builder"},
            "columnTree": deepcopy(self.columnTree),
            "freeformTable": self._to_freeform_table(),
            "hideTitle": False,
            "intelligentCaptions": _intelligent_captions(),
            "isConfigVisible": True,
            "isReadOnly": False,
            "name": self.title,
            "showAnnotations": True,
            "showControls": True,
            "type": "FreeformReportlet",
        }

    # ── Parsing (existing reportlet → FreeForm) ────────────────────────────

    @classmethod
    def from_dict(cls, reportlet: dict) -> "FreeForm":
        """
        Parse an existing ``FreeformReportlet`` dict into a ``FreeForm``.

        Handles the row-encoding shapes observed in real Workspace exports
        (``dimensionSettings``/``dimension``/``dimensions`` for a dynamic row
        dimension; ``staticRows`` for pinned rows; and ``advancedSettings.rows``
        for tables authored in "advanced" mode), and recurses into
        ``freeformTable.breakdowns`` and ``columnTree`` nodes (a
        ``Segment``/``DimensionItem`` node wrapping a child ``Metric`` node
        means "this metric filtered by this segment/item").
        """
        reportlet = reportlet or {}
        ff = cls(title=reportlet.get("name", ""))
        ff.raw = reportlet
        ff.columnTree = reportlet.get("columnTree", {}) or {}
        ff._walk_column_nodes(ff.columnTree.get("nodes", []) or [])

        table = reportlet.get("freeformTable", {}) or {}
        ff._parse_table_rows(table)

        advanced = reportlet.get("advancedSettings", {}) or {}
        if reportlet.get("advancedMode") or advanced.get("tableState") == "done":
            for row in advanced.get("rows", []) or []:
                components = row.get("components", []) or []
                for comp in components:
                    ff._register_component(comp)
                if components:
                    ff.staticRows.append({"components": components, "key": row.get("key")})

        for bd in table.get("breakdowns", []) or []:
            ff.breakdowns.append(ff._parse_breakdown(bd))
        return ff

    def _walk_column_nodes(self, nodes: List[dict]) -> None:
        for node in nodes or []:
            self._register_component(node.get("component") or {})
            self._walk_column_nodes(node.get("nodes", []) or [])

    def _register_component(self, comp: dict) -> None:
        if not comp or "id" not in comp:
            return
        entry = {"id": comp["id"], "name": (comp.get("__metaData__") or {}).get("name", comp["id"])}
        target = {
            "Metric": self.metrics,
            "CalculatedMetric": self.calculatedMetrics,
            "Segment": self.segments,
            "Dimension": self.dimensions,
            "DimensionItem": self.dimensions,
            "DateRange": self.dateRanges,
        }.get(comp.get("type", ""))
        if target is not None and not any(e["id"] == entry["id"] for e in target):
            target.append(entry)

    def _parse_table_rows(self, table: dict) -> None:
        dim = None
        dim_settings = table.get("dimensionSettings")
        if dim_settings:
            dim = (dim_settings[0] or {}).get("dimension")
        elif table.get("dimension"):
            dim = table.get("dimension")
        elif table.get("dimensions"):
            dims = table.get("dimensions") or []
            dim = dims[0] if dims else None
            for d in dims:
                self._register_component(d)
        if dim:
            self.dimension = dim
            self._register_component(dim)
        for row in table.get("staticRows", []) or []:
            self.staticRows.append(row)
            self._register_component(row.get("component") or {})

    def _parse_breakdown(self, bd: dict) -> "FreeForm":
        child = FreeForm(title=self.title)
        child.raw = bd
        child.metrics = list(self.metrics)
        child.calculatedMetrics = list(self.calculatedMetrics)
        child.dateRanges = list(self.dateRanges)
        child.columnTree = self.columnTree
        # `parentItemId` (singular) is the pre-migration key; current exports use
        # `parentItemIds` (a list) instead — see _to_breakdown_entry.
        parent_item_ids = bd.get("parentItemIds")
        child.parentItemId = (parent_item_ids[0] if parent_item_ids else None) or bd.get("parentItemId")
        child.breakdownByPosition = bool((bd.get("settings") or {}).get("breakdownByPosition", False))
        child._parse_table_rows(bd)
        for nested in bd.get("breakdowns", []) or []:
            child.breakdowns.append(child._parse_breakdown(nested))
        return child

    def __str__(self) -> str:
        return json.dumps(self.to_dict(), indent=4)

    def __repr__(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


_COMPONENT_ATTRS = ("dimensions", "metrics", "calculatedMetrics", "segments", "dateRanges")


def _find_column_node(column_tree: dict, node_id: str) -> Optional[dict]:
    """Recursively find a ``columnTree`` node by its ``id``."""
    def _walk(nodes):
        for node in nodes or []:
            if node.get("id") == node_id:
                return node
            found = _walk(node.get("nodes", []))
            if found is not None:
                return found
        return None
    return _walk((column_tree or {}).get("nodes", []))


def _collect_freeform_components(ff: "FreeForm") -> Dict[str, List[dict]]:
    """Merge a FreeForm's own components with those of every nested breakdown, de-duplicated by id."""
    merged: Dict[str, Dict[str, dict]] = {k: {} for k in _COMPONENT_ATTRS}

    def _walk(node: "FreeForm") -> None:
        for key in _COMPONENT_ATTRS:
            for comp in getattr(node, key):
                merged[key].setdefault(comp["id"], comp)
        for bd in node.breakdowns:
            _walk(bd)

    _walk(ff)
    return {k: list(v.values()) for k, v in merged.items()}


def _collect_locked_selection_points(locked: dict) -> List[dict]:
    """Recursively gather ``selectedDataPoints`` from a ``lockedSelection`` dict — each
    entry in its ``breakdowns`` list has the same shape and can itself nest further,
    matching the linked table's own breakdown depth (observed up to several levels deep)."""
    points = list((locked or {}).get("selectedDataPoints", []) or [])
    for bd in (locked or {}).get("breakdowns", []) or []:
        points.extend(_collect_locked_selection_points(bd))
    return points


def _resolve_visualization_components(reportlet: dict, linked_ff: "FreeForm") -> Dict[str, List[dict]]:
    """
    Resolve which components a chart/KPI visualization actually shows.

    Charts and KPI cards carry no data of their own — they point at a sibling
    ``FreeformReportlet`` via ``linkedSourceId`` and pick specific columns/rows
    from it, usually via ``lockedSelection`` (``columnId`` indexes into the linked
    table's ``columnTree``; ``rowItem``/``rowPosition`` identify a specific row).
    Some simpler chart types (e.g. ``HistogramReportlet``) instead carry a direct
    ``component`` key naming the metric/dimension shown. Older/undocumented
    variants (e.g. ``sourceCoords``-only ``SummaryNumberReportlet``, or charts
    with only ``disabledLegends``) don't carry a resolvable reference at all and
    are left empty rather than guessed.
    """
    result: Dict[str, List[dict]] = {k: [] for k in _COMPONENT_ATTRS}
    target_by_type = {
        "Metric": result["metrics"], "CalculatedMetric": result["calculatedMetrics"],
        "Segment": result["segments"], "Dimension": result["dimensions"],
        "DimensionItem": result["dimensions"], "DateRange": result["dateRanges"],
    }
    seen: set = set()

    def _add(comp: dict) -> None:
        if not comp or "id" not in comp or comp["id"] in seen:
            return
        target = target_by_type.get(comp.get("type", ""))
        if target is None:
            return
        seen.add(comp["id"])
        target.append({"id": comp["id"], "name": (comp.get("__metaData__") or {}).get("name", comp["id"])})

    for dp in _collect_locked_selection_points(reportlet.get("lockedSelection", {}) or {}):
        _add(dp.get("rowItem"))
        col_id = dp.get("columnId")
        if col_id:
            node = _find_column_node(linked_ff.columnTree, col_id)
            if node:
                _add(node.get("component"))
        row_pos = dp.get("rowPosition")
        if isinstance(row_pos, int) and 0 <= row_pos < len(linked_ff.staticRows):
            _add(linked_ff.staticRows[row_pos].get("component"))

    _add(reportlet.get("component"))

    if linked_ff.dimension is not None:
        _add(linked_ff.dimension)

    return result


class Panel:
    """
    Composable representation of one node in a Workspace's panel tree.

    A ``Panel`` is either a container (``type == "SubPanel"``, holding nested
    :attr:`elements`) or a leaf (``type`` one of ``"FreeForm"``, ``"Text"``,
    ``"Visualization"``).  Adobe Workspace itself only nests two levels deep
    (project panel → subPanels), but parsing recurses generically through
    ``elements`` so any deeper nesting still parses without extra work.

    Attributes:
        id, name, description, collapsed : Basic panel metadata.
        type           : One of ``"SubPanel"``, ``"FreeForm"``, ``"Text"``, ``"Visualization"``.
        position       : Raw ``{x, y, width, autoHeight, autoSize}`` dict.
        elements       : Nested ``Panel`` children (``type == "SubPanel"`` only).
        freeform       : A :class:`FreeForm` instance (``type == "FreeForm"`` only).
        text           : Plain-text rendering of the text panel (``type == "Text"`` only).
        textOps        : Raw Quill Delta ops (``type == "Text"`` only).
        chartType      : Raw reportlet type string, e.g. ``"LineReportlet"`` (``type == "Visualization"`` only).
        linkedSourceId : Sibling sub-panel id this visualization draws data from, if any.
        dimensions, metrics, calculatedMetrics, segments, dateRanges :
            De-duplicated lists of the components actually present/selected in this element.
            For ``"FreeForm"``, this is everything used in the table, including nested
            breakdowns. For ``"Visualization"``, this is resolved by following
            ``linkedSourceId`` to the backing table and cross-referencing which of its
            columns/rows are actually plotted (empty if the chart type has no linked
            table, e.g. ``Flow``/``Fallout``/``MapReportlet``). For ``"SubPanel"``, this
            is the union of everything used by its ``elements``. Always empty for ``"Text"``.
        dateRange      : Present only at the ``"SubPanel"`` (outer-panel) level.
        segmentGroups  : Present only at the ``"SubPanel"`` (outer-panel) level.
        raw            : Original source dict (escape hatch).
    """

    def __init__(self, type_: str, name: str = "", id: str = None):
        self.id = id
        self.name = name
        self.type = type_
        self.position: dict = {}
        self.description: str = ""
        self.collapsed: bool = False
        self.elements: List["Panel"] = []
        self.freeform: Optional[FreeForm] = None
        self.text: Optional[str] = None
        self.textOps: Optional[list] = None
        self.chartType: Optional[str] = None
        self.linkedSourceId: Optional[str] = None
        self.dimensions: List[dict] = []
        self.metrics: List[dict] = []
        self.calculatedMetrics: List[dict] = []
        self.segments: List[dict] = []
        self.dateRanges: List[dict] = []
        self.dateRange: Optional[dict] = None
        self.segmentGroups: Optional[list] = None
        self.raw: dict = {}

    @classmethod
    def from_panel_dict(cls, panel: dict) -> "Panel":
        """Parse an outer Adobe ``panel`` dict (project-level; has ``subPanels``)."""
        if panel.get("_opaque"):
            raw = panel.get("_raw", {}) or {}
            p = cls(_TYPE_SUBPANEL, name=raw.get("name", ""), id=raw.get("id"))
            p.raw = raw
            p.position = raw.get("position", {}) or {}
            return p

        p = cls(_TYPE_SUBPANEL, name=panel.get("name", ""), id=panel.get("id"))
        p.raw = panel
        p.position = panel.get("position", {}) or {}
        p.description = panel.get("description", "")
        p.collapsed = bool(panel.get("collapsed", False))
        p.dateRange = panel.get("dateRange")
        p.segmentGroups = panel.get("segmentGroups", [])
        for sp in panel.get("subPanels", []) or []:
            try:
                p.elements.append(cls.from_subpanel_dict(sp))
            except Exception:
                fallback = cls(_TYPE_VISUALIZATION, name=sp.get("name", ""), id=sp.get("id"))
                fallback.raw = sp
                fallback.position = sp.get("position", {}) or {}
                p.elements.append(fallback)

        # Charts/KPI cards carry no data of their own — resolve what they actually show
        # by cross-referencing their linkedSourceId sibling now that every sibling is parsed.
        by_id = {el.id: el for el in p.elements if el.id is not None}
        for el in p.elements:
            if el.type == _TYPE_VISUALIZATION and el.linkedSourceId:
                sibling = by_id.get(el.linkedSourceId)
                if sibling is not None and sibling.freeform is not None:
                    reportlet = (el.raw or {}).get("reportlet", {}) or {}
                    resolved = _resolve_visualization_components(reportlet, sibling.freeform)
                    el.dimensions = resolved["dimensions"]
                    el.metrics = resolved["metrics"]
                    el.calculatedMetrics = resolved["calculatedMetrics"]
                    el.segments = resolved["segments"]
                    el.dateRanges = resolved["dateRanges"]

        # This panel's own totals are the union of everything used by its elements.
        for key in _COMPONENT_ATTRS:
            merged: Dict[str, dict] = {}
            for el in p.elements:
                for comp in getattr(el, key):
                    merged.setdefault(comp["id"], comp)
            setattr(p, key, list(merged.values()))
        return p

    @classmethod
    def from_subpanel_dict(cls, subpanel: dict) -> "Panel":
        """Parse an inner Adobe ``subPanel`` dict (wraps exactly one reportlet)."""
        reportlet = subpanel.get("reportlet", {}) or {}
        rtype = reportlet.get("type", "")
        if rtype == "FreeformReportlet":
            ptype = _TYPE_FREEFORM
        elif rtype in _TEXT_REPORTLET_TYPES:
            ptype = _TYPE_TEXT
        else:
            ptype = _TYPE_VISUALIZATION

        p = cls(ptype, name=subpanel.get("name", ""), id=subpanel.get("id"))
        p.raw = subpanel
        p.position = subpanel.get("position", {}) or {}
        p.description = subpanel.get("description", "")
        p.collapsed = bool(subpanel.get("collapsed", False))
        p.linkedSourceId = subpanel.get("linkedSourceId") or None

        if ptype == _TYPE_FREEFORM:
            try:
                p.freeform = FreeForm.from_dict(reportlet)
                merged = _collect_freeform_components(p.freeform)
                p.dimensions = merged["dimensions"]
                p.metrics = merged["metrics"]
                p.calculatedMetrics = merged["calculatedMetrics"]
                p.segments = merged["segments"]
                p.dateRanges = merged["dateRanges"]
            except Exception:
                p.type = _TYPE_VISUALIZATION
                p.chartType = rtype
        elif ptype == _TYPE_TEXT:
            ops = []
            try:
                ops = json.loads(reportlet.get("textContent") or "{}").get("ops", [])
            except (json.JSONDecodeError, AttributeError):
                pass
            p.textOps = ops
            p.text = "".join(op.get("insert", "") for op in ops if isinstance(op, dict))
        else:
            p.chartType = rtype

        return p

    def _summary_dict(self) -> dict:
        d = {
            "id": self.id, "name": self.name, "type": self.type, "position": self.position,
            "dimensions": self.dimensions, "metrics": self.metrics,
            "calculatedMetrics": self.calculatedMetrics, "segments": self.segments,
            "dateRanges": self.dateRanges,
        }
        if self.type == _TYPE_SUBPANEL:
            d["elements"] = [e._summary_dict() for e in self.elements]
        elif self.type == _TYPE_FREEFORM and self.freeform is not None:
            d["breakdowns"] = len(self.freeform.breakdowns)
        elif self.type == _TYPE_TEXT:
            d["text"] = self.text
        elif self.type == _TYPE_VISUALIZATION:
            d["chartType"] = self.chartType
            d["linkedSourceId"] = self.linkedSourceId
        return d

    def __str__(self) -> str:
        return json.dumps(self._summary_dict(), indent=4)

    def __repr__(self) -> str:
        return json.dumps(self._summary_dict(), indent=2)


class WorkspaceManager:
    """
    Programmatically compose and parse Adobe Analytics Workspace projects.

    Building supports composable sub-panel content types: rich text via the
    `TextBuilder` class, and data tables via the `FreeForm` class.

    Reading is symmetric: instantiate with ``data=`` pointing at an existing
    project (dict, JSON string, or ``.json`` file path) 
    Provide a `panels` attributes to see content via a list of `Panel` objects. 
    
    Available attributes:
    - dimensions
    - metrics
    - calculatedMetrics
    - segments
    - dateRanges
    They list a de-duplicated project-wide view of every such component referenced anywhere in the
    project. The same five attributes are also available on each `Panel` (see `panels`), scoped to
    just that panel/element instead of the whole project.
    Other attributes: 
    - version
    - created
    - modified
    - owner

    Typical usage::

        wc = (
            WorkspaceManager("myrsid", "My Project", analytics=analytics)
            .addPanel("Overview", date_range="thisMonth")
            .addSegmentFilter("s1234_abc")
            .addTextFreeform("Introduction", TextBuilder().addTitle("Hello"))
        )
        ff = wc.addFreeform("Activity", item_id="variables/targetraw.activity",
                             metrics=[{"id": "metrics/visits"}])
        ff.addBreakdown(dimension_id="variables/targetraw.experience")
        project_dict = wc.to_dict()

        # Parsing an existing (downloaded) project, offline:
        wc2 = WorkspaceManager(data="Workspaces/601d463a5e4798774c5f9ec2.json")
        for panel in wc2.panels:
            print(panel.name, panel.type)
        print(wc2.version, wc2.created, wc2.owner)
        print(wc2.dimensions)
    """

    DEFAULT_COLOR_SCHEME = [
        "#26C0C7", "#5151D3", "#E68619", "#D83790", "#908DFA", "#58E06F",
        "#2780EB", "#6F38B1", "#DFBF03", "#CB6F10", "#268D6C", "#9BEC54",
        "#5EABFA", "#BE40CC", "#F56BB7", "#FEE02D",
    ]

    def __init__(
        self,
        data: Union[str, dict] = None,
        rsid: str = None,
        name: str = None,
        description: str = "",
        tags: List[Union[int, dict]] = None,
        shares: List[dict] = None,
        config=None,
        companyId=None,
        analytics=None,
    ) -> None:
        """
        Arguments:
            rsid        : REQUIRED : Report suite ID. Required when not loading from ``data``.
            name        : REQUIRED : Workspace project name. Required when not loading from ``data``.
            description : OPTIONAL : Project description.
            data        : OPTIONAL : Existing project definition to load from. Can be:

                * ``dict`` – a project definition as returned by the API.
                * ``str`` ending in ``.json`` – path to a JSON file.
                * raw JSON ``str``.

                When provided, ``analytics``/``config``/``companyId`` become optional —
                every component reference in an export already carries its display name,
                so parsing needs no live API access. ``rsid``, ``name``, and ``description``
                override the values found in the definition when explicitly supplied.
            tags        : OPTIONAL : List of tags to associate with the project. Each item
                          may be:

                * ``int`` – tag ID only, e.g. ``[42, 99]``.
                * ``dict`` – full tag object, e.g. ``{"id": 42, "name": "prod"}``.

                When loading from ``data``, existing tags are preserved and these are
                added on top.
            shares      : OPTIONAL : List of share objects. Each dict must contain at
                          minimum ``"shareToType"`` (``"user"``, ``"group"``, or ``"all"``)
                          and, for ``"user"``/``"group"``, a ``"shareToId"`` (int). Example::
                              [{"shareToId": 622291, "shareToType": "user"}]
            analytics   : OPTIONAL : An :class:`aanalytics2.Analytics` instance used to
                          auto-resolve component names from IDs (and vice-versa) when
                          *building* a project. When ``data`` is supplied, only needed if
                          you also intend to call builder methods (``add*``) afterwards.
            config      : OPTIONAL : Configuration object returned by ``importConfigFile`` or
                          ``configure`` when called with ``return_object=True``.  Carries
                          connection settings (company, endpoint, …) but does **not** expose
                          the Analytics API methods. It requires the companyId argument to be also passed.
            companyId   : OPTIONAL : Company ID to associate with the Adobe Analytics.
                            Required if not using the "analytics" argument.

        """
        self._panels: List[dict] = []
        self._current_panel_index: int = -1
        self.id: str = _upper_uuid()
        self._has_real_id: bool = False
        self.name: str = ""
        self._definition_meta: dict = None
        self.tags: List[dict] = []
        self.shares: List[dict] = []
        self.version: str = ""
        self.created: str = ""
        self.modified: str = ""
        if analytics is None and (config is None or companyId is None) and data is None:
            raise ValueError("Either 'analytics' or both 'config' and 'companyId' must be provided when not loading from 'data'.")
        self._config = config
        # Analytics instance for name/ID auto-resolution (optional)
        if analytics is None and config is not None:
            from aanalytics2 import Analytics
            self._analytics = Analytics(company_id=companyId, config=config)
        else:
            self._analytics = analytics
        # Normalise the owner argument
        userMe = self._analytics.getUserMe() if self._analytics else None
        self.owner: dict = {"id": userMe["loginId"], "name": userMe.get("name", ""), "login": userMe.get("login", "")} if userMe else {"id": None, "name": "", "login": ""}
        # Normalise tags
        if tags:
            for t in tags:
                if isinstance(t, int):
                    self.tags.append({"id": t})
                else:
                    self.tags.append(dict(t))
        # Normalise shares
        if shares:
            for s in shares:
                self.shares.append(dict(s))
        if data is not None:
            if isinstance(data, str):
                if data.strip().endswith('.json'):
                    with open(data, 'r') as f:
                        data = json.load(f)
                else:
                    data = json.loads(data)
            data = deepcopy(data)
            self._has_real_id = bool(data.get("id"))
            self.id = data.get("id") or self.id
            self.rsid = rsid or data.get("rsid", "")
            self.name = name or data.get("name", "")
            self.description = description or data.get("description", "")
            self.created = data.get("created", "")
            self.modified = data.get("modified", "")
            if data.get("owner"):
                self.owner = dict(data["owner"])
            if self._analytics:
                self.rsid_name = self._analytics.getReportSuite(self.rsid).get('name') or data.get("reportSuiteName", self.rsid)
            else:
                self.rsid_name = data.get("reportSuiteName", self.rsid)
            # Preserve tags/shares from loaded project; constructor-supplied ones extend them
            for t in data.get("tags", []):
                if not any(existing.get("id") == t.get("id") for existing in self.tags):
                    self.tags.append(dict(t))
            for s in data.get("shares", []):
                self.shares.append(dict(s))
            defn = data.get("definition", {})
            self.version = defn.get("version", "")
            workspaces = defn.get("workspaces", [{}])
            ws0 = workspaces[0] if workspaces else {}
            existing_panels = ws0.pop("panels", [])
            self._definition_meta = defn
            for p in existing_panels:
                try:
                    panel = deepcopy(p)
                    # A standard panel must have a position dict; if not, treat as opaque
                    if not isinstance(panel.get("position"), dict):
                        raise ValueError("Non-standard panel structure: missing 'position'.")
                    panel["_yOffset"] = sum(
                        sp.get("position", {}).get("autoHeight", 0)
                        for sp in panel.get("subPanels", [])
                    )
                    panel["_vizIndex"] = len(panel.get("subPanels", [])) + 1
                    # Ensure mutable keys exist even if absent in the source
                    panel.setdefault("subPanels", [])
                    panel.setdefault("segmentGroups", [])
                    self._panels.append(panel)
                except Exception:
                    # Unrecognised panel structure: preserve raw definition
                    self._panels.append({
                        "_opaque": True,
                        "_raw": deepcopy(p),
                        "_yOffset": 0,
                        "_vizIndex": 1,
                    })
            if self._panels:
                self._current_panel_index = len(self._panels) - 1
        else:  ## No data to load from – initialise from arguments
            if not rsid:
                raise ValueError("rsid is required when not loading from data.")
            if not name:
                raise ValueError("name is required when not loading from data.")
            self.rsid = rsid
            self.name = name
            self.description = description
            self.rsid_name = self._analytics.getReportSuite(self.rsid).get('name')

        if self._analytics:
            (
                self._segments_id_name,
                self._dim_id_name,
                self._metric_id_name,
                self._calc_metric_id_name,
                self._date_ranges_id_name,
            ) = self._run_async(self._fetch_all_company_data())
        else:
            self._segments_id_name = {}
            self._dim_id_name = {}
            self._metric_id_name = {}
            self._calc_metric_id_name = {}
            self._date_ranges_id_name = {}

    def __str__(self) -> str:
        return json.dumps(self.to_dict(), indent=4)

    def __repr__(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    # ── Internal helpers ──────────────────────────────────────────────────────────

    def _run_async(self, coro):
        try:
            asyncio.get_running_loop()
            # Already inside a running loop (e.g. Jupyter): offload to a thread
            with futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(asyncio.run, coro).result()
        except RuntimeError:
            return asyncio.run(coro)

    async def _fetch_all_company_data(self) -> tuple:
        """Run all four company-data requests in parallel, sharing one AsyncClient."""
        timeout = httpx.Timeout(10.0, read=120.0)
        limits = httpx.Limits(max_connections=100, max_keepalive_connections=50)
        async with httpx.AsyncClient(timeout=timeout, limits=limits) as client:
            results = await asyncio.gather(
                self.__request_company_data__('segments', client=client),
                self.__request_company_data__('dimensions', {'rsid': self.rsid}, client=client),
                self.__request_company_data__('metrics', {'rsid': self.rsid}, client=client),
                self.__request_company_data__('calculatedMetrics', client=client),
                self.__request_company_data__('dateRanges', client=client),
            )
        return results

    async def __request_company_data__(self, service: str = None, params: dict = None, client: httpx.AsyncClient = None) -> dict:
        """
        Make an authenticated request to the Adobe Analytics API.

        Arguments:
            service : REQUIRED : One of "segments", "metrics", "dimensions", or "calculatedMetrics".
            params  : OPTIONAL : Query parameters for GET requests.

        Returns:
            dict: The JSON response from the API.
        """
        endpoint_map = {
            "segments": f"/segments",
            "metrics": f"/metrics",
            "dimensions": f"/dimensions",
            "calculatedMetrics": f"/calculatedmetrics",
            "dateRanges": f"/dateranges",
        }
        if service not in endpoint_map:
            raise ValueError(f"Invalid service '{service}'. Must be one of: {', '.join(endpoint_map.keys())}.")
        endpoint = self._analytics.endpoint_company + endpoint_map[service]
        header = self._analytics.header
        if service in ["segments", "calculatedMetrics","dateRanges"]:
            params = {'includeType': 'all', 'page': 0, 'limit': 10000}
        own_client = client is None
        if own_client:
            client = httpx.AsyncClient(
                timeout=httpx.Timeout(10.0, read=120.0),
                limits=httpx.Limits(max_connections=100, max_keepalive_connections=50),
            )
        async def get_json(request_params):
            # Adobe rate-limits (429) under bursty call volume — this fetcher runs once per
            # WorkspaceManager instantiation, and the MCP builder tools instantiate one per
            # call, so a chain of add_* calls can trigger several of these in quick succession.
            # Without a retry, a 429 body (a small error dict, not the expected list) gets fed
            # straight into `{el['id']: ... for el in json_data}` below and crashes with a
            # confusing "string indices must be integers" TypeError instead of a clear one.
            delay = 1.0
            for attempt in range(5):
                response = await client.get(endpoint, headers=header, timeout=httpx.Timeout(60.0, pool=None), params=request_params)
                if response.status_code == 429 and attempt < 4:
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, 10.0)
                    continue
                response.raise_for_status()
                return response.json()

        try:
            json_data = await get_json(params)
            if service in ["segments", "calculatedMetrics","dateRanges"]:
                data = json_data.get('content', [])
                last_page = json_data.get('lastPage', True)
                while not last_page:
                    params['page'] += 1
                    json_data = await get_json(params)
                    data += json_data.get('content', [])
                    last_page = json_data.get('lastPage', True)
        finally:
            if own_client:
                await client.aclose()
        if service == "dimensions":
            return {el['id']: el['name'] for el in json_data}
        elif service == "metrics":
            return {el['id']: el['name'] for el in json_data}
        elif service == "segments":
            return {el['id']:el['name'] for el in data}
        elif service == "calculatedMetrics":
            return {el['id']:el['name'] for el in data}
        elif service == "dateRanges":
            return {el['id']:el['name'] for el in data}

    # ── Parsed read-only views ───────────────────────────────────────────────

    @property
    def panels(self) -> List[Panel]:
        """Parsed view of every panel as a :class:`Panel` tree (recomputed on each access,
        so panels added via the fluent ``add*`` API show up here too)."""
        result = []
        for p in self._panels:
            try:
                result.append(Panel.from_panel_dict(p))
            except Exception:
                fallback = Panel(_TYPE_SUBPANEL, name=p.get("name", ""), id=p.get("id"))
                fallback.raw = p
                result.append(fallback)
        return result

    def _aggregate_components(self, attr: str) -> List[dict]:
        # Each top-level Panel already carries the fully-resolved union of its own
        # elements (FreeForm breakdowns walked, Visualization lockedSelection/component
        # resolved) — see Panel.from_panel_dict — so a project-wide total is just the
        # union across panels, with no need to re-walk FreeForm objects separately.
        seen: Dict[str, dict] = {}
        for panel in self.panels:
            for comp in getattr(panel, attr):
                seen.setdefault(comp["id"], comp)
        return list(seen.values())

    @property
    def dimensions(self) -> List[dict]:
        """De-duplicated list of every ``Dimension``/``DimensionItem`` used anywhere in the project."""
        return self._aggregate_components("dimensions")

    @property
    def metrics(self) -> List[dict]:
        """De-duplicated list of every standard ``Metric`` used anywhere in the project."""
        return self._aggregate_components("metrics")

    @property
    def calculatedMetrics(self) -> List[dict]:
        """De-duplicated list of every ``CalculatedMetric`` used anywhere in the project."""
        return self._aggregate_components("calculatedMetrics")

    @property
    def segments(self) -> List[dict]:
        """De-duplicated list of every ``Segment`` used anywhere in the project."""
        return self._aggregate_components("segments")

    @property
    def dateRanges(self) -> List[dict]:
        """De-duplicated list of every ``DateRange`` used anywhere in the project."""
        return self._aggregate_components("dateRanges")

    # ── Panel management ───────────────────────────────────────────────────

    def addPanel(
        self,
        name: str,
        date_range: str = "thisMonth",
        position: int = None,
        collapsed: bool = False,
        description: str = "",
    ) -> "WorkspaceManager":
        """
        Add a new panel to the workspace.  All subsequent ``add*`` calls
        target the most recently added panel.

        Arguments:
            name        : REQUIRED : Panel title.
            date_range  : OPTIONAL : Date-range ID or Name (default: ``"thisMonth"``),
                          **or** a custom ISO 8601 interval string such as
                          ``"2026-04-22T00:00:00/2026-05-07T23:59:59"``. When the value
                          contains ``"/"`` it is treated as a custom interval and placed
                          in ``__metaData__.definition`` instead of ``id``.
            position    : OPTIONAL : Zero-based index at which to insert the panel.
                          Defaults to appending at the end.
            collapsed   : OPTIONAL : Whether the panel is collapsed (default ``False``).
            description : OPTIONAL : Panel description (default ``""``).
        """
        # Custom date ranges (ISO 8601 intervals like "2026-04-22T00:00:00/2026-05-07T23:59:59")
        # must be expressed via __metaData__.definition rather than an id, because the API
        # tries to resolve an id as a stored resource and returns 404.
        if "/" in date_range:
            date_range_obj = {
                "__entity__": True,
                "type": "DateRange",
                "__metaData__": {"definition": date_range},
            }
        else:
            if date_range in self._date_ranges_id_name.keys():
                dateRangeId = date_range
                dateRangeName = self._date_ranges_id_name[dateRangeId]
            elif date_range in self._date_ranges_id_name.values():
                dateRangeName = date_range
                dateRangeId = [k for k, v in self._date_ranges_id_name.items() if v == dateRangeName][0]
            else:
                if date_range == "thisMonth":
                    dateRangeId = "thisMonth"
                    dateRangeName = "This Month"
                else:
                    if not self._analytics:
                        raise ValueError(
                            f"Date range '{date_range}' is not a known preset or a custom interval, "
                            "and 'analytics' is not set to look it up."
                        )
                    try:
                        dateRangeId = date_range
                        dateRangeName = self._analytics.getDateRange(dateRangeId)['name'] ## forcing error if not found
                    except Exception:
                        raise ValueError(f"Date range '{date_range}' not found in company data and does not match any known presets.")
            date_range_obj = {
                "id": dateRangeId,
                "__entity__": True,
                "type": "DateRange",
                "__metaData__": {"name": dateRangeName},
            }
        panel = {
            "collapsed": collapsed,
            "dateRange": date_range_obj,
            "datesAreRelativeToPanel": False,
            "description": description,
            "id": _upper_uuid(),
            "name": name,
            "position": {"autoHeight": 0, "autoSize": True, "width": 100, "x": 0, "y": 0},
            "reportSuite": {
                "id": self.rsid,
                "__entity__": True,
                "type": "ReportSuite",
                "__metaData__": {"name": self.rsid_name, "rsid": self.rsid},
            },
            "segmentGroups": [],
            "subPanels": [],
            "type": "panel",
            # internal tracking – stripped by to_dict()
            "_yOffset": 0,
            "_vizIndex": 1,
        }
        if position is None or position >= len(self._panels):
            self._panels.append(panel)
            self._current_panel_index = len(self._panels) - 1
        else:
            insert_at = max(0, position)
            self._panels.insert(insert_at, panel)
            self._current_panel_index = insert_at
        return self

    def _current_panel(self) -> dict:
        if not self._panels or self._current_panel_index < 0:
            raise ValueError("No panel exists. Call addPanel() first.")
        return self._panels[self._current_panel_index]

    def addSegmentFilter(
        self, segment: str = None
    ) -> "WorkspaceManager":
        """
        Add a global segment to the current panel.

        Arguments:
            segment   : OPTIONAL : Segment ID or Segment Name.
                        If segment name passed and match multiple segments, the first match is used.
        """
        if not segment:
            raise ValueError("segment name or ID must be provided.")
        if segment in self._segments_id_name.keys():
            segment_id = segment
            segment_name = self._segments_id_name[segment_id]
        elif segment in self._segments_id_name.values():
            segment_name = segment
            segment_id = [k for k, v in self._segments_id_name.items() if v == segment_name][0]
        else:
            if not self._analytics:
                raise ValueError(f"Segment '{segment}' not found in cached company data, and 'analytics' is not set to look it up.")
            segment_id = segment
            segment_name = self._analytics.getSegment(segment_id)['name'] ## try API lookup as a last resort (may error if not found)
        panel = self._current_panel()
        if panel.get("_opaque"):
            raise ValueError(
                "The current panel has an unrecognised structure and cannot be modified. "
                "Call addPanel() to create a new panel first."
            )
        panel["segmentGroups"].append(
            {
                "componentOptions": [
                    {
                        "component": {
                            "id": segment_id,
                            "__entity__": True,
                            "type": "Segment",
                            "__metaData__": {"name": segment_name},
                        },
                        "isActive": True,
                    }
                ],
                "groupName": "",
                "hasNoFilter": False,
                "runAs": "segment",
                "showGroupName": True,
            }
        )
        return self

    def _find_last_freeform_table(
        self, panel: dict, source: Union[int, str] = None
    ) -> dict:
        """Return the mutable ``freeformTable`` dict of the last (or specified) ``FreeformReportlet``."""
        subpanels = panel.get("subPanels", [])
        if source is None:
            for sp in reversed(subpanels):
                r = sp.get("reportlet", {})
                if r.get("type") == "FreeformReportlet":
                    return r["freeformTable"]
        elif isinstance(source, int):
            r = subpanels[source].get("reportlet", {})
            if r.get("type") == "FreeformReportlet":
                return r["freeformTable"]
        elif isinstance(source, str):
            for sp in reversed(subpanels):
                r = sp.get("reportlet", {})
                if sp.get("name") == source and r.get("type") == "FreeformReportlet":
                    return r["freeformTable"]
        return None

    # ── Component resolution helpers ───────────────────────────────────────

    def _resolve_metric_pair(self, mid: str, mname: str) -> tuple:
        """Return a resolved ``(id, name)`` tuple for a standard or calculated metric."""
        if mid and mname:
            return mid, mname
        if mid:
            name = self._metric_id_name.get(mid) or self._calc_metric_id_name.get(mid, mid)
            return mid, name
        # name-only: search standard metrics first, then calculated
        for k, v in self._metric_id_name.items():
            if v.lower() == mname.lower():
                return k, mname
        for k, v in self._calc_metric_id_name.items():
            if v.lower() == mname.lower():
                return k, mname
        raise ValueError(
            f"Metric '{mname}' not found in report suite '{self.rsid}'. "
            "Check the name spelling or provide the metric ID directly."
        )

    def _resolve_dim_pair(self, did: str, dname: str) -> tuple:
        """Return a resolved ``(id, name)`` tuple for a dimension."""
        if did and dname:
            return did, dname
        if did:
            name = self._dim_id_name.get(did, did)
            return did, name
        # name-only
        for k, v in self._dim_id_name.items():
            if v.lower() == dname.lower():
                return k, dname
        raise ValueError(
            f"Dimension '{dname}' not found in report suite '{self.rsid}'. "
            "Check the name spelling or provide the dimension ID directly."
        )

    def _resolve_seg_pair(self, sid: str, sname: str) -> tuple:
        """Return a resolved ``(id, name)`` tuple for a segment."""
        if sid and sname:
            return sid, sname
        if not sid and not sname:
            raise ValueError("Either a segment ID or segment name must be provided.")
        if sid:
            name = self._segments_id_name.get(sid, sid)
            return sid, name
        # name-only
        for k, v in self._segments_id_name.items():
            if v.lower() == sname.lower():
                return k, sname
        raise ValueError(
            f"Segment '{sname}' not found. "
            "Check the name spelling or provide the segment ID directly."
        )

    def _normalize_metrics(self, metrics: List[dict]) -> List[dict]:
        """Ensure every metric dict has both ``id`` and ``name`` filled in."""
        result = []
        for m in metrics:
            mid, mname = self._resolve_metric_pair(m.get("id") or "", m.get("name") or "")
            result.append({**m, "id": mid, "name": mname})
        return result

    def _normalize_item(self, item_id: str, item_name: str) -> tuple:
        """Resolve a ``(id, name)`` pair for any component type."""
        if item_id and item_name:
            return item_id, item_name
        comp_type = _detect_component_type(item_id) if item_id else None
        if comp_type == "Dimension":
            return self._resolve_dim_pair(item_id, item_name)
        if comp_type == "DimensionItem":
            return item_id, (item_name or item_id.split("::")[-1])
        if comp_type == "Segment" and item_id:
            return self._resolve_seg_pair(item_id, item_name)
        # No ID — search dimensions first, then segments
        try:
            return self._resolve_dim_pair("", item_name)
        except ValueError:
            return self._resolve_seg_pair("", item_name)

    def _normalize_items(self, items: List[dict]) -> List[dict]:
        """Resolve missing ``id``/``name`` in every item dict."""
        result = []
        for it in items:
            iid, iname = self._normalize_item(it.get("id") or "", it.get("name") or "")
            result.append({**it, "id": iid, "name": iname})
        return result

    # ── Freeform / text / chart / KPI builders ──────────────────────────────

    def addTextFreeform(
        self,
        title: str,
        content: Union[str, "TextBuilder", dict],
        collapsed: bool = False,
        description: str = "",
    ) -> "WorkspaceManager":
        """
        Add a text freeform to the current panel.

        Arguments:
            title       : REQUIRED : Sub-panel title.
            content     : REQUIRED : Content as one of:

                * :class:`TextBuilder` instance  (recommended)
                * ``dict`` with ``"ops"`` key (raw Quill Delta)
                * JSON string (raw Quill Delta)
                * plain ``str`` (rendered as-is)

            collapsed   : OPTIONAL : Whether the sub-panel starts collapsed (default ``False``).
            description : OPTIONAL : Sub-panel description (default ``""``).
        """
        panel = self._current_panel()
        if isinstance(content, TextBuilder):
            text_content = content.to_json()
        elif isinstance(content, dict):
            text_content = json.dumps(content)
        elif isinstance(content, str):
            try:
                json.loads(content)
                text_content = content  # already valid Quill Delta JSON
            except json.JSONDecodeError:
                text_content = json.dumps({"ops": [{"insert": content + "\n"}]})
        else:
            text_content = json.dumps({"ops": [{"insert": str(content) + "\n"}]})

        _append_subpanel(panel, title, _text_reportlet(title, text_content),
                          auto_height=321, collapsed=collapsed, description=description)
        return self

    def addFreeform(
        self,
        title: str,
        item_id: str = None,
        item_name: str = "",
        items: List[Dict] = None,
        metrics: List[Dict] = None,
        rows: int = 10,
        collapsed: bool = False,
        description: str = "",
    ) -> "FreeForm":
        """
        Add a freeform table to the current panel and return it as a :class:`FreeForm`.

        Call :meth:`FreeForm.addBreakdown` on the returned object to nest a
        breakdown beneath the table — mutating the returned ``FreeForm``
        updates this project even though ``addFreeform`` has already
        "finished" adding it.

        Pass either a single ``item_id`` + ``item_name`` **or** a list of ``items``:

        * **Single item** (``item_id`` / ``item_name``) — type is inferred from the ID:

          * ``"variables/..."`` (no ``"::"``) → **Dimension** → dynamic top-*N* table.
          * ``"variables/...::hash"`` (with ``"::"``) → **DimensionItem** → single static row.
          * Anything else → **Segment** → single static row.

        * **List of items** (``items``) — each dict needs ``"id"`` and ``"name"``; an optional
          ``"type"`` key (``"Segment"`` or ``"DimensionItem"``) overrides auto-detection.
          Produces a static-rows table (``totalsType="columnSum"``).

        Arguments:
            title       : REQUIRED : Sub-panel title.
            item_id     : OPTIONAL : Single component ID.  One of ``item_id``, ``item_name``,
                          or ``items`` must be supplied.
            item_name   : OPTIONAL : Display label for ``item_id``.  When *analytics* is set,
                          passing only ``item_name`` (without ``item_id``) resolves the ID
                          automatically.
            items       : OPTIONAL : List of ``{"id": ..., "name": ..., "type"?: ...}`` dicts
                          to use as static rows.  When *analytics* is set, each dict may omit
                          ``"id"`` or ``"name"`` and the missing half is resolved automatically.
            metrics     : REQUIRED : List of metric dicts.  Each must have ``"id"`` and/or
                          ``"name"``.  When *analytics* is set, either key alone is sufficient
                          and the missing half is resolved automatically.
                          Supports ``"filters"`` — see :meth:`FreeForm._build_column_nodes`.
            rows        : OPTIONAL : Rows per page (default ``10``).
            collapsed   : OPTIONAL : Whether the sub-panel starts collapsed (default ``False``).
            description : OPTIONAL : Sub-panel description (default ``""``).

        Examples::

            # Dynamic dimension table — ID only, name resolved automatically
            ff = wc.addFreeform(
                "Visits by Market",
                item_id="variables/evar8",
                metrics=[{"id": "metrics/visits"}],
            )
            ff.addBreakdown(dimension_id="variables/evar3", dimension_name="Browser")

            # Segment rows, then two levels of nested breakdown
            ff2 = wc.addFreeform(
                "Device Comparison",
                items=[
                    {"id": "s4222_mobile",  "name": "Mobile"},
                    {"id": "s4222_desktop", "name": "Desktop"},
                ],
                metrics=[{"id": "metrics/occurrences", "name": "Occurrences"}],
            )
            level1 = ff2.addBreakdown(dimension_id="variables/evar8", dimension_name="Market Code")
            level1.addBreakdown(dimension_id="variables/evar3", dimension_name="Browser")

            # Single dimension item as a static row
            wc.addFreeform(
                "DE Market Only",
                item_id="variables/evar8::581609802",
                item_name="DE",
                metrics=[{"id": "metrics/visits", "name": "Visits"}],
            )
        """
        if not metrics:
            raise ValueError("At least one metric is required.")
        if not item_id and not item_name and items is None:
            raise ValueError("Either item_id, item_name, or items must be provided.")

        metrics = self._normalize_metrics(metrics)
        dim_id = dim_name = None
        resolved_items = None
        if items is not None:
            resolved_items = self._normalize_items(items)
        else:
            item_id, item_name = self._normalize_item(item_id or "", item_name or "")
            comp_type = _detect_component_type(item_id) if item_id else "Dimension"
            if comp_type == "Dimension":
                dim_id, dim_name = item_id, item_name
            else:
                resolved_items = [{"id": item_id, "name": item_name, "type": comp_type}]

        panel = self._current_panel()
        ff = FreeForm.build(title, metrics, dim_id=dim_id, dim_name=dim_name, items=resolved_items, rows=rows)
        sub = _append_subpanel(panel, title, ff.to_dict(), auto_height=528,
                                collapsed=collapsed, description=description)
        ff._sync = lambda: sub.__setitem__("reportlet", ff.to_dict())
        return ff

    def addActivityBreakdownFreeform(
        self,
        title: str,
        activity_dim_item_id: str,
        activity_name: str,
        breakdown_dim_id: str,
        breakdown_dim_name: str,
        metrics: List[Dict[str, str]],
        rows: int = 50,
        breakdown_rows: int = 5,
        collapsed: bool = False,
        description: str = "",
    ) -> "WorkspaceManager":
        """
        Add a freeform table that pins a specific dimension item as a static row
        and breaks it down by a secondary dimension.

        This is the standard pattern for Target activity reports: the activity is
        a static row (``DimensionItem``) and each experience is shown as a
        breakdown row underneath it.

        Arguments:
            title                : REQUIRED : Sub-panel title.
            activity_dim_item_id : REQUIRED : Dimension item ID for the static row.
                                   Use double-colon notation,
                                   e.g. ``'variables/targetraw.activity::179567382'``.
            activity_name        : REQUIRED : Display name for the activity item.
            breakdown_dim_id     : REQUIRED : Breakdown dimension ID,
                                   e.g. ``'variables/targetraw.experience'``.
            breakdown_dim_name   : REQUIRED : Breakdown dimension label.
            metrics              : REQUIRED : List of ``{"id": ..., "name": ...}`` dicts.
            rows                 : OPTIONAL : Rows for the static-row table (default ``50``).
            breakdown_rows       : OPTIONAL : Rows for the breakdown (default ``5``).
            collapsed            : OPTIONAL : Whether the sub-panel starts collapsed.
            description          : OPTIONAL : Sub-panel description.
        """
        if not metrics:
            raise ValueError("At least one metric is required.")
        if ':::' in activity_dim_item_id:
            activity_dim_item_id = activity_dim_item_id.replace(":::", "::")
        metrics = self._normalize_metrics(metrics)
        breakdown_dim_id, breakdown_dim_name = self._resolve_dim_pair(
            breakdown_dim_id or "", breakdown_dim_name or ""
        ) if self._analytics and (breakdown_dim_id or breakdown_dim_name) else (breakdown_dim_id, breakdown_dim_name)
        panel = self._current_panel()
        ff = FreeForm.build(
            title, metrics,
            items=[{"id": activity_dim_item_id, "name": activity_name, "type": "DimensionItem"}],
            rows=rows,
        )
        ff.addBreakdown(dimension_id=breakdown_dim_id, dimension_name=breakdown_dim_name, rows=breakdown_rows)
        _append_subpanel(panel, title, ff.to_dict(), auto_height=613,
                          collapsed=collapsed, description=description)
        return self

    def addSegmentAsDimensionFreeform(
        self,
        title: str,
        segments: List[Dict[str, str]],
        metrics: List[Dict[str, str]],
        breakdown_dim_id: str = None,
        breakdown_dim_name: str = "",
        breakdown_segments: List[Dict[str, str]] = None,
        breakdown_rows: int = 5,
        rows: int = 50,
        collapsed: bool = False,
        description: str = "",
    ) -> "WorkspaceManager":
        """
        Add a freeform table where **segments are used as rows** (no dimension).

        This is the "Segment as Dimension" Workspace pattern — each segment
        becomes a static row in the table, and the table reports metric values
        for each segment side-by-side.

        An optional breakdown can be applied beneath each segment row:

        * ``breakdown_dim_id`` / ``breakdown_dim_name`` — break each segment row
          down by a dimension (e.g. Market Code).  The breakdown table uses
          ``totalsType="allVisits"``.
        * ``breakdown_segments`` — break each segment row down by a second list
          of segments (nested segment rows).  The breakdown table also uses
          ``totalsType="columnSum"``.

        Only one breakdown type should be provided at a time.

        Arguments:
            title                : REQUIRED : Sub-panel title.
            segments             : REQUIRED : List of segment dicts, each with ``"id"`` and
                                   ``"name"``.  The order determines the row order.
            metrics              : REQUIRED : List of metric dicts.  Each must have ``"id"`` and
                                   ``"name"``.  The optional ``"filters"`` key is supported — see
                                   :meth:`FreeForm._build_column_nodes`.
            breakdown_dim_id     : OPTIONAL : Dimension ID to break each segment row down by
                                   (e.g. ``"variables/evar8"``).  Requires ``breakdown_dim_name``.
            breakdown_dim_name   : OPTIONAL : Display name for the breakdown dimension.
            breakdown_segments   : OPTIONAL : List of segment dicts (``"id"`` + ``"name"``) to
                                   use as nested segment rows in the breakdown.
            breakdown_rows       : OPTIONAL : Row count for the breakdown (default ``5``).
            rows                 : OPTIONAL : ``viewBy`` pagination size (default ``50``).
            collapsed            : OPTIONAL : Whether the sub-panel starts collapsed (default ``False``).
            description          : OPTIONAL : Sub-panel description (default ``""``).

        Examples::

            # Plain segment rows
            wc.addSegmentAsDimensionFreeform(
                "Device Comparison",
                segments=[
                    {"id": "s4222_mobile",  "name": "Mobile"},
                    {"id": "s4222_desktop", "name": "Desktop"},
                    {"id": "s4222_tablet",  "name": "Tablet"},
                ],
                metrics=[{"id": "metrics/occurrences", "name": "Occurrences"}],
            )

            # Segment rows broken down by a dimension
            wc.addSegmentAsDimensionFreeform(
                "Device × Market",
                segments=[{"id": "s4222_mobile", "name": "Mobile"}],
                metrics=[{"id": "metrics/visits", "name": "Visits"}],
                breakdown_dim_id="variables/evar8",
                breakdown_dim_name="Market Code",
            )

            # Segment rows broken down by further segments
            wc.addSegmentAsDimensionFreeform(
                "Device × Browser",
                segments=[{"id": "s4222_mobile", "name": "Mobile"}],
                metrics=[{"id": "metrics/visits", "name": "Visits"}],
                breakdown_segments=[
                    {"id": "s4222_chrome",  "name": "Chrome"},
                    {"id": "s4222_safari",  "name": "Safari"},
                ],
            )
        """
        if not segments:
            raise ValueError("At least one segment is required.")
        if not metrics:
            raise ValueError("At least one metric is required.")
        segments = self._normalize_items(segments)
        metrics = self._normalize_metrics(metrics)
        if self._analytics and (breakdown_dim_id or breakdown_dim_name):
            breakdown_dim_id, breakdown_dim_name = self._resolve_dim_pair(
                breakdown_dim_id or "", breakdown_dim_name or ""
            )
        if breakdown_segments is not None:
            breakdown_segments = self._normalize_items(breakdown_segments)

        panel = self._current_panel()
        ff = FreeForm.build(title, metrics, items=segments, rows=rows)
        has_breakdown = bool(breakdown_dim_id or breakdown_segments)
        if breakdown_dim_id:
            ff.addBreakdown(dimension_id=breakdown_dim_id, dimension_name=breakdown_dim_name, rows=breakdown_rows)
        elif breakdown_segments:
            ff.addBreakdown(items=breakdown_segments, rows=breakdown_rows)
        _append_subpanel(
            panel, title, ff.to_dict(),
            auto_height=290 if not has_breakdown else 512, collapsed=collapsed, description=description,
        )
        return self

    def addDropdownFilter(
        self,
        group_name: str,
        components: List[Dict],
        has_no_filter: bool = True,
    ) -> "WorkspaceManager":
        """
        Add a **dropdown filter group** to the current panel.

        Dropdown filter groups appear as switchable dropdowns at the top of the
        panel in the Workspace UI.  They let viewers filter all visualisations in
        the panel by a segment or a specific dimension-item value — and are the
        mechanism behind "segment comparison"-style panels.

        Multiple groups can be added by calling this method repeatedly.  Each
        group becomes its own independent dropdown.

        Arguments:
            group_name    : REQUIRED : Label shown for the dropdown (e.g. ``"Brand"``).
            components    : REQUIRED : List of filter-option dicts.  Each dict must
                            contain at least ``"id"`` and ``"name"``.  Optional keys:

                * ``"type"``     – ``"Segment"`` *(default)* or ``"DimensionItem"``.
                * ``"isActive"`` – ``True`` / ``False`` (first component is active by
                  default; at most one item should be ``True`` per group).

            has_no_filter : OPTIONAL : Whether a *"No filter"* option is available
                            (default ``True``).  Set to ``False`` to force one
                            component to always be active.

        Examples::

            # Compare two brands using a DimensionItem dropdown
            wc.addDropdownFilter(
                "Brand",
                components=[
                    {"id": "variables/evar1::1111111111", "type": "DimensionItem", "name": "brand_a",  "isActive": True},
                    {"id": "variables/evar1::2222222222", "type": "DimensionItem", "name": "brand_b"},
                ],
                has_no_filter=True,
            )

            # Compare two segments (no "No filter" option)
            wc.addDropdownFilter(
                "Audience",
                components=[
                    {"id": "s1234_aaa", "type": "Segment", "name": "New Visitors", "isActive": True},
                    {"id": "s1234_bbb", "type": "Segment", "name": "Returning Visitors"},
                ],
                has_no_filter=False,
            )
        """
        panel = self._current_panel()
        if panel.get("_opaque"):
            raise ValueError(
                "The current panel has an unrecognised structure and cannot be modified. "
                "Call addPanel() to create a new panel first."
            )
        components = self._normalize_items(components)
        component_options = []
        for i, comp in enumerate(components):
            comp_type = comp.get("type", "Segment")
            component_options.append({
                "component": {
                    "id": comp["id"],
                    "__entity__": True,
                    "type": comp_type,
                    "__metaData__": {"name": comp.get("name", "")},
                },
                "isActive": bool(comp.get("isActive", i == 0)),
            })
        group: dict = {
            "componentOptions": component_options,
            "groupName": group_name,
            "hasNoFilter": has_no_filter,
            "showGroupName": True,
        }
        panel["segmentGroups"].append(group)
        return self

    def addSummaryNumber(
        self,
        title: str,
        metric: str = None,
        show_change: bool = False,
        show_percent_change: bool = False,
        show_sparkline: bool = False,
        collapsed: bool = False,
        description: str = "",
    ) -> "WorkspaceManager":
        """
        Add a **Summary Number** (KPI card) visualization to the current panel.

        A Summary Number displays the grand-total value of a single metric.
        The Adobe API requires every ``SummaryNumberReportlet`` to be backed by a
        ``FreeformReportlet`` (linked via ``linkedSourceId``).  This method
        automatically creates that backing table — a day-grain freeform table
        containing the requested metric — immediately below the KPI card.

        Arguments:
            title               : REQUIRED : Sub-panel title.
            metric              : REQUIRED : Metric ID or Metric Name (e.g. ``"metrics/visits"``).
            show_change         : OPTIONAL : Reserved — not yet implemented for
                                  ``SummaryNumberReportlet`` (default ``False``).
            show_percent_change : OPTIONAL : Reserved — not yet implemented for
                                  ``SummaryNumberReportlet`` (default ``False``).
            show_sparkline      : OPTIONAL : Reserved — not yet implemented for
                                  ``SummaryNumberReportlet`` (default ``False``).
            collapsed           : OPTIONAL : Whether the KPI sub-panel starts collapsed
                                  (default ``False``).
            description         : OPTIONAL : KPI sub-panel description (default ``""``).

        Example::

            wc.addSummaryNumber("Total Visits", metric="metrics/visits")

            # With analytics= set, name-only is enough:
            wc.addSummaryNumber("Total Visits", metric="Visits")
        """
        if not metric:
            raise ValueError("metric name or metric ID must be provided.")
        if metric.startswith("metrics/"):
            metric_id = metric
            metric_name = self._metric_id_name.get(metric_id, metric_id)
        elif metric.startswith("cm"):
            metric_id = metric
            metric_name = self._calc_metric_id_name.get(metric_id, metric_id)
        else:
            if metric in self._metric_id_name.values():
                metric_id = [k for k, v in self._metric_id_name.items() if v == metric][0]
                metric_name = metric
            elif metric in self._calc_metric_id_name.values():
                metric_id = [k for k, v in self._calc_metric_id_name.items() if v == metric][0]
                metric_name = metric
            else:
                raise ValueError(f"Metric '{metric}' not found in analytics data.")
        panel = self._current_panel()
        if panel.get("_opaque"):
            raise ValueError(
                "The current panel has an unrecognised structure and cannot be modified. "
                "Call addPanel() to create a new panel first."
            )

        current_y = panel["_yOffset"]
        kpi_height = 200
        table_height = 300

        # ── backing freeform table (created first to capture its column id) ────
        backing_ff = FreeForm.build(f"{title} (data)", [{"id": metric_id, "name": metric_name}],
                                     dim_id="all_visits", dim_name="All Visits", rows=10)
        metric_column_id = backing_ff.columnTree["nodes"][0]["id"]

        # Pre-compute swatch indices before any append
        base_idx = len(panel["subPanels"])
        swatch_kpi   = _SWATCH_COLORS[base_idx % len(_SWATCH_COLORS)]
        swatch_table = _SWATCH_COLORS[(base_idx + 1) % len(_SWATCH_COLORS)]

        backing_sub = _sub_panel(
            name=f"{title} (data)",
            reportlet=backing_ff.to_dict(),
            y_position=current_y + kpi_height,
            auto_height=table_height,
            swatch_color=swatch_table,
            viz_index=panel["_vizIndex"] + 1,
        )
        backing_id = backing_sub["id"]

        # ── KPI card linked to the backing table ──────────────────────────────
        summary_sub = _sub_panel(
            name=title,
            reportlet=_summary_number_reportlet(title, metric_column_id),
            y_position=current_y,
            auto_height=kpi_height,
            swatch_color=swatch_kpi,
            viz_index=panel["_vizIndex"],
            collapsed=collapsed,
            description=description,
        )
        summary_sub["linkedSourceId"] = backing_id

        panel["subPanels"].append(summary_sub)
        panel["subPanels"].append(backing_sub)
        panel["_yOffset"] += kpi_height + table_height
        panel["_vizIndex"] += 2
        return self

    def addChart(
        self,
        viz_type: str,
        source: Union[str, int] = None,
        title: str = "",
        collapsed: bool = False,
        description: str = "",
    ) -> "WorkspaceManager":
        """
        Add a **chart visualization** to the current panel, linked to an existing
        freeform table.

        Chart visualizations (line, bar, donut, …) derive their data from a
        ``FreeformReportlet`` sub-panel via ``linkedSourceId``.

        Arguments:
            viz_type    : REQUIRED : Chart type shorthand.  Supported values:

                * ``"line"``
                * ``"bar"``
                * ``"bar_horizontal"``
                * ``"bar_stacked"``
                * ``"area"``
                * ``"area_stacked"``
                * ``"donut"``
                * ``"scatter"``
                * ``"treemap"``
                * ``"histogram"``
                * ``"bullet"``
                * ``"venn"``

            source      : OPTIONAL : The freeform table to link.

                * ``None`` *(default)* – links to the most recently added
                  ``FreeformReportlet`` in the current panel.
                * ``int`` – zero-based index of the sub-panel to link.
                * ``str`` – name of the sub-panel to link.

            title       : OPTIONAL : Sub-panel title (default ``""``).
            collapsed   : OPTIONAL : Whether the sub-panel starts collapsed
                          (default ``False``).
            description : OPTIONAL : Sub-panel description (default ``""``).

        Raises:
            ValueError : If ``viz_type`` is not a recognised shorthand.
            ValueError : If no matching source sub-panel can be found.

        Example::

            wc.addFreeform("Visits by Page", item_id="variables/page",
                            metrics=[{"id": "metrics/visits", "name": "Visits"}])
            wc.addChart("line", source="Visits by Page", title="Trend")
            wc.addChart("donut")   # links to the last freeform automatically
        """
        panel = self._current_panel()
        if panel.get("_opaque"):
            raise ValueError(
                "The current panel has an unrecognised structure and cannot be modified. "
                "Call addPanel() to create a new panel first."
            )

        reportlet_type = _VIZ_TYPE_MAP.get(viz_type.lower() if isinstance(viz_type, str) else "")
        if reportlet_type is None:
            raise ValueError(
                f"Unknown viz_type '{viz_type}'. Supported: {list(_VIZ_TYPE_MAP)}"
            )

        linked_id = ""
        if source is None:
            for sp in reversed(panel["subPanels"]):
                if sp.get("reportlet", {}).get("type") == "FreeformReportlet":
                    linked_id = sp["id"]
                    break
            if not linked_id:
                raise ValueError(
                    "No FreeformReportlet sub-panel found in the current panel to link to. "
                    "Add a freeform table first, or specify 'source' explicitly."
                )
        elif isinstance(source, int):
            if source < 0 or source >= len(panel["subPanels"]):
                raise IndexError(f"Sub-panel index {source} is out of range.")
            linked_id = panel["subPanels"][source]["id"]
        else:
            for sp in panel["subPanels"]:
                if sp.get("name") == source:
                    linked_id = sp["id"]
                    break
            if not linked_id:
                raise ValueError(f"No sub-panel named '{source}' found in the current panel.")

        reportlet = _chart_reportlet(reportlet_type, title)
        sub = _sub_panel(
            name=title,
            reportlet=reportlet,
            y_position=panel["_yOffset"],
            auto_height=300,
            swatch_color=_next_swatch(panel),
            viz_index=panel["_vizIndex"],
            collapsed=collapsed,
            description=description,
        )
        sub["linkedSourceId"] = linked_id
        panel["subPanels"].append(sub)
        panel["_yOffset"] += 300
        panel["_vizIndex"] += 1
        return self

    def addBreakdownToDimension(
        self,
        breakdown_dim_id: str = None,
        breakdown_dim_name: str = None,
        target: Union[str, int] = "all",
        breakdown_rows: int = 5,
    ) -> "WorkspaceManager":
        """
        Inject a breakdown dimension into the ``freeformTable.breakdowns`` of one
        or all existing ``FreeformReportlet`` sub-panels in the current panel.

        This lets you enrich freeforms created with :meth:`addFreeform` (or
        loaded from an existing definition) without having to rebuild them.

        Arguments:
            breakdown_dim_id   : OPTIONAL : Breakdown dimension ID.  Required when *analytics*
                                 is not set.
            breakdown_dim_name : OPTIONAL : Breakdown dimension label.  Required when *analytics*
                                 is not set.  When *analytics* is set, either key alone is
                                 sufficient and the missing half is resolved automatically.
            target             : OPTIONAL : Which sub-panel(s) to target.

                * ``"all"`` *(default)* – apply to every ``FreeformReportlet`` in
                  the current panel.
                * ``int`` – zero-based index of the sub-panel to target.
                * ``str`` (other than ``"all"``) – name of the sub-panel to target.

            breakdown_rows : OPTIONAL : Rows per page for the breakdown (default ``5``).
        """
        if not breakdown_dim_id and not breakdown_dim_name:
            raise ValueError("Either breakdown_dim_id or breakdown_dim_name must be provided.")
        breakdown_dim_id, breakdown_dim_name = self._resolve_dim_pair(
            breakdown_dim_id or "", breakdown_dim_name or ""
        ) if self._analytics else (breakdown_dim_id or "", breakdown_dim_name or "")
        panel = self._current_panel()
        freeform_subs = [
            sp for sp in panel["subPanels"]
            if sp.get("reportlet", {}).get("type") == "FreeformReportlet"
        ]
        if not freeform_subs:
            raise ValueError("No FreeformReportlet sub-panels found in the current panel.")

        if target == "all":
            candidates = freeform_subs
        elif isinstance(target, int):
            if target < 0 or target >= len(panel["subPanels"]):
                raise IndexError(f"Sub-panel index {target} is out of range.")
            sp = panel["subPanels"][target]
            if sp.get("reportlet", {}).get("type") != "FreeformReportlet":
                raise ValueError(f"Sub-panel at index {target} is not a FreeformReportlet.")
            candidates = [sp]
        else:  # str name
            candidates = [sp for sp in panel["subPanels"]
                          if sp.get("name") == target
                          and sp.get("reportlet", {}).get("type") == "FreeformReportlet"]
            if not candidates:
                raise ValueError(f"No FreeformReportlet named '{target}' found in the current panel.")

        for sp in candidates:
            ft = sp["reportlet"]["freeformTable"]
            static_rows = ft.get("staticRows") or []
            bd = FreeForm(title="")
            bd.dimension = {
                "id": breakdown_dim_id, "__entity__": True, "type": "Dimension",
                "__metaData__": {"name": breakdown_dim_name},
            }
            bd.parentItemId = static_rows[0]["id"] if static_rows else "0"
            bd.breakdownByPosition = False  # see FreeForm.addBreakdown
            bd._rows = breakdown_rows
            ft.setdefault("breakdowns", []).append(bd._to_breakdown_entry())
        return self

    # ── Project metadata ────────────────────────────────────────────────────

    def setOwner(self, owner: Union[int, dict]) -> "WorkspaceManager":
        """
        Set (or replace) the project owner. Fluent — returns ``self``.

        Arguments:
            owner : REQUIRED : Either an ``int`` IMS user ID or a ``dict``
                    with keys ``"id"``, ``"name"``, ``"login"``.
        """
        if isinstance(owner, int):
            self.owner = {"id": owner, "name": "", "login": ""}
        else:
            self.owner = dict(owner)
        return self

    def addTag(self, tag: Union[int, dict]) -> "WorkspaceManager":
        """
        Add a tag to the project. Fluent — returns ``self``.

        Duplicate tag IDs are silently ignored.

        Arguments:
            tag : REQUIRED : Either an ``int`` tag ID or a ``dict`` with at
                  minimum an ``"id"`` key, e.g. ``{"id": 42, "name": "prod"}``.
        """
        if isinstance(tag, int):
            tag_dict = {"id": tag}
        else:
            tag_dict = dict(tag)
        if not any(t.get("id") == tag_dict.get("id") for t in self.tags):
            self.tags.append(tag_dict)
        return self

    def addShare(self, share_to_id: int = None, share_to_type: str = "user",
                 share_to_display_name: str = None) -> "WorkspaceManager":
        """
        Share the project with a user, group, or all users. Fluent — returns ``self``.

        Arguments:
            share_to_id           : OPTIONAL : Numeric ID of the user or group to share
                                    with. Not required when ``share_to_type`` is ``"all"``.
            share_to_type         : OPTIONAL : ``"user"`` (default), ``"group"``, or
                                    ``"all"``.
            share_to_display_name : OPTIONAL : Display name (informational only).
        """
        share: dict = {"shareToType": share_to_type}
        if share_to_id is not None:
            share["shareToId"] = share_to_id
        if share_to_display_name is not None:
            share["shareToDisplayName"] = share_to_display_name
        self.shares.append(share)
        return self

    # ── Serialisation ───────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        """
        Return the full project definition as a ``dict`` ready to be passed
        to the Adobe Analytics API (e.g. ``createProject``).
        """
        clean_panels = []
        for p in self._panels:
            if p.get("_opaque"):
                clean_panels.append(deepcopy(p["_raw"]))
                continue
            cp = deepcopy(p)
            cp.pop("_yOffset", None)
            cp.pop("_vizIndex", None)
            cp["position"]["autoHeight"] = sum(
                sp.get("position", {}).get("autoHeight", 0) for sp in cp["subPanels"]
            )
            clean_panels.append(cp)

        if self._definition_meta is not None:
            definition = deepcopy(self._definition_meta)
            workspaces = definition.get("workspaces", [{}])
            if workspaces:
                workspaces[0]["panels"] = clean_panels
            else:
                definition["workspaces"] = [{"id": self.id,
                                              "name": self.name,
                                              "panels": clean_panels}]
        else:
            definition = {
                "additionalCuratedComponents": [],
                "colorScheme": {"id": "default", "label": "", "value": self.DEFAULT_COLOR_SCHEME},
                "countRepeatInstances": True,
                "currentWorkspaceIndex": 0,
                "customColorSchemes": [],
                "hideCommentRail": False,
                "internalAnnotations": [],
                "intrinsicPublicAccessLinkComponents": [],
                "isCurated": False,
                "showAnnotations": True,
                "version": self.version or "98",
                "viewDensity": "expanded",
                "workspaces": [{"id": self.id,
                                "name": self.name,
                                "panels": clean_panels}],
            }

        result = {
            "name": self.name,
            "description": self.description,
            "rsid": self.rsid,
            "type": "project",
            "definition": definition,
        }
        # Only surface "id" when the loaded data actually had one (self._has_real_id) — every
        # add_* builder tool round-trips through `data=`, including chains started from
        # create_workspace, which never had a real id and would otherwise carry the
        # placeholder self.id (see __init__) into a createProject POST body, which Adobe
        # rejects outright ("Cannot create a project that already has an id").
        if self._has_real_id:
            result["id"] = self.id
        if self.owner is not None:
            result["owner"] = self.owner
        if self.tags:
            result["tags"] = list(self.tags)
        if self.shares:
            result["shares"] = list(self.shares)
        return result

    def createProject(self) -> dict:
        """
        Create a new project in Adobe Analytics using the current definition.
        """
        if self._definition_meta is not None:
            raise ValueError("This WorkspaceManager was initialized with an existing project definition and cannot create a new project. Use to_dict() to get the modified definition instead.")
        response = self._analytics.createProject(self.to_dict())
        self.id = response.get("id")
        return response

    def updateProject(self) -> dict:
        """
        Update an existing project in Adobe Analytics with the current definition.

        The project ID must be set (e.g. by initializing with an existing definition
        or by calling createProject()).

        Returns the API response as a dict.
        """
        if self.id is None:
            raise ValueError("Project ID is not set. Initialize with an existing project definition or call createProject() first.")
        response = self._analytics.updateProject(self.id, self.to_dict())
        return response
