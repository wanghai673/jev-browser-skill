"""One invocation, one task. No task server or resumable session."""

import argparse
import fcntl
import json
import math
import os
import signal
from contextlib import contextmanager
from pathlib import Path

from .config import load_environment, state_dir


@contextmanager
def execution_lock():
    folder = state_dir()
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    with open(folder / "run.lock", "a", opener=lambda p, f: os.open(p, f, 0o600)) as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("Another Jev call is running; wait for that call to finish") from None
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def configure_browser():
    # Set the transport before importing Browser Harness. Never restart Chrome.
    profile = Path.home() / "Library/Application Support/Google/Chrome/DevToolsActivePort"
    if not profile.exists():
        raise RuntimeError("Enable chrome://inspect/#remote-debugging in your existing Chrome first")
    port, path = profile.read_text().splitlines()[:2]
    os.environ["BU_NAME"] = "jev-user-chrome"
    os.environ["BU_CDP_WS"] = f"ws://127.0.0.1:{int(port)}{path}"
    os.environ["BH_RECORD"] = "0"
    load_environment()


@contextmanager
def deadline(seconds):
    def expired(_signum, _frame):
        raise TimeoutError("The whole-call time limit was reached")

    def interrupted(_signum, _frame):
        raise KeyboardInterrupt

    handlers = {sig: signal.getsignal(sig) for sig in (signal.SIGALRM, signal.SIGTERM)}
    signal.signal(signal.SIGALRM, expired)
    signal.signal(signal.SIGTERM, interrupted)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        for sig, handler in handlers.items():
            signal.signal(sig, handler)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run a fresh Jev browser task until DONE or failure")
    parser.add_argument("command", choices=["run", "tabs"])
    parser.add_argument("--url", help="Known starting URL; use --target-id for an explicitly selected tab")
    parser.add_argument("--target-id")
    parser.add_argument("--goal", help="The complete user request, including required result evidence")
    parser.add_argument("--inputs", default="[]", help='JSON list of {"value": "literal", "purpose": "field use"}')
    parser.add_argument("--show", action="store_true", help="Show the final page when the user asked to open it")
    parser.add_argument("--max-actions", type=int, default=200, help="Whole-call failure limit, not a handoff window")
    parser.add_argument("--max-seconds", type=float, default=300, help="Whole-call failure limit, not a handoff window")
    args = parser.parse_args(argv)
    if args.command == "run":
        if not args.goal or not args.goal.strip() or not (bool(args.url) ^ bool(args.target_id)):
            parser.error("run requires --goal and exactly one of --url or --target-id")
        if (
            not 1 <= args.max_actions <= 1000
            or not math.isfinite(args.max_seconds)
            or not 1 <= args.max_seconds <= 3600
        ):
            parser.error("Use 1–1000 actions and 1–3600 seconds")
    try:
        with execution_lock():
            configure_browser()
            if args.command == "tabs":
                from .browser import cdp, ensure_daemon

                with deadline(30):
                    ensure_daemon()
                    tabs = cdp("Target.getTargets")["targetInfos"]
                result = {
                    "tabs": [
                        {"target_id": t["targetId"], "title": t.get("title", ""), "url": t.get("url", "")}
                        for t in tabs
                        if t.get("type") == "page"
                    ]
                }
            else:
                from .runner import run_task

                with deadline(args.max_seconds):
                    result = run_task(
                        args.url,
                        args.goal,
                        target_id=args.target_id,
                        inputs=json.loads(args.inputs),
                        show=args.show,
                        max_actions=args.max_actions,
                    )
        print(json.dumps(result, ensure_ascii=False))
        if result.get("status") == "error":
            raise SystemExit(1)
    except (Exception, KeyboardInterrupt) as error:
        print(json.dumps({"status": "error", "reason": f"{type(error).__name__}: {error}"}, ensure_ascii=False))
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
