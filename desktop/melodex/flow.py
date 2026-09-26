from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Callable

try:
    import numpy as np
except Exception:  # Flow degrades gracefully if numpy is unavailable.
    np = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Melodex Flow
# ---------------------------------------------------------------------------
# Flow intentionally does not use a language model.  It analyses audio locally,
# caches a small fingerprint, and uses deterministic musical rules to choose an
# order and a transition style.  The first release favours robust, explainable
# behaviour over trying to imitate a full DJ workstation.

KEY_NAMES = ("C", "C♯", "D", "E♭", "E", "F", "F♯", "G", "A♭", "A", "B♭", "B")

# Krumhansl-Schmuckler key profiles, normalised later before comparison.
_MAJOR_PROFILE = (6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88)
_MINOR_PROFILE = (6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17)


@dataclass(slots=True)
class TrackAnalysis:
    version: int = 1
    path: str = ""
    duration: float = 0.0
    bpm: float = 0.0
    rhythm_confidence: float = 0.0
    key_pc: int = -1
    key_mode: str = ""
    key_confidence: float = 0.0
    loudness_db: float = -60.0
    energy: float = 0.0
    energy_start: float = 0.0
    energy_end: float = 0.0
    energy_curve: list[float] | None = None
    spectral_centroid: float = 0.0
    onset_density: float = 0.0
    intro_mixability: float = 0.0
    outro_mixability: float = 0.0
    ending_type: str = "natural"  # fade, abrupt, natural
    analysed_at: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out["key"] = self.key_label
        return out

    @property
    def key_label(self) -> str:
        if not 0 <= self.key_pc < 12:
            return ""
        return f"{KEY_NAMES[self.key_pc]} {'major' if self.key_mode == 'major' else 'minor'}"

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TrackAnalysis":
        allowed = set(cls.__dataclass_fields__.keys())
        return cls(**{k: v for k, v in payload.items() if k in allowed})


@dataclass(slots=True)
class TransitionPlan:
    style: str = "smooth"       # beat, phrase, harmonic, cut, natural, smooth
    duration_ms: int = 6000
    score: float = 0.0
    reason: str = ""
    bpm_compatibility: float = 0.0
    key_compatibility: float = 0.0
    energy_compatibility: float = 0.0
    confidence: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class FlowCache:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock, self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS flow_analysis (
                    cache_key TEXT PRIMARY KEY,
                    path TEXT NOT NULL,
                    mtime_ns INTEGER NOT NULL,
                    size INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    updated_at REAL NOT NULL
                )
                """
            )

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    @staticmethod
    def fingerprint(path: Path) -> tuple[str, int, int]:
        stat = path.stat()
        raw = f"{path.resolve()}|{stat.st_mtime_ns}|{stat.st_size}".encode("utf-8", "replace")
        return hashlib.sha1(raw).hexdigest(), int(stat.st_mtime_ns), int(stat.st_size)

    def get(self, path: Path) -> TrackAnalysis | None:
        try:
            key, mtime, size = self.fingerprint(path)
        except OSError:
            return None
        with self._lock:
            row = self._conn.execute(
                "SELECT payload_json,mtime_ns,size FROM flow_analysis WHERE cache_key=?", (key,)
            ).fetchone()
        if not row or int(row["mtime_ns"]) != mtime or int(row["size"]) != size:
            return None
        try:
            payload = json.loads(row["payload_json"])
            return TrackAnalysis.from_dict(payload) if isinstance(payload, dict) else None
        except Exception:
            return None

    def put(self, path: Path, analysis: TrackAnalysis) -> None:
        try:
            key, mtime, size = self.fingerprint(path)
        except OSError:
            return
        payload = json.dumps(asdict(analysis), ensure_ascii=False, separators=(",", ":"))
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO flow_analysis(cache_key,path,mtime_ns,size,payload_json,updated_at)
                VALUES(?,?,?,?,?,?)
                ON CONFLICT(cache_key) DO UPDATE SET
                  path=excluded.path,
                  mtime_ns=excluded.mtime_ns,
                  size=excluded.size,
                  payload_json=excluded.payload_json,
                  updated_at=excluded.updated_at
                """,
                (key, str(path), mtime, size, payload, time.time()),
            )


