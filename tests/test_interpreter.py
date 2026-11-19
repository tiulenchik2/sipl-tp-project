import json
from pathlib import Path

import pytest

from sipl import (
    Interpreter,
    StepLimitExceededError,
    UndefinedVariableError,
    execute,
)
from sipl.interpreter import (
    AfterStatementEvent,
    BeforeStatementEvent,
    ConditionCheckedEvent,
    FinishedEvent,
    TraceEvent,
    VarChangedEvent,
)

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples"


@pytest.mark.parametrize(
    ("x", "y", "expected_r"),
    [
        (5, 2, 25),
        (2, 10, 1024),
        (7, 0, 1),
    ],
)
def test_example_pow(x: int, y: int, expected_r: int) -> None:
    source = (EXAMPLES / "pow.sipl").read_text(encoding="utf-8")
    result = execute(source, {"X": x, "Y": y})
    assert result.status == "completed"
    assert result.state == {"X": x, "Y": 0, "R": expected_r}


@pytest.mark.parametrize(
    ("m", "n", "expected"),
    [
        (8, 16, 8),
        (48, 18, 6),
        (7, 7, 7),
    ],
)
def test_example_gcd(m: int, n: int, expected: int) -> None:
    source = (EXAMPLES / "gcd.sipl").read_text(encoding="utf-8")
    result = execute(source, {"M": m, "N": n})
    assert result.state == {"M": expected, "N": expected}


@pytest.mark.parametrize(
    ("x", "y", "expected_q", "expected_rem"),
    [
        (7, 4, 1, 3),
        (12, 3, 4, 0),
        (2, 5, 0, 2),
    ],
)
def test_example_div(x: int, y: int, expected_q: int, expected_rem: int) -> None:
    source = (EXAMPLES / "div.sipl").read_text(encoding="utf-8")
    result = execute(source, {"X": x, "Y": y})
    assert result.state == {"X": expected_rem, "Y": y, "R": expected_q}


def test_skip_block_and_if_branches() -> None:
    source = (
        "begin "
        "  skip; "
        "  if X > 0 then begin R := 10 - 3 - 2 end else R := -5 "
        "end"
    )
    res_true = execute(source, {"X": 1})
    assert res_true.state == {"X": 1, "R": 5}

    res_false = execute(source, {"X": 0})
    assert res_false.state == {"X": 0, "R": -5}


def test_boolean_operators_and_strict_partiality() -> None:
    source = "begin if not (X = 0) or Y > 1 then R := 1 else R := 0 end"
    assert execute(source, {"X": 0, "Y": 2}).state["R"] == 1
    assert execute(source, {"X": 0, "Y": 1}).state["R"] == 0

    # Strict semantics: undefined Y in right operand must fail even if left is True.
    with pytest.raises(UndefinedVariableError) as exc_info:
        execute(source, {"X": 5})
    assert exc_info.value.diagnostic.code == "E2001"
    assert "Y" in exc_info.value.diagnostic.message


def test_undefined_variable_reports_exact_span() -> None:
    source = "begin\n  R := Missing + 1\nend"
    with pytest.raises(UndefinedVariableError) as exc_info:
        execute(source)

    diag = exc_info.value.diagnostic
    assert diag.span.start_line == 2
    assert diag.span.start_col == 8
    assert isinstance(exc_info.value.events[-1], FinishedEvent)
    assert exc_info.value.events[-1].status == "error"


def test_infinite_loop_hits_step_limit() -> None:
    source = "begin while 1 = 1 do skip end"
    with pytest.raises(StepLimitExceededError) as exc_info:
        execute(source, max_steps=20)

    diag = exc_info.value.diagnostic
    assert diag.code == "E2002"
    assert "20" in diag.message
    assert isinstance(exc_info.value.events[-1], FinishedEvent)
    assert exc_info.value.events[-1].status == "error"


def test_invalid_max_steps_raises_value_error() -> None:
    with pytest.raises(ValueError):
        Interpreter(max_steps=0)


def test_trace_events_and_listener_and_json() -> None:
    source = "begin R := 1; while R > 0 do R := R - 1 end"
    streamed: list[TraceEvent] = []
    result = execute(source, on_event=streamed.append)

    assert tuple(streamed) == result.events
    assert any(isinstance(e, BeforeStatementEvent) for e in result.events)
    assert any(isinstance(e, AfterStatementEvent) for e in result.events)

    var_events = [e for e in result.events if isinstance(e, VarChangedEvent)]
    assert len(var_events) == 2
    assert var_events[0].var == "R"
    assert var_events[0].old_value is None
    assert var_events[0].new_value == 1
    assert var_events[1].old_value == 1
    assert var_events[1].new_value == 0

    cond_events = [e for e in result.events if isinstance(e, ConditionCheckedEvent)]
    assert [e.result for e in cond_events] == [True, False]
    assert all(e.context == "while" for e in cond_events)

    assert isinstance(result.events[-1], FinishedEvent)
    assert result.events[-1].status == "completed"

    # Earlier event snapshots must not be mutated by later assignments.
    first_before = next(e for e in result.events if isinstance(e, BeforeStatementEvent))
    assert first_before.state == {}

    serialized = json.dumps(result.to_dict())
    parsed = json.loads(serialized)
    assert parsed["status"] == "completed"
    assert parsed["state"] == {"R": 0}
    assert len(parsed["events"]) == len(result.events)