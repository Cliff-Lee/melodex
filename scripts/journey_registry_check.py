from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "desktop"))

from melodex.journey_registry import (  # noqa: E402
    BUNDLED_REGISTRY,
    validate_journey_registry,
)


def main() -> int:
    path = ROOT / "journey-recipes" / "registry.json"
    errors: list[str] = []
    try:
        public = json.loads(path.read_text("utf-8"))
    except Exception as exc:
        print(f"Journey Recipe registry check failed: {exc}")
        return 1

    errors.extend(validate_journey_registry(public))
    if public != BUNDLED_REGISTRY:
        errors.append(
            "journey-recipes/registry.json no longer matches the bundled offline registry"
        )

    if errors:
        print("Journey Recipe registry check failed:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print(
        "Journey Recipe registry check passed "
        f"({len(public.get('recipes') or [])} recipes)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
