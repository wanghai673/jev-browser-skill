"""Task-local contracts and evidence. Predicates read snapshots, never execute site code."""

import copy
import math
from urllib.parse import urlsplit

from .direct import valid_url


def _text(value, name, limit=2000):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f"{name} must be nonempty text, at most {limit} characters")
    return value


def validate_task(value):
    if not isinstance(value, dict) or set(value) - {
        "rules",
        "boundaries",
        "acceptance",
        "items",
        "inputs",
        "input_candidates",
        "budget",
    }:
        raise ValueError("Invalid task contract fields")
    task = copy.deepcopy(value)
    for key in ("rules", "boundaries", "acceptance"):
        values = task.setdefault(key, [])
        if not isinstance(values, list) or len(values) > 30:
            raise ValueError(f"{key} must be a list of at most 30 instructions")
        for text in values:
            _text(text, key)
    items = task.setdefault("items", [])
    if not isinstance(items, list) or len(items) > 100:
        raise ValueError("items must be a list of at most 100 objects")
    ids = set()
    for item in items:
        if not isinstance(item, dict) or set(item) - {"id", "goal", "url", "checks"}:
            raise ValueError("Invalid item fields")
        identifier = _text(item.get("id"), "item id", 100)
        if identifier in ids:
            raise ValueError("Duplicate item id")
        ids.add(identifier)
        _text(item.get("goal"), "item goal")
        item["url"] = valid_url(_text(item.get("url"), "item url"))
        checks = item.setdefault("checks", [])
        if not isinstance(checks, list) or len(checks) > 20:
            raise ValueError("checks must be a list of at most 20 predicates")
        for check in checks:
            if not isinstance(check, dict):
                raise ValueError("Invalid check")
            kind = check.get("kind")
            fields = {
                "text_contains": {"kind", "value"},
                "title_equals": {"kind", "value"},
                "field_equals": {"kind", "label", "value"},
                "media_advancing": {"kind"},
            }.get(kind)
            if fields is None or set(check) != fields:
                raise ValueError("Unsupported check or fields")
            if "value" in check:
                _text(check["value"], "check value")
            if "label" in check:
                _text(check["label"], "check label")
    inputs = task.setdefault("inputs", [])
    if not isinstance(inputs, list) or len(inputs) > 100:
        raise ValueError("inputs must be a list of at most 100 exact field bindings")
    bindings = set()
    for binding in inputs:
        if not isinstance(binding, dict) or set(binding) != {"url", "label", "value"}:
            raise ValueError("Inputs require exactly url, label and value")
        binding["url"] = valid_url(_text(binding["url"], "input url"))
        _text(binding["label"], "input label")
        _text(binding["value"], "input value")
        key = (binding["url"], binding["label"])
        if key in bindings:
            raise ValueError("Duplicate input binding")
        bindings.add(key)
    candidates = task.setdefault("input_candidates", [])
    if not isinstance(candidates, list) or len(candidates) > 20:
        raise ValueError("input_candidates must contain at most 20 prepared values")
    candidate_ids = set()
    for candidate in candidates:
        if not isinstance(candidate, dict) or set(candidate) - {"id", "value", "purpose", "origins"}:
            raise ValueError("Invalid input candidate fields")
        identifier = _text(candidate.get("id"), "candidate id", 100)
        if identifier in candidate_ids or identifier == "NONE":
            raise ValueError("Duplicate or reserved input candidate id")
        candidate_ids.add(identifier)
        _text(candidate.get("value"), "candidate value")
        _text(candidate.get("purpose"), "candidate purpose", 500)
        origins = candidate.setdefault("origins", [])
        if not isinstance(origins, list) or len(origins) > 10:
            raise ValueError("Candidate origins must be a list of at most 10 exact origins")
        for origin in origins:
            _text(origin, "candidate origin", 500)
            parts = urlsplit(origin)
            if (
                parts.scheme not in {"https", "http"}
                or not parts.hostname
                or parts.username
                or parts.password
                or parts.path
                or parts.query
                or parts.fragment
            ):
                raise ValueError("Candidate origins must be exact http(s) origins without a path")
    budget = task.setdefault("budget", {})
    if not isinstance(budget, dict) or set(budget) - {"max_actions", "max_seconds"}:
        raise ValueError("Invalid task budget")
    actions, seconds = budget.setdefault("max_actions", 200), budget.setdefault("max_seconds", 300)
    if type(actions) is not int or not 1 <= actions <= 1000:
        raise ValueError("Task max_actions must be 1–1000")
    if type(seconds) not in (int, float) or not math.isfinite(seconds) or not 1 <= seconds <= 3600:
        raise ValueError("Task max_seconds must be 1–3600")
    return task


