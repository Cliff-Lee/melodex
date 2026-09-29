from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

from . import __version__ as MELODEX_VERSION
from .journey_recipe import validate_journey_recipe
from .plugin_registry import version_tuple


DEFAULT_JOURNEY_REGISTRY_URL = (
    "https://raw.githubusercontent.com/Cliff-Lee/melodex/main/"
    "journey-recipes/registry.json"
)
CACHE_MAX_AGE_SECONDS = 6 * 60 * 60

BUNDLED_REGISTRY: dict[str, Any] = {
    "schema_version": 1,
    "recipes": [
        {
            "id": "org.melodex.recipe.deep-work-arc",
            "name": "Deep Work Arc",
            "version": "1.0.0",
            "author": "Melodex Project",
            "description": "Settle in, find a groove, stay familiar, then finish with more energy.",
            "tags": ["focus", "work", "calm", "rhythmic", "energy"],
            "license": "CC0-1.0",
            "status": "example",
            "compatibility": {"melodex_min": "0.3.1.dev0", "journey_schema": 1},
            "source": {"repository": "https://github.com/Cliff-Lee/melodex"},
            "sha256": "dd4f3048ecb22fe0374388bbb26700a698d6ffe7d5be9d5af8812c2419bdeec0",
            "recipe": {
                "melodex_journey": 1,
                "name": "Deep Work Arc",
                "description": "Settle in, find a groove, stay familiar, then finish with more energy.",
                "routing_mode": "balanced",
                "stages": [
                    {"type": "constraint", "constraint": "calm", "label": "Calm"},
                    {"type": "constraint", "constraint": "rhythmic", "label": "Rhythmic"},
                    {"type": "constraint", "constraint": "familiar", "label": "Familiar"},
                    {"type": "constraint", "constraint": "energetic", "label": "Energetic"},
                ],
            },
        },
        {
            "id": "org.melodex.recipe.late-night-descent",
            "name": "Late Night Descent",
            "version": "1.0.0",
            "author": "Melodex Project",
            "description": "Begin familiar, move darker, slow the energy, then rediscover something half-forgotten.",
            "tags": ["night", "dark", "calm", "rediscovery"],
            "license": "CC0-1.0",
            "status": "example",
            "compatibility": {"melodex_min": "0.3.1.dev0", "journey_schema": 1},
            "source": {"repository": "https://github.com/Cliff-Lee/melodex"},
            "sha256": "4794329a6fa3dc5a61c6eadfc646b45f08795ac163b1ed151afaeefc387590a7",
            "recipe": {
                "melodex_journey": 1,
                "name": "Late Night Descent",
                "description": "Begin familiar, move darker, slow the energy, then rediscover something half-forgotten.",
                "routing_mode": "balanced",
                "stages": [
                    {"type": "constraint", "constraint": "familiar", "label": "Familiar"},
                    {"type": "constraint", "constraint": "dark", "label": "Darker"},
                    {"type": "constraint", "constraint": "calm", "label": "Calm"},
                    {"type": "constraint", "constraint": "forgotten", "label": "Forgotten"},
                ],
            },
        },
        {
            "id": "org.melodex.recipe.rediscovery-sunday",
            "name": "Rediscovery Sunday",
            "version": "1.0.0",
            "author": "Melodex Project",
            "description": "A gentle route from known favourites into forgotten music and a brighter finish.",
            "tags": ["weekend", "rediscovery", "familiar", "bright"],
            "license": "CC0-1.0",
            "status": "example",
            "compatibility": {"melodex_min": "0.3.1.dev0", "journey_schema": 1},
            "source": {"repository": "https://github.com/Cliff-Lee/melodex"},
            "sha256": "ffa46d9459feb61ab42b5139e324fb9e2e4e44bc613e5f3bf6027587ac4cb7d4",
            "recipe": {
                "melodex_journey": 1,
                "name": "Rediscovery Sunday",
                "description": "A gentle route from known favourites into forgotten music and a brighter finish.",
                "routing_mode": "balanced",
                "stages": [
                    {"type": "constraint", "constraint": "familiar", "label": "Familiar"},
                    {"type": "constraint", "constraint": "forgotten", "label": "Forgotten"},
                    {"type": "constraint", "constraint": "bright", "label": "Bright"},
                ],
            },
        },
        {
            "id": "org.melodex.recipe.dark-to-bright",
            "name": "Dark to Bright",
            "version": "1.0.0",
            "author": "Melodex Project",
            "description": "Start in a darker region, build rhythm and energy, then emerge somewhere brighter.",
            "tags": ["dark", "rhythmic", "energy", "bright"],
            "license": "CC0-1.0",
            "status": "example",
            "compatibility": {"melodex_min": "0.3.1.dev0", "journey_schema": 1},
            "source": {"repository": "https://github.com/Cliff-Lee/melodex"},
            "sha256": "f087096df0de77116ed3bb10166facf7a7fa9bd419302a516b5aab6993312ebf",
            "recipe": {
                "melodex_journey": 1,
                "name": "Dark to Bright",
                "description": "Start in a darker region, build rhythm and energy, then emerge somewhere brighter.",
                "routing_mode": "balanced",
                "stages": [
                    {"type": "constraint", "constraint": "dark", "label": "Darker"},
                    {"type": "constraint", "constraint": "rhythmic", "label": "Rhythmic"},
                    {"type": "constraint", "constraint": "energetic", "label": "Energetic"},
                    {"type": "constraint", "constraint": "bright", "label": "Bright"},
                ],
            },
        },
        {
            "id": "org.melodex.recipe.discovery-drift",
            "name": "Discovery Drift",
            "version": "1.0.0",
            "author": "Melodex Project",
            "description": "A softer exploratory arc that deliberately makes room for surprise before returning to light.",
            "tags": ["discovery", "surprising", "calm", "bright"],
            "license": "CC0-1.0",
            "status": "example",
            "compatibility": {"melodex_min": "0.3.1.dev0", "journey_schema": 1},
            "source": {"repository": "https://github.com/Cliff-Lee/melodex"},
            "sha256": "d3b3dd7bc0f32100861750d2535edaac5185d145cdf66a200a823656b3ba6bc1",
            "recipe": {
                "melodex_journey": 1,
                "name": "Discovery Drift",
                "description": "A softer exploratory arc that deliberately makes room for surprise before returning to light.",
                "routing_mode": "sonic",
                "stages": [
                    {"type": "constraint", "constraint": "calm", "label": "Calm"},
                    {"type": "constraint", "constraint": "surprising", "label": "Surprising"},
                    {"type": "constraint", "constraint": "dark", "label": "Darker"},
                    {"type": "constraint", "constraint": "bright", "label": "Bright"},
                ],
            },
        },
    ],
}


