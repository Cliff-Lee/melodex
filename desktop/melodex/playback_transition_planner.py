from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


class PlaybackTransitionPlanner:
    """Plan one current->next transition outside the Qt playback hot loop.

    Flow cache lookup fingerprints files and reads SQLite. On NAS-backed
    collections those operations can take far longer than a 100 ms playback
    tick, so this adapter always delegates them to Melodex's bounded background
    scheduler. FlowPlayer only receives an already-computed in-memory plan.
    """

    def __init__(
        self,
        flow: Any,
        path_for: Callable[[dict[str, Any]], Path | None],
        run_async: Callable[..., Any],
        player: Any,
    ) -> None:
        self.flow = flow
        self.path_for = path_for
        self.run_async = run_async
        self.player = player
        player.transitionPlanRequested.connect(self.request)

    def request(
        self,
        token: int,
        current: object,
        upcoming: object,
    ) -> None:
        left = dict(current or {}) if isinstance(current, dict) else {}
        right = dict(upcoming or {}) if isinstance(upcoming, dict) else {}
        if not left or not right:
            self.player.reject_transition_plan(int(token))
            return

        def calculate() -> dict[str, Any]:
            a = self.flow.cached_analysis_for(self.path_for(left))
            b = self.flow.cached_analysis_for(self.path_for(right))
            return dict(self.flow.transition(a, b).as_dict())

        self.run_async(
            calculate,
            lambda plan, generation=int(token): self.player.apply_transition_plan(
                generation,
                plan,
            ),
            lambda _error, generation=int(token): self.player.reject_transition_plan(
                generation,
            ),
            priority="prefetch",
            task_name="playback-transition-plan",
            replace_key="playback-transition-plan",
        )


__all__ = ["PlaybackTransitionPlanner"]
