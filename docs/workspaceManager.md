# Workspace Manager

Adobe Analytics Analysis Workspace projects are complex JSON structures that can be tedious to build by hand.\
The `workspaceManager` module provides four classes — `WorkspaceManager`, `TextBuilder`, `FreeForm`, and `Panel` — that let you compose Workspace projects programmatically, obtain an API-ready definition dictionary, and parse existing projects (including ones downloaded outside of this library) into a readable object tree.

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

When you *read* a project (see [Parsing an Existing Project](#parsing-an-existing-project)), each `panels[]` entry is exposed as a `Panel` of type `"SubPanel"` holding nested `elements`, and each `subPanels[]` entry becomes a `Panel` of type:
* `"FreeForm"`, 
* `"Text"`,
* `"Visualization"` — matching the four categories above.


## Importing the module

`WorkspaceManager`, `TextBuilder`, `FreeForm`, and `Panel` are exported directly from the `aanalytics2` package:

```py
import aanalytics2 as api2
from aanalytics2 import workspaceManager

wc = workspaceManager.WorkspaceManager(rsid="myrsid", name="My Project")
tb = workspaceManager.TextBuilder()
```

They can also be imported individually:

```py
from aanalytics2.workspaceManager import WorkspaceManager, TextBuilder, FreeForm, Panel
```

`WorkspaceManager` supports two usage modes:

1. **Build from scratch** – supply `rsid` and `name`, then chain `addPanel` and freeform methods.
2. **Read or edit an existing project** – pass the project definition via the `data` parameter.
   Existing panels and all their metadata (colors, IDs, date ranges, etc.) are preserved; you can then inspect the parsed tree via `.panels` (see below) or add new panels/extend existing ones. Loading from `data` works entirely **offline** — no `analytics`/`config` is required, since every component reference in an exported project already carries its display name.


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
Serialise the content to a Quill Delta **JSON string** (used internally by `WorkspaceManager`).\
Returns:
* `str` : The Quill Delta JSON string.

#### to_dict
Return the Quill Delta as a Python **dictionary**.\
Returns:
* `dict` : The Quill Delta structure with an `"ops"` key.


---

## WorkspaceManager

`WorkspaceManager` is the main class for composing a complete Workspace project.\
All `add*` methods return `self`, enabling a fluent chaining style.

### Instantiation

```py
# Build a new project from scratch (requires analytics, or config + companyId)
wc = WorkspaceManager(
    rsid="myrsid",
    name="My Project",
    description="Optional description",
    analytics=my_an,
)

# Read/edit an existing project — dict from the API, JSON file path, or raw JSON string.
# No credentials required: parsing never needs a live lookup.
wc = WorkspaceManager(data="Workspaces/601d463a5e4798774c5f9ec2.json")

# Load and override the name
wc = WorkspaceManager(data=existing_project_dict, name="Renamed Project")
```

Arguments:
* rsid        : OPTIONAL : Report suite ID (e.g. `"mycompany.global.all"`). Required when `data` is not provided.
* name        : OPTIONAL : Display name for the project. Required when `data` is not provided.
* description : OPTIONAL : Project description. Default is `""`.
* data        : OPTIONAL : An existing project to load. Accepted values:
  * `dict` – project definition as returned by the API (e.g. from `getProject`).
  * `str` ending in `.json` – path to a JSON file.
  * raw JSON `str`.

  When `rsid`, `name`, or `description` are also given alongside `data`, they override the corresponding values read from the definition. See [Parsing an Existing Project](#parsing-an-existing-project) for what becomes available once loaded (`.panels`, `.dimensions`, `.metrics`, `.version`, `.owner`, …).
* tags        : OPTIONAL : Tags to attach to the project at creation time. Each item can be:
  * `int` – tag ID, e.g. `[42, 99]`.
  * `dict` – full tag object, e.g. `[{"id": 42, "name": "prod"}]`.

  When loading from `data`, existing tags from the definition are preserved and these are appended.
* shares      : OPTIONAL : Share objects. Each dict requires `"shareToType"` (`"user"`, `"group"`, or `"all"`) and, for user/group, `"shareToId"` (int). Example: `[{"shareToId": 622291, "shareToType": "user"}]`.
* analytics   : OPTIONAL : An `Analytics` instance (from `aanalytics2`) used to **auto-resolve** component names from IDs (and vice-versa) when *building*. When provided, every `add*` method accepts a component `id` **or** `name` alone — the missing half is looked up automatically via `getMetrics`, `getCalculatedMetrics`, `getDimensions`, or `getSegments`. Lookups are cached, so each API is called at most once per session. Required (or `config`+`companyId`) only when `data` is **not** supplied; optional otherwise.
* config      : OPTIONAL : Configuration object from `importConfigFile`/`configure(..., return_object=True)`. Requires `companyId` alongside it. Alternative to `analytics`.
* companyId   : OPTIONAL : Company ID to pair with `config`.

```py
# Building from scratch without analytics — both id and name are required everywhere
wc = WorkspaceManager(rsid="myrsid", name="My Project", config=my_config, companyId="myCompany")

# With analytics — id or name alone is sufficient for any component
import aanalytics2 as api2
cg = api2.Login()       # or however you authenticate
my_an = cg.createAnalyticsConnection("myrsid")
wc = WorkspaceManager(rsid="myrsid", name="My Project", analytics=my_an)

# Reading an existing project needs neither — parsing is always offline
wc = WorkspaceManager(data="Workspaces/601d463a5e4798774c5f9ec2.json")
```


---

## Parsing an Existing Project

Loading a project via `data=` (a `.json` file path, a JSON string, or a `dict`) parses it into a tree of `Panel` objects, with `FreeForm` objects for every table — entirely offline, since every component reference in an export already embeds its display name in `__metaData__.name`. This has been validated against a corpus of 2,171 real downloaded projects.

### Provenance attributes

Once loaded, these are available directly on the `WorkspaceManager` — useful for tagging extracted data with who/when/which-schema-version, e.g. when indexing many projects into a knowledge graph:

* `wc.version`  : Workspace schema version (`definition.version`, e.g. `"27"`). Different versions can encode the same table differently (see `FreeForm` below) — this lets you explain or group parsing differences.
* `wc.created`  / `wc.modified` : ISO-8601 timestamps from the project root.
* `wc.owner`    : `{"id", "name", "login"}` of the project's actual owner, as recorded in the export (not the credentials used to load it).

These are project-level only — individual panels/tables don't carry their own timestamps or authorship in the Workspace schema, so every `Panel`/`FreeForm` you visit is one hop away from this provenance via the `wc` object it came from.

### `wc.panels` — the panel tree

```py
wc = WorkspaceManager(data="Workspaces/601d463a5e4798774c5f9ec2.json")
for panel in wc.panels:
    print(panel.name, panel.type, panel.position)
    for element in panel.elements:
        print(" ", element.type, element.name)
```

`wc.panels` is a list of `Panel` objects, recomputed fresh on every access (so panels added via `add*` show up too). Each `Panel` has:

* `id`, `name`, `description`, `collapsed`
* `type` : one of `"SubPanel"`, `"FreeForm"`, `"Text"`, `"Visualization"`.
* `position` : raw `{"x", "y", "width", "autoHeight", "autoSize"}` dict.
* `elements` : nested `Panel` children — populated when `type == "SubPanel"` (every top-level entry in `wc.panels` is a `"SubPanel"` container; its `elements` are the actual visualizations).
* `freeform` : a `FreeForm` instance — populated when `type == "FreeForm"`.
* `text` / `textOps` : plain-text join / raw Quill Delta ops — populated when `type == "Text"`.
* `chartType` / `linkedSourceId` : raw reportlet type (e.g. `"LineReportlet"`, `"Flow"`, `"MapReportlet"`) and the sibling sub-panel it draws data from — populated when `type == "Visualization"` (every chart, KPI card, and exotic visualization type buckets into this one category).
* `dimensions`, `metrics`, `calculatedMetrics`, `segments`, `dateRanges` : de-duplicated lists of the components actually present in *this* element — see below. Present on every `Panel` regardless of `type` (empty for `"Text"`).
* `dateRange` / `segmentGroups` : populated only at the `"SubPanel"` level.
* `raw` : the original source dict — always present, so nothing is ever lost even for content not explicitly modeled above.

### Component lists on every element

Every `Panel` — container or leaf — exposes the same five attributes, so you never need to branch on `type` before asking "what does this element use":

```py
for panel in wc.panels:
    print(panel.name, panel.dimensions, panel.metrics, panel.segments)  # union of everything below it
    for element in panel.elements:
        print(" ", element.type, element.dimensions, element.metrics, element.segments, element.dateRanges)
```

What populates them depends on `type`:

* **`"FreeForm"`** : everything used in the table, *including* nested breakdowns (recurses through `element.freeform.breakdowns` for you — no manual walk needed).
* **`"Visualization"`** : charts and KPI cards carry no data of their own — they reference a sibling `FreeformReportlet` via `linkedSourceId` and pick specific columns/rows from it via `lockedSelection`. This is resolved automatically once every sibling in the panel has been parsed: `columnId` is cross-referenced into the linked table's `columnTree`, `rowItem`/`rowPosition` identify a specific row, and the linked table's own dynamic `dimension` (if any) is always included. A handful of older/undocumented reportlet shapes (e.g. `sourceCoords`-only `SummaryNumberReportlet`s, or charts with only `disabledLegends`) don't carry a resolvable reference and are left empty rather than guessed — validated at ~94% resolution coverage across the 2,171-file corpus.
* **`"SubPanel"`** (including every top-level entry in `wc.panels`) : the union of everything used by its `elements`.
* **`"Text"`** : always empty.

### `FreeForm` — reading a table

```py
for panel in wc.panels:
    for element in panel.elements:
        if element.type == "FreeForm":
            ff = element.freeform
            print(ff.metrics, ff.calculatedMetrics, ff.dimensions, ff.segments, ff.dateRanges)
```

Parsing a `FreeformReportlet` handles every row-encoding shape observed across the 2,171-file corpus (`dimensionSettings`/`dimension`/`dimensions` for a dynamic row dimension, `staticRows` for pinned rows, `advancedSettings.rows` for tables authored in "advanced" mode) and recurses into nested breakdowns and column filters. A parsed `FreeForm` exposes:

* `metrics` / `calculatedMetrics` : standard vs. calculated metric columns, as `{"id", "name"}` dicts.
* `dimensions` : `Dimension`/`DimensionItem` components referenced anywhere in the table (row dimension, static rows, or column filters).
* `segments` : `Segment` components referenced anywhere (column-splitting filters or static rows).
* `dateRanges` : `DateRange` components referenced anywhere (period-comparison columns, or date ranges used as static rows).
* `dimension` : the dynamic row dimension, or `None` if the table uses static rows.
* `staticRows` : the explicit static row entries.
* `breakdowns` : nested breakdown levels, as child `FreeForm` instances — mirrors Workspace's own `breakdowns[].breakdowns[]` nesting (observed up to 13 levels deep in real projects). `element.dimensions`/`.metrics`/etc. above already recurse through these for you; walk `breakdowns` directly only if you need per-level detail.
* `columnTree` / `raw` : escape hatches to the underlying dict for anything not modeled above.

### Project-wide aggregates

For building a knowledge graph (or any cross-panel analysis), these de-duplicate every component referenced *anywhere* in the project — across all panels, elements, and nested breakdowns — complementing the per-element attributes above, which answer "which panel/table uses this component":

```py
wc.dimensions          # every Dimension/DimensionItem used anywhere, de-duplicated by id
wc.metrics             # every standard Metric used anywhere
wc.calculatedMetrics   # every CalculatedMetric used anywhere
wc.segments            # every Segment used anywhere
wc.dateRanges          # every DateRange used anywhere
```

> **Note:** Calculated metrics and segments are always reference-only in the exported JSON (`{"id", "name"}`) — there is no `formula`/rule definition embedded. To resolve the actual logic, join the `id` against `getCalculatedMetric`/`getSegment`.


---

## Metric Filters (column-level filtering)

Any method that accepts a `metrics` list (`addFreeform`, `addActivityBreakdownFreeform`, `addSegmentAsDimensionFreeform`) supports **per-metric column filters** via an optional `"filters"` key on each metric dict.

Filters allow you to scope a metric to a specific **dimension item value** or a **segment** — directly at the column level, without adding a global panel filter.  You can stack multiple filter items per metric and mix both types.

### Filter dict structure

Each filter object inside `"filters"` must have:

| Key      | Required | Description |
|----------|----------|-------------|
| `"id"`   | yes      | Component ID (dimension item ID or segment ID). |
| `"name"` | yes      | Display label shown in the column header. |
| `"type"` | no       | `"DimensionItem"` or `"Segment"`. Defaults to `"Segment"`. |

### Filtering rules

| Filter combination | Result |
|--------------------|--------|
| No filters | Plain metric column — identical to the existing behaviour. |
| Segment filters only | One metric column whose sub-columns are the individual segments. |
| DimensionItem filters only | One column per dimension item, each containing the metric. |
| Both DimensionItem and Segment filters | One column per dimension item; each contains the metric with the segment(s) as sub-columns. |

### Examples

```py
# 1. Plain metric — no change to existing usage
{"id": "metrics/visitors", "name": "Unique Visitors"}

# 2. Metric scoped to one dimension item value
#    → produces a single "DE" column containing Visits
{"id": "metrics/visits", "name": "Visits",
 "filters": [
     {"id": "variables/evar8::581609802", "type": "DimensionItem", "name": "DE"}
 ]}

# 3. Metric split by multiple dimension items → one column per country code
{"id": "metrics/visits", "name": "Visits",
 "filters": [
     {"id": "variables/evar8::DE_id", "type": "DimensionItem", "name": "DE"},
     {"id": "variables/evar8::UK_id", "type": "DimensionItem", "name": "UK"},
     {"id": "variables/evar8::FR_id", "type": "DimensionItem", "name": "FR"},
 ]}

# 4. Metric split by segments (Mobile / Desktop / Tablet)
#    → one "Visits" column with three device sub-columns
{"id": "metrics/visits", "name": "Visits",
 "filters": [
     {"id": "s4222_aaa", "type": "Segment", "name": "Mobile"},
     {"id": "s4222_bbb", "type": "Segment", "name": "Desktop"},
     {"id": "s4222_ccc", "type": "Segment", "name": "Tablet"},
 ]}

# 5. Metric filtered by two dimension items, each split by a segment
#    → "DE" column (Mobile sub-column) + "UK" column (Mobile sub-column)
{"id": "metrics/visits", "name": "Visits",
 "filters": [
     {"id": "variables/evar8::DE_id", "type": "DimensionItem", "name": "DE"},
     {"id": "variables/evar8::UK_id", "type": "DimensionItem", "name": "UK"},
     {"id": "s4222_mobile",           "type": "Segment",       "name": "Mobile"},
 ]}
```

You can combine plain and filtered metrics freely in the same `metrics` list:

```py
wc.addFreeform(
    "Market Performance",
    item_id="variables/evar8",
    item_name="Market Code",
    metrics=[
        # plain metric
        {"id": "metrics/visitors", "name": "Unique Visitors"},
        # metric for DE only
        {"id": "metrics/visits", "name": "Visits",
         "filters": [{"id": "variables/evar8::581609802", "type": "DimensionItem", "name": "DE"}]},
        # visits split by device type
        {"id": "metrics/visits", "name": "Visits",
         "filters": [
             {"id": "s4222_mobile",  "type": "Segment", "name": "Mobile"},
             {"id": "s4222_desktop", "type": "Segment", "name": "Desktop"},
             {"id": "s4222_tablet",  "type": "Segment", "name": "Tablet"},
         ]},
    ],
)
```


---

### WorkspaceManager Methods

#### addPanel
Add a new **panel** to the workspace. All subsequent `addTextFreeform`, `addFreeform`, and other sub-panel methods target the most recently added panel.
Arguments:
* name        : REQUIRED : Panel title shown at the top of the panel.
* date_range  : OPTIONAL : Date-range preset ID or name (default `"thisMonth"`) **or** a custom ISO 8601 interval such as `"2026-04-22T00:00:00/2026-05-07T23:59:59"`. When the value contains `"/"` it is treated as a custom interval. Other common presets: `"thisWeek"`, `"last30Days"`, `"last90Days"`.
* position    : OPTIONAL : Zero-based index at which to insert the panel among existing panels. Defaults to appending at the end.
* collapsed   : OPTIONAL : Whether the panel starts collapsed. Default is `False`.
* description : OPTIONAL : Panel description. Default is `""`.

```py
wc.addPanel("Overview", date_range="thisMonth")

# Custom date range (ISO 8601 interval — no stored resource lookup)
wc.addPanel("April–May", date_range="2026-04-22T00:00:00/2026-05-07T23:59:59")

# Insert as the first panel (position 0)
wc.addPanel("New First Panel", position=0, collapsed=True, description="Added later")
```

#### addSegmentFilter
Add a global **segment filter** to the current panel. Multiple segments can be added by calling this method repeatedly.\
Arguments:
* segment : OPTIONAL : Segment ID or segment name. When a name matches multiple segments, the first match is used.

```py
# By ID
wc.addSegmentFilter("s1234_abc123def456abc123de")

# By name — resolved via getSegments when analytics= is set
wc.addSegmentFilter("My Segment")
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

#### addFreeform
Add a **freeform table** to the current panel and return it as a `FreeForm` instance (not `self`) — call `FreeForm.addBreakdown` on the result to nest a breakdown directly on it. Supply either a single `item_id` / `item_name` **or** a list of `items` — the component type is inferred automatically from the ID.

| ID pattern | Inferred type | Table style |
|---|---|---|
| `variables/...` (no `::`) | **Dimension** | dynamic top-*N* rows |
| `variables/...::hash` | **DimensionItem** | single static row |
| anything else | **Segment** | single static row |

When `items` is a list, every dict is auto-typed the same way (or use an explicit `"type"` key to override).  All list entries become static rows (`totalsType="columnSum"`).

Arguments:
* title       : REQUIRED : Sub-panel title.
* item_id     : OPTIONAL : Single component ID.  One of `item_id`, `item_name`, or `items` must be supplied.
* item_name   : OPTIONAL : Display label for `item_id`.  When `analytics` is set, `item_name` alone is sufficient — the ID is resolved automatically.
* items       : OPTIONAL : List of `{"id": ..., "name": ..., "type"?: ...}` dicts to use as static rows.  When `analytics` is set, each dict may omit `"id"` or `"name"`.
* metrics     : REQUIRED : List of metric dicts.  Each must have `"id"` and/or `"name"`.  When `analytics` is set, either key alone is sufficient.  Supports `"filters"` — see [Metric Filters](#metric-filters-column-level-filtering).
* rows        : OPTIONAL : Rows per page. Default is `10`.
* collapsed   : OPTIONAL : Whether the sub-panel starts collapsed. Default is `False`.
* description : OPTIONAL : Sub-panel description. Default is `""`.

```py
# Both id and name provided explicitly
ff = wc.addFreeform(
    "Visits by Experience",
    item_id="variables/targetraw.experience",
    item_name="Target Experiences",
    metrics=[
        {"id": "metrics/visits",  "name": "Visits"},
        {"id": "metrics/orders",  "name": "Orders"},
    ],
)

# With analytics= set: ID only — name and metric names resolved automatically
wc.addFreeform(
    "Visits by Experience",
    item_id="variables/targetraw.experience",
    metrics=[{"id": "metrics/visits"}, {"id": "metrics/orders"}],
)

# Segment static rows
wc.addFreeform(
    "Device Comparison",
    items=[
        {"id": "s4222_5fb7c392e9eaeb3747d8ad70", "name": "Mobile"},
        {"id": "s4222_5fb7c3457e678d6c7422de83", "name": "Desktop"},
        {"id": "s4222_5fb7c3457e678d6c7422de84", "name": "Tablet"},
    ],
    metrics=[{"id": "metrics/occurrences", "name": "Occurrences"}],
)

# Single dimension item as a static row
wc.addFreeform(
    "DE Market Only",
    item_id="variables/evar8::581609802",
    item_name="DE",
    metrics=[{"id": "metrics/visits", "name": "Visits"}],
)
```

#### FreeForm.addBreakdown
Add a **breakdown** nested under a `FreeForm` table (or under a breakdown level, for further nesting). Called on the `FreeForm` returned by `addFreeform` — not on `WorkspaceManager` — since the table object itself owns its breakdowns.

Not fluent on the table: it returns the **new** `FreeForm` representing the breakdown. Call `addBreakdown` again on the returned object to nest another level; call it again on the original table to add a sibling breakdown instead. Mutating the returned object updates the project immediately, even though `addFreeform` already "finished" adding the table.

Arguments:
* dimension_id   : OPTIONAL : Breakdown dimension ID (mutually exclusive with `items`).
* dimension_name : OPTIONAL : Breakdown dimension label.
* items          : OPTIONAL : List of `{"id", "name", "type"?}` dicts to use as static breakdown rows (segments or dimension items).
* rows           : OPTIONAL : Row count in the breakdown table. Default is `5`.

```py
# Dimension table → broken down by a second dimension
ff = wc.addFreeform(
    "Activity × Experience",
    item_id="variables/targetraw.activity",
    item_name="Target Activities",
    metrics=[
        {"id": "metrics/visits",      "name": "Visits"},
        {"id": "metrics/occurrences", "name": "Occurrences"},
    ],
)
ff.addBreakdown(dimension_id="variables/targetraw.experience", dimension_name="Target Experiences")

# Segment rows → broken down by a dimension, then a further breakdown nested underneath it
ff2 = wc.addFreeform(
    "Device Comparison",
    items=[
        {"id": "s4222_mobile",  "name": "Mobile"},
        {"id": "s4222_desktop", "name": "Desktop"},
    ],
    metrics=[{"id": "metrics/visits", "name": "Visits"}],
)
level1 = ff2.addBreakdown(dimension_id="variables/evar8", dimension_name="Market Code")
level1.addBreakdown(dimension_id="variables/evar3", dimension_name="Browser")   # nested 2 levels deep

# Segment rows as the breakdown, instead of a dimension
ff2.addBreakdown(items=[
    {"id": "s4222_mobile",  "name": "Mobile"},
    {"id": "s4222_desktop", "name": "Desktop"},
])
```

#### addActivityBreakdownFreeform
Add a **freeform table that pins a specific dimension item as a static row** broken down by a secondary dimension.

This is the standard pattern for Adobe Target activity reports: the activity is a static row (`DimensionItem`) and each experience is shown as a breakdown row underneath it.\
Arguments:
* title                : REQUIRED : Sub-panel title.
* activity_dim_item_id : REQUIRED : Dimension item ID for the static row (double-colon notation), e.g. `'variables/targetraw.activity::179567382'`.
* activity_name        : REQUIRED : Display name for the activity item.
* breakdown_dim_id     : REQUIRED : Breakdown dimension ID, e.g. `'variables/targetraw.experience'`.
* breakdown_dim_name   : REQUIRED : Breakdown dimension label.
* metrics              : REQUIRED : List of metric dicts (supports `"filters"` — see [Metric Filters](#metric-filters-column-level-filtering)).
* rows                 : OPTIONAL : Rows for the static-row table. Default is `50`.
* breakdown_rows       : OPTIONAL : Rows for the breakdown. Default is `5`.
* collapsed            : OPTIONAL : Whether the sub-panel starts collapsed. Default is `False`.
* description          : OPTIONAL : Sub-panel description. Default is `""`.

```py
wc.addActivityBreakdownFreeform(
    "Activity Results",
    activity_dim_item_id="variables/targetraw.activity::179567382",
    activity_name="My A/B Test",
    breakdown_dim_id="variables/targetraw.experience",
    breakdown_dim_name="Target Experiences",
    metrics=[
        {"id": "metrics/visits", "name": "Visits"},
        {"id": "cm1234_abc",     "name": "Conversion Rate"},
    ],
)
```

#### addSegmentAsDimensionFreeform
Add a **freeform table where segments are the rows** (no dimension).  Each segment becomes a static row, allowing side-by-side metric comparison across segments — the "Segment as Dimension" Workspace pattern.

An optional breakdown can be applied beneath each segment row:
- `breakdown_dim_id` / `breakdown_dim_name` — break each segment row down by a **dimension** (e.g. Market Code).
- `breakdown_segments` — break each segment row down by a second list of **segments** (nested segment rows).

Arguments:
* title               : REQUIRED : Sub-panel title.
* segments            : REQUIRED : List of segment dicts, each with `"id"` and `"name"`. Row order follows list order.
* metrics             : REQUIRED : List of metric dicts (supports `"filters"` — see [Metric Filters](#metric-filters-column-level-filtering)).
* breakdown_dim_id    : OPTIONAL : Dimension ID to break each segment row down by.  Requires `breakdown_dim_name`.
* breakdown_dim_name  : OPTIONAL : Display name for the breakdown dimension.
* breakdown_segments  : OPTIONAL : List of segment dicts (`"id"` + `"name"`) to use as nested rows in the breakdown.
* breakdown_rows      : OPTIONAL : Row count for the breakdown. Default is `5`.
* rows                : OPTIONAL : Pagination size (`viewBy`). Default is `50`.
* collapsed           : OPTIONAL : Whether the sub-panel starts collapsed. Default is `False`.
* description         : OPTIONAL : Sub-panel description. Default is `""`.

```py
# Plain segment rows
wc.addSegmentAsDimensionFreeform(
    "Device Comparison",
    segments=[
        {"id": "s4222_5fb7c392e9eaeb3747d8ad70", "name": "Mobile"},
        {"id": "s4222_5fb7c3457e678d6c7422de83", "name": "Desktop"},
        {"id": "s4222_5fb7c3688d55e5139e3ce3f0", "name": "Tablet"},
    ],
    metrics=[
        {"id": "metrics/occurrences", "name": "Occurrences"},
        {"id": "metrics/visits",      "name": "Visits"},
    ],
)

# Segment rows broken down by a dimension
wc.addSegmentAsDimensionFreeform(
    "Device × Market",
    segments=[
        {"id": "s4222_5fb7c392e9eaeb3747d8ad70", "name": "Mobile"},
        {"id": "s4222_5fb7c3457e678d6c7422de83", "name": "Desktop"},
    ],
    metrics=[{"id": "metrics/visits", "name": "Visits"}],
    breakdown_dim_id="variables/evar8",
    breakdown_dim_name="Market Code",
    breakdown_rows=5,
)

# Segment rows broken down by further segments
wc.addSegmentAsDimensionFreeform(
    "Device × Browser",
    segments=[
        {"id": "s4222_5fb7c392e9eaeb3747d8ad70", "name": "Mobile"},
    ],
    metrics=[{"id": "metrics/visits", "name": "Visits"}],
    breakdown_segments=[
        {"id": "s4222_chrome", "name": "Chrome"},
        {"id": "s4222_safari", "name": "Safari"},
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
* metric              : REQUIRED : Metric ID or metric name (e.g. `"metrics/visits"` or `"Visits"`).
* show_change         : OPTIONAL : Reserved for future support. Default is `False`.
* show_percent_change : OPTIONAL : Reserved for future support. Default is `False`.
* show_sparkline      : OPTIONAL : Reserved for future support. Default is `False`.
* collapsed           : OPTIONAL : Whether the KPI sub-panel starts collapsed. Default is `False`.
* description         : OPTIONAL : KPI sub-panel description. Default is `""`.

```py
# By ID
wc.addSummaryNumber("Total Visits", metric="metrics/visits")

# By name (resolved via analytics=)
wc.addSummaryNumber("Total Visits", metric="Visits")
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
wc.addFreeform("Visits by Page",
                item_id="variables/page", item_name="Page",
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
This is useful when you want to add a breakdown to freeforms that were created with `addFreeform` or loaded from an existing project definition, without rebuilding them.\
Arguments:
* breakdown_dim_id   : OPTIONAL : Breakdown dimension ID.  Required when `analytics` is not set.
* breakdown_dim_name : OPTIONAL : Breakdown dimension label.  Required when `analytics` is not set.  When `analytics` is set, either key alone is sufficient.
* target             : OPTIONAL : Which sub-panel(s) to target. Default is `"all"`.
  * `"all"` – apply to every `FreeformReportlet` in the current panel.
  * `int` – zero-based index of the sub-panel to target.
  * `str` (other than `"all"`) – name of the sub-panel to target.
* breakdown_rows : OPTIONAL : Rows per page for the breakdown. Default is `5`.

```py
# Both id and name provided
wc.addBreakdownToDimension("variables/evar3", "Campaign", target="all")

# With analytics= set: ID only — name resolved automatically
wc.addBreakdownToDimension("variables/evar3")

# With analytics= set: name only — ID resolved automatically
wc.addBreakdownToDimension(breakdown_dim_name="Campaign")

# Target a specific sub-panel by name
wc.addBreakdownToDimension("variables/evar3", "Campaign", target="Visits by Experience")

# Target a sub-panel by index
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

The following example demonstrates all available methods — it builds a project from scratch with a text freeform, KPI cards, a simple freeform with filtered metrics, a linked chart, a breakdown table, and a segment-comparison dropdown:

```py
import aanalytics2 as api2
from aanalytics2.workspaceManager import WorkspaceManager, TextBuilder

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
api2.importConfigFile("config_analytics.json")
myAnalytics = api2.Analytics()

wc = (
    WorkspaceManager(
        rsid="mycompany.global.all",
        name="Example Workspace",
        analytics=myAnalytics,
    )
    # ── Panel 1: Overview ──────────────────────────────────────────────────
    .addPanel("Example Workspace", date_range="thisMonth")
    .addSegmentFilter("s1234_abc123def456abc123de")

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

    # KPI cards
    .addSummaryNumber("Total Visits", metric="metrics/visits")
    .addSummaryNumber("Total Orders", metric="metrics/orders")
)

# Freeform with plain and filtered metrics + linked chart (addFreeform returns the FreeForm, not wc)
wc.addFreeform(
    "Market Performance",
    item_id="variables/evar8",
    item_name="Market Code",
    metrics=[
        # plain metric
        {"id": "metrics/visitors", "name": "Unique Visitors"},
        # scoped to DE dimension item
        {"id": "metrics/visits", "name": "Visits",
         "filters": [{"id": "variables/evar8::581609802", "type": "DimensionItem", "name": "DE"}]},
        # split by device segments
        {"id": "metrics/visits", "name": "Visits",
         "filters": [
             {"id": "s4222_mobile",  "type": "Segment", "name": "Mobile"},
             {"id": "s4222_desktop", "type": "Segment", "name": "Desktop"},
             {"id": "s4222_tablet",  "type": "Segment", "name": "Tablet"},
         ]},
    ],
)
wc.addChart("line", source="Market Performance", title="Visits Trend")
wc.addChart("donut")

# Dimension table broken down by a second dimension
activity_ff = wc.addFreeform(
    "Activity × Experience",
    item_id="variables/targetraw.activity",
    item_name="Target Activities",
    metrics=[
        {"id": "metrics/visits",      "name": "Visits"},
        {"id": "metrics/occurrences", "name": "Occurrences"},
    ],
)
activity_ff.addBreakdown(
    dimension_id="variables/targetraw.experience",
    dimension_name="Target Experiences",
)

# ── Panel 2: Segment Comparison ────────────────────────────────────────────
wc.addPanel("Segment Comparison", date_range="last30Days")
wc.addDropdownFilter(
    "Audience",
    components=[
        {"id": "s1234_aaa", "type": "Segment", "name": "New Visitors",       "isActive": True},
        {"id": "s1234_bbb", "type": "Segment", "name": "Returning Visitors"},
    ],
    has_no_filter=False,
)
wc.addFreeform(
    "Visits by Page",
    item_id="variables/page",
    item_name="Page",
    metrics=[{"id": "metrics/visits", "name": "Visits"}],
)
wc.addBreakdownToDimension("variables/evar3", "Campaign", target="all")
wc.addChart("bar", title="Visits by Page – Bar")

# 3. Create the project via the API
response = myAnalytics.createProject(projectDict=wc.to_dict())
print(response)
```

