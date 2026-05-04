"""JSON output formatter."""

from __future__ import annotations

import json

from codewise.models import DocGenResult, ReviewResult, SecurityResult, TestGenResult


class JsonFormatter:
    """Format results as JSON — for piping, CI, or programmatic use."""

    def format_review(self, result: ReviewResult, show_rules: str = "") -> None:
        data = result.model_dump(mode="json")
        print(json.dumps(data, indent=2))

    def format_security(self, result: SecurityResult) -> None:
        data = result.model_dump(mode="json")
        print(json.dumps(data, indent=2))

    def format_testgen(self, result: TestGenResult) -> None:
        data = result.model_dump(mode="json")
        print(json.dumps(data, indent=2))

    def format_docgen(self, result: DocGenResult) -> None:
        data = result.model_dump(mode="json")
        print(json.dumps(data, indent=2))

    def format_hook_result(self, result: ReviewResult | SecurityResult, hook_type: str) -> int:
        data = result.model_dump(mode="json")
        data["hook_type"] = hook_type
        print(json.dumps(data, indent=2))
        if hasattr(result, "findings") and any(
            f.severity.value in ("critical", "high") for f in result.findings
        ):
            return 1
        return 0
