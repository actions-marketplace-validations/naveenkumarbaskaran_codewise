"""Configurable rules engine — custom & standard lint checks.

Users define rules in `.codewise.yaml` under the `rules:` key. Each rule has
a pattern (regex or glob), severity, a human message, and optionally a
category and an LLM instruction that tells the reviewer to enforce it.

Standard rule packs ship with codewise and can be enabled by name.

Example .codewise.yaml:
```yaml
rules:
  enable_packs:
    - python-best-practices
    - security-basics

  custom:
    - id: no-print-statements
      pattern: "\\bprint\\("
      file_pattern: "*.py"
      severity: medium
      category: best-practice
      message: "Use logging instead of print() in production code."

    - id: no-fixme-in-main
      pattern: "FIXME|TODO|HACK"
      file_pattern: "*.py"
      severity: low
      category: maintainability
      message: "Resolve TODO/FIXME comments before merging to main."
      branches: [main, master, release/*]

    - id: max-function-length
      llm_check: "Flag any function or method longer than 50 lines."
      file_pattern: "*.py"
      severity: medium
      category: complexity

    - id: require-error-handling
      llm_check: "Ensure all HTTP/API calls have proper error handling with try/except or equivalent."
      file_pattern: "*.py"
      severity: high
      category: error-handling
```
"""

from __future__ import annotations

import fnmatch
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from codewise.models import CodewiseConfig, FileChange, ReviewFinding, Severity, ReviewCategory

logger = logging.getLogger("codewise.rules")


# ── Rule Types ──────────────────────────────────────────────────────

class RuleType(str, Enum):
    REGEX = "regex"       # Pattern-based match (fast, no LLM)
    LLM = "llm"          # LLM-evaluated check (rich, uses tokens)
    COMPOSITE = "composite"  # Combines multiple rules


@dataclass
class Rule:
    """A single codewise rule — regex-based or LLM-evaluated."""

    id: str
    severity: Severity = Severity.MEDIUM
    category: ReviewCategory = ReviewCategory.BEST_PRACTICE
    message: str = ""
    enabled: bool = True

    # Regex-based detection
    pattern: str | None = None  # regex applied to file content
    file_pattern: str = "*"     # glob pattern for file paths
    multiline: bool = False     # whether regex uses re.MULTILINE

    # LLM-based detection
    llm_check: str | None = None  # natural-language instruction for the LLM

    # Scoping
    branches: list[str] = field(default_factory=list)  # only enforce on these branches
    paths_only: list[str] = field(default_factory=list)  # only in these directories
    paths_ignore: list[str] = field(default_factory=list)  # skip these directories

    # Metadata
    pack: str | None = None  # which rule pack this belongs to
    docs_url: str | None = None
    autofix: str | None = None  # regex replacement string (for regex rules)

    @property
    def rule_type(self) -> RuleType:
        if self.pattern and self.llm_check:
            return RuleType.COMPOSITE
        if self.llm_check:
            return RuleType.LLM
        return RuleType.REGEX

    def matches_file(self, path: str) -> bool:
        """Check if this rule applies to the given file path."""
        if not fnmatch.fnmatch(path, self.file_pattern) and not fnmatch.fnmatch(
            Path(path).name, self.file_pattern
        ):
            return False
        if self.paths_only and not any(
            path.startswith(p) or fnmatch.fnmatch(path, p) for p in self.paths_only
        ):
            return False
        if self.paths_ignore and any(
            path.startswith(p) or fnmatch.fnmatch(path, p) for p in self.paths_ignore
        ):
            return False
        return True

    def matches_branch(self, branch: str | None) -> bool:
        """Check if this rule should run on the given branch."""
        if not self.branches:
            return True  # no branch restriction = run everywhere
        if branch is None:
            return True  # can't determine branch, run anyway
        return any(fnmatch.fnmatch(branch, b) for b in self.branches)


