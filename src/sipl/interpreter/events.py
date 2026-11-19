from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, TypeAlias

from sipl.diagnostics import Diagnostic, SourceSpan


@dataclass(frozen=True)
class BeforeStatementEvent:
    step: int
    stmt_kind: str
    span: SourceSpan
    state: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "event": "BeforeStatement",
            "step": self.step,
            "stmt_kind": self.stmt_kind,
            "span": self.span.to_dict(),
            "state": dict(self.state),
        }


@dataclass(frozen=True)
class AfterStatementEvent:
    step: int
    stmt_kind: str
    span: SourceSpan
    state: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "event": "AfterStatement",
            "step": self.step,
            "stmt_kind": self.stmt_kind,
            "span": self.span.to_dict(),
            "state": dict(self.state),
        }


@dataclass(frozen=True)
class VarChangedEvent:
    step: int
    var: str
    old_value: int | None
    new_value: int
    span: SourceSpan

    def to_dict(self) -> dict[str, Any]:
        return {
            "event": "VarChanged",
            "step": self.step,
            "var": self.var,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "span": self.span.to_dict(),
        }


@dataclass(frozen=True)
class ConditionCheckedEvent:
    step: int
    context: Literal["if", "while"]
    result: bool
    span: SourceSpan

    def to_dict(self) -> dict[str, Any]:
        return {
            "event": "ConditionChecked",
            "step": self.step,
            "context": self.context,
            "result": self.result,
            "span": self.span.to_dict(),
        }


@dataclass(frozen=True)
class FinishedEvent:
    steps: int
    status: Literal["completed", "error"]
    state: dict[str, int]
    error: Diagnostic | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "event": "Finished",
            "steps": self.steps,
            "status": self.status,
            "state": dict(self.state),
            "error": self.error.to_dict() if self.error is not None else None,
        }


TraceEvent: TypeAlias = (
    BeforeStatementEvent
    | AfterStatementEvent
    | VarChangedEvent
    | ConditionCheckedEvent
    | FinishedEvent
)


@dataclass(frozen=True)
class ExecutionResult:
    state: dict[str, int]
    steps: int
    events: tuple[TraceEvent, ...]
    status: Literal["completed", "error"] = "completed"
    error: Diagnostic | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "steps": self.steps,
            "state": dict(self.state),
            "error": self.error.to_dict() if self.error is not None else None,
            "events": [event.to_dict() for event in self.events],
        }