"""
aanalytics2 CLI — interactive REPL for Adobe Analytics API 2.0.

Entry point: aanalytics2 (registered via pyproject.toml [project.scripts])
Usage:
    aanalytics2 [-cf config.json] [-cid companyId] [-rsid rsid] [-v]
    aanalytics2 -cmd "get_segments -f mobile -sv"
"""

import argparse
import cmd
import json
import os
import shlex
import sys
import datetime
from pathlib import Path
from typing import Any, Optional

import pandas as pd
from rich.console import Console
from rich.panel import Panel

import aanalytics2
from aanalytics2 import Analytics, Login
from aanalytics2.requestCreator import RequestCreator
from aanalytics2.configs import importConfigFile, configure, createConfigFile
from aanalytics2.knowledgegraph import KnowledgeGraph

from ._helpers import (
    CLIError, SafeArgumentParser, login_required, str2bool,
    confirm_action, print_table, print_dataframe,
    save_df, save_list, load_json, resolve_rsid, console,
)

# ---------------------------------------------------------------------------
# Environment variables used as a fallback for credentials when no config
# file is found and no individual parameter was passed to `config`.
# ---------------------------------------------------------------------------
ENV_ORG_ID = "AANALYTICS2_ORG_ID"
ENV_CLIENT_ID = "AANALYTICS2_CLIENT_ID"
ENV_SECRET = "AANALYTICS2_SECRET"
ENV_SCOPES = "AANALYTICS2_SCOPES"
ENV_TECH_ID = "AANALYTICS2_TECH_ID"
ENV_COMPANY_ID = "AANALYTICS2_COMPANY_ID"
ENV_RSID = "AANALYTICS2_RSID"
ENV_PROXY = "AANALYTICS2_PROXY"

# ---------------------------------------------------------------------------
# Command group metadata (used by the custom help display)
# ---------------------------------------------------------------------------
COMMAND_GROUPS = {
    "Session": [
        "create_config_file", "config", "get_company_id", "set_company_id", "set_rsid", "whoami", "clear", "exit", "quit",
    ],
    "Report Suites": [
        "get_report_suites", "get_report_suite",
        "get_virtual_report_suites", "get_virtual_report_suite",
        "create_virtual_report_suite", "delete_virtual_report_suite",
        "compare_report_suites",
    ],
    "Dimensions & Metrics": [
        "get_dimensions", "get_metrics",
        "get_calculated_metrics", "get_calculated_metric",
        "create_calculated_metric", "update_calculated_metric",
        "delete_calculated_metric", "get_calculated_functions",
        "scan_calculated_metric",
    ],
    "Segments": [
        "get_segments", "get_segment",
        "create_segment", "update_segment", "delete_segment",
        "scan_segment",
    ],
    "Date Ranges": [
        "get_date_ranges", "get_date_range",
        "create_date_range", "update_date_range", "delete_date_range",
    ],
    "Tags": [
        "get_tags", "get_tag", "get_component_tags",
        "search_tags", "create_tags", "delete_tag",
    ],
    "Projects": [
        "get_projects", "get_project", "get_all_project_details",
        "create_project", "update_project", "delete_project",
    ],
    "Reporting": [
        "get_report", "get_top_items", "decode_aa_requests",
    ],
    "Request Creator": [
        "request_creator",
    ],
    "Scheduled Jobs": [
        "get_scheduled_jobs", "get_scheduled_job",
        "create_scheduled_job", "update_scheduled_job", "delete_scheduled_job",
    ],
    "Annotations": [
        "get_annotations", "get_annotation",
        "create_annotation", "update_annotation", "delete_annotation",
    ],
    "Alerts": [
        "get_alerts", "get_alert",
        "enable_alert", "disable_alert", "delete_alert", "renew_alerts",
    ],
    "Users": [
        "get_users",
    ],
    "Usage Logs": [
        "get_usage_logs",
    ],
    "Classifications": [
        "get_classification_datasets", "get_classification_jobs",
        "get_classification_job", "get_classification_template",
        "import_classification_json", "create_export_classification",
        "delete_classification",
    ],
    "Data Feeds": [
        "get_data_feeds", "get_data_feed",
        "get_data_feed_requests", "update_data_feed",
    ],
    "Data Warehouse": [
        "get_dw_requests", "get_dw_request", "get_dw_reports",
    ],
    "Data Sources": [
        "get_data_source_accounts", "get_data_source_jobs",
    ],
    "Cloud": [
        "get_cloud_accounts", "get_cloud_locations",
    ],
    "Knowledge Graph": [
        "build_knowledge_graph",
    ],
}


