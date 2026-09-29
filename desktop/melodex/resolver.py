from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any


_MAJOR_VARIANTS = {"live", "remix", "instrumental", "karaoke", "cover", "acoustic"}
_MINOR_VARIANTS = {"remaster", "remastered", "edit", "radio", "demo", "mono", "stereo"}
_NON_WORD = re.compile(r"[^a-z0-9]+")


def _norm(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).casefold()
    text = text.replace("&", " and ")
    return " ".join(_NON_WORD.sub(" ", text).split())


def _similarity(a: Any, b: Any) -> float:
    left, right = _norm(a), _norm(b)
    if not left or not right:
        return 0.0
    if left == right:
        return 1.0
    seq = SequenceMatcher(None, left, right).ratio()
    lt, rt = set(left.split()), set(right.split())
    overlap = len(lt & rt) / max(1, len(lt | rt))
    containment = min(
        len(lt & rt) / max(1, len(lt)),
        len(lt & rt) / max(1, len(rt)),
    )
    return max(seq, 0.72 * overlap + 0.28 * containment)


def _variant_terms(track: dict[str, Any]) -> set[str]:
    text = _norm(f"{track.get('title', '')} {track.get('album', '')}")
    return set(text.split()) & (_MAJOR_VARIANTS | _MINOR_VARIANTS)


def _fingerprint(track: dict[str, Any]) -> str:
    return "|".join(
        (_norm(track.get("artist")), _norm(track.get("title")), _norm(track.get("album")))
    )


def _candidate_key(track: dict[str, Any]) -> str:
    provider = str(track.get("provider_id") or "").strip()
    track_id = str(track.get("track_id") or track.get("id") or "").strip()
    if provider and track_id:
        return f"{provider}:{track_id}"
    return f"{provider}:{_fingerprint(track)}"


def _playable(track: dict[str, Any]) -> bool:
    return bool(track.get("local_path") or track.get("stream_url") or track.get("url"))


def _provider_supports(provider: Any, capability: str) -> bool:
    """Honor declared capabilities without breaking older/internal providers.

    Providers that expose ProviderInfo.capabilities are authoritative. Minimal
    legacy/internal providers with no capability metadata keep the historical
    behavior and are treated as supporting the operation.
    """
    info = getattr(provider, "info", None)
    if info is None:
        return True
    capabilities = getattr(info, "capabilities", None)
    if capabilities is None:
        return True
    return str(capability) in list(capabilities or [])


def _duration(track: dict[str, Any]) -> float:
    try:
        value = float(track.get("duration") or track.get("duration_seconds") or 0)
        return value if value > 0 else 0.0
    except Exception:
        return 0.0


def _safe_track_snapshot(track: dict[str, Any]) -> dict[str, Any]:
    """Keep only resolver-relevant JSON-like fields for persistent preferences."""
    keys = (
        "provider_id", "track_id", "id", "artist", "title", "album", "duration",
        "source", "source_page", "artwork", "license_url", "attribution",
    )
    return {key: track.get(key) for key in keys if track.get(key) not in (None, "")}


@dataclass(slots=True)
class ResolutionCandidate:
    track: dict[str, Any]
    score: float
    provider_id: str
    provider_rank: int
    title_score: float
    artist_score: float
    album_score: float
    version_penalty: float
    duration_adjustment: float = 0.0
    duration_delta: float | None = None
    preferred: bool = False

    def reasons(self) -> list[str]:
        reasons: list[str] = []
        if self.preferred:
            reasons.append("preferred match")
        if self.title_score >= 0.985:
            reasons.append("exact title")
        elif self.title_score >= 0.88:
            reasons.append("very close title")
        if self.artist_score >= 0.985:
            reasons.append("exact artist")
        elif self.artist_score >= 0.88:
            reasons.append("very close artist")
        if self.album_score >= 0.985:
            reasons.append("exact album")
        elif self.album_score >= 0.82:
            reasons.append("close album")
        if self.duration_delta is not None:
            if self.duration_delta <= 3:
                reasons.append("duration matches")
            elif self.duration_delta > 30:
                reasons.append(f"duration differs by {int(round(self.duration_delta))}s")
        if self.version_penalty > 0:
            reasons.append("version mismatch penalty")
        if self.provider_rank == 0:
            reasons.append("top-priority source")
        return reasons or ["metadata similarity"]

    def flags(self) -> list[str]:
        return sorted(_variant_terms(self.track))

    def as_dict(self) -> dict[str, Any]:
        return {
            "track": dict(self.track),
            "score": round(self.score, 4),
            "provider_id": self.provider_id,
            "provider_rank": self.provider_rank,
            "title_score": round(self.title_score, 4),
            "artist_score": round(self.artist_score, 4),
            "album_score": round(self.album_score, 4),
            "version_penalty": round(self.version_penalty, 4),
            "duration_adjustment": round(self.duration_adjustment, 4),
            "duration_delta": None if self.duration_delta is None else round(self.duration_delta, 2),
            "preferred": bool(self.preferred),
            "candidate_key": _candidate_key(self.track),
            "flags": self.flags(),
            "reasons": self.reasons(),
        }


