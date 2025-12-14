"""Code review engine — analyzes diffs/files and produces review findings."""

from __future__ import annotations

import logging

from codewise.llm.prompts import (
    REVIEW_SYSTEM,
    REVIEW_USER,
    build_system_prompt,
    build_user_prompt,
)
from codewise.llm.provider import completion_json
from codewise.models import (
    CodewiseConfig,
    FileChange,
    ReviewFinding,
    ReviewResult,
    Severity,
)

logger = logging.getLogger("codewise.reviewer")

# Max diff size to send in one LLM call (chars)
MAX_DIFF_CHUNK = 40_000


async def review_changes(
    changes: list[FileChange],
    config: CodewiseConfig,
) -> ReviewResult:
    """Review a list of file changes and return findings.

    Chunks large diffs to stay within context limits.
    """
    if not changes:
        return ReviewResult(summary="No changes to review.", files_reviewed=0)

    all_findings: list[ReviewFinding] = []
    total_tokens = 0
    score_sum = 0
    chunk_count = 0

    # Build chunks of diffs that fit within the limit
    chunks = _chunk_diffs(changes)

    for chunk in chunks:
        diff_text = "\n\n".join(c.patch for c in chunk)
        languages = {c.language for c in chunk if c.language != "unknown"}
        context = f"Languages: {', '.join(languages)}" if languages else ""

        system = build_system_prompt(
            REVIEW_SYSTEM,
            extra_instructions=config.extra_instructions,
        )
        user = build_user_prompt(
            REVIEW_USER,
            diff_content=diff_text,
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
                    finding = ReviewFinding(**f)
                    # Apply severity filter
                    if _severity_rank(finding.severity) >= _severity_rank(config.min_severity):
                        all_findings.append(finding)
                except Exception as e:
                    logger.warning("Skipping malformed finding: %s", e)

            if "score" in data and data["score"] is not None:
                score_sum += data["score"]
                chunk_count += 1

        except Exception as e:
            logger.error("Review chunk failed: %s", e)

    avg_score = round(score_sum / chunk_count) if chunk_count > 0 else None

    return ReviewResult(
        findings=all_findings,
        summary=_build_summary(all_findings, len(changes)),
        score=avg_score,
        files_reviewed=len(changes),
        model=config.model,
        tokens_used=total_tokens,
    )


async def review_file(
    path: str,
    content: str,
    config: CodewiseConfig,
) -> ReviewResult:
    """Review a single file's full content (not a diff)."""
    from codewise.core.diff import detect_language

    language = detect_language(path)
    change = FileChange(
        path=path,
        language=language,
        patch=f"--- a/{path}\n+++ b/{path}\n\n{content}",
        full_content=content,
        is_new=True,
    )
    return await review_changes([change], config)


def _chunk_diffs(changes: list[FileChange]) -> list[list[FileChange]]:
    """Split changes into chunks that fit within MAX_DIFF_CHUNK."""
    chunks: list[list[FileChange]] = []
    current: list[FileChange] = []
    current_size = 0

    for change in changes:
        patch_size = len(change.patch)
        if current_size + patch_size > MAX_DIFF_CHUNK and current:
            chunks.append(current)
            current = []
            current_size = 0
        current.append(change)
        current_size += patch_size

    if current:
        chunks.append(current)
    return chunks


def _severity_rank(severity: Severity) -> int:
    """Numeric rank for severity comparison."""
    return {
        Severity.INFO: 0,
        Severity.LOW: 1,
        Severity.MEDIUM: 2,
        Severity.HIGH: 3,
        Severity.CRITICAL: 4,
    }.get(severity, 0)


def _build_summary(findings: list[ReviewFinding], files_reviewed: int) -> str:
    """Build a human-readable summary from findings."""
    if not findings:
        return f"Reviewed {files_reviewed} file(s) — no issues found. Code looks good!"

    by_severity = {}
    for f in findings:
        by_severity.setdefault(f.severity.value, 0)
        by_severity[f.severity.value] += 1

    parts = [f"Reviewed {files_reviewed} file(s), found {len(findings)} issue(s):"]
    for sev in ["critical", "high", "medium", "low", "info"]:
        count = by_severity.get(sev, 0)
        if count:
            parts.append(f"  {sev}: {count}")
    return "\n".join(parts)
