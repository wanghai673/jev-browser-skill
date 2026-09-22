"""Observed actions through Browser Harness; one CDP session, no per-step subprocess."""

import hashlib
import json
import sys
import time
from pathlib import Path

from browser_harness.admin import ensure_daemon
from browser_harness.helpers import cdp

# Atomically read visible content and controls, preserving actual DOM node identity.
BACKGROUND = Path(__file__).with_name("background.js").read_text()
READ_STATE = Path(__file__).with_name("snapshot.js").read_text()
MARKER = f"(() => {{ const state={READ_STATE}; return state?.marker ?? null; }})()"


class StalePage(ValueError):
    """A decision no longer refers to the observed page."""


class NeedsUser(RuntimeError):
    """Authentication or native interaction must be completed by the user."""


class Browser:
    def __init__(self, url=None, *, target_id=None):
        ensure_daemon()
        self.created_targets = set()
        self.sessions = {}
        self.scripts = {}
        self.issues = []
        self.background = True
        if target_id:
            info = cdp("Target.getTargetInfo", targetId=target_id)["targetInfo"]
            if info.get("type") != "page":
                raise ValueError("Attach requires a page target")
            self.target = target_id
        else:
            self.target = cdp("Target.createTarget", url="about:blank", background=True)["targetId"]
            self.created_targets.add(self.target)
        self.owned_targets = {self.target}  # registered task tabs, including explicitly adopted pages
        self.pending_popup = None
        try:
            self.bind(self.target)
            if not target_id:
                self.call("Page.navigate", url=url or "about:blank")
                self.wait_document()
        except BaseException:
            self.detach()
            raise

    def bind(self, target):
        session = self.sessions.get(target)
        if not session:
            session = cdp("Target.attachToTarget", targetId=target, flatten=True)["sessionId"]
            self.sessions[target] = session
        self.target, self.session = target, session
        if target not in self.scripts:
            self.call("Page.enable")
            self.scripts[target] = self.call("Page.addScriptToEvaluateOnNewDocument", source=BACKGROUND)["identifier"]
            self.evaluate(BACKGROUND)
        self.call("Emulation.setFocusEmulationEnabled", enabled=self.background)
        self.evaluate(f"window.__jevBridge && (window.__jevBridge.enabled={str(self.background).lower()})")

    def wait_document(self):
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            try:
                if self.evaluate("location.href !== 'about:blank' && document.readyState === 'complete'"):
                    break
            except StalePage:
                pass
            time.sleep(0.05)
        time.sleep(0.2)
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            try:
                pending = self.evaluate("""[...document.querySelectorAll('video,audio')]
                    .some(v => !v.error && (v.readyState < 2 || (!v.paused && v.currentTime === 0)))""")
                if not pending:
                    break
            except StalePage:
                pass
            time.sleep(0.1)

    def set_background(self, enabled):
        if enabled and not self.background:
            self.sync_user_tabs()
        self.background = enabled
        current = self.target
        for target in list(self.sessions):
            if target in self.live_targets():
                self.bind(target)
                self.call("Page.removeScriptToEvaluateOnNewDocument", identifier=self.scripts[target])
                source = BACKGROUND if enabled else BACKGROUND.replace("enabled: true", "enabled: false")
                self.scripts[target] = self.call("Page.addScriptToEvaluateOnNewDocument", source=source)["identifier"]
        if current in self.live_targets():
            self.bind(current)

    def sync_user_tabs(self):
        # A manual popup belongs to the task only when Chrome reports a task page as its opener.
        candidates = cdp("Target.getTargets")["targetInfos"]
        opened = [
            t["targetId"]
            for t in candidates
            if t.get("type") == "page"
            and t.get("openerId") in self.owned_targets
            and t["targetId"] not in self.owned_targets
        ]
        self.owned_targets.update(opened)
        self.created_targets.update(opened)
        if len(opened) == 1:
            self.bind(opened[0])
        elif opened:
            self.issues.append(
                {"controller": "LLM", "reason": "Manual work opened multiple task pages; select the intended task tab."}
            )

    def live_targets(self):
        return {t["targetId"] for t in cdp("Target.getTargets")["targetInfos"] if t.get("type") == "page"}

    def recover_target(self):
        live = self.live_targets()
        if self.target in live:
            return
        previous = self.target
        self.sessions.pop(previous, None)
        self.scripts.pop(previous, None)
        self.after_input = None
        remaining = sorted(self.owned_targets & live)
        if not remaining:
            raise RuntimeError("All pages belonging to this call were closed")
        self.bind(remaining[0])
        self.issues.append(
            {
                "controller": "LLM",
                "reason": "The previous task page was closed; inspect the remaining task page before continuing.",
            }
        )

    def show(self):
        cdp("Target.activateTarget", targetId=self.target)

    def call(self, method, **params):
        return cdp(method, session_id=self.session, **params)

    def evaluate(self, expression):
        response = self.call("Runtime.evaluate", expression=expression, returnByValue=True)
        if response.get("exceptionDetails"):
            raise StalePage("Document changed during evaluation")
        return response.get("result", {}).get("value")

    def follow_popup(self):
        # Drain only task-owned page requests. Never follow another user's unrelated tab.
        events = self.evaluate("window.__jevBridge?.events.splice(0) || []") or []
        opened = []
        for event in events:
            if event.get("type") == "needs_user":
                self.issues.append(event["reason"])
            elif event.get("type") == "open":
                target = cdp("Target.createTarget", url="about:blank", background=True)["targetId"]
                self.created_targets.add(target)
                self.owned_targets.add(target)
                self.bind(target)
                self.call("Page.navigate", url=event["url"], referrer=event.get("referrer", ""))
                opened.append(target)
        if opened:
            self.wait_document()
        if len(opened) > 1:
            self.issues.append(
                {"controller": "LLM", "reason": "The action opened several pages; inspect task tabs before continuing."}
            )

    def with_tabs(self, page):
        targets = cdp("Target.getTargets")["targetInfos"]
        tabs = [t for t in targets if t["targetId"] in self.owned_targets and t.get("type") == "page"]
        tabs.sort(key=lambda t: t["targetId"])
        page["tab_id"] = self.target
        page["tabs"] = []
        for i, tab in enumerate(tabs, 1):
            active = tab["targetId"] == self.target
            label = f"{tab.get('title') or 'Untitled'} · {tab.get('url', '')}"
            page["tabs"].append(
                {
                    "index": f"T{i}",
                    "target_id": tab["targetId"],
                    "title": tab.get("title", ""),
                    "url": tab.get("url", ""),
                    "active": active,
                }
            )
            if not active:
                page["actions"].append(
                    {
                        "id": f"tab_{i}",
                        "kind": "tab",
                        "node": f"tab:{tab['targetId']}",
                        "target_id": tab["targetId"],
                        "role": "tab",
                        "label": label,
                    }
                )
        page["fingerprint"] = fingerprint(page)
        return page

    def observe(self, screenshot=True):
        self.recover_target()
        if getattr(self, "after_input", None):
            action, self.after_input = self.after_input, None
            # This is read-only and happens after execution was logged, even if navigation interrupts it.
            try:
                self.call(
                    "Runtime.evaluate",
                    expression="""(action => new Promise(resolve => {
                      const field=window.__jevFast?.nodes.get(action.node);
                      const autocomplete=action.kind==='fill' && field?.getAttribute('role')==='combobox';
                      let frames=0, stopped=false;
                      const finish=()=>{stopped=true;resolve()};
                      setTimeout(finish,autocomplete ? 200 : 50);
                      const ready=()=>{
                        if (stopped) return;
                        const ids=(field?.getAttribute('aria-controls')||field?.getAttribute('aria-owns')||'')
                          .split(/\\s+/).filter(Boolean);
                        const roots=ids.length ? ids.map(id=>document.getElementById(id)).filter(Boolean) : [document];
                        const options=roots.flatMap(root=>[...root.querySelectorAll('[role="option"]')]);
                        if (++frames>=2 && (!autocomplete || options.some(e=>{
                          const r=e.getBoundingClientRect();
                          return r.width && r.height && r.bottom>0 && r.top<innerHeight &&
                            e.checkVisibility({checkOpacity:true,checkVisibilityCSS:true});
                        }))) finish();
                        else requestAnimationFrame(ready);
                      };
                      requestAnimationFrame(ready);
                    }))("""
                    + json.dumps(action)
                    + ")",
                    awaitPromise=True,
                    returnByValue=True,
                )
            except RuntimeError:
                pass
        self.follow_popup()
        for attempt in range(10):
            try:
                return self.with_tabs(
                    browser_operation({"operation": "observe", "session": self.session, "screenshot": screenshot})
                )
            except StalePage:
                if attempt == 9:
                    raise
                time.sleep(0.02)
        raise StalePage("Page did not settle")

    def fresh(self, page, action=None):
        if self.target not in self.live_targets():
            return False
        if page.get("tab_id", self.target) != self.target:
            return False
        if action is not None and action["kind"] == "tab":
            return True  # Switching tabs does not depend on mutable DOM content.
        if getattr(self, "background", False) and not self.evaluate("window.__jevBridge?.enabled === true"):
            raise NeedsUser("Background page protection is unavailable. Pause and reattach before continuing.")
        gate = self.evaluate("window.__jevFast?.userGate?.() || []")
        if gate:
            raise NeedsUser("; ".join(gate))
        if action is not None and action["kind"] in {"click", "select"}:
            node = action["node"]
            if type(node) is not int:
                return False
            current = self.evaluate(
                "(() => { const c=window.__jevFast; "
                f"return c ? [c.pageKey(),c.guard(c.nodes.get({node}))] : null; }})()"
            )
            return current == [page["page_key"], page["guards"].get(str(node))]
        return self.evaluate(MARKER) == page["marker"]

    def act(self, action, page, text=None):
        if not self.fresh(page, action):
            raise StalePage("Page changed since this decision. Observe again.")
        if action["kind"] == "tab":
            target = action["target_id"]
            if target not in self.owned_targets:
                raise ValueError("Cannot switch to a tab outside this task")
            if not any(t["targetId"] == target for t in cdp("Target.getTargets")["targetInfos"]):
                raise StalePage("The selected tab was closed. Observe again.")
            self.bind(target)
            self.pending_popup = None
            self.after_input = None
            self.call("Emulation.setFocusEmulationEnabled", enabled=True)
            return {"executed": action["id"]}
        if action["kind"] == "click":
            self.pending_popup = None
        if action["kind"] == "wait":
            time.sleep(0.1)
        result = browser_operation({"operation": "act", "session": self.session, "action": action, "text": text})
        self.after_input = action if action["kind"] != "wait" else None
        return result

    def close(self):
        targets = getattr(
            self, "created_targets", getattr(self, "owned_targets", {self.target} if self.target else set())
        )
        for target in list(targets):
            try:
                cdp("Target.closeTarget", targetId=target)
            except RuntimeError as error:
                if "No target with given id found" not in str(error):
                    raise
            targets.discard(target)
            getattr(self, "sessions", {}).pop(target, None)
            getattr(self, "scripts", {}).pop(target, None)
        self.detach()
        self.target = None

    def detach(self):
        # Removing the task control never closes pages adopted from the user's browser.
        for target, session in list(getattr(self, "sessions", {}).items()):
            try:
                cdp(
                    "Runtime.evaluate",
                    session_id=session,
                    expression="window.__jevBridge && (window.__jevBridge.enabled=false)",
                )
                if target in self.scripts:
                    cdp("Page.removeScriptToEvaluateOnNewDocument", session_id=session, identifier=self.scripts[target])
                cdp("Emulation.setFocusEmulationEnabled", session_id=session, enabled=False)
                cdp("Target.detachFromTarget", sessionId=session)
            except RuntimeError:
                pass  # The tab may have been closed by its owner.
        if hasattr(self, "sessions"):
            self.sessions.clear()
            self.scripts.clear()
        self.pending_popup = None


