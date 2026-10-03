#!/usr/bin/env python3
"""Emit repeatable structural metrics for Campaign 12."""
from __future__ import annotations

import ast
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROOTS = (
    "desktop/melodex",
    "desktop/tests",
    "provider-sdk/src",
    "provider-sdk/tests",
    "official-providers",
    "scripts",
)


def files() -> list[Path]:
    found: set[Path] = set()
    for name in ROOTS:
        base = ROOT / name
        if base.exists():
            found.update(p for p in base.rglob("*.py") if p.is_file())
    return sorted(found)


def module_name(path: Path) -> str | None:
    try:
        rel = path.relative_to(ROOT / "desktop")
    except ValueError:
        return None
    if not rel.parts or rel.parts[0] != "melodex":
        return None
    parts = list(rel.with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def internal_imports(tree: ast.AST, current: str | None, is_init: bool) -> set[str]:
    out: set[str] = set()
    package = current if is_init else (current.rpartition(".")[0] if current else "")
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out.update(a.name for a in node.names if a.name == "melodex" or a.name.startswith("melodex."))
        elif isinstance(node, ast.ImportFrom):
            if node.level and package:
                parts = package.split(".")
                if node.level > 1:
                    parts = parts[: -(node.level - 1)]
                if node.module:
                    parts += node.module.split(".")
                if parts and parts[0] == "melodex":
                    out.add(".".join(parts))
            elif node.module and (node.module == "melodex" or node.module.startswith("melodex.")):
                out.add(node.module)
    return out


def resolve(name: str, known: set[str]) -> str | None:
    while name:
        if name in known:
            return name
        if "." not in name:
            return None
        name = name.rsplit(".", 1)[0]
    return None


def cycles(graph: dict[str, set[str]]) -> list[list[str]]:
    index = 0
    stack: list[str] = []
    on_stack: set[str] = set()
    indices: dict[str, int] = {}
    low: dict[str, int] = {}
    result: list[list[str]] = []

    def visit(v: str) -> None:
        nonlocal index
        indices[v] = low[v] = index
        index += 1
        stack.append(v)
        on_stack.add(v)
        for w in graph[v]:
            if w not in indices:
                visit(w)
                low[v] = min(low[v], low[w])
            elif w in on_stack:
                low[v] = min(low[v], indices[w])
        if low[v] == indices[v]:
            group: list[str] = []
            while True:
                w = stack.pop()
                on_stack.remove(w)
                group.append(w)
                if w == v:
                    break
            if len(group) > 1:
                result.append(sorted(group))

    for v in sorted(graph):
        if v not in indices:
            visit(v)
    return sorted(result, key=lambda group: (-len(group), group))


def main() -> int:
    paths = files()
    modules = {p: module_name(p) for p in paths}
    known = {m for m in modules.values() if m}
    graph = {m: set() for m in known}
    rows = []
    longest = []
    syntax_errors = []

    for path in paths:
        rel = path.relative_to(ROOT).as_posix()
        source = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source, filename=rel)
        except SyntaxError as exc:
            syntax_errors.append({"path": rel, "error": str(exc)})
            continue

        funcs = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        handlers = [n for n in ast.walk(tree) if isinstance(n, ast.ExceptHandler)]
        broad = sum(isinstance(h.type, ast.Name) and h.type.id in {"Exception", "BaseException"} for h in handlers)
        bare = sum(h.type is None for h in handlers)
        current = modules[path]
        resolved = {r for name in internal_imports(tree, current, path.name == "__init__.py") if (r := resolve(name, known))}
        if current:
            graph[current].update(r for r in resolved if r != current)

        for fn in funcs:
            if fn.end_lineno is not None:
                longest.append({"path": rel, "name": fn.name, "line": fn.lineno, "lines": fn.end_lineno - fn.lineno + 1})

        rows.append({
            "path": rel,
            "lines": max(1, len(source.splitlines())),
            "classes": sum(isinstance(n, ast.ClassDef) for n in ast.walk(tree)),
            "functions": len(funcs),
            "broad_exception_handlers": broad,
            "bare_exception_handlers": bare,
            "internal_imports": len(resolved),
        })

    fan_in: Counter[str] = Counter()
    for targets in graph.values():
        fan_in.update(targets)
    hubs = [
        {"module": m, "fan_in": fan_in[m], "fan_out": len(graph[m]), "total": fan_in[m] + len(graph[m])}
        for m in graph
    ]
    hubs.sort(key=lambda x: (x["total"], x["fan_in"], x["fan_out"]), reverse=True)
    desktop = [r for r in rows if r["path"].startswith("desktop/melodex/")]
    tests = [r for r in rows if "/tests/" in r["path"] or r["path"].startswith("desktop/tests/")]

    report = {
        "schema_version": 1,
        "roots": list(ROOTS),
        "summary": {
            "python_files": len(rows),
            "python_lines": sum(r["lines"] for r in rows),
            "desktop_package_files": len(desktop),
            "desktop_package_lines": sum(r["lines"] for r in desktop),
            "test_files": len(tests),
            "broad_exception_handlers": sum(r["broad_exception_handlers"] for r in rows),
            "bare_exception_handlers": sum(r["bare_exception_handlers"] for r in rows),
            "syntax_errors": len(syntax_errors),
        },
        "largest_files": sorted(rows, key=lambda r: r["lines"], reverse=True)[:25],
        "longest_functions": sorted(longest, key=lambda r: r["lines"], reverse=True)[:30],
        "desktop_dependency_hubs": hubs[:25],
        "desktop_dependency_cycles": cycles(graph),
        "syntax_errors": syntax_errors,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if syntax_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
