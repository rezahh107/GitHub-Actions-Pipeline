"""Bounded shell-command evidence for GitHub Actions ``run`` blocks.

This module does not attempt to emulate a shell. It recognizes only standalone,
non-control-flow invocations that can be tokenized deterministically. Comments,
assignments, shell builtins, compound commands, substitutions, heredocs, and
control-flow bodies never become executable capability evidence.
"""
from __future__ import annotations

import re
import shlex
from typing import Iterable

COMMAND_EVIDENCE_VERSION = "1.0.0"

_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=.*$", re.DOTALL)
_CONTROL_WORDS = {
    "if", "then", "elif", "else", "fi", "for", "while", "until", "do",
    "done", "case", "esac", "select", "function", "time", "coproc",
}
_SHELL_BUILTINS = {
    ":", ".", "alias", "bg", "bind", "break", "builtin", "caller", "cd",
    "command", "compgen", "complete", "continue", "declare", "dirs",
    "disown", "echo", "enable", "eval", "exec", "exit", "export", "false",
    "fc", "fg", "getopts", "hash", "help", "history", "jobs", "kill",
    "let", "local", "logout", "mapfile", "popd", "printf", "pushd", "pwd",
    "read", "readarray", "readonly", "return", "set", "shift", "shopt",
    "source", "suspend", "test", "times", "trap", "true", "type",
    "typeset", "ulimit", "umask", "unalias", "unset", "wait", "[", "[[",
}
_UNSAFE_TEXT = ("$(", "`", "<(", ">(", "${!", "<<<", "<<")
_CONTROL_TOKENS = {"&&", "||", "|", "|&", ";", "&", "(", ")", "{", "}"}
_REDIRECT_TOKENS = {">", ">>", "<", "<>"}
_FD_REDIRECT_TOKENS = {">&", "<&"}
_UNSUPPORTED_REDIRECT_TOKENS = {"<<", "<<<"}


def _logical_lines(run: str) -> list[tuple[int, str]]:
    """Join simple backslash continuations and retain the first source line."""
    result: list[tuple[int, str]] = []
    buffer = ""
    start = 1
    for number, raw in enumerate(run.splitlines(), 1):
        line = raw.rstrip()
        if not buffer:
            start = number
        if line.endswith("\\") and not line.endswith("\\\\"):
            buffer += line[:-1] + " "
            continue
        buffer += line
        result.append((start, buffer))
        buffer = ""
    if buffer:
        result.append((start, buffer))
    return result


def _tokenize(text: str) -> list[str] | None:
    try:
        lexer = shlex.shlex(text, posix=True, punctuation_chars=";&|<>(){}")
        lexer.whitespace_split = True
        lexer.commenters = "#"
        return list(lexer)
    except ValueError:
        return None


def _strip_prefixes(tokens: list[str]) -> tuple[list[str], list[str]]:
    assignments: list[str] = []
    index = 0
    if tokens and tokens[0] == "env":
        index = 1
        while index < len(tokens) and tokens[index].startswith("-"):
            if tokens[index] == "--":
                index += 1
                break
            return [], []
    while index < len(tokens) and _ASSIGNMENT.match(tokens[index]):
        assignments.append(tokens[index])
        index += 1
    while index < len(tokens) and tokens[index] in {"command", "exec"}:
        index += 1
    return tokens[index:], assignments


def _strip_redirections(tokens: list[str]) -> list[str] | None:
    argv: list[str] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token in _CONTROL_TOKENS or token in _UNSUPPORTED_REDIRECT_TOKENS:
            return None
        if token.isdigit() and index + 1 < len(tokens) and tokens[index + 1] in (
            _REDIRECT_TOKENS | _FD_REDIRECT_TOKENS | _UNSUPPORTED_REDIRECT_TOKENS
        ):
            operator = tokens[index + 1]
            if operator in _UNSUPPORTED_REDIRECT_TOKENS or index + 2 >= len(tokens):
                return None
            if operator in _FD_REDIRECT_TOKENS and not re.fullmatch(r"[0-9-]+", tokens[index + 2]):
                return None
            index += 3
            continue
        if token in _FD_REDIRECT_TOKENS:
            if index + 1 >= len(tokens) or not re.fullmatch(r"[0-9-]+", tokens[index + 1]):
                return None
            index += 2
            continue
        if token in _REDIRECT_TOKENS:
            if index + 1 >= len(tokens):
                return None
            index += 2
            continue
        argv.append(token)
        index += 1
    return argv


