from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from sipl.cli import SCHEMA_VERSION, ExitCode, main

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples"


def _run_subprocess(*args: str, stdin_text: str | None = None) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    return subprocess.run(
        [sys.executable, "-m", "sipl", *args],
        input=stdin_text,
        text=True,
        encoding="utf-8",
        capture_output=True,
        env=env,
        check=False,
    )


def test_cli_parse_json_and_text(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["parse", str(EXAMPLES / "pow.sipl"), "--json"])
    assert code == ExitCode.OK
    data = json.loads(capsys.readouterr().out)
    assert data["schema_version"] == SCHEMA_VERSION
    assert data["command"] == "parse"
    assert data["ok"] is True
    assert data["ast"]["kind"] == "Program"

    code_text = main(["parse", str(EXAMPLES / "pow.sipl")])
    assert code_text == ExitCode.OK
    assert '"kind": "Program"' in capsys.readouterr().out


def test_cli_check_valid_and_invalid(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["check", str(EXAMPLES / "gcd.sipl")]) == ExitCode.OK
    assert capsys.readouterr().out.strip() == "OK"

    assert main(["check", str(EXAMPLES / "gcd.sipl"), "--json"]) == ExitCode.OK
    ok_payload = json.loads(capsys.readouterr().out)
    assert ok_payload["ok"] is True
    assert ok_payload["diagnostics"] == []

    broken = tmp_path / "broken.sipl"
    broken.write_text("begin\n  X := 1;\nend", encoding="utf-8")

    assert main(["check", str(broken), "--json"]) == ExitCode.SYNTAX_ERROR
    err_payload = json.loads(capsys.readouterr().out)
    assert err_payload["ok"] is False
    assert err_payload["exit_code"] == ExitCode.SYNTAX_ERROR
    assert err_payload["diagnostics"][0]["span"]["start_line"] == 3

    assert main(["check", str(broken)]) == ExitCode.SYNTAX_ERROR
    assert "[E1" in capsys.readouterr().err


def test_cli_run_and_state_options(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["run", str(EXAMPLES / "pow.sipl"), "--var", "X=5", "--var", "Y=2", "--json"])
    assert code == ExitCode.OK
    data = json.loads(capsys.readouterr().out)
    assert data["ok"] is True
    assert data["status"] == "completed"
    assert data["state"] == {"X": 5, "Y": 0, "R": 25}

    code_state = main(
        [
            "run",
            str(EXAMPLES / "div.sipl"),
            "--state",
            '{"X": 7, "Y": 4}',
        ]
    )
    assert code_state == ExitCode.OK
    out = capsys.readouterr().out
    assert "R = 1" in out
    assert "X = 3" in out


def test_cli_trace_json_and_text(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["trace", str(EXAMPLES / "pow.sipl"), "--var", "X=2", "--var", "Y=1", "--json"])
    assert code == ExitCode.OK
    data = json.loads(capsys.readouterr().out)
    assert data["command"] == "trace"
    assert data["ok"] is True
    assert data["state"]["R"] == 2
    assert len(data["events"]) > 0
    assert data["events"][-1]["event"] == "Finished"

    code_text = main(["trace", str(EXAMPLES / "pow.sipl"), "--var", "X=2", "--var", "Y=1"])
    assert code_text == ExitCode.OK
    lines = capsys.readouterr().out.strip().splitlines()
    assert json.loads(lines[-1])["event"] == "Finished"


def test_cli_runtime_and_step_limit_exit_codes(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    code_undef = main(["run", str(EXAMPLES / "pow.sipl"), "--json"])
    assert code_undef == ExitCode.RUNTIME_ERROR
    undef_data = json.loads(capsys.readouterr().out)
    assert undef_data["ok"] is False
    assert undef_data["diagnostics"][0]["code"] == "E2001"

    inf_file = tmp_path / "inf.sipl"
    inf_file.write_text("begin while 1 = 1 do skip end", encoding="utf-8")

    code_limit = main(["trace", str(inf_file), "--max-steps", "10", "--json"])
    assert code_limit == ExitCode.STEP_LIMIT_ERROR
    limit_data = json.loads(capsys.readouterr().out)
    assert limit_data["ok"] is False
    assert limit_data["diagnostics"][0]["code"] == "E2002"
    assert limit_data["events"][-1]["status"] == "error"


def test_cli_input_and_usage_errors(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    missing = tmp_path / "does_not_exist.sipl"
    assert main(["parse", str(missing), "--json"]) == ExitCode.USAGE_ERROR
    assert json.loads(capsys.readouterr().out)["exit_code"] == ExitCode.USAGE_ERROR

    assert main(["run", str(EXAMPLES / "pow.sipl"), "--var", "BADFORMAT"]) == ExitCode.USAGE_ERROR
    assert "Error:" in capsys.readouterr().err

    assert (
        main(["run", str(EXAMPLES / "pow.sipl"), "--state", "[1, 2]", "--json"])
        == ExitCode.USAGE_ERROR
    )
    assert json.loads(capsys.readouterr().out)["ok"] is False

    assert (
        main(["run", str(EXAMPLES / "pow.sipl"), "--max-steps", "0", "--json"])
        == ExitCode.USAGE_ERROR
    )
    assert json.loads(capsys.readouterr().out)["ok"] is False


def test_subprocess_integration_run_and_stdin() -> None:
    proc = _run_subprocess(
        "run",
        str(EXAMPLES / "gcd.sipl"),
        "--var",
        "M=8",
        "--var",
        "N=16",
        "--json",
    )
    assert proc.returncode == ExitCode.OK
    data = json.loads(proc.stdout)
    assert data["state"] == {"M": 8, "N": 8}

    proc_stdin = _run_subprocess("check", "-", "--json", stdin_text="begin skip end")
    assert proc_stdin.returncode == ExitCode.OK
    assert json.loads(proc_stdin.stdout)["ok"] is True

    proc_err = _run_subprocess("parse", "-", "--json", stdin_text="begin X := end")
    assert proc_err.returncode == ExitCode.SYNTAX_ERROR
    assert json.loads(proc_err.stdout)["ok"] is False