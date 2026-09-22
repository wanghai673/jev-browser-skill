"""Jev chooses actions and supplied literals; it is the only model called by this runtime."""

import math
import os
import time
from contextlib import nullcontext
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

from .metrics import ACTIVE_METRICS, numeric_usage
from .questions import NEXT_ACTION, PREPARED_TARGET, TARGET
from .workflow import Workflow

CLIENT = httpx.Client(http2=True, timeout=25)


def post_json(url, key, body):
    for attempt in range(3):
        metrics = ACTIVE_METRICS.get()
        with metrics.span("model_http") if metrics else nullcontext({}) as record:
            record.update(
                provider="jev",
                model=body.get("model"),
                usage=None,
            )
            try:
                response = CLIENT.post(url, json=body, headers={"Authorization": f"Bearer {key}"})
            except httpx.HTTPError:
                raise RuntimeError("Model connection failed; no action executed.") from None
            record["http_status"] = response.status_code
            if not response.is_error:
                result = response.json()
                record["requested_model"] = body.get("model")
                record["model"] = result.get("model", body.get("model"))
                record["usage"] = numeric_usage(result.get("usage"))
                return result
        if metrics and response.is_error:
            record["ok"] = False
        if response.status_code in {429, 529, 503} and attempt < 2:
            time.sleep(0.5 * 2**attempt)
            continue
        if response.is_error:
            raise RuntimeError(f"Model provider returned HTTP {response.status_code}; no action executed.")
    raise RuntimeError("Model unavailable")


def validate_choice(answer, ids):
    try:
        probabilities = answer["probabilities"]
        numbers = [*probabilities.values(), answer["confidence"]]
        valid = (
            answer["choice"] in ids
            and set(probabilities) == set(ids)
            and all(type(n) in (int, float) and math.isfinite(n) and 0 <= n <= 1 for n in numbers)
            and abs(sum(probabilities.values()) - 1) < 0.02
            and probabilities[answer["choice"]] >= max(probabilities.values()) - 1e-6
        )
    except (KeyError, TypeError, ValueError):
        valid = False
    if not valid:
        raise ValueError("Invalid TypeSafe response; no action executed.")
    return answer


def action_space(actions):
    """One index per observed element; each operation has its own valid target choices."""
    elements, indices, targets, controls = [], {}, {}, {}
    operations = {"click": "CLICK", "fill": "TYPE_TEXT", "select": "SELECT", "tab": "SWITCH_TAB"}
    for action in actions:
        kind = action["kind"]
        if kind not in operations:
            controls[action["id"].upper()] = action
            continue
        node = action["node"]
        if node not in indices:
            index = str(len(elements) + 1)
            indices[node] = index
            element = {
                k: action[k] for k in ("role", "value", "checked", "selected", "expanded", "href") if k in action
            }
            if "href" in element:
                element["href"] = compact_href(element["href"])
            element.update(index=index, label=action["label"].split(" → ")[0], operations=[])
            if kind == "select":
                element["value"] = action.get("current_value", "")
                element["options"] = []
            elements.append(element)
        index = indices[node]
        operation = operations[kind]
        group = targets.setdefault(operation, {})
        element = elements[int(index) - 1]
        if operation not in element["operations"]:
            element["operations"].append(operation)
        target = index
        if kind == "select":
            target = f"{index}:{len(element['options']) + 1}"
            element["options"].append({"index": target, "label": action["label"], "value": action["value"]})
        group[target] = action
    return elements, targets, controls


def compact_href(value):
    """A bounded navigation hint; the executor still clicks the original observed DOM node."""
    try:
        parts = urlsplit(value)
        query = urlencode([(k, v) for k, v in parse_qsl(parts.query) if len(k) <= 40 and len(v) <= 80][:4])
        return urlunsplit((parts.scheme, parts.netloc, parts.path[:180], query, parts.fragment[:60]))[:300]
    except (ValueError, TypeError):
        return ""


def operation_history(history):
    """Compact executed actions only, without probabilities or inferred reasoning."""
    return [
        f"{i}. [{h.get('actor', 'JEV')}] {h.get('operation') or h.get('kind', '')}: "
        + " ".join(h["action"].split())[:300]
        + (f" → {h['text']}" if h.get("text") else "")
        for i, h in enumerate(history, 1)
    ]


