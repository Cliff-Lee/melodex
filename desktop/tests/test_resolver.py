from types import SimpleNamespace

from melodex.resolver import UniversalResolver


class FakeProvider:
    def __init__(self, pid, rows, capabilities=None):
        self.pid = pid
        self.rows = rows
        self.info = SimpleNamespace(
            id=pid,
            capabilities=list(capabilities or ["search", "playback"]),
        )
        self.search_calls = 0
        self.resolve_calls = 0
    def search(self, query, limit=50):
        self.search_calls += 1
        return [dict(x) for x in self.rows[:limit]]
    def resolve(self, track):
        self.resolve_calls += 1
        out = dict(track)
        out.setdefault("stream_url", f"https://example.invalid/{self.pid}/{out.get('track_id')}")
        return out


class Manager:
    def __init__(self, providers):
        self.providers = providers
        self.settings = {}
        self.saved = 0
    def save(self):
        self.saved += 1


def test_exact_match_beats_high_priority_bad_variant():
    m = Manager({
        "first": FakeProvider("first", [{"provider_id":"first","track_id":"1","artist":"Massive Attack","title":"Teardrop (Live)","album":"Live"}]),
        "second": FakeProvider("second", [{"provider_id":"second","track_id":"2","artist":"Massive Attack","title":"Teardrop","album":"Mezzanine"}]),
    })
    r = UniversalResolver(m)
    out = r.resolve({"artist":"Massive Attack","title":"Teardrop","album":"Mezzanine"})
    assert out["provider_id"] == "second"
    assert out["track_id"] == "2"


def test_priority_breaks_near_tie():
    m = Manager({
        "a": FakeProvider("a", [{"provider_id":"a","track_id":"1","artist":"Autechre","title":"Bike"}]),
        "b": FakeProvider("b", [{"provider_id":"b","track_id":"2","artist":"Autechre","title":"Bike"}]),
    })
    m.settings["provider_priority"] = ["b", "a"]
    out = UniversalResolver(m).resolve({"artist":"Autechre","title":"Bike"})
    assert out["provider_id"] == "b"


def test_blocklist_skips_only_bad_candidate():
    m = Manager({
        "a": FakeProvider("a", [{"provider_id":"a","track_id":"1","artist":"Boards of Canada","title":"Roygbiv"}]),
        "b": FakeProvider("b", [{"provider_id":"b","track_id":"2","artist":"Boards of Canada","title":"Roygbiv"}]),
    })
    r = UniversalResolver(m)
    target = {"artist":"Boards of Canada","title":"Roygbiv"}
    r.block(target, m.providers["a"].rows[0])
    out = r.resolve(target)
    assert out["provider_id"] == "b"
    assert m.saved == 1


def test_direct_provider_identity_stays_direct():
    m = Manager({"a": FakeProvider("a", [])})
    r = UniversalResolver(m)
    out = r.resolve({"provider_id":"a","track_id":"123","artist":"X","title":"Y"})
    assert out["provider_id"] == "a"
    assert out["_resolution"]["mode"] == "direct"


def test_resolve_many_keeps_failures_separate():
    m = Manager({"a": FakeProvider("a", [{"provider_id":"a","track_id":"1","artist":"One","title":"Found"}])})
    r = UniversalResolver(m)
    result = r.resolve_many([
        {"artist":"One","title":"Found"},
        {"artist":"Nobody","title":"Missing"},
    ])
    assert len(result["tracks"]) == 1
    assert len(result["unresolved"]) == 1


def test_resolver_skips_recommendation_only_provider():
    recommend = FakeProvider(
        "recommend",
        [{"provider_id":"recommend","track_id":"r1","artist":"Massive Attack","title":"Teardrop"}],
        capabilities=["recommendations"],
    )
    playable = FakeProvider(
        "playable",
        [{"provider_id":"playable","track_id":"p1","artist":"Massive Attack","title":"Teardrop"}],
    )
    m = Manager({"recommend": recommend, "playable": playable})
    out = UniversalResolver(m).resolve({"artist":"Massive Attack","title":"Teardrop"})
    assert out["provider_id"] == "playable"
    assert recommend.search_calls == 0
    assert playable.search_calls >= 1


def test_recommendation_result_resolves_through_playback_provider_without_direct_call():
    recommend = FakeProvider(
        "recommend",
        [],
        capabilities=["recommendations"],
    )
    playable = FakeProvider(
        "playable",
        [{"provider_id":"playable","track_id":"p1","artist":"Portishead","title":"Roads"}],
    )
    m = Manager({"recommend": recommend, "playable": playable})
    out = UniversalResolver(m).resolve({
        "provider_id": "recommend",
        "track_id": "rec-1",
        "artist": "Portishead",
        "title": "Roads",
        "metadata": {"playable": False},
    })
    assert out["provider_id"] == "playable"
    assert recommend.resolve_calls == 0
    assert recommend.search_calls == 0
    assert playable.resolve_calls == 1


def test_direct_provider_id_identity_stays_direct_without_track_id():
    class IdentityDroppingProvider(FakeProvider):
        def resolve(self, track):
            self.resolve_calls += 1
            return {"stream_url": "https://example.invalid/fresh"}

    provider = IdentityDroppingProvider("a", [])
    manager = Manager({"a": provider})
    out = UniversalResolver(manager).resolve({
        "provider_id": "a",
        "id": "provider-track-123",
        "artist": "X",
        "title": "Y",
    })
    assert out["provider_id"] == "a"
    assert out["id"] == "provider-track-123"
    assert out["_resolution"]["mode"] == "direct"
    assert provider.resolve_calls == 1
