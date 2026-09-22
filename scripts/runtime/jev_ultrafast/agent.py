"""The complete agent loop. Typed choices, observable state, bounded execution."""

import base64
import time
from pathlib import Path

from .browser import Browser, StalePage
from .metrics import Metrics
from .model import action_space, choose, operation_history
from .questions import MAX_STEPS
from .repetition import RepetitionGuard
from .workflow import Workflow


class Agent:
    def __init__(
        self, url, goals, *, record_dir=None, screenshots=False, browser=None, metrics=None, max_steps=MAX_STEPS
    ):
        task = goals.strip() if isinstance(goals, str) else "\n".join(goals).strip()
        if not task:
            raise ValueError("Supply a task")
        plan = [task]
        self.max_steps = max_steps
        self.metrics = metrics or Metrics()
        self.workflow = Workflow()
        self.repetition_guard = RepetitionGuard()
        self.task_history_start = 0
        self.browser = browser or Browser(url)
        self.record_dir = Path(record_dir) if record_dir else None
        self.screenshots = screenshots or bool(record_dir)
        try:
            page = self.observe()
        except Exception:
            self.browser.detach()
            raise
        self.state = dict(
            browser=self.browser,
            goal="\n".join(plan),
            page=page,
            decision=None,
            history=[],
            status="ready",
            plan=plan,
            plan_index=0,
            decisions=[],
            elapsed_ms=0,
            started_at=None,
            record=bool(self.record_dir),
        )
        if self.record_dir:
            self.record_dir.mkdir(parents=True, exist_ok=True)
            (self.record_dir / "000000.jpg").write_bytes(base64.b64decode(page["screenshot"]))

    def snapshot(self):
        return {
            **{k: v for k, v in self.state.items() if k != "browser"},
            "operation_history": operation_history(self.state["history"]),
            "elements": action_space(self.repetition_guard.available_page(self.state["page"])["actions"])[0],
        }

    def observe(self):
        page = self.metrics.call("observe", self.browser.observe, screenshot=self.screenshots)
        if getattr(self, "observed", None):
            self.observed(page)
        return page

    def command(self, name, body=None):
        body = body or {}
        state = self.state
        if name == "tick":
            try:
                self.command("predict", {})
                return self.command("act", {"fingerprint": state["page"]["fingerprint"]})
            except StalePage:
                # An uncertain observation cannot establish a no-progress streak.
                self.repetition_guard.reset()
                self.metrics.counters["stale_decisions"] += 1
                state["decision"] = None
                state["status"] = "ready"
                state["page"] = self.observe()
                state["elapsed_ms"] = round((time.perf_counter() - state["started_at"]) * 1000)
                return self.snapshot()
        elif name == "predict":
            if not state["browser"]:
                raise ValueError("Start a browser task first")
            if state["started_at"] is None:
                state["started_at"] = time.perf_counter()
            if not state["browser"].fresh(state["page"]):
                state["page"] = self.observe()
            state["decision"] = None
            if state["status"] in {"done", "blocked"}:
                raise ValueError("This call has stopped. Start a fresh run.")
            if len(state["decisions"]) >= self.max_steps * 2:
                raise RuntimeError("Reached the whole-call model-call limit")
            state["decision"] = self.metrics.call(
                "decision", choose, self.repetition_guard.available_page(state["page"]),
                state["goal"], state["history"][self.task_history_start :]
            )
            state["decisions"].append(
                {
                    **state["decision"],
                    "fingerprint": state["page"]["fingerprint"],
                    "elapsed_ms": round((time.perf_counter() - state["started_at"]) * 1000),
                }
            )
            state["status"] = "predicted"
        elif name == "act":
            decision, page = state["decision"], state["page"]
            if not decision or body.get("fingerprint") != page["fingerprint"]:
                raise ValueError("Observe and choose before acting")
            # Consume once, before any mutation or model call. A retry cannot double-click.
            state["decision"] = None
            selected = decision["choice"]
            if selected in {"DONE", "BLOCKED"}:
                if not state["browser"].fresh(page):
                    state["status"] = "ready"
                    raise StalePage("Page changed since the decision. Choose again.")
                state["status"] = {"DONE": "done", "BLOCKED": "blocked"}[selected]
                state["plan_index"] = int(selected == "DONE")
                state["elapsed_ms"] = round((time.perf_counter() - state["started_at"]) * 1000)
                return self.snapshot()
            action = next(a for a in self.repetition_guard.available_page(page)["actions"] if a["id"] == selected)
            if len(state["history"]) >= self.max_steps:
                state["status"] = "blocked"
                raise RuntimeError(f"Reached the whole-call limit of {self.max_steps} actions")
            text, text_source = None, None
            state["input_request"] = None
            if action["kind"] == "fill":
                if not state["browser"].fresh(page):
                    raise StalePage("Page changed before filling. Choose again.")
                text = self.workflow.exact_input(page, action)
                if text is not None:
                    self.metrics.counters["exact_input_uses"] += 1
                    text_source = "exact_binding"
                else:
                    try:
                        text = self.workflow.candidate_input(page, decision.get("input_id"))
                    except ValueError:
                        state["input_request"] = {
                            "label": action["label"],
                            "url": page["url"],
                            "reason": "No supplied text fits this field; Codex must provide a candidate",
                        }
                        raise
                    text_source = "prepared_candidate"
                    self.metrics.counters["prepared_input_uses"] += 1
            # Execute only a selected supplied literal; never generate or infer field text here.
            self.metrics.call(
                "wait" if action["kind"] == "wait" else "execute", state["browser"].act, action, page, text=text
            )
            state["elapsed_ms"] = round((time.perf_counter() - state["started_at"]) * 1000)
            # Record execution before observing. A stale post-action observation must not erase the action.
            state["history"].append(
                {
                    "step": len(state["history"]) + 1,
                    "actor": "JEV",
                    "action": action["label"],
                    "kind": action["kind"],
                    "choice": selected,
                    "probability": decision["probabilities"][selected],
                    "confidence": decision["confidence"],
                    "latency_ms": decision["latency_ms"],
                    "text": text,
                    "text_source": text_source,
                    "input_id": decision.get("input_id") if text_source == "prepared_candidate" else None,
                    "operation": decision["operation"],
                    "target": decision["target"],
                    "page_changed": None,
                    "source_url": page["url"],
                    "target_url": action.get("href"),
                    "url": page["url"],
                    "usage": decision["usage"],
                    "executed_ms": round((time.perf_counter() - state["started_at"]) * 1000),
                    "elapsed_ms": state["elapsed_ms"],
                }
            )
            state["page"] = self.observe()
            state["elapsed_ms"] = round((time.perf_counter() - state["started_at"]) * 1000)
            state["history"][-1].update(
                page_changed=state["page"]["fingerprint"] != page["fingerprint"],
                url=state["page"]["url"],
                elapsed_ms=state["elapsed_ms"],
            )
            if state["record"]:
                (self.record_dir / f"{state['elapsed_ms']:06d}.jpg").write_bytes(
                    base64.b64decode(state["page"]["screenshot"])
                )
            repetition = self.repetition_guard.record(action, page, state["page"], text)
            if repetition:
                state.setdefault("excluded_actions", []).append(repetition)
                self.metrics.counters["repeated_action_exclusions"] += 1
                self.repetition_guard.reset()
            state["status"] = "ready"
        else:
            raise ValueError("Unknown command")
        return self.snapshot()

    def run(self):
        while self.state["status"] not in {"done", "blocked"}:
            yield self.command("tick")

    def close(self):
        self.browser.close()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()