def fingerprint(state):
    content = {k: state[k] for k in ("url", "text", "actions", "scroll")}
    return hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()


def browser_operation(request):
    operation = request["operation"]
    session = request["session"]

    def call(method, **params):
        return cdp(method, session_id=session, **params)

    def evaluate(expression):
        result = call("Runtime.evaluate", expression=expression, returnByValue=True)
        if result.get("exceptionDetails"):
            if operation == "act" and request["action"]["kind"] == "select":
                raise RuntimeError("Dropdown execution was interrupted; inspect before retrying.")
            raise StalePage("Document changed during evaluation")
        return result.get("result", {}).get("value")

    if operation == "act":
        action = request["action"]
        kind = action["kind"]
        if kind == "scroll":
            center = evaluate("({x:innerWidth/2,y:innerHeight/2})")
            call("Input.dispatchMouseEvent", type="mouseWheel", **center, deltaX=0, deltaY=action["delta"])
        elif kind != "wait":
            if type(action["node"]) is not int:
                raise ValueError("Invalid observed node")
            # Code-owned node IDs refer to actual observed elements, never model-generated selectors.
            target = evaluate(
                """(action => {
              const e=window.__jevFast?.nodes.get(action.node);
              if (!e?.isConnected || e.matches(':disabled') || e.closest('[aria-disabled="true"],[inert]') ||
                  !e.checkVisibility({checkOpacity:true,checkVisibilityCSS:true})) return null;
              if (action.kind==='fill' && (e.readOnly || e.getAttribute('aria-readonly')==='true')) return null;
              const r=e.getBoundingClientRect(), x=r.x+r.width/2, y=r.y+r.height/2;
              if (!r.width || !r.height || x<0 || y<0 || x>=innerWidth || y>=innerHeight) return null;
              if (!e.contains(document.elementFromPoint(x,y))) return null;
              if (action.kind==='select') {
                if (e.tagName!=='SELECT' || ![...e.options].some(o=>o.value===action.value &&
                    !o.disabled && !o.closest('optgroup[disabled]'))) return null;
                e.value=action.value;
                e.dispatchEvent(new Event('input',{bubbles:true}));
                e.dispatchEvent(new Event('change',{bubbles:true}));
              }
              return {x,y};
            })("""
                + json.dumps(action)
                + ")"
            )
            if target is None:
                if kind == "select":
                    raise RuntimeError("Dropdown execution was not confirmed; inspect before retrying.")
                raise StalePage("Target changed or is covered. Observe again.")
            if kind != "select":
                x, y = target["x"], target["y"]
                for event in ("mousePressed", "mouseReleased"):
                    call("Input.dispatchMouseEvent", type=event, x=x, y=y, button="left", clickCount=1)
                if kind == "fill":
                    call(
                        "Input.dispatchKeyEvent",
                        type="keyDown",
                        key="a",
                        code="KeyA",
                        modifiers=4 if sys.platform == "darwin" else 2,
                        commands=["selectAll"],
                    )
                    call(
                        "Input.dispatchKeyEvent",
                        type="keyUp",
                        key="a",
                        code="KeyA",
                        modifiers=4 if sys.platform == "darwin" else 2,
                    )
                    call("Input.insertText", text=request["text"])
        return {"executed": action["id"]}

    info = evaluate(READ_STATE)
    if info is None:
        raise StalePage("Document is navigating")
    info["fingerprint"] = fingerprint(info)
    if request.get("screenshot", True):
        info["screenshot"] = call("Page.captureScreenshot", format="jpeg", quality=72)["data"]
    return info
