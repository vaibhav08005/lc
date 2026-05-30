from __future__ import annotations

import argparse
import json
from pathlib import Path

from rich.console import Console
from rich.table import Table

from .evaluator import evaluate_file


def _print_text(report: dict) -> None:
    console = Console()
    console.print(f"[bold]{report['lender']} criteria result:[/bold] {report['overall_result']}")
    console.print(f"Criteria version: {report['criteria_version']}")
    console.print_json(json.dumps({"derived": report["derived"], "summary": report["rule_summary"]}, default=str))
    table = Table(title="Failed and Refer Rule Results")
    table.add_column("Status")
    table.add_column("Rule")
    table.add_column("Category")
    table.add_column("Message")
    for rule in report["issues"]:
        table.add_row(rule["status"], rule["rule_id"], rule["category"], rule["message"][:120])
    if report["issues"]:
        console.print(table)
    else:
        console.print("[green]No failed or refer rules to show.[/green]")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate a case against lender mortgage criteria.")
    subparsers = parser.add_subparsers(dest="command")
    evaluate = subparsers.add_parser("evaluate", help="Evaluate a YAML case file.")
    evaluate.add_argument("path", nargs="?", default="input.yaml", help="Path to YAML input. Defaults to input.yaml.")
    evaluate.add_argument("--lender", choices=["halifax", "barclays"], default="halifax", help="Lender rule pack to use. Defaults to halifax.")
    evaluate.add_argument("--text", action="store_true", help="Print a human-readable report instead of JSON.")
    evaluate.add_argument("--no-snapshot", action="store_true", help="Run only automated rules, without snapshot catalogue entries.")
    evaluate.add_argument("--show-all-rules", action="store_true", help="Include every rule result in JSON output for debugging.")
    args = parser.parse_args()

    if args.command in {None, "evaluate"}:
        report = evaluate_file(
            Path(getattr(args, "path", "input.yaml")),
            include_snapshot=not getattr(args, "no_snapshot", False),
            include_all_rules=getattr(args, "show_all_rules", False),
            lender=getattr(args, "lender", "halifax"),
        )
        if getattr(args, "text", False):
            _print_text(report)
        else:
            print(json.dumps(report, indent=2, default=str))
