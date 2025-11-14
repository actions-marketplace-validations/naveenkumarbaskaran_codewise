"""Data models used across codewise."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ── Severity & Categories ──────────────────────────────────────────

class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class ReviewCategory(str, Enum):
    BUG = "bug"
    PERFORMANCE = "performance"
    READABILITY = "readability"
    MAINTAINABILITY = "maintainability"
    BEST_PRACTICE = "best-practice"
    ERROR_HANDLING = "error-handling"
    CONCURRENCY = "concurrency"
    NAMING = "naming"
    DUPLICATION = "duplication"
    COMPLEXITY = "complexity"


class SecurityCategory(str, Enum):
    INJECTION = "injection"
    XSS = "xss"
    AUTH = "authentication"
    SECRETS = "hardcoded-secret"
    CRYPTO = "weak-cryptography"
    PATH_TRAVERSAL = "path-traversal"
    SSRF = "ssrf"
    DESERIALIZATION = "insecure-deserialization"
    DEPENDENCY = "vulnerable-dependency"
    MISCONFIGURATION = "misconfiguration"
    INFORMATION_DISCLOSURE = "information-disclosure"


# ── File & Diff Models ─────────────────────────────────────────────

class FileChange(BaseModel):
    """Represents a single changed file in a diff."""

    path: str
    language: str = "unknown"
    added_lines: list[str] = Field(default_factory=list)
    removed_lines: list[str] = Field(default_factory=list)
    patch: str = ""
    full_content: str | None = None
    is_new: bool = False
    is_deleted: bool = False
    hunks: list[DiffHunk] = Field(default_factory=list)


class DiffHunk(BaseModel):
    """A contiguous block of changes in a diff."""

    start_line: int
    end_line: int
    header: str = ""
    content: str = ""


# Resolve forward reference
FileChange.model_rebuild()


# ── Review Models ──────────────────────────────────────────────────

class ReviewFinding(BaseModel):
    """A single finding from code review."""

    file: str
    line: int | None = None
    end_line: int | None = None
    severity: Severity
    category: ReviewCategory
    title: str
    description: str
    suggestion: str | None = None
    code_before: str | None = None
    code_after: str | None = None


class ReviewResult(BaseModel):
    """Complete review result for one or more files."""

    findings: list[ReviewFinding] = Field(default_factory=list)
    summary: str = ""
    score: int | None = Field(None, ge=0, le=100, description="Overall quality 0-100")
    files_reviewed: int = 0
    model: str = ""
    tokens_used: int = 0

    @property
    def critical_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.CRITICAL)

    @property
    def high_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.HIGH)


# ── Security Models ────────────────────────────────────────────────

class SecurityFinding(BaseModel):
    """A security vulnerability or risk."""

    file: str
    line: int | None = None
    end_line: int | None = None
    severity: Severity
    category: SecurityCategory
    title: str
    description: str
    cwe: str | None = Field(None, description="CWE identifier, e.g. CWE-79")
    owasp: str | None = Field(None, description="OWASP Top 10 category")
    recommendation: str = ""
    evidence: str | None = None


class SecurityResult(BaseModel):
    """Security scan result."""

    findings: list[SecurityFinding] = Field(default_factory=list)
    summary: str = ""
    files_scanned: int = 0
    risk_level: Severity = Severity.INFO
    model: str = ""
    tokens_used: int = 0


# ── Test Generation Models ─────────────────────────────────────────

class GeneratedTest(BaseModel):
    """A generated test case."""

    file: str
    test_name: str
    test_code: str
    target_function: str | None = None
    description: str = ""
    framework: str = "pytest"


class TestGenResult(BaseModel):
    """Test generation result."""

    tests: list[GeneratedTest] = Field(default_factory=list)
    summary: str = ""
    coverage_targets: list[str] = Field(default_factory=list)
    model: str = ""
    tokens_used: int = 0


# ── Documentation Generation Models ───────────────────────────────

class DocChange(BaseModel):
    """A documentation improvement."""

    file: str
    line: int | None = None
    doc_type: str = "docstring"  # docstring, readme, comment, type-hint
    original: str | None = None
    generated: str = ""
    target_symbol: str | None = None


class DocGenResult(BaseModel):
    """Documentation generation result."""

    changes: list[DocChange] = Field(default_factory=list)
    summary: str = ""
    model: str = ""
    tokens_used: int = 0


# ── Configuration ──────────────────────────────────────────────────

class CodewiseConfig(BaseModel):
    """Configuration loaded from .codewise.yaml or CLI flags."""

    # LLM
    model: str = "gpt-4o-mini"
    provider: str | None = None  # auto-detected from model name
    api_key: str | None = None
    api_base: str | None = None
    temperature: float = 0.1
    max_tokens: int = 4096

    # Review
    review_enabled: bool = True
    review_categories: list[ReviewCategory] | None = None
    min_severity: Severity = Severity.LOW

    # Security
    security_enabled: bool = True
    security_categories: list[SecurityCategory] | None = None

    # Test generation
    testgen_enabled: bool = False
    test_framework: str = "pytest"

    # Doc generation
    docgen_enabled: bool = False

    # Filtering
    include_patterns: list[str] = Field(default_factory=lambda: ["**/*"])
    exclude_patterns: list[str] = Field(
        default_factory=lambda: [
            "**/*.lock",
            "**/node_modules/**",
            "**/.git/**",
            "**/dist/**",
            "**/build/**",
            "**/__pycache__/**",
            "**/*.min.js",
            "**/*.min.css",
        ]
    )
    max_file_size: int = 100_000  # bytes

    # Output
    output_format: str = "terminal"  # terminal, json, sarif, markdown
    fail_on: Severity | None = Severity.HIGH  # exit code 1 if findings >= this severity

    # Git
    base_ref: str | None = None  # e.g. main, origin/main
    head_ref: str | None = None

    # Extra context
    extra_instructions: str | None = None  # custom instructions appended to prompts


# ── SARIF Output ───────────────────────────────────────────────────

class SarifResult(BaseModel):
    """Simplified SARIF 2.1.0 result for GitHub Security integration."""

    ruleId: str
    level: str  # error, warning, note
    message: dict[str, str]
    locations: list[dict[str, Any]] = Field(default_factory=list)


class SarifRun(BaseModel):
    tool: dict[str, Any]
    results: list[SarifResult] = Field(default_factory=list)


class SarifReport(BaseModel):
    version: str = "2.1.0"
    schema_url: str = Field(
        "https://json.schemastore.org/sarif-2.1.0.json",
        alias="$schema",
    )
    runs: list[SarifRun] = Field(default_factory=list)
