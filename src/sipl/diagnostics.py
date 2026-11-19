from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


@dataclass(frozen=True)
class SourceSpan:
    """1-based line/column range and 0-based character offsets in source text."""

    start_line: int
    start_col: int
    end_line: int
    end_col: int
    start_pos: int
    end_pos: int

    def to_dict(self) -> dict[str, int]:
        return {
            "start_line": self.start_line,
            "start_col": self.start_col,
            "end_line": self.end_line,
            "end_col": self.end_col,
            "start_pos": self.start_pos,
            "end_pos": self.end_pos,
        }


@dataclass(frozen=True)
class Diagnostic:
    """Structured syntax or runtime diagnostic anchored to a SourceSpan."""

    code: str
    message: str
    span: SourceSpan
    severity: Literal["error", "warning"] = "error"

    def format(self) -> str:
        return (
            f"[{self.code}] {self.span.start_line}:{self.span.start_col}: {self.message}"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "span": self.span.to_dict(),
        }


class SiplError(Exception):
    """Base exception for SIPL toolkit errors."""

    def __init__(self, diagnostic: Diagnostic) -> None:
        self.diagnostic = diagnostic
        super().__init__(diagnostic.format())


class SiplSyntaxError(SiplError):
    """Raised when SIPL source code contains a lexical or syntax error."""