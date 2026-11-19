from __future__ import annotations

from dataclasses import replace
from functools import lru_cache
from importlib import resources

from lark import (
    Lark,
    Token,
    Tree,
    UnexpectedCharacters,
    UnexpectedEOF,
    UnexpectedInput,
    UnexpectedToken,
)
from lark.tree import Meta

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
from sipl.diagnostics import Diagnostic, SiplSyntaxError, SourceSpan


@lru_cache(maxsize=1)
def _get_lark_parser() -> Lark:
    grammar_text = resources.files("sipl").joinpath("sipl.lark").read_text(encoding="utf-8")
    return Lark(
        grammar_text,
        start="program",
        parser="earley",
        lexer="basic",
        ambiguity="explicit",
        propagate_positions=True,
        keep_all_tokens=True,
    )


def _span_from_meta(meta: Meta) -> SourceSpan:
    return SourceSpan(
        start_line=meta.line,
        start_col=meta.column,
        end_line=meta.end_line,
        end_col=meta.end_column,
        start_pos=meta.start_pos,
        end_pos=meta.end_pos,
    )


def _expect_tree(node: Tree[Token] | Token) -> Tree[Token]:
    if not isinstance(node, Tree):
        raise TypeError(f"Expected parse tree node, got token {node!r}")
    return node


def _expect_token(node: Tree[Token] | Token) -> Token:
    if not isinstance(node, Token):
        raise TypeError(f"Expected token, got parse tree node {node.data!r}")
    return node


def _build_diagnostic(source: str, exc: UnexpectedInput) -> Diagnostic:
    lines = source.splitlines()
    fallback_line = len(lines) if lines else 1
    fallback_col = (len(lines[-1]) + 1) if lines else 1
    fallback_pos = len(source)

    start_line = exc.line if (exc.line is not None and exc.line > 0) else fallback_line
    start_col = exc.column if (exc.column is not None and exc.column > 0) else fallback_col
    start_pos = (
        exc.pos_in_stream
        if (exc.pos_in_stream is not None and exc.pos_in_stream >= 0)
        else fallback_pos
    )

    if isinstance(exc, UnexpectedToken):
        token = exc.token
        if token.type == "$END":
            message = "Unexpected end of input."
            end_line, end_col, end_pos = start_line, start_col, start_pos
        else:
            message = f"Unexpected token {token.value!r}."
            end_line = token.end_line if token.end_line is not None else start_line
            end_col = (
                token.end_column
                if token.end_column is not None
                else start_col + max(len(token.value), 1)
            )
            end_pos = (
                token.end_pos
                if token.end_pos is not None
                else start_pos + max(len(token.value), 1)
            )
        code = "E1002"
    elif isinstance(exc, UnexpectedCharacters):
        message = f"Unexpected character {exc.char!r}."
        end_line = start_line
        end_col = start_col + 1
        end_pos = start_pos + 1
        code = "E1001"
    elif isinstance(exc, UnexpectedEOF):
        message = "Unexpected end of input."
        end_line, end_col, end_pos = start_line, start_col, start_pos
        code = "E1003"
    else:
        message = str(exc).splitlines()[0]
        end_line, end_col, end_pos = start_line, start_col + 1, start_pos + 1
        code = "E1000"

    span = SourceSpan(
        start_line=start_line,
        start_col=start_col,
        end_line=end_line,
        end_col=end_col,
        start_pos=start_pos,
        end_pos=end_pos,
    )
    return Diagnostic(code=code, message=message, span=span)


def _build_aexp(tree: Tree[Token]) -> AExpr:
    rule = tree.data
    span = _span_from_meta(tree.meta)

    if rule in {"add_expr", "mul_expr"}:
        return _build_aexp(_expect_tree(tree.children[0]))
    if rule == "a_paren":
        inner = _build_aexp(_expect_tree(tree.children[1]))
        return replace(inner, span=span)
    if rule == "number":
        tok = _expect_token(tree.children[0])
        return NumExpr(value=int(tok.value), span=span)
    if rule == "neg_number":
        tok = _expect_token(tree.children[1])
        return NumExpr(value=-int(tok.value), span=span)
    if rule == "var":
        tok = _expect_token(tree.children[0])
        return VarExpr(name=tok.value, span=span)
    if rule == "add":
        return BinOpExpr(
            op="+",
            left=_build_aexp(_expect_tree(tree.children[0])),
            right=_build_aexp(_expect_tree(tree.children[2])),
            span=span,
        )
    if rule == "sub":
        return BinOpExpr(
            op="-",
            left=_build_aexp(_expect_tree(tree.children[0])),
            right=_build_aexp(_expect_tree(tree.children[2])),
            span=span,
        )
    if rule == "mul":
        return BinOpExpr(
            op="*",
            left=_build_aexp(_expect_tree(tree.children[0])),
            right=_build_aexp(_expect_tree(tree.children[2])),
            span=span,
        )
    raise ValueError(f"Unsupported arithmetic expression rule: {rule!r}")