# ---------------------------------------------------------------------------
# RequestCreator nested sub-shell
# ---------------------------------------------------------------------------
class RequestCreatorShell(cmd.Cmd):
    """Nested REPL for building Analytics report requests interactively."""

    intro = "RequestCreator mode — type 'help' for commands, 'done' to return."

    def __init__(self, analytics: Analytics, session_rsid: Optional[str] = None):
        super().__init__()
        self.analytics = analytics
        self.rc = RequestCreator()
        if session_rsid:
            self.rc.setRSID(session_rsid)
        self._update_prompt()

    # ------------------------------------------------------------------
    # Prompt
    # ------------------------------------------------------------------
    def _update_prompt(self):
        rsid = getattr(self.rc, "rsid", None) or "no-rsid"
        self.prompt = f"  [request:{rsid}]> "

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _parse(self, parser: SafeArgumentParser, args: str):
        try:
            return parser.parse_args(shlex.split(args))
        except CLIError as exc:
            console.print(f"[red]{exc}[/red]")
            return None
        except SystemExit:
            return None

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------
    def do_set_rsid(self, args: Any):
        """set_rsid <rsid>  — Set the report suite ID for this request."""
        rsid = args.strip()
        if not rsid:
            console.print("[red]Usage: set_rsid <rsid>[/red]")
            return
        self.rc.setRSID(rsid)
        self._update_prompt()
        console.print(f"[green]RSID set to {rsid}[/green]")

    def do_set_dimension(self, args: Any):
        """set_dimension <dimension>  — Set the breakdown dimension (e.g. variables/eVar1)."""
        dim = args.strip()
        if not dim:
            console.print("[red]Usage: set_dimension <dimension>[/red]")
            return
        self.rc.setDimension(dim)
        console.print(f"[green]Dimension set to {dim}[/green]")

    def do_add_metric(self, args: Any):
        """add_metric <metricId>  — Add a metric to the request (repeatable)."""
        metric = args.strip()
        if not metric:
            console.print("[red]Usage: add_metric <metricId>[/red]")
            return
        self.rc.addMetric(metric)
        console.print(f"[green]Metric added: {metric}[/green]")

    def do_remove_metric(self, args: Any):
        """remove_metric <metricId>  — Remove a specific metric."""
        metric = args.strip()
        if not metric:
            console.print("[red]Usage: remove_metric <metricId>[/red]")
            return
        self.rc.removeMetric(metric)
        console.print(f"[yellow]Metric removed: {metric}[/yellow]")

    def do_remove_metrics(self, _args: Any):
        """remove_metrics  — Remove all metrics from the request."""
        self.rc.removeMetrics()
        console.print("[yellow]All metrics removed.[/yellow]")

    def do_add_global_filter(self, args: Any):
        """add_global_filter <id>  — Add a global filter (segment ID or date range ID)."""
        fid = args.strip()
        if not fid:
            console.print("[red]Usage: add_global_filter <filterId>[/red]")
            return
        self.rc.addGlobalFilter(fid)
        console.print(f"[green]Global filter added: {fid}[/green]")

    def do_remove_global_filter(self, args: Any):
        """remove_global_filter <id>  — Remove a global filter by ID."""
        fid = args.strip()
        if not fid:
            console.print("[red]Usage: remove_global_filter <filterId>[/red]")
            return
        self.rc.removeGlobalFilter(filterId=fid)
        console.print(f"[yellow]Global filter removed: {fid}[/yellow]")

    def do_add_metric_filter(self, args: Any):
        """add_metric_filter <metricId> <filterId>  — Add a filter to a specific metric."""
        parser = SafeArgumentParser(prog="add_metric_filter")
        parser.add_argument("metricId", metavar="metricId")
        parser.add_argument("filterId", metavar="filterId")
        args = self._parse(parser, args)
        if args is None:
            return
        self.rc.addMetricFilter(metricId=args.metricId, filterId=args.filterId)
        console.print(f"[green]Metric filter added: {args.filterId} → {args.metricId}[/green]")

    def do_set_limit(self, args: Any):
        """set_limit <n>  — Set the number of result rows (default 100)."""
        try:
            n = int(args.strip())
        except ValueError:
            console.print("[red]Usage: set_limit <integer>[/red]")
            return
        self.rc.setLimit(n)
        console.print(f"[green]Limit set to {n}[/green]")

    def do_set_search(self, args: Any):
        """set_search <clause>  — Add a search clause to the request."""
        clause = args.strip()
        if not clause:
            console.print("[red]Usage: set_search <clause>[/red]")
            return
        self.rc.setSearch(clause)
        console.print(f"[green]Search set to: {clause}[/green]")

    def do_remove_search(self, _args: Any):
        """remove_search  — Remove the search clause."""
        self.rc.removeSearch()
        console.print("[yellow]Search removed.[/yellow]")

    def do_set_repeat_instance(self, args: Any):
        """set_repeat_instance <true|false>  — Count repeat instances."""
        try:
            val = str2bool(args.strip())
        except argparse.ArgumentTypeError:
            console.print("[red]Usage: set_repeat_instance <true|false>[/red]")
            return
        self.rc.setRepeatInstance(val)
        console.print(f"[green]RepeatInstance set to {val}[/green]")

    def do_set_none_behavior(self, args: Any):
        """set_none_behavior <true|false>  — Return None values in results."""
        try:
            val = str2bool(args.strip())
        except argparse.ArgumentTypeError:
            console.print("[red]Usage: set_none_behavior <true|false>[/red]")
            return
        self.rc.setNoneBehavior(val)
        console.print(f"[green]NoneBehavior set to {val}[/green]")

    def do_set_date_range(self, args: Any):
        """set_date_range <range> | -d <days> [--start DATE | --end DATE] | -id <dateRangeId>
        — Set (add or replace) the dateRange global filter. Accepts a full timeframe
        (2026-03-01T00:00:00.000/2026-03-31T23:59:59.999) or a simplified date-only version
        (2026-03-01/2026-03-31), automatically expanded to the full timeframe. Use -d <n> instead
        to set the range to n days — ending today by default, or anchored on --start/--end. Use
        -id <dateRangeId> to reference a saved/custom Date Range component instead."""
        parser = SafeArgumentParser(prog="set_date_range")
        parser.add_argument("daterange", nargs="?", default=None, metavar="RANGE")
        parser.add_argument("-d", "--days", type=int, default=None, metavar="N",
                             help="Set the range to N days. Ends today unless --start or --end "
                                  "anchors it on a specific date instead.")
        parser.add_argument("--start", default=None, metavar="YYYY-MM-DD",
                             help="Anchor the range's start date. Combine with -d to compute the "
                                  "end date (start + N - 1 days), or with --end for an explicit range.")
        parser.add_argument("--end", default=None, metavar="YYYY-MM-DD",
                             help="Anchor the range's end date. Combine with -d to compute the "
                                  "start date (end - N + 1 days), or with --start for an explicit range.")
        parser.add_argument("-id", "--dateRangeId", default=None, metavar="ID",
                             help="Reference a saved/custom Date Range component by id "
                                  "(see get_date_ranges) instead of a literal date range.")
        args = self._parse(parser, args)
        if args is None:
            return
        if not args.daterange and args.days is None and not args.start and not args.end and not args.dateRangeId:
            console.print("[red]Usage: set_date_range <YYYY-MM-DD/YYYY-MM-DD> or "
                           "set_date_range -d <days> [--start DATE | --end DATE] or "
                           "set_date_range -id <dateRangeId>[/red]")
            return
        try:
            self.rc.setDateRange(dateRange=args.daterange, last=args.days,
                                  start=args.start, end=args.end, dateRangeId=args.dateRangeId)
        except ValueError as exc:
            console.print(f"[red]{exc}[/red]")
            return
        console.print(f"[green]Date range set to: {self.rc.getGlobalTimeRange()}[/green]")

    def do_get_report_metrics(self, _args: Any):
        """get_report_metrics  — List all metrics currently in the request."""
        metrics = self.rc.getMetrics()
        if metrics:
            for m in metrics:
                console.print(f"  • {m}")
        else:
            console.print("[yellow]No metrics set.[/yellow]")

    def do_get_filters(self, _args: Any):
        """get_filters  — List all global filters currently in the request."""
        filters = self.rc.getFilters()
        if filters:
            console.print_json(json.dumps(filters, indent=2))
        else:
            console.print("[yellow]No global filters set.[/yellow]")

    # ------------------------------------------------------------------
    # Explore — read-only lookups against the Analytics API, useful while
    # building a request to check what dimensions/metrics/segments exist.
    # ------------------------------------------------------------------
    def do_get_dimensions(self, args: Any):
        """get_dimensions [-rsid id] [-f filter] [-fn file.csv]  — List dimensions available for a report suite. Always saved to CSV (default dimensions_<rsid>.csv, override with -fn)."""
        parser = SafeArgumentParser(prog="get_dimensions")
        parser.add_argument("-rsid", default=None)
        parser.add_argument("-f", "--filter", default=None, metavar="TEXT",
                             help="Case-insensitive substring filter, matched against every column of each "
                                  "result row. Applied locally after the data is retrieved from the API — "
                                  "does not change what is requested from Adobe Analytics.")
        parser.add_argument("-fn", "--filename", default=None, metavar="FILE",
                             help="Override the default filename used to save the result to CSV. The result "
                                  "is always saved (default: dimensions_<rsid>.csv) — this only renames the file.")
        args = self._parse(parser, args)
        if args is None:
            return
        rsid = resolve_rsid(args.rsid, getattr(self.rc, "rsid", None))
        if rsid is None:
            return
        try:
            df = self.analytics.getDimensions(rsid=rsid)
            if args.filter and not df.empty:
                mask = df.apply(lambda r: args.filter.lower() in str(r).lower(), axis=1)
                df = df[mask]
            print_dataframe(df, title=f"Dimensions — {rsid}")
            save_df(df, args.filename or f"dimensions_{rsid}.csv")
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    def do_get_metrics(self, args: Any):
        """get_metrics [-rsid id] [-f filter] [-fn file.csv]  — List metrics available for a report suite. Always saved to CSV (default metrics_<rsid>.csv, override with -fn). For the metrics already added to this request, use get_report_metrics."""
        parser = SafeArgumentParser(prog="get_metrics")
        parser.add_argument("-rsid", default=None)
        parser.add_argument("-f", "--filter", default=None, metavar="TEXT",
                             help="Case-insensitive substring filter, matched against every column of each "
                                  "result row. Applied locally after the data is retrieved from the API — "
                                  "does not change what is requested from Adobe Analytics.")
        parser.add_argument("-fn", "--filename", default=None, metavar="FILE",
                             help="Override the default filename used to save the result to CSV. The result "
                                  "is always saved (default: metrics_<rsid>.csv) — this only renames the file.")
        args = self._parse(parser, args)
        if args is None:
            return
        rsid = resolve_rsid(args.rsid, getattr(self.rc, "rsid", None))
        if rsid is None:
            return
        try:
            df = self.analytics.getMetrics(rsid=rsid)
            if args.filter and not df.empty:
                mask = df.apply(lambda r: args.filter.lower() in str(r).lower(), axis=1)
                df = df[mask]
            print_dataframe(df, title=f"Metrics — {rsid}")
            save_df(df, args.filename or f"metrics_{rsid}.csv")
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    def do_get_calculated_metrics(self, args: Any):
        """get_calculated_metrics [-n name] [-f filter] [-fn file.csv]  — List calculated metrics. Always saved to CSV (default calculated_metrics.csv, override with -fn)."""
        parser = SafeArgumentParser(prog="get_calculated_metrics")
        parser.add_argument("-n", "--name", default=None, metavar="NAME")
        parser.add_argument("-f", "--filter", default=None, metavar="TEXT",
                             help="Case-insensitive substring filter, matched against every column of each "
                                  "result row. Applied locally after the data is retrieved from the API — "
                                  "does not change what is requested from Adobe Analytics.")
        parser.add_argument("-fn", "--filename", default=None, metavar="FILE",
                             help="Override the default filename used to save the result to CSV. The result "
                                  "is always saved (default: calculated_metrics.csv) — this only renames the file.")
        args = self._parse(parser, args)
        if args is None:
            return
        try:
            df = self.analytics.getCalculatedMetrics(name=args.name)
            if args.filter and not df.empty:
                mask = df.apply(lambda r: args.filter.lower() in str(r).lower(), axis=1)
                df = df[mask]
            print_dataframe(df, title="Calculated Metrics")
            save_df(df, args.filename or "calculated_metrics.csv")
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    def do_get_segments(self, args: Any):
        """get_segments [-n name] [-rsid id] [-f filter] [-fn file.csv]  — List segments. Always saved to CSV (default segments.csv, override with -fn)."""
        parser = SafeArgumentParser(prog="get_segments")
        parser.add_argument("-n", "--name", default=None, metavar="NAME")
        parser.add_argument("-rsid", default=None)
        parser.add_argument("-f", "--filter", default=None, metavar="TEXT",
                             help="Case-insensitive substring filter, matched against every column of each "
                                  "result row. Applied locally after the data is retrieved from the API — "
                                  "does not change what is requested from Adobe Analytics.")
        parser.add_argument("-fn", "--filename", default=None, metavar="FILE",
                             help="Override the default filename used to save the result to CSV. The result "
                                  "is always saved (default: segments.csv) — this only renames the file.")
        args = self._parse(parser, args)
        if args is None:
            return
        rsid_arg = args.rsid or getattr(self.rc, "rsid", None)
        rsid_list = [rsid_arg] if rsid_arg else None
        try:
            df = self.analytics.getSegments(name=args.name, rsids_list=rsid_list)
            if args.filter and not df.empty:
                mask = df.apply(lambda r: args.filter.lower() in str(r).lower(), axis=1)
                df = df[mask]
            print_dataframe(df, title="Segments")
            save_df(df, args.filename or "segments.csv")
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    def do_get_date_ranges(self, args: Any):
        """get_date_ranges [-f filter] [-fn file.csv]  — List date ranges. Always saved to CSV (default date_ranges.csv, override with -fn). Reference one in a request with 'set_date_range -id <id>'."""
        parser = SafeArgumentParser(prog="get_date_ranges")
        parser.add_argument("-f", "--filter", default=None, metavar="TEXT",
                             help="Case-insensitive substring filter, matched against every column of each "
                                  "result row. Applied locally after the data is retrieved from the API — "
                                  "does not change what is requested from Adobe Analytics.")
        parser.add_argument("-fn", "--filename", default=None, metavar="FILE",
                             help="Override the default filename used to save the result to CSV. The result "
                                  "is always saved (default: date_ranges.csv) — this only renames the file.")
        args = self._parse(parser, args)
        if args is None:
            return
        try:
            df = self.analytics.getDateRanges()
            if args.filter and not df.empty:
                mask = df.apply(lambda r: args.filter.lower() in str(r).lower(), axis=1)
                df = df[mask]
            print_dataframe(df, title="Date Ranges")
            save_df(df, args.filename or "date_ranges.csv")
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    def do_show(self, _args: Any):
        """show  — Print the current request as formatted JSON."""
        console.print_json(json.dumps(self.rc.to_dict(), indent=2))

    def do_save(self, args: Any):
        """save [filename]  — Save the current request to a JSON file."""
        filename = args.strip() or None
        self.rc.save(fileName=filename)
        console.print(f"[green]Request saved.[/green]")

    def do_load(self, args: Any):
        """load <filename>  — Load a request from a JSON file."""
        path = args.strip()
        if not path:
            console.print("[red]Usage: load <filename>[/red]")
            return
        data = load_json(path)
        if data is None:
            return
        self.rc = RequestCreator(request=data)
        self._update_prompt()
        console.print(f"[green]Request loaded from {path}[/green]")

    def do_run(self, _args: Any):
        """run  — Execute the request and show the top 10 rows; save all to CSV."""
        req = self.rc.to_dict()
        if not req.get("rsid"):
            console.print("[red]RSID not set. Run 'set_rsid <rsid>' first.[/red]")
            return
        try:
            workspace = self.analytics.getReport2(request=req, n_results="inf")
            if not hasattr(workspace, "dataframe"):
                console.print_json(json.dumps(workspace, indent=2, default=str))
                return
            df = workspace.dataframe
            print_dataframe(df, title="Report result (top 10)", max_rows=10)
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"report_{req['rsid']}_{ts}.csv"
            save_df(df, filename)
        except Exception as exc:
            console.print(f"[red]Report failed: {exc}[/red]")

    def do_done(self, _args: Any):
        """done  — Exit RequestCreator mode and return to the main shell."""
        return True

    def do_clear(self, _args: Any):
        """clear  — Clear the terminal screen."""
        console.clear()

    def do_EOF(self, _args: Any):
        console.print()
        return True

    def default(self, args: Any):
        console.print(f"[red]Unknown command: {args.split()[0]}  (type 'help' for commands)[/red]")


