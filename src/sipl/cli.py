from __future__ import annotations

import argparse
import io
import json
import sys
from collections.abc import Sequence
from enum import IntEnum
from pathlib import Path
from typing import Any

from sipl import __version__
from sipl.diagnostics import (
    SiplRuntimeError,
    SiplSyntaxError,
    StepLimitExceededError,
)
from sipl.interpreter import execute
from sipl.parser import check_syntax, parse
from sipl.semantics import build_semantic_term
from sipl.visualization import (
    build_parse_tree,
    render_dot,
    render_json,
    render_svg,
    render_text,
)

SCHEMA_VERSION = "1.0"


class ExitCode(IntEnum):
    OK = 0
    USAGE_ERROR = 2
    SYNTAX_ERROR = 3
    RUNTIME_ERROR = 4
    STEP_LIMIT_ERROR = 5


def _ensure_utf8_streams() -> None:
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if isinstance(sys.stderr, io.TextIOWrapper):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def _emit_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _read_source(file_arg: str) -> str:
    if file_arg == "-":
        return sys.stdin.read()
    path = Path(file_arg)
    return path.read_text(encoding="utf-8")


def _parse_initial_state(
    state_json: str | None,
    var_items: Sequence[str] | None,
) -> dict[str, int]:
    state: dict[str, int] = {}

    if state_json is not None:
        try:
            raw = json.loads(state_json)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid --state JSON: {exc.msg}.") from exc
        if not isinstance(raw, dict):
            raise ValueError("--state must be a JSON object mapping variable names to integers.")
        for key, value in raw.items():
            if not isinstance(key, str) or not key.isidentifier():
                raise ValueError(f"Invalid variable name in --state: {key!r}.")
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"Variable {key!r} must have an integer value.")
            state[key] = value

    for item in var_items or ():
        if "=" not in item:
            raise ValueError(f"Invalid --var format {item!r}; expected NAME=INT.")
        name, raw_val = item.split("=", 1)
        name = name.strip()
        if not name.isidentifier():
            raise ValueError(f"Invalid variable name {name!r} in --var.")
        try:
            value = int(raw_val.strip())
        except ValueError as exc:
            raise ValueError(f"Invalid integer value for {name!r}: {raw_val!r}.") from exc
        state[name] = value

    return state


def _report_input_error(command: str, message: str, as_json: bool) -> int:
    if as_json:
        _emit_json(
            {
                "schema_version": SCHEMA_VERSION,
                "command": command,
                "ok": False,
                "exit_code": int(ExitCode.USAGE_ERROR),
                "error": message,
            }
        )
    else:
        print(f"Error: {message}", file=sys.stderr)
    return int(ExitCode.USAGE_ERROR)


def _cmd_parse(args: argparse.Namespace) -> int:
    try:
        source = _read_source(args.file)
    except OSError as exc:
        return _report_input_error("parse", f"Cannot read {args.file!r}: {exc}", args.json)

    try:
        program = parse(source)
    except SiplSyntaxError as exc:
        if args.json:
            _emit_json(
                {
                    "schema_version": SCHEMA_VERSION,
                    "command": "parse",
                    "ok": False,
                    "exit_code": int(ExitCode.SYNTAX_ERROR),
                    "diagnostics": [exc.diagnostic.to_dict()],
                }
            )
        else:
            print(exc.diagnostic.format(), file=sys.stderr)
        return int(ExitCode.SYNTAX_ERROR)

    if args.json:
        _emit_json(
            {
                "schema_version": SCHEMA_VERSION,
                "command": "parse",
                "ok": True,
                "exit_code": int(ExitCode.OK),
                "ast": program.to_dict(),
            }
        )
    else:
        print(json.dumps(program.to_dict(), ensure_ascii=False, indent=2))
    return int(ExitCode.OK)


def _cmd_check(args: argparse.Namespace) -> int:
    try:
        source = _read_source(args.file)
    except OSError as exc:
        return _report_input_error("check", f"Cannot read {args.file!r}: {exc}", args.json)

    diagnostics = check_syntax(source)
    ok = len(diagnostics) == 0
    exit_code = ExitCode.OK if ok else ExitCode.SYNTAX_ERROR

    if args.json:
        _emit_json(
            {
                "schema_version": SCHEMA_VERSION,
                "command": "check",
                "ok": ok,
                "exit_code": int(exit_code),
                "diagnostics": [diag.to_dict() for diag in diagnostics],
            }
        )
    elif ok:
        print("OK")
    else:
        for diag in diagnostics:
            print(diag.format(), file=sys.stderr)

    return int(exit_code)


