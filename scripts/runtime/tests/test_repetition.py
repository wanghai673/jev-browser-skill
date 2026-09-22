from copy import deepcopy

import pytest

from jev_ultrafast.repetition import RepetitionGuard
from jev_ultrafast.runner import run_task


def page():
    return {
        "url": "https://example.com/search",
        "title": "Search",
        "text": "Search",
        "tab_id": "tab1",
        "document_id": 1,
        "fingerprint": "unchanged",
        "scroll": {"y": 0, "height": 900},
        "actions": [{"id": "e1", "node": 1, "kind": "click", "label": "Open search", "value": "", "rect": {"x": 10}}],
    }


def test_third_unchanged_click_stops_despite_geometry_jitter():
    guard = RepetitionGuard()
    before = page()
    for index in range(3):
        after = deepcopy(before)
        after["actions"][0]["rect"]["x"] += 0.1
        result = guard.record(before["actions"][0], before, after)
        assert bool(result) == (index == 2)
        before = after
    assert result["count"] == 3


@pytest.mark.parametrize("change", ["text", "url", "tab_id", "document_id", "value", "scroll", "checked"])
def test_progress_resets_streak(change):
    guard, before = RepetitionGuard(), page()
    action = before["actions"][0]
    guard.record(action, before, before)
    guard.record(action, before, before)
    after = deepcopy(before)
    if change in {"value", "checked"}:
        after["actions"][0][change] = "new"
    elif change == "scroll":
        after["scroll"]["y"] = 100
    else:
        after[change] = "new"
    assert guard.record(action, before, after) is None
    assert guard.count == 0


def test_async_progress_between_actions_resets_streak():
    guard, before = RepetitionGuard(), page()
    action = before["actions"][0]
    for _ in range(2):
        guard.record(action, before, before)
    before["text"] = "Loaded results"
    assert guard.record(action, before, before) is None
    assert guard.count == 1


def test_different_control_and_input_do_not_share_streak():
    guard, before = RepetitionGuard(), page()
    action = before["actions"][0]
    guard.record(action, before, before)
    guard.record(action, before, before)
    assert guard.record({**action, "node": 2}, before, before) is None
    assert guard.count == 1
    for literal in ("first", "second", "third"):
        assert guard.record({**action, "kind": "fill"}, before, before, literal) is None
        assert guard.count == 1


def test_wait_does_not_trigger_guard():
    guard, before = RepetitionGuard(), page()
    for _ in range(10):
        assert guard.record({"id": "wait", "kind": "wait", "label": "Wait"}, before, before) is None


def test_playback_clock_is_ignored_but_play_pause_is_progress():
    guard, before = RepetitionGuard(), page()
    before["media"] = [{"current_time": 10, "paused": False}]
    action = before["actions"][0]
    for _ in range(3):
        after = deepcopy(before)
        after["media"][0]["current_time"] += 1
        result = guard.record(action, before, after)
        before = after
    assert result["count"] == 3
    after = deepcopy(before)
    after["media"][0]["paused"] = True
    assert guard.record(action, before, after) is None
    assert guard.count == 0


def test_runner_excludes_after_three_clicks_and_continues(monkeypatch):
    class Browser:
        issues = []

        def __init__(self, *args, **kwargs):
            self.clicks = 0
            self.detached = False
            self.finished = False

        def observe(self, **kwargs):
            state = page()
            state["actions"].append({"id": "e2", "node": 2, "kind": "click", "label": "Alternative"})
            if self.finished:
                state["text"] = "Results loaded"
            return state

        def fresh(self, page):
            return True

        def act(self, action, *args, **kwargs):
            self.clicks += 1
            self.finished = action["id"] == "e2"

        def detach(self):
            self.detached = True

    browser = Browser()
    monkeypatch.setattr("jev_ultrafast.runner.Browser", lambda *a, **kw: browser)
    monkeypatch.setattr(
        "jev_ultrafast.agent.choose",
        lambda state, *a: {
            "choice": "DONE" if state["text"] == "Results loaded" else state["actions"][0]["id"],
            "probabilities": {"e1": 1, "e2": 1},
            "confidence": 1,
            "latency_ms": 0,
            "operation": "CLICK",
            "target": "1",
            "usage": {},
        },
    )
    result = run_task("https://example.com", "Search", max_actions=20)
    assert result["status"] == "done"
    assert result["stop_choice"] == "DONE"
    assert result["excluded_actions"][0]["code"] == "repeated_action_no_progress"
    assert result["action_count"] == browser.clicks == 4
    assert browser.finished
    assert result["page"]["url"] == page()["url"]
    assert result["timing"]["counters"]["repeated_action_exclusions"] == 1
    assert browser.detached


def test_exclusion_survives_renumbering_and_streak_reset_but_is_page_scoped():
    guard, before = RepetitionGuard(), page()
    action = before["actions"][0]
    for _ in range(3):
        guard.record(action, before, before)
    guard.reset()
    after = deepcopy(before)
    after["actions"][0]["id"] = "e99"
    after["actions"].append({**action, "id": "e2", "node": 2})
    assert [a["id"] for a in guard.available_page(after)["actions"]] == ["e2"]
    assert len(after["actions"]) == 2
    after["document_id"] = 2
    assert len(guard.available_page(after)["actions"]) == 2
    assert len(RepetitionGuard().available_page(before)["actions"]) == 1
