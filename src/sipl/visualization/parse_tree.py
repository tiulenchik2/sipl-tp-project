from __future__ import annotations

import json
from dataclasses import dataclass
from html import escape as xml_escape
from typing import Any, Literal

from lark import Token, Tree

from sipl.diagnostics import SourceSpan
from sipl.parser import parse_tree

NodeKind = Literal["rule", "token"]


@dataclass(frozen=True)
class ParseTreeNode:
    """Concrete syntax tree node linked to an exact source span and text fragment."""

    node_id: int
    kind: NodeKind
    label: str
    span: SourceSpan
    source_fragment: str
    leaf_index: int | None = None
    children: tuple[ParseTreeNode, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.node_id,
            "kind": self.kind,
            "label": self.label,
            "span": self.span.to_dict(),
            "source_fragment": self.source_fragment,
            "leaf_index": self.leaf_index,
            "children": [child.to_dict() for child in self.children],
        }


def _span_from_lark(node: Tree[Token] | Token) -> SourceSpan:
    if isinstance(node, Tree):
        meta = node.meta
        return SourceSpan(
            start_line=meta.line,
            start_col=meta.column,
            end_line=meta.end_line,
            end_col=meta.end_column,
            start_pos=meta.start_pos,
            end_pos=meta.end_pos,
        )

    start_line = node.line if node.line is not None else 1
    start_col = node.column if node.column is not None else 1
    end_line = node.end_line if node.end_line is not None else start_line
    end_col = node.end_column if node.end_column is not None else start_col + len(node.value)
    start_pos = node.start_pos if node.start_pos is not None else 0
    end_pos = node.end_pos if node.end_pos is not None else start_pos + len(node.value)
    return SourceSpan(
        start_line=start_line,
        start_col=start_col,
        end_line=end_line,
        end_col=end_col,
        start_pos=start_pos,
        end_pos=end_pos,
    )


def _compact_fragment(fragment: str, max_len: int = 28) -> str:
    collapsed = " ".join(fragment.split())
    if len(collapsed) <= max_len:
        return collapsed
    return f"{collapsed[: max_len - 3]}..."


def _format_span_short(span: SourceSpan) -> str:
    return f"{span.start_line}:{span.start_col}-{span.end_line}:{span.end_col}"


class _ParseTreeBuilder:
    def __init__(self, source: str) -> None:
        self._source = source
        self._next_id = 0
        self._next_leaf = 0

    def build(self, node: Tree[Token] | Token) -> ParseTreeNode:
        self._next_id += 1
        node_id = self._next_id
        span = _span_from_lark(node)
        fragment = self._source[span.start_pos : span.end_pos]

        if isinstance(node, Token):
            self._next_leaf += 1
            return ParseTreeNode(
                node_id=node_id,
                kind="token",
                label=node.value,
                span=span,
                source_fragment=fragment,
                leaf_index=self._next_leaf,
            )

        children = tuple(self.build(child) for child in node.children)
        return ParseTreeNode(
            node_id=node_id,
            kind="rule",
            label=str(node.data),
            span=span,
            source_fragment=fragment,
            children=children,
        )


def build_parse_tree(source: str) -> ParseTreeNode:
    """Parse SIPL source and return a ParseTreeNode tree with source spans and leaf indices."""
    raw_tree = parse_tree(source)
    return _ParseTreeBuilder(source).build(raw_tree)


def iter_leaves(root: ParseTreeNode) -> list[ParseTreeNode]:
    """Collect terminal leaves in left-to-right traversal order."""
    if not root.children:
        return [root]
    leaves: list[ParseTreeNode] = []
    for child in root.children:
        leaves.extend(iter_leaves(child))
    return leaves


def render_text(root: ParseTreeNode) -> str:
    """Render parse tree as an indented text diagram with spans and source snippets."""
    lines: list[str] = []

    def _visit(node: ParseTreeNode, prefix: str, is_last: bool, is_root: bool) -> None:
        connector = "" if is_root else ("└── " if is_last else "├── ")
        span_str = _format_span_short(node.span)
        snippet = _compact_fragment(node.source_fragment)

        if node.kind == "token":
            leaf_tag = f"#{node.leaf_index} " if node.leaf_index is not None else ""
            header = f"{leaf_tag}{node.label!r} [{span_str}]"
        else:
            header = f"<{node.label}> [{span_str}] {snippet!r}"

        lines.append(f"{prefix}{connector}{header}")

        child_prefix = "" if is_root else prefix + ("    " if is_last else "│   ")
        last_idx = len(node.children) - 1
        for idx, child in enumerate(node.children):
            _visit(child, child_prefix, idx == last_idx, False)

    _visit(root, "", True, True)
    return "\n".join(lines)


def render_json(root: ParseTreeNode) -> str:
    """Render parse tree as pretty-printed JSON."""
    return json.dumps(root.to_dict(), ensure_ascii=False, indent=2)