def _cmd_execute(args: argparse.Namespace, *, include_events: bool) -> int:
    command = "trace" if include_events else "run"

    try:
        source = _read_source(args.file)
        initial_state = _parse_initial_state(args.state, args.var)
        if args.max_steps <= 0:
            raise ValueError("--max-steps must be a positive integer.")
    except (OSError, ValueError) as exc:
        return _report_input_error(command, str(exc), args.json)

    try:
        result = execute(source, initial_state=initial_state, max_steps=args.max_steps)
    except SiplSyntaxError as exc:
        if args.json:
            _emit_json(
                {
                    "schema_version": SCHEMA_VERSION,
                    "command": command,
                    "ok": False,
                    "exit_code": int(ExitCode.SYNTAX_ERROR),
                    "diagnostics": [exc.diagnostic.to_dict()],
                }
            )
        else:
            print(exc.diagnostic.format(), file=sys.stderr)
        return int(ExitCode.SYNTAX_ERROR)
    except SiplRuntimeError as exc:
        exit_code = (
            ExitCode.STEP_LIMIT_ERROR
            if isinstance(exc, StepLimitExceededError)
            else ExitCode.RUNTIME_ERROR
        )
        if args.json:
            payload: dict[str, Any] = {
                "schema_version": SCHEMA_VERSION,
                "command": command,
                "ok": False,
                "exit_code": int(exit_code),
                "status": "error",
                "diagnostics": [exc.diagnostic.to_dict()],
            }
            if include_events:
                payload["events"] = [event.to_dict() for event in exc.events]
            _emit_json(payload)
        else:
            print(exc.diagnostic.format(), file=sys.stderr)
        return int(exit_code)

    if args.json:
        ok_payload: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "command": command,
            "ok": True,
            "exit_code": int(ExitCode.OK),
            "status": result.status,
            "steps": result.steps,
            "state": dict(result.state),
        }
        if include_events:
            ok_payload["events"] = [event.to_dict() for event in result.events]
        _emit_json(ok_payload)
    elif include_events:
        for event in result.events:
            print(json.dumps(event.to_dict(), ensure_ascii=False))
    else:
        print(f"Steps: {result.steps}")
        if result.state:
            for name in sorted(result.state):
                print(f"{name} = {result.state[name]}")
        else:
            print("(empty state)")

    return int(ExitCode.OK)

def _cmd_tree(args: argparse.Namespace) -> int:
    try:
        source = _read_source(args.file)
    except OSError as exc:
        return _report_input_error("tree", f"Cannot read {args.file!r}: {exc}", args.json)

    try:
        root = build_parse_tree(source)
    except SiplSyntaxError as exc:
        if args.json:
            _emit_json(
                {
                    "schema_version": SCHEMA_VERSION,
                    "command": "tree",
                    "ok": False,
                    "exit_code": int(ExitCode.SYNTAX_ERROR),
                    "diagnostics": [exc.diagnostic.to_dict()],
                }
            )
        else:
            print(exc.diagnostic.format(), file=sys.stderr)
        return int(ExitCode.SYNTAX_ERROR)

    fmt: str = args.format
    if fmt == "text":
        rendered = render_text(root)
    elif fmt == "json":
        rendered = render_json(root)
    elif fmt == "dot":
        rendered = render_dot(root)
    elif fmt == "svg":
        rendered = render_svg(root)
    else:
        return _report_input_error("tree", f"Unsupported format {fmt!r}.", args.json)

    output_path: str | None = args.output
    if output_path is not None:
        try:
            Path(output_path).write_text(rendered, encoding="utf-8")
        except OSError as exc:
            return _report_input_error(
                "tree",
                f"Cannot write {output_path!r}: {exc}",
                args.json,
            )

    if args.json:
        payload: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "command": "tree",
            "ok": True,
            "exit_code": int(ExitCode.OK),
            "format": fmt,
            "tree": root.to_dict(),
        }
        if fmt != "json":
            payload["output"] = rendered
        if output_path is not None:
            payload["output_path"] = output_path
        _emit_json(payload)
    elif output_path is not None:
        print(f"Wrote {fmt} parse tree to {output_path}")
    else:
        print(rendered)

    return int(ExitCode.OK)

