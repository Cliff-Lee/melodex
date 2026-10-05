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
        self.applied_plans = []
        self.applied_resources = []
        self.rejected_plans = []
        self.rejected_resources = []

    def apply_transition_plan(self, token, plan):
        self.applied_plans.append((int(token), dict(plan or {})))
        return True

    def reject_transition_plan(self, token):
        self.rejected_plans.append(int(token))
        return True

    def apply_transition_resource(self, token, resolved):
        self.applied_resources.append((int(token), dict(resolved or {})))
        return True

    def reject_transition_resource(self, token):
        self.rejected_resources.append(int(token))
        return True


class FakeProviders:
    def __init__(self):
        self.resolutions = []

    def resolve(self, track):
        self.resolutions.append(dict(track))
        return {**dict(track), "local_path": str(track.get("local_path") or "")}


class FakeFlow:
    def __init__(self):
        self.lookups = []

    def cached_analysis_for(self, path):
        self.lookups.append(path)
        return {"path": str(path)}

    def transition(self, left, right):
        assert left["path"].endswith("a.flac")
        assert right["path"].endswith("b.flac")
        return SimpleNamespace(
            as_dict=lambda: {"duration_ms": 7300, "style": "smooth"}
        )


def _planner():
    player = FakePlayer()
    flow = FakeFlow()
    providers = FakeProviders()
    scheduled = []

    def run_async(fn, done, on_error, **kwargs):
        scheduled.append((fn, done, on_error, kwargs))

    planner = PlaybackTransitionPlanner(
        flow,
        providers,
        lambda track: Path(track["local_path"]),
        run_async,
        player,
    )
    return planner, player, flow, providers, scheduled


def test_request_only_schedules_work_and_performs_no_io_inline():
    planner, player, flow, providers, scheduled = _planner()

    planner.request(
        7,
        {"local_path": "/nas/a.flac", "title": "Private A"},
        {"local_path": "/nas/b.flac", "title": "Private B"},
    )

    # The Qt-side request handler only queues work. Neither NAS-backed Flow
    # lookup nor provider resolution has happened yet.
    assert flow.lookups == []
    assert providers.resolutions == []
    assert len(scheduled) == 2
    assert {job[3]["replace_key"] for job in scheduled} == {
        "playback-transition-plan",
        "playback-transition-resource",
    }

    jobs = {job[3]["replace_key"]: job for job in scheduled}
    plan_fn, plan_done, _plan_error, plan_kwargs = jobs[
        "playback-transition-plan"
    ]
    resource_fn, resource_done, _resource_error, resource_kwargs = jobs[
        "playback-transition-resource"
    ]
    assert plan_kwargs["priority"] == "prefetch"
    assert resource_kwargs["priority"] == "prefetch"

    plan = plan_fn()
    assert flow.lookups == [Path("/nas/a.flac"), Path("/nas/b.flac")]
    assert providers.resolutions == []
    plan_done(plan)
    assert player.applied_plans == [
        (7, {"duration_ms": 7300, "style": "smooth"})
    ]

    resolved = resource_fn()
    assert providers.resolutions == [
        {"local_path": "/nas/b.flac", "title": "Private B"}
    ]
    resource_done(resolved)
    assert player.applied_resources == [
        (7, {"local_path": "/nas/b.flac", "title": "Private B"})
    ]


def test_slow_nas_analysis_cannot_delay_playback_resource_resolution():
    planner, player, flow, providers, scheduled = _planner()
    planner.request(
        8,
        {"local_path": "/nas/a.flac"},
        {"local_path": "/nas/b.flac"},
    )

    jobs = {job[3]["replace_key"]: job for job in scheduled}
    resource_fn, resource_done, _error, _kwargs = jobs[
        "playback-transition-resource"
    ]

    # Execute only the playback job. It is independent from the Flow/NAS job.
    resolved = resource_fn()
    resource_done(resolved)

    assert flow.lookups == []
    assert providers.resolutions == [{"local_path": "/nas/b.flac"}]
    assert player.applied_resources == [
        (8, {"local_path": "/nas/b.flac"})
    ]


def test_planner_rejects_invalid_pair_without_scheduling_io():
    planner, player, flow, providers, scheduled = _planner()

    planner.request(9, {}, {"local_path": "/nas/b.flac"})

    assert scheduled == []
    assert flow.lookups == []
    assert providers.resolutions == []
    assert player.rejected_plans == [9]
    assert player.rejected_resources == []


def test_plan_and_resource_failures_are_reported_separately():
    planner, player, _flow, _providers, scheduled = _planner()
    planner.request(
        11,
        {"local_path": "/nas/a.flac"},
        {"local_path": "/nas/b.flac"},
    )

    jobs = {job[3]["replace_key"]: job for job in scheduled}
    jobs["playback-transition-plan"][2]("private plan failure")
    jobs["playback-transition-resource"][2]("private provider failure")

    assert player.rejected_plans == [11]
    assert player.rejected_resources == [11]
