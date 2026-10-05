from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


class PlaybackTransitionPlanner:
    """Plan one current->next transition outside the Qt playback hot loop.

    Flow cache lookup fingerprints files and reads SQLite, while provider playback
    resolution may perform database or network work. On NAS-backed or remote
    collections those operations can take far longer than a 100 ms playback
    tick, so this adapter delegates both to Melodex's bounded background
    scheduler as two independent tokenized jobs. FlowPlayer receives only an
    in-memory plan and prepared resource, and neither can delay the other.
    """

    def __init__(
        self,
        flow: Any,
        providers: Any,
        path_for: Callable[[dict[str, Any]], Path | None],
        run_async: Callable[..., Any],
        player: Any,
    ) -> None:
        self.flow = flow
        self.providers = providers
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

        def calculate_plan() -> dict[str, Any]:
            a = self.flow.cached_analysis_for(self.path_for(left))
            b = self.flow.cached_analysis_for(self.path_for(right))
            return dict(self.flow.transition(a, b).as_dict())

        def resolve_playback() -> dict[str, Any]:
            return dict(self.providers.resolve(dict(right)))

        generation = int(token)
        self.run_async(
            calculate_plan,
            lambda plan, generation=generation: self.player.apply_transition_plan(
                generation,
                plan,
            ),
            lambda _error, generation=generation: self.player.reject_transition_plan(
                generation,
            ),
            priority="prefetch",
            task_name="playback-transition-plan",
            replace_key="playback-transition-plan",
        )
        self.run_async(
            resolve_playback,
            lambda resolved, generation=generation:
                self.player.apply_transition_resource(generation, resolved),
            lambda _error, generation=generation:
                self.player.reject_transition_resource(generation),
            priority="prefetch",
            task_name="playback-transition-resource",
            replace_key="playback-transition-resource",
        )


__all__ = ["PlaybackTransitionPlanner"]
