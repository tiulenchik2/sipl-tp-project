"""SIPL Language Toolkit core package."""

from sipl.diagnostics import Diagnostic, SiplError, SiplSyntaxError, SourceSpan
from sipl.parser import check_syntax, parse, parse_tree

__version__ = "0.1.0"

__all__ = [
    "Diagnostic",
    "SiplError",
    "SiplSyntaxError",
    "SourceSpan",
    "__version__",
    "check_syntax",
    "parse",
    "parse_tree",
]