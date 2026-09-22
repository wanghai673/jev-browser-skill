"""Check API and Chrome readiness without reading or changing browser pages."""

import json
import os
import time
from pathlib import Path

import httpx
from websockets.sync.client import connect

from .config import load_environment
from .model import validate_choice


def check_api():
    key = os.environ.get("TYPESAFE_API_KEY", "").strip()
    model = os.environ.get("TYPESAFE_MODEL", "jev-latest")
    if not key or key == "your_typesafe_api_key":
        return {"status": "missing", "hint": "Configure TYPESAFE_API_KEY in the Jev configuration file."}
    payload = {
        "model": model,
        "state": {"purpose": "Configuration check. No browser data is included."},
        "questions": {
            "check": {
                "type": "choice",
                "criteria": {"READY": "The configuration test is ready."},
                "instructions": "Choose READY.",
            }
        },
    }
    try:
        response = httpx.post(
            "https://api.typesafe.ai/v1/systemone",
            headers={"Authorization": f"Bearer {key}"},
            json=payload,
            timeout=15,
            follow_redirects=False,
        )
        if response.status_code != 200:
            hints = {
                401: "Check the Jev API key.",
                403: "Check API key permissions and model access.",
                429: "Check API quota or retry after the rate limit clears.",
            }
            return {
                "status": "error", "http_status": response.status_code,
                "hint": hints.get(response.status_code, "The API did not accept the test request."),
            }
        validate_choice(response.json()["answers"]["check"], {"READY"})
        return {"status": "ready", "model": model}
    except Exception as error:
        # Provider bodies and exception messages can contain credentials; never return them.
        return {"status": "error", "error_type": type(error).__name__, "hint": "Check API connectivity and response."}


def check_chrome():
    profile = Path.home() / "Library/Application Support/Google/Chrome/DevToolsActivePort"
    hint = "Open Chrome, enable chrome://inspect/#remote-debugging, and allow its debugging connection prompt."
    try:
        if not profile.exists():
            return {"status": "missing", "hint": hint}
        port, path = profile.read_text().splitlines()[:2]
        port = int(port)
        if not 1 <= port <= 65535 or not path.startswith("/devtools/browser/"):
            raise ValueError("Invalid Chrome debugging endpoint")
        with connect(f"ws://127.0.0.1:{port}{path}", open_timeout=5, close_timeout=1) as socket:
            socket.send(json.dumps({"id": 1, "method": "Browser.getVersion"}))
            expires = time.monotonic() + 5
            while True:
                remaining = expires - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("Chrome did not respond")
                reply = json.loads(socket.recv(timeout=remaining))
                if reply.get("id") == 1:
                    if reply.get("error") or not reply.get("result", {}).get("protocolVersion"):
                        raise ValueError("Chrome debugging check failed")
                    return {"status": "ready"}
    except Exception as error:
        return {"status": "error", "error_type": type(error).__name__, "hint": hint}


def run_doctor():
    try:
        load_environment()
        api = check_api()
    except Exception as error:
        api = {"status": "error", "error_type": type(error).__name__, "hint": "Check Jev configuration file access."}
    checks = {"jev_api": api, "chrome": check_chrome()}
    return {
        "status": "ready" if all(check["status"] == "ready" for check in checks.values()) else "error",
        "checks": checks,
    }
