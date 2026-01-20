"""Terminal output formatter — rich-powered colorful output."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from codewise.models import (
    DocGenResult,
    ReviewResult,
    SecurityResult,
    Severity,
    TestGenResult,
)

SEVERITY_COLORS = {
    Severity.CRITICAL: "bold red",
    Severity.HIGH: "red",
    Severity.MEDIUM: "yellow",
    Severity.LOW: "cyan",
    Severity.INFO: "dim",
}

SEVERITY_ICONS = {
    Severity.CRITICAL: "🔴",
    Severity.HIGH: "🟠",
    Severity.MEDIUM: "🟡",
    Severity.LOW: "🔵",
    Severity.INFO: "⚪",
}


class TerminalFormatter:
    """Format results for terminal output using rich."""

    def __init__(self, console: Console | None = None):
        self.console = console or Console()

    def format_review(self, result: ReviewResult, show_rules: str = "") -> None:
        """Print review results to terminal."""
        self.console.print()

        if show_rules:
            self.console.print(Panel(show_rules, title="[bold]Active Rules", border_style="blue"))
            self.console.print()

        # Header
        score_text = f" — Score: {result.score}/100" if result.score is not None else ""
        header = f"[bold]Code Review[/bold] ({result.files_reviewed} files){score_text}"
        self.console.print(Panel(header, border_style="blue"))

        if not result.findings:
            self.console.print("[green]✅ No issues found. Code looks good![/green]\n")
            return

        # Findings table
        table = Table(show_header=True, header_style="bold", expand=True, pad_edge=False)
        table.add_column("", width=3)
        table.add_column("Severity", width=10)
        table.add_column("File", width=30)
        table.add_column("Finding", ratio=1)

        for f in sorted(result.findings, key=lambda x: _sev_rank(x.severity), reverse=True):
            icon = SEVERITY_ICONS.get(f.severity, "⚪")
            sev_style = SEVERITY_COLORS.get(f.severity, "")
            location = f.file
            if f.line:
                location += f":{f.line}"

            detail = f"[bold]{f.title}[/bold]\n{f.description}"
            if f.suggestion:
                detail += f"\n[green]Fix: {f.suggestion}[/green]"

            table.add_row(icon, Text(f.severity.value, style=sev_style), location, detail)

        self.console.print(table)

        # Summary
        self.console.print(f"\n{result.summary}")
        if result.tokens_used:
            self.console.print(f"[dim]Model: {result.model} | Tokens: {result.tokens_used:,}[/dim]")
        self.console.print()

    def format_security(self, result: SecurityResult) -> None:
        """Print security scan results."""
        self.console.print()

        risk_style = SEVERITY_COLORS.get(result.risk_level, "")
        header = (
            f"[bold]Security Scan[/bold] ({result.files_scanned} files) — "
            f"Risk: [{risk_style}]{result.risk_level.value.upper()}[/{risk_style}]"
        )
        self.console.print(Panel(header, border_style="red"))

        if not result.findings:
            self.console.print("[green]✅ No security issues found.[/green]\n")
            return

        for f in sorted(result.findings, key=lambda x: _sev_rank(x.severity), reverse=True):
            icon = SEVERITY_ICONS.get(f.severity, "⚪")
            sev_style = SEVERITY_COLORS.get(f.severity, "")

            location = f.file
            if f.line:
                location += f":{f.line}"

            refs = []
            if f.cwe:
                refs.append(f.cwe)
            if f.owasp:
                refs.append(f.owasp)
            ref_str = f" ({', '.join(refs)})" if refs else ""

            self.console.print(
                f"  {icon} [{sev_style}]{f.severity.value.upper()}[/{sev_style}] "
                f"[bold]{f.title}[/bold]{ref_str}"
            )
            self.console.print(f"     {location}")
            self.console.print(f"     {f.description}")
            if f.recommendation:
                self.console.print(f"     [green]Fix: {f.recommendation}[/green]")
            if f.evidence:
                self.console.print(f"     [dim]Evidence: {f.evidence[:200]}[/dim]")
            self.console.print()

        self.console.print(result.summary)
        if result.tokens_used:
            self.console.print(f"[dim]Model: {result.model} | Tokens: {result.tokens_used:,}[/dim]")
        self.console.print()

    def format_testgen(self, result: TestGenResult) -> None:
        """Print generated tests."""
        self.console.print()
        self.console.print(Panel(f"[bold]Test Generation[/bold] — {len(result.tests)} test(s)", border_style="green"))

        for t in result.tests:
            self.console.print(f"\n[bold]{t.test_name}[/bold] ({t.framework})")
            if t.description:
                self.console.print(f"  {t.description}")
            self.console.print(f"  Target: {t.target_function or t.file}")
            self.console.print()
            self.console.print(Panel(t.test_code, title=t.test_name, border_style="green"))

        self.console.print(f"\n{result.summary}")
        self.console.print()

    def format_docgen(self, result: DocGenResult) -> None:
        """Print generated documentation."""
        self.console.print()
        self.console.print(Panel(f"[bold]Documentation[/bold] — {len(result.changes)} change(s)", border_style="magenta"))

        for c in result.changes:
            location = c.file
            if c.line:
                location += f":{c.line}"
            self.console.print(f"\n[bold]{c.target_symbol or c.doc_type}[/bold] in {location}")
            self.console.print(Panel(c.generated, border_style="magenta"))

        self.console.print(f"\n{result.summary}")
        self.console.print()

    def format_hook_result(self, result: ReviewResult | SecurityResult, hook_type: str) -> int:
        """Format results for git hook mode (compact). Returns exit code."""
        findings = result.findings
        if not findings:
            return 0

        self.console.print(f"\n[bold]{hook_type} Hook Results:[/bold]")
        for f in sorted(findings, key=lambda x: _sev_rank(x.severity), reverse=True)[:10]:
            icon = SEVERITY_ICONS.get(f.severity, "⚪")
            location = f.file
            if f.line:
                location += f":{f.line}"
            self.console.print(f"  {icon} {location}: {f.title}")

        remaining = len(findings) - 10
        if remaining > 0:
            self.console.print(f"  ... and {remaining} more")

        return 1 if any(_sev_rank(f.severity) >= 3 for f in findings) else 0


def _sev_rank(severity: Severity) -> int:
    return {Severity.INFO: 0, Severity.LOW: 1, Severity.MEDIUM: 2, Severity.HIGH: 3, Severity.CRITICAL: 4}.get(severity, 0)
