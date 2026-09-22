"""Content-free timings, including failed calls. No prompts, URLs, keys or field values."""

import contextvars
import math
import time
from collections import Counter
from contextlib import contextmanager

ACTIVE_METRICS = contextvars.ContextVar("jev_metrics", default=None)


def numeric_usage(value):
    if not isinstance(value, dict):
        return None
    return {
        k: v
        for k, v in value.items()
        if k in {"input_tokens", "output_tokens", "prompt_tokens", "completion_tokens", "total_tokens"}
        and type(v) in (int, float)
        and math.isfinite(v)
        and v >= 0
    }


class Metrics:
    def __init__(self):
        self.started = time.monotonic()
        self.ended = None
        self.records = []
        self.counters = Counter()
        self.automation_ms = 0
        self.user_started = None
        self.user_wait_ms = 0

    @contextmanager
    def span(self, stage):
        started = time.monotonic()
        record = {"stage": stage, "ok": False}
        token = ACTIVE_METRICS.set(self)
        try:
            yield record
            record["ok"] = True
        finally:
            record["ms"] = round((time.monotonic() - started) * 1000, 3)
            self.records.append(record)
            ACTIVE_METRICS.reset(token)

    def call(self, stage, function, *args, **kwargs):
        with self.span(stage):
            return function(*args, **kwargs)

    def controller(self, owner):
        if owner == "USER" and self.user_started is None:
            self.user_started = time.monotonic()
        elif owner != "USER" and self.user_started is not None:
            self.user_wait_ms += (time.monotonic() - self.user_started) * 1000
            self.user_started = None

    def summary(self):
        stages = {}
        for record in self.records:
            stage = stages.setdefault(record["stage"], {"calls": 0, "failed": 0, "ms": 0})
            stage["calls"] += 1
            stage["failed"] += int(not record["ok"])
            stage["ms"] = round(stage["ms"] + record["ms"], 3)
        requests = [r for r in self.records if r["stage"] == "model_http"]
        usage = Counter()
        for record in requests:
            usage.update(record.get("usage") or {})
        now = self.ended or time.monotonic()
        user_ms = self.user_wait_ms + ((now - self.user_started) * 1000 if self.user_started else 0)
        return {
            "wall_ms": round((now - self.started) * 1000),
            "automation_ms": round(self.automation_ms),
            "user_wait_ms": round(user_ms),
            "stages": stages,
            "counters": dict(self.counters),
            "provider_usage": dict(usage),
            "requests_with_missing_usage": sum(not r.get("usage") for r in requests),
            "model_requests": requests,
            "cost_usd": None,
            "main_agent_usage": None,
            "main_agent_cost_usd": None,
            "timing_note": "Stages may nest; do not sum them. Wall includes orchestration and user waiting.",
        }
