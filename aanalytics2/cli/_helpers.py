import argparse
import functools
import json
from typing import Optional

import pandas as pd
from rich.console import Console
from rich.table import Table

console = Console()


class CLIError(Exception):
    pass


class SafeArgumentParser(argparse.ArgumentParser):
    """ArgumentParser that raises CLIError instead of calling sys.exit, keeping the REPL alive."""

    def error(self, message: str):
        raise CLIError(f"{message}  (use -h for help)")

    def exit(self, status: int = 0, message: str = None):
        # Called by argparse after -h/--help (status 0) and on parse errors (status != 0).
        # Must always stop parsing here — otherwise -h just prints help and falls through
        # to execute the command with default argument values.
        if status != 0 and message:
            raise CLIError(message)
        raise SystemExit(status)


def login_required(f):
    """Decorator: abort command with a clear message if Analytics is not yet connected."""
    @functools.wraps(f)
    def wrapper(self, *args, **kwargs):
        if self.analytics is None:
            console.print("[red]Not connected. Check your config and run 'config' to reconnect.[/red]")
            return
        return f(self, *args, **kwargs)
    return wrapper


def str2bool(v) -> bool:
    if isinstance(v, bool):
        return v
    if v.lower() in ("yes", "true", "t", "y", "1"):
        return True
    if v.lower() in ("no", "false", "f", "n", "0"):
        return False
    raise argparse.ArgumentTypeError("Boolean value expected (true/false).")


def confirm_action(prompt: str = "Are you sure? [y/N] ") -> bool:
    try:
        return input(prompt).strip().lower() in ("y", "yes")
    except (KeyboardInterrupt, EOFError):
        return False


def print_table(data, columns: list, title: str = ""):
    """Render a list of dicts as a rich Table."""
    if not data:
        console.print("[yellow]No results.[/yellow]")
        return
    table = Table(title=title, show_lines=False, highlight=True)
    for col in columns:
        table.add_column(str(col), overflow="fold")
    for row in data:
        if isinstance(row, dict):
            table.add_row(*[str(row.get(col, "")) for col in columns])
        else:
            table.add_row(*[""] * len(columns))
    console.print(table)


def print_dataframe(df: pd.DataFrame, title: str = "", max_rows: int = 0):
    """Render a DataFrame as a rich Table. max_rows=0 means all rows."""
    if df is None or df.empty:
        console.print("[yellow]No data returned.[/yellow]")
        return
    table = Table(title=title, show_lines=False, highlight=True)
    for col in df.columns:
        table.add_column(str(col), overflow="fold")
    rows = df if max_rows == 0 else df.head(max_rows)
    for _, row in rows.iterrows():
        table.add_row(*[str(v) if v is not None else "" for v in row])
    console.print(table)


def save_df(df: pd.DataFrame, filename: str):
    try:
        df.to_csv(filename, index=False)
        console.print(f"[green]Saved → {filename}[/green]")
    except Exception as exc:
        console.print(f"[red]Save failed: {exc}[/red]")


def save_list(data: list, filename: str):
    try:
        pd.DataFrame(data).to_csv(filename, index=False)
        console.print(f"[green]Saved → {filename}[/green]")
    except Exception as exc:
        console.print(f"[red]Save failed: {exc}[/red]")


def load_json(path: str) -> Optional[dict]:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        console.print(f"[red]File not found: {path}[/red]")
    except json.JSONDecodeError as exc:
        console.print(f"[red]Invalid JSON in {path}: {exc}[/red]")
    return None


def resolve_rsid(arg_rsid: Optional[str], session_rsid: Optional[str], required: bool = True) -> Optional[str]:
    """Return the effective RSID, falling back to the session default. Prints an error if required and missing."""
    rsid = arg_rsid or session_rsid
    if required and rsid is None:
        console.print("[red]RSID required. Use -rsid <id> or run 'set_rsid <id>' first.[/red]")
    return rsid