def choose(state, goal, history):
    compact = bool(state.get("task_context", {}).get("progress"))
    elements, targets, controls = action_space(state["actions"])
    context = state.get("task_context", {})
    workflow = Workflow({k: context[k] for k in ("inputs", "input_candidates") if k in context})
    if "TYPE_TEXT" in targets:
        targets["TYPE_TEXT"] = workflow.fill_targets(state, targets["TYPE_TEXT"])
    labels = {
        "CLICK": "Click an element, button, menu option, autocomplete suggestion, or calendar day.",
        "TYPE_TEXT": "Select a field and a supplied literal to fill, or NONE if the needed value is missing.",
        "SELECT": "Select an observed dropdown value.",
        "SWITCH_TAB": "Return to a previously opened task tab; keep the current tab open.",
    }
    operations = {key: labels[key] for key in targets}
    operations.update({key: value["label"] for key, value in controls.items()})
    operations.update(
        DONE="All requirements are satisfied by the current page and observations from this call.",
        BLOCKED="Unrecoverable: no supported operation can progress.",
    )
    questions = {
        "operation": {"type": "choice", "criteria": operations, "instructions": {"goal": goal, "rules": NEXT_ACTION}}
    }
    for operation, candidates in targets.items():
        questions[operation.lower() + "_target"] = {
            "type": "choice",
            "criteria": {
                index: {
                    "element": f"[{index}] {a['label']}",
                    "current_value": a.get("current_value", a.get("value", "")),
                    **{k: a[k] for k in ("role", "checked", "selected", "expanded") if k in a},
                    **({"href": compact_href(a["href"])} if "href" in a else {}),
                    **({"input_id": a["input_id"]} if "input_id" in a else {}),
                    **(
                        {"fill_action": f"Fill {a['label']!r} with exactly {a['prepared_value']!r}"}
                        if "prepared_value" in a
                        else {}
                    ),
                    **({"purpose": a["input_purpose"]} if "input_purpose" in a else {}),
                    **({"input_source": a["input_source"]} if "input_source" in a else {}),
                }
                for index, a in candidates.items()
            },
            "instructions": {
                "goal": goal,
                "operation": operation,
                "rules": PREPARED_TARGET
                if operation == "TYPE_TEXT"
                else [NEXT_ACTION, TARGET],
            },
        }
    body = {
        "model": os.environ.get("TYPESAFE_MODEL", "jev-latest"),
        "state": {
            "page": {
                **{k: state[k] for k in ("url", "title", "text")},
                "media": state.get("media", []),
                "scroll": state.get("scroll", {}),
                "viewport_height": state.get("h"),
            },
            "elements": elements,
            "operation_history": operation_history(history)[-12:] if compact else operation_history(history),
            "omitted_history_count": max(0, len(history) - 12) if compact else 0,
            "tabs": state.get("tabs", []),
            "task_context": state.get("task_context", {}),
        },
        "questions": questions,
    }
    started = time.perf_counter()
    result = post_json("https://api.typesafe.ai/v1/systemone", os.environ["TYPESAFE_API_KEY"], body)
    operation_answer = validate_choice(result["answers"].get("operation", {}), operations)
    operation = operation_answer["choice"]
    target = None
    target_answer = None
    probabilities = {}
    input_id = None
    if operation in targets:
        # Unused target heads cannot cause an action. Validate the head selected by the operation.
        target_answer = validate_choice(result["answers"].get(operation.lower() + "_target", {}), targets[operation])
        target = target_answer["choice"]
        selected_action = targets[operation][target]
        choice = selected_action["id"]
        if operation == "TYPE_TEXT":
            input_id = selected_action.get("input_id")
        for index, action in targets[operation].items():
            probabilities[action["id"]] = probabilities.get(action["id"], 0) + target_answer["probabilities"][index]
    else:
        choice = controls[operation]["id"] if operation in controls else operation
        probabilities[choice] = operation_answer["probabilities"][operation]
    return {
        "choice": choice,
        "operation": operation,
        "target": target,
        "input_id": input_id,
        "confidence": operation_answer["confidence"],
        "probabilities": probabilities,
        "operation_probabilities": operation_answer["probabilities"],
        "target_probabilities": target_answer["probabilities"] if target_answer else {},
        "target_confidence": target_answer["confidence"] if target_answer else None,
        "raw_answers": result["answers"],
        "model": result["model"],
        "usage": result.get("usage", {}),
        "latency_ms": round((time.perf_counter() - started) * 1000),
        "request": body,
    }
