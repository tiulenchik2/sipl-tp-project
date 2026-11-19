from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, TypeAlias

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
from sipl.diagnostics import SourceSpan
from sipl.parser import parse

NotationStyle: TypeAlias = Literal["course", "ascii"]
BaseFunc: TypeAlias = Literal["add", "sub", "mult", "eq", "gr", "or", "neg"]

_ARITH_FUNC_MAP: dict[str, tuple[Literal["add", "sub", "mult"], str]] = {
    "+": ("add", "NS_A_Add"),
    "-": ("sub", "NS_A_Sub"),
    "*": ("mult", "NS_A_Mult"),
}

_COMPARE_FUNC_MAP: dict[str, tuple[Literal["eq", "gr"], str]] = {
    "=": ("eq", "NS_B_eq"),
    ">": ("gr", "NS_B_gr"),
}


@dataclass(frozen=True)
class RuleStep:
    """Single rewriting rule application recorded during term construction."""

    rule: str
    ast_kind: str
    span: SourceSpan

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule": self.rule,
            "ast_kind": self.ast_kind,
            "span": self.span.to_dict(),
        }


@dataclass(frozen=True)
class ConstTerm:
    value: int

    def to_dict(self) -> dict[str, Any]:
        return {"kind": "ConstTerm", "value": self.value}


@dataclass(frozen=True)
class DerefTerm:
    var: str

    def to_dict(self) -> dict[str, Any]:
        return {"kind": "DerefTerm", "var": self.var}


@dataclass(frozen=True)
class SuperpositionTerm:
    arity: Literal[1, 2]
    func: BaseFunc
    args: tuple[ExprTerm, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "SuperpositionTerm",
            "arity": self.arity,
            "func": self.func,
            "args": [arg.to_dict() for arg in self.args],
        }


ExprTerm: TypeAlias = ConstTerm | DerefTerm | SuperpositionTerm


@dataclass(frozen=True)
class AssignTerm:
    var: str
    expr: ExprTerm

    def to_dict(self) -> dict[str, Any]:
        return {"kind": "AssignTerm", "var": self.var, "expr": self.expr.to_dict()}


@dataclass(frozen=True)
class SeqTerm:
    first: StmtTerm
    second: StmtTerm

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "SeqTerm",
            "first": self.first.to_dict(),
            "second": self.second.to_dict(),
        }


@dataclass(frozen=True)
class IfTerm:
    condition: ExprTerm
    then_term: StmtTerm
    else_term: StmtTerm

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "IfTerm",
            "condition": self.condition.to_dict(),
            "then_term": self.then_term.to_dict(),
            "else_term": self.else_term.to_dict(),
        }


@dataclass(frozen=True)
class WhileTerm:
    condition: ExprTerm
    body_term: StmtTerm

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "WhileTerm",
            "condition": self.condition.to_dict(),
            "body_term": self.body_term.to_dict(),
        }


@dataclass(frozen=True)
class BlockTerm:
    body: StmtTerm

    def to_dict(self) -> dict[str, Any]:
        return {"kind": "BlockTerm", "body": self.body.to_dict()}


@dataclass(frozen=True)
class IdTerm:
    def to_dict(self) -> dict[str, Any]:
        return {"kind": "IdTerm"}


StmtTerm: TypeAlias = AssignTerm | SeqTerm | IfTerm | WhileTerm | BlockTerm | IdTerm
SemanticTerm: TypeAlias = ExprTerm | StmtTerm


@dataclass(frozen=True)
class SemanticBuildResult:
    term: StmtTerm
    steps: tuple[RuleStep, ...]

    def format(self, style: NotationStyle = "course") -> str:
        return format_term(self.term, style=style)

    def to_dict(self, style: NotationStyle = "course") -> dict[str, Any]:
        return {
            "notation": self.format(style=style),
            "style": style,
            "term": self.term.to_dict(),
            "steps": [step.to_dict() for step in self.steps],
        }


def _overline_number(value: int) -> str:
    return "".join(f"{ch}\u0304" for ch in str(value))


