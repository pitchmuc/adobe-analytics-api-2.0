# MCP Server

The `aanalytics2` package ships with an [MCP](https://modelcontextprotocol.io/) server that exposes Adobe Analytics — and, optionally, your [Knowledge Graph](./knowledgegraph.md) — as tools any MCP-compatible LLM client (Claude Desktop, VS Code, …) can call directly.

It is a companion to the CLI: same config file, same `Analytics` connection, same `WorkspaceManager` builder — but callable by an LLM instead of typed at a terminal.

> For the underlying design/architecture, see [docs/mcp_plan.md](./mcp_plan.md). This page is about **running** it.

## Menu
- [MCP Server](#mcp-server)
  - [Menu](#menu)
  - [Overview](#overview)
  - [Prerequisites](#prerequisites)
  - [Installing](#installing)
  - [Command-line flags](#command-line-flags)
  - [Knowledge Graph ontology (resource)](#knowledge-graph-ontology-resource)
  - [Running it manually (smoke test)](#running-it-manually-smoke-test)
  - [Claude Desktop setup](#claude-desktop-setup)
  - [VS Code setup](#vs-code-setup)
    - [GitHub Copilot Chat (Agent Mode)](#github-copilot-chat-agent-mode)
    - [Claude Code extension](#claude-code-extension)
  - [Available tools](#available-tools)
  - [Troubleshooting](#troubleshooting)

## Overview

Once connected, the client gets tools grouped into four areas:

* **Discovery** — list report suites, dimensions, metrics, segments, calculated metrics, date ranges, projects.
* **Reporting** — build a report request and run it (`getReport2`).
* **Workspace building** — compose a Workspace project (panels, freeform tables, breakdowns, charts, segment filters, …) and publish it.
* **Classifications** — look up classification dataset(s) linked to a dimension in a report suite, and a dataset's full metadata.
* **Knowledge Graph** *(optional)* — query co-occurrence and usage relationships between components from a pre-built `.ttl` file, via SPARQL or convenience lookups.

The Knowledge Graph tools only appear if you start the server with a `.ttl` file (`-kg`). Everything else is always available.

## Prerequisites

* Python environment with `aanalytics2` installed (see [Installing](#installing)).
* A working Adobe Analytics config file — the same one used by the CLI. See [Getting Started](./getting_started.md) if you don't have one yet.
* *(Optional, for Knowledge Graph tools)* A `.ttl` file built with the [`KnowledgeGraph`](./knowledgegraph.md) class:
  ```py
  import aanalytics2 
  from aanalytics2.knowledgegraph import KnowledgeGraph

  cfg = aanalytics2.importConfigFile('myconfig.json',return_object=True)

  kg = KnowledgeGraph(config=cfg, rsids="all")
  kg.loadProjects(50)
  kg.buildGraph(save=True, filename="analytics_knowledge_graph.ttl")
  ```

## Installing

From your local checkout of the repository:

```bash
pip install -e .
```

This installs the `mcp` dependency and registers the `aanalytics2-mcp` console script on your `PATH`. Confirm it resolved correctly:

```bash
aanalytics2-mcp --help
```

If `aanalytics2-mcp` isn't found (e.g. it's installed in a virtual environment your client doesn't activate), use the module form instead everywhere below: `python -m aanalytics2.mcp_server` (with the correct interpreter's absolute path in `command`).

## Command-line flags

| Flag | Description |
| -- | -- |
| `-cf`, `--config_file` | Path to the JSON config file. Default: `config_analytics.json` in the current directory. |
| `-cid`, `--company_id` | Adobe Analytics `globalCompanyId`. Overrides the config file. Optional — resolved from the config file's `companyId`/`company_id` field if omitted (same field the CLI reads — see [cli.md](./cli.md)), or from the first company returned by the API if that field isn't set either. |
| `-rsid`, `--report_suite_id` | Default report suite ID used by any tool call that omits `rsid`. Optional, but recommended — most Discovery/Reporting/KG tools need an rsid, and a session default lets the LLM skip re-specifying it every call. |
| `-kg`, `--knowledge_graph` | Path to a local Knowledge Graph `.ttl` file. Enables the KG tool group. |
| `-kg-endpoint`, `--kg_endpoint` | Remote SPARQL endpoint URL. **Not implemented yet** — the server exits with an error if you pass this today. |
| `-kg-ontology`, `--kg_ontology` | Path to a markdown file describing a custom Knowledge Graph ontology. Overrides the built-in default (see [below](#knowledge-graph-ontology-resource)). |

`-kg` and `-kg-endpoint` are mutually exclusive.

Because your MCP client (Claude Desktop, VS Code, …) launches the server itself and does not run it from your project directory, **always pass an absolute path** to `-cf` and `-kg` in the client configs below — a relative path resolves against whatever the client's own working directory happens to be, not your project folder.

## Knowledge Graph ontology (resource)

Beyond tools, the server exposes an MCP **resource** at `ontology://knowledge-graph` — a markdown
reference describing the graph's entity types, predicates, and namespace patterns (the same
content as the [Ontology section](./knowledgegraph.md#ontology) of the Knowledge Graph docs). MCP
clients that support resources (Claude Desktop, Claude Code, …) can read it to understand how to
call `sparql_query` and the other KG tools correctly, without you having to explain the schema in
the chat every time.

The server also sets MCP server `instructions` pointing the client at this resource, so most
clients pick it up automatically on connect.

By default the resource serves the ontology produced by `KnowledgeGraph.buildGraph()`. If you
extend the graph yourself — adding custom predicates or literals on top of the base schema — pass
`-kg-ontology "C:\path\to\my_ontology.md"` with a markdown file documenting your additions, and the
server serves that file's content instead:

```bash
aanalytics2-mcp -cf "C:\path\to\config_analytics.json" -rsid your_rsid \
  -kg "C:\path\to\analytics_knowledge_graph.ttl" \
  -kg-ontology "C:\path\to\my_ontology.md"
```

## Running it manually (smoke test)

Before wiring it into a client, confirm it starts cleanly and can log in:

```bash
aanalytics2-mcp -cf "C:\path\to\config_analytics.json" -rsid your_rsid -kg "C:\path\to\analytics_knowledge_graph.ttl"
```

A correctly-starting server prints its startup logs (config loading, KG triple count) to **stderr** and then blocks, waiting for an MCP client to talk to it over stdin/stdout — it will not print a prompt or return control to you. That's expected for the `stdio` transport; press `Ctrl+C` to stop it. If you see a Python traceback instead, fix that first (typically a wrong config path, wrong `rsid`, or missing API access) before configuring a client.

If you want to inspect the tool list interactively without a full client, the [MCP Inspector](https://modelcontextprotocol.io/docs/tools/inspector) works with any stdio server:

```bash
npx @modelcontextprotocol/inspector aanalytics2-mcp -cf "C:\path\to\config_analytics.json" -rsid your_rsid
```

## Claude Desktop setup

Edit Claude Desktop's config file:

* **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
* **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "aanalytics2": {
      "command": "aanalytics2-mcp",
      "args": [
        "-cf", "C:\\path\\to\\config_analytics.json",
        "-cid", "your_globalCompanyId",
        "-rsid", "your_rsid",
        "-kg", "C:\\path\\to\\analytics_knowledge_graph.ttl"
      ]
    }
  }
}
```

Omit the `-kg` line entirely if you don't have a Knowledge Graph file yet — the server starts fine without it, just without the KG tools. Omit `-cid` only if your credential has access to a single Adobe Analytics company, or if `companyId` is already set in the config file — see the [Command-line flags](#command-line-flags) note and [Troubleshooting](#troubleshooting) below on why pinning it explicitly matters when a credential has access to more than one.

Fully quit and reopen Claude Desktop (not just close the window) for it to pick up the change. A hammer/tools icon showing `aanalytics2` tools should then appear in the chat composer.

## VS Code setup

VS Code can talk to MCP servers two ways: through **GitHub Copilot Chat's** built-in MCP support, or through the **Claude Code** extension. Both can be configured side by side; pick whichever you use day to day.

### GitHub Copilot Chat (Agent Mode)

1. Open the Command Palette (`Ctrl+Shift+P` / `Cmd+Shift+P`) and run **MCP: Add Server**, choosing **Command (stdio)** — this writes the file below for you and is the most reliable path across VS Code versions. Alternatively, create it by hand.
2. Workspace-level config: `.vscode/mcp.json` at the repository root:

```json
{
  "servers": {
    "aanalytics2": {
      "type": "stdio",
      "command": "aanalytics2-mcp",
      "args": [
        "-cf", "C:\\path\\to\\config_analytics.json",
        "-cid", "your_globalCompanyId",
        "-rsid", "your_rsid",
        "-kg", "C:\\path\\to\\analytics_knowledge_graph.ttl"
      ]
    }
  }
}
```

`-cid` pins the Adobe Analytics `globalCompanyId` this server connects to. It's important to set explicitly here: without it (and without a `companyId` field in the config file), the server defaults to the first company your credential has access to, which may not be the one you expect if the credential can see more than one — see [Troubleshooting](#troubleshooting).

3. Reload the window (`Developer: Reload Window`). In Copilot Chat, switch to **Agent** mode and open the tools picker (wrench icon) — `aanalytics2` tools should be listed and toggleable.

If you'd rather not commit connection details to the repo, add the same server under your **user** MCP config instead (Command Palette → **MCP: Open User Configuration**) so it applies across projects without landing in `.vscode/mcp.json`.

### Claude Code extension

The Claude Code extension for VS Code shares its MCP configuration with the Claude Code CLI. From the VS Code integrated terminal (or any terminal), register the server once:

```bash
claude mcp add aanalytics2 -- aanalytics2-mcp -cf "C:\path\to\config_analytics.json" -cid your_globalCompanyId -rsid your_rsid -kg "C:\path\to\analytics_knowledge_graph.ttl"
```

This writes an entry equivalent to:

```json
{
  "mcpServers": {
    "aanalytics2": {
      "command": "aanalytics2-mcp",
      "args": [
        "-cf", "C:\\path\\to\\config_analytics.json",
        "-cid", "your_globalCompanyId",
        "-rsid", "your_rsid",
        "-kg", "C:\\path\\to\\analytics_knowledge_graph.ttl"
      ]
    }
  }
}
```

into `.mcp.json` (project scope) or your user-level Claude config (`claude mcp add -s user ...`), depending on the `-s`/`--scope` flag you pass. Run `claude mcp list` to confirm it registered, then start a new Claude Code session — the tools are available immediately, no reload needed.

## Available tools

| Group | Tools |
| -- | -- |
| Discovery | `list_report_suites`, `list_dimensions`, `list_metrics`, `list_segments`, `list_calculated_metrics`, `list_date_ranges`, `list_projects`, `get_segment`, `get_project` |
| Reporting | `build_report_request`, `run_report`, `get_top_items` |
| Workspace building | `create_workspace`, `add_panel`, `add_segment_filter`, `add_dropdown_filter`, `add_text`, `add_freeform`, `add_breakdown`, `add_chart`, `add_segment_comparison_table`, `publish_workspace`, `update_workspace` |
| Classifications | `list_classification_datasets`, `get_classification_dataset_id`, `get_classification_dataset` |
| Knowledge Graph *(needs `-kg`)* | `sparql_query`, `get_related_metrics`, `get_related_dimensions`, `get_related_segments`, `get_popular_combinations`, `get_component_context` |

Workspace-building tools are stateless: each one takes the project dict returned by the previous call and returns an updated one, so a typical session chains `create_workspace` → `add_panel` → `add_freeform` → `add_chart` → `publish_workspace`. Each tool's full parameter list is in its own docstring, visible to the client when it inspects the tool.

To edit an **existing** project instead of building a new one, start from `get_project` instead of `create_workspace`, chain the same `add_*` tools on the returned dict, then call `update_workspace` instead of `publish_workspace` — `update_workspace` requires the project dict to still carry its original `"id"` (present on anything returned by `get_project`) and saves in place rather than creating a duplicate.

| Resource | Description |
| -- | -- |
| `ontology://knowledge-graph` | Markdown reference of KG entity types, predicates and namespace patterns. See [Knowledge Graph ontology](#knowledge-graph-ontology-resource). |

## Troubleshooting

* **`list_report_suites` (or other Discovery tools) return the wrong companies' data** — the server connected using the wrong `globalCompanyId`. This happens when your credential has access to more than one Adobe Analytics company and neither `-cid` nor a `companyId`/`company_id` field in the config file pins one, so the server falls back to the first company the API returns — which isn't guaranteed to be the one the CLI or another session picked for you. Check the server's stderr log at startup: if multiple companies were found it prints the full list it's choosing from. Fix by passing `-cid <globalCompanyId>` explicitly or adding `"companyId": "<globalCompanyId>"` to the config file (same field the CLI honors, see [cli.md](./cli.md)).
* **"No company IDs found for this config file."** — the config file's credentials don't have access to any Adobe Analytics company, or the path is wrong (see the absolute-path note above).
* **Server appears to hang** — this is normal for `-cf`/`-kg`/normal invocation without a client attached (see [Running it manually](#running-it-manually-smoke-test)); it's waiting on stdio.
* **Tools don't show up in the client** — most clients only load MCP servers at startup; fully restart the client (not just reload the chat) after editing its config.
* **`aanalytics2-mcp` not found by the client** — the client may launch processes without your shell's `PATH` (common on macOS GUI apps). Use the module form with an absolute interpreter path instead, e.g. `"command": "C:\\path\\to\\venv\\Scripts\\python.exe", "args": ["-m", "aanalytics2.mcp_server", "-cf", "..."]`.
* **KG tools return a "Knowledge Graph not connected" error** — the server was started without `-kg`, or `-kg` points at a missing/invalid file; check the startup stderr log for the triple count it printed.