@dataclass
class RuleMatch:
    """A single match from a regex rule."""

    rule: Rule
    file: str
    line: int
    matched_text: str
    context: str = ""  # surrounding lines


# ── Standard Rule Packs ─────────────────────────────────────────────

STANDARD_PACKS: dict[str, list[dict[str, Any]]] = {
    "python-best-practices": [
        {
            "id": "py/no-print",
            "pattern": r"\bprint\s*\(",
            "file_pattern": "*.py",
            "severity": "medium",
            "category": "best-practice",
            "message": "Use `logging` instead of `print()` in production code.",
            "paths_ignore": ["tests/*", "test_*", "conftest.py"],
        },
        {
            "id": "py/no-bare-except",
            "pattern": r"except\s*:",
            "file_pattern": "*.py",
            "severity": "high",
            "category": "error-handling",
            "message": "Avoid bare `except:` — catch specific exceptions.",
        },
        {
            "id": "py/no-star-import",
            "pattern": r"from\s+\S+\s+import\s+\*",
            "file_pattern": "*.py",
            "severity": "medium",
            "category": "maintainability",
            "message": "Avoid wildcard imports — they pollute the namespace.",
        },
        {
            "id": "py/no-mutable-defaults",
            "pattern": r"def\s+\w+\([^)]*(?:=\s*\[\]|=\s*\{\}|=\s*set\(\))",
            "file_pattern": "*.py",
            "severity": "high",
            "category": "bug",
            "message": "Mutable default argument — use `None` and create inside the function.",
        },
        {
            "id": "py/no-assert-in-prod",
            "pattern": r"^\s*assert\s+",
            "file_pattern": "*.py",
            "severity": "low",
            "category": "best-practice",
            "message": "Assert statements are stripped with `python -O`. Use explicit checks for production code.",
            "multiline": True,
            "paths_ignore": ["tests/*", "test_*"],
        },
        {
            "id": "py/type-hints",
            "llm_check": "Flag public functions/methods missing return type annotations or parameter type hints.",
            "file_pattern": "*.py",
            "severity": "low",
            "category": "maintainability",
            "paths_ignore": ["tests/*"],
        },
    ],
    "javascript-best-practices": [
        {
            "id": "js/no-console-log",
            "pattern": r"\bconsole\.(log|debug|info)\s*\(",
            "file_pattern": "*.{js,ts,jsx,tsx}",
            "severity": "medium",
            "category": "best-practice",
            "message": "Remove `console.log` before merging — use a proper logger.",
            "paths_ignore": ["tests/*", "*.test.*", "*.spec.*"],
        },
        {
            "id": "js/no-var",
            "pattern": r"\bvar\s+",
            "file_pattern": "*.{js,jsx}",
            "severity": "medium",
            "category": "best-practice",
            "message": "Use `const` or `let` instead of `var`.",
        },
        {
            "id": "js/no-any",
            "pattern": r":\s*any\b",
            "file_pattern": "*.{ts,tsx}",
            "severity": "low",
            "category": "maintainability",
            "message": "Avoid `any` type — use a specific type or `unknown`.",
        },
        {
            "id": "js/no-eval",
            "pattern": r"\beval\s*\(",
            "file_pattern": "*.{js,ts,jsx,tsx}",
            "severity": "critical",
            "category": "best-practice",
            "message": "Never use `eval()` — it's a security and performance risk.",
        },
    ],
    "security-basics": [
        {
            "id": "sec/no-hardcoded-secrets",
            "pattern": r"""(?i)(password|secret|api[_-]?key|token|private[_-]?key)\s*[=:]\s*["'][^"']{8,}["']""",
            "file_pattern": "*",
            "severity": "critical",
            "category": "best-practice",
            "message": "Possible hardcoded secret — use environment variables or a secrets manager.",
        },
        {
            "id": "sec/no-http-urls",
            "pattern": r"""http://(?!localhost|127\.0\.0\.1|0\.0\.0\.0)""",
            "file_pattern": "*",
            "severity": "medium",
            "category": "best-practice",
            "message": "Use HTTPS instead of HTTP for external URLs.",
            "paths_ignore": ["*.md", "*.txt", "*.rst"],
        },
        {
            "id": "sec/no-sql-concat",
            "pattern": r"""(?:execute|cursor\.execute|query)\s*\(\s*(?:f["']|["']\s*[+%]|.*\.format\()""",
            "file_pattern": "*.py",
            "severity": "critical",
            "category": "best-practice",
            "message": "SQL injection risk — use parameterized queries instead of string concatenation.",
        },
        {
            "id": "sec/no-pickle-load",
            "pattern": r"\bpickle\.loads?\s*\(",
            "file_pattern": "*.py",
            "severity": "high",
            "category": "best-practice",
            "message": "Pickle deserialization can execute arbitrary code — use JSON or a safe format.",
        },
        {
            "id": "sec/dockerfile-no-latest",
            "pattern": r"^FROM\s+\S+:latest\b",
            "file_pattern": "Dockerfile*",
            "severity": "medium",
            "category": "best-practice",
            "message": "Pin Docker image versions instead of using `:latest`.",
            "multiline": True,
        },
    ],
    "go-best-practices": [
        {
            "id": "go/no-naked-return",
            "pattern": r"^\s*return\s*$",
            "file_pattern": "*.go",
            "severity": "low",
            "category": "readability",
            "message": "Avoid naked returns — they reduce readability.",
            "multiline": True,
        },
        {
            "id": "go/error-not-handled",
            "pattern": r",\s*(?:_|err)\s*(?::)?=\s*\S+\([^)]*\)\s*\n\s*(?!if\s+err)",
            "file_pattern": "*.go",
            "severity": "high",
            "category": "error-handling",
            "message": "Error return value not checked — handle the error or explicitly ignore it.",
            "multiline": True,
        },
        {
            "id": "go/fmt-errorf",
            "pattern": r"fmt\.Errorf\(",
            "file_pattern": "*.go",
            "severity": "info",
            "category": "best-practice",
            "message": "Consider using `errors.New` for simple errors or `%w` for wrapping.",
        },
    ],
    "java-best-practices": [
        {
            "id": "java/no-system-out",
            "pattern": r"System\.(out|err)\.print",
            "file_pattern": "*.java",
            "severity": "medium",
            "category": "best-practice",
            "message": "Use a logging framework (SLF4J/Log4j) instead of System.out.",
        },
        {
            "id": "java/no-catch-exception",
            "pattern": r"catch\s*\(\s*Exception\s+",
            "file_pattern": "*.java",
            "severity": "high",
            "category": "error-handling",
            "message": "Don't catch generic `Exception` — catch specific exception types.",
        },
        {
            "id": "java/no-raw-types",
            "pattern": r"\b(?:List|Map|Set|Collection|Iterator)\s+\w+\s*[;=]",
            "file_pattern": "*.java",
            "severity": "medium",
            "category": "maintainability",
            "message": "Use generic types (e.g., `List<String>`) instead of raw types.",
        },
    ],
    "rust-best-practices": [
        {
            "id": "rs/no-unwrap",
            "pattern": r"\.unwrap\(\)",
            "file_pattern": "*.rs",
            "severity": "medium",
            "category": "error-handling",
            "message": "Avoid `.unwrap()` — use `?`, `.expect()`, or match instead.",
            "paths_ignore": ["tests/*", "test_*"],
        },
        {
            "id": "rs/no-clone-needless",
            "llm_check": "Flag unnecessary `.clone()` calls where a reference or borrow would suffice.",
            "file_pattern": "*.rs",
            "severity": "low",
            "category": "performance",
        },
    ],
}


