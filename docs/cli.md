# aanalytics2 CLI

The `aanalytics2` package ships with an interactive command-line interface (CLI).\
It gives you a terminal REPL to explore and manage your Adobe Analytics account without writing Python code.\
The CLI wraps the `Analytics` class and the `RequestCreator` class. Every method that exists on those classes has a corresponding command.

---

## Installation

The CLI is included in the package and becomes available after installation:

```bash
pip install aanalytics2
```

You can also invoke it directly as a Python module without a registered entry point:

```bash
python -m aanalytics2.cli
```

---

## Configuration file

The CLI reads credentials from the same JSON config file used by the Python library.\
Two optional CLI-specific fields can be added: `companyId` and `rsid`.

```json
{
    "org_id": "<your IMS org ID>",
    "client_id": "<your client ID>",
    "secret": "<your secret>",
    "scopes": "<your OAuth scopes>",
    "companyId": "<your globalCompanyId>",
    "rsid": "<your default report suite ID>"
}
```

The `companyId` field skips the interactive company-selection prompt at startup.\
The `rsid` field pre-sets the default report suite for the session.

You can generate a blank credentials file with:

```python
import aanalytics2
aanalytics2.createConfigFile()
```

Then add `companyId` and `rsid` manually before launching the CLI.

### Configuring without a file

If no config file is found (e.g. the default `config_analytics.json` does not exist), the CLI falls back to individual credential parameters, sourced from either the `config` command's flags or from environment variables — useful on servers where dropping a JSON file on disk isn't practical.

Environment variables:

* `AANALYTICS2_ORG_ID`
* `AANALYTICS2_CLIENT_ID`
* `AANALYTICS2_SECRET`
* `AANALYTICS2_SCOPES`
* `AANALYTICS2_TECH_ID` (optional)
* `AANALYTICS2_COMPANY_ID` (optional — same role as `companyId` in the config file)
* `AANALYTICS2_RSID` (optional — same role as `rsid` in the config file)

```bash
export AANALYTICS2_ORG_ID="<your IMS org ID>"
export AANALYTICS2_CLIENT_ID="<your client ID>"
export AANALYTICS2_SECRET="<your secret>"
export AANALYTICS2_SCOPES="<your OAuth scopes>"
aanalytics2
```

A config file, when present, still takes priority over environment variables — this is purely a fallback for when one isn't found. See [`config`](#config) for using individual parameters directly instead of environment variables.

---

## Starting the CLI

```bash
aanalytics2 [-cf config.json] [-cid companyId] [-rsid rsid] [-v] [-cmd "command"]
```

Arguments:

* `-cf` / `--config_file` : OPTIONAL : Path to the JSON config file. Default is `config_analytics.json` in the current directory.
* `-cid` / `--company_id` : OPTIONAL : Override the `globalCompanyId`. Takes precedence over the value in the config file.
* `-rsid` / `--report_suite_id` : OPTIONAL : Override the default RSID for the session.
* `-v` / `--verbose` : OPTIONAL : Enable verbose HTTP output.
* `-cmd` / `--command` : OPTIONAL : Run a single command non-interactively and exit immediately.

When the CLI starts, it loads the config file, acquires an OAuth token, resolves the company ID, and connects to the Analytics API.\
If no `companyId` is found in the flags or the config file, it calls `getCompanyId()` and displays a list of accessible companies for you to pick from.

```bash
# Use the default config file in the current directory
aanalytics2

# Specify a config file and a default RSID
aanalytics2 -cf ~/credentials/prod.json -rsid myprodrsid
```

---

## The prompt

The prompt tells you which company and report suite are active at all times.

```
# Company connected, no RSID set yet
mycompanyid>

# Company connected, RSID set
mycompanyid:myprodrsid>

# Inside the RequestCreator sub-shell
  [request:myprodrsid]>
```

Use `set_rsid` at any point to change the active report suite for the session, and `set_company_id` to switch companies (this also reconnects Analytics for the new company).

---

## Help

```
help                  # grouped list of all available commands
help <command>        # usage and argument details for a specific command
```

---

## Non-interactive mode

Pass `-cmd` to run a single command and exit. This is useful for scripting and cron jobs.

```bash
# Export all segments to CSV
aanalytics2 -cf config.json -cmd "get_segments -fn segments.csv"

# Filter dimensions for a given RSID
aanalytics2 -cf config.json -rsid myprodrsid -cmd "get_dimensions -f prop"
```

---

## Common arguments

Most commands share the following optional arguments:

