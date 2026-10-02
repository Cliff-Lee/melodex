#!/usr/bin/env python3
"""Produce a reproducible size breakdown for a built Melodex application bundle."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Iterable


def _human_size(value: int) -> str:
    size = float(max(0, int(value)))
    units = ("B", "KB", "MB", "GB", "TB")
    for unit in units:
        if size < 1024.0 or unit == units[-1]:
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024.0
    return f"{size:.1f} TB"


def _bundle_files(root: Path) -> Iterable[tuple[Path, int]]:
    for path in root.rglob("*"):
        if path.is_symlink() or not path.is_file():
            continue
        try:
            size = int(path.stat().st_size)
        except OSError:
            continue
        yield path, size


def build_report(
    root: Path,
    *,
    archive: Path | None = None,
    largest_count: int = 30,
) -> dict:
    root = Path(root).resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"bundle directory not found: {root}")

    total = 0
    count = 0
    largest: list[tuple[int, str]] = []
    depth2: dict[str, int] = defaultdict(int)
    depth3: dict[str, int] = defaultdict(int)
    extensions: dict[str, int] = defaultdict(int)

    for path, size in _bundle_files(root):
        relative = path.relative_to(root)
        parts = relative.parts
        total += size
        count += 1
        if parts:
            depth2["/".join(parts[: min(2, len(parts))])] += size
            depth3["/".join(parts[: min(3, len(parts))])] += size
        suffix = path.suffix.lower() or "<none>"
        extensions[suffix] += size
        largest.append((size, relative.as_posix()))

    largest.sort(reverse=True)
    archive_info = None
    if archive is not None:
        archive = Path(archive)
        if archive.is_file():
            archive_info = {
                "path": archive.name,
                "bytes": int(archive.stat().st_size),
            }

    def ranked(values: dict[str, int], limit: int = 30) -> list[dict]:
        return [
            {"name": name, "bytes": value}
            for name, value in sorted(
                values.items(),
                key=lambda item: (-item[1], item[0]),
            )[:limit]
        ]

    return {
        "schema_version": 1,
        "bundle_name": root.name,
        "total_bytes": total,
        "file_count": count,
        "archive": archive_info,
        "largest_files": [
            {"path": path, "bytes": size}
            for size, path in largest[: max(1, int(largest_count))]
        ],
        "directory_buckets_depth_2": ranked(depth2),
        "directory_buckets_depth_3": ranked(depth3),
        "extension_totals": ranked(extensions),
    }


def markdown_report(report: dict) -> str:
    total = int(report.get("total_bytes") or 0)
    lines = [
        "# Melodex bundle size report",
        "",
        f"- Installed bundle: **{_human_size(total)}** ({total:,} bytes)",
        f"- Files counted: **{int(report.get('file_count') or 0):,}**",
    ]
    archive = report.get("archive")
    if isinstance(archive, dict):
        archive_bytes = int(archive.get("bytes") or 0)
        lines.append(
            f"- Archive: **{_human_size(archive_bytes)}** "
            f"({archive_bytes:,} bytes)"
        )

    lines.extend(["", "## Largest bundle areas", "", "| Area | Size |", "| --- | ---: |"])
    for row in list(report.get("directory_buckets_depth_3") or [])[:20]:
        lines.append(
            f"| `{row['name']}` | {_human_size(int(row['bytes']))} |"
        )

    lines.extend(["", "## Largest files", "", "| File | Size |", "| --- | ---: |"])
    for row in list(report.get("largest_files") or [])[:20]:
        lines.append(
            f"| `{row['path']}` | {_human_size(int(row['bytes']))} |"
        )

    lines.extend(["", "## Size by file type", "", "| Extension | Size |", "| --- | ---: |"])
    for row in list(report.get("extension_totals") or [])[:20]:
        lines.append(
            f"| `{row['name']}` | {_human_size(int(row['bytes']))} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--markdown-out", type=Path)
    parser.add_argument("--largest", type=int, default=30)
    args = parser.parse_args()

    report = build_report(
        args.bundle,
        archive=args.archive,
        largest_count=args.largest,
    )
    rendered = markdown_report(report)

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    if args.markdown_out:
        args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_out.write_text(rendered, encoding="utf-8")

    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