# ── Rule Loading ────────────────────────────────────────────────────

def load_rules_from_config(config_data: dict[str, Any]) -> list[Rule]:
    """Load rules from parsed .codewise.yaml config.

    Args:
        config_data: The parsed YAML dict, specifically the `rules:` section.
    """
    rules_section = config_data.get("rules", {})
    rules: list[Rule] = []

    # Load standard packs
    packs = rules_section.get("enable_packs", [])
    for pack_name in packs:
        pack_rules = STANDARD_PACKS.get(pack_name)
        if pack_rules is None:
            logger.warning("Unknown rule pack: %s (available: %s)",
                           pack_name, ", ".join(STANDARD_PACKS.keys()))
            continue
        for rd in pack_rules:
            rules.append(_dict_to_rule(rd, pack=pack_name))

    # Load custom rules
    custom = rules_section.get("custom", [])
    for rd in custom:
        rules.append(_dict_to_rule(rd, pack="custom"))

    # Apply disabled list
    disabled_ids = set(rules_section.get("disable", []))
    for r in rules:
        if r.id in disabled_ids:
            r.enabled = False

    # Apply severity overrides
    overrides = rules_section.get("severity_overrides", {})
    for r in rules:
        if r.id in overrides:
            try:
                r.severity = Severity(overrides[r.id])
            except ValueError:
                logger.warning("Invalid severity override for %s: %s", r.id, overrides[r.id])

    return rules


