"""Configuration loader — reads .codewise.yaml with layered config.

Config resolution order (later wins):
1. Built-in defaults (CodewiseConfig defaults)
2. Global config: ~/.config/codewise/config.yaml
3. Repo config: .codewise.yaml (in repo root)
4. Environment variables: CODEWISE_MODEL, CODEWISE_API_KEY, etc.
5. CLI flags (applied last, highest priority)
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import yaml

from codewise.models import (
    CodewiseConfig,
    ReviewCategory,
    SecurityCategory,
    Severity,
)
from codewise.rules import Rule, load_rules_from_config

logger = logging.getLogger("codewise.config")

# Default config file names
CONFIG_FILENAMES = [".codewise.yaml", ".codewise.yml", "codewise.yaml"]
GLOBAL_CONFIG_DIR = Path.home() / ".config" / "codewise"


def find_config_file(start_dir: str | Path | None = None) -> Path | None:
    """Walk up from start_dir looking for a config file.

    Stops at filesystem root or when a .git directory is found.
    """
    start = Path(start_dir) if start_dir else Path.cwd()

    current = start.resolve()
    while True:
        for name in CONFIG_FILENAMES:
            candidate = current / name
            if candidate.is_file():
                return candidate

        # Stop at .git boundary or root
        if (current / ".git").exists():
            break
        parent = current.parent
        if parent == current:
            break
        current = parent

    return None


def load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML config file."""
    try:
        with open(path) as f:
            data = yaml.safe_load(f)
            return data if isinstance(data, dict) else {}
    except Exception as e:
        logger.warning("Failed to load config from %s: %s", path, e)
        return {}


def load_config(
    config_path: str | None = None,
    repo_root: str | None = None,
    overrides: dict[str, Any] | None = None,
) -> tuple[CodewiseConfig, list[Rule]]:
    """Load configuration from all sources and return (config, rules).

    Args:
        config_path: Explicit config file path (highest YAML priority).
        repo_root: Repository root for finding .codewise.yaml.
        overrides: CLI-level overrides (highest overall priority).

    Returns:
        Tuple of (CodewiseConfig, list[Rule]) ready to use.
    """
    merged: dict[str, Any] = {}

    # 1. Global config
    global_config = GLOBAL_CONFIG_DIR / "config.yaml"
    if global_config.is_file():
        logger.debug("Loading global config from %s", global_config)
        merged.update(load_yaml(global_config))

    # 2. Repo config
    if config_path:
        repo_yaml = load_yaml(Path(config_path))
        logger.debug("Loading config from explicit path: %s", config_path)
        merged = _deep_merge(merged, repo_yaml)
    else:
        found = find_config_file(repo_root)
        if found:
            logger.debug("Found repo config at %s", found)
            merged = _deep_merge(merged, load_yaml(found))

    # 3. Environment variables
    env_overrides = _env_overrides()
    merged = _deep_merge(merged, env_overrides)

    # 4. CLI overrides
    if overrides:
        merged = _deep_merge(merged, overrides)

    # Build config object
    config = _build_config(merged)

    # Load rules
    rules = load_rules_from_config(merged)

    return config, rules


def _env_overrides() -> dict[str, Any]:
    """Read CODEWISE_* environment variables."""
    mapping: dict[str, str] = {
        "CODEWISE_MODEL": "model",
        "CODEWISE_API_KEY": "api_key",
        "CODEWISE_API_BASE": "api_base",
        "CODEWISE_PROVIDER": "provider",
        "CODEWISE_TEMPERATURE": "temperature",
        "CODEWISE_MAX_TOKENS": "max_tokens",
        "CODEWISE_OUTPUT_FORMAT": "output_format",
        "CODEWISE_MIN_SEVERITY": "min_severity",
        "CODEWISE_FAIL_ON": "fail_on",
    }
    result: dict[str, Any] = {}
    for env_key, config_key in mapping.items():
        val = os.environ.get(env_key)
        if val is not None:
            # Type coercion
            if config_key in ("temperature",):
                result[config_key] = float(val)
            elif config_key in ("max_tokens",):
                result[config_key] = int(val)
            else:
                result[config_key] = val
    return result


