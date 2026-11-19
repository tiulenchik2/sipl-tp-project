from pathlib import Path

import pytest
from lark import Lark, UnexpectedInput

ROOT = Path(__file__).resolve().parent.parent
GRAMMAR_PATH = ROOT / "grammar" / "sipl.lark"
EXAMPLES_DIR = ROOT / "examples"


@pytest.fixture(scope="module")
def sipl_grammar_parser() -> Lark:
    grammar_text = GRAMMAR_PATH.read_text(encoding="utf-8")
    return Lark(
        grammar_text,
        start="program",
        parser="earley",
        lexer="basic",
        ambiguity="explicit",
        propagate_positions=True,
    )


POSITIVE_PROGRAMS = [
    "begin skip end",
    "begin X := 42 end",
    "begin X := -7 end",
    "begin X := 1 + 2 * 3 - 4 end",
    "begin X := (1 + 2) * (3 - 4) end",
    "begin X := 1; Y := 2; Z := X + Y end",
    "begin if X = 0 then Y := 1 else Y := 2 end",
    "begin if not X > Y or X = 0 then skip else X := X - 1 end",
    "begin if ¬(X = Y) ∨ X > 10 then X := 0 else skip end",
    "begin while Y > 0 do begin R := R * X; Y := Y - 1 end end",
    "begin while ¬M = N do if M > N then M := M - N else N := N - M end",
    "begin begin skip end; skip end",
    "begin not_done := 1; order := not_done + 2 end",
    "begin # inline comment\n X := 1 end",
]

NEGATIVE_PROGRAMS = [
    "",
    "begin end",
    "X := 1",
    "begin X := 1",
    "begin X = 1 end",
    "begin X := 1; end",
    "begin if X > 0 then X := 1 end",
    "begin while X > 0 X := X - 1 end",
    "begin if X + 1 then skip else skip end",
    "begin X := (1 + 2 end",
    "begin begin := 1 end",
    "begin X := 1 + * 2 end",
]


@pytest.mark.parametrize("source", POSITIVE_PROGRAMS)
def test_valid_sipl_programs_parse_unambiguously(
    sipl_grammar_parser: Lark,
    source: str,
) -> None:
    tree = sipl_grammar_parser.parse(source)
    assert tree.data == "program"
    assert not list(tree.find_data("_ambig"))


@pytest.mark.parametrize("source", NEGATIVE_PROGRAMS)
def test_invalid_sipl_programs_are_rejected(
    sipl_grammar_parser: Lark,
    source: str,
) -> None:
    with pytest.raises(UnexpectedInput):
        sipl_grammar_parser.parse(source)


def test_all_example_files_parse(sipl_grammar_parser: Lark) -> None:
    example_files = sorted(EXAMPLES_DIR.glob("*.sipl"))
    assert len(example_files) >= 3
    for path in example_files:
        tree = sipl_grammar_parser.parse(path.read_text(encoding="utf-8"))
        assert tree.data == "program"
        assert not list(tree.find_data("_ambig"))