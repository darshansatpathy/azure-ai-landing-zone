"""A pre-flight approximation of `terraform fmt -check`.

It enforces the parts of canonical formatting that drift most often: two-space
indentation derived from bracket nesting, aligned `=` signs for consecutive single-line
attributes, no tabs or trailing whitespace, single blank lines and a final newline.
CI still runs the real `terraform fmt -check`; this catches problems without Terraform.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_ATTR = re.compile(r'^(\s*)("[^"]+"|[A-Za-z_][A-Za-z0-9_\-.]*)(\s*)=(?!=)(\s*)(\S.*)$')
_HEREDOC = re.compile(r"<<-?([A-Za-z_][A-Za-z0-9_]*)\s*$")


@dataclass(frozen=True)
class FmtIssue:
    file: str
    line: int
    message: str


def _code_only(line: str) -> str:
    """Remove string contents and trailing comments so brackets inside them are ignored."""
    out: list[str] = []
    i, n = 0, len(line)
    while i < n:
        c = line[i]
        if c == '"':
            j = i + 1
            while j < n:
                if line[j] == "\\":
                    j += 2
                    continue
                if line[j] == '"':
                    break
                j += 1
            out.append('""')
            i = j + 1
            continue
        if c == "#" or line.startswith("//", i):
            break
        out.append(c)
        i += 1
    return "".join(out)


def _net(code: str) -> int:
    return sum(code.count(c) for c in "([{") - sum(code.count(c) for c in ")]}")


def check_text(text: str, name: str) -> list[FmtIssue]:
    issues: list[FmtIssue] = []
    if text and not text.endswith("\n"):
        issues.append(FmtIssue(name, text.count("\n") + 1, "file must end with a newline"))
    if text.endswith("\n\n"):
        issues.append(FmtIssue(name, text.count("\n"), "file must not end with blank lines"))
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines = lines[:-1]

    stack: list[int] = []
    heredoc: str | None = None
    blank_run = 0
    group: list[tuple[int, str, str, str]] = []  # (lineno, indent, key, rest)

    def flush() -> None:
        if len(group) < 1:
            return
        width = max(len(k) for _, _, k, _ in group)
        for lineno, indent, key, _ in group:
            raw = lines[lineno - 1]
            expected_prefix = f"{indent}{key.ljust(width)} = "
            if not raw.startswith(expected_prefix) or raw[len(expected_prefix)] == " ":
                issues.append(
                    FmtIssue(name, lineno, "'=' is not aligned with neighbouring attributes")
                )
        group.clear()

    for idx, raw in enumerate(lines, start=1):
        if heredoc is not None:
            if raw.strip() == heredoc:
                heredoc = None
            continue
        if "\t" in raw:
            issues.append(FmtIssue(name, idx, "tab character"))
        if raw != raw.rstrip():
            issues.append(FmtIssue(name, idx, "trailing whitespace"))
        stripped = raw.strip()
        if not stripped:
            blank_run += 1
            if blank_run > 1:
                issues.append(FmtIssue(name, idx, "more than one consecutive blank line"))
            flush()
            continue
        blank_run = 0
        code = _code_only(stripped)
        net = _net(code)
        indent_now = len(stack)
        if net > 0:
            expected = 2 * len(stack)
            stack.append(net)
        elif net < 0:
            closed = -net
            while closed > 0 and stack:
                if closed > stack[-1]:
                    closed -= stack.pop()
                elif closed < stack[-1]:
                    stack[-1] -= closed
                    closed = 0
                else:
                    stack.pop()
                    closed = 0
            expected = 2 * len(stack)
        else:
            expected = 2 * indent_now
        actual = len(raw) - len(raw.lstrip(" "))
        if actual != expected:
            issues.append(FmtIssue(name, idx, f"indent is {actual} spaces, expected {expected}"))

        m = _ATTR.match(raw)
        if m and net == 0 and not stripped.startswith(("#", "//")):
            indent, key, _, _, rest = m.groups()
            if group and len(group[0][1]) != len(indent):
                flush()
            group.append((idx, indent, key, rest))
        else:
            flush()
        h = _HEREDOC.search(stripped)
        if h:
            heredoc = h.group(1)
    flush()
    return issues


def check_paths(paths: list[Path]) -> list[FmtIssue]:
    issues: list[FmtIssue] = []
    for root in paths:
        files = (
            [root]
            if root.is_file()
            else sorted(root.rglob("*.tf")) + sorted(root.rglob("*.tfvars"))
        )
        for f in files:
            if ".terraform" in f.parts:
                continue
            issues.extend(check_text(f.read_text(encoding="utf-8"), str(f)))
    return issues
