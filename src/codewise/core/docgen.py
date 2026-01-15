"""Documentation generation engine — generates/improves docstrings and docs."""

from __future__ import annotations

import logging

from codewise.core.diff import detect_language, read_file_content
from codewise.llm.prompts import (
    DOCGEN_SYSTEM,
    DOCGEN_USER,
    build_system_prompt,
    build_user_prompt,
)
from codewise.llm.provider import completion_json
from codewise.models import CodewiseConfig, DocChange, DocGenResult

logger = logging.getLogger("codewise.docgen")


async def generate_docs(
    path: str,
    content: str | None = None,
    config: CodewiseConfig | None = None,
    repo_root: str | None = None,
) -> DocGenResult:
    """Generate or improve documentation for a source file.

    Args:
        path: Path to the source file.
        content: File content (read from disk if not provided).
        config: Codewise configuration.
        repo_root: Repository root for resolving paths.
    """
    config = config or CodewiseConfig()

    if content is None:
        content = read_file_content(path, repo_root)
        if content is None:
            return DocGenResult(summary=f"Could not read file: {path}")

    language = detect_language(path)

    system = build_system_prompt(
        DOCGEN_SYSTEM,
        extra_instructions=config.extra_instructions,
    )
    user = build_user_prompt(
        DOCGEN_USER,
        language=language,
        code_content=content,
        context=f"Source file: {path}",
    )

    try:
        data, tokens = await completion_json(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            config,
        )

        changes = []
        for c in data.get("changes", []):
            try:
                change = DocChange(**c)
                changes.append(change)
            except Exception as e:
                logger.warning("Skipping malformed doc change: %s", e)

        return DocGenResult(
            changes=changes,
            summary=data.get("summary", f"Generated docs for {path}"),
            model=config.model,
            tokens_used=tokens,
        )

    except Exception as e:
        logger.error("Doc generation failed for %s: %s", path, e)
        return DocGenResult(summary=f"Doc generation failed: {e}")


async def generate_docs_batch(
    paths: list[str],
    config: CodewiseConfig,
    repo_root: str | None = None,
) -> DocGenResult:
    """Generate docs for multiple files."""
    all_changes: list[DocChange] = []
    total_tokens = 0

    for path in paths:
        content = read_file_content(path, repo_root)
        if content is None:
            continue

        result = await generate_docs(path, content, config, repo_root)
        all_changes.extend(result.changes)
        total_tokens += result.tokens_used

    return DocGenResult(
        changes=all_changes,
        summary=f"Generated documentation for {len(paths)} file(s), {len(all_changes)} change(s)",
        model=config.model,
        tokens_used=total_tokens,
    )
