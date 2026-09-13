# Knowledge Graph Ontology

Reference for the RDF graph built by `aanalytics2.knowledgegraph.KnowledgeGraph` and queried
through the `sparql_query` / `get_related_*` / `get_popular_combinations` / `get_component_context`
tools. Use this to decide which predicate to look up or which SPARQL query to write.

## Namespaces

For a company with ID `{companyId}`:

| Prefix | Namespace URI | Used for |
| -- | -- | -- |
| `rs`    | `http://analytics.com/{companyId}/reportSuite#` | ReportSuite nodes and `rs:*` predicates |
| `dim`   | `http://analytics.com/{companyId}/dimension#` | `dim:*` predicates on Dimension nodes |
| `met`   | `http://analytics.com/{companyId}/metric#` | `met:*` predicates on Metric nodes |
| `mc`    | `http://analytics.com/{companyId}/marketingChannel#` | `mc:*` predicates on MarketingChannel nodes |
| `seg`   | `http://analytics.com/{companyId}/segment#` | `seg:*` predicates on Segment nodes |
| `cm`    | `http://analytics.com/{companyId}/calculatedMetric#` | `cm:*` predicates on CalculatedMetric nodes |
| `dr`    | `http://analytics.com/{companyId}/dateRange#` | `dr:*` predicates on DateRange nodes |
| `proj`  | `http://analytics.com/{companyId}/projects#` | `proj:*` predicates, and the URI of the "projects root" node |
| `usage` | `http://analytics.com/{companyId}/usage#` | usage counters and co-occurrence predicates |

## Entity node URI patterns

| Entity | URI pattern |
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
| MetricCooccurrence / SegmentCooccurrence | blank node — found via `usage:dimension` + `usage:metric`/`usage:segment` |

## Node types (`rdf:type`, a plain string literal, not a class URI)

| Value | Meaning |
| -- | -- |
| `ReportSuite` | a report suite |
| `Dimension` | a dimension, scoped to one report suite |
| `Metric` | a metric, scoped to one report suite |
| `MarketingChannels` | the marketing channel container for a report suite |
| `MarketingChannel` | one configured marketing channel rule |
| `Segment` | a segment (company-wide) |
| `CalculatedMetric` | a calculated metric (company-wide) |
| `DateRange` | a date range (company-wide) |
| `Workspace` | a Workspace project (only present if projects were loaded before building the graph) |
| `MetricCooccurrence` | blank node: a dimension and a metric used together in a Workspace visualization, with a `cooccurrenceCount` |
| `SegmentCooccurrence` | blank node: a dimension and a segment used together in a Workspace visualization, with a `cooccurrenceCount` |

## Predicates

| Predicate | Usage |
| -- | -- |
| `rdf:type` | node type, see above (string literal, not a URI) |
| `rdfs:label` | human-readable name of a node |
| `rdfs:comment` | description of a node, when the source component has one |
| `dim:id` / `met:id` / `seg:id` / `cm:id` / `mc:id` / `dr:id` / `rs:id` | the raw Adobe Analytics component ID |
| `dim:dataType` | dimension data type (`string`, `int`, …) |
| `dim:classification` | boolean — whether the dimension ID contains a `.` (classification / sub-classification) |
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
| `proj:visualition` *(sic)* | name of a Visualization panel |
| `proj:panelFreeForm` | name (and description) of a FreeForm panel |
| `proj:dimension_ref` / `proj:metric_ref` / `proj:calculated_ref` | back-links from a Dimension / Metric / CalculatedMetric node to every Workspace that uses it |
| `usage:segmentUsage` / `usage:projectUsage` / `usage:metricUsage` | integer counters: how many times a node is referenced by segments, Workspace projects, or calculated metrics |
| `usage:usedWithMetric` / `usage:usedWithDimension` | direct co-occurrence edge between a Dimension and a Metric node (both directions) |
| `usage:usedWithSegment` / `usage:usedWithDimension` | direct co-occurrence edge between a Dimension and a Segment node (both directions) |
| `usage:dimension` / `usage:metric` / `usage:segment` | from a `MetricCooccurrence` / `SegmentCooccurrence` blank node to the entity it relates |
| `usage:cooccurrenceCount` | how many times that specific pairing was observed |
| `usage:rsid` | from a cooccurrence blank node to the ReportSuite it was observed on |

For the full narrative documentation (how the graph is built, the `KnowledgeGraph` class reference,
a Mermaid diagram) see `docs/knowledgegraph.md` in the aanalytics2 repository.