def _dict_to_rule(data: dict[str, Any], pack: str | None = None) -> Rule:
    """Convert a dict (from YAML or standard pack) to a Rule object."""
    severity = Severity.MEDIUM
    if "severity" in data:
        try:
            severity = Severity(data["severity"])
        except ValueError:
            logger.warning("Invalid severity '%s' for rule %s", data["severity"], data.get("id"))

    category = ReviewCategory.BEST_PRACTICE
    if "category" in data:
        try:
            category = ReviewCategory(data["category"])
        except ValueError:
            logger.warning("Invalid category '%s' for rule %s", data["category"], data.get("id"))

    file_pattern = data.get("file_pattern", "*")
    # Expand brace patterns like *.{js,ts} into multiple globs
    # (fnmatch doesn't support braces)
    # We'll handle this in matches_file instead

    return Rule(
        id=data.get("id", f"custom-{id(data)}"),
        severity=severity,
        category=category,
        message=data.get("message", ""),
        pattern=data.get("pattern"),
        file_pattern=file_pattern,
        multiline=data.get("multiline", False),
        llm_check=data.get("llm_check"),
        branches=data.get("branches", []),
        paths_only=data.get("paths_only", []),
        paths_ignore=data.get("paths_ignore", []),
        pack=pack,
        docs_url=data.get("docs_url"),
        autofix=data.get("autofix"),
        enabled=data.get("enabled", True),
    )


def get_available_packs() -> dict[str, int]:
    """Return pack names and their rule counts."""
    return {name: len(rules) for name, rules in STANDARD_PACKS.items()}


# ── Rule Execution (Regex) ──────────────────────────────────────────

def run_regex_rules(
    changes: list[FileChange],
    rules: list[Rule],
    branch: str | None = None,
) -> list[ReviewFinding]:
    """Run all regex-based rules against file changes. Fast, no LLM calls.

    Returns ReviewFinding objects for integration with the rest of the pipeline.
    """
    findings: list[ReviewFinding] = []

    regex_rules = [r for r in rules if r.enabled and r.pattern and r.rule_type in (RuleType.REGEX, RuleType.COMPOSITE)]

    for change in changes:
        content = change.full_content or change.patch
        if not content:
            continue

        for rule in regex_rules:
            if not rule.matches_file(change.path):
                continue
            if not rule.matches_branch(branch):
                continue

            flags = re.MULTILINE if rule.multiline else 0
            try:
                # Also expand brace patterns
                if not _file_matches_with_braces(change.path, rule.file_pattern):
                    continue

                for match in re.finditer(rule.pattern, content, flags):
                    line_no = content[:match.start()].count("\n") + 1
                    findings.append(ReviewFinding(
                        file=change.path,
                        line=line_no,
                        severity=rule.severity,
                        category=rule.category,
                        title=f"[{rule.id}] {rule.message[:80]}" if rule.message else f"Rule violation: {rule.id}",
                        description=rule.message,
                        suggestion=rule.autofix if rule.autofix else None,
                        code_before=match.group(0)[:200],
                    ))
            except re.error as e:
                logger.warning("Invalid regex in rule %s: %s", rule.id, e)

    return findings