def _cmd_sem(args: argparse.Namespace) -> int:
    try:
        source = _read_source(args.file)
    except OSError as exc:
        return _report_input_error("sem", f"Cannot read {args.file!r}: {exc}", args.json)

    try:
        built = build_semantic_term(source)
    except SiplSyntaxError as exc:
        if args.json:
            _emit_json(
                {
                    "schema_version": SCHEMA_VERSION,
                    "command": "sem",
                    "ok": False,
                    "exit_code": int(ExitCode.SYNTAX_ERROR),
                    "diagnostics": [exc.diagnostic.to_dict()],
                }
            )
        else:
            print(exc.diagnostic.format(), file=sys.stderr)
        return int(ExitCode.SYNTAX_ERROR)

    style = args.style
    if args.json:
        payload: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "command": "sem",
            "ok": True,
            "exit_code": int(ExitCode.OK),
            **built.to_dict(style=style),
        }
        _emit_json(payload)
    else:
        print(built.format(style=style))
        if args.steps:
            print("Applied rules:")
            for idx, step in enumerate(built.steps, start=1):
                loc = f"{step.span.start_line}:{step.span.start_col}"
                print(f"  {idx}. {step.rule} ({step.ast_kind} @ {loc})")

    return int(ExitCode.OK)

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sipl",
        description="SIPL Language Toolkit CLI.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    common_io = argparse.ArgumentParser(add_help=False)
    common_io.add_argument(
        "file",
        help="Path to a .sipl source file, or '-' to read from stdin.",
    )
    common_io.add_argument(
        "--json",
        action="store_true",
        help="Emit structured JSON output.",
    )

    common_exec = argparse.ArgumentParser(add_help=False)
    common_exec.add_argument(
        "-v",
        "--var",
        action="append",
        metavar="NAME=INT",
        help="Initial variable assignment (repeatable), e.g. --var X=5.",
    )
    common_exec.add_argument(
        "--state",
        metavar="JSON",
        help='Initial state as JSON object, e.g. \'{"X": 5, "Y": 2}\'.',
    )
    common_exec.add_argument(
        "--max-steps",
        type=int,
        default=10_000,
        help="Maximum executed statements before aborting (default: 10000).",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    p_parse = subparsers.add_parser(
        "parse",
        parents=[common_io],
        help="Parse a SIPL program and output its typed AST.",
    )
    p_parse.set_defaults(handler=_cmd_parse)

    p_check = subparsers.add_parser(
        "check",
        parents=[common_io],
        help="Validate SIPL syntax and report diagnostics.",
    )
    p_check.set_defaults(handler=_cmd_check)

    p_run = subparsers.add_parser(
        "run",
        parents=[common_io, common_exec],
        help="Execute a SIPL program and print the resulting state.",
    )
    p_run.set_defaults(handler=lambda ns: _cmd_execute(ns, include_events=False))

    p_trace = subparsers.add_parser(
        "trace",
        parents=[common_io, common_exec],
        help="Execute a SIPL program and emit execution trace events.",
    )
    p_trace.set_defaults(handler=lambda ns: _cmd_execute(ns, include_events=True))

    p_tree = subparsers.add_parser(
        "tree",
        parents=[common_io],
        help="Render the concrete parse tree as text, json, dot, or svg.",
    )
    p_tree.add_argument(
        "-f",
        "--format",
        choices=("text", "json", "dot", "svg"),
        default="text",
        help="Visualization output format (default: text).",
    )
    p_tree.add_argument(
        "-o",
        "--output",
        metavar="PATH",
        help="Write rendered output to a file instead of stdout.",
    )
    p_tree.set_defaults(handler=_cmd_tree)

    p_sem = subparsers.add_parser(
        "sem",
        parents=[common_io],
        help="Construct the course semantic term for a SIPL program.",
    )
    p_sem.add_argument(
        "--style",
        choices=("course", "ascii"),
        default="course",
        help="Semantic term notation style (default: course).",
    )
    p_sem.add_argument(
        "--steps",
        action="store_true",
        help="Print the sequence of applied rewriting rules in text mode.",
    )
    p_sem.set_defaults(handler=_cmd_sem)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    _ensure_utf8_streams()
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = args.handler
    return int(handler(args))


if __name__ == "__main__":
    raise SystemExit(main())