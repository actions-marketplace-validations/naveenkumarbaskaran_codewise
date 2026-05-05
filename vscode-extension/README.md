# Codewise — AI Code Review & Security for VS Code

**LLM-agnostic code review, security scanning, test generation, and documentation — right inside VS Code.**

Works with **any LLM provider**: OpenAI, Anthropic, Google Gemini, Ollama, Azure OpenAI, AWS Bedrock.

![Codewise in action](https://raw.githubusercontent.com/naveenkumarbaskaran/codewise/main/assets/demo.gif)

## Features

| Feature | Description |
|---------|-------------|
| **Code Review** | Inline diagnostics for bugs, performance, maintainability |
| **Security Scan** | OWASP/CWE vulnerability detection with severity levels |
| **Test Generation** | Generate tests (pytest, jest, vitest, go, junit) |
| **Doc Generation** | Add docstrings, type hints, inline comments |
| **Review on Save** | Automatic review when you save files |
| **Status Bar** | Live progress indicator and finding counts |

## Requirements

```bash
pip install codewise-ai
```

The extension calls the `codewise` CLI under the hood — make sure it's installed and accessible on your PATH.

## Quick Start

1. Install this extension
2. Install the CLI: `pip install codewise-ai`
3. Set your API key in settings or `CODEWISE_API_KEY` env var
4. Open a file and run **Codewise: Review Current File** (`Cmd+Shift+R` / `Ctrl+Shift+R`)

## Commands

| Command | Keybinding | Description |
|---------|------------|-------------|
| `Codewise: Review Current File` | `Cmd+Shift+R` | Review the active file |
| `Codewise: Review Uncommitted Changes` | — | Review all uncommitted changes |
| `Codewise: Review Staged Changes` | — | Review staged changes (pre-commit) |
| `Codewise: Security Scan` | — | Scan workspace for vulnerabilities |
| `Codewise: Security Scan Current File` | `Cmd+Shift+S` | Scan active file |
| `Codewise: Generate Tests` | — | Generate tests for active file |
| `Codewise: Generate Docs` | — | Add documentation to active file |
| `Codewise: Clear All Findings` | — | Clear all diagnostic markers |

## Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `codewise.model` | `gpt-4o-mini` | LLM model to use |
| `codewise.apiKey` | — | API key for the LLM provider |
| `codewise.pythonPath` | — | Custom Python path for codewise |
| `codewise.failOn` | `none` | Min severity to mark as errors |
| `codewise.reviewOnSave` | `false` | Auto-review on save |
| `codewise.testFramework` | `pytest` | Framework for test generation |
| `codewise.extraArgs` | — | Extra CLI arguments |

## How It Works

The extension calls `codewise` CLI with `--format json` and maps the structured output to VS Code diagnostics (the squiggly underlines in your editor). Findings appear in the **Problems** panel with severity, category, and suggested fixes.

```
codewise review src/handler.py --format json --model gpt-4o-mini
  → JSON findings → VS Code Diagnostics (inline markers)
```

## Supported LLM Providers

Any provider supported by [litellm](https://docs.litellm.ai/docs/providers):

- **OpenAI** — `gpt-4o`, `gpt-4o-mini`
- **Anthropic** — `claude-sonnet-4-20250514`, `claude-3-haiku`
- **Google Gemini** — `gemini/gemini-2.0-flash`
- **Ollama** (local) — `ollama/llama3`, `ollama/codellama`
- **Azure OpenAI** — `azure/gpt-4o`
- **AWS Bedrock** — `bedrock/anthropic.claude-3`
- And many more…

## Links

- [GitHub Repository](https://github.com/naveenkumarbaskaran/codewise)
- [PyPI Package](https://pypi.org/project/codewise-ai/)
- [CLI Documentation](https://github.com/naveenkumarbaskaran/codewise#readme)
- [Report Issues](https://github.com/naveenkumarbaskaran/codewise/issues)

## License

MIT