* `-rsid` : OPTIONAL : Report suite ID for this command. When a session RSID is set with `set_rsid`, this argument is optional — the session value is used as the default. When no session RSID is set, `-rsid` is required.
* `-f` / `--filter` : OPTIONAL : Case-insensitive substring filter, matched against every column of each result row. Applied locally, after the data has already been retrieved from the API — it does not change what is requested from Adobe Analytics, it only narrows what is displayed/saved.
* `-sv` / `--save` : OPTIONAL : Save the command output to a CSV file at the given path (e.g. `-sv output.csv`). If omitted, the result is only printed to the terminal and nothing is written to disk.
* `-fn` / `--filename` : OPTIONAL : Used on `get_dimensions`, `get_metrics`, `get_calculated_metrics`, and `get_segments` — these commands always save their result to CSV, so there is no on/off switch for saving. `-fn` only overrides the default filename (e.g. `dimensions_<rsid>.csv`); omitting it just keeps the default name.
* `-d` / `--definition` : OPTIONAL or REQUIRED : Path to a JSON file used as the object definition or request body for create/update commands.
* `-n` : OPTIONAL : Limit the number of results returned. On `get_report` and `request_creator run`, `inf` (the default) retrieves all rows.

### Destructive operations

All delete commands print a confirmation prompt before executing:

```
Delete segment 's123456789'? [y/N]
```

Type `y` or `yes` to confirm. Anything else cancels the operation.

---

## Session commands

These commands manage the CLI session itself.

### `config`

Reload the configuration and reconnect.\
Useful when you want to switch credentials without restarting the shell.

```
config [-cf path/to/config.json] [-org_id ID] [-client_id ID] [-secret SECRET] [-scopes SCOPES] [-tech_id ID]
```

