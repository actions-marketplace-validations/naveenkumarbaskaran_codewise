"""Test generation engine — generates test cases for source code."""

from __future__ import annotations

import logging

from codewise.core.diff import detect_language, read_file_content
from codewise.llm.prompts import (
    TESTGEN_SYSTEM,
    TESTGEN_USER,
    build_system_prompt,
    build_user_prompt,
)
from codewise.llm.provider import completion_json
from codewise.models import CodewiseConfig, GeneratedTest, TestGenResult

logger = logging.getLogger("codewise.testgen")


async def generate_tests(
    path: str,
    content: str | None = None,
    config: CodewiseConfig | None = None,
    repo_root: str | None = None,
) -> TestGenResult:
    """Generate test cases for a source file.

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
            return TestGenResult(summary=f"Could not read file: {path}")

    language = detect_language(path)

    system = build_system_prompt(
        TESTGEN_SYSTEM,
        extra_instructions=config.extra_instructions,
        test_framework=config.test_framework,
    )
    user = build_user_prompt(
        TESTGEN_USER,
        language=language,
        code_content=content,
        context=f"Source file: {path}",
    )

    try:
        data, tokens = await completion_json(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            config,
        )

        tests = []
        for t in data.get("tests", []):
            try:
                test = GeneratedTest(**t, framework=config.test_framework)
                tests.append(test)
            except Exception as e:
                logger.warning("Skipping malformed test: %s", e)

        return TestGenResult(
            tests=tests,
            summary=data.get("summary", f"Generated {len(tests)} test(s) for {path}"),
            coverage_targets=data.get("coverage_targets", []),
            model=config.model,
            tokens_used=tokens,
        )

    except Exception as e:
        logger.error("Test generation failed for %s: %s", path, e)
        return TestGenResult(summary=f"Test generation failed: {e}")


async def generate_tests_for_diff(
    paths: list[str],
    config: CodewiseConfig,
    repo_root: str | None = None,
) -> TestGenResult:
    """Generate tests for multiple changed files."""
    all_tests: list[GeneratedTest] = []
    all_targets: list[str] = []
    total_tokens = 0

    for path in paths:
        content = read_file_content(path, repo_root)
        if content is None:
            continue

        result = await generate_tests(path, content, config, repo_root)
        all_tests.extend(result.tests)
        all_targets.extend(result.coverage_targets)
        total_tokens += result.tokens_used

    return TestGenResult(
        tests=all_tests,
        summary=f"Generated {len(all_tests)} test(s) across {len(paths)} file(s)",
        coverage_targets=all_targets,
        model=config.model,
        tokens_used=total_tokens,
    )
