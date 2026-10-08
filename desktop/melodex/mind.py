from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .flow import FlowEngine
from .rediscovery_signals import build_rediscovery_signals
from .user_state import UserState


@dataclass
class MindPlan:
    tracks: list[dict[str, Any]]
    transitions: list[dict[str, Any]]
    analysed: int
    metadata_only: int
    mode: str
    minutes: int
    adventure: float
    familiar_share: float
    rediscovered: int
    new_to_you: int
    end_anchor: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "tracks": self.tracks,
            "transitions": self.transitions,
            "analysed": self.analysed,
            "metadata_only": self.metadata_only,
            "mode": self.mode,
            "minutes": self.minutes,
            "adventure": self.adventure,
            "familiar_share": self.familiar_share,
            "rediscovered": self.rediscovered,
            "new_to_you": self.new_to_you,
            "end_anchor": self.end_anchor,
        }


class MindEngine:
    """Local preference + session planner for Melodex.

    This is deliberately not a generative-AI feature.  It combines explicit
    user signals, completion/skip history, spacing/recency and Flow's audio
    compatibility to reduce choice overload while preserving user control.
    """

    def __init__(self, state: UserState, flow: FlowEngine):
        self.state = state
        self.flow = flow

    @staticmethod
    def track_key(track: dict[str, Any]) -> str:
        return UserState.track_key(track)

    @classmethod
    def dedupe(cls, tracks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        seen: set[str] = set()
        for raw in tracks:
            track = dict(raw or {})
            if not (track.get("local_path") or (track.get("track_id") and track.get("rel"))):
                continue
            key = cls.track_key(track)
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(track)
        return out

    def _stats(self) -> dict[str, dict[str, Any]]:
        return {str(row.get("track_key") or ""): dict(row) for row in self.state.track_signals(5000)}

    @staticmethod
    def _positive_signal(row: dict[str, Any]) -> float:
        plays = max(0, int(row.get("plays") or 0))
        completes = max(0, int(row.get("completes") or 0))
        skips = max(0, int(row.get("skips") or 0))
        loves = max(0, int(row.get("loves") or 0))
        dislikes = max(0, int(row.get("dislikes") or 0))
        keeps = max(0, int(row.get("keeps") or 0))
        completion = completes / max(1, plays)
        skip_rate = skips / max(1, plays)
        return 3.2 * loves + 1.5 * keeps + 1.25 * completion + 0.28 * math.log1p(plays) - 1.8 * skip_rate - 6.0 * dislikes

    def _artist_affinity(self, stats: dict[str, dict[str, Any]]) -> dict[str, float]:
        total: dict[str, float] = {}
        counts: dict[str, int] = {}
        for row in stats.values():
            artist = str(row.get("artist") or "").strip().casefold()
            if not artist:
                continue
            total[artist] = total.get(artist, 0.0) + self._positive_signal(row)
            counts[artist] = counts.get(artist, 0) + 1
        return {a: total[a] / max(1, counts[a]) for a in total}

    def _artist_memory_signals(
        self, stats: dict[str, dict[str, Any]], now: float
    ) -> dict[str, dict[str, Any]]:
        grouped: dict[str, dict[str, Any]] = {}
        for row in stats.values():
            artist = str(row.get("artist") or "").strip().casefold()
            if not artist:
                continue
            group = grouped.setdefault(
                artist,
                {
                    "played_tracks": 0,
                    "favorite_tracks": 0,
                    "positive_total": 0.0,
                    "last_played": 0.0,
                },
            )
            plays = max(0, int(row.get("plays") or 0))
            if plays:
                group["played_tracks"] += 1
                group["positive_total"] += self._positive_signal(row)
            if int(row.get("loves") or 0) > 0 or int(row.get("keeps") or 0) > 0:
                group["favorite_tracks"] += 1
            group["last_played"] = max(
                float(group["last_played"] or 0.0),
                float(row.get("last_played") or 0.0),
            )

        result: dict[str, dict[str, Any]] = {}
        for artist, group in grouped.items():
            played_tracks = int(group["played_tracks"])
            last_played = float(group["last_played"] or 0.0)
            days = max(0.0, (now - last_played) / 86400.0) if last_played else None
            average_positive = float(group["positive_total"]) / max(1, played_tracks)
            favorite_tracks = int(group["favorite_tracks"])

            spacing = 0.0
            if played_tracks and days is not None and 21.0 <= days <= 1460.0:
                centre = 120.0
                spacing = math.exp(
                    -((math.log(days + 1.0) - math.log(centre + 1.0)) ** 2) / 1.8
                )
            affinity = max(0.0, min(1.0, (average_positive + 0.2) / 2.7))
            strength = 1.0 if favorite_tracks else affinity
            result[artist] = {
                "played_tracks": played_tracks,
                "favorite_tracks": favorite_tracks,
                "favorite_artist": favorite_tracks > 0,
                "average_positive": average_positive,
                "days_since_last_played": days,
                "rediscovery": max(0.0, min(1.0, spacing * strength)),
            }
        return result

    def score(
        self,
        track: dict[str, Any],
        stats: dict[str, dict[str, Any]],
        mode: str,
        adventure: float,
        now: float,
        artist_affinity: dict[str, float] | None = None,
        library_signal: dict[str, Any] | None = None,
        artist_memory: dict[str, Any] | None = None,
    ) -> tuple[float, str]:
        key = self.track_key(track)
        row = stats.get(key, {})
        plays = int(row.get("plays") or 0)
        dislikes = int(row.get("dislikes") or 0)
        last_played = float(row.get("last_played") or 0)
        days = ((now - last_played) / 86400.0) if last_played else 9999.0
        positive = self._positive_signal(row)
        artist = str(track.get("artist") or "").strip().casefold()
        affinity_map = artist_affinity if artist_affinity is not None else self._artist_affinity(stats)
        affinity = affinity_map.get(artist, 0.0) if artist else 0.0
        library_signal = library_signal or {}
        library_score = max(0.0, min(1.0, float(library_signal.get("library_score") or 0.0)))
        library_reason = str(library_signal.get("reason") or "")
        artist_memory = artist_memory or {}
        artist_rediscovery = max(
            0.0, min(1.0, float(artist_memory.get("rediscovery") or 0.0))
        )
        favorite_track = int(row.get("loves") or 0) > 0 or int(row.get("keeps") or 0) > 0
        adventure = max(0.0, min(1.0, float(adventure)))

        # Recently heard tracks get a strong temporary penalty: familiarity is
        # valuable, but immediate repetition quickly creates habituation.
        recent_penalty = 0.0
        if days < 0.25:
            recent_penalty = 4.0
        elif days < 1.0:
            recent_penalty = 2.2
        elif days < 3.0:
            recent_penalty = 1.0

        # Keep older favourites eligible for spaced resurfacing, not just
        # tracks last played a few weeks ago.
        rediscovery = 0.0
        if plays and 10.0 <= days <= 1460.0:
            centre = 120.0
            rediscovery = 1.6 * math.exp(
                -((math.log(days + 1.0) - math.log(centre + 1.0)) ** 2) / 1.8
            )

        unheard = 1.0 if plays == 0 else 0.0
        familiar = min(1.8, 0.45 * math.log1p(plays) + max(0.0, positive) * 0.18)
        artist_bonus = max(-1.2, min(1.2, affinity * 0.12))

        mode = str(mode or "balanced").lower()
        if mode == "comfort":
            score = 1.30 * positive + 1.5 * familiar + 0.8 * artist_bonus + 0.30 * rediscovery - 1.2 * unheard
            reason = "trusted favourite" if positive > 1.2 else "familiar fit"
        elif mode == "rediscover":
            score = (
                0.72 * positive + 2.25 * rediscovery + 0.55 * familiar
                + 0.25 * artist_bonus + 1.25 * library_score
                + 1.2 * artist_rediscovery - 0.4 * unheard
            )
            if rediscovery > 0.6:
                reason = "favourite ready to return" if favorite_track else "ready to rediscover"
            elif not plays and artist_rediscovery > 0.35:
                reason = (
                    "from a favourite artist you haven't heard lately"
                    if artist_memory.get("favorite_artist")
                    else "from an artist you haven't heard lately"
                )
            elif plays:
                if favorite_track and days >= 30.0:
                    reason = "older favourite"
                elif days < 3.0:
                    reason = "heard recently"
                else:
                    reason = "from your listening history"
            else:
                reason = library_reason or "new to you"
        elif mode == "explore":
            score = 2.2 * unheard + 0.65 * artist_bonus + 0.45 * max(0.0, positive) + 0.4 * adventure - 0.35 * familiar
            reason = "new to you" if unheard else "less familiar direction"
        else:
            # Familiarity/novelty balance (mere exposure + novelty) is directly
            # controlled by the user's Adventure slider rather than hidden.
            score = (1.05 - 0.45 * adventure) * positive + (1.15 - 0.85 * adventure) * familiar + (0.45 + 1.65 * adventure) * unheard + 0.75 * rediscovery + 0.45 * artist_bonus
            if unheard:
                reason = "fresh discovery"
            elif rediscovery > 0.55:
                reason = "spaced rediscovery"
            elif positive > 1.3:
                reason = "strong taste match"
            else:
                reason = "fits your listening pattern"

        if dislikes:
            score -= 20.0 * dislikes
            reason = "previously marked not for me"
        score -= recent_penalty
        return score, reason

    @staticmethod
    def _duration_seconds(track: dict[str, Any]) -> int:
        try:
            value = int(float(track.get("duration") or 0))
            return value if value >= 45 else 240
        except Exception:
            return 240

    def build_session(
        self,
        candidates: list[dict[str, Any]],
        path_for: Callable[[dict[str, Any]], Path | None],
        *,
        minutes: int = 60,
        adventure: float = 0.34,
        mode: str = "balanced",
        start_track: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        pool = self.dedupe(candidates)
        if not pool:
            return MindPlan([], [], 0, 0, mode, minutes, adventure, 0.0, 0, 0, "").as_dict()

        stats = self._stats()
        now = time.time()
        rng = random.Random(time.time_ns())
        scored: list[tuple[float, float, dict[str, Any], str]] = []
        artist_affinity = self._artist_affinity(stats)
        artist_memories = self._artist_memory_signals(stats, now)
        library_signals = build_rediscovery_signals(pool, stats)
        for track in pool:
            artist = str(track.get("artist") or "").strip().casefold()
            score, reason = self.score(
                track,
                stats,
                mode,
                adventure,
                now,
                artist_affinity,
                library_signals.get(self.track_key(track)),
                artist_memories.get(artist),
            )
            # Tiny bounded jitter prevents every session from being identical
            # without turning selection into opaque random shuffle.
            jitter = rng.uniform(-0.12, 0.12) * (0.35 + adventure)
            scored.append((score + jitter, score, track, reason))
        scored.sort(key=lambda x: x[0], reverse=True)

        target_seconds = max(15, int(minutes)) * 60
        durations = sorted(self._duration_seconds(t) for t in pool)
        typical = durations[len(durations) // 2] if durations else 240
        typical = max(120, min(480, typical))
        max_tracks = max(4, min(40, int(math.ceil(target_seconds / typical))))
        selected: list[dict[str, Any]] = []
        seconds = 0
        seen_artists: dict[str, int] = {}
        if mode == "comfort":
            target_new = max(0, round(max_tracks * 0.06))
        elif mode == "rediscover":
            target_new = max(0, round(max_tracks * 0.10))
        elif mode == "explore":
            target_new = max(1, round(max_tracks * 0.78))
        else:
            target_new = max(1, round(max_tracks * (0.12 + 0.65 * adventure)))
        new_selected = 0

        if start_track:
            start_key = self.track_key(start_track)
            for _jittered, _base, track, reason in scored:
                if self.track_key(track) == start_key:
                    t = dict(track)
                    t["_mind_reason"] = "continue from here"
                    selected.append(t)
                    seconds += self._duration_seconds(t)
                    if int(stats.get(start_key, {}).get("plays") or 0) == 0:
                        new_selected += 1
                    a = str(t.get("artist") or "").casefold()
                    seen_artists[a] = seen_artists.get(a, 0) + 1
                    break

        for _jittered, base, track, reason in scored:
            if len(selected) >= max_tracks or seconds >= target_seconds * 1.06:
                break
            key = self.track_key(track)
            if any(self.track_key(x) == key for x in selected):
                continue
            artist = str(track.get("artist") or "").strip().casefold()
            # Artist-spacing combats habituation and makes rediscovery feel
            # broader. Allow a repeat only if the candidate pool is small.
            if artist and seen_artists.get(artist, 0) >= (2 if len(pool) < 20 else 1):
                continue
            if base < -8.0:
                continue
            is_new = int(stats.get(key, {}).get("plays") or 0) == 0
            if is_new and new_selected >= target_new and mode != "explore":
                continue
            if (not is_new) and mode == "explore" and new_selected < target_new:
                # In Explore mode, reserve early capacity for genuinely new
                # tracks before filling with familiar bridges.
                remaining_new = sum(1 for _a, _b, cand, _r in scored if int(stats.get(self.track_key(cand), {}).get("plays") or 0) == 0 and not any(self.track_key(x) == self.track_key(cand) for x in selected))
                if remaining_new > 0:
                    continue
            t = dict(track)
            t["_mind_reason"] = reason
            selected.append(t)
            seconds += self._duration_seconds(t)
            if is_new:
                new_selected += 1
            if artist:
                seen_artists[artist] = seen_artists.get(artist, 0) + 1

        # If strict artist-spacing left the session too short, first backfill
        # with familiar tracks while preserving the explicit novelty budget.
        if seconds < target_seconds * 0.92:
            for _jittered, base, track, reason in scored:
                if len(selected) >= max_tracks or seconds >= target_seconds:
                    break
                key = self.track_key(track)
                if base < -8.0 or any(self.track_key(x) == key for x in selected):
                    continue
                is_new = int(stats.get(key, {}).get("plays") or 0) == 0
                if is_new and new_selected >= target_new and mode != "explore":
                    continue
                t = dict(track)
                t["_mind_reason"] = reason
                selected.append(t)
                seconds += self._duration_seconds(t)
                if is_new:
                    new_selected += 1

        # Only if the known library simply cannot fill the requested duration do
        # we relax the novelty quota. This avoids dead air without hiding the
        # Familiar/Surprising control from the user.
        if seconds < target_seconds * 0.72:
            for _jittered, base, track, reason in scored:
                if len(selected) >= max_tracks or seconds >= target_seconds:
                    break
                key = self.track_key(track)
                if base < -8.0 or any(self.track_key(x) == key for x in selected):
                    continue
                t = dict(track)
                t["_mind_reason"] = reason
                selected.append(t)
                seconds += self._duration_seconds(t)
                if int(stats.get(key, {}).get("plays") or 0) == 0:
                    new_selected += 1

        if not selected:
            selected = [dict(scored[0][2])]

        # Peak-end rule, applied transparently: reserve one positively rated,
        # familiar track as the landing point. Flow still chooses the route.
        end_index: int | None = None
        best_end = -999.0
        for i, track in enumerate(selected):
            row = stats.get(self.track_key(track), {})
            positive = self._positive_signal(row)
            if int(row.get("plays") or 0) > 0 and int(row.get("dislikes") or 0) == 0 and positive > best_end:
                best_end = positive
                end_index = i
        start_index_for_flow = 0
        if end_index == 0 and len(selected) > 2:
            if start_track:
                # Preserve the explicit/current starting track, and choose the
                # best different familiar track for the landing point.
                alt_index = None
                alt_score = -999.0
                for i, track in enumerate(selected[1:], start=1):
                    row = stats.get(self.track_key(track), {})
                    positive = self._positive_signal(row)
                    if int(row.get("plays") or 0) > 0 and int(row.get("dislikes") or 0) == 0 and positive > alt_score:
                        alt_score = positive
                        alt_index = i
                end_index = alt_index
            else:
                # Let the strongest anchor remain reserved for the end and start
                # from the next best candidate instead.
                start_index_for_flow = 1

        plan = self.flow.plan_order(
            selected,
            path_for,
            start_index=start_index_for_flow,
            end_index=end_index,
            adventurous=max(0.0, min(1.0, adventure)),
            analyse_missing=True,
        )
        ordered = [dict(t) for t in plan.get("tracks") or selected]

        played = 0
        new_to_you = 0
        rediscovered = 0
        for track in ordered:
            row = stats.get(self.track_key(track), {})
            p = int(row.get("plays") or 0)
            if p:
                played += 1
                last = float(row.get("last_played") or 0)
                days = (now - last) / 86400.0 if last else 9999
                if 10 <= days <= 240:
                    rediscovered += 1
            else:
                new_to_you += 1

        familiar_share = played / max(1, len(ordered))
        end_anchor = ""
        if ordered:
            end_anchor = str(ordered[-1].get("title") or "")
        return MindPlan(
            tracks=ordered,
            transitions=[dict(x) for x in (plan.get("transitions") or [])],
            analysed=int(plan.get("analysed") or 0),
            metadata_only=int(plan.get("metadata_only") or 0),
            mode=mode,
            minutes=max(15, int(minutes)),
            adventure=max(0.0, min(1.0, adventure)),
            familiar_share=familiar_share,
            rediscovered=rediscovered,
            new_to_you=new_to_you,
            end_anchor=end_anchor,
        ).as_dict()


__all__ = ["MindEngine", "MindPlan"]
