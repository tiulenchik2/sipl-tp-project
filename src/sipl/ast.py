from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, TypeAlias

from sipl.diagnostics import SourceSpan

ArithOp: TypeAlias = Literal["+", "-", "*"]
CompareOp: TypeAlias = Literal["=", ">"]


@dataclass(frozen=True)
class NumExpr:
    value: int
    span: SourceSpan

    def to_dict(self) -> dict[str, Any]:
        return {"kind": "NumExpr", "value": self.value, "span": self.span.to_dict()}


@dataclass(frozen=True)
class VarExpr:
    name: str
    span: SourceSpan

    def to_dict(self) -> dict[str, Any]:
        return {"kind": "VarExpr", "name": self.name, "span": self.span.to_dict()}


@dataclass(frozen=True)
class BinOpExpr:
    op: ArithOp
    left: AExpr
    right: AExpr
    span: SourceSpan

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "BinOpExpr",
            "op": self.op,
            "left": self.left.to_dict(),
            "right": self.right.to_dict(),
            "span": self.span.to_dict(),
        }


AExpr: TypeAlias = NumExpr | VarExpr | BinOpExpr


@dataclass(frozen=True)
class CompareExpr:
    op: CompareOp
    left: AExpr
    right: AExpr
    span: SourceSpan

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "CompareExpr",
            "op": self.op,
            "left": self.left.to_dict(),
            "right": self.right.to_dict(),
            "span": self.span.to_dict(),
        }


@dataclass(frozen=True)
class OrExpr:
    left: BExpr
    right: BExpr
    span: SourceSpan

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "OrExpr",
            "left": self.left.to_dict(),
            "right": self.right.to_dict(),
            "span": self.span.to_dict(),
        }


@dataclass(frozen=True)
class NotExpr:
    operand: BExpr
    span: SourceSpan

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "NotExpr",
            "operand": self.operand.to_dict(),
            "span": self.span.to_dict(),
        }


BExpr: TypeAlias = CompareExpr | OrExpr | NotExpr


@dataclass(frozen=True)
class AssignStmt:
    var: str
    expr: AExpr
    span: SourceSpan

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "AssignStmt",
            "var": self.var,
            "expr": self.expr.to_dict(),
            "span": self.span.to_dict(),
        }


@dataclass(frozen=True)
class SeqStmt:
    first: Stmt
    second: Stmt
    span: SourceSpan

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "SeqStmt",
            "first": self.first.to_dict(),
            "second": self.second.to_dict(),
            "span": self.span.to_dict(),
        }


@dataclass(frozen=True)
class IfStmt:
    condition: BExpr
    then_branch: Stmt
    else_branch: Stmt
    span: SourceSpan

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "IfStmt",
            "condition": self.condition.to_dict(),
            "then_branch": self.then_branch.to_dict(),
            "else_branch": self.else_branch.to_dict(),
            "span": self.span.to_dict(),
        }


@dataclass(frozen=True)
class WhileStmt:
    condition: BExpr
    body: Stmt
    span: SourceSpan

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "WhileStmt",
            "condition": self.condition.to_dict(),
            "body": self.body.to_dict(),
            "span": self.span.to_dict(),
        }


@dataclass(frozen=True)
class BlockStmt:
    body: Stmt
    span: SourceSpan

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "BlockStmt",
            "body": self.body.to_dict(),
            "span": self.span.to_dict(),
        }


@dataclass(frozen=True)
class SkipStmt:
    span: SourceSpan

    def to_dict(self) -> dict[str, Any]:
        return {"kind": "SkipStmt", "span": self.span.to_dict()}


Stmt: TypeAlias = AssignStmt | SeqStmt | IfStmt | WhileStmt | BlockStmt | SkipStmt


@dataclass(frozen=True)
class Program:
    body: Stmt
    span: SourceSpan

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "Program",
            "body": self.body.to_dict(),
            "span": self.span.to_dict(),
        }