def get_llm_rules(
    rules: list[Rule],
    changes: list[FileChange],
    branch: str | None = None,
) -> list[tuple[Rule, list[FileChange]]]:
    """Get LLM rules matched against their applicable files.

    Returns (rule, applicable_changes) pairs for the review engine to send
    as extra instructions to the LLM.
    """
    llm_rules = [r for r in rules if r.enabled and r.llm_check and r.rule_type in (RuleType.LLM, RuleType.COMPOSITE)]
    result: list[tuple[Rule, list[FileChange]]] = []

    for rule in llm_rules:
        if not rule.matches_branch(branch):
            continue
        applicable = [c for c in changes if rule.matches_file(c.path) and _file_matches_with_braces(c.path, rule.file_pattern)]
        if applicable:
            result.append((rule, applicable))

    return result


def build_llm_rules_instruction(rules: list[Rule], changes: list[FileChange], branch: str | None = None) -> str:
    """Build an extra instruction string from LLM rules for appending to the review prompt.

    This gets injected as `extra_instructions` so the LLM knows to enforce
    the user's custom rules during its review pass.
    """
    matched = get_llm_rules(rules, changes, branch)
    if not matched:
        return ""

    lines = ["\n\n## Custom Rules (MUST enforce)\n"]
    for rule, files in matched:
        file_list = ", ".join(c.path for c in files[:5])
        if len(files) > 5:
            file_list += f" (+{len(files) - 5} more)"
        lines.append(
            f"- **[{rule.id}]** (severity: {rule.severity.value}): "
            f"{rule.llm_check} — applies to: {file_list}"
        )

    return "\n".join(lines)


def _file_matches_with_braces(path: str, pattern: str) -> bool:
    """Match file path against a pattern that may contain {a,b} brace expansion."""
    if "{" in pattern and "}" in pattern:
        # Expand *.{js,ts,jsx} into separate globs
        prefix, rest = pattern.split("{", 1)
        options, suffix = rest.split("}", 1)
        for opt in options.split(","):
            expanded = f"{prefix}{opt.strip()}{suffix}"
            if fnmatch.fnmatch(path, expanded) or fnmatch.fnmatch(Path(path).name, expanded):
                return True
        return False
    return fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(Path(path).name, pattern)


# ── Summary Helpers ─────────────────────────────────────────────────

def summarize_rules(rules: list[Rule]) -> str:
    """Return a human-readable summary of loaded rules."""
    if not rules:
        return "No rules configured."

    enabled = [r for r in rules if r.enabled]
    by_pack: dict[str, list[Rule]] = {}
    for r in enabled:
        by_pack.setdefault(r.pack or "custom", []).append(r)

    lines = [f"**{len(enabled)} rules active** ({len(rules) - len(enabled)} disabled)\n"]
    for pack, pack_rules in sorted(by_pack.items()):
        regex_count = sum(1 for r in pack_rules if r.rule_type == RuleType.REGEX)
        llm_count = sum(1 for r in pack_rules if r.rule_type in (RuleType.LLM, RuleType.COMPOSITE))
        lines.append(f"  [{pack}] {len(pack_rules)} rules ({regex_count} regex, {llm_count} LLM)")

    return "\n".join(lines)