def _build_config(data: dict[str, Any]) -> CodewiseConfig:
    """Build a CodewiseConfig from merged dict."""
    kwargs: dict[str, Any] = {}

    # Simple string/number fields
    for key in ("model", "provider", "api_key", "api_base", "output_format",
                "base_ref", "head_ref", "extra_instructions", "test_framework"):
        if key in data:
            kwargs[key] = data[key]

    for key in ("temperature",):
        if key in data:
            kwargs[key] = float(data[key])

    for key in ("max_tokens", "max_file_size"):
        if key in data:
            kwargs[key] = int(data[key])

    # Boolean fields
    for key in ("review_enabled", "security_enabled", "testgen_enabled", "docgen_enabled"):
        if key in data:
            kwargs[key] = bool(data[key])

    # Severity
    if "min_severity" in data:
        try:
            kwargs["min_severity"] = Severity(data["min_severity"])
        except ValueError:
            pass

    if "fail_on" in data:
        val = data["fail_on"]
        if val is None or val == "none":
            kwargs["fail_on"] = None
        else:
            try:
                kwargs["fail_on"] = Severity(val)
            except ValueError:
                pass

    # Lists
    if "include_patterns" in data:
        kwargs["include_patterns"] = data["include_patterns"]
    if "exclude_patterns" in data:
        kwargs["exclude_patterns"] = data["exclude_patterns"]

    # Category filters
    if "review_categories" in data:
        try:
            kwargs["review_categories"] = [ReviewCategory(c) for c in data["review_categories"]]
        except ValueError:
            pass
    if "security_categories" in data:
        try:
            kwargs["security_categories"] = [SecurityCategory(c) for c in data["security_categories"]]
        except ValueError:
            pass

    return CodewiseConfig(**kwargs)


def _deep_merge(base: dict, override: dict) -> dict:
    """Deep-merge two dicts. override wins for scalar values, lists are replaced."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def generate_default_config() -> str:
    """Generate a commented .codewise.yaml template."""
    return """\
# Codewise configuration — place in your repo root as .codewise.yaml
# Docs: https://github.com/naveenkumarbaskaran/codewise#configuration

# ── LLM Settings ──────────────────────────────────────────────────
model: gpt-4o-mini          # Any litellm-supported model
# provider: openai           # Auto-detected from model name
# api_key: sk-...            # Or set CODEWISE_API_KEY env var
# api_base: https://...      # Custom endpoint (Ollama, Azure, etc.)
temperature: 0.1
max_tokens: 4096

# ── Capabilities ──────────────────────────────────────────────────
review_enabled: true
security_enabled: true
testgen_enabled: false
docgen_enabled: false

# ── Review Settings ───────────────────────────────────────────────
min_severity: low            # Minimum severity to report: critical|high|medium|low|info
fail_on: high                # Exit code 1 if findings >= this severity (or "none")
output_format: terminal      # terminal|json|sarif|markdown
# extra_instructions: "Focus on thread safety in async handlers."

# ── File Filtering ────────────────────────────────────────────────
include_patterns:
  - "**/*"
exclude_patterns:
  - "**/*.lock"
  - "**/node_modules/**"
  - "**/.git/**"
  - "**/dist/**"
  - "**/build/**"
  - "**/__pycache__/**"
  - "**/*.min.js"
  - "**/*.min.css"
max_file_size: 100000        # Skip files larger than this (bytes)

# ── Rules ─────────────────────────────────────────────────────────
rules:
  # Enable standard rule packs (see: codewise rules --list-packs)
  enable_packs:
    - python-best-practices
    - security-basics
    # - javascript-best-practices
    # - go-best-practices
    # - java-best-practices
    # - rust-best-practices

  # Disable specific rules from packs
  # disable:
  #   - py/no-print
  #   - sec/no-http-urls

  # Override severity of specific rules
  # severity_overrides:
  #   py/no-print: info
  #   sec/no-hardcoded-secrets: high

  # Custom rules
  custom: []
    # - id: my-org/no-debug-flags
    #   pattern: "DEBUG\\s*=\\s*True"
    #   file_pattern: "*.py"
    #   severity: high
    #   category: best-practice
    #   message: "Remove debug flags before merging."
    #
    # - id: my-org/require-changelog
    #   llm_check: "If any public API function signature changed, flag if CHANGELOG.md wasn't updated."
    #   file_pattern: "*.py"
    #   severity: medium
    #   category: maintainability
    #
    # - id: my-org/protected-branch-checks
    #   pattern: "FIXME|HACK|XXX"
    #   file_pattern: "*.py"
    #   severity: high
    #   category: maintainability
    #   message: "Resolve all FIXME/HACK comments before merging to main."
    #   branches: [main, master, release/*]

# ── Git Hooks ─────────────────────────────────────────────────────
hooks:
  # pre-commit: runs on staged files before commit
  pre_commit:
    enabled: false
    review: true
    security: true
    fail_on: high            # Block commit if findings >= this severity
    # rules override for hooks (uses main rules section if not set)

  # pre-push: runs on commits being pushed (vs remote branch)
  pre_push:
    enabled: false
    review: true
    security: true
    fail_on: high            # Block push if findings >= this severity
    include_patterns:
      - "**/*.py"
      - "**/*.js"
      - "**/*.ts"
    max_files: 20            # Skip if > N files changed (avoid slow pushes)
    timeout: 120             # Max seconds for the hook to run
"""
