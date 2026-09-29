from __future__ import annotations

import json
import math
import sys


def _clamp(v):
    return max(0.0, min(1.0, float(v)))


def _near(a, b, scale):
    return _clamp(math.exp(-abs(float(a or 0) - float(b or 0)) / max(1e-6, scale)))


def _bpm(a, b):
    aa, bb = float(a or 0), float(b or 0)
    if aa <= 0 or bb <= 0:
        return 0.45
    ratios = [bb / aa, (bb * .5) / aa, (bb * 2.0) / aa]
    diff = min(abs(math.log(max(1e-6, r), 2.0)) for r in ratios)
    return _clamp(math.exp(-9.0 * diff * diff))


def _key(a, b):
    ap, bp = int(a.get("key_pc", -1)), int(b.get("key_pc", -1))
    if ap < 0 or bp < 0:
        return .5
    d = (bp - ap) % 12
    am, bm = str(a.get("key_mode") or ""), str(b.get("key_mode") or "")
    if d == 0:
        return 1.0 if am == bm else .92
    if am != bm and d in {3, 9}:
        return .90
    if d in {5, 7}:
        return .84
    if d in {2, 10}:
        return .66
    if d in {1, 11}:
        return .48
    return .35


def _timbre(a, b):
    aa, bb = float(a or 0), float(b or 0)
    if aa <= 0 or bb <= 0:
        return .5
    return _clamp(math.exp(-1.8 * abs(math.log((bb + 120.0) / (aa + 120.0)))))


def _pair(a, b):
    tempo = _bpm(a.get("bpm"), b.get("bpm"))
    key = _key(a, b)
    energy = _near(a.get("energy_end", a.get("energy")), b.get("energy_start", b.get("energy")), .28)
    timbre = _timbre(a.get("spectral_centroid"), b.get("spectral_centroid"))
    mix = (
        _clamp(a.get("outro_mixability") or .45)
        + _clamp(b.get("intro_mixability") or .45)
    ) / 2.0
    return _clamp(.23 * tempo + .23 * key + .24 * energy + .17 * timbre + .13 * mix), {
        "tempo": tempo, "key": key, "energy": energy, "timbre": timbre, "mix": mix
    }


def _score(start, candidate, end, adventure):
    a, c, b = start.get("analysis"), candidate.get("analysis"), end.get("analysis")
    if not all(isinstance(x, dict) for x in (a, c, b)):
        return None
    left, lm = _pair(a, c)
    right, rm = _pair(c, b)

    # A bridge should work on both sides; geometric mean punishes a candidate
    # that is excellent on one side and terrible on the other.
    balanced = math.sqrt(max(0.0, left) * max(0.0, right))

    # Reward an energy trajectory that sits between the two endpoints rather
    # than jumping far outside them.
    start_e = float(a.get("energy") or 0)
    end_e = float(b.get("energy") or 0)
    cand_e = float(c.get("energy") or 0)
    lo, hi = sorted((start_e, end_e))
    if lo <= cand_e <= hi:
        trajectory = 1.0
    else:
        trajectory = _near(cand_e, (start_e + end_e) / 2.0, .30)

    adventure = _clamp(adventure)
    score = _clamp(.82 * balanced + .18 * trajectory + adventure * .04 * (1.0 - min(lm["timbre"], rm["timbre"])))

    dimensions = {
        "tempo path": (lm["tempo"] + rm["tempo"]) / 2.0,
        "harmonic path": (lm["key"] + rm["key"]) / 2.0,
        "energy path": (lm["energy"] + rm["energy"]) / 2.0,
        "timbre path": (lm["timbre"] + rm["timbre"]) / 2.0,
    }
    ordered = sorted(((v, k) for k, v in dimensions.items()), reverse=True)
    reason = " · ".join(k for v, k in ordered[:2] if v >= .58) or "balanced two-sided transition"
    badges = [k.replace(" path", "") for v, k in ordered[:3] if v >= .70]
    return score, reason, badges


def suggest(params):
    intent = str(params.get("intent") or "")
    if intent != "bridge":
        return {"schema_version":"0.1","capability":"library_suggestions","intent":intent,"suggestions":[]}
    tracks = [x for x in list(params.get("tracks") or []) if isinstance(x, dict)]
    by_ref = {str(x.get("ref") or ""): x for x in tracks}
    seeds = [str(x) for x in list(params.get("seed_refs") or []) if str(x)]
    if len(seeds) < 2:
        return {"schema_version":"0.1","capability":"library_suggestions","intent":intent,"suggestions":[]}
    start, end = by_ref.get(seeds[0]), by_ref.get(seeds[1])
    if not start or not end:
        return {"schema_version":"0.1","capability":"library_suggestions","intent":intent,"suggestions":[]}

    rows = []
    for candidate in tracks:
        ref = str(candidate.get("ref") or "")
        if not ref or ref in seeds:
            continue
        taste = candidate.get("taste") if isinstance(candidate.get("taste"), dict) else {}
        if int(taste.get("dislikes") or 0) > 0:
            continue
        scored = _score(start, candidate, end, params.get("adventure") or .35)
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
