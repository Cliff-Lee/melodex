from __future__ import annotations

import re
import sys
from pathlib import Path


GLIBC_VERSION = re.compile(rb"GLIBC_(\d+(?:\.\d+)+)")
MAXIMUM_SUPPORTED = (2, 35)
CHUNK_SIZE = 1024 * 1024


def elf_glibc_versions(path: Path):
    carry = b""
    with path.open("rb") as stream:
        if stream.read(4) != b"\x7fELF":
            return
        stream.seek(0)
        while chunk := stream.read(CHUNK_SIZE):
            data = carry + chunk
            for match in GLIBC_VERSION.finditer(data):
                yield tuple(int(part) for part in match.group(1).split(b"."))
            carry = data[-32:]


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: check_glibc_abi.py /path/to/frozen-app")
    root = Path(sys.argv[1])
    if not root.is_dir():
        raise SystemExit(f"frozen application directory not found: {root}")

    highest: tuple[int, ...] | None = None
    highest_file: Path | None = None
    elf_count = 0
    for path in root.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        versions = list(elf_glibc_versions(path))
        if not versions:
            continue
        elf_count += 1
        local_highest = max(versions)
        if highest is None or local_highest > highest:
            highest = local_highest
            highest_file = path

    if highest is None:
        raise SystemExit(f"no ELF files with GLIBC symbol versions found in {root}")
    if highest > MAXIMUM_SUPPORTED:
        rendered = ".".join(str(part) for part in highest)
        raise SystemExit(
            f"AppImage requires GLIBC_{rendered} in {highest_file}; "
            "the published baseline is GLIBC_2.35 or older"
        )

    rendered = ".".join(str(part) for part in highest)
    print(f"GLIBC compatibility check passed: {elf_count} ELF files, maximum GLIBC_{rendered}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
