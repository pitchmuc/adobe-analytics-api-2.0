# Workspace Creator

Adobe Analytics Analysis Workspace projects are complex JSON structures that can be tedious to build by hand.\
The `workspaceCreator` module provides two classes — `WorkspaceCreator` and `TextBuilder` — that let you compose Workspace projects programmatically and obtain an API-ready definition dictionary.

The official Workspace Projects API documentation is available here: <https://developer.adobe.com/analytics-apis/docs/2.0/guides/endpoints/projects/>


## Overview of a Workspace Project

A Workspace project is organised as follows:

```
Project
 └─ definition
     └─ workspaces[]
         └─ panels[]
             ├─ segmentGroups   ← global segment filters
             └─ subPanels[]     ← individual visualisations (freeforms, text…)
```

Each sub-panel contains a **reportlet**, which can be:

- `TextReportlet` – rich text
- `FreeformReportlet` – table with dimensions and metrics
- `SummaryNumberReportlet` – single KPI metric card
- `LineReportlet`, `BarReportlet`, `DonutReportlet`, etc. – chart visualizations linked to a freeform table


## Importing the module

`WorkspaceCreator` and `TextBuilder` are exported directly from the `aanalytics2` package:

```py
import aanalytics2 as api2
from aanalytics2 import workspaceCreator

wc = workspaceCreator.WorkspaceCreator(rsid="myrsid", name="My Project")
tb = workspaceCreator.TextBuilder()
```

They can also be imported individually:

```py
from aanalytics2.workspaceCreator import WorkspaceCreator, TextBuilder
```

`WorkspaceCreator` supports two usage modes:

1. **Build from scratch** – supply `rsid` and `name`, then chain `addPanel` and freeform methods.
2. **Edit an existing project** – pass the project definition via the `data` parameter.
   Existing panels and all their metadata (colors, IDs, date ranges, etc.) are preserved; you can then add new panels or extend existing ones.


---

## TextBuilder

`TextBuilder` is a fluent helper for composing rich-text content in **Quill Delta** format, which is the format used by Adobe Analytics `TextReportlet` sub-panels.

### Instantiation

```py
tb = TextBuilder()
```

No arguments are required.  All methods return `self`, so calls can be chained:

```py
tb = (
    TextBuilder()
    .addTitle("My Title")
    .addText("\nSome explanation.\n")
    .addBold("Important note")
    .addNewline()
    .addColor("danger", "var(--spectrum-red-800)")
    .addNewline()
)
```

### TextBuilder Methods

#### addTitle
Add a heading line.\
Arguments:
* text  : REQUIRED : Heading text.
* level : OPTIONAL : Heading level (1–6). Default is `2`.

#### addText
Add plain (unstyled) text.\
Arguments:
* text : REQUIRED : Text string to insert.

#### addBold
Add **bold** text.\
Arguments:
* text : REQUIRED : Text to render in bold.

#### addItalic
Add *italic* text.\
Arguments:
* text : REQUIRED : Text to render in italic.

#### addUnderline
Add underlined text.\
Arguments:
* text : REQUIRED : Text to render with underline.

#### addColor
Add colored text using a CSS color value or an Adobe Spectrum variable.\
Arguments:
* text  : REQUIRED : Text to colorize.
* color : REQUIRED : CSS color or Spectrum variable string, for example:
  * `"var(--spectrum-red-800)"`
  * `"var(--spectrum-celery-500)"`
  * `"var(--spectrum-blue-800)"`
  * Any valid CSS hex or named color.

#### addLink
Add a clickable hyperlink.\
Arguments:
* text : REQUIRED : Display label for the link.
* url  : REQUIRED : Target URL.

#### addNewline
Insert a newline character (`\n`). No arguments.

#### to_json
Serialise the content to a Quill Delta **JSON string** (used internally by `WorkspaceCreator`).\
Returns:
* `str` : The Quill Delta JSON string.

#### to_dict
Return the Quill Delta as a Python **dictionary**.\
Returns:
* `dict` : The Quill Delta structure with an `"ops"` key.


---

## WorkspaceCreator

`WorkspaceCreator` is the main class for composing a complete Workspace project.\
All `add*` methods return `self`, enabling a fluent chaining style.

### Instantiation

```py
# Build a new project from scratch
wc = WorkspaceCreator(
    rsid="myrsid",
    name="My Project",
    description="Optional description",
    rsid_name="My Report Suite",
)

# Load and edit an existing project (dict from the API, JSON file, or raw JSON string)
wc = WorkspaceCreator(data=existing_project_dict)

# Load and override the name
wc = WorkspaceCreator(data=existing_project_dict, name="Renamed Project")
```

