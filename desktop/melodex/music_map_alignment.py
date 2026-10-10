from __future__ import annotations

"""Conservative visual alignment of successive Music Map projections.

PCA projections are sign/axis ambiguous. Newly analysed tracks can otherwise
mirror or rotate an otherwise familiar music landscape. This helper aligns
*display coordinates only*; audio features, identities and pathfinder edges
are never modified.
"""

from math import isfinite
from typing import Mapping


def align_projection(
    current: Mapping[str, tuple[float, float]],
    previous: Mapping[str, tuple[float, float]],
    *,
    minimum_shared: int = 8,
    minimum_overlap: float = 0.75,
) -> dict[str, tuple[float, float]]:
    """Align two normalized 2-D coordinate maps when they mostly overlap.

    Restricts alignment to eight rigid axis orientations, one uniform scale
    bounded to 15%, and a small translation. Rejects transformations that
    do not meaningfully beat retaining the new projection unchanged.
    """
    rows = {str(ref): (float(x), float(y)) for ref, (x, y) in current.items()}
    shared = sorted(set(rows) & set(previous))
    if (len(shared) < minimum_shared or
            len(shared) / max(1, len(previous)) < minimum_overlap):
        return rows

    new = [rows[r] for r in shared]
    old = [tuple(map(float, previous[r])) for r in shared]
    if not all(isfinite(v) for point in new + old for v in point):
        return rows

    old_mean = (
        sum(p[0] for p in old) / len(old),
        sum(p[1] for p in old) / len(old),
    )
    variance = sum(
        (p[0] - old_mean[0]) ** 2 + (p[1] - old_mean[1]) ** 2
        for p in old
    )
    if variance < 1e-4:
        return rows

    original_error = sum(
        (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2
        for a, b in zip(new, old)
    )

    best_error = original_error
    best_params = None
    for swap in (False, True):
        for sx in (-1.0, 1.0):
            for sy in (-1.0, 1.0):
                rotated = [(sx * (y if swap else x),
                            sy * (x if swap else y)) for x, y in new]
                mean = (
                    sum(p[0] for p in rotated) / len(rotated),
                    sum(p[1] for p in rotated) / len(rotated),
                )
                centered = [(p[0] - mean[0], p[1] - mean[1]) for p in rotated]
                old_centered = [(p[0] - old_mean[0], p[1] - old_mean[1]) for p in old]
                denominator = sum(x*x + y*y for x, y in centered)
                if denominator < 1e-8:
                    continue
                numerator = sum(
                    a[0]*b[0] + a[1]*b[1] for a, b in zip(centered, old_centered)
                )
                scale = max(0.85, min(1.15, numerator / denominator))
                tx = max(-0.25, min(0.25, old_mean[0] - scale*mean[0]))
                ty = max(-0.25, min(0.25, old_mean[1] - scale*mean[1]))
                error = sum(
                    (scale*x + tx - target[0])**2
                    + (scale*y + ty - target[1])**2
                    for (x,y), target in zip(rotated, old)
                )
                if error < best_error:
                    best_error = error
                    best_params = (swap, sx, sy, scale, tx, ty)

    if best_params is None or best_error >= original_error * 0.85:
        return rows

    swap, sx, sy, scale, tx, ty = best_params
    result = {}
    for ref, (x, y) in rows.items():
        ax = scale * sx * (y if swap else x) + tx
        ay = scale * sy * (x if swap else y) + ty
        result[ref] = (max(-1.0, min(1.0, ax)),
                       max(-1.0, min(1.0, ay)))
    return result


__all__ = ["align_projection"]
