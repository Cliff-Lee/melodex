from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from melodex.playback_transition_planner import PlaybackTransitionPlanner


class FakeSignal:
    def __init__(self):
        self.callback = None

    def connect(self, callback):
        self.callback = callback


class FakePlayer:
    def __init__(self):
        self.transitionPlanRequested = FakeSignal()
        self.applied = []
        self.rejected = []

    def apply_transition_plan(self, token, plan):
        self.applied.append((int(token), dict(plan or {})))
        return True

    def reject_transition_plan(self, token):
        self.rejected.append(int(token))
        return True


class FakeFlow:
    def __init__(self):
        self.lookups = []

    def cached_analysis_for(self, path):
        self.lookups.append(path)
        return {"path": str(path)}

    def transition(self, left, right):
        assert left["path"].endswith("a.flac")
        assert right["path"].endswith("b.flac")
        return SimpleNamespace(as_dict=lambda: {"duration_ms": 7300, "style": "smooth"})


def test_request_only_schedules_work_and_does_not_touch_flow_cache_inline():
    player = FakePlayer()
    flow = FakeFlow()
    scheduled = []

    def run_async(fn, done, on_error, **kwargs):
        scheduled.append((fn, done, on_error, kwargs))

    planner = PlaybackTransitionPlanner(
        flow,
        lambda track: Path(track["local_path"]),
        run_async,
        player,
    )

    planner.request(
        7,
        {"local_path": "/nas/a.flac", "title": "Private A"},
        {"local_path": "/nas/b.flac", "title": "Private B"},
    )

    # This is the P14d contract: signal handling on the Qt thread only queues
    # background work. Filesystem/SQLite-backed Flow lookup has not run yet.
    assert flow.lookups == []
    assert len(scheduled) == 1
    fn, done, _error, kwargs = scheduled[0]
    assert kwargs["priority"] == "prefetch"
    assert kwargs["replace_key"] == "playback-transition-plan"

    plan = fn()
    assert flow.lookups == [Path("/nas/a.flac"), Path("/nas/b.flac")]
    done(plan)
    assert player.applied == [(7, {"duration_ms": 7300, "style": "smooth"})]


def test_planner_rejects_invalid_pair_without_scheduling_io():
    player = FakePlayer()
    flow = FakeFlow()
    scheduled = []

    planner = PlaybackTransitionPlanner(
        flow,
        lambda track: Path(track["local_path"]),
        lambda *args, **kwargs: scheduled.append((args, kwargs)),
        player,
    )

    planner.request(9, {}, {"local_path": "/nas/b.flac"})

    assert scheduled == []
    assert flow.lookups == []
    assert player.rejected == [9]


def test_planner_failure_returns_token_to_player_without_content():
    player = FakePlayer()
    flow = FakeFlow()
    captured = {}

    def run_async(fn, done, on_error, **kwargs):
        captured.update(fn=fn, done=done, on_error=on_error, kwargs=kwargs)

    planner = PlaybackTransitionPlanner(
        flow,
        lambda track: Path(track["local_path"]),
        run_async,
        player,
    )
    planner.request(
        11,
        {"local_path": "/nas/a.flac"},
        {"local_path": "/nas/b.flac"},
    )

    captured["on_error"]("private failure text /nas/a.flac")
    assert player.rejected == [11]