@dataclass(slots=True)
class JourneyRegistryResult:
    recipes: list[dict[str, Any]]
    source: str
    stale: bool = False
    error: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "recipes": [dict(row) for row in self.recipes],
            "source": self.source,
            "stale": self.stale,
            "error": self.error,
        }


def canonical_recipe_bytes(recipe: dict[str, Any]) -> bytes:
    validated = validate_journey_recipe(recipe)
    return json.dumps(
        validated,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def recipe_sha256(recipe: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_recipe_bytes(recipe)).hexdigest()


def validate_journey_registry(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["registry must be a JSON object"]
    if int(data.get("schema_version") or 0) != 1:
        errors.append("schema_version must be 1")
    rows = data.get("recipes")
    if not isinstance(rows, list):
        return errors + ["recipes must be an array"]

    seen: set[str] = set()
    for index, raw in enumerate(rows):
        prefix = f"recipes[{index}]"
        if not isinstance(raw, dict):
            errors.append(f"{prefix} must be an object")
            continue
        recipe_id = str(raw.get("id") or "").strip()
        if not recipe_id:
            errors.append(f"{prefix}.id is required")
        elif recipe_id in seen:
            errors.append(f"{prefix}.id is duplicated: {recipe_id}")
        else:
            seen.add(recipe_id)

        for key in ("name", "version", "author", "description", "license", "status"):
            if not str(raw.get(key) or "").strip():
                errors.append(f"{prefix}.{key} is required")
        if raw.get("status") not in {"example", "community", "reviewed", "deprecated", "blocked"}:
            errors.append(f"{prefix}.status is invalid")
        if not isinstance(raw.get("tags"), list):
            errors.append(f"{prefix}.tags must be an array")

        compatibility = raw.get("compatibility")
        if not isinstance(compatibility, dict):
            errors.append(f"{prefix}.compatibility is required")
        elif int(compatibility.get("journey_schema") or 0) != 1:
            errors.append(f"{prefix}.compatibility.journey_schema must be 1")

        source = raw.get("source")
        if not isinstance(source, dict):
            errors.append(f"{prefix}.source is required")
        else:
            repository = str(source.get("repository") or "")
            if not repository or urlparse(repository).scheme != "https":
                errors.append(f"{prefix}.source.repository must use HTTPS")

        recipe = raw.get("recipe")
        if not isinstance(recipe, dict):
            errors.append(f"{prefix}.recipe is required")
            continue
        try:
            validate_journey_recipe(recipe)
        except Exception as exc:
            errors.append(f"{prefix}.recipe is invalid: {exc}")
            continue
        expected = str(raw.get("sha256") or "").strip().lower()
        actual = recipe_sha256(recipe)
        if expected != actual:
            errors.append(f"{prefix}.sha256 does not match canonical recipe bytes")
    return errors


class JourneyRegistryClient:
    def __init__(
        self,
        data_dir: Path,
        registry_url: str | None = None,
        session: requests.Session | None = None,
        timeout: float = 12.0,
    ):
        self.data_dir = Path(data_dir)
        self.cache_dir = self.data_dir / "journey-registry"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_path = self.cache_dir / "registry-cache.json"
        self.registry_url = str(
            registry_url
            or os.environ.get("MELODEX_JOURNEY_REGISTRY_URL")
            or DEFAULT_JOURNEY_REGISTRY_URL
        ).strip()
        self.session = session or requests.Session()
        self.timeout = float(timeout)
        self.user_agent = "Melodex-Journey-Gallery/1"

    def _read_cache(self) -> dict[str, Any] | None:
        try:
            value = json.loads(self.cache_path.read_text("utf-8"))
            return value if not validate_journey_registry(value) else None
        except Exception:
            return None

    def _write_cache(self, data: dict[str, Any]) -> None:
        temp = self.cache_path.with_suffix(".tmp")
        temp.write_text(json.dumps(data, indent=2, ensure_ascii=False), "utf-8")
        temp.replace(self.cache_path)

    def fetch(self, force: bool = False) -> JourneyRegistryResult:
        cached = self._read_cache()
        fresh = False
        if cached is not None:
            try:
                fresh = time.time() - self.cache_path.stat().st_mtime <= CACHE_MAX_AGE_SECONDS
            except OSError:
                fresh = False
        if cached is not None and fresh and not force:
            return JourneyRegistryResult(list(cached.get("recipes") or []), "cache")

        try:
            response = self.session.get(
                self.registry_url,
                headers={"User-Agent": self.user_agent, "Accept": "application/json"},
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
            errors = validate_journey_registry(data)
            if errors:
                raise RuntimeError("Journey registry validation failed: " + "; ".join(errors))
            self._write_cache(data)
            return JourneyRegistryResult(list(data.get("recipes") or []), self.registry_url)
        except Exception as exc:
            if cached is not None:
                return JourneyRegistryResult(
                    list(cached.get("recipes") or []),
                    "cache",
                    stale=True,
                    error=str(exc),
                )
            bundled = json.loads(json.dumps(BUNDLED_REGISTRY))
            return JourneyRegistryResult(
                list(bundled.get("recipes") or []),
                "bundled",
                stale=True,
                error=str(exc),
            )

    @staticmethod
    def compatible(entry: dict[str, Any]) -> tuple[bool, str]:
        compatibility = dict(entry.get("compatibility") or {})
        minimum = str(compatibility.get("melodex_min") or "").strip()
        if minimum and version_tuple(MELODEX_VERSION) < version_tuple(minimum):
            return False, f"Requires Melodex {minimum} or newer; this build is {MELODEX_VERSION}."
        if int(compatibility.get("journey_schema") or 0) != 1:
            return False, "This recipe uses an unsupported journey schema."
        return True, ""

    @staticmethod
    def filter_recipes(
        recipes: list[dict[str, Any]],
        query: str = "",
        tag: str = "all",
    ) -> list[dict[str, Any]]:
        q = str(query or "").strip().casefold()
        tag = str(tag or "all").strip().casefold()
        out: list[dict[str, Any]] = []
        for raw in recipes:
            row = dict(raw)
            if str(row.get("status") or "") == "blocked":
                continue
            tags = [str(x).casefold() for x in list(row.get("tags") or []) if str(x)]
            if tag != "all" and tag not in tags:
                continue
            haystack = " ".join(
                [
                    str(row.get("name") or ""),
                    str(row.get("author") or ""),
                    str(row.get("description") or ""),
                    " ".join(tags),
                ]
            ).casefold()
            if q and q not in haystack:
                continue
            out.append(row)
        out.sort(
            key=lambda row: (
                {"reviewed": 0, "example": 1, "community": 2, "deprecated": 3}.get(
                    str(row.get("status") or ""), 9
                ),
                str(row.get("name") or "").casefold(),
            )
        )
        return out

    @staticmethod
    def recipe_for_entry(entry: dict[str, Any]) -> dict[str, Any]:
        row = dict(entry or {})
        if str(row.get("status") or "") == "blocked":
            raise RuntimeError("This Journey Recipe is blocked")
        recipe = dict(row.get("recipe") or {})
        validated = validate_journey_recipe(recipe)
        expected = str(row.get("sha256") or "").strip().lower()
        actual = recipe_sha256(validated)
        if expected != actual:
            raise RuntimeError("Journey Recipe SHA-256 mismatch")
        compatible, reason = JourneyRegistryClient.compatible(row)
        if not compatible:
            raise RuntimeError(reason)
        return validated


__all__ = [
    "DEFAULT_JOURNEY_REGISTRY_URL",
    "BUNDLED_REGISTRY",
    "JourneyRegistryResult",
    "JourneyRegistryClient",
    "canonical_recipe_bytes",
    "recipe_sha256",
    "validate_journey_registry",
]
