"""Code-owned computer-use primitives, all scoped to the shared task CDP session."""

import math
import time
from urllib.parse import urlparse

from .browser import StalePage


def valid_url(url):
    if not isinstance(url, str) or urlparse(url).scheme not in {"http", "https", "about"}:
        raise ValueError("Use an http(s) URL or about:blank")
    if url.startswith("about:") and url != "about:blank":
        raise ValueError("Only about:blank is supported")
    return url


def point(page, x, y):
    if not all(type(v) in (int, float) and math.isfinite(v) for v in (x, y)):
        raise ValueError("Coordinates must be finite numbers")
    if not (0 <= x < page["w"] and 0 <= y < page["h"]):
        raise ValueError("Coordinates are outside the observed viewport")
    return x, y


def execute(browser, page, action):
    kind = action.get("kind")
    if kind == "element":
        target = next((a for a in page["actions"] if a["id"] == action.get("id")), None)
        if not target:
            raise ValueError("Choose an action ID from the latest observation")
        if target["kind"] == "fill" and not isinstance(action.get("text"), str):
            raise ValueError("Filling a field requires text")
        browser.act(target, page, text=action.get("text"))
        return target["label"], target["kind"]
    if kind == "switch_tab":
        target = next((a for a in page["actions"] if a.get("target_id") == action.get("target_id")), None)
        if not target:
            raise ValueError("Select another open task tab")
        browser.act(target, page)
        return target["label"], "tab"
    if not browser.fresh(page):
        raise StalePage("Page changed; observe before issuing another action")
    if kind == "navigate":
        url = valid_url(action.get("url"))
        result = browser.call("Page.navigate", url=url)
        if result.get("errorText"):
            raise RuntimeError("Navigation failed: " + result["errorText"])
        browser.wait_document()
        return url, kind
    if kind == "click":
        x, y = point(page, action.get("x"), action.get("y"))
        for event in ("mousePressed", "mouseReleased"):
            browser.call("Input.dispatchMouseEvent", type=event, x=x, y=y, button="left", clickCount=1)
        return f"Click ({x}, {y})", kind
    if kind == "type":
        text = action.get("text")
        if not isinstance(text, str) or not 0 < len(text) <= 20000:
            raise ValueError("Provide 1–20000 characters")
        browser.call("Input.insertText", text=text)
        return "Type into focused control", kind
    if kind == "press":
        chord = action.get("keys", "").split("+")
        if not chord or not chord[-1]:
            raise ValueError("Provide a key or chord, such as Enter or Meta+A")
        modifiers = {"Alt": 1, "Control": 2, "Meta": 4, "Shift": 8}
        if any(k not in modifiers for k in chord[:-1]):
            raise ValueError("Unknown modifier")
        key = chord[-1]
        special = {
            "Enter": 13,
            "Tab": 9,
            "Escape": 27,
            "Backspace": 8,
            "Delete": 46,
            "ArrowLeft": 37,
            "ArrowUp": 38,
            "ArrowRight": 39,
            "ArrowDown": 40,
            "Home": 36,
            "End": 35,
            "PageUp": 33,
            "PageDown": 34,
            "Space": 32,
        }
        if key not in special and len(key) != 1:
            raise ValueError("Unsupported key")
        params = dict(
            key=" " if key == "Space" else key,
            modifiers=sum(modifiers[k] for k in set(chord[:-1])),
            windowsVirtualKeyCode=special.get(key, ord(key.upper()) if len(key) == 1 else 0),
        )
        if key.lower() == "a" and any(k in chord for k in ("Meta", "Control")):
            params["commands"] = ["selectAll"]
        browser.call("Input.dispatchKeyEvent", type="keyDown", **params)
        params.pop("commands", None)
        browser.call("Input.dispatchKeyEvent", type="keyUp", **params)
        return action["keys"], kind
    if kind == "scroll":
        x, y = point(page, action.get("x", page["w"] / 2), action.get("y", page["h"] / 2))
        dx, dy = action.get("dx", 0), action.get("dy", 560)
        if not all(type(v) in (int, float) and math.isfinite(v) and abs(v) <= 10000 for v in (dx, dy)):
            raise ValueError("Invalid scroll delta")
        browser.call("Input.dispatchMouseEvent", type="mouseWheel", x=x, y=y, deltaX=dx, deltaY=dy)
        time.sleep(0.1)
        return f"Scroll ({dx}, {dy})", kind
    if kind == "drag":
        x, y = point(page, action.get("x"), action.get("y"))
        to_x, to_y = point(page, action.get("to_x"), action.get("to_y"))
        browser.call("Input.dispatchMouseEvent", type="mousePressed", x=x, y=y, button="left", clickCount=1)
        try:
            for step in range(1, 13):
                browser.call(
                    "Input.dispatchMouseEvent",
                    type="mouseMoved",
                    x=x + (to_x - x) * step / 12,
                    y=y + (to_y - y) * step / 12,
                    button="left",
                    buttons=1,
                )
        finally:
            browser.call("Input.dispatchMouseEvent", type="mouseReleased", x=to_x, y=to_y, button="left", clickCount=1)
        return f"Drag ({x}, {y}) → ({to_x}, {to_y})", kind
    if kind == "wait":
        seconds = action.get("seconds", 0.5)
        if type(seconds) not in (int, float) or not 0 <= seconds <= 5:
            raise ValueError("Wait must be between 0 and 5 seconds")
        time.sleep(seconds)
        return f"Wait {seconds}s", kind
    raise ValueError("Unsupported computer-use action")
