"""SARIF 2.1.0 output formatter — for GitHub Security tab integration."""

from __future__ import annotations

import json
from typing import Any

from codewise.models import ReviewResult, SecurityResult, Severity

# Severity → SARIF level mapping
SARIF_LEVELS = {
    Severity.CRITICAL: "error",
    Severity.HIGH: "error",
    Severity.MEDIUM: "warning",
    Severity.LOW: "note",
    Severity.INFO: "note",
}


class SarifFormatter:
    """Format results as SARIF 2.1.0 for GitHub Code Scanning."""

    def format_review(self, result: ReviewResult, show_rules: str = "") -> None:
        report = _build_sarif("codewise-review", "Codewise Code Review")

        rules: list[dict[str, Any]] = []
        results: list[dict[str, Any]] = []
        rule_ids: dict[str, int] = {}

        for f in result.findings:
            rule_id = f"codewise/{f.category.value}"
            if rule_id not in rule_ids:
                rule_ids[rule_id] = len(rules)
                rules.append({
                    "id": rule_id,
                    "shortDescription": {"text": f.category.value.replace("-", " ").title()},
                    "defaultConfiguration": {"level": SARIF_LEVELS.get(f.severity, "note")},
                })

            result_obj: dict[str, Any] = {
                "ruleId": rule_id,
                "ruleIndex": rule_ids[rule_id],
                "level": SARIF_LEVELS.get(f.severity, "note"),
                "message": {"text": f"{f.title}\n\n{f.description}"},
            }

            if f.line:
                result_obj["locations"] = [{
                    "physicalLocation": {
                        "artifactLocation": {"uri": f.file},
                        "region": {
                            "startLine": f.line,
                            **({"endLine": f.end_line} if f.end_line else {}),
                        },
                    }
                }]

            results.append(result_obj)

        report["runs"][0]["tool"]["driver"]["rules"] = rules
        report["runs"][0]["results"] = results

        print(json.dumps(report, indent=2))

    def format_security(self, result: SecurityResult) -> None:
        report = _build_sarif("codewise-security", "Codewise Security Scanner")

        rules: list[dict[str, Any]] = []
        results: list[dict[str, Any]] = []
        rule_ids: dict[str, int] = {}

        for f in result.findings:
            rule_id = f"codewise/security/{f.category.value}"
            if rule_id not in rule_ids:
                rule_ids[rule_id] = len(rules)
                rule_def: dict[str, Any] = {
                    "id": rule_id,
                    "shortDescription": {"text": f.category.value.replace("-", " ").title()},
                    "defaultConfiguration": {"level": SARIF_LEVELS.get(f.severity, "note")},
                }
                if f.cwe:
                    rule_def["properties"] = {"tags": [f.cwe]}
                rules.append(rule_def)

            result_obj: dict[str, Any] = {
                "ruleId": rule_id,
                "ruleIndex": rule_ids[rule_id],
                "level": SARIF_LEVELS.get(f.severity, "note"),
                "message": {"text": f"{f.title}\n\n{f.description}\n\nRecommendation: {f.recommendation}"},
            }

            if f.line:
                result_obj["locations"] = [{
                    "physicalLocation": {
                        "artifactLocation": {"uri": f.file},
                        "region": {
                            "startLine": f.line,
                            **({"endLine": f.end_line} if f.end_line else {}),
                        },
                    }
                }]

            results.append(result_obj)

        report["runs"][0]["tool"]["driver"]["rules"] = rules
        report["runs"][0]["results"] = results

        print(json.dumps(report, indent=2))

    def format_testgen(self, result, show_rules: str = "") -> None:
        # SARIF not applicable for test generation
        from codewise.output.json_fmt import JsonFormatter
        JsonFormatter().format_testgen(result)

    def format_docgen(self, result, show_rules: str = "") -> None:
        from codewise.output.json_fmt import JsonFormatter
        JsonFormatter().format_docgen(result)

    def format_hook_result(self, result, hook_type: str) -> int:
        from codewise.output.json_fmt import JsonFormatter
        return JsonFormatter().format_hook_result(result, hook_type)


def _build_sarif(tool_name: str, tool_desc: str) -> dict[str, Any]:
    """Build a minimal SARIF 2.1.0 report skeleton."""
    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [{
            "tool": {
                "driver": {
                    "name": tool_name,
                    "informationUri": "https://github.com/naveenkumarbaskaran/codewise",
                    "version": "0.1.0",
                    "semanticVersion": "0.1.0",
                    "rules": [],
                }
            },
            "results": [],
        }],
    }
