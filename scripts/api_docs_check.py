from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "desktop"
sys.path.insert(0, str(DESKTOP))

from melodex.api_schema import openapi_document
from melodex.openai_tools import CHAT_COMPLETIONS_TOOLS


def mcp_tool_names() -> set[str]:
    source = (DESKTOP / "melodex/mcp_server.py").read_text("utf-8")
    tree = ast.parse(source)
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue
            func = decorator.func
            if not (
                isinstance(func, ast.Attribute)
                and func.attr == "tool"
                and isinstance(func.value, ast.Name)
                and func.value.id == "mcp"
            ):
                continue
            for keyword in decorator.keywords:
                if keyword.arg == "name" and isinstance(keyword.value, ast.Constant):
                    if isinstance(keyword.value.value, str):
                        names.add(keyword.value.value)
    return names


def main() -> int:
    errors: list[str] = []

    rest_doc = (ROOT / "docs/api/LOCAL_REST_API.md").read_text("utf-8")
    for path in sorted(openapi_document()["paths"]):
        if path not in rest_doc:
            errors.append(f"LOCAL_REST_API.md does not mention OpenAPI path {path}")

    openai_doc = (ROOT / "docs/api/OPENAI_FUNCTION_CALLING.md").read_text("utf-8")
    openai_names = {
        str(item["function"]["name"])
        for item in CHAT_COMPLETIONS_TOOLS
    }
    for name in sorted(openai_names):
        if name not in openai_doc:
            errors.append(
                f"OPENAI_FUNCTION_CALLING.md does not mention OpenAI tool {name}"
            )

    mcp_doc = (ROOT / "docs/MCP_CONTROL.md").read_text("utf-8")
    names = mcp_tool_names()
    if not names:
        errors.append("no MCP @mcp.tool decorators found")
    for name in sorted(names):
        if name not in mcp_doc:
            errors.append(f"MCP_CONTROL.md does not mention MCP tool {name}")

    if errors:
        print("API documentation consistency check failed:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print(
        "API documentation consistency check passed: "
        f"{len(openapi_document()['paths'])} REST paths, "
        f"{len(openai_names)} OpenAI tools, {len(names)} MCP tools"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
