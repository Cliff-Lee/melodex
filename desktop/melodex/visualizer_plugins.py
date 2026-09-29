"""Validated, non-executable `.mdxviz` visualizer recipes."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
import re
from typing import Any, Mapping


MAX_PLUGIN_BYTES = 64 * 1024
MAX_LAYERS = 32
MAX_LAYER_MARKS = 128
MAX_SCENE_POINTS = 4096
MAX_INSTALLED_VISUALIZERS = 64
PLUGIN_API_VERSION = 1
SUPPORTED_SHAPES = frozenset({"contour", "orbit", "terrain", "rings", "glyphs"})
SUPPORTED_FEATURES = frozenset({"energy", "brightness", "rhythm", "progress", "tempo"})
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{1,63}$")
_ROOT_KEYS = {"format", "api_version", "manifest", "scene"}
_MANIFEST_KEYS = {"id", "name", "author", "description"}
_SCENE_KEYS = {"layers"}
_LAYER_KEYS = {"type", "count", "gain", "feature", "palette", "speed"}


@dataclass(frozen=True, slots=True)
class VisualizerRecipe:
    id: str
    name: str
    author: str
    description: str
    layers: tuple[dict[str, Any], ...]


def _bounded_text(value: Any, name: str, *, required: bool, limit: int = 128) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be text")
    result = value.strip()
    if required and not result:
        raise ValueError(f"{name} is required")
    if len(result) > limit:
        raise ValueError(f"{name} is longer than {limit} characters")
    return result


def _number(value: Any, name: str, low: float, high: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number")
    result = float(value)
    if not math.isfinite(result) or result < low or result > high:
        raise ValueError(f"{name} must be between {low:g} and {high:g}")
    return result


def parse_visualizer(raw: bytes | str) -> VisualizerRecipe:
    """Parse the strict v1 JSON recipe format; unknown keys are refused."""

    if isinstance(raw, bytes):
        if len(raw) > MAX_PLUGIN_BYTES:
            raise ValueError("Visualizer files must be 64 KiB or smaller")
        try:
            source = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("Visualizer files must be UTF-8 JSON") from exc
    elif isinstance(raw, str):
        if len(raw.encode("utf-8")) > MAX_PLUGIN_BYTES:
            raise ValueError("Visualizer files must be 64 KiB or smaller")
        source = raw
    else:
        raise ValueError("Visualizer content must be UTF-8 JSON")

    try:
        payload = json.loads(source)
    except (json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("Visualizer file is not valid JSON") from exc
    if not isinstance(payload, dict) or set(payload) != _ROOT_KEYS:
        raise ValueError("A visualizer needs exactly format, api_version, manifest and scene fields")
    if payload.get("format") != "mdxviz":
        raise ValueError("Visualizer format must be 'mdxviz'")
    api_version = payload.get("api_version")
    if isinstance(api_version, bool) or not isinstance(api_version, int) or api_version != PLUGIN_API_VERSION:
        raise ValueError(f"Unsupported .mdxviz API version: {payload.get('api_version')!r}")

    manifest = payload.get("manifest")
    scene = payload.get("scene")
    if not isinstance(manifest, dict) or set(manifest) != _MANIFEST_KEYS:
        raise ValueError("Visualizer manifest fields are invalid")
    if not isinstance(scene, dict) or set(scene) != _SCENE_KEYS:
        raise ValueError("Visualizer scene fields are invalid")

    plugin_id = _bounded_text(manifest.get("id"), "manifest.id", required=True, limit=64)
    if not _ID_RE.fullmatch(plugin_id):
        raise ValueError("manifest.id must use lowercase letters, digits, dots, underscores or hyphens")
    name = _bounded_text(manifest.get("name"), "manifest.name", required=True)
    author = _bounded_text(manifest.get("author"), "manifest.author", required=False)
    description = _bounded_text(manifest.get("description"), "manifest.description", required=False, limit=512)

    layers = scene.get("layers")
    if not isinstance(layers, list) or not layers or len(layers) > MAX_LAYERS:
        raise ValueError(f"scene.layers must contain between 1 and {MAX_LAYERS} items")
    normalized: list[dict[str, Any]] = []
    layer_marks = 0
    scene_points = 0
    for index, layer in enumerate(layers):
        label = f"scene.layers[{index}]"
        if not isinstance(layer, dict) or not set(layer).issubset(_LAYER_KEYS):
            raise ValueError(f"{label} has unsupported fields")
        shape = layer.get("type")
        if not isinstance(shape, str) or shape not in SUPPORTED_SHAPES:
            raise ValueError(f"{label}.type must be one of {', '.join(sorted(SUPPORTED_SHAPES))}")
        feature = layer.get("feature", "energy")
        if not isinstance(feature, str) or feature not in SUPPORTED_FEATURES:
            raise ValueError(f"{label}.feature is not supported")
        count_max = 24 if shape in {"orbit", "glyphs"} else 12 if shape == "rings" else 8 if shape == "terrain" else 4
        count = layer.get("count", 1)
        if isinstance(count, bool) or not isinstance(count, int) or count < 1 or count > count_max:
            raise ValueError(f"{label}.count must be from 1 to {count_max}")
        layer_marks += count
        scene_points += count * (48 if shape in {"contour", "terrain"} else 8)
        if layer_marks > MAX_LAYER_MARKS or scene_points > MAX_SCENE_POINTS:
            raise ValueError(
                f"{label} exceeds the scene budget ({MAX_LAYER_MARKS} marks / {MAX_SCENE_POINTS} points)"
            )
        gain = _number(layer.get("gain", 0.20), f"{label}.gain", 0.0, 0.50)
        palette = layer.get("palette", 0)
        if isinstance(palette, bool) or not isinstance(palette, int) or palette < 0 or palette > 5:
            raise ValueError(f"{label}.palette must be an integer from 0 to 5")
        speed = _number(layer.get("speed", 0.08), f"{label}.speed", 0.0, 0.25)
        normalized.append({
            "type": shape,
            "count": count,
            "gain": gain,
            "feature": feature,
            "palette": palette,
            "speed": speed,
        })

    return VisualizerRecipe(plugin_id, name, author, description, tuple(normalized))


def load_visualizer(path: Path) -> VisualizerRecipe:
    path = Path(path)
    if path.suffix.lower() != ".mdxviz":
        raise ValueError("Choose a .mdxviz visualizer file")
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ValueError(f"Could not read visualizer file: {exc}") from exc
    return parse_visualizer(raw)


def install_visualizer_file(source: Path, directory: Path, *, overwrite: bool = False) -> tuple[VisualizerRecipe, Path]:
    """Copy a validated JSON recipe into Melodex's visualizer directory."""

    source = Path(source)
    recipe = load_visualizer(source)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{recipe.id}.mdxviz"
    if target.exists() and not overwrite:
        raise FileExistsError(f"A visualizer named {recipe.name!r} is already installed")
    raw = source.read_bytes()
    # The identifier is restricted above, and a same-directory temporary keeps
    # interrupted copies from appearing as partially installed plugins.
    temporary = directory / f".{recipe.id}.mdxviz.tmp"
    temporary.write_bytes(raw)
    temporary.replace(target)
    return recipe, target


def installed_visualizers(directory: Path) -> tuple[tuple[VisualizerRecipe, Path], ...]:
    directory = Path(directory)
    if not directory.is_dir():
        return ()
    result: list[tuple[VisualizerRecipe, Path]] = []
    paths = sorted(directory.glob("*.mdxviz"), key=lambda p: p.name.casefold())[:MAX_INSTALLED_VISUALIZERS]
    for path in paths:
        try:
            result.append((load_visualizer(path), path))
        except (OSError, ValueError):
            continue
    return tuple(result)