class Workflow:
    def __init__(self, contract=None):
        self.contract = validate_task({} if contract is None else contract)
        self.items = {
            item["id"]: {**copy.deepcopy(item), "status": "pending", "evidence": []} for item in self.contract["items"]
        }
        self.previous_media = {}
        self.verified_events = 0

    def observe(self, page, revision):
        """Update only items scoped to this exact page. Retain other pages' evidence."""
        url = page["url"]
        media_key = (page.get("tab_id"), url, page.get("document_id"))
        previous = self.previous_media.get(media_key, [])
        media = page.get("media", [])
        for item in self.items.values():
            if item["url"] != url or not item["checks"]:
                continue
            evidence = []
            for check in item["checks"]:
                kind, expected = check["kind"], check.get("value")
                if kind == "text_contains":
                    passed, actual = expected in page.get("text", ""), expected
                elif kind == "title_equals":
                    actual = page.get("title", "")
                    passed = actual == expected
                elif kind == "field_equals":
                    matches = {
                        a.get("node", a["id"]): a.get("current_value", a.get("value", ""))
                        for a in page.get("actions", [])
                        if a.get("kind") in {"fill", "select"} and a.get("label", "").split(" → ")[0] == check["label"]
                    }
                    actual = next(iter(matches.values())) if len(matches) == 1 else None
                    passed = actual == expected
                else:
                    pairs = [
                        (old, now)
                        for old in previous
                        for now in media
                        if now.get("src")
                        and old.get("src") == now.get("src")
                        and old.get("node") == now.get("node")
                        and now.get("playing")
                        and old.get("playing")
                        and now.get("current_time", 0) > old.get("current_time", 0)
                    ]
                    passed = bool(pairs)
                    actual = [{"before": p[0]["current_time"], "after": p[1]["current_time"]} for p in pairs]
                evidence.append(
                    {
                        "kind": kind,
                        "passed": passed,
                        "actual": actual if passed else None,
                        "url": url,
                        "revision": revision,
                        "source": "page_observation",
                    }
                )
            verified = all(e["passed"] for e in evidence)
            if verified and item["status"] != "verified":
                self.verified_events += 1
            item.update(status="verified" if verified else "pending", evidence=evidence)
        self.previous_media[media_key] = copy.deepcopy(media)

    def checkpoint(self, identifier, status, evidence, page, revision):
        if identifier not in self.items or status not in {"reviewed", "blocked", "pending"}:
            raise ValueError("Checkpoint requires an existing item and reviewed/blocked/pending status")
        item = self.items[identifier]
        if status == "reviewed" and item["checks"]:
            raise ValueError("A manual checkpoint cannot override configured page checks")
        if item["url"] != page["url"]:
            raise ValueError("Observe the item's exact page before recording a checkpoint")
        _text(evidence, "checkpoint evidence")
        item.update(
            status=status,
            evidence=[{"source": "main_agent_review", "statement": evidence, "url": page["url"], "revision": revision}],
        )

    def summary(self):
        items = list(self.items.values())
        return {
            "total": len(items),
            "verified": sum(i["status"] == "verified" for i in items),
            "reviewed": sum(i["status"] == "reviewed" for i in items),
            "blocked": sum(i["status"] == "blocked" for i in items),
            "pending": sum(i["status"] == "pending" for i in items),
            "items": copy.deepcopy(items),
        }

    def incomplete(self):
        return any(i["status"] not in {"verified", "reviewed"} for i in self.items.values())

    def exact_input(self, page, action):
        if action.get("kind") != "fill":
            return None
        matches = [
            a for a in page.get("actions", []) if a.get("kind") == "fill" and a.get("label") == action.get("label")
        ]
        if len(matches) != 1:
            return None
        return next(
            (i["value"] for i in self.contract["inputs"] if i["url"] == page["url"] and i["label"] == action["label"]),
            None,
        )

    def available_candidates(self, page):
        parts = urlsplit(page["url"])
        origin = f"{parts.scheme}://{parts.netloc}"
        return [c for c in self.contract["input_candidates"] if not c["origins"] or origin in c["origins"]]

    def candidate_input(self, page, identifier):
        candidate = next((c for c in self.available_candidates(page) if c["id"] == identifier), None)
        if candidate is None:
            raise ValueError("No applicable prepared text; main agent must supply the missing value")
        return candidate["value"]

    def fill_targets(self, page, targets):
        """One Choice binds an observed field and a prepared value; no independent value head."""
        choices = {}
        for index, action in targets.items():
            exact = self.exact_input(page, action)
            if exact is not None:
                choices[index] = {**action, "prepared_value": exact, "input_source": "exact"}
                continue
            for number, candidate in enumerate(self.available_candidates(page), 1):
                choices[f"{index}:v{number}"] = {
                    **action,
                    "input_id": candidate["id"],
                    "prepared_value": candidate["value"],
                    "input_purpose": candidate["purpose"],
                    "input_source": "prepared",
                }
            choices[f"{index}:NONE"] = {**action, "input_id": "NONE"}
        if len(choices) > 200:
            raise ValueError("Too many prepared field/value pairs; narrow the task's input candidates")
        return choices
