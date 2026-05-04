"""MCP server — exposes codewise capabilities as MCP tools.

Run with: codewise mcp --transport stdio
Or:       codewise mcp --transport sse --port 3000
"""

from __future__ import annotations

import asyncio
import json
import logging

logger = logging.getLogger("codewise.mcp")

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import TextContent, Tool
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False


def create_server() -> Server:
    """Create and configure the MCP server with all codewise tools."""
    if not MCP_AVAILABLE:
        raise ImportError("mcp package not installed. Run: pip install codewise-ai[mcp]")

    server = Server("codewise")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="review_code",
                description="Review code changes or files for bugs, quality, and best practices. Returns structured findings with severity, line numbers, and fix suggestions.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "code": {"type": "string", "description": "Code content or unified diff to review"},
                        "file_path": {"type": "string", "description": "File path for language detection"},
                        "model": {"type": "string", "description": "LLM model to use (default: gpt-4o-mini)"},
                        "extra_instructions": {"type": "string", "description": "Additional review instructions"},
                    },
                    "required": ["code"],
                },
            ),
            Tool(
                name="scan_security",
                description="Scan code for security vulnerabilities with CWE/OWASP classification.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "code": {"type": "string", "description": "Code content to scan"},
                        "file_path": {"type": "string", "description": "File path for context"},
                        "model": {"type": "string", "description": "LLM model to use"},
                    },
                    "required": ["code"],
                },
            ),
            Tool(
                name="generate_tests",
                description="Generate test cases for source code.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "code": {"type": "string", "description": "Source code to generate tests for"},
                        "file_path": {"type": "string", "description": "Source file path"},
                        "framework": {"type": "string", "description": "Test framework (pytest, jest, go, junit)"},
                        "model": {"type": "string", "description": "LLM model to use"},
                    },
                    "required": ["code"],
                },
            ),
            Tool(
                name="generate_docs",
                description="Generate or improve documentation, docstrings, and type hints.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "code": {"type": "string", "description": "Source code to document"},
                        "file_path": {"type": "string", "description": "Source file path"},
                        "model": {"type": "string", "description": "LLM model to use"},
                    },
                    "required": ["code"],
                },
            ),
            Tool(
                name="check_rules",
                description="Run configured regex rules against code (no LLM needed). Returns rule violations.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "code": {"type": "string", "description": "Code content to check"},
                        "file_path": {"type": "string", "description": "File path for rule matching"},
                        "config_path": {"type": "string", "description": "Path to .codewise.yaml"},
                    },
                    "required": ["code"],
                },
            ),
            Tool(
                name="list_rule_packs",
                description="List available standard rule packs and their rules.",
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        try:
            if name == "review_code":
                return await _handle_review(arguments)
            elif name == "scan_security":
                return await _handle_security(arguments)
            elif name == "generate_tests":
                return await _handle_testgen(arguments)
            elif name == "generate_docs":
                return await _handle_docgen(arguments)
            elif name == "check_rules":
                return await _handle_check_rules(arguments)
            elif name == "list_rule_packs":
                return await _handle_list_packs(arguments)
            else:
                return [TextContent(type="text", text=f"Unknown tool: {name}")]
        except Exception as e:
            logger.error("Tool %s failed: %s", name, e)
            return [TextContent(type="text", text=f"Error: {e}")]

    return server


async def _handle_review(args: dict) -> list[TextContent]:
    from codewise.core.diff import parse_diff
    from codewise.core.reviewer import review_changes, review_file
    from codewise.models import CodewiseConfig

    config = CodewiseConfig(
        model=args.get("model", "gpt-4o-mini"),
        extra_instructions=args.get("extra_instructions"),
    )
    code = args["code"]
    file_path = args.get("file_path", "unknown.txt")

    # Try parsing as diff first
    if code.startswith("diff ") or code.startswith("---"):
        changes = parse_diff(code)
        result = await review_changes(changes, config)
    else:
        result = await review_file(file_path, code, config)

    return [TextContent(type="text", text=json.dumps(result.model_dump(mode="json"), indent=2))]


async def _handle_security(args: dict) -> list[TextContent]:
    from codewise.core.security import scan_file
    from codewise.models import CodewiseConfig

    config = CodewiseConfig(model=args.get("model", "gpt-4o-mini"))
    result = await scan_file(
        args.get("file_path", "unknown.txt"),
        args["code"],
        config,
    )
    return [TextContent(type="text", text=json.dumps(result.model_dump(mode="json"), indent=2))]


async def _handle_testgen(args: dict) -> list[TextContent]:
    from codewise.core.testgen import generate_tests
    from codewise.models import CodewiseConfig

    config = CodewiseConfig(
        model=args.get("model", "gpt-4o-mini"),
        test_framework=args.get("framework", "pytest"),
    )
    result = await generate_tests(
        args.get("file_path", "unknown.txt"),
        args["code"],
        config,
    )
    return [TextContent(type="text", text=json.dumps(result.model_dump(mode="json"), indent=2))]


async def _handle_docgen(args: dict) -> list[TextContent]:
    from codewise.core.docgen import generate_docs
    from codewise.models import CodewiseConfig

    config = CodewiseConfig(model=args.get("model", "gpt-4o-mini"))
    result = await generate_docs(
        args.get("file_path", "unknown.txt"),
        args["code"],
        config,
    )
    return [TextContent(type="text", text=json.dumps(result.model_dump(mode="json"), indent=2))]


async def _handle_check_rules(args: dict) -> list[TextContent]:
    from codewise.config import load_config
    from codewise.core.diff import detect_language
    from codewise.models import FileChange
    from codewise.rules import run_regex_rules

    _, rules = load_config(config_path=args.get("config_path"))
    file_path = args.get("file_path", "unknown.txt")
    change = FileChange(
        path=file_path,
        language=detect_language(file_path),
        full_content=args["code"],
        patch=args["code"],
    )
    findings = run_regex_rules([change], rules)
    return [TextContent(
        type="text",
        text=json.dumps([f.model_dump(mode="json") for f in findings], indent=2),
    )]


async def _handle_list_packs(args: dict) -> list[TextContent]:
    from codewise.rules import STANDARD_PACKS
    packs = {}
    for name, rules in STANDARD_PACKS.items():
        packs[name] = [{"id": r["id"], "message": r.get("message", r.get("llm_check", ""))} for r in rules]
    return [TextContent(type="text", text=json.dumps(packs, indent=2))]


def run_server(transport: str = "stdio", port: int = 3000) -> None:
    """Start the MCP server."""
    if not MCP_AVAILABLE:
        raise ImportError("mcp package not installed. Run: pip install codewise-ai[mcp]")

    server = create_server()

    if transport == "stdio":
        async def _run():
            async with stdio_server() as (read_stream, write_stream):
                await server.run(read_stream, write_stream, server.create_initialization_options())
        asyncio.run(_run())
    elif transport == "sse":
        try:
            import uvicorn
            from mcp.server.sse import SseServerTransport
            from starlette.applications import Starlette
            from starlette.routing import Route

            sse = SseServerTransport("/messages")

            async def handle_sse(request):
                async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
                    await server.run(streams[0], streams[1], server.create_initialization_options())

            app = Starlette(routes=[
                Route("/sse", endpoint=handle_sse),
                Route("/messages", endpoint=sse.handle_post_message, methods=["POST"]),
            ])
            uvicorn.run(app, host="0.0.0.0", port=port)
        except ImportError:
            raise ImportError("SSE transport requires: pip install uvicorn starlette")