By default this loads `-cf` (or the current config file). If `-org_id`, `-client_id`, `-secret`, or `-scopes` are passed, they take priority over the config file and are used to build the credentials directly — any of them left unset falls back to the matching `AANALYTICS2_*` environment variable (see [Configuring without a file](#configuring-without-a-file)).

Example — switching to a different set of credentials without a file, e.g. sourced from a secrets manager into environment variables at deploy time:

```
mycompanyid> config -org_id 1234@AdobeOrg -client_id abcd1234 -secret ****** -scopes ent_analytics_bulk_ingest_sdk
Connected to company: othercompanyid
```

### `get_company_id`

List all Adobe Analytics companies accessible with the current credentials.

```
get_company_id [-sv file.csv]
```

### `set_company_id`

Set or change the company ID for the session, and reconnect Analytics against it.\
Useful after `get_company_id` reveals a company you want to switch to without restarting the shell.

```
set_company_id <company_id>
```

Example:

```
mycompanyid> set_company_id otherclientid
Company ID set to otherclientid
otherclientid>
```

### `set_rsid`

Set or change the default RSID for the session.\
Once set, all commands that require a report suite ID will use it automatically.

```
set_rsid <rsid>
```

Example:

```
mycompanyid> set_rsid myprodrsid
Default RSID set to myprodrsid
mycompanyid:myprodrsid>
```

### `whoami`

Display information about the currently authenticated user. Calls `getUserMe()`.

```
whoami
```

### `clear`

Clear the terminal screen. Also available inside the [RequestCreator sub-shell](#requestcreator-sub-shell).

```
clear
```

### `exit` / `quit`

Exit the CLI.

---

## Report Suites

### `get_report_suites`

List all report suites accessible to the current company.

```
get_report_suites [-f filter] [-ext] [-sv file.csv]
```

Arguments:
* `-f` : OPTIONAL : Filter by name substring.
* `-ext` : OPTIONAL : Include extended information.
* `-sv` : OPTIONAL : Save to CSV.

### `get_report_suite`

Get the full details for a single report suite. Uses the session RSID if no argument is passed.

```
get_report_suite <rsid>
```

### `get_virtual_report_suites`

List all virtual report suites.

```
get_virtual_report_suites [-f filter] [-ext] [-sv file.csv]
```

### `get_virtual_report_suite`

Get the full details for a single virtual report suite.

```
get_virtual_report_suite <vrsid>
```

### `create_virtual_report_suite`

Create a virtual report suite from a JSON definition file.\
The JSON file should contain the full VRS definition as expected by the Adobe Analytics API.

```
create_virtual_report_suite -d definition.json
```

### `delete_virtual_report_suite`

Delete a virtual report suite. Prompts for confirmation.

```
delete_virtual_report_suite <vrsid>
```

### `compare_report_suites`

Compare several report suites side-by-side for a given element type (dimensions, metrics, etc.).

```
compare_report_suites -rsids id1,id2,id3 [-el element] [-sv file.csv]
```

Arguments:
* `-rsids` : REQUIRED : Comma-separated list of RSIDs to compare.
* `-el` : OPTIONAL : Element to compare (e.g. `dimensions`, `metrics`). Default is `dimensions`.
* `-sv` : OPTIONAL : Save the comparison to CSV.

---

## Dimensions & Metrics

### `get_dimensions`

List all dimensions for a report suite. Always saved to CSV as `dimensions_<rsid>.csv` unless `-fn` overrides the filename.

```
get_dimensions [-rsid id] [-f filter] [-fn file.csv]
```

### `get_metrics`

List all metrics for a report suite. Always saved to CSV as `metrics_<rsid>.csv` unless `-fn` overrides the filename.

```
get_metrics [-rsid id] [-f filter] [-fn file.csv]
```

### `get_calculated_metrics`

List all calculated metrics. Always saved to CSV as `calculated_metrics.csv` unless `-fn` overrides the filename.

```
get_calculated_metrics [-n name] [-f filter] [-fn file.csv]
```

Arguments:
* `-n` : OPTIONAL : Exact name filter passed to the API.
* `-f` : OPTIONAL : Additional local substring filter.
* `-fn` : OPTIONAL : Override the default output CSV filename (the result is always saved).

### `get_calculated_metric`

Get full details for a single calculated metric.

```
get_calculated_metric <id>
```

### `create_calculated_metric`

Create a calculated metric from a JSON definition file.

```
create_calculated_metric -d definition.json
```

### `update_calculated_metric`

Update an existing calculated metric.

```
update_calculated_metric <id> -d definition.json
```

### `delete_calculated_metric`

Delete a calculated metric. Prompts for confirmation.

```
delete_calculated_metric <id>
```

### `get_calculated_functions`

List all functions available in the metric builder.

```
get_calculated_functions [-sv file.csv]
```

### `scan_calculated_metric`

Scan a calculated metric definition and report which components (segments, metrics) it references.

```
scan_calculated_metric <id> [-v]
```

---

## Segments

### `get_segments`

List segments. Always saved to CSV as `segments.csv` unless `-fn` overrides the filename.

```
get_segments [-n name] [-rsid id] [-f filter] [-fn file.csv]
```

### `get_segment`

Get full details for a single segment.

```
get_segment <id> [-full]
```

`-full` includes the full segment definition container.

### `create_segment`

Create a segment from a JSON definition file.

```
create_segment -d definition.json
```

### `update_segment`

Update an existing segment.

```
update_segment <id> -d definition.json
```

### `delete_segment`

Delete a segment. Prompts for confirmation.

```
delete_segment <id>
```

### `scan_segment`

Scan a segment definition and report which components it references.

```
scan_segment <id> [-v]
```

---

## Date Ranges

### `get_date_ranges`

List all date ranges.

```
get_date_ranges [-f filter] [-sv file.csv]
```

### `get_date_range`

Get full details for a single date range.

```
get_date_range <id>
```

### `create_date_range`

Create a date range from a JSON definition file.

```
create_date_range -d definition.json
```

### `update_date_range`

Update an existing date range.

```
update_date_range <id> -d definition.json
```

### `delete_date_range`

Delete a date range. Prompts for confirmation.

```
delete_date_range <id>
```

---

## Tags

### `get_tags`

List all tags.

```
get_tags [-sv file.csv]
```

### `get_tag`

Get details for a single tag.

```
get_tag <id>
```

### `get_component_tags`

List all tags attached to a specific component.

```
get_component_tags <componentId> -type <componentType>
```

Component type examples: `segment`, `calculatedMetric`, `dateRange`, `project`.

### `search_tags`

Search for components that carry specific tag names.

```
search_tags -n tagName1,tagName2 -type <componentType>
```

### `create_tags`

Create one or more tags from a JSON definition file.

```
create_tags -d definition.json
```

### `delete_tag`

Delete a tag. Prompts for confirmation.

```
delete_tag <id>
```

---

## Projects

### `get_projects`

List Workspace projects.

```
get_projects [-f filter] [-full] [-sv file.csv]
```

`-full` includes the full project definition for each result.

### `get_project`

Get full details for a single project.

```
get_project <id>
```

### `get_all_project_details`

Fetch full details for every project in the company.\
**Note**: this call retrieves each project definition individually and can be slow on large accounts. A warning is displayed before the request is sent.

```
get_all_project_details [-f filter] [-sv file.csv]
```

### `create_project`

Create a project from a JSON definition file.

```
create_project -d definition.json
```

### `update_project`

Update an existing project.

```
update_project <id> -d definition.json
```

### `delete_project`

Delete a project. Prompts for confirmation.

```
delete_project <id>
```

---

## Reporting

### `get_report`

Run a report from a saved JSON request file.\
The terminal displays the top 10 rows. The full result is always saved to a CSV file.

```
get_report -d request.json [-rsid id] [-n rows] [-sv output.csv]
```

Arguments:
* `-d` : REQUIRED : Path to the JSON report request file.
* `-rsid` : OPTIONAL : Override the RSID embedded in the request.
* `-n` : OPTIONAL : Maximum number of rows to retrieve. Default is `inf` (all rows).
* `-sv` : OPTIONAL : Output CSV filename. A timestamped name is generated automatically if omitted.

The JSON request file follows the Adobe Analytics API 2.0 report request format.\
You can build one interactively with the [RequestCreator sub-shell](#requestcreator-sub-shell) and save it with `save`.

```
mycompanyid:myprodrsid> get_report -d my_q1_report.json
```

### `get_top_items`

Get the top-ranked values for a dimension.

```
get_top_items <dimension> [-rsid id] [-dr dateRange] [-n limit] [-sv file.csv]
```

Arguments:
* `dimension` : REQUIRED : Dimension ID, e.g. `variables/eVar1`, `variables/page`.
* `-rsid` : OPTIONAL : Report suite (uses session default if set).
* `-dr` : OPTIONAL : Date range in `YYYY-MM-DD/YYYY-MM-DD` format.
* `-n` : OPTIONAL : Number of items to return. Default is 10.
* `-sv` : OPTIONAL : Save results to CSV.

Example:

```
mycompanyid:myprodrsid> get_top_items variables/page -dr 2024-01-01/2024-01-31 -n 25
```

### `decode_aa_requests`

Decode Adobe Analytics image request URLs from a file.

```
decode_aa_requests -d file [-sv output.csv]
```

---

## RequestCreator sub-shell

The `request_creator` command enters a dedicated sub-shell for building report requests interactively.\
It wraps the `RequestCreator` class — every method on that class is available as a sub-command.\
The session RSID is pre-loaded automatically when you enter the sub-shell.

```
mycompanyid:myprodrsid> request_creator
RequestCreator mode — type 'help' for commands, 'done' to return.
  [request:myprodrsid]>
```

The prompt shows the current RSID. Type `done` or press `Ctrl+D` to return to the main shell.

### Building the request

* `set_rsid <rsid>`\
  Set the report suite for this request. Also updates the sub-shell prompt.

* `set_dimension <dimension>`\
  Set the breakdown dimension, e.g. `variables/eVar1`.

* `set_date_range <range>` or `set_date_range -d <days> [--start DATE | --end DATE]` or `set_date_range -id <dateRangeId>`\
  Set (add or replace) the request's date range — the only command for this, replacing the old
  `update_date_range`. `<range>` accepts either the full timeframe
  (`2026-03-01T00:00:00.000/2026-03-31T23:59:59.999`) or a simplified date-only version
  (`2026-03-01/2026-03-31`), which is automatically expanded to the full timeframe.

  Use `-d <n>` instead to set the range to `n` days. Alone, it ends today (today and the `n-1` days
  before it). Combine it with `--start DATE` to anchor the window's start and compute the end
  (`start + n - 1` days), or with `--end DATE` to anchor the end and compute the start
  (`end - n + 1` days). `--start` and `--end` can also be combined without `-d` for an explicit range.

  Use `-id <dateRangeId>` instead to reference a saved/custom Date Range component (see
  `get_date_ranges` in the main shell) rather than a literal range.

  ```
  [request:myprodrsid]> set_date_range 2026-03-01/2026-03-31
  Date range set to: 2026-03-01T00:00:00.000/2026-03-31T23:59:59.999

  [request:myprodrsid]> set_date_range -d 7
  Date range set to: 2026-09-04T00:00:00.000/2026-09-10T23:59:59.999

  [request:myprodrsid]> set_date_range -d 5 --start 2026-03-01
  Date range set to: 2026-03-01T00:00:00.000/2026-03-05T23:59:59.999

  [request:myprodrsid]> set_date_range -id 586ac3ec71ade31753dc35d0
  Date range set to: 586ac3ec71ade31753dc35d0
  ```

* `set_limit <n>`\
  Set the number of result rows. Default is 100.

* `set_repeat_instance <true|false>`\
  Specify whether repeated instances should be counted.

* `set_none_behavior <true|false>`\
  Include or exclude None values in the results.

### Metrics

* `add_metric <metricId>`\
  Add a metric to the request. Repeatable, e.g. `add_metric metrics/visits`.

* `remove_metric <metricId>`\
  Remove a specific metric from the request.

* `remove_metrics`\
  Remove all metrics from the request.

* `get_report_metrics`\
  List all metrics currently in the request.

### Explore (read-only lookups against the Analytics API)

Handy while building a request, to check what's actually available in the report suite before adding it.\
Same behavior as their top-level counterparts: results are always saved to CSV (override the filename with `-fn`).

* `get_dimensions [-rsid id] [-f filter] [-fn file.csv]`\
  List dimensions available for a report suite. Uses the sub-shell's current RSID if `-rsid` is omitted.

* `get_metrics [-rsid id] [-f filter] [-fn file.csv]`\
  List metrics available for a report suite. Uses the sub-shell's current RSID if `-rsid` is omitted.\
  Not to be confused with `get_report_metrics`, which lists the metrics already added to this request.

* `get_calculated_metrics [-n name] [-f filter] [-fn file.csv]`\
  List all calculated metrics.

* `get_segments [-n name] [-rsid id] [-f filter] [-fn file.csv]`\
  List segments.

* `get_date_ranges [-f filter] [-fn file.csv]`\
  List saved/custom date ranges. Grab an `id` from here to use with `set_date_range -id <id>`.

### Filters

* `add_global_filter <id>`\
  Add a global filter. The `id` can be a segment ID or a date range ID.

* `remove_global_filter <id>`\
  Remove a global filter by its ID.

* `add_metric_filter <metricId> <filterId>`\
  Attach a filter to a specific metric.

* `set_search <clause>`\
  Add a search clause to the request.

* `remove_search`\
  Remove the search clause.

* `get_filters`\
  List all global filters currently in the request.

### Saving and loading

* `show`\
  Print the current request as formatted JSON.

* `save [filename]`\
  Save the request to a JSON file. A timestamped filename is generated if none is provided.

* `load <filename>`\
  Load a previously saved request from a JSON file, replacing the current state.

### Running

* `run`\
  Execute the current request. Displays the top 10 rows in the terminal and saves the full result to a timestamped CSV file. The CSV filename is printed on completion.

### `done`

Exit the RequestCreator sub-shell and return to the main shell.

### Example session

```
mycompanyid:myprodrsid> request_creator
  [request:myprodrsid]> set_dimension variables/eVar1
  [request:myprodrsid]> add_metric metrics/visits
  [request:myprodrsid]> add_metric metrics/pageviews
  [request:myprodrsid]> add_global_filter s123456789
  [request:myprodrsid]> update_date_range 2024-01-01/2024-03-31
  [request:myprodrsid]> set_limit 50
  [request:myprodrsid]> show
  [request:myprodrsid]> save my_q1_report.json
  [request:myprodrsid]> run
  [request:myprodrsid]> done
mycompanyid:myprodrsid>
```

The saved JSON file can be reused at any time with `get_report`:

```
mycompanyid:myprodrsid> get_report -d my_q1_report.json -sv full_q1.csv
```

---

## Scheduled Jobs

### `get_scheduled_jobs`

List all scheduled Workspace projects.

```
get_scheduled_jobs [-f filter] [-sv file.csv]
```

### `get_scheduled_job`

Get details for a single scheduled job.

```
get_scheduled_job <id>
```

### `create_scheduled_job`

Create a scheduled job for a project.\
The JSON definition file should contain the schedule parameters (`type`, `schedule`, `loginIds`, `emails`, etc.).

```
create_scheduled_job -pid <projectId> -d definition.json
```

### `update_scheduled_job`

Update an existing scheduled job.

```
update_scheduled_job <id> -d definition.json
```

### `delete_scheduled_job`

Delete a scheduled job. Prompts for confirmation.

```
delete_scheduled_job <id>
```

---

## Annotations

### `get_annotations`

List all annotations.

```
get_annotations [-sv file.csv]
```

### `get_annotation`

Get full details for a single annotation.

```
get_annotation <id>
```

### `create_annotation`

Create an annotation from a JSON definition file.\
The JSON file fields map to the `createAnnotation()` method parameters (`name`, `dateRange`, `rsid`, `metricIds`, etc.).

```
create_annotation -d definition.json
```

### `update_annotation`

Update an existing annotation.

```
update_annotation <id> -d definition.json
```

### `delete_annotation`

Delete an annotation. Prompts for confirmation.

```
delete_annotation <id>
```

---

## Alerts

### `get_alerts`

List all alerts.

```
get_alerts [-sv file.csv]
```

### `get_alert`

Get details for a single alert.

```
get_alert <id>
```

### `enable_alert`

Enable an alert.

```
enable_alert <id>
```

### `disable_alert`

Disable an alert.

```
disable_alert <id>
```

### `delete_alert`

Delete an alert. Prompts for confirmation.

```
delete_alert <id>
```

### `renew_alerts`

Renew one or more alerts.

```
renew_alerts -ids id1,id2,id3
```

---

## Users

### `get_users`

List all users in the company.

```
get_users [-f filter] [-sv file.csv]
```

### `whoami`

Display information about the currently authenticated user. Also available as a session command at the top level.

```
whoami
```

---

## Usage Logs

### `get_usage_logs`

Retrieve usage audit logs for a date range.

```
get_usage_logs -start YYYY-MM-DD -end YYYY-MM-DD [-login user] [-rsid id] [-sv file.csv]
```

Arguments:
* `-start` : REQUIRED : Start date in `YYYY-MM-DD` format.
* `-end` : REQUIRED : End date in `YYYY-MM-DD` format.
* `-login` : OPTIONAL : Filter by user login.
* `-rsid` : OPTIONAL : Filter by report suite.
* `-sv` : OPTIONAL : Save results to CSV.

Example:

```
mycompanyid> get_usage_logs -start 2024-01-01 -end 2024-01-31 -login jpiccini -sv jan_logs.csv
```

---

## Classifications

### `get_classification_datasets`

List all classification datasets for a report suite.

```
get_classification_datasets [-rsid id] [-sv file.csv]
```

### `get_classification_jobs`

List classification jobs for a dataset.

```
get_classification_jobs <datasetId> [-n n_results]
```

### `get_classification_job`

Get details for a single classification job.

```
get_classification_job <jobId>
```

### `get_classification_template`

Download the classification template for a dataset.

```
get_classification_template <datasetId> [-sv file.csv]
```

### `import_classification_json`

Import classification data from a JSON file.\
This uses the simpler single-call path (`importClassificationJSON`).

```
import_classification_json <datasetId> -d data.json [-n jobName]
```

### `create_export_classification`

Create a classification export job.

```
create_export_classification <datasetId> -n jobName [-d options.json]
```

### `delete_classification`

Delete a classification dataset. Prompts for confirmation.

```
delete_classification <datasetId>
```

---

## Data Feeds

### `get_data_feeds`

List all data feeds for a report suite.

```
get_data_feeds [-rsid id] [-sv file.csv]
```

### `get_data_feed`

Get details for a single data feed.

```
get_data_feed <id>
```

### `get_data_feed_requests`

List data feed request runs.

```
get_data_feed_requests [-ids feedId1,feedId2] [-status status] [-sv file.csv]
```

### `update_data_feed`

Update a data feed from a JSON definition file.

```
update_data_feed <id> -d definition.json
```

---

## Data Warehouse

### `get_dw_requests`

List Data Warehouse scheduled requests.

```
get_dw_requests [-rsid id] [-sv file.csv]
```

### `get_dw_request`

Get details for a single scheduled DW request.

```
get_dw_request <id>
```

### `get_dw_reports`

List Data Warehouse report runs.

```
get_dw_reports [-status status] [-sv file.csv]
```

---

## Data Sources

### `get_data_source_accounts`

List data source accounts for a report suite.

```
get_data_source_accounts [-rsid id] [-sv file.csv]
```

### `get_data_source_jobs`

List jobs for a data source account.

```
get_data_source_jobs <accountId> [-rsid id] [-status status] [-sv file.csv]
```

---

## Cloud Accounts & Locations

These commands manage the cloud accounts and locations used for Data Warehouse and Data Feed delivery.

### `get_cloud_accounts`

List all cloud accounts.

```
get_cloud_accounts [-type accountType] [-sv file.csv]
```

### `get_cloud_locations`

List all cloud locations.

```
get_cloud_locations [-sv file.csv]
```