def _build_bexp(tree: Tree[Token]) -> BExpr:
    rule = tree.data
    span = _span_from_meta(tree.meta)

    if rule in {"or_expr", "not_expr"}:
        return _build_bexp(_expect_tree(tree.children[0]))
    if rule == "b_paren":
        inner = _build_bexp(_expect_tree(tree.children[1]))
        return replace(inner, span=span)
    if rule == "b_or":
        return OrExpr(
            left=_build_bexp(_expect_tree(tree.children[0])),
            right=_build_bexp(_expect_tree(tree.children[2])),
            span=span,
        )
    if rule == "b_not":
        return NotExpr(operand=_build_bexp(_expect_tree(tree.children[1])), span=span)
    if rule == "b_eq":
        return CompareExpr(
            op="=",
            left=_build_aexp(_expect_tree(tree.children[0])),
            right=_build_aexp(_expect_tree(tree.children[2])),
            span=span,
        )
    if rule == "b_gt":
        return CompareExpr(
            op=">",
            left=_build_aexp(_expect_tree(tree.children[0])),
            right=_build_aexp(_expect_tree(tree.children[2])),
            span=span,
        )
    raise ValueError(f"Unsupported boolean expression rule: {rule!r}")


def _build_stmt(tree: Tree[Token]) -> Stmt:
    rule = tree.data
    span = _span_from_meta(tree.meta)

    if rule == "seq_stmt":
        return _build_stmt(_expect_tree(tree.children[0]))
    if rule == "seq":
        return SeqStmt(
            first=_build_stmt(_expect_tree(tree.children[0])),
            second=_build_stmt(_expect_tree(tree.children[2])),
            span=span,
        )
    if rule == "assign":
        var_tok = _expect_token(tree.children[0])
        return AssignStmt(
            var=var_tok.value,
            expr=_build_aexp(_expect_tree(tree.children[2])),
            span=span,
        )
    if rule == "if_stmt":
        return IfStmt(
            condition=_build_bexp(_expect_tree(tree.children[1])),
            then_branch=_build_stmt(_expect_tree(tree.children[3])),
            else_branch=_build_stmt(_expect_tree(tree.children[5])),
            span=span,
        )
    if rule == "while_stmt":
        return WhileStmt(
            condition=_build_bexp(_expect_tree(tree.children[1])),
            body=_build_stmt(_expect_tree(tree.children[3])),
            span=span,
        )
    if rule == "block":
        return BlockStmt(body=_build_stmt(_expect_tree(tree.children[1])), span=span)
    if rule == "skip":
        return SkipStmt(span=span)
    raise ValueError(f"Unsupported statement rule: {rule!r}")


def parse_tree(source: str) -> Tree[Token]:
    """Parse SIPL source into a concrete syntax tree (Lark Tree) with all tokens and spans."""
    parser = _get_lark_parser()
    try:
        tree = parser.parse(source)
    except UnexpectedInput as exc:
        raise SiplSyntaxError(_build_diagnostic(source, exc)) from exc

    if any(tree.find_data("_ambig")):
        span = _span_from_meta(tree.meta)
        raise SiplSyntaxError(
            Diagnostic(code="E1004", message="Ambiguous parse tree detected.", span=span)
        )
    return tree


def parse(source: str) -> Program:
    """Parse SIPL source into a typed AST with SourceSpan metadata."""
    tree = parse_tree(source)
    body = _build_stmt(_expect_tree(tree.children[1]))
    return Program(body=body, span=_span_from_meta(tree.meta))


def check_syntax(source: str) -> list[Diagnostic]:
    """Return a list of syntax diagnostics (empty when source is syntactically valid)."""
    try:
        parse(source)
    except SiplSyntaxError as exc:
        return [exc.diagnostic]
    return []