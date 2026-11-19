import json
from pathlib import Path

import pytest

from sipl import SiplSyntaxError, check_syntax, parse
from sipl.ast import (
    AssignStmt,
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
    VarExpr,
    WhileStmt,
)

ROOT = Path(__file__).resolve().parent.parent


def test_packaged_grammar_matches_spec() -> None:
    spec = (ROOT / "grammar" / "sipl.lark").read_text(encoding="utf-8")
    packaged = (ROOT / "src" / "sipl" / "sipl.lark").read_text(encoding="utf-8")
    assert packaged == spec


def test_parse_all_statement_and_expression_nodes() -> None:
    source = (
        "begin\n"
        "  R := -1;\n"
        "  if ¬X = 0 ∨ X > 5 then skip else begin X := X + 1 end;\n"
        "  while X > 0 do X := X - 1\n"
        "end"
    )
    prog = parse(source)
    assert isinstance(prog, Program)
    assert isinstance(prog.body, SeqStmt)
    assert isinstance(prog.body.first, SeqStmt)

    assign_stmt = prog.body.first.first
    if_stmt = prog.body.first.second
    while_stmt = prog.body.second

    assert isinstance(assign_stmt, AssignStmt)
    assert assign_stmt.var == "R"
    assert isinstance(assign_stmt.expr, NumExpr)
    assert assign_stmt.expr.value == -1

    assert isinstance(if_stmt, IfStmt)
    assert isinstance(if_stmt.condition, OrExpr)
    assert isinstance(if_stmt.condition.left, NotExpr)
    assert isinstance(if_stmt.condition.left.operand, CompareExpr)
    assert isinstance(if_stmt.then_branch, SkipStmt)
    assert isinstance(if_stmt.else_branch, BlockStmt)

    assert isinstance(while_stmt, WhileStmt)
    assert isinstance(while_stmt.condition, CompareExpr)
    assert while_stmt.condition.op == ">"


def test_arithmetic_precedence_and_left_associativity() -> None:
    prog = parse("begin X := 1 + 2 * 3 - 4 - 5 end")
    assert isinstance(prog.body, AssignStmt)
    # (((1 + (2 * 3)) - 4) - 5)
    outer = prog.body.expr
    assert isinstance(outer, BinOpExpr) and outer.op == "-"
    assert isinstance(outer.right, NumExpr) and outer.right.value == 5

    mid = outer.left
    assert isinstance(mid, BinOpExpr) and mid.op == "-"
    assert isinstance(mid.right, NumExpr) and mid.right.value == 4

    inner = mid.left
    assert isinstance(inner, BinOpExpr) and inner.op == "+"
    assert isinstance(inner.left, NumExpr) and inner.left.value == 1
    assert isinstance(inner.right, BinOpExpr) and inner.right.op == "*"


def test_statement_precedence_while_and_if_over_seq() -> None:
    prog = parse("begin while X > 0 do X := X - 1; Y := 1 end")
    assert isinstance(prog.body, SeqStmt)
    assert isinstance(prog.body.first, WhileStmt)
    assert isinstance(prog.body.second, AssignStmt)
    assert prog.body.second.var == "Y"

    prog_if = parse("begin if X = 0 then Y := 1 else Y := 2; Z := 3 end")
    assert isinstance(prog_if.body, SeqStmt)
    assert isinstance(prog_if.body.first, IfStmt)
    assert isinstance(prog_if.body.second, AssignStmt)
    assert prog_if.body.second.var == "Z"


def test_boolean_precedence_not_over_or() -> None:
    prog = parse("begin if not X = 1 or Y > 2 then skip else skip end")
    assert isinstance(prog.body, IfStmt)
    cond = prog.body.condition
    assert isinstance(cond, OrExpr)
    assert isinstance(cond.left, NotExpr)
    assert isinstance(cond.left.operand, CompareExpr)
    assert isinstance(cond.right, CompareExpr)


def test_source_spans_are_accurate() -> None:
    source = "begin\n  R := X + 1\nend"
    prog = parse(source)
    assert prog.span.start_line == 1
    assert prog.span.start_col == 1
    assert prog.span.end_line == 3
    assert prog.span.end_col == 4

    stmt = prog.body
    assert isinstance(stmt, AssignStmt)
    assert stmt.span.start_line == 2
    assert stmt.span.start_col == 3
    assert stmt.span.end_line == 2
    assert stmt.span.end_col == 13
    assert source[stmt.span.start_pos : stmt.span.end_pos] == "R := X + 1"

    assert isinstance(stmt.expr, BinOpExpr)
    assert isinstance(stmt.expr.left, VarExpr)
    assert source[stmt.expr.left.span.start_pos : stmt.expr.left.span.end_pos] == "X"


def test_ast_to_dict_is_json_serializable() -> None:
    pow_source = (ROOT / "examples" / "pow.sipl").read_text(encoding="utf-8")
    prog = parse(pow_source)
    payload = prog.to_dict()
    serialized = json.dumps(payload)
    assert '"kind": "Program"' in serialized
    assert '"kind": "WhileStmt"' in serialized


@pytest.mark.parametrize(
    ("source", "expected_line"),
    [
        ("", 1),
        ("begin\n  X := 1;\nend", 3),
        ("begin\n  X := @\nend", 2),
        ("begin X := 1", 1),
    ],
)
def test_syntax_errors_produce_diagnostics_with_span(
    source: str,
    expected_line: int,
) -> None:
    with pytest.raises(SiplSyntaxError) as exc_info:
        parse(source)

    diag = exc_info.value.diagnostic
    assert diag.span.start_line == expected_line
    assert diag.span.start_col >= 1
    assert diag.message != ""
    assert diag.code.startswith("E1")

    diagnostics = check_syntax(source)
    assert diagnostics == [diag]


def test_check_syntax_returns_empty_list_for_examples() -> None:
    for path in sorted((ROOT / "examples").glob("*.sipl")):
        assert check_syntax(path.read_text(encoding="utf-8")) == []