# Changelog

## [2.0.0] - 2025-05-07

### Breaking Changes
- Minimum `litellm` version raised to 1.50 for improved model support
- Development status upgraded to Production/Stable

### Added
- `tenacity` dependency for robust retry logic on LLM calls
- `mypy` added to dev dependencies for full type checking
- `Typing :: Typed` classifier — package now ships `py.typed`
- New keywords: `code-quality`, `developer-tools`

### Improved
- Bumped `rich` minimum to 13.7 for better terminal rendering
- Bumped `pydantic` minimum to 2.5 for performance improvements
- Bumped `pytest-asyncio` minimum to 0.24
- Bumped `ruff` minimum to 0.5

### Fixed
- Improved error handling in CLI diff resolution
- Better model name matching in LLM provider selection

---

## [1.0.0] - 2025-03-15

### Added
- Stable release with full CLI, MCP, GitHub Action, and pre-commit hook support
- Security scanning with configurable severity thresholds
- Test generation and documentation generation commands
- SARIF output format for GitHub Security tab integration

### Improved
- Reduced LLM token usage by ~30% through smarter diff chunking
- Parallel file processing for large changesets

---

## [0.1.0] - 2025-01-20

### Added
- Initial release
- Code review, security scan, testgen, docgen commands
- MCP server mode
- GitHub Action and pre-commit hook integration
- Multi-provider LLM support via litellm
