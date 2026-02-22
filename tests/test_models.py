"""Tests for codewise models."""

from codewise.models import (
    CodewiseConfig,
    DiffHunk,
    FileChange,
    ReviewCategory,
    ReviewFinding,
    ReviewResult,
    SecurityCategory,
    SecurityFinding,
    SecurityResult,
    Severity,
)


def test_severity_enum():
    assert Severity.CRITICAL.value == "critical"
    assert Severity("high") == Severity.HIGH


def test_review_finding():
    f = ReviewFinding(
        file="main.py",
        line=42,
        severity=Severity.HIGH,
        category=ReviewCategory.BUG,
        title="Null pointer",
        description="Variable may be None",
    )
    assert f.file == "main.py"
    assert f.line == 42
    assert f.severity == Severity.HIGH


def test_review_result_counts():
    result = ReviewResult(
        findings=[
            ReviewFinding(file="a.py", severity=Severity.CRITICAL, category=ReviewCategory.BUG, title="t1", description="d1"),
            ReviewFinding(file="b.py", severity=Severity.HIGH, category=ReviewCategory.BUG, title="t2", description="d2"),
            ReviewFinding(file="c.py", severity=Severity.CRITICAL, category=ReviewCategory.BUG, title="t3", description="d3"),
            ReviewFinding(file="d.py", severity=Severity.LOW, category=ReviewCategory.NAMING, title="t4", description="d4"),
        ],
        files_reviewed=4,
    )
    assert result.critical_count == 2
    assert result.high_count == 1


def test_file_change():
    change = FileChange(
        path="src/app.py",
        language="python",
        added_lines=["import os"],
        removed_lines=[],
        patch="diff...",
        is_new=True,
    )
    assert change.path == "src/app.py"
    assert change.is_new is True


def test_security_finding():
    f = SecurityFinding(
        file="auth.py",
        line=10,
        severity=Severity.CRITICAL,
        category=SecurityCategory.INJECTION,
        title="SQL Injection",
        description="Unparameterized query",
        cwe="CWE-89",
        owasp="A03:2021",
    )
    assert f.cwe == "CWE-89"


def test_config_defaults():
    config = CodewiseConfig()
    assert config.model == "gpt-4o-mini"
    assert config.temperature == 0.1
    assert config.review_enabled is True
    assert config.security_enabled is True
    assert config.fail_on == Severity.HIGH
    assert "**/*.lock" in config.exclude_patterns
