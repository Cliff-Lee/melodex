from __future__ import annotations

import argparse
import json
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

from melodex.provider_manager import ProviderManager


# Real network checks; intentionally not part of deterministic PR CI.
CASES = {
    "org.melodex.internetarchive.audio": "Grateful Dead",
    "org.melodex.librivox": "Odyssey",
    "org.melodex.nichedb.radio": "jazz",
    "org.melodex.radiobrowser": "jazz",
    "org.melodex.somafm": "Groove Salad",
    "org.melodex.wikimedia.commons.audio": "Beethoven",
    "org.melodex.ccmixter": "ambient",
}


def _compact_url(value: str) -> str:
    parsed = urlsplit(value)
    if not parsed.scheme or not parsed.netloc:
        return value[:180]
    path = parsed.path or "/"
    if len(path) > 120:
        path = path[:117] + "..."
    return f"{parsed.scheme}://{parsed.netloc}{path}"


def _probe(resource: dict, *, timeout: float = 20.0) -> dict:
    url = str(resource.get("stream_url") or resource.get("url") or "").strip()
    if not url:
        raise RuntimeError("resolved resource has no URL")

    headers = {
        str(k): str(v)
        for k, v in dict(resource.get("headers") or {}).items()
        if str(k).strip()
    }
    headers.setdefault(
        "User-Agent",
        "Melodex-LiveProvider-Smoke/0.1 (https://github.com/Cliff-Lee/melodex)",
    )
    headers.setdefault("Range", "bytes=0-4095")

    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            body = response.read(4096)
            status = int(getattr(response, "status", 200) or 200)
            content_type = str(response.headers.get("Content-Type") or "")
            final_url = str(response.geturl() or url)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"media probe HTTP {exc.code}") from exc
    except Exception as exc:
        raise RuntimeError(f"media probe failed: {exc}") from exc

    if status not in {200, 206}:
        raise RuntimeError(f"media probe returned HTTP {status}")
    if not body:
        raise RuntimeError("media probe returned no bytes")

    lowered = content_type.casefold()
    if "text/html" in lowered:
        sample = body[:120].decode("utf-8", errors="replace").replace("\n", " ")
        raise RuntimeError(f"media URL returned HTML: {sample!r}")

    return {
        "http_status": status,
        "content_type": content_type,
        "bytes_read": len(body),
        "final_url": _compact_url(final_url),
    }


def _verify_provider(manager: ProviderManager, provider_id: str, query: str) -> dict:
    provider = manager.providers.get(provider_id)
    if provider is None:
        raise RuntimeError("provider was not installed from bundled payload")

    health = manager.test_plugin_health(provider_id, timeout=15.0)
    rows = provider.search(query, limit=8)
    if not rows:
        raise RuntimeError(f"search returned no results for {query!r}")

    attempts = []
    for track in rows[:5]:
        label = f"{track.get('artist') or ''} — {track.get('title') or ''}".strip(" —")
        try:
            resolved = provider.resolve(track)
            probe = _probe(resolved)
            return {
                "provider_id": provider_id,
                "provider_name": provider.info.name,
                "provider_version": provider.info.version,
                "query": query,
                "health": health,
                "search_results": len(rows),
                "selected": {
                    "title": str(track.get("title") or ""),
                    "artist": str(track.get("artist") or ""),
                    "track_id": str(
                        track.get("provider_track_id")
                        or track.get("track_id")
                        or ""
                    ),
                },
                "resolved_kind": str(resolved.get("kind") or ""),
                "resolved_url": _compact_url(
                    str(resolved.get("stream_url") or resolved.get("url") or "")
                ),
                "probe": probe,
                "status": "pass",
            }
        except Exception as exc:
            attempts.append({"track": label, "error": str(exc)})

    raise RuntimeError(
        "search worked but no candidate passed resolve + media probe: "
        + "; ".join(f"{x['track']}: {x['error']}" for x in attempts)
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Live smoke test the provider packages bundled with Melodex."
    )
    parser.add_argument("--json", type=Path, help="Optional output report path.")
    parser.add_argument(
        "--provider",
        choices=sorted(CASES),
        help="Verify only one bundled provider. Useful for CI matrix jobs.",
    )
    args = parser.parse_args()

    selected_cases = (
        {args.provider: CASES[args.provider]}
        if args.provider
        else CASES
    )
    results = []
    failures = []

    with tempfile.TemporaryDirectory(prefix="melodex-live-provider-") as tmp:
        manager = ProviderManager(Path(tmp))
        try:
            for provider_id, query in selected_cases.items():
                try:
                    result = _verify_provider(manager, provider_id, query)
                    results.append(result)
                    probe = result["probe"]
                    print(
                        "PASS "
                        f"{result['provider_name']} {result['provider_version']} | "
                        f"search={result['search_results']} | "
                        f"{probe['http_status']} {probe['content_type']} "
                        f"{probe['bytes_read']} bytes"
                    )
                except Exception as exc:
                    failure = {
                        "provider_id": provider_id,
                        "query": query,
                        "status": "fail",
                        "error": str(exc),
                    }
                    failures.append(failure)
                    results.append(failure)
                    print(f"FAIL {provider_id} | {exc}")
        finally:
            manager.close()

    report = {
        "schema_version": 1,
        "purpose": "live bundled-provider search/resolve/playback reachability",
        "providers_expected": len(selected_cases),
        "providers_passed": sum(1 for row in results if row.get("status") == "pass"),
        "providers_failed": len(failures),
        "results": results,
    }

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n",
            "utf-8",
        )

    print(
        f"SUMMARY {report['providers_passed']}/{report['providers_expected']} "
        "bundled providers live-verified"
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
