from __future__ import annotations

import json
import math
import sys


def _clamp(value):
    return max(0.0, min(1.0, float(value)))


def _spacing(days):
    if days is None:
        return 0.0
    days = max(0.0, float(days))
    if days < 7.0:
        return 0.0
    # Broad log-normal-shaped return window centred around ~75 days. The wide
    # curve means a loved track can remain rediscoverable for many months.
    centre = math.log(76.0)
    width = 1.35
    return _clamp(math.exp(-((math.log(days + 1.0) - centre) ** 2) / width))


def _score(track):
    taste = track.get("taste") if isinstance(track.get("taste"), dict) else {}
    if int(taste.get("dislikes") or 0) > 0:
        return None
    plays = max(0, int(taste.get("plays") or 0))
    if plays <= 0:
        return None
    days = taste.get("days_since_last_played")
    if days is not None and float(days) < 7.0:
        return None

    loves = 1.0 if int(taste.get("loves") or 0) > 0 else 0.0
    keeps = _clamp(int(taste.get("keeps") or 0) / 3.0)
    completion = _clamp(taste.get("completion_rate") or 0.0)
    skip = _clamp(taste.get("skip_rate") or 0.0)
    familiarity = _clamp(math.log1p(plays) / math.log(25.0))
    spacing = _spacing(days)

    positive = 0.30 * loves + 0.18 * keeps + 0.23 * completion + 0.10 * familiarity
    score = _clamp(0.54 * positive + 0.46 * spacing - 0.35 * skip)
    if score < 0.18:
        return None

    reason_bits = []
    badges = []
    if loves:
        reason_bits.append("loved")
        badges.append("loved")
    elif keeps >= 0.34:
        reason_bits.append("kept before")
        badges.append("kept")
    if completion >= 0.75:
        reason_bits.append("usually finished")
        badges.append("high completion")
    if days is not None:
        d = int(round(float(days)))
        reason_bits.append(f"{d} days since last play")
        if d >= 30:
            badges.append("ready to return")
    return score, " · ".join(reason_bits or ["worth another listen"]), badges[:4]


def suggest(params):
    intent = str(params.get("intent") or "")
    if intent != "rediscover":
        return {"schema_version":"0.1","capability":"library_suggestions","intent":intent,"suggestions":[]}
    rows = []
    for track in list(params.get("tracks") or []):
        if not isinstance(track, dict):
            continue
        ref = str(track.get("ref") or "")
        if not ref:
            continue
        scored = _score(track)
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