Arguments:
* rsid        : OPTIONAL : Report suite ID (e.g. `"mycompany.global.all"`). Required when `data` is not provided.
* name        : OPTIONAL : Display name for the project. Required when `data` is not provided.
* description : OPTIONAL : Project description. Default is `""`.
* rsid_name   : OPTIONAL : Human-readable label for the report suite. Defaults to the value of `rsid`.
* data        : OPTIONAL : An existing project to load. Accepted values:
  * `dict` – project definition as returned by the API (e.g. from `getProject`).
  * `str` ending in `.json` – path to a JSON file.
  * raw JSON `str`.

  When `rsid`, `name`, `description`, or `rsid_name` are also given alongside `data`, they override the corresponding values read from the definition.
* owner       : OPTIONAL : Project owner. Accepted values:
  * `int` – IMS user numeric ID (e.g. `200225987`); name and login will be blank.
  * `dict` – full owner object, e.g. `{"id": 200225987, "name": "Admin User", "login": "admin@example.com"}`.

  When loading from `data`, the owner embedded in the definition is preserved unless `owner` is explicitly provided here.
* tags        : OPTIONAL : Tags to attach to the project at creation time. Each item can be:
  * `int` – tag ID, e.g. `[42, 99]`.
  * `dict` – full tag object, e.g. `[{"id": 42, "name": "prod"}]`.

  When loading from `data`, existing tags from the definition are preserved and these are appended.
* shares      : OPTIONAL : Share objects. Each dict requires `"shareToType"` (`"user"`, `"group"`, or `"all"`) and, for user/group, `"shareToId"` (int). Example: `[{"shareToId": 622291, "shareToType": "user"}]`.


### WorkspaceCreator Methods

#### addPanel
Add a new **panel** to the workspace. All subsequent `addTextFreeform`, `addSimpleFreeform`, and `addBreakdownFreeform` calls target the most recently added panel.\
Arguments:
* name            : REQUIRED : Panel title shown at the top of the panel.
* date_range_id   : OPTIONAL : Date-range preset ID. Default is `"thisMonth"`. Other common values: `"thisWeek"`, `"last30Days"`, `"last90Days"`.
* date_range_name : OPTIONAL : Human-readable label for the date range. Default is `"This month"`.
* position        : OPTIONAL : Zero-based index at which to insert the panel among existing panels. Defaults to appending at the end.
* collapsed       : OPTIONAL : Whether the panel starts collapsed. Default is `False`.
* description     : OPTIONAL : Panel description. Default is `""`.

```py
wc.addPanel("Overview", date_range_id="thisMonth")

# Insert as the first panel (position 0)
wc.addPanel("New First Panel", position=0, collapsed=True, description="Added later")
```

#### addSegmentFilter
Add a global **segment filter** to the current panel. Multiple segments can be added by calling this method repeatedly.\
Arguments:
* segment_id   : REQUIRED : Segment ID (e.g. `"s1234_abc123…"`).
* segment_name : OPTIONAL : Display name for the segment.

```py
wc.addSegmentFilter("s1234_abc123def456abc123de", "My Segment")
```

#### addDropdownFilter
Add a **dropdown filter group** to the current panel.

Dropdown filter groups appear as switchable dropdowns at the top of the panel, letting the viewer filter all visualizations in the panel by a segment or a specific dimension-item value.  Multiple calls add independent dropdowns side by side.  This is how "segment comparison"-style panels are built in Workspace.\
Arguments:
* group_name    : REQUIRED : Label shown for the dropdown (e.g. `"Brand"`).
* components    : REQUIRED : List of filter-option dicts.  Each entry requires `"id"` and `"name"`.  Optional keys per entry:
  * `"type"` – `"Segment"` *(default)* or `"DimensionItem"`.
  * `"isActive"` – `True`/`False`. The first component is pre-selected by default.
* has_no_filter : OPTIONAL : Whether a *"No filter"* option is available. Default is `True`.

