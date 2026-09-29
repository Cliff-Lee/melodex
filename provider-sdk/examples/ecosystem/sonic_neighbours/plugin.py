from __future__ import annotations

import json
import math
import sys


def _clamp(value):
    return max(0.0, min(1.0, float(value)))


def _bpm(a, b):
    aa, bb = float(a or 0), float(b or 0)
    if aa <= 0 or bb <= 0:
        return 0.45
    ratios = [bb / aa, (bb * 0.5) / aa, (bb * 2.0) / aa]
    diff = min(abs(math.log(max(1e-6, ratio), 2.0)) for ratio in ratios)
    return _clamp(math.exp(-9.0 * diff * diff))


def _key(a, b):
    if int(a.get("key_pc", -1)) < 0 or int(b.get("key_pc", -1)) < 0:
        return 0.5
    d = (int(b["key_pc"]) - int(a["key_pc"])) % 12
    am, bm = str(a.get("key_mode") or ""), str(b.get("key_mode") or "")
    if d == 0:
        return 1.0 if am == bm else 0.92
    if am != bm and d in {3, 9}:
        return 0.90
    if d in {5, 7}:
        return 0.84
    if d in {2, 10}:
        return 0.66
    if d in {1, 11}:
        return 0.48
    return 0.35


def _near(a, b, scale):
    return _clamp(math.exp(-abs(float(a or 0) - float(b or 0)) / max(1e-6, scale)))


def _timbre(a, b):
    aa, bb = float(a or 0), float(b or 0)
    if aa <= 0 or bb <= 0:
        return 0.5
    return _clamp(math.exp(-1.8 * abs(math.log((bb + 120.0) / (aa + 120.0)))))


def _score(seed, candidate, adventure):
    sa, ca = seed.get("analysis"), candidate.get("analysis")
    if not isinstance(sa, dict) or not isinstance(ca, dict):
        return None
    energy = _near(sa.get("energy"), ca.get("energy"), 0.22)
    tempo = _bpm(sa.get("bpm"), ca.get("bpm"))
    key = _key(sa, ca)
    timbre = _timbre(sa.get("spectral_centroid"), ca.get("spectral_centroid"))
    onset = _near(sa.get("onset_density"), ca.get("onset_density"), 0.12)
    mix = (
        _near(sa.get("intro_mixability"), ca.get("intro_mixability"), 0.35)
        + _near(sa.get("outro_mixability"), ca.get("outro_mixability"), 0.35)
    ) / 2.0
    base = 0.27 * energy + 0.20 * timbre + 0.18 * tempo + 0.16 * key + 0.10 * onset + 0.09 * mix

    # Higher adventure allows a little more timbral/tonal distance while still
    # keeping energy and rhythmic character recognisable.
    adventure = _clamp(adventure)
    novelty = 0.5 * (1.0 - key) + 0.5 * (1.0 - timbre)
    total = _clamp(base + adventure * 0.08 * novelty)

    parts = sorted(
        [
            (energy, "similar energy", "energy"),
            (tempo, "compatible tempo", "tempo"),
            (key, "nearby key", "harmonic"),
            (timbre, "similar timbre", "timbre"),
            (onset, "similar rhythmic density", "rhythm"),
        ],
        reverse=True,
    )
    reasons = [label for value, label, _badge in parts[:2] if value >= 0.62]
    badges = [badge for value, _label, badge in parts[:3] if value >= 0.70]
    return total, " · ".join(reasons or ["closest analysed neighbour"]), badges


def suggest(params):
    intent = str(params.get("intent") or "")
    if intent != "similar":
        return {"schema_version":"0.1","capability":"library_suggestions","intent":intent,"suggestions":[]}
    tracks = [x for x in list(params.get("tracks") or []) if isinstance(x, dict)]
    by_ref = {str(x.get("ref") or ""): x for x in tracks}
    seeds = [str(x) for x in list(params.get("seed_refs") or []) if str(x)]
    seed = by_ref.get(seeds[0]) if seeds else None
    if not seed or not isinstance(seed.get("analysis"), dict):
        return {"schema_version":"0.1","capability":"library_suggestions","intent":intent,"suggestions":[]}

    rows = []
    for candidate in tracks:
        ref = str(candidate.get("ref") or "")
        if not ref or ref in seeds:
            continue
        taste = candidate.get("taste") if isinstance(candidate.get("taste"), dict) else {}
        if int(taste.get("dislikes") or 0) > 0:
            continue
        scored = _score(seed, candidate, params.get("adventure") or 0.35)
        if scored is None:
            continue
        score, reason, badges = scored
        rows.append({"ref":ref,"score":score,"reason":reason,"badges":badges})
    rows.sort(key=lambda row: (-float(row["score"]), row["ref"]))
    return {
        "schema_version":"0.1","capability":"library_suggestions","intent":intent,
        "suggestions":rows[:max(1, min(50, int(params.get("limit") or 12)))]
    }


def respond(request):
    if request.get("method") == "library.suggest":
        return suggest(request.get("params") or {})
    raise RuntimeError("unsupported method")


def run_jsonrpc():
    for line in sys.stdin:
        if not line.strip():
            continue
        request = None
        try:
            request = json.loads(line)
            payload = {"jsonrpc":"2.0","id":request.get("id"),"result":respond(request)}
        except Exception as exc:
            payload = {"jsonrpc":"2.0","id":request.get("id") if isinstance(request,dict) else None,"error":{"code":-32000,"message":str(exc)}}
        print(json.dumps(payload, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    run_jsonrpc()
