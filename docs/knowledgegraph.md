# Knowledge Graph

Adobe Analytics implementations accumulate hundreds of dimensions, metrics, segments, calculated metrics, and Workspace projects — with no built-in way to see how they relate to each other.\
The `knowledgegraph` module builds an [RDF](https://www.w3.org/RDF/) **Knowledge Graph** out of your Adobe Analytics implementation, connecting every component (dimensions, metrics, marketing channels, segments, calculated metrics, date ranges) to the report suites they belong to, and — when Workspace projects are loaded — to each other, through actual usage.

It relies on the `WorkspaceManager` class to parse Workspace project definitions, and on [`rdflib`](https://rdflib.readthedocs.io/) to build, serialize, and query the resulting graph with SPARQL.

> **Not loaded by default**: unlike most of the package, `KnowledgeGraph` is **not** re-exported from the top-level `aanalytics2` package (no `import aanalytics2; aanalytics2.KnowledgeGraph(...)`). Import it explicitly from its module:
> ```py
> from aanalytics2.knowledgegraph import KnowledgeGraph
> ```

## Menu
- [Overview](#overview)
- [Importing the module](#importing-the-module)
- [Instantiation](#instantiation)
  - [What happens at instantiation](#what-happens-at-instantiation)
- [Attributes](#attributes)
- [Methods](#methods)
  - [loadGraph](#loadgraph)
  - [loadProjects](#loadprojects)
  - [buildGraph](#buildgraph)
  - [getUsageCounts](#getusagecounts)
  - [exportGraph](#exportgraph)
  - [query](#query)
- [Complete Example](#complete-example)
  - [Resume a saved graph](#resume-a-saved-graph)
- [Ontology](#ontology)
  - [Namespaces](#namespaces)
  - [Node types](#node-types)
  - [Predicates](#predicates)
  - [Mermaid Diagram](#mermaid-diagram)

## Overview

Building the graph creates RDF entities (as `URIRef` nodes) for:

* **ReportSuite** — one per rsid considered.
* **Dimension** / **Metric** — scoped per report suite (the same dimension ID on two report suites becomes two distinct nodes).
* **MarketingChannel** — the marketing channel rules configured for a report suite.
* **Segment** / **CalculatedMetric** / **DateRange** — company-wide (not scoped to a single report suite).
* **Workspace** — one per project loaded via `loadProjects`.

On top of these entities, `buildGraph` derives two kinds of relationships that aren't available anywhere else in the API:

* **Usage counts** : how many times each dimension, metric, segment, calculated metric, and report suite is referenced across segments, calculated metrics, and loaded Workspace projects (`segmentUsage`, `metricUsage`, `projectUsage`).
* **Co-occurrence** : which dimensions are used *together with* which metrics, and which dimensions are used *together with* which segments, inside the same Workspace visualization — with a count of how often that pairing occurs.

The result is a `rdflib.Graph` that can be serialized to Turtle (`.ttl`) and queried with SPARQL, or explored with any RDF-compatible tool. The full node/predicate vocabulary is described in [Ontology](#ontology).

Use [loadGraph](#loadgraph) to restore a saved snapshot, then
[buildGraph](#buildgraph) with `incremental=True` to add new projects without rebuilding
its components. [getUsageCounts](#getusagecounts) exposes the stored usage counters as
Python dictionaries.

## Importing the module

```py
from aanalytics2.knowledgegraph import KnowledgeGraph
```

## Instantiation

`KnowledgeGraph` connects to Adobe Analytics on instantiation — it needs a `config` object the same way `Analytics` or `Login` do.

```py
import aanalytics2 as api2
from aanalytics2.knowledgegraph import KnowledgeGraph

cfg = api2.importConfigFile('config_analytics.json', return_object=True)

# Auto-detect the most commonly used report suite from your projects
kg = KnowledgeGraph(config=cfg)

# Build the graph across every report suite in the company
kg_all = KnowledgeGraph(config=cfg, rsids="all")

# Restrict to specific report suites
kg_some = KnowledgeGraph(config=cfg, rsids=["rsid_a", "rsid_b"])

```

Arguments:
* config : OPTIONAL : The config dictionary/`ConfigObj` returned by `importConfigFile(..., return_object=True)` (or `configure(..., return_object=True)`).
* companyId : OPTIONAL : The company ID to use for building the knowledge graph. If not provided, the first company ID returned by `Login.getCompanyId()` is used.
* rsids : OPTIONAL : Which report suite(s) to include (`list[str]`, `str`, or `"all"`).
  * Not provided (default) : the report suite ID most frequently used across your Workspace projects is auto-detected and used.
  * `"all"` : every (non-virtual) report suite in the company is used.
  * `str` : a single report suite ID.
  * `list` : an explicit list of report suite IDs.
* filterDims : OPTIONAL : If set to `True` (default), entry/exit dimensions (`/entry`, `/exit`) are excluded and only Oberon-reportable dimensions are kept.

The proxy is always inherited from the configuration; there is no Knowledge Graph
proxy override. Set `cfg.config["proxy"]` to a proxy URL or a mapping such as
`{"http": "...", "https": "..."}`. The resolved login configuration is reused for
the Analytics connection, including scan requests and OAuth token refreshes.

### What happens at instantiation

Instantiating the class performs several API calls right away, before you call any method:

1. Connects via `Login` and resolves the `companyId`.
2. Retrieves the report suites (`getReportSuites(extended_info=True)`).
3. Resolves `rsids` (auto-detecting from your most-used project's report suite when not provided).
4. Fetches dimensions, metrics, and marketing channels **per report suite concurrently** (`ThreadPoolExecutor`, up to 10 workers).
5. Fetches segments, calculated metrics, date ranges, project stubs, and annotations for the whole company.
6. Builds one `rdflib.Namespace` per entity type (plus one dimension/metric namespace per report suite), stored in `kg.namespaces`. See [Namespaces](#namespaces).

## Attributes

Once instantiated, the `KnowledgeGraph` object exposes the following attributes:

* `kg.companyId` : the resolved company ID.
* `kg.rsids` : the list of report suite IDs considered.
* `kg.reportSuites` : `DataFrame` of report suite metadata.
* `kg.dimensions` / `kg.metrics` : `dict` keyed by rsid, each value a raw list of dimension/metric dicts.
* `kg.marketingChannels` : `dict` keyed by rsid.
* `kg.segments` / `kg.calculatedMetrics` / `kg.dateRanges` : raw lists (extended info), company-wide.
* `kg.projects` : raw list of project stubs (`id`, `name`, `rsid`, `modified`, …) — not full definitions. Use `loadProjects` to fetch full definitions.
* `kg.annotations` : raw list of annotations.
* `kg.namespaces` : `dict` of `rdflib.Namespace` objects, one per entity type (`"segments"`, `"metrics"`, `"reportSuites"`, `"usage"`, …), plus one `"{rsid}/dimensions"` / `"{rsid}/metrics"` pair per report suite. See [Namespaces](#namespaces).
* `kg.project_details` : initially empty list of `WorkspaceManager` instances.
  Each `loadProjects` call appends its results without replacing previously loaded details.
* `kg.graph` : an initially empty `rdflib.Graph`, populated by `loadGraph` or `buildGraph`.
* `kg.entity_usage` : a Python dictionary mapping entity `URIRef` objects to their
  integer `segmentUsage`, `metricUsage`, and `projectUsage` counters.
* `kg.dim_metric_cooccurrence` / `kg.dim_segment_cooccurrence` : Python dictionaries
  mapping `(dimension_uri, metric_or_segment_uri, report_suite_uri)` tuples to integer counts.

The three counter dictionaries are per-instance, initially empty, restored by `loadGraph`,
and synchronized after builds. They are snapshots, not setters for the RDF graph. If a
loaded graph contains invalid or ambiguous counters, including after an explicit merge,
a warning is logged and these attributes become `None`. Incremental builds validate the
RDF counters again and reject invalid data rather than guess the counts. A clean full
build restores the dictionaries.

## Methods

### loadGraph

Load an existing local Turtle (`.ttl`) file into `kg.graph`, ready to query, edit, export,
or extend with `buildGraph`.

```py
kg = KnowledgeGraph(config=cfg, rsids=["rsid_a"])
graph = kg.loadGraph("previous_graph.ttl")

# Reuse its components and add only new projects, saving a separate snapshot
kg.loadProjects(["new_project_id"])
graph = kg.buildGraph(incremental=True, save=True, filename="extended_graph.ttl")

# Loading another snapshot replaces the graph and counter state by default
kg.loadGraph("another_graph.ttl")

# Explicitly combine triples from a separate file with the current graph
kg.loadGraph("additional_graph.ttl", merge=True)
```

Arguments:
* filename : REQUIRED : Path to an existing local Turtle file (`str` or `pathlib.Path`).
  Relative paths are resolved from the current working directory; no extension is appended.
* merge : OPTIONAL : Whether to combine the file's triples with the current graph
  (bool : default `False`). By default, replace the current graph and counter state.

Returns the loaded or merged `rdflib.Graph`, also stored on `kg.graph`. Namespace
bindings from the Turtle file are retained. Missing/unreadable files and invalid Turtle
raise their original exceptions (such as `FileNotFoundError` or a Turtle parser error)
without changing the current graph or counter dictionaries.

Usage and co-occurrence counters are reconstructed as Python dictionaries, including
counts from projects whose definitions have not been loaded in this Python session.
Loading does not repopulate the Analytics metadata attributes or restore
`WorkspaceManager` instances. Use the same company and report suite scope as the saved
graph when you intend to extend it.
Instantiation still connects to Adobe Analytics as described above; `loadGraph` itself
makes no Analytics API calls.

When `merge=True`, identical triples are deduplicated, but conflicting numeric values or
duplicate co-occurrence records are not guessed or summed. Such graphs remain loadable,
with a warning and unavailable counter dictionaries, but cannot be incrementally updated
until the counters are corrected or rebuilt.

### loadProjects

Fetch full Workspace project definitions and parse them (via `WorkspaceManager`) so `buildGraph` can extract dimension/metric/segment/calculated-metric usage and co-occurrence from them.\
This step is optional — without it, `buildGraph` still produces the full component graph and usage counts from segments and calculated metrics, but no project-derived usage or co-occurrence.

```py
# Load the 20 most recently modified projects
kg.loadProjects(20)

# Load a random sample of 20 projects instead
kg.loadProjects(20, sampleMethod='random')

# Load specific projects by ID
kg.loadProjects(['5f9...abc', '5f9...def'])

# Load projects whose owner login contains either value (case-insensitive)
kg.loadProjects(['analyst@example.com', 'reporting-team'], sampleMethod='users')

# Load every project in the company (can take a long time)
kg.loadProjects('all')
```

Arguments:
* projects : REQUIRED : Which projects to load.
  * `int` : number of projects to load, selected via `sampleMethod`.
  * `list` : explicit list of project IDs, or owner login filters when `sampleMethod='users'`.
  * `"all"` : every project in the company. This fetches each project definition individually and can take a large amount of time on big accounts.
* sampleMethod : OPTIONAL : How to select projects. (str : default `'most_recent'`)
  * `'most_recent'` : the most recently modified projects, when `projects` is an `int`.
  * `'random'` : a random sample of projects, when `projects` is an `int`.
  * `'users'` : match a list of values against project owner logins using
    case-insensitive substring matching.

Project definitions are fetched concurrently (`ThreadPoolExecutor`, up to 6 workers) and stored as `WorkspaceManager` instances in `kg.project_details`.

Returns `None`. Repeated calls append project details and leave the complete
`kg.projects` catalogue intact, so you can load additional batches later. Previously
loaded IDs are not skipped during fetching. Avoid loading the same project more than
once before a full build, which counts every entry in `kg.project_details`; incremental
builds deduplicate project IDs.

Loading projects does not update the RDF graph. Call `buildGraph(incremental=True)` to
incorporate only projects not already registered in its counter snapshot.

### buildGraph

Build the RDF graph from everything fetched at instantiation (and from `kg.project_details`, if `loadProjects` was called beforehand).

```py
graph = kg.buildGraph()

# Build and save straight to a Turtle file
graph = kg.buildGraph(save=True, filename='my_graph.ttl')

# Print progress while building
graph = kg.buildGraph(verbose=True)

# Discard any loaded or previously built graph and rebuild from scratch
graph = kg.buildGraph(merge=False)

# Reuse a loaded or previously built component graph, processing only new projects
graph = kg.buildGraph(incremental=True, save=True, filename='new_snapshot.ttl')
```

Arguments:
* save : OPTIONAL : If set to `True`, serializes the graph to a Turtle file. (bool : default `False`)
* filename : OPTIONAL : Filename used when `save=True`. A `.ttl` extension is appended automatically if missing. (str : default `'knowledge_graph.ttl'`)
* verbose : OPTIONAL : If set to `True`, prints progress statements while the graph is being built.
* merge : OPTIONAL : Retain existing metadata and add the newly built data (`True`, the default).
  Generated counters are replaced during a full build, even with `merge=True`.
  Set to `False` to discard the entire current graph before building.
* incremental : OPTIONAL : Reuse existing components and process only new projects
  (`False`, the default). Requires a non-empty graph and `merge=True`; incompatible
  combinations raise `ValueError`.
* calculatedMetricWorkers : OPTIONAL : Keyword argument controlling the number of
  concurrent calculated-metric scan workers (int : default `10`). Applies only to
  full builds; incremental builds do not perform these scans.

Returns the built `rdflib.Graph`, also stored on `kg.graph`.

**Full builds** compute a fresh counter snapshot from the current Analytics data and
`kg.project_details`. Old usage values, co-occurrence records and direct co-occurrence
links are replaced, rather than retaining obsolete values alongside new ones. Project
registrations are reset to the projects included in that computation. Other metadata
is retained when `merge=True`. Load all desired projects before a full build, or use
incremental mode to preserve contributions from projects already in a saved snapshot.

**Incremental builds** skip dimension, metric, marketing-channel, segment,
calculated-metric and date-range construction, including segment/calculated-metric scans.
Only newly loaded projects are processed. Persisted project registrations identify
projects already counted, including after a Turtle round trip; repeated project IDs in
the same batch are also counted once. An existing project's changed definition is not
refreshed in this mode; use a full build with all desired projects to refresh it.

Stored counters are read and validated as Python integers before adding projects.
New `projectUsage` contributions are added to their existing totals, while
`segmentUsage` and `metricUsage` remain unchanged. Co-occurrence counts are incremented
on the existing node for the same dimension/component/report-suite tuple, or a new node
is created for a new pairing. Each counter has one current numeric value in the output.
The instance counter dictionaries are updated alongside the graph. Direct RDF edits are
reread on each incremental build so stale Python snapshots cannot corrupt the totals.

Negative/non-integer counts, multiple values for one counter, malformed co-occurrence
records and duplicate records for the same pairing raise `ValueError` before new projects
are added. Missing usage fields count as zero. Counter validation does not repair ambiguous
historical merges automatically; a full build can recompute a clean snapshot.

Saving to a different filename leaves the original Turtle snapshot unchanged.
Incremental mode speeds up graph construction, not instantiation: the initial Analytics
metadata fetches still take place.

If a segment or calculated-metric scan raises a Requests connection error (including proxy
and TLS errors) or timeout, graph construction continues with the remaining components.
A warning from the `aanalytics2.knowledgegraph` logger identifies the failed component and
error type, even when `verbose=False`. Its metadata is retained, but usage counts from that
scan are omitted, so aggregate usage counts may be incomplete. Other exceptions still
propagate, as do network errors during initial data loading or project loading.

Segment definitions supplied as dictionaries are scanned locally. Calculated-metric scans
reuse the already-loaded segments and only fetch a referenced segment when it is absent
or its definition is missing; these fallback requests use the same Analytics connection
and proxy as other API calls.

What gets added during a full build (incremental builds add only new project data and counters):
* One node per **ReportSuite**, **Dimension**, **Metric**, **MarketingChannel**, **Segment**, **CalculatedMetric**, and **DateRange**, each carrying its own properties (`RDFS.label`, `id`, `type`, `reportable`, `segmentable`, tags, share counts, last-access timestamps, …) under its entity namespace (`kg.namespaces[...]`).
* Classification dimensions (IDs containing `.`) are linked to their parent via `parent_dimension` / `children_dimension` predicates.
* Every `Segment` and `CalculatedMetric` is scanned (`scanSegment` / `scanCalculatedMetric`) to increment `usage.segmentUsage` / `usage.metricUsage` on every dimension/metric/report suite it references.
* One **Workspace** node per project in `kg.project_details` (populated by `loadProjects`), linked to its report suite, with each panel's text, freeform table, and visualization content attached, and every dimension/metric/calculated-metric/segment it uses incrementing `usage.projectUsage`.
* **Co-occurrence** blank nodes: a `MetricCooccurrence` node for every (dimension, metric) pair found together in the same Workspace visualization, and a `SegmentCooccurrence` node for every (dimension, segment) pair — each carrying a `cooccurrenceCount` and the `rsid` it was observed on. The dimension and metric/segment nodes are additionally linked directly via `usedWithMetric` / `usedWithDimension` and `usedWithSegment` / `usedWithDimension` predicates.

The full list of node types and predicates produced here is detailed in [Ontology](#ontology).

### getUsageCounts

Read the RDF usage counters into a fresh Python dictionary, keyed by entity `URIRef`.
Only stored usage fields are returned, and values are ordinary Python integers.
This method takes no arguments and returns `dict[URIRef, dict[str, int]]`; the inner
keys are `segmentUsage`, `metricUsage`, and `projectUsage`. Missing fields are omitted
rather than filled with zero, and an empty graph returns `{}`.

```py
from rdflib import URIRef

metric_uri = URIRef(
    f"http://analytics.com/{kg.companyId}/{kg.rsids[0]}/metric/metrics/visits"
)
counts = kg.getUsageCounts()
project_count = counts.get(metric_uri, {}).get("projectUsage", 0)

# The instance also exposes the last loaded/built counter snapshots
usage_counts = kg.entity_usage
metric_pairs = kg.dim_metric_cooccurrence
segment_pairs = kg.dim_segment_cooccurrence
```

Editing the returned dictionary does not modify the RDF graph or the instance counter
snapshots. Each call rereads the RDF graph but does not synchronize those attributes.
Negative or non-integer values (including booleans), multiple values for the same
counter, and counters attached to something other than an entity URI raise `ValueError`.
Co-occurrence counters are exposed through the instance dictionaries, not this method;
they are validated when loading or incrementally building a graph.

### exportGraph

Serialize the built or loaded graph (`kg.graph`) to a Turtle file. Use this when you want to save the graph separately from `buildGraph`, e.g. after running additional edits on `kg.graph`.

```py
kg.exportGraph(filename='my_graph.ttl')
```

Arguments:
* filename : REQUIRED : The name of the Turtle file to write. A `.ttl` extension is appended automatically if missing.

### query

Run a SPARQL query against the graph built by `buildGraph()` or loaded by `loadGraph()`.\
Unlike calling `kg.graph.query(...)` directly, this returns a list of plain Python dictionaries (one per result row, values converted with `.toPython()`) instead of raw `rdflib` `Result` rows — easier to load straight into a `pandas.DataFrame`.

```py
rows = kg.query("""
    PREFIX usage: <http://analytics.com/COMPANYID/usage#>
    SELECT ?dimension ?count WHERE {
        ?dimension usage:projectUsage ?count .
    }
    ORDER BY DESC(?count)
    LIMIT 10
""")

import pandas as pd
df = pd.DataFrame(rows)
```

Arguments:
* sparql_string : REQUIRED : The SPARQL query to execute.

Returns a `list` of `dict`, one per result row, keyed by SPARQL variable name.

## Complete Example

```py
import aanalytics2 as api2
from aanalytics2.knowledgegraph import KnowledgeGraph

# 1. Authenticate
cfg = api2.importConfigFile('config_analytics.json', return_object=True)

# 2. Build the component graph across every report suite
kg = KnowledgeGraph(config=cfg, rsids="all")

# 3. Load the 50 most recently modified projects to enrich the graph
#    with real usage and co-occurrence data
kg.loadProjects(50, sampleMethod='most_recent')

# 4. Build and save the graph
graph = kg.buildGraph(save=True, filename='analytics_knowledge_graph.ttl', verbose=True)

# 5. Query it — e.g. the 10 most-used dimensions across loaded projects
rows = kg.query(f"""
    PREFIX usage: <http://analytics.com/{kg.companyId}/usage#>
    SELECT ?dimension ?count WHERE {{
        ?dimension usage:projectUsage ?count .
    }}
    ORDER BY DESC(?count)
    LIMIT 10
""")
for row in rows:
    print(row['dimension'], row['count'])

# 6. Re-export the graph later without rebuilding it
kg.exportGraph(filename='analytics_knowledge_graph_backup.ttl')
```

### Resume a saved graph

Continuing from the example above, create a new instance with the same company and
report suite scope, then load the snapshot. Replace `new_project_id` with an actual
project ID that was not already counted.

```py
resumed = KnowledgeGraph(config=cfg, companyId=kg.companyId, rsids=kg.rsids)
graph = resumed.loadGraph('analytics_knowledge_graph.ttl')

resumed.loadProjects(['new_project_id'])
graph = resumed.buildGraph(
    incremental=True,
    save=True,
    filename='analytics_knowledge_graph_extended.ttl',
)
counts = resumed.getUsageCounts()
```

The original file is unchanged. Saved usage and co-occurrence counts are retained,
new project contributions are added once, and the extended graph can be queried or
exported using the same methods as a freshly built graph. Instantiation still fetches
Analytics metadata; incremental mode avoids rebuilding and rescanning the components.

## Ontology

> This section is also shipped as a standalone file, [`aanalytics2/resources/kg_ontology.md`](../aanalytics2/resources/kg_ontology.md), which the [MCP server](./mcp_server.md#knowledge-graph-ontology-resource) serves to LLM clients as the `ontology://knowledge-graph` resource. Keep the two in sync when the schema changes.

### Namespaces

For a company with ID `{companyId}`, the following namespaces are minted at instantiation and stored in `kg.namespaces`:

| Key in `kg.namespaces` | URI pattern | Used for |
| -- | -- | -- |
| `reportSuites` | `http://analytics.com/{companyId}/reportSuite#` | ReportSuite nodes (`reportSuites[rsid]`) and the `rs:*` predicates |
| `dimensions` | `http://analytics.com/{companyId}/dimension#` | the `dim:*` predicates attached to Dimension nodes |
| `metrics` | `http://analytics.com/{companyId}/metric#` | the `met:*` predicates attached to Metric nodes |
| `marketingChannels` | `http://analytics.com/{companyId}/marketingChannel#` | the `mc:*` predicates attached to MarketingChannel nodes |
| `segments` | `http://analytics.com/{companyId}/segment#` | the `seg:*` predicates attached to Segment nodes |
| `calculatedMetrics` | `http://analytics.com/{companyId}/calculatedMetric#` | the `cm:*` predicates attached to CalculatedMetric nodes |
| `dateRange` | `http://analytics.com/{companyId}/dateRange#` | the `dr:*` predicates attached to DateRange nodes |
| `projects` | `http://analytics.com/{companyId}/projects#` | the `proj:*` predicates, and the URI of the single "projects root" node |
| `usage` | `http://analytics.com/{companyId}/usage#` | the `usage:*` predicates (usage counts, co-occurrence) |
| `{rsid}/dimensions`, `{rsid}/metrics` | `http://analytics.com/{companyId}/{rsid}/dimension#` / `.../{rsid}/metric#` | one pair per report suite, bound as serialization prefixes — the actual Dimension/Metric node URIs use the pattern below, not these namespace objects |

Entity **nodes** (other than `ReportSuite`) are not minted from the namespace objects above — each has its own dedicated URI template:

| Entity | Node URI pattern |
| -- | -- |
| ReportSuite | `http://analytics.com/{companyId}/reportSuite#{rsid}` |
| Dimension | `http://analytics.com/{companyId}/{rsid}/dimension/{dimensionId}` |
| Metric | `http://analytics.com/{companyId}/{rsid}/metric/{metricId}` |
| MarketingChannel container (one per rsid) | `http://analytics.com/{companyId}/{rsid}/marketingChannel/` |
| MarketingChannel (each configured channel) | `http://analytics.com/{companyId}/{rsid}/marketingChannel/{channelId}` |
| Segment | `http://analytics.com/{companyId}/segment/{segmentId}` |
| CalculatedMetric | `http://analytics.com/{companyId}/calculatedMetric/{calculatedMetricId}` |
| DateRange | `http://analytics.com/{companyId}/dateRange/{dateRangeId}` |
| Workspace (project) | `http://analytics.com/{companyId}/projects/{projectId}` |
| Projects root | `http://analytics.com/{companyId}/projects#` (the `projects` namespace itself, used as a single node every Workspace is attached to via `proj:contains`) |
| MetricCooccurrence / SegmentCooccurrence | blank node (`BNode()`) — no stable URI; found via the `usage:dimension` + `usage:metric`/`usage:segment` predicates |

### Node types

Nodes are typed with `rdf:type` (`RDF.type`) using the following (literal) values:

| rdf:type | Meaning |
| -- | -- |
| `ReportSuite` | a report suite |
| `Dimension` | a dimension, scoped to one report suite |
| `Metric` | a metric, scoped to one report suite |
| `MarketingChannels` | the marketing channel container for a report suite |
| `MarketingChannel` | one configured marketing channel rule |
| `Segment` | a segment (company-wide) |
| `CalculatedMetric` | a calculated metric (company-wide) |
| `DateRange` | a date range (company-wide) |
| `Workspace` | a Workspace project — only present after `loadProjects` + `buildGraph` |
| `MetricCooccurrence` | blank node recording that a dimension and a metric were used together in a Workspace visualization, with a `cooccurrenceCount` |
| `SegmentCooccurrence` | blank node recording that a dimension and a segment were used together in a Workspace visualization, with a `cooccurrenceCount` |

### Predicates

The tables below use short prefixes for readability. They map to `kg.namespaces` as follows:

```
dim   → kg.namespaces['dimensions']
met   → kg.namespaces['metrics']
mc    → kg.namespaces['marketingChannels']
seg   → kg.namespaces['segments']
cm    → kg.namespaces['calculatedMetrics']
rs    → kg.namespaces['reportSuites']
dr    → kg.namespaces['dateRange']
proj  → kg.namespaces['projects']
usage → kg.namespaces['usage']
```

| Predicate | Usage |
| -- | -- |
| `rdf:type` | node type, see [Node types](#node-types) |
| `rdfs:label` | human-readable name of a node |
| `rdfs:comment` | description of a node, when the source component has one |
| `dim:id` / `met:id` / `seg:id` / `cm:id` / `mc:id` / `dr:id` / `rs:id` | the raw Adobe Analytics component ID |
| `dim:dataType` | dimension data type (`string`, `int`, …) |
| `dim:classification` | `true` / `false` — whether the dimension ID contains a `.` (classification / sub-classification) |
| `dim:parent_dimension` / `dim:children_dimension` | links a classification dimension to its parent, and back |
| `dim:reportable` / `met:reportable` / `cm:reportable` | one triple per supported report type / product |
| `dim:segmentable` / `met:segmentable` | boolean |
| `dim:rsid` / `met:rsid` / `mc:rsid` / `seg:rsid` / `cm:rsid` | link from the component to its owning ReportSuite node |
| `met:type` / `cm:type` | metric / calculated metric type |
| `met:polarity` / `cm:polarity` | `positive` / `negative` |
| `mc:defines` | the marketing channel container → each configured channel |
| `mc:position` / `mc:override` / `mc:enabled` | channel rule configuration |
| `rs:currency` | ReportSuite currency |
| `rs:dimensions` / `rs:metrics` / `rs:marketingChannels` / `rs:segments` / `rs:calculatedMetrics` | ReportSuite → each of its component nodes |
| `seg:definition` / `cm:definition` | segment / calculated metric definition (JSON, as a string literal) |
| `seg:lastAccess` / `cm:lastAccess` | last recorded access, `xsd:dateTime` |
| `seg:tag` / `cm:tag` | one triple per tag name |
| `seg:shares` / `cm:shares` | number of shares |
| `dr:description` / `dr:definition` | date range metadata |
| `proj:contains` | the projects root node → each loaded Workspace |
| `proj:rsid` | Workspace → its ReportSuite |
| `proj:description` / `proj:created` | Workspace metadata |
| `proj:text` | text panel content (title, and body when not empty) |
| `proj:visualition` *(sic — kept as-is to match the current implementation)* | name of a Visualization panel |
| `proj:panelFreeForm` | name (and description) of a FreeForm panel |
| `proj:dimension_ref` / `proj:metric_ref` / `proj:calculated_ref` | back-links from a Dimension / Metric / CalculatedMetric node to every Workspace that uses it |
| `usage:segmentUsage` / `usage:projectUsage` / `usage:metricUsage` | integer counters on Dimension/Metric/ReportSuite/Segment/CalculatedMetric nodes: how many times it is referenced by segments, Workspace projects, or calculated metrics respectively |
| `usage:usedWithMetric` / `usage:usedWithDimension` | direct co-occurrence edge between a Dimension and a Metric node (both directions) |
| `usage:usedWithSegment` / `usage:usedWithDimension` | direct co-occurrence edge between a Dimension and a Segment node (both directions) |
| `usage:dimension` / `usage:metric` / `usage:segment` | from a `MetricCooccurrence` / `SegmentCooccurrence` blank node to the Dimension/Metric/Segment it relates |
| `usage:cooccurrenceCount` | how many times that specific pairing was observed |
| `usage:rsid` | from a cooccurrence blank node to the ReportSuite it was observed on |

### Mermaid Diagram

Below is a Mermaid diagram of the main artefacts and relationships in the knowledge graph. It is not exhaustive, but it gives a good overview of the graph structure.

```mermaid
graph TD
    ReportSuite -->|rs:dimensions| Dimension
    ReportSuite -->|rs:metrics| Metric
    ReportSuite -->|rs:marketingChannels| MarketingChannel
    ReportSuite -->|rs:segments| Segment
    ReportSuite -->|rs:calculatedMetrics| CalculatedMetric
    Dimension -->|dim:parent_dimension| Dimension
    Dimension -->|dim:children_dimension| Dimension
    Segment -->|seg:rsid| ReportSuite
    CalculatedMetric -->|cm:rsid| ReportSuite
    MarketingChannel -->|mc:rsid| ReportSuite
    ProjectsRoot["Projects (root)"] -->|proj:contains| Workspace
    Workspace -->|proj:rsid| ReportSuite
    Dimension -->|proj:dimension_ref| Workspace
    Metric -->|proj:metric_ref| Workspace
    CalculatedMetric -->|proj:calculated_ref| Workspace
    Segment -.->|counted via usage:projectUsage| Workspace
    Dimension -->|usage:usedWithMetric| Metric
    Metric -->|usage:usedWithDimension| Dimension
    Dimension -->|usage:usedWithSegment| Segment
    Segment -->|usage:usedWithDimension| Dimension
    MetricCooccurrence["MetricCooccurrence (blank node)"] -->|usage:dimension| Dimension
    MetricCooccurrence -->|usage:metric| Metric
    MetricCooccurrence -->|usage:cooccurrenceCount| Count
    SegmentCooccurrence["SegmentCooccurrence (blank node)"] -->|usage:dimension| Dimension
    SegmentCooccurrence -->|usage:segment| Segment
    SegmentCooccurrence -->|usage:cooccurrenceCount| Count
    ReportSuite -->|usage:segmentUsage / projectUsage / metricUsage| UsageCounters["usage counters"]
    Dimension -->|usage:segmentUsage / projectUsage| UsageCounters
    Metric -->|usage:metricUsage / projectUsage| UsageCounters
```
