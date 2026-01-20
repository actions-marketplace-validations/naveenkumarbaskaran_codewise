"""Output formatters — render results to terminal, JSON, SARIF, or Markdown."""

from codewise.output.terminal import TerminalFormatter
from codewise.output.json_fmt import JsonFormatter
from codewise.output.sarif_fmt import SarifFormatter
from codewise.output.markdown_fmt import MarkdownFormatter

__all__ = ["TerminalFormatter", "JsonFormatter", "SarifFormatter", "MarkdownFormatter", "get_formatter"]


def get_formatter(format_name: str):
    """Get a formatter by name."""
    formatters = {
        "terminal": TerminalFormatter,
        "json": JsonFormatter,
        "sarif": SarifFormatter,
        "markdown": MarkdownFormatter,
    }
    cls = formatters.get(format_name)
    if cls is None:
        raise ValueError(f"Unknown format: {format_name}. Available: {', '.join(formatters)}")
    return cls()
