from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from sipl.cli import ExitCode, main
from sipl.visualization import (
    ParseTreeNode,
    build_parse_tree,
    iter_leaves,
    render_dot,
    render_json,
    render_svg,
    render_text,
)

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples"


def _walk_nodes(node: ParseTreeNode) -> list[ParseTreeNode]:
    result = [node]
    for child in node.children:
        result.extend(_walk_nodes(child))
    return result


def test_parse_tree_nodes_link_to_exact_source_fragments() -> None:
    source = (EXAMPLES / "pow.sipl").read_text(encoding="utf-8")
    root = build_parse_tree(source)

    assert root.kind == "rule"
    assert root.label == "program"
    assert root.source_fragment == source.strip()

    for node in _walk_nodes(root):
        expected = source[node.span.start_pos : node.span.end_pos]
        assert node.source_fragment == expected
        assert node.span.start_line >= 1
        assert node.span.start_col >= 1


def test_leaves_left_to_right_reconstruct_program_tokens() -> None:
    source = (EXAMPLES / "pow.sipl").read_text(encoding="utf-8")
    root = build_parse_tree(source)
    leaves = iter_leaves(root)

    assert [leaf.leaf_index for leaf in leaves] == list(range(1, len(leaves) + 1))
    tokens = [leaf.label for leaf in leaves]
    assert tokens[0] == "begin"
    assert tokens[-1] == "end"
    assert tokens == [
        "begin",
        "R",
        ":=",
        "1",
        ";",
        "while",
        "Y",
        ">",
        "0",
        "do",
        "begin",
        "R",
        ":=",
        "R",
        "*",
        "X",
        ";",
        "Y",
        ":=",
        "Y",
        "-",
        "1",
        "end",
        "end",
    ]


def test_render_text_and_json() -> None:
    source = "begin X := 1 + 2 end"
    root = build_parse_tree(source)

    text_out = render_text(root)
    assert "<program>" in text_out
    assert "#1 'begin'" in text_out
    assert "[1:1-1:21]" in text_out

    json_out = render_json(root)
    parsed = json.loads(json_out)
    assert parsed["label"] == "program"
    assert parsed["source_fragment"] == source
    assert len(parsed["children"]) == 3


def test_render_dot_and_valid_svg() -> None:
    source = (EXAMPLES / "gcd.sipl").read_text(encoding="utf-8")
    root = build_parse_tree(source)

    dot_out = render_dot(root)
    assert dot_out.startswith("digraph SIPLParseTree {")
    assert dot_out.endswith("}")
    assert "n1 ->" in dot_out
    assert "tooltip=" in dot_out

    svg_out = render_svg(root)
    svg_elem = ET.fromstring(svg_out)
    assert svg_elem.tag.endswith("svg")
    assert int(svg_elem.attrib["width"]) > 0
    assert int(svg_elem.attrib["height"]) > 0

    all_nodes = _walk_nodes(root)
    ns = {"svg": "http://www.w3.org/2000/svg"}
    groups = svg_elem.findall(".//svg:g[@data-node-id]", ns)
    assert len(groups) == len(all_nodes)
    assert all("data-span" in g.attrib for g in groups)


def test_cli_tree_formats_and_file_output(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    pow_file = str(EXAMPLES / "pow.sipl")

    assert main(["tree", pow_file, "--format", "text"]) == ExitCode.OK
    assert "<program>" in capsys.readouterr().out

    assert main(["tree", pow_file, "--format", "dot", "--json"]) == ExitCode.OK
    dot_payload = json.loads(capsys.readouterr().out)
    assert dot_payload["ok"] is True
    assert dot_payload["format"] == "dot"
    assert dot_payload["tree"]["label"] == "program"
    assert "digraph SIPLParseTree" in dot_payload["output"]

    svg_target = tmp_path / "pow.svg"
    assert (
        main(["tree", pow_file, "--format", "svg", "--output", str(svg_target)])
        == ExitCode.OK
    )
    assert "Wrote svg parse tree" in capsys.readouterr().out
    assert svg_target.exists()
    ET.fromstring(svg_target.read_text(encoding="utf-8"))

    broken = tmp_path / "broken.sipl"
    broken.write_text("begin X := end", encoding="utf-8")
    assert main(["tree", str(broken), "--json"]) == ExitCode.SYNTAX_ERROR
    err_payload = json.loads(capsys.readouterr().out)
    assert err_payload["ok"] is False
    assert err_payload["diagnostics"][0]["code"].startswith("E1")