# ---------------------------------------------------------------------------
# Main Analytics shell
# ---------------------------------------------------------------------------
class AnalyticsShell(cmd.Cmd):
    """Interactive REPL for the Adobe Analytics API 2.0."""

    # cmd.Cmd prints `intro` with a raw stdout.write, which does not interpret rich
    # markup — leaving literal "[bold]...[/bold]" on screen. Keep intro unset and
    # print the styled banner ourselves in preloop() via the rich console instead.
    intro = None
    _banner = "\n[bold blue]aanalytics2[/bold blue] CLI  —  type 'help' for grouped commands, 'exit' to quit.\n"

    def preloop(self) -> None:
        console.print(self._banner)

    def __init__(
        self,
        config_file: str = "config_analytics.json",
        company_id: Optional[str] = None,
        rsid: Optional[str] = None,
        verbose: bool = False,
    ):
        super().__init__()
        self.analytics: Optional[Analytics] = None
        self.login_obj: Optional[Login] = None
        self.cfg = None
        self.company_id: Optional[str] = company_id
        self.rsid: Optional[str] = rsid
        self.verbose = verbose
        self.config_file = config_file
        self._update_prompt()
        self._startup()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _update_prompt(self):
        cid = self.company_id or "not-connected"
        self.prompt = f"{cid}:{self.rsid}> " if self.rsid else f"{cid}> "

    def _startup(
        self,
        org_id: Optional[str] = None,
        client_id: Optional[str] = None,
        secret: Optional[str] = None,
        scopes: Optional[str] = None,
        tech_id: Optional[str] = None,
        proxy: Optional[str] = None,
    ):
        """Load config, authenticate, and connect to Analytics."""
        try:
            cfg = self._resolve_config(org_id, client_id, secret, scopes, tech_id, proxy)
            if cfg is None:
                return
            self.cfg = cfg
            self.login_obj = Login(config=cfg)

            # Resolve company_id interactively if still unknown
            if self.company_id is None:
                self.company_id = self._pick_company_id()
                if self.company_id is None:
                    console.print("[red]No company ID selected. Use 'get_company_id' then 'config'.[/red]")
                    return

            self.analytics = self.login_obj.createAnalyticsConnection(companyId=self.company_id)
            self._update_prompt()
            console.print(f"[green]Connected to company: {self.company_id}[/green]")
            if self.rsid:
                console.print(f"[green]Default RSID: {self.rsid}[/green]")
        except FileNotFoundError as exc:
            console.print(f"[red]Config file not found: {exc}[/red]")
        except Exception as exc:
            console.print(f"[red]Startup error: {exc}[/red]")

    def _resolve_config(
        self,
        org_id: Optional[str],
        client_id: Optional[str],
        secret: Optional[str],
        scopes: Optional[str],
        tech_id: Optional[str],
        proxy: Optional[str] = None,
    ):
        """Resolve credentials into a ConfigObj, in order of priority:

        1. Individual parameters passed explicitly to `config` (org_id/client_id/secret/scopes/tech_id).
        2. The config file at ``self.config_file``, when no individual parameter was passed and the
           file exists — unchanged default behaviour.
        3. Environment variables (AANALYTICS2_ORG_ID, AANALYTICS2_CLIENT_ID, AANALYTICS2_SECRET,
           AANALYTICS2_SCOPES, AANALYTICS2_TECH_ID), used to fill in whatever wasn't passed explicitly,
           as a last resort when no config file is found.

        Also resolves company_id/rsid, from the config file or from AANALYTICS2_COMPANY_ID /
        AANALYTICS2_RSID, when not already set by flags.

        proxy (e.g. "http://proxy.example.com:8080") is entirely optional in every path below —
        omit it to connect directly, with no proxy involved. When passed explicitly (-proxy flag
        or AANALYTICS2_PROXY), it overrides whatever the config file may already contain, so a
        proxy can be applied on top of an existing config file without editing it.
        """
        explicit_params = any([org_id, client_id, secret, scopes, tech_id])

        if not explicit_params and Path(self.config_file).exists():
            # Load raw JSON to extract CLI-specific fields (companyId, rsid)
            raw = load_json(self.config_file)
            if raw is None:
                return None
            if self.company_id is None:
                self.company_id = raw.get("companyId") or raw.get("company_id")
            if self.rsid is None:
                self.rsid = raw.get("rsid")
            # Build ConfigObj via importConfigFile (handles OAuth token acquisition)
            cfg = importConfigFile(self.config_file, return_object=True)
            proxy = proxy or os.environ.get(ENV_PROXY)
            if proxy:
                cfg.config["proxy"] = proxy
            return cfg

        org_id = org_id or os.environ.get(ENV_ORG_ID)
        client_id = client_id or os.environ.get(ENV_CLIENT_ID)
        secret = secret or os.environ.get(ENV_SECRET)
        scopes = scopes or os.environ.get(ENV_SCOPES)
        tech_id = tech_id or os.environ.get(ENV_TECH_ID)
        proxy = proxy or os.environ.get(ENV_PROXY)

        if not (org_id and client_id and secret and scopes):
            console.print(
                f"[red]Could not load config file: {self.config_file}[/red]\n"
                "[red]No config file found and credentials are incomplete. Provide -org_id, -client_id, "
                "-secret and -scopes (or set the AANALYTICS2_ORG_ID, AANALYTICS2_CLIENT_ID, "
                "AANALYTICS2_SECRET and AANALYTICS2_SCOPES environment variables).[/red]"
            )
            return None

        if self.company_id is None:
            self.company_id = os.environ.get(ENV_COMPANY_ID)
        if self.rsid is None:
            self.rsid = os.environ.get(ENV_RSID)

        return configure(
            org_id=org_id, client_id=client_id, secret=secret,
            scopes=scopes, tech_id=tech_id, proxy=proxy, return_object=True,
        )

    def _pick_company_id(self) -> Optional[str]:
        """Call getCompanyId and let the user pick interactively."""
        try:
            companies = self.login_obj.getCompanyId()
            if not companies:
                return None
            console.print("[bold]Available companies:[/bold]")
            for i, company in enumerate(companies):
                cid = company.get("globalCompanyId", "")
                name = company.get("companyName", "")
                console.print(f"  [{i}] {cid}  ({name})")
            choice = input("Select company number [0]: ").strip() or "0"
            return companies[int(choice)].get("globalCompanyId")
        except (KeyboardInterrupt, EOFError, ValueError, IndexError):
            return None

    def _parse(self, parser: SafeArgumentParser, args: str):
        try:
            return parser.parse_args(shlex.split(args))
        except CLIError as exc:
            console.print(f"[red]{exc}[/red]")
            return None
        except SystemExit:
            return None

    def default(self, args: Any):
        if args.strip():
            console.print(f"[red]Unknown command: {args.split()[0]}  (type 'help' for commands)[/red]")

    # ------------------------------------------------------------------
    # Help system — grouped display
    # ------------------------------------------------------------------
    def do_help(self, arg):
        """Show grouped command list, or detail for a specific command."""
        if arg:
            # Delegate to default per-command help (uses docstring)
            super().do_help(arg)
            return
        console.print()
        for group, cmds in COMMAND_GROUPS.items():
            available = [c for c in cmds if hasattr(self, f"do_{c}")]
            if available:
                console.print(f"[bold cyan]{group}[/bold cyan]")
                for c in available:
                    doc = getattr(self, f"do_{c}").__doc__ or ""
                    brief = doc.strip().splitlines()[0] if doc.strip() else ""
                    console.print(f"  [green]{c:<35}[/green]{brief}")
                console.print()

    # ------------------------------------------------------------------
    # Group 0 — Session / System
    # ------------------------------------------------------------------
    def do_config(self, args: Any):
        """config [-cf path] [-org_id ID] [-client_id ID] [-secret SECRET] [-scopes SCOPES] [-tech_id ID] [-proxy URL]  — Reload configuration (and reconnect). Uses a config file by default; if none is found, falls back to these individual parameters or their AANALYTICS2_* environment variables."""
        parser = SafeArgumentParser(prog="config")
        parser.add_argument("-cf", "--config_file", default=None)
        parser.add_argument("-org_id", "--org_id", default=None, metavar="ORG_ID",
                             help=f"Organization ID. Falls back to the {ENV_ORG_ID} environment "
                                  "variable when omitted.")
        parser.add_argument("-client_id", "--client_id", default=None, metavar="CLIENT_ID",
                             help=f"API/client ID. Falls back to the {ENV_CLIENT_ID} environment "
                                  "variable when omitted.")
        parser.add_argument("-secret", "--secret", default=None, metavar="SECRET",
                             help=f"Client secret. Falls back to the {ENV_SECRET} environment "
                                  "variable when omitted.")
        parser.add_argument("-scopes", "--scopes", default=None, metavar="SCOPES",
                             help=f"OAuth Server-to-Server scopes. Falls back to the {ENV_SCOPES} "
                                  "environment variable when omitted.")
        parser.add_argument("-tech_id", "--tech_id", default=None, metavar="TECH_ID",
                             help=f"Technical account ID. Falls back to the {ENV_TECH_ID} environment "
                                  "variable when omitted.")
        parser.add_argument("-proxy", "--proxy", default=None, metavar="URL",
                             help="Proxy URL to route all requests through (e.g. http://proxy.example.com:8080), "
                                  f"for organizations that require one. Falls back to the {ENV_PROXY} environment "
                                  "variable, then to any \"proxy\" set in the config file. Optional — omit it to "
                                  "connect without a proxy.")
        args = self._parse(parser, args)
        if args is None:
            return
        if args.config_file:
            self.config_file = args.config_file
        self.analytics = None
        self.login_obj = None
        self._startup(
            org_id=args.org_id,
            client_id=args.client_id,
            secret=args.secret,
            scopes=args.scopes,
            tech_id=args.tech_id,
            proxy=args.proxy,
        )

    def do_create_config_file(self, args: Any):
        """create_config_file [-fn file.json] [-auth_type oauthV2] [-cid company_id] [-rsid rsid] [-proxy URL]  — Create a config file template with placeholder credentials to fill in (default: config_analytics_template.json). Does not require a connection."""
        parser = SafeArgumentParser(prog="create_config_file")
        parser.add_argument("-fn", "--filename", default="config_analytics_template.json", metavar="FILE",
                             help="Destination path for the generated config file "
                                  "(default: config_analytics_template.json).")
        parser.add_argument("-auth_type", "--auth_type", default="oauthV2", metavar="TYPE",
                             help="OAuth type to use in the template (default: oauthV2).")
        parser.add_argument("-cid", "--company_id", default=None, metavar="COMPANY_ID",
                             help="Pre-fill the globalCompanyId in the generated file, so the CLI can "
                                  "skip the interactive company-selection prompt once credentials are filled in.")
        parser.add_argument("-rsid", "--rsid", default=None, metavar="RSID",
                             help="Pre-fill the default report suite ID in the generated file.")
        parser.add_argument("-proxy", "--proxy", default=None, metavar="URL",
                             help="Pre-fill a proxy URL in the generated file (e.g. http://proxy.example.com:8080), "
                                  "for organizations that need to reach the Adobe Analytics API through a proxy. "
                                  "Optional — omit it (default) to leave the file without a proxy.")
        args = self._parse(parser, args)
        if args is None:
            return
        try:
            createConfigFile(destination=args.filename, auth_type=args.auth_type,
                              verbose=self.verbose, company_id=args.company_id, rsid=args.rsid,
                              proxy=args.proxy)
            console.print(f"[green]Config file template created → {args.filename}[/green]")
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    def do_get_company_id(self, args: Any):
        """get_company_id [-sv file.csv]  — List all companies accessible with the current credentials."""
        parser = SafeArgumentParser(prog="get_company_id")
        parser.add_argument("-sv", "--save", default=None, metavar="FILE",
                             help="Save the result to a CSV file at this path. Optional — if omitted, "
                                  "the result is only printed to the terminal and nothing is written to disk.")
        args = self._parse(parser, args)
        if args is None:
            return
        if self.login_obj is None:
            console.print("[red]Not connected. Run 'config' first.[/red]")
            return
        try:
            companies = self.login_obj.getCompanyId()
            if not companies:
                console.print("[yellow]No companies found.[/yellow]")
                return
            print_table(
                companies,
                columns=["globalCompanyId", "companyName"],
                title="Available Companies",
            )
            if args.save:
                save_list(companies, args.save)
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    def do_set_company_id(self, args: Any):
        """set_company_id <company_id>  — Set (or change) the company ID and reconnect for this session."""
        company_id = args.strip()
        if not company_id:
            console.print("[red]Usage: set_company_id <company_id>[/red]")
            return
        if self.login_obj is None:
            console.print("[red]Not connected. Run 'config' first.[/red]")
            return
        try:
            self.analytics = self.login_obj.createAnalyticsConnection(companyId=company_id)
            self.company_id = company_id
            self._update_prompt()
            console.print(f"[green]Company ID set to {company_id}[/green]")
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    def do_set_rsid(self, args: Any):
        """set_rsid <rsid>  — Set (or change) the default RSID for this session."""
        rsid = args.strip()
        if not rsid:
            console.print("[red]Usage: set_rsid <rsid>[/red]")
            return
        self.rsid = rsid
        self._update_prompt()
        console.print(f"[green]Default RSID set to {rsid}[/green]")

    @login_required
    def do_whoami(self, _args: Any):
        """whoami  — Show information about the currently authenticated user."""
        try:
            user = self.analytics.getUserMe()
            console.print_json(json.dumps(user, indent=2))
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    def do_clear(self, _args: Any):
        """clear  — Clear the terminal screen."""
        console.clear()

    def do_exit(self, _args: Any):
        """exit  — Exit the CLI."""
        console.print("[bold]Goodbye![/bold]")
        return True

    def do_quit(self, _args: Any):
        """quit  — Exit the CLI."""
        return self.do_exit(_args)

    def do_EOF(self, _args: Any):
        console.print()
        return True

    # ------------------------------------------------------------------
    # Group 1 — Report Suites
    # ------------------------------------------------------------------
    @login_required
    def do_get_report_suites(self, args: Any):
        """get_report_suites [-f filter] [-ext] [-sv file.csv]  — List all report suites."""
        parser = SafeArgumentParser(prog="get_report_suites")
        parser.add_argument("-f", "--filter", default=None, metavar="TEXT",
                             help="Case-insensitive substring filter, matched against every column of each "
                                  "result row. Applied locally after the data is retrieved from the API — "
                                  "does not change what is requested from Adobe Analytics.")
        parser.add_argument("-ext", "--extended", action="store_true")
        parser.add_argument("-sv", "--save", default=None, metavar="FILE",
                             help="Save the result to a CSV file at this path. Optional — if omitted, "
                                  "the result is only printed to the terminal and nothing is written to disk.")
        args = self._parse(parser, args)
        if args is None:
            return
        try:
            df = self.analytics.getReportSuites(txt=args.filter, extended_info=args.extended)
            print_dataframe(df, title="Report Suites")
            if args.save:
                save_df(df, args.save)
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    @login_required
    def do_get_report_suite(self, args: Any):
        """get_report_suite <rsid>  — Get details for a single report suite."""
        rsid = args.strip()
        if not rsid:
            rsid = self.rsid
        if not rsid:
            console.print("[red]Usage: get_report_suite <rsid>[/red]")
            return
        try:
            data = self.analytics.getReportSuite(rsid=rsid)
            console.print_json(json.dumps(data, indent=2))
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    @login_required
    def do_get_virtual_report_suites(self, args: Any):
        """get_virtual_report_suites [-f filter] [-ext] [-sv file.csv]  — List virtual report suites."""
        parser = SafeArgumentParser(prog="get_virtual_report_suites")
        parser.add_argument("-f", "--filter", default=None, metavar="TEXT",
                             help="Case-insensitive substring filter, matched against every column of each "
                                  "result row. Applied locally after the data is retrieved from the API — "
                                  "does not change what is requested from Adobe Analytics.")
        parser.add_argument("-ext", "--extended", action="store_true")
        parser.add_argument("-sv", "--save", default=None, metavar="FILE",
                             help="Save the result to a CSV file at this path. Optional — if omitted, "
                                  "the result is only printed to the terminal and nothing is written to disk.")
        args = self._parse(parser, args)
        if args is None:
            return
        try:
            df = self.analytics.getVirtualReportSuites(extended_info=args.extended)
            if args.filter:
                df = df[df.apply(lambda r: args.filter.lower() in str(r).lower(), axis=1)]
            print_dataframe(df, title="Virtual Report Suites")
            if args.save:
                save_df(df, args.save)
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    @login_required
    def do_get_virtual_report_suite(self, args: Any):
        """get_virtual_report_suite <vrsid>  — Get details for a single virtual report suite."""
        vrsid = args.strip()
        if not vrsid:
            console.print("[red]Usage: get_virtual_report_suite <vrsid>[/red]")
            return
        try:
            data = self.analytics.getVirtualReportSuite(vrsid=vrsid)
            console.print_json(json.dumps(data, indent=2))
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    @login_required
    def do_create_virtual_report_suite(self, args: Any):
        """create_virtual_report_suite -d def.json  — Create a VRS from a JSON definition file."""
        parser = SafeArgumentParser(prog="create_virtual_report_suite")
        parser.add_argument("-d", "--definition", required=True, metavar="FILE")
        args = self._parse(parser, args)
        if args is None:
            return
        data = load_json(args.definition)
        if data is None:
            return
        try:
            result = self.analytics.createVirtualReportSuite(data_dict=data)
            console.print_json(json.dumps(result, indent=2))
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    @login_required
    def do_delete_virtual_report_suite(self, args: Any):
        """delete_virtual_report_suite <vrsid>  — Delete a virtual report suite (prompts for confirmation)."""
        vrsid = args.strip()
        if not vrsid:
            console.print("[red]Usage: delete_virtual_report_suite <vrsid>[/red]")
            return
        if not confirm_action(f"Delete virtual report suite '{vrsid}'? [y/N] "):
            console.print("[yellow]Cancelled.[/yellow]")
            return
        try:
            result = self.analytics.deleteVirtualReportSuite(vrsid=vrsid)
            console.print(f"[green]{result}[/green]")
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    @login_required
    def do_compare_report_suites(self, args: Any):
        """compare_report_suites -rsids id1,id2 [-el element] [-sv file.csv]  — Compare report suites."""
        parser = SafeArgumentParser(prog="compare_report_suites")
        parser.add_argument("-rsids", "--rsids", required=True, metavar="ID1,ID2,...")
        parser.add_argument("-el", "--element", default="dimensions", metavar="ELEMENT")
        parser.add_argument("-sv", "--save", default=None, metavar="FILE",
                             help="Save the result to a CSV file at this path. Optional — if omitted, "
                                  "the result is only printed to the terminal and nothing is written to disk.")
        args = self._parse(parser, args)
        if args is None:
            return
        rsid_list = [r.strip() for r in args.rsids.split(",")]
        try:
            df = self.analytics.compareReportSuites(listRsids=rsid_list, element=args.element)
            print_dataframe(df, title="Report Suite Comparison")
            if args.save:
                save_df(df, args.save)
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    # ------------------------------------------------------------------
    # Group 2 — Dimensions & Metrics
    # ------------------------------------------------------------------
    @login_required
    def do_get_dimensions(self, args: Any):
        """get_dimensions [-rsid id] [-f filter] [-fn file.csv]  — List dimensions for a report suite. Always saved to CSV (default dimensions_<rsid>.csv, override with -fn)."""
        parser = SafeArgumentParser(prog="get_dimensions")
        parser.add_argument("-rsid", default=None)
        parser.add_argument("-f", "--filter", default=None, metavar="TEXT",
                             help="Case-insensitive substring filter, matched against every column of each "
                                  "result row. Applied locally after the data is retrieved from the API — "
                                  "does not change what is requested from Adobe Analytics.")
        parser.add_argument("-fn", "--filename", default=None, metavar="FILE",
                             help="Override the default filename used to save the result to CSV. The result "
                                  "is always saved (default: dimensions_<rsid>.csv) — this only renames the file.")
        args = self._parse(parser, args)
        if args is None:
            return
        rsid = resolve_rsid(args.rsid, self.rsid)
        if rsid is None:
            return
        try:
            df = self.analytics.getDimensions(rsid=rsid)
            if args.filter and not df.empty:
                mask = df.apply(lambda r: args.filter.lower() in str(r).lower(), axis=1)
                df = df[mask]
            print_dataframe(df, title=f"Dimensions — {rsid}")
            save_df(df, args.filename or f"dimensions_{rsid}.csv")
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    @login_required
    def do_get_metrics(self, args: Any):
        """get_metrics [-rsid id] [-f filter] [-fn file.csv]  — List metrics for a report suite. Always saved to CSV (default metrics_<rsid>.csv, override with -fn)."""
        parser = SafeArgumentParser(prog="get_metrics")
        parser.add_argument("-rsid", default=None)
        parser.add_argument("-f", "--filter", default=None, metavar="TEXT",
                             help="Case-insensitive substring filter, matched against every column of each "
                                  "result row. Applied locally after the data is retrieved from the API — "
                                  "does not change what is requested from Adobe Analytics.")
        parser.add_argument("-fn", "--filename", default=None, metavar="FILE",
                             help="Override the default filename used to save the result to CSV. The result "
                                  "is always saved (default: metrics_<rsid>.csv) — this only renames the file.")
        args = self._parse(parser, args)
        if args is None:
            return
        rsid = resolve_rsid(args.rsid, self.rsid)
        if rsid is None:
            return
        try:
            df = self.analytics.getMetrics(rsid=rsid)
            if args.filter and not df.empty:
                mask = df.apply(lambda r: args.filter.lower() in str(r).lower(), axis=1)
                df = df[mask]
            print_dataframe(df, title=f"Metrics — {rsid}")
            save_df(df, args.filename or f"metrics_{rsid}.csv")
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    @login_required
    def do_get_calculated_metrics(self, args: Any):
        """get_calculated_metrics [-n name] [-f filter] [-fn file.csv]  — List calculated metrics. Always saved to CSV (default calculated_metrics.csv, override with -fn)."""
        parser = SafeArgumentParser(prog="get_calculated_metrics")
        parser.add_argument("-n", "--name", default=None, metavar="NAME")
        parser.add_argument("-f", "--filter", default=None, metavar="TEXT",
                             help="Case-insensitive substring filter, matched against every column of each "
                                  "result row. Applied locally after the data is retrieved from the API — "
                                  "does not change what is requested from Adobe Analytics.")
        parser.add_argument("-fn", "--filename", default=None, metavar="FILE",
                             help="Override the default filename used to save the result to CSV. The result "
                                  "is always saved (default: calculated_metrics.csv) — this only renames the file.")
        args = self._parse(parser, args)
        if args is None:
            return
        try:
            df = self.analytics.getCalculatedMetrics(name=args.name)
            if args.filter and not df.empty:
                mask = df.apply(lambda r: args.filter.lower() in str(r).lower(), axis=1)
                df = df[mask]
            print_dataframe(df, title="Calculated Metrics")
            save_df(df, args.filename or "calculated_metrics.csv")
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    @login_required
    def do_get_calculated_metric(self, args: Any):
        """get_calculated_metric <id>  — Get details for a single calculated metric."""
        cid = args.strip()
        if not cid:
            console.print("[red]Usage: get_calculated_metric <id>[/red]")
            return
        try:
            data = self.analytics.getCalculatedMetric(calculatedMetricId=cid)
            console.print_json(json.dumps(data, indent=2))
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    @login_required
    def do_create_calculated_metric(self, args: Any):
        """create_calculated_metric -d def.json  — Create a calculated metric from a JSON definition."""
        parser = SafeArgumentParser(prog="create_calculated_metric")
        parser.add_argument("-d", "--definition", required=True, metavar="FILE")
        args = self._parse(parser, args)
        if args is None:
            return
        data = load_json(args.definition)
        if data is None:
            return
        try:
            result = self.analytics.createCalculatedMetric(metricJSON=data)
            console.print_json(json.dumps(result, indent=2))
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    @login_required
    def do_update_calculated_metric(self, args: Any):
        """update_calculated_metric <id> -d def.json  — Update a calculated metric."""
        parser = SafeArgumentParser(prog="update_calculated_metric")
        parser.add_argument("id", metavar="ID")
        parser.add_argument("-d", "--definition", required=True, metavar="FILE")
        args = self._parse(parser, args)
        if args is None:
            return
        data = load_json(args.definition)
        if data is None:
            return
        try:
            result = self.analytics.updateCalculatedMetric(calcID=args.id, calcJSON=data)
            console.print_json(json.dumps(result, indent=2))
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    @login_required
    def do_delete_calculated_metric(self, args: Any):
        """delete_calculated_metric <id>  — Delete a calculated metric (prompts for confirmation)."""
        cid = args.strip()
        if not cid:
            console.print("[red]Usage: delete_calculated_metric <id>[/red]")
            return
        if not confirm_action(f"Delete calculated metric '{cid}'? [y/N] "):
            console.print("[yellow]Cancelled.[/yellow]")
            return
        try:
            result = self.analytics.deleteCalculatedMetric(calcID=cid)
            console.print(f"[green]{result}[/green]")
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    @login_required
    def do_get_calculated_functions(self, args: Any):
        """get_calculated_functions [-sv file.csv]  — List all functions available in the metric builder."""
        parser = SafeArgumentParser(prog="get_calculated_functions")
        parser.add_argument("-sv", "--save", default=None, metavar="FILE",
                             help="Save the result to a CSV file at this path. Optional — if omitted, "
                                  "the result is only printed to the terminal and nothing is written to disk.")
        args = self._parse(parser, args)
        if args is None:
            return
        try:
            df = self.analytics.getCalculatedFunctions()
            print_dataframe(df, title="Calculated Functions")
            if args.save:
                save_df(df, args.save)
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    @login_required
    def do_scan_calculated_metric(self, args: Any):
        """scan_calculated_metric <id> [-v]  — Scan a calculated metric definition for component references."""
        parser = SafeArgumentParser(prog="scan_calculated_metric")
        parser.add_argument("id", metavar="ID")
        parser.add_argument("-v", "--verbose", action="store_true")
        args = self._parse(parser, args)
        if args is None:
            return
        try:
            data = self.analytics.getCalculatedMetric(calculatedMetricId=args.id)
            result = self.analytics.scanCalculatedMetric(calculatedMetric=data, verbose=args.verbose)
            console.print_json(json.dumps(result, indent=2))
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    # ------------------------------------------------------------------
    # Group 3 — Segments
    # ------------------------------------------------------------------
    @login_required
    def do_get_segments(self, args: Any):
        """get_segments [-n name] [-rsid id] [-f filter] [-fn file.csv]  — List segments. Always saved to CSV (default segments.csv, override with -fn)."""
        parser = SafeArgumentParser(prog="get_segments")
        parser.add_argument("-n", "--name", default=None, metavar="NAME")
        parser.add_argument("-rsid", default=None)
        parser.add_argument("-f", "--filter", default=None, metavar="TEXT",
                             help="Case-insensitive substring filter, matched against every column of each "
                                  "result row. Applied locally after the data is retrieved from the API — "
                                  "does not change what is requested from Adobe Analytics.")
        parser.add_argument("-fn", "--filename", default=None, metavar="FILE",
                             help="Override the default filename used to save the result to CSV. The result "
                                  "is always saved (default: segments.csv) — this only renames the file.")
        args = self._parse(parser, args)
        if args is None:
            return
        rsid_list = [args.rsid or self.rsid] if (args.rsid or self.rsid) else None
        try:
            df = self.analytics.getSegments(name=args.name, rsids_list=rsid_list)
            if args.filter and not df.empty:
                mask = df.apply(lambda r: args.filter.lower() in str(r).lower(), axis=1)
                df = df[mask]
            print_dataframe(df, title="Segments")
            save_df(df, args.filename or "segments.csv")
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    @login_required
    def do_get_segment(self, args: Any):
        """get_segment <id> [-full]  — Get details for a single segment."""
        parser = SafeArgumentParser(prog="get_segment")
        parser.add_argument("id", metavar="ID")
        parser.add_argument("-full", "--full", action="store_true")
        args = self._parse(parser, args)
        if args is None:
            return
        try:
            data = self.analytics.getSegment(segment_id=args.id, full=args.full)
            console.print_json(json.dumps(data, indent=2))
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    @login_required
    def do_create_segment(self, args: Any):
        """create_segment -d def.json  — Create a segment from a JSON definition."""
        parser = SafeArgumentParser(prog="create_segment")
        parser.add_argument("-d", "--definition", required=True, metavar="FILE")
        args = self._parse(parser, args)
        if args is None:
            return
        data = load_json(args.definition)
        if data is None:
            return
        try:
            result = self.analytics.createSegment(segmentJSON=data)
            console.print_json(json.dumps(result, indent=2))
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    @login_required
    def do_update_segment(self, args: Any):
        """update_segment <id> -d def.json  — Update an existing segment."""
        parser = SafeArgumentParser(prog="update_segment")
        parser.add_argument("id", metavar="ID")
        parser.add_argument("-d", "--definition", required=True, metavar="FILE")
        args = self._parse(parser, args)
        if args is None:
            return
        data = load_json(args.definition)
        if data is None:
            return
        try:
            result = self.analytics.updateSegment(segmentID=args.id, segmentJSON=data)
            console.print_json(json.dumps(result, indent=2))
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    @login_required
    def do_delete_segment(self, args: Any):
        """delete_segment <id>  — Delete a segment (prompts for confirmation)."""
        sid = args.strip()
        if not sid:
            console.print("[red]Usage: delete_segment <id>[/red]")
            return
        if not confirm_action(f"Delete segment '{sid}'? [y/N] "):
            console.print("[yellow]Cancelled.[/yellow]")
            return
        try:
            result = self.analytics.deleteSegment(segmentID=sid)
            console.print(f"[green]{result}[/green]")
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    @login_required
    def do_scan_segment(self, args: Any):
        """scan_segment <id> [-v]  — Scan a segment definition for component references."""
        parser = SafeArgumentParser(prog="scan_segment")
        parser.add_argument("id", metavar="ID")
        parser.add_argument("-v", "--verbose", action="store_true")
        args = self._parse(parser, args)
        if args is None:
            return
        try:
            data = self.analytics.getSegment(segment_id=args.id, full=True)
            result = self.analytics.scanSegment(segment=data, verbose=args.verbose)
            console.print_json(json.dumps(result, indent=2))
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    # ------------------------------------------------------------------
    # Group 4 — Date Ranges
    # ------------------------------------------------------------------
    @login_required
    def do_get_date_ranges(self, args: Any):
        """get_date_ranges [-f filter] [-sv file.csv]  — List all date ranges."""
        parser = SafeArgumentParser(prog="get_date_ranges")
        parser.add_argument("-f", "--filter", default=None, metavar="TEXT",
                             help="Case-insensitive substring filter, matched against every column of each "
                                  "result row. Applied locally after the data is retrieved from the API — "
                                  "does not change what is requested from Adobe Analytics.")
        parser.add_argument("-sv", "--save", default=None, metavar="FILE",
                             help="Save the result to a CSV file at this path. Optional — if omitted, "
                                  "the result is only printed to the terminal and nothing is written to disk.")
        args = self._parse(parser, args)
        if args is None:
            return
        try:
            df = self.analytics.getDateRanges()
            if args.filter and not df.empty:
                mask = df.apply(lambda r: args.filter.lower() in str(r).lower(), axis=1)
                df = df[mask]
            print_dataframe(df, title="Date Ranges")
            if args.save:
                save_df(df, args.save)
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    @login_required
    def do_get_date_range(self, args: Any):
        """get_date_range <id>  — Get details for a single date range."""
        dr_id = args.strip()
        if not dr_id:
            console.print("[red]Usage: get_date_range <id>[/red]")
            return
        try:
            data = self.analytics.getDateRange(dateRangeID=dr_id)
            console.print_json(json.dumps(data, indent=2))
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    @login_required
    def do_create_date_range(self, args: Any):
        """create_date_range -d def.json  — Create a date range from a JSON definition."""
        parser = SafeArgumentParser(prog="create_date_range")
        parser.add_argument("-d", "--definition", required=True, metavar="FILE")
        args = self._parse(parser, args)
        if args is None:
            return
        data = load_json(args.definition)
        if data is None:
            return
        try:
            result = self.analytics.createDateRange(dateRangeJSON=data)
            console.print_json(json.dumps(result, indent=2))
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    @login_required
    def do_update_date_range(self, args: Any):
        """update_date_range <id> -d def.json  — Update an existing date range."""
        parser = SafeArgumentParser(prog="update_date_range")
        parser.add_argument("id", metavar="ID")
        parser.add_argument("-d", "--definition", required=True, metavar="FILE")
        args = self._parse(parser, args)
        if args is None:
            return
        data = load_json(args.definition)
        if data is None:
            return
        try:
            result = self.analytics.updateDateRange(dateRangeID=args.id, dateRangeJSON=data)
            console.print_json(json.dumps(result, indent=2))
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    @login_required
    def do_delete_date_range(self, args: Any):
        """delete_date_range <id>  — Delete a date range (prompts for confirmation)."""
        dr_id = args.strip()
        if not dr_id:
            console.print("[red]Usage: delete_date_range <id>[/red]")
            return
        if not confirm_action(f"Delete date range '{dr_id}'? [y/N] "):
            console.print("[yellow]Cancelled.[/yellow]")
            return
        try:
            result = self.analytics.deleteDateRange(dateRangeID=dr_id)
            console.print(f"[green]{result}[/green]")
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    # ------------------------------------------------------------------
    # Group 5 — Tags
    # ------------------------------------------------------------------
    @login_required
    def do_get_tags(self, args: Any):
        """get_tags [-sv file.csv]  — List all tags."""
        parser = SafeArgumentParser(prog="get_tags")
        parser.add_argument("-sv", "--save", default=None, metavar="FILE",
                             help="Save the result to a CSV file at this path. Optional — if omitted, "
                                  "the result is only printed to the terminal and nothing is written to disk.")
        args = self._parse(parser, args)
        if args is None:
            return
        try:
            tags = self.analytics.getTags()
            print_table(tags, columns=["id", "name"], title="Tags")
            if args.save:
                save_list(tags, args.save)
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    @login_required
    def do_get_tag(self, args: Any):
        """get_tag <id>  — Get details for a single tag."""
        tag_id = args.strip()
        if not tag_id:
            console.print("[red]Usage: get_tag <id>[/red]")
            return
        try:
            data = self.analytics.getTag(tagId=tag_id)
            console.print_json(json.dumps(data, indent=2))
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    @login_required
    def do_get_component_tags(self, args: Any):
        """get_component_tags <componentId> -type <segment|calculatedMetric|...>  — List tags on a component."""
        parser = SafeArgumentParser(prog="get_component_tags")
        parser.add_argument("id", metavar="COMPONENT_ID")
        parser.add_argument("-type", "--type", required=True, metavar="TYPE")
        args = self._parse(parser, args)
        if args is None:
            return
        try:
            tags = self.analytics.getComponentTags(componentId=args.id, componentType=args.type)
            print_table(tags, columns=["id", "name"], title=f"Tags on {args.id}")
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    @login_required
    def do_search_tags(self, args: Any):
        """search_tags -n tagName1,tagName2 -type <componentType>  — Search components by tag name."""
        parser = SafeArgumentParser(prog="search_tags")
        parser.add_argument("-n", "--names", required=True, metavar="TAG_NAMES")
        parser.add_argument("-type", "--type", required=True, metavar="TYPE")
        args = self._parse(parser, args)
        if args is None:
            return
        try:
            result = self.analytics.getComponentTagName(tagNames=args.names, componentType=args.type)
            console.print_json(json.dumps(result, indent=2))
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    @login_required
    def do_create_tags(self, args: Any):
        """create_tags -d def.json  — Create tags from a JSON definition."""
        parser = SafeArgumentParser(prog="create_tags")
        parser.add_argument("-d", "--definition", required=True, metavar="FILE")
        args = self._parse(parser, args)
        if args is None:
            return
        data = load_json(args.definition)
        if data is None:
            return
        try:
            result = self.analytics.createTags(data=data)
            console.print_json(json.dumps(result, indent=2))
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    @login_required
    def do_delete_tag(self, args: Any):
        """delete_tag <id>  — Delete a tag (prompts for confirmation)."""
        tag_id = args.strip()
        if not tag_id:
            console.print("[red]Usage: delete_tag <id>[/red]")
            return
        if not confirm_action(f"Delete tag '{tag_id}'? [y/N] "):
            console.print("[yellow]Cancelled.[/yellow]")
            return
        try:
            result = self.analytics.deleteTag(tagId=tag_id)
            console.print(f"[green]{result}[/green]")
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    # ------------------------------------------------------------------
    # Group 6 — Projects
    # ------------------------------------------------------------------
    @login_required
    def do_get_projects(self, args: Any):
        """get_projects [-f filter] [-full] [-sv file.csv]  — List Workspace projects."""
        parser = SafeArgumentParser(prog="get_projects")
        parser.add_argument("-f", "--filter", default=None, metavar="TEXT",
                             help="Case-insensitive substring filter, matched against every column of each "
                                  "result row. Applied locally after the data is retrieved from the API — "
                                  "does not change what is requested from Adobe Analytics.")
        parser.add_argument("-full", "--full", action="store_true")
        parser.add_argument("-sv", "--save", default=None, metavar="FILE",
                             help="Save the result to a CSV file at this path. Optional — if omitted, "
                                  "the result is only printed to the terminal and nothing is written to disk.")
        args = self._parse(parser, args)
        if args is None:
            return
        try:
            df = self.analytics.getProjects(full=args.full)
            if args.filter and not df.empty:
                mask = df.apply(lambda r: args.filter.lower() in str(r).lower(), axis=1)
                df = df[mask]
            print_dataframe(df, title="Projects")
            if args.save:
                save_df(df, args.save)
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    @login_required
    def do_get_project(self, args: Any):
        """get_project <id>  — Get details for a single project."""
        pid = args.strip()
        if not pid:
            console.print("[red]Usage: get_project <id>[/red]")
            return
        try:
            data = self.analytics.getProject(projectId=pid)
            if hasattr(data, "to_dict"):
                console.print_json(json.dumps(data.to_dict(), indent=2))
            else:
                console.print_json(json.dumps(data, indent=2))
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    @login_required
    def do_get_all_project_details(self, args: Any):
        """get_all_project_details [-f filter] [-sv file.csv]  — Fetch full details for all projects."""
        parser = SafeArgumentParser(prog="get_all_project_details")
        parser.add_argument("-f", "--filter", default=None, metavar="TEXT",
                             help="Case-insensitive substring filter, matched against every column of each "
                                  "result row. Applied locally after the data is retrieved from the API — "
                                  "does not change what is requested from Adobe Analytics.")
        parser.add_argument("-sv", "--save", default=None, metavar="FILE",
                             help="Save the result to a CSV file at this path. Optional — if omitted, "
                                  "the result is only printed to the terminal and nothing is written to disk.")
        args = self._parse(parser, args)
        if args is None:
            return
        console.print("[yellow]This call fetches details for every project and may take a while...[/yellow]")
        try:
            result = self.analytics.getAllProjectDetails(
                filterNameProject=args.filter,
                output="dict",
            )
            console.print_json(json.dumps(result, indent=2, default=str))
            if args.save:
                save_list(list(result.values()) if isinstance(result, dict) else result, args.save)
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    @login_required
    def do_create_project(self, args: Any):
        """create_project -d def.json  — Create a project from a JSON definition."""
        parser = SafeArgumentParser(prog="create_project")
        parser.add_argument("-d", "--definition", required=True, metavar="FILE")
        args = self._parse(parser, args)
        if args is None:
            return
        data = load_json(args.definition)
        if data is None:
            return
        try:
            result = self.analytics.createProject(projectObj=data)
            console.print_json(json.dumps(result, indent=2))
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    @login_required
    def do_update_project(self, args: Any):
        """update_project <id> -d def.json  — Update an existing project."""
        parser = SafeArgumentParser(prog="update_project")
        parser.add_argument("id", metavar="ID")
        parser.add_argument("-d", "--definition", required=True, metavar="FILE")
        args = self._parse(parser, args)
        if args is None:
            return
        data = load_json(args.definition)
        if data is None:
            return
        try:
            result = self.analytics.updateProject(projectId=args.id, projectObj=data)
            console.print_json(json.dumps(result, indent=2))
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    @login_required
    def do_delete_project(self, args: Any):
        """delete_project <id>  — Delete a project (prompts for confirmation)."""
        pid = args.strip()
        if not pid:
            console.print("[red]Usage: delete_project <id>[/red]")
            return
        if not confirm_action(f"Delete project '{pid}'? [y/N] "):
            console.print("[yellow]Cancelled.[/yellow]")
            return
        try:
            result = self.analytics.deleteProject(projectId=pid)
            console.print(f"[green]{result}[/green]")
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    # ------------------------------------------------------------------
    # Group 7 — Reporting
    # ------------------------------------------------------------------
    @login_required
    def do_get_report(self, args: Any):
        """get_report -d request.json [-rsid id] [-n rows] [-sv file.csv]  — Run a report from a JSON request file."""
        parser = SafeArgumentParser(prog="get_report")
        parser.add_argument("-d", "--definition", required=True, metavar="FILE")
        parser.add_argument("-rsid", default=None)
        parser.add_argument("-n", "--n_results", default="inf", metavar="N")
        parser.add_argument("-sv", "--save", default=None, metavar="FILE",
                             help="Save the result to a CSV file at this path. Optional — if omitted, "
                                  "the result is only printed to the terminal and nothing is written to disk.")
        args = self._parse(parser, args)
        if args is None:
            return
        request = load_json(args.definition)
        if request is None:
            return
        rsid = args.rsid or self.rsid
        n = args.n_results if args.n_results == "inf" else int(args.n_results)
        try:
            workspace = self.analytics.getReport2(request=request, n_results=n, rsid=rsid)
            if not hasattr(workspace, "dataframe"):
                console.print_json(json.dumps(workspace, indent=2, default=str))
                return
            df = workspace.dataframe
            print_dataframe(df, title="Report Results (top 10)", max_rows=10)
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = args.save or f"report_{rsid or 'result'}_{ts}.csv"
            save_df(df, filename)
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    @login_required
    def do_get_top_items(self, args: Any):
        """get_top_items <dimension> [-rsid id] [-dr dateRange] [-n limit] [-sv file.csv]  — Get top dimension items."""
        parser = SafeArgumentParser(prog="get_top_items")
        parser.add_argument("dimension", metavar="DIMENSION")
        parser.add_argument("-rsid", default=None)
        parser.add_argument("-dr", "--date_range", default=None, metavar="RANGE")
        parser.add_argument("-n", "--limit", type=int, default=10)
        parser.add_argument("-sv", "--save", default=None, metavar="FILE",
                             help="Save the result to a CSV file at this path. Optional — if omitted, "
                                  "the result is only printed to the terminal and nothing is written to disk.")
        args = self._parse(parser, args)
        if args is None:
            return
        rsid = resolve_rsid(args.rsid, self.rsid)
        if rsid is None:
            return
        try:
            df = self.analytics.getTopItems(
                rsid=rsid,
                dimension=args.dimension,
                dateRange=args.date_range,
                limit=args.limit,
            )
            print_dataframe(df, title=f"Top items — {args.dimension}")
            if args.save:
                save_df(df, args.save)
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    @login_required
    def do_decode_aa_requests(self, args: Any):
        """decode_aa_requests -d file [-sv output.csv]  — Decode Adobe Analytics image request URLs."""
        parser = SafeArgumentParser(prog="decode_aa_requests")
        parser.add_argument("-d", "--definition", required=True, metavar="FILE")
        parser.add_argument("-sv", "--save", default=None, metavar="FILE",
                             help="Save the result to a CSV file at this path. Optional — if omitted, "
                                  "the result is only printed to the terminal and nothing is written to disk.")
        args = self._parse(parser, args)
        if args is None:
            return
        try:
            df = self.analytics.decodeAArequests(file=args.definition, save=bool(args.save))
            print_dataframe(df, title="Decoded AA Requests", max_rows=20)
            if args.save:
                save_df(df, args.save)
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    # ------------------------------------------------------------------
    # Group 8 — RequestCreator sub-shell
    # ------------------------------------------------------------------
    @login_required
    def do_request_creator(self, _args: Any):
        """request_creator  — Enter interactive RequestCreator mode to build a report request."""
        rc_shell = RequestCreatorShell(analytics=self.analytics, session_rsid=self.rsid)
        try:
            rc_shell.cmdloop()
        except KeyboardInterrupt:
            console.print("\n[yellow]Exiting RequestCreator mode.[/yellow]")

    # ------------------------------------------------------------------
    # Group 9 — Scheduled Jobs
    # ------------------------------------------------------------------
    @login_required
    def do_get_scheduled_jobs(self, args: Any):
        """get_scheduled_jobs [-f filter] [-sv file.csv]  — List all scheduled projects."""
        parser = SafeArgumentParser(prog="get_scheduled_jobs")
        parser.add_argument("-f", "--filter", default=None, metavar="TEXT",
                             help="Case-insensitive substring filter, matched against every column of each "
                                  "result row. Applied locally after the data is retrieved from the API — "
                                  "does not change what is requested from Adobe Analytics.")
        parser.add_argument("-sv", "--save", default=None, metavar="FILE",
                             help="Save the result to a CSV file at this path. Optional — if omitted, "
                                  "the result is only printed to the terminal and nothing is written to disk.")
        args = self._parse(parser, args)
        if args is None:
            return
        try:
            df = self.analytics.getScheduledJobs()
            if args.filter and not df.empty:
                mask = df.apply(lambda r: args.filter.lower() in str(r).lower(), axis=1)
                df = df[mask]
            print_dataframe(df, title="Scheduled Jobs")
            if args.save:
                save_df(df, args.save)
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    @login_required
    def do_get_scheduled_job(self, args: Any):
        """get_scheduled_job <id>  — Get details for a single scheduled job."""
        jid = args.strip()
        if not jid:
            console.print("[red]Usage: get_scheduled_job <id>[/red]")
            return
        try:
            data = self.analytics.getScheduledJob(scheduleId=jid)
            console.print_json(json.dumps(data, indent=2))
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    @login_required
    def do_create_scheduled_job(self, args: Any):
        """create_scheduled_job -pid <projectId> -d def.json  — Create a scheduled job."""
        parser = SafeArgumentParser(prog="create_scheduled_job")
        parser.add_argument("-pid", "--project_id", required=True, metavar="PROJECT_ID")
        parser.add_argument("-d", "--definition", required=True, metavar="FILE")
        args = self._parse(parser, args)
        if args is None:
            return
        data = load_json(args.definition)
        if data is None:
            return
        try:
            result = self.analytics.createScheduledJob(projectId=args.project_id, **data)
            console.print_json(json.dumps(result, indent=2))
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    @login_required
    def do_update_scheduled_job(self, args: Any):
        """update_scheduled_job <id> -d def.json  — Update a scheduled job."""
        parser = SafeArgumentParser(prog="update_scheduled_job")
        parser.add_argument("id", metavar="ID")
        parser.add_argument("-d", "--definition", required=True, metavar="FILE")
        args = self._parse(parser, args)
        if args is None:
            return
        data = load_json(args.definition)
        if data is None:
            return
        try:
            result = self.analytics.updateScheduledJob(scheduleId=args.id, scheduleObj=data)
            console.print_json(json.dumps(result, indent=2))
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    @login_required
    def do_delete_scheduled_job(self, args: Any):
        """delete_scheduled_job <id>  — Delete a scheduled job (prompts for confirmation)."""
        jid = args.strip()
        if not jid:
            console.print("[red]Usage: delete_scheduled_job <id>[/red]")
            return
        if not confirm_action(f"Delete scheduled job '{jid}'? [y/N] "):
            console.print("[yellow]Cancelled.[/yellow]")
            return
        try:
            result = self.analytics.deleteScheduledJob(scheduleId=jid)
            console.print(f"[green]{result}[/green]")
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    # ------------------------------------------------------------------
    # Group 10 — Annotations
    # ------------------------------------------------------------------
    @login_required
    def do_get_annotations(self, args: Any):
        """get_annotations [-sv file.csv]  — List all annotations."""
        parser = SafeArgumentParser(prog="get_annotations")
        parser.add_argument("-sv", "--save", default=None, metavar="FILE",
                             help="Save the result to a CSV file at this path. Optional — if omitted, "
                                  "the result is only printed to the terminal and nothing is written to disk.")
        args = self._parse(parser, args)
        if args is None:
            return
        try:
            annotations = self.analytics.getAnnotations()
            print_table(annotations, columns=["id", "name", "description"], title="Annotations")
            if args.save:
                save_list(annotations, args.save)
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    @login_required
    def do_get_annotation(self, args: Any):
        """get_annotation <id>  — Get details for a single annotation."""
        aid = args.strip()
        if not aid:
            console.print("[red]Usage: get_annotation <id>[/red]")
            return
        try:
            data = self.analytics.getAnnotation(annotationId=aid)
            console.print_json(json.dumps(data, indent=2))
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    @login_required
    def do_create_annotation(self, args: Any):
        """create_annotation -d def.json  — Create an annotation from a JSON definition."""
        parser = SafeArgumentParser(prog="create_annotation")
        parser.add_argument("-d", "--definition", required=True, metavar="FILE")
        args = self._parse(parser, args)
        if args is None:
            return
        data = load_json(args.definition)
        if data is None:
            return
        try:
            result = self.analytics.createAnnotation(**data)
            console.print_json(json.dumps(result, indent=2))
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    @login_required
    def do_update_annotation(self, args: Any):
        """update_annotation <id> -d def.json  — Update an existing annotation."""
        parser = SafeArgumentParser(prog="update_annotation")
        parser.add_argument("id", metavar="ID")
        parser.add_argument("-d", "--definition", required=True, metavar="FILE")
        args = self._parse(parser, args)
        if args is None:
            return
        data = load_json(args.definition)
        if data is None:
            return
        try:
            result = self.analytics.updateAnnotation(annotationId=args.id, annotationObj=data)
            console.print_json(json.dumps(result, indent=2))
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    @login_required
    def do_delete_annotation(self, args: Any):
        """delete_annotation <id>  — Delete an annotation (prompts for confirmation)."""
        aid = args.strip()
        if not aid:
            console.print("[red]Usage: delete_annotation <id>[/red]")
            return
        if not confirm_action(f"Delete annotation '{aid}'? [y/N] "):
            console.print("[yellow]Cancelled.[/yellow]")
            return
        try:
            result = self.analytics.deleteAnnotation(annotationId=aid)
            console.print(f"[green]{result}[/green]")
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    # ------------------------------------------------------------------
    # Group 11 — Alerts
    # ------------------------------------------------------------------
    @login_required
    def do_get_alerts(self, args: Any):
        """get_alerts [-sv file.csv]  — List all alerts."""
        parser = SafeArgumentParser(prog="get_alerts")
        parser.add_argument("-sv", "--save", default=None, metavar="FILE",
                             help="Save the result to a CSV file at this path. Optional — if omitted, "
                                  "the result is only printed to the terminal and nothing is written to disk.")
        args = self._parse(parser, args)
        if args is None:
            return
        try:
            df = self.analytics.getAlerts()
            print_dataframe(df, title="Alerts")
            if args.save:
                save_df(df, args.save)
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    @login_required
    def do_get_alert(self, args: Any):
        """get_alert <id>  — Get details for a single alert."""
        aid = args.strip()
        if not aid:
            console.print("[red]Usage: get_alert <id>[/red]")
            return
        try:
            data = self.analytics.getAlert(alertId=aid)
            console.print_json(json.dumps(data, indent=2))
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    @login_required
    def do_enable_alert(self, args: Any):
        """enable_alert <id>  — Enable an alert."""
        aid = args.strip()
        if not aid:
            console.print("[red]Usage: enable_alert <id>[/red]")
            return
        try:
            result = self.analytics.enableAlert(alertId=aid)
            console.print_json(json.dumps(result, indent=2))
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    @login_required
    def do_disable_alert(self, args: Any):
        """disable_alert <id>  — Disable an alert."""
        aid = args.strip()
        if not aid:
            console.print("[red]Usage: disable_alert <id>[/red]")
            return
        try:
            result = self.analytics.disableAlert(alertId=aid)
            console.print_json(json.dumps(result, indent=2))
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    @login_required
    def do_delete_alert(self, args: Any):
        """delete_alert <id>  — Delete an alert (prompts for confirmation)."""
        aid = args.strip()
        if not aid:
            console.print("[red]Usage: delete_alert <id>[/red]")
            return
        if not confirm_action(f"Delete alert '{aid}'? [y/N] "):
            console.print("[yellow]Cancelled.[/yellow]")
            return
        try:
            result = self.analytics.deleteAlert(alertId=aid)
            console.print(f"[green]Deleted (status {result})[/green]")
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    @login_required
    def do_renew_alerts(self, args: Any):
        """renew_alerts -ids id1,id2,...  — Renew one or more alerts."""
        parser = SafeArgumentParser(prog="renew_alerts")
        parser.add_argument("-ids", "--ids", required=True, metavar="ID1,ID2,...")
        args = self._parse(parser, args)
        if args is None:
            return
        ids = [i.strip() for i in args.ids.split(",")]
        try:
            result = self.analytics.renewAlerts(alertIds=ids)
            console.print_json(json.dumps(result, indent=2))
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    # ------------------------------------------------------------------
    # Group 12 — Users
    # ------------------------------------------------------------------
    @login_required
    def do_get_users(self, args: Any):
        """get_users [-f filter] [-sv file.csv]  — List all users."""
        parser = SafeArgumentParser(prog="get_users")
        parser.add_argument("-f", "--filter", default=None, metavar="TEXT",
                             help="Case-insensitive substring filter, matched against every column of each "
                                  "result row. Applied locally after the data is retrieved from the API — "
                                  "does not change what is requested from Adobe Analytics.")
        parser.add_argument("-sv", "--save", default=None, metavar="FILE",
                             help="Save the result to a CSV file at this path. Optional — if omitted, "
                                  "the result is only printed to the terminal and nothing is written to disk.")
        args = self._parse(parser, args)
        if args is None:
            return
        try:
            df = self.analytics.getUsers()
            if args.filter and not df.empty:
                mask = df.apply(lambda r: args.filter.lower() in str(r).lower(), axis=1)
                df = df[mask]
            print_dataframe(df, title="Users")
            if args.save:
                save_df(df, args.save)
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    # ------------------------------------------------------------------
    # Group 13 — Usage Logs
    # ------------------------------------------------------------------
    @login_required
    def do_get_usage_logs(self, args: Any):
        """get_usage_logs -start YYYY-MM-DD -end YYYY-MM-DD [-login user] [-rsid id] [-sv file.csv]  — Retrieve usage audit logs."""
        parser = SafeArgumentParser(prog="get_usage_logs")
        parser.add_argument("-start", "--start_date", required=True, metavar="YYYY-MM-DD")
        parser.add_argument("-end", "--end_date", required=True, metavar="YYYY-MM-DD")
        parser.add_argument("-login", "--login", default=None, metavar="LOGIN")
        parser.add_argument("-rsid", default=None)
        parser.add_argument("-sv", "--save", default=None, metavar="FILE",
                             help="Save the result to a CSV file at this path. Optional — if omitted, "
                                  "the result is only printed to the terminal and nothing is written to disk.")
        args = self._parse(parser, args)
        if args is None:
            return
        rsid = args.rsid or self.rsid
        try:
            df = self.analytics.getUsageLogs(
                startDate=args.start_date,
                endDate=args.end_date,
                login=args.login,
                rsid=rsid,
            )
            print_dataframe(df, title="Usage Logs")
            if args.save:
                save_df(df, args.save)
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    # ------------------------------------------------------------------
    # Group 14 — Classifications
    # ------------------------------------------------------------------
    @login_required
    def do_get_classification_datasets(self, args: Any):
        """get_classification_datasets [-rsid id] [-sv file.csv]  — List classification datasets."""
        parser = SafeArgumentParser(prog="get_classification_datasets")
        parser.add_argument("-rsid", default=None)
        parser.add_argument("-sv", "--save", default=None, metavar="FILE",
                             help="Save the result to a CSV file at this path. Optional — if omitted, "
                                  "the result is only printed to the terminal and nothing is written to disk.")
        args = self._parse(parser, args)
        if args is None:
            return
        rsid = resolve_rsid(args.rsid, self.rsid)
        if rsid is None:
            return
        try:
            data = self.analytics.getClassificationDatasets(rsid=rsid)
            console.print_json(json.dumps(data, indent=2, default=str))
            if args.save:
                save_list(data if isinstance(data, list) else [data], args.save)
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    @login_required
    def do_get_classification_jobs(self, args: Any):
        """get_classification_jobs <datasetId> [-n n_results]  — List classification jobs for a dataset."""
        parser = SafeArgumentParser(prog="get_classification_jobs")
        parser.add_argument("dataset_id", metavar="DATASET_ID")
        parser.add_argument("-n", "--n_results", type=int, default=100)
        args = self._parse(parser, args)
        if args is None:
            return
        try:
            jobs = self.analytics.getClassificationJobs(datasetId=args.dataset_id, n_results=args.n_results)
            print_table(jobs, columns=["jobId", "jobName", "state"], title="Classification Jobs")
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    @login_required
    def do_get_classification_job(self, args: Any):
        """get_classification_job <jobId>  — Get details for a single classification job."""
        jid = args.strip()
        if not jid:
            console.print("[red]Usage: get_classification_job <jobId>[/red]")
            return
        try:
            data = self.analytics.getClassificationJob(jobId=jid)
            console.print_json(json.dumps(data, indent=2))
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    @login_required
    def do_get_classification_template(self, args: Any):
        """get_classification_template <datasetId> [-sv file.csv]  — Get a classification template."""
        parser = SafeArgumentParser(prog="get_classification_template")
        parser.add_argument("dataset_id", metavar="DATASET_ID")
        parser.add_argument("-sv", "--save", default=None, metavar="FILE",
                             help="Save the result to a CSV file at this path. Optional — if omitted, "
                                  "the result is only printed to the terminal and nothing is written to disk.")
        args = self._parse(parser, args)
        if args is None:
            return
        try:
            df = self.analytics.getClassificationTemplate(datasetId=args.dataset_id)
            print_dataframe(df, title="Classification Template")
            if args.save:
                save_df(df, args.save)
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    @login_required
    def do_import_classification_json(self, args: Any):
        """import_classification_json <datasetId> -d data.json [-n jobName]  — Import classification data from JSON."""
        parser = SafeArgumentParser(prog="import_classification_json")
        parser.add_argument("dataset_id", metavar="DATASET_ID")
        parser.add_argument("-d", "--definition", required=True, metavar="FILE")
        parser.add_argument("-n", "--job_name", default="CLI Import", metavar="NAME")
        args = self._parse(parser, args)
        if args is None:
            return
        data = load_json(args.definition)
        if data is None:
            return
        try:
            result = self.analytics.importClassificationJSON(
                datasetId=args.dataset_id,
                jobName=args.job_name,
                data=data,
            )
            console.print_json(json.dumps(result, indent=2))
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    @login_required
    def do_create_export_classification(self, args: Any):
        """create_export_classification <datasetId> -n jobName [-d def.json]  — Create a classification export job."""
        parser = SafeArgumentParser(prog="create_export_classification")
        parser.add_argument("dataset_id", metavar="DATASET_ID")
        parser.add_argument("-n", "--job_name", required=True, metavar="NAME")
        parser.add_argument("-d", "--definition", default=None, metavar="FILE")
        args = self._parse(parser, args)
        if args is None:
            return
        extra = {}
        if args.definition:
            extra = load_json(args.definition) or {}
        try:
            result = self.analytics.createExportClassification(
                datasetId=args.dataset_id,
                jobName=args.job_name,
                **extra,
            )
            console.print_json(json.dumps(result, indent=2))
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    @login_required
    def do_delete_classification(self, args: Any):
        """delete_classification <datasetId>  — Delete a classification dataset (prompts for confirmation)."""
        did = args.strip()
        if not did:
            console.print("[red]Usage: delete_classification <datasetId>[/red]")
            return
        if not confirm_action(f"Delete classification dataset '{did}'? [y/N] "):
            console.print("[yellow]Cancelled.[/yellow]")
            return
        try:
            result = self.analytics.deleteClassification(datasetId=did)
            console.print_json(json.dumps(result, indent=2))
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    # ------------------------------------------------------------------
    # Group 15 — Data Feeds
    # ------------------------------------------------------------------
    @login_required
    def do_get_data_feeds(self, args: Any):
        """get_data_feeds [-rsid id] [-sv file.csv]  — List data feeds."""
        parser = SafeArgumentParser(prog="get_data_feeds")
        parser.add_argument("-rsid", default=None)
        parser.add_argument("-sv", "--save", default=None, metavar="FILE",
                             help="Save the result to a CSV file at this path. Optional — if omitted, "
                                  "the result is only printed to the terminal and nothing is written to disk.")
        args = self._parse(parser, args)
        if args is None:
            return
        rsid = resolve_rsid(args.rsid, self.rsid)
        if rsid is None:
            return
        try:
            feeds = self.analytics.getDataFeeds(rsid=rsid)
            print_table(feeds, columns=["id", "name", "rsid", "status"], title="Data Feeds")
            if args.save:
                save_list(feeds, args.save)
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    @login_required
    def do_get_data_feed(self, args: Any):
        """get_data_feed <id>  — Get details for a single data feed."""
        fid = args.strip()
        if not fid:
            console.print("[red]Usage: get_data_feed <id>[/red]")
            return
        try:
            data = self.analytics.getDataFeed(datafeedId=fid)
            console.print_json(json.dumps(data, indent=2))
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    @login_required
    def do_get_data_feed_requests(self, args: Any):
        """get_data_feed_requests [-ids id1,id2] [-status status] [-sv file.csv]  — List data feed requests."""
        parser = SafeArgumentParser(prog="get_data_feed_requests")
        parser.add_argument("-ids", "--feed_ids", default=None, metavar="ID1,ID2,...")
        parser.add_argument("-status", "--status", default=None, metavar="STATUS")
        parser.add_argument("-sv", "--save", default=None, metavar="FILE",
                             help="Save the result to a CSV file at this path. Optional — if omitted, "
                                  "the result is only printed to the terminal and nothing is written to disk.")
        args = self._parse(parser, args)
        if args is None:
            return
        feed_ids = [i.strip() for i in args.feed_ids.split(",")] if args.feed_ids else None
        try:
            requests_list = self.analytics.getDataFeedRequests(
                feedsIds=feed_ids,
                requestStates=args.status,
            )
            print_table(requests_list, columns=["feedId", "requestId", "status"], title="Data Feed Requests")
            if args.save:
                save_list(requests_list, args.save)
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    @login_required
    def do_update_data_feed(self, args: Any):
        """update_data_feed <id> -d def.json  — Update a data feed."""
        parser = SafeArgumentParser(prog="update_data_feed")
        parser.add_argument("id", metavar="ID")
        parser.add_argument("-d", "--definition", required=True, metavar="FILE")
        args = self._parse(parser, args)
        if args is None:
            return
        data = load_json(args.definition)
        if data is None:
            return
        try:
            result = self.analytics.updateDataFeed(datafeedId=args.id, **data)
            console.print_json(json.dumps(result, indent=2))
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    # ------------------------------------------------------------------
    # Group 16 — Data Warehouse
    # ------------------------------------------------------------------
    @login_required
    def do_get_dw_requests(self, args: Any):
        """get_dw_requests [-rsid id] [-sv file.csv]  — List Data Warehouse scheduled requests."""
        parser = SafeArgumentParser(prog="get_dw_requests")
        parser.add_argument("-rsid", default=None)
        parser.add_argument("-sv", "--save", default=None, metavar="FILE",
                             help="Save the result to a CSV file at this path. Optional — if omitted, "
                                  "the result is only printed to the terminal and nothing is written to disk.")
        args = self._parse(parser, args)
        if args is None:
            return
        rsid = args.rsid or self.rsid
        try:
            data = self.analytics.getDataWarehouseScheduledRequests(rsid=rsid)
            console.print_json(json.dumps(data, indent=2, default=str))
            if args.save:
                save_list(data if isinstance(data, list) else [data], args.save)
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    @login_required
    def do_get_dw_request(self, args: Any):
        """get_dw_request <id>  — Get details for a single Data Warehouse scheduled request."""
        rid = args.strip()
        if not rid:
            console.print("[red]Usage: get_dw_request <id>[/red]")
            return
        try:
            data = self.analytics.getDataWarehouseScheduledRequest(scheduleUUID=rid)
            console.print_json(json.dumps(data, indent=2))
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    @login_required
    def do_get_dw_reports(self, args: Any):
        """get_dw_reports [-status status] [-sv file.csv]  — List Data Warehouse report runs."""
        parser = SafeArgumentParser(prog="get_dw_reports")
        parser.add_argument("-status", "--status", default=None, metavar="STATUS")
        parser.add_argument("-sv", "--save", default=None, metavar="FILE",
                             help="Save the result to a CSV file at this path. Optional — if omitted, "
                                  "the result is only printed to the terminal and nothing is written to disk.")
        args = self._parse(parser, args)
        if args is None:
            return
        try:
            data = self.analytics.getDataWarehouseReports(status=args.status)
            console.print_json(json.dumps(data, indent=2, default=str))
            if args.save:
                save_list(data if isinstance(data, list) else [data], args.save)
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    # ------------------------------------------------------------------
    # Group 17 — Data Sources
    # ------------------------------------------------------------------
    @login_required
    def do_get_data_source_accounts(self, args: Any):
        """get_data_source_accounts [-rsid id] [-sv file.csv]  — List data source accounts."""
        parser = SafeArgumentParser(prog="get_data_source_accounts")
        parser.add_argument("-rsid", default=None)
        parser.add_argument("-sv", "--save", default=None, metavar="FILE",
                             help="Save the result to a CSV file at this path. Optional — if omitted, "
                                  "the result is only printed to the terminal and nothing is written to disk.")
        args = self._parse(parser, args)
        if args is None:
            return
        rsid = resolve_rsid(args.rsid, self.rsid)
        if rsid is None:
            return
        try:
            accounts = self.analytics.getDataSourceAccounts(rsid=rsid)
            print_table(accounts, columns=["id", "name", "type"], title="Data Source Accounts")
            if args.save:
                save_list(accounts, args.save)
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    @login_required
    def do_get_data_source_jobs(self, args: Any):
        """get_data_source_jobs <accountId> [-rsid id] [-status status] [-sv file.csv]  — List data source jobs."""
        parser = SafeArgumentParser(prog="get_data_source_jobs")
        parser.add_argument("account_id", metavar="ACCOUNT_ID")
        parser.add_argument("-rsid", default=None)
        parser.add_argument("-status", "--status", default=None, metavar="STATUS")
        parser.add_argument("-sv", "--save", default=None, metavar="FILE",
                             help="Save the result to a CSV file at this path. Optional — if omitted, "
                                  "the result is only printed to the terminal and nothing is written to disk.")
        args = self._parse(parser, args)
        if args is None:
            return
        rsid = resolve_rsid(args.rsid, self.rsid)
        if rsid is None:
            return
        try:
            df = self.analytics.getDataSourceJobs(rsid=rsid, accountId=args.account_id, status=args.status)
            print_dataframe(df, title="Data Source Jobs")
            if args.save:
                save_df(df, args.save)
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    # ------------------------------------------------------------------
    # Group 18 — Cloud Accounts & Locations
    # ------------------------------------------------------------------
    @login_required
    def do_get_cloud_accounts(self, args: Any):
        """get_cloud_accounts [-type accountType] [-sv file.csv]  — List cloud accounts."""
        parser = SafeArgumentParser(prog="get_cloud_accounts")
        parser.add_argument("-type", "--account_type", default=None, metavar="TYPE")
        parser.add_argument("-sv", "--save", default=None, metavar="FILE",
                             help="Save the result to a CSV file at this path. Optional — if omitted, "
                                  "the result is only printed to the terminal and nothing is written to disk.")
        args = self._parse(parser, args)
        if args is None:
            return
        try:
            accounts = self.analytics.getCloudAccounts(accountType=args.account_type)
            print_table(accounts, columns=["id", "name", "type"], title="Cloud Accounts")
            if args.save:
                save_list(accounts, args.save)
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    @login_required
    def do_get_cloud_locations(self, args: Any):
        """get_cloud_locations [-sv file.csv]  — List cloud locations."""
        parser = SafeArgumentParser(prog="get_cloud_locations")
        parser.add_argument("-sv", "--save", default=None, metavar="FILE",
                             help="Save the result to a CSV file at this path. Optional — if omitted, "
                                  "the result is only printed to the terminal and nothing is written to disk.")
        args = self._parse(parser, args)
        if args is None:
            return
        try:
            locations = self.analytics.getCloudLocations()
            print_table(locations, columns=["id", "name", "type"], title="Cloud Locations")
            if args.save:
                save_list(locations, args.save)
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")

    # ------------------------------------------------------------------
    # Group 19 — Knowledge Graph
    # ------------------------------------------------------------------
    @login_required
    def do_build_knowledge_graph(self, args: Any):
        """build_knowledge_graph [-rsids id1,id2|all] [-no-filter-dims] [-projects n|all|id_or_email [id_or_email ...]] [-sample most_recent|random|users] [-fn file.ttl] [-v]  — Build a Knowledge Graph (RDF graph of dimensions, metrics, segments, calculated metrics and projects) for the connected company and save it to a .ttl file."""
        parser = SafeArgumentParser(prog="build_knowledge_graph")
        parser.add_argument("-rsids", "--rsids", default=None, metavar="RSID1,RSID2,...",
                             help="Report suite ID(s) to include, or 'all' for every report suite. Defaults to "
                                  "the most commonly used report suite across projects when omitted.")
        parser.add_argument("-no-filter-dims", "--no_filter_dims", action="store_true",
                             help="Keep entry/exit and non-reportable dimensions (excluded by default).")
        parser.add_argument("-projects", "--projects", nargs="+", default=None,
                             metavar="N|all|ID_OR_EMAIL",
                             help="Projects to load for extra context: a single integer sample size, the single "
                                  "keyword 'all', or one or more project IDs / owner emails (use -sample users "
                                  "for emails).")
        parser.add_argument("-sample", "--sample_method", default="most_recent",
                             choices=["most_recent", "random", "users"], metavar="METHOD",
                             help="Sampling method used when -projects is an integer or a list of emails "
                                  "(default: most_recent).")
        parser.add_argument("-fn", "--filename", default="knowledge_graph.ttl", metavar="FILE",
                             help="Output filename for the saved knowledge graph (default: knowledge_graph.ttl).")
        parser.add_argument("-v", "--verbose", action="store_true")
        args = self._parse(parser, args)
        if args is None:
            return
        rsids = None
        if args.rsids:
            rsids = args.rsids if args.rsids.lower() == "all" else [r.strip() for r in args.rsids.split(",")]
        try:
            kg = KnowledgeGraph(config=self.cfg, companyId=self.company_id, rsids=rsids,
                                 filterDims=not args.no_filter_dims)
            if args.projects:
                if len(args.projects) == 1 and args.projects[0].lower() == "all":
                    projects: Any = "all"
                elif len(args.projects) == 1 and args.projects[0].isdigit():
                    projects = int(args.projects[0])
                else:
                    projects = args.projects
                kg.loadProjects(projects=projects, sampleMethod=args.sample_method)
            kg.buildGraph(save=True, filename=args.filename, verbose=args.verbose)
            console.print(f"[green]Knowledge graph saved → {args.filename}[/green]")
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        prog="aanalytics2",
        description="Interactive CLI for Adobe Analytics API 2.0",
    )
    parser.add_argument(
        "-cf", "--config_file",
        default="config_analytics.json",
        metavar="FILE",
        help="Path to the JSON config file (default: config_analytics.json in cwd)",
    )
    parser.add_argument(
        "-cid", "--company_id",
        default=None,
        metavar="COMPANY_ID",
        help="Adobe Analytics globalCompanyId (overrides config file)",
    )
    parser.add_argument(
        "-rsid", "--report_suite_id",
        default=None,
        metavar="RSID",
        help="Default report suite ID for the session (overrides config file)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output",
    )
    parser.add_argument(
        "-cmd", "--command",
        default=None,
        metavar="CMD",
        help="Run a single command non-interactively and exit",
    )
    args = parser.parse_args()

    shell = AnalyticsShell(
        config_file=args.config_file,
        company_id=args.company_id,
        rsid=args.report_suite_id,
        verbose=args.verbose,
    )

    if args.command:
        shell.onecmd(args.command)
    else:
        try:
            shell.cmdloop()
        except KeyboardInterrupt:
            console.print("\n[bold]Goodbye![/bold]")


if __name__ == "__main__":
    main()
