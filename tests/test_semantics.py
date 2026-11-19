from __future__ import annotations

import json
from pathlib import Path

import pytest

from sipl import build_semantic_term, format_term
from sipl.cli import ExitCode, main
from sipl.semantics import IdTerm, SeqTerm

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples"
GOLDEN = ROOT / "tests" / "golden"


@pytest.mark.parametrize("name", ["pow", "gcd", "div"])
def test_golden_semantic_terms(name: str) -> None:
    source = (EXAMPLES / f"{name}.sipl").read_text(encoding="utf-8")
    expected = (GOLDEN / f"{name}.term.txt").read_text(encoding="utf-8").strip()

    built = build_semantic_term(source)
    assert built.format(style="course") == expected


def test_all_basic_operators_and_ascii_style() -> None:
    source = (
        "begin "
        "skip; "
        "if not (X = -1) or Y > 2 then begin Z := X + Y * 3 end else Z := X - 1; "
        "while Z > 0 do Z := Z - 1 "
        "end"
    )
    built = build_semantic_term(source)
    assert isinstance(built.term, SeqTerm)
    assert isinstance(built.term.first, SeqTerm)
    assert isinstance(built.term.first.first, IdTerm)

    ascii_out = format_term(built.term, style="ascii")
    expected_ascii = (
        "id . IF(S^2(or, S^1(neg, S^2(eq, X=>, const(-1))), S^2(gr, Y=>, const(2))), "
        "(AS^Z(S^2(add, X=>, S^2(mult, Y=>, const(3))))), "
        "AS^Z(S^2(sub, X=>, const(1)))) . "
        "WH(S^2(gr, Z=>, const(0)), AS^Z(S^2(sub, Z=>, const(1))))"
    )
    assert ascii_out == expected_ascii


def test_rule_application_trace_and_json_contract() -> None:
    built = build_semantic_term("begin R := 1; skip end")
    rules = [step.rule for step in built.steps]
    assert rules == ["NS_Prog", "NS_Stm_Seq", "NS_Stm_As", "NS_A_Num", "NS_Stm_skip"]

    payload = built.to_dict(style="course")
    serialized = json.dumps(payload, ensure_ascii=False)
    parsed = json.loads(serialized)
    assert parsed["style"] == "course"
    assert parsed["term"]["kind"] == "SeqTerm"
    assert len(parsed["steps"]) == 5


def test_cli_sem_text_steps_json_and_errors(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    pow_file = str(EXAMPLES / "pow.sipl")

    assert main(["sem", pow_file, "--steps"]) == ExitCode.OK
    out = capsys.readouterr().out
    assert "AS^R(" in out
    assert "Applied rules:" in out
    assert "NS_Prog" in out

    assert main(["sem", pow_file, "--style", "ascii", "--json"]) == ExitCode.OK
    data = json.loads(capsys.readouterr().out)
    assert data["ok"] is True
    assert data["command"] == "sem"
    assert data["style"] == "ascii"
    assert "const(1)" in data["notation"]

    broken = tmp_path / "broken.sipl"
    broken.write_text("begin R := end", encoding="utf-8")
    assert main(["sem", str(broken), "--json"]) == ExitCode.SYNTAX_ERROR
    err_data = json.loads(capsys.readouterr().out)
    assert err_data["ok"] is False
    assert err_data["diagnostics"][0]["code"].startswith("E1")