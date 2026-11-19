from __future__ import annotations

from collections.abc import Callable, Mapping

from sipl.ast import (
    AExpr,
    AssignStmt,
    BExpr,
    BinOpExpr,
    BlockStmt,
    CompareExpr,
    IfStmt,
    NotExpr,
    NumExpr,
    OrExpr,
    Program,
    SeqStmt,
    SkipStmt,
    Stmt,
    VarExpr,
    WhileStmt,
)
from sipl.diagnostics import (
    Diagnostic,
    SiplRuntimeError,
    SourceSpan,
    StepLimitExceededError,
    UndefinedVariableError,
)
from sipl.interpreter.events import (
    AfterStatementEvent,
    BeforeStatementEvent,
    ConditionCheckedEvent,
    ExecutionResult,
    FinishedEvent,
    TraceEvent,
    VarChangedEvent,
)
from sipl.parser import parse

EventListener = Callable[[TraceEvent], None]


class Interpreter:
    """Tree-walking interpreter for SIPL with step-limit protection and event tracing."""

    def __init__(
        self,
        *,
        max_steps: int = 10_000,
        on_event: EventListener | None = None,
    ) -> None:
        if max_steps <= 0:
            raise ValueError("max_steps must be a positive integer.")
        self.max_steps = max_steps
        self._on_event = on_event
        self._state: dict[str, int] = {}
        self._steps: int = 0
        self._events: list[TraceEvent] = []

    def execute(
        self,
        program: Program,
        initial_state: Mapping[str, int] | None = None,
    ) -> ExecutionResult:
        self._state = dict(initial_state) if initial_state is not None else {}
        self._steps = 0
        self._events = []

        try:
            self._exec_stmt(program.body)
        except SiplRuntimeError as exc:
            self._emit(
                FinishedEvent(
                    steps=self._steps,
                    status="error",
                    state=dict(self._state),
                    error=exc.diagnostic,
                )
            )
            raise type(exc)(exc.diagnostic, events=tuple(self._events)) from None

        self._emit(
            FinishedEvent(
                steps=self._steps,
                status="completed",
                state=dict(self._state),
            )
        )
        return ExecutionResult(
            state=dict(self._state),
            steps=self._steps,
            events=tuple(self._events),
        )

    def _emit(self, event: TraceEvent) -> None:
        self._events.append(event)
        if self._on_event is not None:
            self._on_event(event)

    def _consume_step(self, span: SourceSpan) -> int:
        if self._steps >= self.max_steps:
            diag = Diagnostic(
                code="E2002",
                message=f"Execution exceeded maximum step limit ({self.max_steps}).",
                span=span,
            )
            raise StepLimitExceededError(diag)
        self._steps += 1
        return self._steps

    def _exec_stmt(self, stmt: Stmt) -> None:
        step = self._consume_step(stmt.span)
        stmt_kind = type(stmt).__name__
        self._emit(
            BeforeStatementEvent(
                step=step,
                stmt_kind=stmt_kind,
                span=stmt.span,
                state=dict(self._state),
            )
        )

        match stmt:
            case SkipStmt():
                pass
            case AssignStmt(var=var, expr=expr, span=span):
                new_value = self._eval_aexp(expr)
                old_value = self._state.get(var)
                self._state[var] = new_value
                self._emit(
                    VarChangedEvent(
                        step=step,
                        var=var,
                        old_value=old_value,
                        new_value=new_value,
                        span=span,
                    )
                )
            case SeqStmt(first=first, second=second):
                self._exec_stmt(first)
                self._exec_stmt(second)
            case BlockStmt(body=body):
                self._exec_stmt(body)
            case IfStmt(condition=cond, then_branch=then_branch, else_branch=else_branch):
                cond_val = self._eval_bexp(cond)
                self._emit(
                    ConditionCheckedEvent(
                        step=step,
                        context="if",
                        result=cond_val,
                        span=cond.span,
                    )
                )
                if cond_val:
                    self._exec_stmt(then_branch)
                else:
                    self._exec_stmt(else_branch)
            case WhileStmt(condition=cond, body=body):
                while True:
                    cond_val = self._eval_bexp(cond)
                    self._emit(
                        ConditionCheckedEvent(
                            step=self._steps,
                            context="while",
                            result=cond_val,
                            span=cond.span,
                        )
                    )
                    if not cond_val:
                        break
                    self._exec_stmt(body)
            case _:
                raise TypeError(f"Unsupported statement node: {stmt!r}")

        self._emit(
            AfterStatementEvent(
                step=self._steps,
                stmt_kind=stmt_kind,
                span=stmt.span,
                state=dict(self._state),
            )
        )

    def _eval_aexp(self, expr: AExpr) -> int:
        match expr:
            case NumExpr(value=value):
                return value
            case VarExpr(name=name, span=span):
                if name not in self._state:
                    diag = Diagnostic(
                        code="E2001",
                        message=f"Variable {name!r} is not defined in the current state.",
                        span=span,
                    )
                    raise UndefinedVariableError(diag)
                return self._state[name]
            case BinOpExpr(op=op, left=left, right=right):
                left_val = self._eval_aexp(left)
                right_val = self._eval_aexp(right)
                if op == "+":
                    return left_val + right_val
                if op == "-":
                    return left_val - right_val
                if op == "*":
                    return left_val * right_val
                raise ValueError(f"Unsupported arithmetic operator: {op!r}")
            case _:
                raise TypeError(f"Unsupported arithmetic expression: {expr!r}")

    def _eval_bexp(self, expr: BExpr) -> bool:
        match expr:
            case CompareExpr(op=op, left=left, right=right):
                left_val = self._eval_aexp(left)
                right_val = self._eval_aexp(right)
                if op == "=":
                    return left_val == right_val
                if op == ">":
                    return left_val > right_val
                raise ValueError(f"Unsupported comparison operator: {op!r}")
            case OrExpr(left=left, right=right):
                left_val = self._eval_bexp(left)
                right_val = self._eval_bexp(right)
                return left_val or right_val
            case NotExpr(operand=operand):
                return not self._eval_bexp(operand)
            case _:
                raise TypeError(f"Unsupported boolean expression: {expr!r}")


def execute(
    source_or_program: str | Program,
    initial_state: Mapping[str, int] | None = None,
    *,
    max_steps: int = 10_000,
    on_event: EventListener | None = None,
) -> ExecutionResult:
    """Parse (if needed) and execute a SIPL program, returning final state and trace."""
    program = parse(source_or_program) if isinstance(source_or_program, str) else source_or_program
    interpreter = Interpreter(max_steps=max_steps, on_event=on_event)
    return interpreter.execute(program, initial_state=initial_state)