def format_term(term: SemanticTerm, style: NotationStyle = "course") -> str:
    """Format a semantic term in course Unicode notation or plain ASCII."""
    is_course = style == "course"

    match term:
        case ConstTerm(value=value):
            return _overline_number(value) if is_course else f"const({value})"
        case DerefTerm(var=var):
            return f"{var}\u21d2" if is_course else f"{var}=>"
        case SuperpositionTerm(arity=arity, func=func, args=args):
            if is_course:
                sup = "\u00b9" if arity == 1 else "\u00b2"
                head = f"S{sup}"
            else:
                head = f"S^{arity}"
            rendered_args = ", ".join(format_term(arg, style=style) for arg in args)
            return f"{head}({func}, {rendered_args})"
        case AssignTerm(var=var, expr=expr):
            return f"AS^{var}({format_term(expr, style=style)})"
        case SeqTerm(first=first, second=second):
            sep = " \u00b7 " if is_course else " . "
            return f"{format_term(first, style=style)}{sep}{format_term(second, style=style)}"
        case IfTerm(condition=cond, then_term=then_term, else_term=else_term):
            c_str = format_term(cond, style=style)
            t_str = format_term(then_term, style=style)
            e_str = format_term(else_term, style=style)
            return f"IF({c_str}, {t_str}, {e_str})"
        case WhileTerm(condition=cond, body_term=body_term):
            c_str = format_term(cond, style=style)
            b_str = format_term(body_term, style=style)
            return f"WH({c_str}, {b_str})"
        case BlockTerm(body=body):
            return f"({format_term(body, style=style)})"
        case IdTerm():
            return "id"
        case _:
            raise TypeError(f"Unsupported semantic term node: {term!r}")


class _TermBuilder:
    def __init__(self) -> None:
        self._steps: list[RuleStep] = []

    def build_program(self, program: Program) -> SemanticBuildResult:
        self._record("NS_Prog", program)
        body_term = self._build_stmt(program.body)
        return SemanticBuildResult(term=body_term, steps=tuple(self._steps))

    def _record(self, rule: str, node: Program | Stmt | AExpr | BExpr) -> None:
        self._steps.append(RuleStep(rule=rule, ast_kind=type(node).__name__, span=node.span))

    def _build_stmt(self, stmt: Stmt) -> StmtTerm:
        match stmt:
            case AssignStmt(var=var, expr=expr):
                self._record("NS_Stm_As", stmt)
                return AssignTerm(var=var, expr=self._build_aexp(expr))
            case SeqStmt(first=first, second=second):
                self._record("NS_Stm_Seq", stmt)
                return SeqTerm(first=self._build_stmt(first), second=self._build_stmt(second))
            case IfStmt(condition=cond, then_branch=then_b, else_branch=else_b):
                self._record("NS_Stm_If", stmt)
                return IfTerm(
                    condition=self._build_bexp(cond),
                    then_term=self._build_stmt(then_b),
                    else_term=self._build_stmt(else_b),
                )
            case WhileStmt(condition=cond, body=body):
                self._record("NS_Stm_Wh", stmt)
                return WhileTerm(
                    condition=self._build_bexp(cond),
                    body_term=self._build_stmt(body),
                )
            case BlockStmt(body=body):
                self._record("NS_Stm_BE", stmt)
                return BlockTerm(body=self._build_stmt(body))
            case SkipStmt():
                self._record("NS_Stm_skip", stmt)
                return IdTerm()
            case _:
                raise TypeError(f"Unsupported statement node: {stmt!r}")

    def _build_aexp(self, expr: AExpr) -> ExprTerm:
        match expr:
            case NumExpr(value=value):
                self._record("NS_A_Num", expr)
                return ConstTerm(value=value)
            case VarExpr(name=name):
                self._record("NS_A_Var", expr)
                return DerefTerm(var=name)
            case BinOpExpr(op=op, left=left, right=right):
                func, rule = _ARITH_FUNC_MAP[op]
                self._record(rule, expr)
                return SuperpositionTerm(
                    arity=2,
                    func=func,
                    args=(self._build_aexp(left), self._build_aexp(right)),
                )
            case _:
                raise TypeError(f"Unsupported arithmetic expression: {expr!r}")

    def _build_bexp(self, expr: BExpr) -> ExprTerm:
        match expr:
            case CompareExpr(op=op, left=left, right=right):
                func, rule = _COMPARE_FUNC_MAP[op]
                self._record(rule, expr)
                return SuperpositionTerm(
                    arity=2,
                    func=func,
                    args=(self._build_aexp(left), self._build_aexp(right)),
                )
            case OrExpr(left=left, right=right):
                self._record("NS_B_or", expr)
                return SuperpositionTerm(
                    arity=2,
                    func="or",
                    args=(self._build_bexp(left), self._build_bexp(right)),
                )
            case NotExpr(operand=operand):
                self._record("NS_B_neg", expr)
                return SuperpositionTerm(
                    arity=1,
                    func="neg",
                    args=(self._build_bexp(operand),),
                )
            case _:
                raise TypeError(f"Unsupported boolean expression: {expr!r}")


def build_semantic_term(source_or_program: str | Program) -> SemanticBuildResult:
    """Recursively construct the course semantic term from a SIPL AST or source string."""
    program = parse(source_or_program) if isinstance(source_or_program, str) else source_or_program
    return _TermBuilder().build_program(program)