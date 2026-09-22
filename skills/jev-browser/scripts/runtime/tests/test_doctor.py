import json
from contextlib import contextmanager

import httpx
import pytest

from jev_ultrafast import cli, doctor


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-secret-do-not-print")
    monkeypatch.setenv("TYPESAFE_MODEL", "test-model")
    monkeypatch.setenv("JEV_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(doctor.Path, "home", lambda: tmp_path)

    def unexpected(*args, **kwargs):
        pytest.fail("Unexpected network access")

    monkeypatch.setattr(doctor.httpx, "post", unexpected)
    monkeypatch.setattr(doctor, "connect", unexpected)


def ready_api(monkeypatch):
    def post(url, **kwargs):
        assert url == "https://api.typesafe.ai/v1/systemone"
        assert kwargs["headers"]["Authorization"] == "Bearer test-secret-do-not-print"
        assert kwargs["json"]["model"] == "test-model"
        assert "page" not in kwargs["json"]["state"]
        assert not kwargs["follow_redirects"]
        return httpx.Response(200, json={
            "answers": {"check": {"choice": "READY", "probabilities": {"READY": 1}, "confidence": 1}}
        })

    monkeypatch.setattr(doctor.httpx, "post", post)


def chrome_file(tmp_path):
    path = tmp_path / "Library/Application Support/Google/Chrome/DevToolsActivePort"
    path.parent.mkdir(parents=True)
    path.write_text("9222\n/devtools/browser/test")
    return path


def test_live_checks_report_ready_without_page_operations(monkeypatch, tmp_path):
    ready_api(monkeypatch)
    chrome_file(tmp_path)
    messages = []

    class Socket:
        def send(self, message):
            messages.append(json.loads(message))

        def recv(self, **kwargs):
            return json.dumps({"id": 1, "result": {"protocolVersion": "1.3"}})

    @contextmanager
    def connect(url, **kwargs):
        assert url == "ws://127.0.0.1:9222/devtools/browser/test"
        yield Socket()

    monkeypatch.setattr(doctor, "connect", connect)
    result = doctor.run_doctor()
    assert result["status"] == "ready"
    assert messages == [{"id": 1, "method": "Browser.getVersion"}]
    assert "test-secret" not in json.dumps(result)


@pytest.mark.parametrize("key", ["", "your_typesafe_api_key"])
def test_missing_key_skips_api(monkeypatch, key):
    monkeypatch.setenv("TYPESAFE_API_KEY", key)
    assert doctor.run_doctor() == {
        "status": "error",
        "checks": {
            "jev_api": {"status": "missing", "hint": "Configure TYPESAFE_API_KEY in the Jev configuration file."},
            "chrome": doctor.check_chrome(),
        },
    }


@pytest.mark.parametrize("status", [401, 403, 429, 500, 302])
def test_api_failure_is_redacted(monkeypatch, status):
    monkeypatch.setattr(doctor.httpx, "post", lambda *a, **kw: httpx.Response(status, text="test-secret-do-not-print"))
    result = doctor.check_api()
    assert result["status"] == "error"
    assert result["http_status"] == status
    assert "test-secret" not in json.dumps(result)


def test_invalid_api_body_is_not_ready(monkeypatch):
    monkeypatch.setattr(doctor.httpx, "post", lambda *a, **kw: httpx.Response(200, json={"error": "test-secret"}))
    assert doctor.check_api()["status"] == "error"


def test_stale_chrome_file_is_not_ready(monkeypatch, tmp_path):
    chrome_file(tmp_path)

    def connect(*args, **kwargs):
        raise ConnectionRefusedError("test-secret-do-not-print")

    monkeypatch.setattr(doctor, "connect", connect)
    result = doctor.check_chrome()
    assert result["status"] == "error"
    assert "test-secret" not in json.dumps(result)


def test_missing_chrome_does_not_skip_api(monkeypatch):
    ready_api(monkeypatch)
    result = doctor.run_doctor()
    assert result["status"] == "error"
    assert result["checks"]["jev_api"]["status"] == "ready"
    assert result["checks"]["chrome"]["status"] == "missing"


def test_cli_doctor_does_not_enter_browser_runner(monkeypatch, capsys):
    def unexpected():
        pytest.fail("Doctor must not start the browser harness")

    monkeypatch.setattr(cli, "configure_browser", unexpected)
    monkeypatch.setattr(cli, "execution_lock", unexpected)
    monkeypatch.setattr(doctor, "run_doctor", lambda: {"status": "ready", "checks": {}})
    cli.main(["doctor"])
    assert json.loads(capsys.readouterr().out)["status"] == "ready"


def test_cli_doctor_failure_exit_code(monkeypatch, capsys):
    monkeypatch.setattr(doctor, "run_doctor", lambda: {"status": "error", "checks": {}})
    with pytest.raises(SystemExit) as error:
        cli.main(["doctor"])
    assert error.value.code == 1
    assert json.loads(capsys.readouterr().out)["status"] == "error"
