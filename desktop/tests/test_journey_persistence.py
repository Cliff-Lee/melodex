from __future__ import annotations

from pathlib import Path

from melodex.user_state import UserState


def test_journey_recipe_and_run_history_persist(tmp_path: Path):
    state = UserState(tmp_path / "taste.sqlite3")
    try:
        recipe = {
            "melodex_journey": 1,
            "name": "Arc",
            "description": "",
            "routing_mode": "balanced",
            "stages": [{"type": "constraint", "constraint": "calm", "label": "Calm"}],
        }
        state.save_journey_recipe("recipe-1", "Arc", "", recipe)
        rows = state.journey_recipes()
        assert rows[0]["id"] == "recipe-1"
        assert rows[0]["payload"]["name"] == "Arc"
        assert state.get_journey_recipe("recipe-1")["payload"] == recipe

        original = {"tracks": [{"display": "A — One"}, {"display": "B — Two"}]}
        final = {"tracks": [{"display": "A — One"}, {"display": "C — Three"}]}
        state.start_journey_run(
            "run-1",
            recipe_id="recipe-1",
            recipe=recipe,
            original_route=original,
        )
        event_id = state.record_journey_event(
            "run-1",
            "steer",
            {"label": "More energy next"},
        )
        assert event_id > 0
        state.finish_journey_run(
            "run-1",
            status="completed",
            final_route=final,
        )

        run = state.journey_runs()[0]
        assert run["id"] == "run-1"
        assert run["status"] == "completed"
        assert run["original_route"] == original
        assert run["final_route"] == final
        events = state.journey_events("run-1")
        assert events[0]["event_type"] == "steer"
        assert events[0]["payload"]["label"] == "More energy next"

        state.delete_journey_recipe("recipe-1")
        assert state.get_journey_recipe("recipe-1") is None
    finally:
        state.close()