class UniversalResolver:
    """Provider-neutral metadata resolver used by playback, APIs and AI playlists."""

    def __init__(self, manager: Any, minimum_score: float = 0.62):
        self.manager = manager
        self.minimum_score = float(minimum_score)

    def provider_order(self) -> list[str]:
        installed = list(self.manager.providers)
        configured = [
            str(x)
            for x in self.manager.settings.get("provider_priority", [])
            if str(x) in self.manager.providers
        ]
        return configured + [pid for pid in installed if pid not in configured]

    def set_provider_order(self, provider_ids: list[str]) -> list[str]:
        seen: set[str] = set()
        order: list[str] = []
        for raw in provider_ids:
            pid = str(raw)
            if pid in self.manager.providers and pid not in seen:
                seen.add(pid)
                order.append(pid)
        order.extend(pid for pid in self.manager.providers if pid not in seen)
        self.manager.settings["provider_priority"] = order
        self.manager.save()
        return order

    def _blocklist(self) -> list[dict[str, str]]:
        raw = self.manager.settings.get("resolver_blocklist", [])
        if not isinstance(raw, list):
            return []
        return [x for x in raw if isinstance(x, dict)]

    def _preferences(self) -> list[dict[str, Any]]:
        raw = self.manager.settings.get("resolver_preferences", [])
        if not isinstance(raw, list):
            return []
        return [x for x in raw if isinstance(x, dict)]

    def preferred_entry(self, target: dict[str, Any]) -> dict[str, Any] | None:
        tfp = _fingerprint(target)
        for entry in reversed(self._preferences()):
            if str(entry.get("target") or "") == tfp:
                return dict(entry)
        return None

    def is_preferred(self, target: dict[str, Any], candidate: dict[str, Any]) -> bool:
        entry = self.preferred_entry(target)
        return bool(entry and str(entry.get("candidate") or "") == _candidate_key(candidate))

    def prefer(self, target: dict[str, Any], candidate: dict[str, Any]) -> None:
        tfp, ckey = _fingerprint(target), _candidate_key(candidate)
        entries = [x for x in self._preferences() if str(x.get("target") or "") != tfp]
        entries.append({"target": tfp, "candidate": ckey, "track": _safe_track_snapshot(candidate)})
        self.manager.settings["resolver_preferences"] = entries[-1000:]
        self.manager.save()

    def clear_preference(self, target: dict[str, Any]) -> None:
        tfp = _fingerprint(target)
        entries = [x for x in self._preferences() if str(x.get("target") or "") != tfp]
        if len(entries) != len(self._preferences()):
            self.manager.settings["resolver_preferences"] = entries
            self.manager.save()

    def is_blocked(self, target: dict[str, Any], candidate: dict[str, Any]) -> bool:
        tfp, ckey = _fingerprint(target), _candidate_key(candidate)
        return any(
            str(x.get("target")) == tfp and str(x.get("candidate")) == ckey
            for x in self._blocklist()
        )

    def block(self, target: dict[str, Any], candidate: dict[str, Any]) -> None:
        tfp, ckey = _fingerprint(target), _candidate_key(candidate)
        entries = self._blocklist()
        if not any(
            str(x.get("target")) == tfp and str(x.get("candidate")) == ckey
            for x in entries
        ):
            entries.append({"target": tfp, "candidate": ckey})
            self.manager.settings["resolver_blocklist"] = entries[-1000:]
            pref = self.preferred_entry(target)
            if pref and str(pref.get("candidate") or "") == ckey:
                self.manager.settings["resolver_preferences"] = [
                    x for x in self._preferences() if str(x.get("target") or "") != tfp
                ]
            self.manager.save()

    def unblock_target(self, target: dict[str, Any]) -> None:
        tfp = _fingerprint(target)
        entries = [x for x in self._blocklist() if str(x.get("target") or "") != tfp]
        if len(entries) != len(self._blocklist()):
            self.manager.settings["resolver_blocklist"] = entries
            self.manager.save()

    def unblock_all(self) -> None:
        self.manager.settings["resolver_blocklist"] = []
        self.manager.save()

    def score(
        self,
        target: dict[str, Any],
        candidate: dict[str, Any],
        provider_rank: int = 0,
        provider_count: int = 1,
    ) -> ResolutionCandidate:
        title = _similarity(target.get("title"), candidate.get("title"))
        artist_target = str(target.get("artist") or "").strip()
        artist = _similarity(artist_target, candidate.get("artist")) if artist_target else 1.0
        album_target = str(target.get("album") or "").strip()
        album = _similarity(album_target, candidate.get("album")) if album_target else 1.0

        target_terms = _variant_terms(target)
        candidate_terms = _variant_terms(candidate)
        major_mismatch = len((target_terms ^ candidate_terms) & _MAJOR_VARIANTS)
        minor_mismatch = len((target_terms ^ candidate_terms) & _MINOR_VARIANTS)
        penalty = min(0.36, 0.16 * major_mismatch + 0.055 * minor_mismatch)

        td, cd = _duration(target), _duration(candidate)
        duration_delta: float | None = abs(td - cd) if td and cd else None
        duration_adjustment = 0.0
        if duration_delta is not None:
            if duration_delta <= 3:
                duration_adjustment = 0.03
            elif duration_delta <= 10:
                duration_adjustment = 0.015
            elif duration_delta > 30:
                duration_adjustment = -0.04

        base = 0.60 * title + 0.32 * artist + 0.08 * album
        if provider_count <= 1:
            priority_bonus = 0.025
        else:
            priority_bonus = 0.025 * (1.0 - provider_rank / max(1, provider_count - 1))
        preferred = self.is_preferred(target, candidate)
        preference_bonus = 0.24 if preferred else 0.0
        total = max(0.0, min(1.0, base + priority_bonus + duration_adjustment + preference_bonus - penalty))
        return ResolutionCandidate(
            track=dict(candidate),
            score=total,
            provider_id=str(candidate.get("provider_id") or ""),
            provider_rank=provider_rank,
            title_score=title,
            artist_score=artist,
            album_score=album,
            version_penalty=penalty,
            duration_adjustment=duration_adjustment,
            duration_delta=duration_delta,
            preferred=preferred,
        )

    @staticmethod
    def _queries(track: dict[str, Any]) -> list[str]:
        artist = str(track.get("artist") or "").strip()
        title = str(track.get("title") or track.get("name") or "").strip()
        album = str(track.get("album") or "").strip()
        proposed: list[str] = []
        if artist and title:
            proposed.append(f"{artist} {title}")
        if title and album:
            proposed.append(f"{title} {album}")
        if title:
            proposed.append(title)
        if artist and not title:
            proposed.append(artist)

        seen: set[str] = set()
        queries: list[str] = []
        for query in proposed:
            key = query.casefold()
            if key not in seen:
                seen.add(key)
                queries.append(query)
        return queries

    def candidates(
        self,
        target: dict[str, Any],
        per_provider_limit: int = 12,
        total_limit: int = 40,
    ) -> list[ResolutionCandidate]:
        queries = self._queries(target)
        if not queries:
            return []
        order = self.provider_order()
        found: list[ResolutionCandidate] = []
        seen: set[str] = set()
        for rank, pid in enumerate(order):
            provider = self.manager.providers.get(pid)
            if provider is None:
                continue
            if not _provider_supports(provider, "search"):
                continue
            rows: list[dict[str, Any]] = []
            for query in queries:
                try:
                    rows = list(provider.search(query, per_provider_limit) or [])
                except Exception:
                    rows = []
                if rows:
                    break
            for raw in rows:
                candidate = dict(raw)
                candidate.setdefault("provider_id", pid)
                key = _candidate_key(candidate)
                if key in seen or self.is_blocked(target, candidate):
                    continue
                seen.add(key)
                scored = self.score(target, candidate, rank, max(1, len(order)))
                target_has_artist = bool(str(target.get("artist") or "").strip())
                if scored.title_score >= 0.42 and (
                    scored.artist_score >= 0.34 or not target_has_artist
                ):
                    found.append(scored)
        found.sort(
            key=lambda x: (-int(x.preferred), -x.score, x.provider_rank, -x.title_score, -x.artist_score)
        )
        return found[: max(1, int(total_limit))]

    def inspect(self, target: dict[str, Any], limit: int = 20) -> dict[str, Any]:
        requested = dict(target)
        ranked = self.candidates(requested, total_limit=limit)
        return {
            "requested": requested,
            "minimum_score": self.minimum_score,
            "preferred": self.preferred_entry(requested),
            "blocked_count": sum(1 for x in self._blocklist() if str(x.get("target") or "") == _fingerprint(requested)),
            "candidates": [x.as_dict() for x in ranked],
        }

    def resolve_exact(self, candidate: dict[str, Any], requested: dict[str, Any] | None = None) -> dict[str, Any]:
        item = dict(candidate)
        pid = str(item.get("provider_id") or "").strip()
        if not pid or pid not in self.manager.providers:
            raise RuntimeError("The selected source is no longer installed")
        provider = self.manager.providers[pid]
        if not _provider_supports(provider, "playback"):
            raise RuntimeError("The selected source does not provide playback")
        resolved = dict(provider.resolve(item))
        if not _playable(resolved):
            raise RuntimeError("The selected match is not currently playable")
        resolved.setdefault("provider_id", pid)
        target = dict(requested or {})
        resolved["_resolution"] = {
            "mode": "manual" if target else "direct",
            "provider_id": pid,
            "confidence": 1.0,
            "requested": {
                "artist": str(target.get("artist") or resolved.get("artist") or ""),
                "title": str(target.get("title") or resolved.get("title") or ""),
                "album": str(target.get("album") or resolved.get("album") or ""),
            },
        }
        return resolved

    def resolve(self, track: dict[str, Any]) -> dict[str, Any]:
        target = dict(track)
        pid = str(target.get("provider_id") or "").strip()
        direct_error = ""

        if not pid and _playable(target):
            target["_resolution"] = {
                "mode": "playlist-direct",
                "provider_id": "",
                "confidence": 1.0,
            }
            return target
        if pid and pid in self.manager.providers and (
            target.get("track_id") or target.get("local_path") or target.get("stream_url")
        ) and _provider_supports(self.manager.providers[pid], "playback"):
            try:
                direct = dict(self.manager.providers[pid].resolve(target))
                if _playable(direct):
                    direct.setdefault("provider_id", pid)
                    direct["_resolution"] = {
                        "mode": "direct",
                        "provider_id": pid,
                        "confidence": 1.0,
                    }
                    return direct
            except Exception as exc:
                direct_error = str(exc)

        pref = self.preferred_entry(target)
        if pref:
            preferred_track = pref.get("track")
            if isinstance(preferred_track, dict) and not self.is_blocked(target, preferred_track):
                try:
                    resolved = self.resolve_exact(preferred_track, target)
                    resolved["_resolution"]["mode"] = "preferred"
                    return resolved
                except Exception:
                    pass

        ranked = self.candidates(target)
        errors: list[str] = []
        for item in ranked:
            if item.score < self.minimum_score:
                break
            provider = self.manager.providers.get(item.provider_id)
            if provider is None:
                continue
            try:
                resolved = dict(provider.resolve(item.track))
                if not _playable(resolved):
                    raise RuntimeError("provider did not return a playable URL or local file")
                resolved.setdefault("provider_id", item.provider_id)
                for key in ("year", "reason"):
                    if target.get(key) not in (None, "") and resolved.get(key) in (None, ""):
                        resolved[key] = target[key]
                resolved["_resolution"] = {
                    "mode": "preferred" if item.preferred else "matched",
                    "provider_id": item.provider_id,
                    "confidence": round(item.score, 4),
                    "candidate_key": _candidate_key(item.track),
                    "requested": {
                        "artist": str(target.get("artist") or ""),
                        "title": str(target.get("title") or ""),
                        "album": str(target.get("album") or ""),
                    },
                }
                return resolved
            except Exception as exc:
                errors.append(f"{item.provider_id}: {exc}")

        title = str(target.get("title") or target.get("name") or "track")
        artist = str(target.get("artist") or "").strip()
        label = f"{artist} — {title}" if artist else title
        suffix = f" Direct source error: {direct_error}." if direct_error else ""
        if ranked:
            suffix += f" Best match confidence was {ranked[0].score:.0%}."
        if errors:
            suffix += " " + "; ".join(errors[:3])
        raise RuntimeError(f"Could not resolve {label} from the connected sources.{suffix}")

    def resolve_many(self, tracks: list[dict[str, Any]]) -> dict[str, Any]:
        resolved: list[dict[str, Any]] = []
        unresolved: list[dict[str, Any]] = []
        for raw in tracks:
            target = dict(raw)
            try:
                resolved.append(self.resolve(target))
            except Exception as exc:
                unresolved.append({"track": target, "error": str(exc)})
        return {"tracks": resolved, "unresolved": unresolved, "requested": len(tracks)}
