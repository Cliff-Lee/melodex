from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from .flow import FlowEngine, TrackAnalysis
from .user_state import UserState


_ANALYSIS_FIELDS = (
    "bpm",
    "rhythm_confidence",
    "key_pc",
    "key_mode",
    "key_confidence",
    "loudness_db",
    "energy",
    "energy_start",
    "energy_end",
    "spectral_centroid",
    "onset_density",
    "intro_mixability",
    "outro_mixability",
    "ending_type",
)


class LocalIntelligenceService:
    """Privacy-preserving adapter between Melodex Core and local-intelligence plugins.

    Plugins receive ephemeral refs plus a bounded, sanitized snapshot. Absolute
    paths, provider IDs, database keys and absolute listening timestamps never
    cross the extension boundary.
    """

    def __init__(self, state: UserState, flow: FlowEngine, capability_broker: Any):
        self.state = state
        self.flow = flow
        self.capability_broker = capability_broker

    @staticmethod
    def _duration_ms(track: dict[str, Any]) -> int:
        try:
            if track.get("duration_ms") not in (None, ""):
                return max(0, int(float(track.get("duration_ms") or 0)))
            return max(0, int(float(track.get("duration") or 0) * 1000))
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _analysis_payload(analysis: TrackAnalysis | None) -> dict[str, Any] | None:
        if analysis is None:
            return None
        raw = analysis.as_dict()
        return {key: raw.get(key) for key in _ANALYSIS_FIELDS}

    @staticmethod
    def _taste_payload(row: dict[str, Any], now: float) -> dict[str, Any]:
        plays = max(0, int(row.get("plays") or 0))
        completes = max(0, int(row.get("completes") or 0))
        skips = max(0, int(row.get("skips") or 0))
        last_played = float(row.get("last_played") or 0)
        days = None
        if last_played > 0:
            days = max(0.0, (now - last_played) / 86400.0)
        return {
            "plays": plays,
            "completes": completes,
            "skips": skips,
            "loves": max(0, int(row.get("loves") or 0)),
            "dislikes": max(0, int(row.get("dislikes") or 0)),
            "keeps": max(0, int(row.get("keeps") or 0)),
            "completion_rate": completes / max(1, plays),
            "skip_rate": skips / max(1, plays),
            "days_since_last_played": days,
        }

    @staticmethod
    def _path(track: dict[str, Any]) -> Path | None:
        value = str(track.get("local_path") or "").strip()
        return Path(value) if value else None

    def build_snapshot(
        self,
        catalog: list[dict[str, Any]],
        seeds: list[dict[str, Any]] | None = None,
        *,
        max_tracks: int = 2500,
        analyse_seeds: bool = True,
    ) -> tuple[list[dict[str, Any]], list[str], dict[str, dict[str, Any]], int]:
        seeds = [dict(x) for x in (seeds or []) if isinstance(x, dict)]
        seed_keys = {UserState.track_key(track) for track in seeds}
        signals = {
            str(row.get("track_key") or ""): dict(row)
            for row in self.state.track_signals(max(5000, int(max_tracks)))
        }

        deduped: list[dict[str, Any]] = []
        seen: set[str] = set()
        for raw in catalog:
            track = dict(raw or {})
            key = UserState.track_key(track)
            if not key or key in seen:
                continue
            seen.add(key)
            deduped.append(track)
            if len(deduped) >= max(1, int(max_tracks)):
                break

        # Ensure explicit seeds are represented even when they were outside the
        # bounded catalog slice.
        for track in seeds:
            key = UserState.track_key(track)
            if key and key not in seen:
                seen.add(key)
                deduped.append(track)

        now = time.time()
        profiles: list[dict[str, Any]] = []
        ref_map: dict[str, dict[str, Any]] = {}
        key_to_ref: dict[str, str] = {}
        analysed = 0

        for index, track in enumerate(deduped):
            key = UserState.track_key(track)
            ref = f"t{index}"
            key_to_ref[key] = ref
            ref_map[ref] = dict(track)

            path = self._path(track)
            analysis = None
            if path is not None:
                analysis = self.flow.cached_analysis_for(path)
                if analysis is None and analyse_seeds and key in seed_keys:
                    analysis = self.flow.analysis_for(path)
            if analysis is not None:
                analysed += 1

            profiles.append(
                {
                    "ref": ref,
                    "title": str(track.get("title") or ""),
                    "artist": str(track.get("artist") or ""),
                    "album": str(track.get("album") or ""),
                    "duration_ms": self._duration_ms(track),
                    "analysis": self._analysis_payload(analysis),
                    "taste": self._taste_payload(signals.get(key, {}), now),
                }
            )

        seed_refs = [
            key_to_ref[key]
            for key in (UserState.track_key(track) for track in seeds)
            if key in key_to_ref
        ][:2]
        return profiles, seed_refs, ref_map, analysed

    def analyse_catalog(self, catalog: list[dict[str, Any]]) -> dict[str, int]:
        total = 0
        analysed = 0
        already_cached = 0
        failed = 0
        seen: set[str] = set()
        for raw in catalog:
            track = dict(raw or {})
            key = UserState.track_key(track)
            if not key or key in seen:
                continue
            seen.add(key)
            path = self._path(track)
            if path is None or not path.exists():
                continue
            total += 1
            cached = self.flow.cached_analysis_for(path)
            if cached is not None:
                already_cached += 1
                analysed += 1
                continue
            result = self.flow.analysis_for(path)
            if result is not None:
                analysed += 1
            else:
                failed += 1
        return {
            "total": total,
            "analysed": analysed,
            "already_cached": already_cached,
            "newly_analysed": max(0, analysed - already_cached),
            "failed": failed,
        }

    def suggest(
        self,
        intent: str,
        catalog: list[dict[str, Any]],
        seeds: list[dict[str, Any]] | None = None,
        *,
        limit: int = 12,
        adventure: float = 0.35,
    ) -> dict[str, Any]:
        profiles, seed_refs, ref_map, analysed = self.build_snapshot(
            catalog,
            seeds,
            analyse_seeds=True,
        )
        result = self.capability_broker.suggest_library(
            profiles,
            intent=str(intent),
            seed_refs=seed_refs,
            limit=limit,
            adventure=adventure,
        )
        tracks: list[dict[str, Any]] = []
        for row in list(result.get("suggestions") or []):
            if not isinstance(row, dict):
                continue
            ref = str(row.get("ref") or "")
            track = ref_map.get(ref)
            if track is None:
                continue
            item = dict(track)
            item["_intelligence_score"] = float(row.get("score") or 0.0)
            item["_intelligence_reason"] = str(row.get("reason") or "")
            item["_intelligence_badges"] = [
                str(x) for x in list(row.get("badges") or []) if str(x)
            ]
            item["_intelligence_extension_id"] = str(row.get("_extension_id") or "")
            tracks.append(item)
        return {
            "intent": str(intent),
            "tracks": tracks,
            "analysed": analysed,
            "profiles": len(profiles),
            "seed_count": len(seed_refs),
            "errors": [str(x) for x in list(result.get("errors") or []) if x],
        }


__all__ = ["LocalIntelligenceService"]