```py
# Compare two brands with a DimensionItem dropdown
wc.addDropdownFilter(
    "Brand",
    components=[
        {"id": "variables/evar1::1111111111", "type": "DimensionItem", "name": "brand_a", "isActive": True},
        {"id": "variables/evar1::2222222222", "type": "DimensionItem", "name": "brand_b"},
    ],
)

# Compare two segments without a "No filter" option
wc.addDropdownFilter(
    "Audience",
    components=[
        {"id": "s1234_aaa", "type": "Segment", "name": "New Visitors", "isActive": True},
        {"id": "s1234_bbb", "type": "Segment", "name": "Returning Visitors"},
    ],
    has_no_filter=False,
)
```

#### addTextFreeform
Add a **rich-text sub-panel** to the current panel.\
Arguments:
* title       : REQUIRED : Sub-panel title.
* content     : REQUIRED : Content to display. Accepted types:
  * `TextBuilder` instance *(recommended)*
  * `dict` with an `"ops"` key (raw Quill Delta)
  * JSON string (raw Quill Delta)
  * Plain `str` (rendered as-is, no formatting)
* collapsed   : OPTIONAL : Whether the sub-panel starts collapsed. Default is `False`.
* description : OPTIONAL : Sub-panel description. Default is `""`.

```py
tb = (
    TextBuilder()
    .addTitle("Introduction")
    .addText("\nThis workspace shows Target performance.\n")
    .addBold("Key metric: Visits")
    .addNewline()
    .addColor("Warning: ", "var(--spectrum-red-800)")
    .addText("data updated daily.")
    .addNewline()
)

wc.addTextFreeform("Introduction", tb)
```

#### addSimpleFreeform
Add a **freeform table** with a single dimension and one or more metrics.\
Arguments:
* title          : REQUIRED : Sub-panel title.
* dimension_id   : REQUIRED : Dimension ID (e.g. `"variables/evar1"`, `"variables/targetraw.experience"`).
* dimension_name : REQUIRED : Human-readable dimension label.
* metrics        : REQUIRED : List of metric dictionaries, each with `"id"` and `"name"` keys.
* rows           : OPTIONAL : Number of rows per page. Default is `10`.
* collapsed      : OPTIONAL : Whether the sub-panel starts collapsed. Default is `False`.
* description    : OPTIONAL : Sub-panel description. Default is `""`.

```py
wc.addSimpleFreeform(
    "Visits by Experience",
    dimension_id="variables/targetraw.experience",
    dimension_name="Target Experiences",
    metrics=[
        {"id": "metrics/visits",  "name": "Visits"},
        {"id": "metrics/orders",  "name": "Orders"},
    ],
)
```

#### addBreakdownFreeform
Add a **freeform table with a breakdown**: a primary dimension whose rows are each broken down by a secondary dimension.\
Arguments:
* title               : REQUIRED : Sub-panel title.
* dimension_id        : REQUIRED : Primary dimension ID.
* dimension_name      : REQUIRED : Primary dimension label.
* breakdown_dim_id    : REQUIRED : Breakdown (secondary) dimension ID.
* breakdown_dim_name  : REQUIRED : Breakdown dimension label.
* metrics             : REQUIRED : List of metric dictionaries, each with `"id"` and `"name"` keys.
* rows                : OPTIONAL : Rows per page for the primary dimension. Default is `10`.
* breakdown_rows      : OPTIONAL : Rows per page for the breakdown dimension. Default is `5`.
* collapsed           : OPTIONAL : Whether the sub-panel starts collapsed. Default is `False`.
* description         : OPTIONAL : Sub-panel description. Default is `""`.

```py
wc.addBreakdownFreeform(
    "Activity × Experience",
    dimension_id="variables/targetraw.activity",
    dimension_name="Target Activities",
    breakdown_dim_id="variables/targetraw.experience",
    breakdown_dim_name="Target Experiences",
    metrics=[
        {"id": "metrics/visits",      "name": "Visits"},
        {"id": "metrics/occurrences", "name": "Occurrences"},
    ],
)
```

#### addSummaryNumber
Add a **Summary Number** (KPI card) visualization to the current panel — a large card showing the grand-total of a single metric.

> **Note:** The Adobe Analytics API requires every `SummaryNumberReportlet` to be backed by a `FreeformReportlet`.
> `addSummaryNumber` automatically creates that backing table (a day-grain freeform table containing the metric)
> and positions it directly below the KPI card.  Both subpanels are visible in the Workspace UI.