class LocalAudioAnalyzer:
    """Small local audio analyser used by Flow.

    ffmpeg is used only as a decoder.  The musical analysis itself is local
    numpy code.  When Melodex is packaged, build_macos.sh bundles the user's
    ffmpeg binary into the app if one is present.  Source runs can use Homebrew
    ffmpeg or a MELODEX_FFMPEG override.
    """

    sample_rate = 11025

    def __init__(self, cache: FlowCache):
        self.cache = cache
        self.ffmpeg = self._find_ffmpeg()

    @staticmethod
    def _find_ffmpeg() -> str:
        candidates: list[str] = []
        env = str(os.environ.get("MELODEX_FFMPEG", "") or "").strip()
        if env:
            candidates.append(env)
        meipass = str(getattr(sys, "_MEIPASS", "") or "")
        if meipass:
            candidates.extend([
                str(Path(meipass) / "ffmpeg"),
                str(Path(meipass) / "bin" / "ffmpeg"),
            ])
        found = shutil.which("ffmpeg")
        if found:
            candidates.append(found)
        candidates.extend(["/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg"])
        for item in candidates:
            if item and Path(item).exists() and os.access(item, os.X_OK):
                return item
        return ""

    @property
    def available(self) -> bool:
        return bool(self.ffmpeg and np is not None)

    def analyse(self, path: Path) -> TrackAnalysis | None:
        path = Path(path)
        cached = self.cache.get(path)
        if cached is not None:
            return cached
        if not self.available or not path.exists():
            return None
        samples = self._decode(path)
        if samples is None or samples.size < self.sample_rate * 8:
            return None
        result = self._features(path, samples)
        self.cache.put(path, result)
        return result

    def _decode(self, path: Path):
        # 11.025 kHz mono is more than sufficient for structural/BPM/key
        # analysis and keeps memory use low (~10 MB for a four minute song).
        cmd = [
            self.ffmpeg, "-v", "error", "-nostdin", "-i", str(path),
            "-vn", "-ac", "1", "-ar", str(self.sample_rate),
            "-f", "f32le", "-acodec", "pcm_f32le", "pipe:1",
        ]
        try:
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180, check=False)
            if proc.returncode != 0 or not proc.stdout:
                return None
            return np.frombuffer(proc.stdout, dtype="<f4").astype(np.float32, copy=False)
        except Exception:
            return None

    @staticmethod
    def _normalise01(values):
        values = np.asarray(values, dtype=float)
        if values.size == 0:
            return values
        lo = float(np.percentile(values, 10))
        hi = float(np.percentile(values, 90))
        if hi <= lo + 1e-12:
            return np.zeros_like(values)
        return np.clip((values - lo) / (hi - lo), 0.0, 1.0)

    def _features(self, path: Path, y) -> TrackAnalysis:
        sr = self.sample_rate
        duration = float(y.size) / sr

        # Energy envelope: 93 ms frames with 50% overlap.
        frame = 1024
        hop = 512
        n_frames = max(1, 1 + (len(y) - frame) // hop)
        rms = np.empty(n_frames, dtype=np.float32)
        flux = np.empty(n_frames, dtype=np.float32)
        prev_mag = None
        window = np.hanning(frame).astype(np.float32)
        centroid_sum = 0.0
        centroid_weight = 0.0
        freqs = np.fft.rfftfreq(frame, 1.0 / sr)
        for i in range(n_frames):
            start = i * hop
            chunk = y[start:start + frame]
            if chunk.size < frame:
                chunk = np.pad(chunk, (0, frame - chunk.size))
            rms[i] = float(np.sqrt(np.mean(chunk * chunk) + 1e-12))
            mag = np.abs(np.fft.rfft(chunk * window)).astype(np.float32)
            total = float(mag.sum()) + 1e-12
            centroid_sum += float((mag * freqs).sum() / total) * float(rms[i] + 1e-6)
            centroid_weight += float(rms[i] + 1e-6)
            if prev_mag is None:
                flux[i] = 0.0
            else:
                diff = mag - prev_mag
                flux[i] = float(np.maximum(diff, 0).sum() / (total + float(prev_mag.sum()) + 1e-12))
            prev_mag = mag

        rms_n = self._normalise01(rms)
        flux_n = self._normalise01(flux)
        onset = np.clip(0.72 * flux_n + 0.28 * np.maximum(0, np.r_[0.0, np.diff(rms_n)]), 0, 1)

        bpm, rhythm_conf = self._tempo(onset, sr / hop)
        key_pc, key_mode, key_conf = self._key(y, sr)

        # Perceived energy favours density and rhythmic activity, but does not
        # assume that fast == energetic.  This makes Flow useful for rock,
        # metal, hip-hop, ambient and acoustic material too.
        median_rms = float(np.median(rms))
        loudness_db = 20.0 * math.log10(max(1e-8, float(np.percentile(rms, 70))))
        onset_density = float(np.mean(onset > max(0.35, float(np.mean(onset) + 0.55 * np.std(onset)))))
        centroid = centroid_sum / max(1e-12, centroid_weight)
        brightness = max(0.0, min(1.0, (centroid - 600.0) / 2800.0))
        loud_component = max(0.0, min(1.0, (loudness_db + 42.0) / 28.0))
        energy = max(0.0, min(1.0,
            0.46 * loud_component + 0.24 * min(1.0, onset_density * 7.0)
            + 0.18 * rhythm_conf + 0.12 * brightness
        ))

        curve: list[float] = []
        for section in np.array_split(rms_n, 24):
            curve.append(round(float(np.mean(section)) if len(section) else 0.0, 4))
        head_n = max(1, int(12.0 / (hop / sr)))
        tail_n = head_n
        energy_start = float(np.mean(rms_n[:head_n]))
        energy_end = float(np.mean(rms_n[-tail_n:]))

        intro_mix = self._mixability(rms_n[:head_n], onset[:head_n])
        outro_mix = self._mixability(rms_n[-tail_n:], onset[-tail_n:])
        ending = self._ending_type(rms, sr / hop)

        return TrackAnalysis(
            path=str(path), duration=duration, bpm=bpm, rhythm_confidence=rhythm_conf,
            key_pc=key_pc, key_mode=key_mode, key_confidence=key_conf,
            loudness_db=loudness_db, energy=energy,
            energy_start=energy_start, energy_end=energy_end,
            energy_curve=curve, spectral_centroid=float(centroid),
            onset_density=onset_density, intro_mixability=intro_mix,
            outro_mixability=outro_mix, ending_type=ending, analysed_at=time.time(),
        )

    @staticmethod
    def _tempo(onset, frame_rate: float) -> tuple[float, float]:
        x = np.asarray(onset, dtype=np.float64)
        if x.size < 32 or float(np.std(x)) < 1e-6:
            return 0.0, 0.0
        x = x - float(np.mean(x))
        lo_bpm, hi_bpm = 60.0, 200.0
        min_lag = max(1, int(round(frame_rate * 60.0 / hi_bpm)))
        max_lag = min(len(x) - 2, int(round(frame_rate * 60.0 / lo_bpm)))
        if max_lag <= min_lag:
            return 0.0, 0.0
        # Direct correlations over this small lag range are quick and avoid a
        # huge autocorrelation array for long recordings.
        corrs = []
        for lag in range(min_lag, max_lag + 1):
            a = x[:-lag]
            b = x[lag:]
            denom = math.sqrt(float(np.dot(a, a)) * float(np.dot(b, b))) + 1e-12
            corrs.append(float(np.dot(a, b)) / denom)
        arr = np.asarray(corrs)
        idx = int(np.argmax(arr))
        lag = min_lag + idx
        bpm = 60.0 * frame_rate / lag
        peak = float(arr[idx])
        baseline = float(np.median(arr))
        conf = max(0.0, min(1.0, (peak - baseline) / 0.42))
        # Prefer a musically useful metrical level without assuming dance music.
        while bpm < 78.0:
            bpm *= 2.0
        while bpm > 178.0:
            bpm *= 0.5
        return round(float(bpm), 2), round(conf, 4)

    @staticmethod
    def _key(y, sr: int) -> tuple[int, str, float]:
        # Sample at most ~70 s spread across the track so long intros/outros do
        # not dominate the tonal estimate.
        if len(y) < sr * 4:
            return -1, "", 0.0
        frame = 4096
        window = np.hanning(frame)
        max_frames = 180
        starts = np.linspace(0, max(0, len(y) - frame), max_frames, dtype=int)
        chroma = np.zeros(12, dtype=np.float64)
        freqs = np.fft.rfftfreq(frame, 1.0 / sr)
        valid = (freqs >= 55.0) & (freqs <= 4200.0)
        vf = freqs[valid]
        midi = np.rint(69.0 + 12.0 * np.log2(np.maximum(vf, 1e-9) / 440.0)).astype(int)
        pcs = np.mod(midi, 12)
        for start in starts:
            chunk = y[start:start + frame]
            if len(chunk) < frame:
                continue
            mag = np.abs(np.fft.rfft(chunk * window))[valid]
            power = mag * mag
            np.add.at(chroma, pcs, power)
        if float(chroma.sum()) <= 1e-12:
            return -1, "", 0.0
        chroma /= float(chroma.sum())
        major = np.asarray(_MAJOR_PROFILE, dtype=float)
        minor = np.asarray(_MINOR_PROFILE, dtype=float)
        major = (major - major.mean()) / (major.std() + 1e-12)
        minor = (minor - minor.mean()) / (minor.std() + 1e-12)
        c = (chroma - chroma.mean()) / (chroma.std() + 1e-12)
        candidates: list[tuple[float, int, str]] = []
        for root in range(12):
            candidates.append((float(np.dot(c, np.roll(major, root)) / 12.0), root, "major"))
            candidates.append((float(np.dot(c, np.roll(minor, root)) / 12.0), root, "minor"))
        candidates.sort(reverse=True, key=lambda x: x[0])
        best = candidates[0]
        second = candidates[1]
        conf = max(0.0, min(1.0, 0.35 + 1.8 * (best[0] - second[0])))
        return int(best[1]), str(best[2]), round(conf, 4)

    @staticmethod
    def _mixability(rms_n, onset) -> float:
        if len(rms_n) == 0:
            return 0.0
        # Sparse / stable sections are easier to layer without creating a mess.
        activity = float(np.mean(rms_n))
        variation = float(np.std(rms_n))
        transient = float(np.mean(onset)) if len(onset) else 0.0
        value = 0.45 * (1.0 - min(1.0, variation * 2.5)) + 0.35 * (1.0 - min(1.0, transient * 1.8)) + 0.20 * (1.0 - activity * 0.55)
        return round(max(0.0, min(1.0, value)), 4)

    @staticmethod
    def _ending_type(rms, frame_rate: float) -> str:
        if len(rms) < max(8, int(frame_rate * 8)):
            return "natural"
        one = max(1, int(frame_rate * 1.0))
        five = max(one + 1, int(frame_rate * 5.0))
        fifteen = max(five + 1, int(frame_rate * 15.0))
        end1 = float(np.mean(rms[-one:]))
        before5 = float(np.mean(rms[-five:-one]))
        before15 = float(np.mean(rms[-fifteen:-five]))
        # A pronounced downward ramp indicates a recorded fade.
        if before15 > 1e-7 and end1 / before15 < 0.20 and before5 < before15 * 0.72:
            return "fade"
        # If the recording remains energetic right up to the boundary, preserve
        # the final hit/chord with a cut or very short handover.
        global_med = float(np.median(rms)) + 1e-12
        if end1 > global_med * 0.72 and before5 > global_med * 0.70:
            return "abrupt"
        return "natural"


class FlowEngine:
    def __init__(self, cache_path: Path):
        self.cache = FlowCache(cache_path)
        self.analyzer = LocalAudioAnalyzer(self.cache)

    def close(self) -> None:
        self.cache.close()

    @property
    def analysis_available(self) -> bool:
        return self.analyzer.available

    def analysis_for(self, path: Path | None) -> TrackAnalysis | None:
        if path is None:
            return None
        return self.analyzer.analyse(path)

    def cached_analysis_for(self, path: Path | None) -> TrackAnalysis | None:
        if path is None or not Path(path).exists():
            return None
        return self.cache.get(Path(path))

    @staticmethod
    def _bpm_compat(a: TrackAnalysis | None, b: TrackAnalysis | None) -> float:
        if not a or not b or a.bpm <= 0 or b.bpm <= 0:
            return 0.45
        ratios = [b.bpm / a.bpm, (b.bpm * 0.5) / a.bpm, (b.bpm * 2.0) / a.bpm]
        diff = min(abs(math.log(max(1e-6, r), 2.0)) for r in ratios)
        return max(0.0, min(1.0, math.exp(-9.0 * diff * diff)))

    @staticmethod
    def _key_compat(a: TrackAnalysis | None, b: TrackAnalysis | None) -> float:
        if not a or not b or a.key_pc < 0 or b.key_pc < 0:
            return 0.50
        d = (b.key_pc - a.key_pc) % 12
        # Same key, relative major/minor, fifth/fourth, then nearby tonal centres.
        if d == 0:
            return 1.0 if a.key_mode == b.key_mode else 0.92
        if a.key_mode != b.key_mode and d in {3, 9}:
            return 0.90
        if d in {5, 7}:
            return 0.84
        if d in {2, 10}:
            return 0.66
        if d in {1, 11}:
            return 0.48
        return 0.38

    @staticmethod
    def _energy_compat(a: TrackAnalysis | None, b: TrackAnalysis | None, target_delta: float = 0.0) -> float:
        if not a or not b:
            return 0.55
        actual = b.energy - a.energy
        return max(0.0, min(1.0, math.exp(-8.0 * (actual - target_delta) ** 2)))

    @staticmethod
    def _timbre_compat(a: TrackAnalysis | None, b: TrackAnalysis | None) -> float:
        if not a or not b or a.spectral_centroid <= 0 or b.spectral_centroid <= 0:
            return 0.55
        distance = abs(math.log((b.spectral_centroid + 120.0) / (a.spectral_centroid + 120.0)))
        return max(0.0, min(1.0, math.exp(-1.8 * distance)))

    def transition(self, a: TrackAnalysis | None, b: TrackAnalysis | None) -> TransitionPlan:
        bpm = self._bpm_compat(a, b)
        key = self._key_compat(a, b)
        energy = self._energy_compat(a, b)
        timbre = self._timbre_compat(a, b)
        mixability = ((a.outro_mixability if a else 0.45) + (b.intro_mixability if b else 0.45)) / 2.0
        confidence = ((a.rhythm_confidence if a else 0.0) + (b.rhythm_confidence if b else 0.0)) / 2.0
        score = 0.26 * key + 0.22 * energy + 0.18 * bpm + 0.18 * timbre + 0.16 * mixability

        # Respect abrupt endings: fading a punk/rock final chord sounds worse than
        # an intentional cut.  This is one of the core genre-agnostic rules.
        if a and a.ending_type == "abrupt":
            return TransitionPlan("cut", 500, score, "preserve the outgoing final hit", bpm, key, energy, confidence)

        # Beat blends only when both tracks show a stable rhythmic pulse and
        # their tempi genuinely fit.  Flow never forces an acoustic/classical
        # recording through dance-music logic.
        if a and b and a.rhythm_confidence >= 0.48 and b.rhythm_confidence >= 0.48 and bpm >= 0.78:
            return TransitionPlan("beat", 11000, score + 0.08, "compatible pulse and tempo", bpm, key, energy, confidence)

        if key >= 0.82 and mixability >= 0.58:
            return TransitionPlan("harmonic", 7500, score + 0.04, "compatible tonality with a clean overlap", bpm, key, energy, confidence)

        if mixability >= 0.60 and (a and a.ending_type == "fade"):
            return TransitionPlan("phrase", 6500, score, "use the outgoing fade as a natural handover", bpm, key, energy, confidence)

        if mixability < 0.35:
            return TransitionPlan("natural", 1800, score, "busy sections: keep overlap short", bpm, key, energy, confidence)

        return TransitionPlan("smooth", 5200, score, "balanced genre-neutral blend", bpm, key, energy, confidence)

    @staticmethod
    def _target_energy(position: float) -> float:
        # Default Journey shape: warm-up -> gradual build -> peak near 78% ->
        # gentle release.  It is intentionally subtle so mixed-genre playlists
        # do not feel artificially sorted by loudness.
        p = max(0.0, min(1.0, position))
        if p < 0.78:
            return 0.30 + 0.62 * (p / 0.78) ** 0.85
        return 0.92 - 0.28 * ((p - 0.78) / 0.22)

    def _pair_score(self, a: TrackAnalysis | None, b: TrackAnalysis | None, target_energy: float, adventurous: float) -> float:
        plan = self.transition(a, b)
        target = 0.55 if not b else max(0.0, min(1.0, 1.0 - abs(b.energy - target_energy)))
        # Adventure reduces the penalty for timbral distance / imperfect keys,
        # while still keeping transition mechanics sane.
        adventure = max(0.0, min(1.0, adventurous))
        return (0.62 + 0.20 * (1.0 - adventure)) * plan.score + (0.28 * target) + adventure * 0.10 * (1.0 - plan.key_compatibility)

    def plan_order(
        self,
        tracks: list[dict[str, Any]],
        path_for: Callable[[dict[str, Any]], Path | None],
        start_index: int = 0,
        end_index: int | None = None,
        adventurous: float = 0.28,
        analyse_missing: bool = True,
    ) -> dict[str, Any]:
        if not tracks:
            return {"tracks": [], "analysed": 0, "metadata_only": 0, "transitions": []}

        analyses: list[TrackAnalysis | None] = []
        analysed = 0
        for track in tracks:
            path = path_for(track)
            feature = None
            if path is not None and Path(path).exists():
                feature = self.analysis_for(path) if analyse_missing else self.cached_analysis_for(path)
            analyses.append(feature)
            if feature is not None:
                analysed += 1

        start_index = max(0, min(len(tracks) - 1, int(start_index)))
        if end_index is not None:
            end_index = max(0, min(len(tracks) - 1, int(end_index)))
            if end_index == start_index and len(tracks) > 1:
                end_index = None
        remaining = set(range(len(tracks)))
        order = [start_index]
        remaining.remove(start_index)

        while remaining:
            # Reserve an optional landing track until the final step.  Mind uses
            # this for a transparent peak-end rule while Flow still optimises
            # the musical path leading into it.
            if end_index is not None and end_index in remaining and len(remaining) > 1:
                candidates = remaining - {end_index}
            else:
                candidates = remaining
            current_i = order[-1]
            progress = len(order) / max(1, len(tracks) - 1)
            target_energy = self._target_energy(progress)
            # Metadata-only tracks are not forbidden: they receive neutral
            # compatibility and therefore remain available in a fresh library.
            def candidate_key(i: int) -> tuple[float, int]:
                score = self._pair_score(analyses[current_i], analyses[i], target_energy, adventurous)
                # With no analysis yet, preserve the supplied listening order
                # rather than turning Flow into a disguised random shuffle.
                forward = (i - current_i) % len(tracks)
                if forward == 0:
                    forward = len(tracks)
                return score, -forward

            best_i = max(candidates, key=candidate_key)
            order.append(best_i)
            remaining.remove(best_i)

        ordered_tracks = [dict(tracks[i]) for i in order]
        ordered_analyses = [analyses[i] for i in order]
        transitions: list[dict[str, Any]] = []
        for i in range(len(order) - 1):
            transitions.append(self.transition(ordered_analyses[i], ordered_analyses[i + 1]).as_dict())

        return {
            "tracks": ordered_tracks,
            "analyses": [x.as_dict() if x else None for x in ordered_analyses],
            "analysed": analysed,
            "metadata_only": len(tracks) - analysed,
            "transitions": transitions,
            "analysis_available": self.analysis_available,
        }


__all__ = ["FlowEngine", "TrackAnalysis", "TransitionPlan"]
