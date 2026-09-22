"""Continuous, task-local execution; return evidence once and detach every page."""

import time

from .agent import Agent
from .browser import Browser, NeedsUser
from .direct import valid_url
from .evidence import TaskEvidence
from .metrics import Metrics
from .workflow import Workflow


def compact_page(page, limit=6000):
    return {
        "url": page.get("url"),
        "title": page.get("title"),
        "tab_id": page.get("tab_id"),
        "text": page.get("text", "")[:limit],
        "media": page.get("media", []),
    }


def run_task(url, goal, *, target_id=None, inputs=None, show=False, max_actions=200):
    if not isinstance(goal, str) or not 0 < len(goal.strip()) <= 10000:
        raise ValueError("Supply a goal of 1–10000 characters")
    inputs = [] if inputs is None else inputs
    if not isinstance(inputs, list) or any(not isinstance(i, dict) or set(i) != {"value", "purpose"} for i in inputs):
        raise ValueError("inputs must be a list of objects with value and purpose")
    workflow = Workflow({"input_candidates": [{"id": f"input{i}", **v} for i, v in enumerate(inputs)]})
    if url is not None:
        valid_url(url)
    metrics = Metrics()
    browser = None
    agent = None
    evidence = TaskEvidence()
    last_page = None
    result = {"status": "error"}

    def observed(page):
        nonlocal last_page
        last_page = page
        issues = page.get("user_action_required", []) + browser.issues
        browser.issues.clear()
        user_issues = [
            i if isinstance(i, str) else i["reason"]
            for i in issues
            if isinstance(i, str) or i.get("controller") == "USER"
        ]
        if user_issues:
            raise NeedsUser("; ".join(user_issues))
        evidence.record(page, agent.state["history"])
        # Recoverable tab changes stay inside Jev's loop.
        page["task_context"] = {
            "total_goal": goal,
            "input_candidates": workflow.contract["input_candidates"],
            "browser_notes": [i["reason"] for i in issues if isinstance(i, dict)],
            **evidence.context(page["url"]),
        }

    try:
        browser = metrics.call("browser_setup", Browser, url, target_id=target_id)
        agent = Agent(url, goal, browser=browser, metrics=metrics, max_steps=max_actions)
        agent.workflow = workflow
        agent.observed = observed
        observed(agent.state["page"])
        with metrics.span("execution"):
            while agent.state["status"] not in {"done", "blocked"}:
                agent.command("tick")
        status = agent.state["status"]
        result = {"status": "done" if status == "done" else "error", "stop_choice": status.upper()}
        if status != "done":
            result["reason"] = agent.state.get(
                "stop_reason", "Jev could not continue using the available operations"
            )
            if agent.state.get("repetition"):
                result["repetition"] = agent.state["repetition"]
    except (Exception, KeyboardInterrupt) as error:
        result = {"status": "error", "reason": f"{type(error).__name__}: {error}"}
    finally:
        if browser is not None:
            try:
                if show:
                    browser.show()
            except Exception as error:
                result.setdefault("warnings", []).append(f"Could not show final page: {type(error).__name__}")
            try:
                browser.detach()
            except Exception as error:
                result["status"] = "error"
                result["cleanup_error"] = f"Could not detach browser: {type(error).__name__}"
        metrics.ended = time.monotonic()
    if agent is not None:
        page = last_page or agent.state["page"]
        result["page"] = compact_page(page)
        result["tabs"] = page.get("tabs", [])
        result["evidence"] = evidence.context(page["url"])
        if agent.state.get("input_request"):
            result["input_request"] = agent.state["input_request"]
        result["actions"] = [
            {k: h.get(k) for k in ("action", "kind", "url", "elapsed_ms", "text_source", "input_id")}
            for h in agent.state["history"][-30:]
        ]
        result["action_count"] = len(agent.state["history"])
        result["excluded_actions"] = agent.state.get("excluded_actions", [])
    summary = metrics.summary()
    result["timing"] = {k: summary[k] for k in ("wall_ms", "stages", "counters")}
    return result
