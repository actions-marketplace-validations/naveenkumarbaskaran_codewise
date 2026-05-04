"""Security scanning engine — analyzes code for vulnerabilities."""

from __future__ import annotations

import logging

from codewise.llm.prompts import (
    SECURITY_SYSTEM,
    SECURITY_USER,
    build_system_prompt,
    build_user_prompt,
)
from codewise.llm.provider import completion_json
from codewise.models import (
    CodewiseConfig,
    FileChange,
    SecurityFinding,
    SecurityResult,
    Severity,
)

logger = logging.getLogger("codewise.security")

# File extensions most likely to contain security issues
SECURITY_RELEVANT_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rb", ".php",
    ".cs", ".rs", ".kt", ".swift", ".scala", ".sh", ".bash",
    ".yaml", ".yml", ".toml", ".json", ".xml", ".env", ".cfg", ".ini",
    ".sql", ".html", ".tf", ".dockerfile",
}


async def scan_changes(
    changes: list[FileChange],
    config: CodewiseConfig,
) -> SecurityResult:
    """Scan file changes for security vulnerabilities."""
    # Filter to security-relevant files
    relevant = [c for c in changes if _is_security_relevant(c.path)]
    if not relevant:
        return SecurityResult(
            summary="No security-relevant files in the changes.",
            files_scanned=0,
        )

    all_findings: list[SecurityFinding] = []
    total_tokens = 0

    # Process files in batches
    for batch in _batch_files(relevant, max_chars=40_000):
        code_content = "\n\n".join(
            f"### File: {c.path}\n```\n{c.full_content or c.patch}\n```"
            for c in batch
        )
        languages = {c.language for c in batch if c.language != "unknown"}
        context = f"Languages: {', '.join(languages)}" if languages else ""

        system = build_system_prompt(
            SECURITY_SYSTEM,
            extra_instructions=config.extra_instructions,
        )
        user = build_user_prompt(
            SECURITY_USER,
            code_content=code_content,
            context=context,
        )

        try:
            data, tokens = await completion_json(
                [{"role": "system", "content": system}, {"role": "user", "content": user}],
                config,
            )
            total_tokens += tokens

            for f in data.get("findings", []):
                try:
                    finding = SecurityFinding(**f)
                    # Apply category filter if configured
                    if config.security_categories and finding.category not in config.security_categories:
                        continue
                    all_findings.append(finding)
                except Exception as e:
                    logger.warning("Skipping malformed security finding: %s", e)

        except Exception as e:
            logger.error("Security scan batch failed: %s", e)

    risk_level = _compute_risk_level(all_findings)

    return SecurityResult(
        findings=all_findings,
        summary=_build_summary(all_findings, len(relevant)),
        files_scanned=len(relevant),
        risk_level=risk_level,
        model=config.model,
        tokens_used=total_tokens,
    )


async def scan_file(
    path: str,
    content: str,
    config: CodewiseConfig,
) -> SecurityResult:
    """Scan a single file for security vulnerabilities."""
    from codewise.core.diff import detect_language

    change = FileChange(
        path=path,
        language=detect_language(path),
        full_content=content,
        patch=content,
    )
    return await scan_changes([change], config)


def _is_security_relevant(path: str) -> bool:
    """Check if a file extension is security-relevant."""
    from pathlib import Path as P
    name = P(path).name.lower()
    ext = P(path).suffix.lower()
    # Always scan these files
    if name in {"dockerfile", ".env", ".env.local", ".env.production", "docker-compose.yml",
                "docker-compose.yaml", "secrets.yaml", "secrets.yml"}:
        return True
    return ext in SECURITY_RELEVANT_EXTENSIONS


def _batch_files(changes: list[FileChange], max_chars: int) -> list[list[FileChange]]:
    """Batch files to stay within character limit."""
    batches: list[list[FileChange]] = []
    current: list[FileChange] = []
    current_size = 0

    for c in changes:
        size = len(c.full_content or c.patch)
        if current_size + size > max_chars and current:
            batches.append(current)
            current = []
            current_size = 0
        current.append(c)
        current_size += size

    if current:
        batches.append(current)
    return batches


def _compute_risk_level(findings: list[SecurityFinding]) -> Severity:
    """Determine overall risk level from findings."""
    if any(f.severity == Severity.CRITICAL for f in findings):
        return Severity.CRITICAL
    if any(f.severity == Severity.HIGH for f in findings):
        return Severity.HIGH
    if any(f.severity == Severity.MEDIUM for f in findings):
        return Severity.MEDIUM
    if any(f.severity == Severity.LOW for f in findings):
        return Severity.LOW
    return Severity.INFO


def _build_summary(findings: list[SecurityFinding], files_scanned: int) -> str:
    """Build scan summary."""
    if not findings:
        return f"Scanned {files_scanned} file(s) — no security issues found."

    by_severity = {}
    for f in findings:
        by_severity.setdefault(f.severity.value, 0)
        by_severity[f.severity.value] += 1

    parts = [f"Scanned {files_scanned} file(s), found {len(findings)} security issue(s):"]
    for sev in ["critical", "high", "medium", "low", "info"]:
        count = by_severity.get(sev, 0)
        if count:
            parts.append(f"  {sev}: {count}")
    return "\n".join(parts)
