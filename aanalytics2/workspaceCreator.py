import json
import uuid
from copy import deepcopy
from typing import Union, List, Dict


# ── Internal helpers ──────────────────────────────────────────────────────────

def _upper_uuid() -> str:
    return str(uuid.uuid4()).upper()


def _lower_uuid() -> str:
    return str(uuid.uuid4())


def _short_hex_id() -> str:
    return uuid.uuid4().hex[:6]


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


def _metric_node(metric_id: str, metric_name: str) -> dict:
    """Build a single metric node for columnTree.nodes."""
    if metric_id.startswith("cm"):
        component_type = "CalculatedMetric"
    else:
        component_type = "Metric"
    return {
        "_computedValues": [],
        "component": {
            "id": metric_id,
            "__entity__": True,
            "type": component_type,
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


def _column_tree(metric_nodes: List[dict]) -> dict:
    """Build the columnTree wrapper around a list of metric nodes."""
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


def _dimension_setting(dim_id: str, dim_name: str) -> dict:
    return {
        "dimension": {
            "id": dim_id,
            "__entity__": True,
            "type": "Dimension",
            "__metaData__": {"name": dim_name},
        },
        "id": f"{_short_hex_id()}-1",
        "search": _default_search(),
    }


def _freeform_table(
    dim_id: str,
    dim_name: str,
    first_metric_node_id: str,
    breakdowns: List[dict] = None,
    n_columns: int = 3,
    view_by: int = 10,
    parent_item_ids: List[str] = None,
) -> dict:
    """Build the freeformTable object."""
    column_widths = [100 / n_columns] * n_columns
    return {
        "alignDatesForTimeDimension": True,
        "attributionSettings": [],
        "breakdowns": breakdowns or [],
        "collapsed": False,
        "columnWidths": column_widths,
        "dimensionSettings": [_dimension_setting(dim_id, dim_name)],
        "hyperlinks": [],
        "pagination": {"currentPage": 0, "viewBy": view_by},
        "parentItemIds": parent_item_ids or [],
        "selectionCoordinates": [],
        "settings": {
            "breakdownByPosition": False,
            "rowBasedPercentages": False,
            "showThumbnails": False,
            "totalsType": "allVisits",
        },
        "sort": {
            "advancedSortRules": [],
            "asc": False,
            "columnId": first_metric_node_id,
            "labelColumn": False,
        },
        "staticRows": [],
        "staticSearch": _default_search(),
        "statistics": {"functions": [], "ignoreZeros": True},
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


def _freeform_reportlet(title: str, column_tree: dict, freeform_table: dict) -> dict:
    return {
        "advancedMode": False,
        "advancedSettings": {"rows": [], "tableState": "builder"},
        "columnTree": column_tree,
        "freeformTable": freeform_table,
        "hideTitle": False,
        "intelligentCaptions": _intelligent_captions(),
        "isConfigVisible": True,
        "isReadOnly": False,
        "name": title,
        "showAnnotations": True,
        "showControls": True,
        "type": "FreeformReportlet",
    }


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


def _summary_number_reportlet(title: str, column_id: str) -> dict:
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
            "selectedDataPoints": [{"columnId": column_id, "rowPosition": -1}],
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


def _static_row_item(dim_item_id: str, dim_item_name: str) -> tuple:
    """Build a static row component and return (row_dict, row_id)."""
    row_id = f"{_short_hex_id()}-4c"
    return {
        "component": {
            "id": dim_item_id,
            "__entity__": True,
            "type": "DimensionItem",
            "__metaData__": {"name": dim_item_name},
        },
        "dataSettings": _default_data_settings(),
        "id": row_id,
    }, row_id


def _static_row_freeform_table(
    static_row: dict,
    static_row_id: str,
    breakdown_dim_id: str,
    breakdown_dim_name: str,
    first_metric_node_id: str,
    n_columns: int = 3,
    view_by: int = 50,
    breakdown_rows: int = 5,
) -> dict:
    """Build a freeform table that uses a DimensionItem static row broken down by a second dimension."""
    breakdown_ft = _freeform_table(
        breakdown_dim_id,
        breakdown_dim_name,
        first_metric_node_id=first_metric_node_id,
        n_columns=1,
        view_by=breakdown_rows,
        parent_item_ids=[static_row_id],
    )
    column_widths = [100 / n_columns] * n_columns
    return {
        "alignDatesForTimeDimension": True,
        "attributionSettings": [],
        "breakdowns": [breakdown_ft],
        "collapsed": False,
        "columnWidths": column_widths,
        "dimensionSettings": [],
        "hyperlinks": [],
        "pagination": {"currentPage": 0, "viewBy": view_by},
        "parentItemIds": [],
        "selectionCoordinates": [],
        "settings": {
            "breakdownByPosition": False,
            "rowBasedPercentages": False,
            "showThumbnails": False,
            "totalsType": "columnSum",
        },
        "sort": {
            "advancedSortRules": [],
            "asc": False,
            "columnId": first_metric_node_id,
            "labelColumn": False,
        },
        "staticRows": [static_row],
        "staticSearch": _default_search(),
        "statistics": {"functions": [], "ignoreZeros": True},
    }


def _chart_reportlet(reportlet_type: str, title: str) -> dict:
    return {
        "hideTitle": False,
        "name": title,
        "showAnnotations": True,
        "showControls": True,
        "type": reportlet_type,
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


class WorkspaceCreator:
    """
    Programmatically compose Adobe Analytics Workspace projects.

    Supports three kinds of sub-panels (freeforms):

    * **Text freeform** – rich formatted text via :class:`TextBuilder`.
    * **Simple freeform table** – one dimension and any number of metrics.
    * **Breakdown freeform table** – a primary dimension broken down by a
      secondary dimension, with any number of metrics.

    Typical usage::

        wc = (
            WorkspaceCreator("myrsid", "My Project", rsid_name="My Report Suite")
            .addPanel("Overview", date_range_id="thisMonth")
            .addSegmentFilter("s1234_abc", "My Segment")
            .addTextFreeform(
                "Introduction",
                TextBuilder().addTitle("Hello").addText("\\nSome description.\\n"),
            )
            .addSimpleFreeform(
                "Visits by Experience",
                dimension_id="variables/targetraw.experience",
                dimension_name="Target Experiences",
                metrics=[
                    {"id": "metrics/visits", "name": "Visits"},
                    {"id": "metrics/orders", "name": "Orders"},
                ],
            )
            .addBreakdownFreeform(
                "Activity × Experience",
                dimension_id="variables/targetraw.activity",
                dimension_name="Target Activities",
                breakdown_dim_id="variables/targetraw.experience",
                breakdown_dim_name="Target Experiences",
                metrics=[
                    {"id": "metrics/visits", "name": "Visits"},
                    {"id": "metrics/occurrences", "name": "Occurrences"},
                ],
            )
        )
        project_dict = wc.to_dict()
    """

    DEFAULT_COLOR_SCHEME = [
        "#26C0C7", "#5151D3", "#E68619", "#D83790", "#908DFA", "#58E06F",
        "#2780EB", "#6F38B1", "#DFBF03", "#CB6F10", "#268D6C", "#9BEC54",
        "#5EABFA", "#BE40CC", "#F56BB7", "#FEE02D",
    ]

    def __init__(
        self,
        rsid: str = None,
        name: str = None,
        description: str = "",
        rsid_name: str = "",
        data: Union[str, dict] = None,
        owner: Union[int, dict] = None,
        tags: List[Union[int, dict]] = None,
        shares: List[dict] = None,
    ) -> None:
        """
        Arguments:
            rsid        : OPTIONAL : Report suite ID. Required when not loading from ``data``.
            name        : OPTIONAL : Workspace project name. Required when not loading from ``data``.
            description : OPTIONAL : Project description.
            rsid_name   : OPTIONAL : Human-readable report suite label.
            data        : OPTIONAL : Existing project definition to load from. Can be:

                * ``dict`` – a project definition as returned by the API.
                * ``str`` ending in ``.json`` – path to a JSON file.
                * raw JSON ``str``.

                When provided, ``rsid``, ``name``, ``description``, and ``rsid_name``
                override the values found in the definition when explicitly supplied.
            owner       : OPTIONAL : Project owner. Accepted values:

                * ``int`` – IMS user ID (e.g. ``200225987``); name and login left blank.
                * ``dict`` – full owner object with any of the keys ``"id"``,
                  ``"name"``, ``"login"``.

                When loading from ``data``, the owner found in the definition is
                preserved unless ``owner`` is explicitly provided here.
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
        """
        self._panels: List[dict] = []
        self._current_panel_index: int = -1
        self._workspace_id: str = _upper_uuid()
        self._workspace_name: str = ""
        self._definition_meta: dict = None
        self._owner: dict = None
        self._tags: List[dict] = []
        self._shares: List[dict] = []

        # Normalise the owner argument
        if owner is not None:
            if isinstance(owner, int):
                self._owner = {"id": owner, "name": "", "login": ""}
            else:
                self._owner = dict(owner)

        # Normalise tags
        if tags:
            for t in tags:
                if isinstance(t, int):
                    self._tags.append({"id": t})
                else:
                    self._tags.append(dict(t))

        # Normalise shares
        if shares:
            for s in shares:
                self._shares.append(dict(s))

        if data is not None:
            if isinstance(data, str):
                if data.strip().endswith('.json'):
                    with open(data, 'r') as f:
                        data = json.load(f)
                else:
                    data = json.loads(data)
            data = deepcopy(data)
            self._rsid = rsid or data.get("rsid", "")
            self._name = name or data.get("name", "")
            self._description = description or data.get("description", "")
            self._rsid_name = rsid_name or data.get("reportSuiteName", self._rsid)
            if self._owner is None and data.get("owner"):
                self._owner = dict(data["owner"])
            # Preserve tags/shares from loaded project; constructor-supplied ones extend them
            for t in data.get("tags", []):
                if not any(existing.get("id") == t.get("id") for existing in self._tags):
                    self._tags.append(dict(t))
            for s in data.get("shares", []):
                self._shares.append(dict(s))
            defn = data.get("definition", {})
            workspaces = defn.get("workspaces", [{}])
            ws0 = workspaces[0] if workspaces else {}
            self._workspace_id = ws0.get("id", _upper_uuid())
            self._workspace_name = ws0.get("name", "")
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
        else:
            if not rsid:
                raise ValueError("rsid is required when not loading from data.")
            if not name:
                raise ValueError("name is required when not loading from data.")
            self._rsid = rsid
            self._name = name
            self._description = description
            self._rsid_name = rsid_name or rsid

    # ── Panel management ───────────────────────────────────────────────────

    def addPanel(
        self,
        name: str,
        date_range_id: str = "thisMonth",
        date_range_name: str = "This month",
        position: int = None,
        collapsed: bool = False,
        description: str = "",
    ) -> "WorkspaceCreator":
        """
        Add a new panel to the workspace.  All subsequent ``add*`` calls
        target the most recently added panel.

        Arguments:
            name            : REQUIRED : Panel title.
            date_range_id   : OPTIONAL : Date-range preset ID (default: ``"thisMonth"``) **or** a
                              custom ISO 8601 interval string such as
                              ``"2026-04-22T00:00:00/2026-05-07T23:59:59"``.
                              When the value contains ``"/"`` it is treated as a custom interval
                              and placed in ``__metaData__.definition`` instead of ``id``.
            date_range_name : OPTIONAL : Human-readable label for the date range.
            position        : OPTIONAL : Zero-based index at which to insert the panel.
                              Defaults to appending at the end.
            collapsed       : OPTIONAL : Whether the panel is collapsed (default ``False``).
            description     : OPTIONAL : Panel description (default ``""``).
        """
        # Custom date ranges (ISO 8601 intervals like "2026-04-22T00:00:00/2026-05-07T23:59:59")
        # must be expressed via __metaData__.definition rather than an id, because the API
        # tries to resolve an id as a stored resource and returns 404.
        if "/" in date_range_id:
            date_range_obj = {
                "__entity__": True,
                "type": "DateRange",
                "__metaData__": {"definition": date_range_id},
            }
        else:
            date_range_obj = {
                "id": date_range_id,
                "__entity__": True,
                "type": "DateRange",
                "__metaData__": {"name": date_range_name},
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
                "id": self._rsid,
                "__entity__": True,
                "type": "ReportSuite",
                "__metaData__": {"name": self._rsid_name, "rsid": self._rsid},
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
        self, segment_id: str, segment_name: str = ""
    ) -> "WorkspaceCreator":
        """
        Add a segment (global filter) to the current panel.

        Arguments:
            segment_id   : REQUIRED : Segment ID.
            segment_name : OPTIONAL : Display name for the segment.
        """
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

    # ── Sub-panel helpers ──────────────────────────────────────────────────

    def _next_swatch(self, panel: dict) -> str:
        if panel.get("_opaque"):
            raise ValueError(
                "The current panel has an unrecognised structure and cannot be modified. "
                "Call addPanel() to create a new panel first."
            )
        return _SWATCH_COLORS[len(panel["subPanels"]) % len(_SWATCH_COLORS)]

    def _append_subpanel(self, panel: dict, name: str, reportlet: dict, auto_height: int,
                         collapsed: bool = False, description: str = "") -> None:
        sub = _sub_panel(
            name=name,
            reportlet=reportlet,
            y_position=panel["_yOffset"],
            auto_height=auto_height,
            swatch_color=self._next_swatch(panel),
            viz_index=panel["_vizIndex"],
            collapsed=collapsed,
            description=description,
        )
        panel["subPanels"].append(sub)
        panel["_yOffset"] += auto_height
        panel["_vizIndex"] += 1

    # ── Public add* methods ────────────────────────────────────────────────

    def addTextFreeform(
        self,
        title: str,
        content: Union[str, "TextBuilder", dict],
        collapsed: bool = False,
        description: str = "",
    ) -> "WorkspaceCreator":
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

        self._append_subpanel(panel, title, _text_reportlet(title, text_content),
                              auto_height=321, collapsed=collapsed, description=description)
        return self

    def addSimpleFreeform(
        self,
        title: str,
        dimension_id: str,
        dimension_name: str,
        metrics: List[Dict[str, str]],
        rows: int = 10,
        collapsed: bool = False,
        description: str = "",
    ) -> "WorkspaceCreator":
        """
        Add a freeform table with a single dimension and one or more metrics.

        Arguments:
            title          : REQUIRED : Sub-panel title.
            dimension_id   : REQUIRED : Dimension ID (e.g. ``"variables/evar1"``).
            dimension_name : REQUIRED : Human-readable dimension label.
            metrics        : REQUIRED : List of ``{"id": ..., "name": ...}`` dicts.
            rows           : OPTIONAL : Rows per page (default ``10``).
            collapsed      : OPTIONAL : Whether the sub-panel starts collapsed (default ``False``).
            description    : OPTIONAL : Sub-panel description (default ``""``).
        """
        if not metrics:
            raise ValueError("At least one metric is required.")
        panel = self._current_panel()
        metric_nodes = [_metric_node(m["id"], m["name"]) for m in metrics]
        col_tree = _column_tree(metric_nodes)
        ft = _freeform_table(
            dimension_id,
            dimension_name,
            first_metric_node_id=metric_nodes[0]["id"],
            n_columns=len(metrics) + 1,
            view_by=rows,
        )
        self._append_subpanel(
            panel, title, _freeform_reportlet(title, col_tree, ft),
            auto_height=528, collapsed=collapsed, description=description,
        )
        return self

    def addBreakdownFreeform(
        self,
        title: str,
        dimension_id: str,
        dimension_name: str,
        breakdown_dim_id: str,
        breakdown_dim_name: str,
        metrics: List[Dict[str, str]],
        rows: int = 10,
        breakdown_rows: int = 5,
        collapsed: bool = False,
        description: str = "",
    ) -> "WorkspaceCreator":
        """
        Add a freeform table where a primary dimension is broken down by a
        secondary dimension.

        Arguments:
            title               : REQUIRED : Sub-panel title.
            dimension_id        : REQUIRED : Primary dimension ID.
            dimension_name      : REQUIRED : Primary dimension label.
            breakdown_dim_id    : REQUIRED : Breakdown dimension ID.
            breakdown_dim_name  : REQUIRED : Breakdown dimension label.
            metrics             : REQUIRED : List of ``{"id": ..., "name": ...}`` dicts.
            rows                : OPTIONAL : Rows per page for the primary dimension (default ``10``).
            breakdown_rows      : OPTIONAL : Rows per page for the breakdown (default ``5``).
            collapsed           : OPTIONAL : Whether the sub-panel starts collapsed (default ``False``).
            description         : OPTIONAL : Sub-panel description (default ``""``).
        """
        if not metrics:
            raise ValueError("At least one metric is required.")
        panel = self._current_panel()
        metric_nodes = [_metric_node(m["id"], m["name"]) for m in metrics]
        col_tree = _column_tree(metric_nodes)
        first_metric_id = metric_nodes[0]["id"]

        breakdown_ft = _freeform_table(
            breakdown_dim_id,
            breakdown_dim_name,
            first_metric_node_id=first_metric_id,
            n_columns=1,
            view_by=breakdown_rows,
            parent_item_ids=[],
        )
        main_ft = _freeform_table(
            dimension_id,
            dimension_name,
            first_metric_node_id=first_metric_id,
            breakdowns=[breakdown_ft],
            n_columns=len(metrics) + 1,
            view_by=rows,
        )
        self._append_subpanel(
            panel, title, _freeform_reportlet(title, col_tree, main_ft),
            auto_height=613, collapsed=collapsed, description=description,
        )
        return self

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
    ) -> "WorkspaceCreator":
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
        panel = self._current_panel()
        metric_nodes = [_metric_node(m["id"], m["name"]) for m in metrics]
        col_tree = _column_tree(metric_nodes)
        first_metric_id = metric_nodes[0]["id"]
        static_row, static_row_id = _static_row_item(activity_dim_item_id, activity_name)
        ft = _static_row_freeform_table(
            static_row=static_row,
            static_row_id=static_row_id,
            breakdown_dim_id=breakdown_dim_id,
            breakdown_dim_name=breakdown_dim_name,
            first_metric_node_id=first_metric_id,
            n_columns=len(metrics) + 1,
            view_by=rows,
            breakdown_rows=breakdown_rows,
        )
        self._append_subpanel(
            panel, title, _freeform_reportlet(title, col_tree, ft),
            auto_height=613, collapsed=collapsed, description=description,
        )
        return self

    def addDropdownFilter(
        self,
        group_name: str,
        components: List[Dict],
        has_no_filter: bool = True,
    ) -> "WorkspaceCreator":
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
        metric_id: str,
        metric_name: str,
        show_change: bool = False,
        show_percent_change: bool = False,
        show_sparkline: bool = False,
        collapsed: bool = False,
        description: str = "",
    ) -> "WorkspaceCreator":
        """
        Add a **Summary Number** (KPI card) visualization to the current panel.

        A Summary Number displays the grand-total value of a single metric.
        The Adobe API requires every ``SummaryNumberReportlet`` to be backed by a
        ``FreeformReportlet`` (linked via ``linkedSourceId``).  This method
        automatically creates that backing table — a day-grain freeform table
        containing the requested metric — immediately below the KPI card.

        Arguments:
            title               : REQUIRED : Sub-panel title.
            metric_id           : REQUIRED : Metric ID (e.g. ``"metrics/visits"``).
            metric_name         : REQUIRED : Human-readable metric label.
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

            wc.addSummaryNumber(
                "Total Visits",
                metric_id="metrics/visits",
                metric_name="Visits",
            )
        """
        panel = self._current_panel()
        if panel.get("_opaque"):
            raise ValueError(
                "The current panel has an unrecognised structure and cannot be modified. "
                "Call addPanel() to create a new panel first."
            )

        current_y = panel["_yOffset"]
        kpi_height = 200
        table_height = 300

        # ── backing freeform table (created first to capture its ID) ──────────
        metric_node = _metric_node(metric_id, metric_name)
        col_tree = _column_tree([metric_node])
        backing_reportlet = _freeform_reportlet(
            title=f"{title} (data)",
            column_tree=col_tree,
            freeform_table=_freeform_table(
                dim_id="daterangeday",
                dim_name="Day",
                first_metric_node_id=metric_node["id"],
                n_columns=2,
            ),
        )
        # Pre-compute swatch indices before any append
        base_idx = len(panel["subPanels"])
        swatch_kpi   = _SWATCH_COLORS[base_idx % len(_SWATCH_COLORS)]
        swatch_table = _SWATCH_COLORS[(base_idx + 1) % len(_SWATCH_COLORS)]

        backing_sub = _sub_panel(
            name=f"{title} (data)",
            reportlet=backing_reportlet,
            y_position=current_y + kpi_height,
            auto_height=table_height,
            swatch_color=swatch_table,
            viz_index=panel["_vizIndex"] + 1,
        )
        backing_id = backing_sub["id"]

        # ── KPI card linked to the backing table ──────────────────────────────
        summary_sub = _sub_panel(
            name=title,
            reportlet=_summary_number_reportlet(title, metric_node["id"]),
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
    ) -> "WorkspaceCreator":
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

            wc.addSimpleFreeform("Visits by Page", dimension_id="variables/page",
                                 dimension_name="Page", metrics=[{"id": "metrics/visits", "name": "Visits"}])
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
            swatch_color=self._next_swatch(panel),
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
        breakdown_dim_id: str,
        breakdown_dim_name: str,
        target: Union[str, int] = "all",
        breakdown_rows: int = 5,
    ) -> "WorkspaceCreator":
        """
        Inject a breakdown dimension into the ``freeformTable.breakdowns`` of one
        or all existing ``FreeformReportlet`` sub-panels in the current panel.

        This lets you enrich freeforms created with :meth:`addSimpleFreeform` (or
        loaded from an existing definition) without having to rebuild them.

        Arguments:
            breakdown_dim_id   : REQUIRED : Breakdown dimension ID.
            breakdown_dim_name : REQUIRED : Breakdown dimension label.
            target             : OPTIONAL : Which sub-panel(s) to target.

                * ``"all"`` *(default)* – apply to every ``FreeformReportlet`` in
                  the current panel.
                * ``int`` – zero-based index of the sub-panel to target.
                * ``str`` (other than ``"all"``) – name of the sub-panel to target.

            breakdown_rows : OPTIONAL : Rows per page for the breakdown (default ``5``).
        """
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
            # derive first_metric_node_id from the existing columnTree
            nodes = sp["reportlet"]["columnTree"].get("nodes", [])
            first_metric_id = nodes[0]["id"] if nodes else "0"
            bd = _freeform_table(
                breakdown_dim_id,
                breakdown_dim_name,
                first_metric_node_id=first_metric_id,
                n_columns=1,
                view_by=breakdown_rows,
                parent_item_ids=[],
            )
            ft["breakdowns"].append(bd)
        return self

    # ── Project metadata ───────────────────────────────────────────────────

    def setOwner(self, owner: Union[int, dict]) -> "WorkspaceCreator":
        """
        Set (or replace) the project owner. Fluent — returns ``self``.

        Arguments:
            owner : REQUIRED : Either an ``int`` IMS user ID or a ``dict``
                    with keys ``"id"``, ``"name"``, ``"login"``.
        """
        if isinstance(owner, int):
            self._owner = {"id": owner, "name": "", "login": ""}
        else:
            self._owner = dict(owner)
        return self

    def addTag(self, tag: Union[int, dict]) -> "WorkspaceCreator":
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
        if not any(t.get("id") == tag_dict.get("id") for t in self._tags):
            self._tags.append(tag_dict)
        return self

    def addShare(self, share_to_id: int = None, share_to_type: str = "user",
                 share_to_display_name: str = None) -> "WorkspaceCreator":
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
        self._shares.append(share)
        return self

    # ── Serialisation ──────────────────────────────────────────────────────

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
                definition["workspaces"] = [{"id": self._workspace_id,
                                              "name": self._workspace_name,
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
                "version": "98",
                "viewDensity": "expanded",
                "workspaces": [{"id": self._workspace_id,
                                "name": self._workspace_name,
                                "panels": clean_panels}],
            }

        result = {
            "name": self._name,
            "description": self._description,
            "rsid": self._rsid,
            "type": "project",
            "definition": definition,
        }
        if self._owner is not None:
            result["owner"] = self._owner
        if self._tags:
            result["tags"] = list(self._tags)
        if self._shares:
            result["shares"] = list(self._shares)
        return result

    def __str__(self) -> str:
        return json.dumps(self.to_dict(), indent=4)

    def __repr__(self) -> str:
        return json.dumps(self.to_dict(), indent=2)