Arguments:
* title               : REQUIRED : Sub-panel title.
* metric_id           : REQUIRED : Metric ID (e.g. `"metrics/visits"`).
* metric_name         : REQUIRED : Human-readable metric label.
* show_change         : OPTIONAL : Reserved for future support — has no effect on `SummaryNumberReportlet`. Default is `False`.
* show_percent_change : OPTIONAL : Reserved for future support — has no effect on `SummaryNumberReportlet`. Default is `False`.
* show_sparkline      : OPTIONAL : Reserved for future support — has no effect on `SummaryNumberReportlet`. Default is `False`.
* collapsed           : OPTIONAL : Whether the KPI sub-panel starts collapsed. Default is `False`.
* description         : OPTIONAL : KPI sub-panel description. Default is `""`.

```py
wc.addSummaryNumber(
    "Total Visits",
    metric_id="metrics/visits",
    metric_name="Visits",
)
```

#### addChart
Add a **chart visualization** to the current panel, linked to an existing freeform table.\
Arguments:
* viz_type    : REQUIRED : Chart type shorthand. Supported values:
  * `"line"`, `"bar"`, `"bar_horizontal"`, `"bar_stacked"`
  * `"area"`, `"area_stacked"`
  * `"donut"`, `"scatter"`, `"treemap"`, `"histogram"`
  * `"bullet"`, `"venn"`
* source      : OPTIONAL : Which freeform table to link. Default is `None` (links to the most recently added `FreeformReportlet`).
  * `None` – last `FreeformReportlet` in the current panel.
  * `int` – zero-based index of the sub-panel.
  * `str` – name of the sub-panel.
* title       : OPTIONAL : Sub-panel title. Default is `""`.
* collapsed   : OPTIONAL : Whether the sub-panel starts collapsed. Default is `False`.
* description : OPTIONAL : Sub-panel description. Default is `""`.

```py
wc.addSimpleFreeform("Visits by Page",
                     dimension_id="variables/page", dimension_name="Page",
                     metrics=[{"id": "metrics/visits", "name": "Visits"}])

# Link by name
wc.addChart("line", source="Visits by Page", title="Visits Trend")

# Link automatically to the last freeform
wc.addChart("donut")

# Link by index
wc.addChart("bar_horizontal", source=0)
```

#### addBreakdownToDimension
Inject a **breakdown dimension** into the `freeformTable.breakdowns` of one or all existing `FreeformReportlet` sub-panels in the current panel.
This is useful when you want to add a breakdown to freeforms that were created with `addSimpleFreeform` or loaded from an existing project definition, without rebuilding them.\
Arguments:
* breakdown_dim_id   : REQUIRED : Breakdown dimension ID.
* breakdown_dim_name : REQUIRED : Breakdown dimension label.
* target             : OPTIONAL : Which sub-panel(s) to target. Default is `"all"`.
  * `"all"` – apply to every `FreeformReportlet` in the current panel.
  * `int` – zero-based index of the sub-panel to target.
  * `str` (other than `"all"`) – name of the sub-panel to target.
* breakdown_rows : OPTIONAL : Rows per page for the breakdown. Default is `5`.

```py
# Add a breakdown to ALL freeform tables in the current panel
wc.addBreakdownToDimension("variables/evar3", "Campaign", target="all")

# Add a breakdown only to the sub-panel named "Visits by Experience"
wc.addBreakdownToDimension("variables/evar3", "Campaign", target="Visits by Experience")

# Add a breakdown to the sub-panel at index 1
wc.addBreakdownToDimension("variables/evar3", "Campaign", target=1)
```

#### setOwner
Set (or replace) the project **owner** after construction. Fluent — returns `self`.\
Arguments:
* owner : REQUIRED : Either an `int` IMS user ID or a `dict` with keys `"id"`, `"name"`, `"login"`.

```py
wc.setOwner({"id": 200225987, "name": "Admin User", "login": "admin@example.com"})

# Or with just an ID
wc.setOwner(200225987)
```

#### addTag
Add a **tag** to the project. Duplicate tag IDs are silently ignored. Fluent — returns `self`.\
Arguments:
* tag : REQUIRED : Either an `int` tag ID or a `dict` with at minimum an `"id"` key.

```py
wc.addTag(42)                          # by ID only
wc.addTag({"id": 99, "name": "prod"}) # with display name
```

#### addShare
**Share** the project with a user, group, or all users. Fluent — returns `self`.\
Arguments:
* share_to_id           : OPTIONAL : Numeric ID of the user or group. Not required when `share_to_type` is `"all"`.
* share_to_type         : OPTIONAL : `"user"` *(default)*, `"group"`, or `"all"`.
* share_to_display_name : OPTIONAL : Informational display name stored alongside the share object.