def _dot_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def render_dot(root: ParseTreeNode) -> str:
    """Render parse tree in Graphviz DOT format with span and fragment metadata."""
    lines = [
        "digraph SIPLParseTree {",
        '  node [fontname="Helvetica", fontsize=10];',
        '  edge [color="#64748b"];',
    ]

    def _visit(node: ParseTreeNode) -> None:
        span_str = _format_span_short(node.span)
        tooltip = _dot_escape(f"{span_str}: {node.source_fragment}")

        if node.kind == "token":
            leaf_tag = f"#{node.leaf_index} " if node.leaf_index is not None else ""
            label = _dot_escape(f"{leaf_tag}{node.label}\n[{span_str}]")
            attrs = (
                f'label="{label}", shape=ellipse, style=filled, '
                f'fillcolor="#ecfdf5", color="#059669", tooltip="{tooltip}"'
            )
        else:
            snippet = _compact_fragment(node.source_fragment, max_len=24)
            label = _dot_escape(f"<{node.label}>\n[{span_str}]\n{snippet}")
            attrs = (
                f'label="{label}", shape=box, style="rounded,filled", '
                f'fillcolor="#eff6ff", color="#2563eb", tooltip="{tooltip}"'
            )

        lines.append(f"  n{node.node_id} [{attrs}];")
        for child in node.children:
            lines.append(f"  n{node.node_id} -> n{child.node_id};")
            _visit(child)

    _visit(root)
    lines.append("}")
    return "\n".join(lines)


class _SvgLayout:
    NODE_W = 136.0
    NODE_H = 44.0
    H_GAP = 16.0
    V_GAP = 36.0
    PAD = 24.0

    def __init__(self) -> None:
        self._leaf_slot = 0
        self.positions: dict[int, tuple[float, float]] = {}
        self.max_x = 0.0
        self.max_y = 0.0

    def place(self, node: ParseTreeNode, depth: int = 0) -> float:
        cy = self.PAD + depth * (self.NODE_H + self.V_GAP) + self.NODE_H / 2
        if not node.children:
            cx = self.PAD + self._leaf_slot * (self.NODE_W + self.H_GAP) + self.NODE_W / 2
            self._leaf_slot += 1
        else:
            child_xs = [self.place(child, depth + 1) for child in node.children]
            cx = (child_xs[0] + child_xs[-1]) / 2

        self.positions[node.node_id] = (cx, cy)
        self.max_x = max(self.max_x, cx + self.NODE_W / 2 + self.PAD)
        self.max_y = max(self.max_y, cy + self.NODE_H / 2 + self.PAD)
        return cx


def render_svg(root: ParseTreeNode) -> str:
    """Render parse tree as a self-contained SVG diagram with source span tooltips."""
    layout = _SvgLayout()
    layout.place(root)
    width = int(layout.max_x)
    height = int(layout.max_y)
    half_w = layout.NODE_W / 2
    half_h = layout.NODE_H / 2

    edges: list[str] = []
    nodes: list[str] = []

    def _collect(node: ParseTreeNode) -> None:
        cx, cy = layout.positions[node.node_id]
        span_str = _format_span_short(node.span)
        title_text = xml_escape(f"{node.label} [{span_str}]: {node.source_fragment}")

        if node.kind == "token":
            leaf_tag = f"#{node.leaf_index} " if node.leaf_index is not None else ""
            main_label = xml_escape(_compact_fragment(f"{leaf_tag}{node.label}", max_len=18))
            sub_label = xml_escape(span_str)
            box_class = "token-box"
        else:
            main_label = xml_escape(f"<{node.label}>")
            sub_label = xml_escape(span_str)
            box_class = "rule-box"

        x = cx - half_w
        y = cy - half_h
        nodes.append(
            f'  <g class="node" data-node-id="{node.node_id}" data-kind="{node.kind}" '
            f'data-span="{xml_escape(span_str)}">\n'
            f"    <title>{title_text}</title>\n"
            f'    <rect class="{box_class}" x="{x:.1f}" y="{y:.1f}" '
            f'width="{layout.NODE_W:.1f}" height="{layout.NODE_H:.1f}" rx="8" ry="8" />\n'
            f'    <text class="label" x="{cx:.1f}" y="{cy - 4:.1f}">{main_label}</text>\n'
            f'    <text class="meta" x="{cx:.1f}" y="{cy + 13:.1f}">{sub_label}</text>\n'
            "  </g>"
        )

        for child in node.children:
            child_x, child_y = layout.positions[child.node_id]
            edges.append(
                f'  <line class="edge" x1="{cx:.1f}" y1="{cy + half_h:.1f}" '
                f'x2="{child_x:.1f}" y2="{child_y - half_h:.1f}" />'
            )
            _collect(child)

    _collect(root)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        "  <style>",
        "    .edge { stroke: #64748b; stroke-width: 1.5; }",
        "    .rule-box { fill: #eff6ff; stroke: #2563eb; stroke-width: 1.5; }",
        "    .token-box { fill: #ecfdf5; stroke: #059669; stroke-width: 1.5; }",
        "    .label { font-family: sans-serif; font-size: 12px; font-weight: 600; "
        "fill: #0f172a; text-anchor: middle; }",
        "    .meta { font-family: monospace; font-size: 10px; "
        "fill: #475569; text-anchor: middle; }",
        "  </style>",
        f'  <rect width="{width}" height="{height}" fill="#ffffff" />',
        *edges,
        *nodes,
        "</svg>",
    ]
    return "\n".join(parts)