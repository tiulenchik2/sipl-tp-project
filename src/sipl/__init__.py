"""SIPL Language Toolkit core package."""

from sipl.diagnostics import (
    Diagnostic,
    SiplError,
    SiplRuntimeError,
    SiplSyntaxError,
    SourceSpan,
    StepLimitExceededError,
    UndefinedVariableError,
)
from sipl.interpreter import ExecutionResult, Interpreter, execute
from sipl.parser import check_syntax, parse, parse_tree
from sipl.semantics import SemanticBuildResult, build_semantic_term, format_term

__version__ = "1.0.0"

__all__ = [
    "Diagnostic",
    "ExecutionResult",
    "Interpreter",
    "SiplError",
    "SiplRuntimeError",
    "SiplSyntaxError",
    "SourceSpan",
    "StepLimitExceededError",
    "UndefinedVariableError",
    "__version__",
    "check_syntax",
    "execute",
    "parse",
    "parse_tree",
    "SemanticBuildResult",
    "build_semantic_term",
    "format_term"
]