```py
wc.addShare(622291, "user", "Jane Doe")   # share with a specific user
wc.addShare(8880, "group")                # share with a product-profile group
wc.addShare(share_to_type="all")          # share with everyone in the org
```

#### to_dict
Return the complete project definition as a Python **dictionary** ready to be passed to the Adobe Analytics API (e.g. `createProject`).\
Returns:
* `dict` : Full project payload including `name`, `rsid`, `type`, `definition`, and optionally `owner`, `tags`, `shares`.

```py
project_definition = wc.to_dict()
```


---

## Complete Example

The following example demonstrates all available methods — it builds a project from scratch with a text freeform, KPI cards, a simple freeform with a linked chart, a breakdown table, and a segment-comparison dropdown:

```py
import aanalytics2 as api2
from aanalytics2.workspaceCreator import WorkspaceCreator, TextBuilder

# 1. Build the rich-text intro content
tb = (
    TextBuilder()
    .addTitle("Overview")
    .addNewline()
    .addText("This workspace shows Target A/B test performance.\n")
    .addBold("Key metric: ")
    .addText("Visits and Orders.\n")
    .addColor("Note: ", "var(--spectrum-red-800)")
    .addText("data is updated daily.")
    .addNewline()
)

# 2. Compose the project
wc = (
    WorkspaceCreator(
        rsid="mycompany.global.all",
        name="Example Workspace",
        rsid_name="My Company Global",
    )
    # ── Panel 1: Overview ──────────────────────────────────────────────────
    .addPanel("Example Workspace", date_range_id="thisMonth")

    # Global segment filter applied to every visualization in this panel
    .addSegmentFilter("s1234_abc123def456abc123de", "Global Segment")

    # Switchable brand dropdown (segment comparison style)
    .addDropdownFilter(
        "Brand",
        components=[
            {"id": "variables/evar1::1111111111", "type": "DimensionItem", "name": "brand_a", "isActive": True},
            {"id": "variables/evar1::2222222222", "type": "DimensionItem", "name": "brand_b"},
        ],
    )

    # Rich-text introduction
    .addTextFreeform("Introduction", tb)

    # KPI cards (each automatically creates a linked backing freeform table)
    .addSummaryNumber(
        "Total Visits",
        metric_id="metrics/visits",
        metric_name="Visits",
    )
    .addSummaryNumber(
        "Total Orders",
        metric_id="metrics/orders",
        metric_name="Orders",
    )

    # Simple freeform table + linked line chart
    .addSimpleFreeform(
        "Visits by Experience",
        dimension_id="variables/targetraw.experience",
        dimension_name="Target Experiences",
        metrics=[
            {"id": "metrics/visits", "name": "Visits"},
            {"id": "metrics/orders", "name": "Orders"},
        ],
    )
    .addChart("line", source="Visits by Experience", title="Visits Trend")
    .addChart("donut")   # links automatically to the last freeform

    # Breakdown freeform table
    .addBreakdownFreeform(
        "Activity × Experience",
        dimension_id="variables/targetraw.activity",
        dimension_name="Target Activities",
        breakdown_dim_id="variables/targetraw.experience",
        breakdown_dim_name="Target Experiences",
        metrics=[
            {"id": "metrics/visits",      "name": "Visits"},
            {"id": "metrics/occurrences", "name": "Occurrences"},
        ],
    )

    # ── Panel 2: Segment Comparison ────────────────────────────────────────
    .addPanel("Segment Comparison", date_range_id="last30Days", date_range_name="Last 30 days")
    .addDropdownFilter(
        "Audience",
        components=[
            {"id": "s1234_aaa", "type": "Segment", "name": "New Visitors",       "isActive": True},
            {"id": "s1234_bbb", "type": "Segment", "name": "Returning Visitors"},
        ],
        has_no_filter=False,
    )
    .addSimpleFreeform(
        "Visits by Page",
        dimension_id="variables/page",
        dimension_name="Page",
        metrics=[{"id": "metrics/visits", "name": "Visits"}],
    )
    # Add a breakdown to all freeforms in this panel
    .addBreakdownToDimension("variables/evar3", "Campaign", target="all")
    .addChart("bar", title="Visits by Page – Bar")
)

# 3. Get the definition and create the project via the API
project_def = wc.to_dict()

# Connect to your Analytics instance (see getting_started.md)
api2.importConfigFile("config_analytics.json")
myAnalytics = api2.Analytics()
response = myAnalytics.createProject(projectDict=project_def)
print(response)
```