def classify_invocation(argv: Iterable[str]) -> list[str]:
    """Return capability families proven by one resolved argv vector."""
    args = list(argv)
    if not args:
        return []
    executable = args[0].rsplit("/", 1)[-1].lower()
    tail = [part.lower() for part in args[1:]]
    families: set[str] = set()

    if executable in {"python", "python3", "py"}:
        if tail[:2] in (["-m", "pytest"], ["-m", "unittest"]):
            families.add("test")
        if tail[:2] == ["-m", "build"]:
            families.update({"build", "release"})
        if tail[:2] == ["-m", "pip"] and len(tail) >= 3 and tail[2] == "install":
            families.add("install")
    elif executable in {"pytest", "py.test", "nosetests"}:
        families.add("test")
    elif executable in {"npm", "pnpm", "yarn"}:
        if tail[:1] == ["test"]:
            families.add("test")
        if len(tail) >= 2 and tail[0] == "run":
            script = tail[1]
            if script in {"test", "tests", "check", "validate"}:
                families.add("test")
            if script in {"build", "compile", "bundle"}:
                families.add("build")
        if tail[:1] in (["ci"], ["install"], ["--frozen-lockfile"]):
            families.add("install")
        if tail[:1] in (["pack"], ["publish"]):
            families.add("release")
    elif executable == "uv":
        if tail[:1] == ["sync"]:
            families.add("install")
        if tail[:2] in (["run", "pytest"], ["run", "python"]):
            families.update(classify_invocation(tail[1:]))
    elif executable == "poetry":
        if tail[:1] == ["install"]:
            families.add("install")
        if tail[:2] in (["run", "pytest"], ["run", "python"]):
            families.update(classify_invocation(tail[1:]))
        if tail[:1] == ["build"]:
            families.update({"build", "release"})
    elif executable == "cargo":
        if tail[:1] == ["test"]:
            families.add("test")
        if tail[:1] in (["build"], ["check"]):
            families.add("build")
        if tail[:1] == ["package"]:
            families.add("release")
    elif executable == "go":
        if tail[:1] == ["test"]:
            families.add("test")
        if tail[:1] == ["build"]:
            families.add("build")
    elif executable in {"mvn", "mvnw", "gradle", "gradlew"}:
        normalized = {part.lstrip("-") for part in tail}
        if "test" in normalized or "check" in normalized:
            families.add("test")
        if "package" in normalized or "build" in normalized or "assemble" in normalized:
            families.add("build")
    elif executable == "twine" and tail[:1] == ["check"]:
        families.add("release")

    return sorted(families)


def parse_run_block(run: str, *, working_directory: str | None = None) -> list[dict[str, object]]:
    """Parse bounded standalone command evidence from a workflow run block."""
    records: list[dict[str, object]] = []
    control_depth = 0
    opening_words = {"if", "for", "while", "until", "case", "select"}
    closing_words = {"fi", "done", "esac"}
    for line_number, raw in _logical_lines(run):
        stripped = raw.strip()
        base: dict[str, object] = {
            "record_version": COMMAND_EVIDENCE_VERSION,
            "line": line_number,
            "raw": raw,
            "working_directory": working_directory,
            "argv": [],
            "executable": None,
            "normalized": None,
            "families": [],
        }
        if not stripped:
            continue
        if stripped.startswith("#"):
            records.append({**base, "status": "comment", "reason": "full_line_comment"})
            continue
        if any(token in stripped for token in _UNSAFE_TEXT):
            records.append({**base, "status": "unsupported", "reason": "substitution_or_heredoc"})
            continue
        tokens = _tokenize(stripped)
        if tokens is None:
            records.append({**base, "status": "unsupported", "reason": "shell_tokenization_failed"})
            continue
        if not tokens:
            records.append({**base, "status": "comment", "reason": "comment_or_whitespace"})
            continue
        first = tokens[0]
        inside_control = control_depth > 0
        opens_control = first in opening_words
        closes_control = first in closing_words
        if opens_control:
            control_depth += 1
        if closes_control:
            control_depth = max(0, control_depth - 1)
        if inside_control or opens_control or closes_control or first in _CONTROL_WORDS or any(token in _CONTROL_TOKENS for token in tokens):
            records.append({**base, "status": "unsupported", "reason": "compound_or_control_flow"})
            continue
        invocation, assignments = _strip_prefixes(tokens)
        if not invocation:
            reason = "assignment_only" if assignments else "unsupported_environment_wrapper"
            records.append({**base, "status": "inert", "reason": reason})
            continue
        argv = _strip_redirections(invocation)
        if argv is None or not argv:
            records.append({**base, "status": "unsupported", "reason": "unsupported_redirection_or_operator"})
            continue
        executable = argv[0].rsplit("/", 1)[-1]
        if executable in _SHELL_BUILTINS:
            records.append({**base, "status": "inert", "reason": "shell_builtin", "argv": argv, "executable": executable})
            continue
        families = classify_invocation(argv)
        records.append({
            **base,
            "status": "resolved",
            "reason": "standalone_argv",
            "argv": argv,
            "executable": executable,
            "normalized": shlex.join(argv),
            "families": families,
        })
    return records


def resolved_family(records: Iterable[dict[str, object]], family: str) -> bool:
    return any(
        item.get("status") == "resolved"
        and family in item.get("families", [])
        for item in records
        if isinstance(item, dict)
    )
