"""A small, dependency-free parser for the subset of HCL2 that Terraform code uses.

It understands blocks, labelled blocks, attributes, comments, quoted strings with
interpolation, heredocs, and balanced expressions (lists, objects, calls, conditionals).
Expressions are kept as raw text with helpers for literals, references, objects and
lists. That is all a policy checker needs, and it keeps the tool free of dependencies.
"""

from __future__ import annotations

import bisect
import re
from dataclasses import dataclass, field
from pathlib import Path

LiteralValue = bool | int | float | str | None

_IDENT_START = re.compile(r"[A-Za-z_]")
_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_\-]*")
_HEREDOC = re.compile(r"<<-?([A-Za-z_][A-Za-z0-9_]*)[ \t]*\r?\n")
_INT = re.compile(r"-?\d+")
_FLOAT = re.compile(r"-?\d+\.\d+")
_REF = re.compile(r"\b((?:data\.)?[a-z][a-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_\-]*)")
_TRAVERSAL = re.compile(
    r"\b((?:data\.)?[a-z][a-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_\-]*)(?:\[[^\]]*\])?(?:\.([A-Za-z_][A-Za-z0-9_\-]*))?"
)


class HclError(ValueError):
    """Raised when a file cannot be parsed."""

    def __init__(self, message: str, file: str, line: int) -> None:
        super().__init__(f"{file}:{line}: {message}")
        self.file = file
        self.line = line


@dataclass(frozen=True)
class Expr:
    """An expression kept as raw source text."""

    raw: str
    line: int

    def literal(self) -> tuple[bool, LiteralValue]:
        """Return (is_literal, value) for booleans, null, numbers and plain strings."""
        s = self.raw.strip()
        if s == "true":
            return True, True
        if s == "false":
            return True, False
        if s == "null":
            return True, None
        if _FLOAT.fullmatch(s):
            return True, float(s)
        if _INT.fullmatch(s):
            return True, int(s)
        if len(s) >= 2 and s.startswith('"') and s.endswith('"'):
            body = s[1:-1]
            if "${" in body.replace("$${", "") or "%{" in body:
                return False, None
            if _string_end(s, 0) != len(s):
                return False, None
            return True, _unescape(body)
        return False, None

    @property
    def is_literal(self) -> bool:
        return self.literal()[0]

    @property
    def value(self) -> LiteralValue:
        return self.literal()[1]

    def is_true(self) -> bool:
        ok, v = self.literal()
        return ok and v is True

    def is_false(self) -> bool:
        ok, v = self.literal()
        return ok and v is False

    def string(self) -> str | None:
        ok, v = self.literal()
        return v if ok and isinstance(v, str) else None

    def number(self) -> float | None:
        ok, v = self.literal()
        if ok and isinstance(v, (int, float)) and not isinstance(v, bool):
            return float(v)
        return None

    def refs(self) -> list[tuple[str, str]]:
        """References such as azurerm_key_vault.this or var.name, as (type, name)."""
        out: list[tuple[str, str]] = []
        for m in _REF.finditer(_strip_literal_strings(self.raw)):
            out.append((m.group(1), m.group(2)))
        for m in re.finditer(r"\$\{([^}]*)\}", self.raw):
            for r in _REF.finditer(m.group(1)):
                out.append((r.group(1), r.group(2)))
        return out

    def traversals(self) -> list[tuple[str, str, str | None]]:
        """References with up to three segments, as (root, name, attribute)."""
        out: list[tuple[str, str, str | None]] = []
        code = _strip_literal_strings(self.raw)
        for m in _TRAVERSAL.finditer(code):
            out.append((m.group(1), m.group(2), m.group(3)))
        return out

    def as_object(self) -> dict[str, Expr] | None:
        """Parse `{ key = value, ... }` into entries, or None if it is not a plain object."""
        s = self.raw.strip()
        if not (s.startswith("{") and s.endswith("}")):
            return None
        inner = s[1:-1]
        if re.match(r"\s*for\b", inner):
            return None
        try:
            p = _Parser(inner, "<expr>", line_offset=self.line - 1)
            attrs, blocks = p.parse_body(None, in_object=True)
        except HclError:
            return None
        if blocks:
            return None
        return {k: a.value for k, a in attrs.items()}

    def as_list(self) -> list[Expr] | None:
        s = self.raw.strip()
        if not (s.startswith("[") and s.endswith("]")):
            return None
        inner = s[1:-1]
        if re.match(r"\s*for\b", inner):
            return None
        return [Expr(part.strip(), self.line) for part in _split_top_level(inner) if part.strip()]


@dataclass(frozen=True)
class Attribute:
    name: str
    value: Expr
    line: int


@dataclass
class Block:
    type: str
    labels: tuple[str, ...]
    attrs: dict[str, Attribute]
    blocks: list[Block]
    line: int
    end_line: int
    file: Path
    comments: dict[int, str] = field(default_factory=dict, repr=False)

    @property
    def address(self) -> str:
        if self.type == "resource" and len(self.labels) == 2:
            return f"{self.labels[0]}.{self.labels[1]}"
        if self.type == "data" and len(self.labels) == 2:
            return f"data.{self.labels[0]}.{self.labels[1]}"
        if self.type in {"variable", "output", "module", "provider"} and self.labels:
            prefix = {"variable": "var", "output": "output"}.get(self.type, self.type)
            return f"{prefix}.{self.labels[0]}"
        return self.type

    def expr(self, name: str) -> Expr | None:
        a = self.attrs.get(name)
        return a.value if a else None

    def children(self, block_type: str) -> list[Block]:
        return [b for b in self.blocks if b.type == block_type]

    def child(self, block_type: str) -> Block | None:
        found = self.children(block_type)
        return found[0] if found else None

    def walk(self) -> list[Block]:
        out = [self]
        for b in self.blocks:
            out.extend(b.walk())
        return out


@dataclass
class HclFile:
    path: Path
    blocks: list[Block]
    comments: dict[int, str]
    text: str


def parse_file(path: Path) -> HclFile:
    text = path.read_text(encoding="utf-8")
    return parse_text(text, path)


def parse_text(text: str, path: Path | str = "<memory>") -> HclFile:
    p = _Parser(text, str(path))
    attrs, blocks = p.parse_body(None)
    top_attrs = {k: v for k, v in attrs.items()}
    if top_attrs:
        first = next(iter(top_attrs.values()))
        raise HclError("attributes are not allowed at the top level", str(path), first.line)
    for b in blocks:
        b.file = Path(path)
    return HclFile(Path(path), blocks, p.comments, text)


def _unescape(body: str) -> str:
    return (
        body.replace('\\"', '"')
        .replace("\\n", "\n")
        .replace("\\t", "\t")
        .replace("\\\\", "\\")
        .replace("$${", "${")
    )


def _string_end(t: str, i: int) -> int:
    """Index just after the string that opens at t[i]. Returns -1 if unterminated."""
    n = len(t)
    i += 1
    while i < n:
        c = t[i]
        if c == "\\":
            i += 2
            continue
        if c == '"':
            return i + 1
        if t.startswith("$${", i) or t.startswith("%%{", i):
            i += 3
            continue
        if c in "$%" and t.startswith("{", i + 1):
            i = _interp_end(t, i + 2)
            if i < 0:
                return -1
            continue
        i += 1
    return -1


def _interp_end(t: str, i: int) -> int:
    depth = 1
    n = len(t)
    while i < n:
        c = t[i]
        if c == '"':
            i = _string_end(t, i)
            if i < 0:
                return -1
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return -1


def _strip_literal_strings(raw: str) -> str:
    """Blank out quoted string text so identifiers inside strings are not read as references,
    while keeping interpolated code visible."""
    out: list[str] = []
    i, n = 0, len(raw)
    while i < n:
        if raw[i] == '"':
            end = _string_end(raw, i)
            if end < 0:
                out.append(raw[i:])
                break
            seg = raw[i:end]
            interps = re.findall(r"\$\{([^}]*)\}", seg)
            out.append(" " + " ".join(interps) + " ")
            i = end
            continue
        out.append(raw[i])
        i += 1
    return "".join(out)


def _split_top_level(s: str) -> list[str]:
    parts: list[str] = []
    depth = 0
    start = 0
    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if c == '"':
            end = _string_end(s, i)
            i = end if end > 0 else n
            continue
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        elif c == "," and depth == 0:
            parts.append(s[start:i])
            start = i + 1
        i += 1
    parts.append(s[start:])
    return parts


class _Parser:
    def __init__(self, text: str, file: str, line_offset: int = 0) -> None:
        self.t = text
        self.n = len(text)
        self.i = 0
        self.file = file
        self.offset = line_offset
        self.comments: dict[int, str] = {}
        self._starts = [0] + [m.end() for m in re.finditer(r"\n", text)]

    def line_at(self, i: int) -> int:
        return bisect.bisect_right(self._starts, i) + self.offset

    def err(self, msg: str, i: int | None = None) -> HclError:
        return HclError(msg, self.file, self.line_at(self.i if i is None else i))

    def _comment(self, start: int) -> int:
        end = self.t.find("\n", start)
        end = self.n if end < 0 else end
        self.comments[self.line_at(start)] = self.t[start:end].strip()
        return end

    def skip_ws(self, newlines: bool = True, commas: bool = False) -> None:
        t = self.t
        while self.i < self.n:
            c = t[self.i]
            if c in " \t\r" or (newlines and c == "\n") or (commas and c == ","):
                self.i += 1
            elif c == "#" or t.startswith("//", self.i):
                self.i = self._comment(self.i)
            elif t.startswith("/*", self.i):
                end = t.find("*/", self.i + 2)
                if end < 0:
                    raise self.err("unterminated comment")
                self.i = end + 2
            else:
                return

    def parse_body(
        self, closing: str | None, in_object: bool = False
    ) -> tuple[dict[str, Attribute], list[Block]]:
        attrs: dict[str, Attribute] = {}
        blocks: list[Block] = []
        t = self.t
        while True:
            self.skip_ws(newlines=True, commas=in_object)
            if self.i >= self.n:
                if closing:
                    raise self.err(f"expected {closing!r} before end of input")
                return attrs, blocks
            c = t[self.i]
            if closing and c == closing:
                self.i += 1
                return attrs, blocks
            start = self.i
            line = self.line_at(start)
            name = self._read_name()
            self.skip_ws(newlines=False)
            nxt = t[self.i : self.i + 1]
            is_assign = (nxt == "=" and t[self.i + 1 : self.i + 2] != "=") or (
                in_object and nxt == ":"
            )
            if is_assign:
                self.i += 1
                self.skip_ws(newlines=False)
                expr_start = self.i
                raw = self._scan_expr(stop_comma=in_object)
                attrs[name] = Attribute(name, Expr(raw.strip(), self.line_at(expr_start)), line)
                continue
            labels: list[str] = []
            while True:
                self.skip_ws(newlines=False)
                ch = t[self.i : self.i + 1]
                if ch == '"':
                    end = _string_end(t, self.i)
                    if end < 0:
                        raise self.err("unterminated string")
                    labels.append(t[self.i + 1 : end - 1])
                    self.i = end
                elif ch and _IDENT_START.match(ch):
                    labels.append(self._read_name())
                else:
                    break
            if t[self.i : self.i + 1] != "{":
                raise self.err(f"expected '=' or '{{' after {name!r}")
            self.i += 1
            sub_attrs, sub_blocks = self.parse_body("}")
            blocks.append(
                Block(
                    type=name,
                    labels=tuple(labels),
                    attrs=sub_attrs,
                    blocks=sub_blocks,
                    line=line,
                    end_line=self.line_at(self.i - 1),
                    file=Path(self.file),
                )
            )

    def _read_name(self) -> str:
        t = self.t
        if t[self.i : self.i + 1] == '"':
            end = _string_end(t, self.i)
            if end < 0:
                raise self.err("unterminated string")
            name = t[self.i + 1 : end - 1]
            self.i = end
            return name
        m = _IDENT.match(t, self.i)
        if not m:
            if t[self.i : self.i + 1] == "(":
                end = self.i
                depth = 0
                while end < self.n:
                    if t[end] == "(":
                        depth += 1
                    elif t[end] == ")":
                        depth -= 1
                        if depth == 0:
                            break
                    end += 1
                name = t[self.i : end + 1]
                self.i = end + 1
                return name
            raise self.err(f"unexpected character {t[self.i : self.i + 1]!r}")
        self.i = m.end()
        return m.group(0)

    def _scan_expr(self, stop_comma: bool) -> str:
        t = self.t
        start = self.i
        seg = start
        parts: list[str] = []
        depth = 0
        i = self.i
        while i < self.n:
            c = t[i]
            if c == '"':
                end = _string_end(t, i)
                if end < 0:
                    raise self.err("unterminated string", i)
                i = end
                continue
            if c == "<" and t.startswith("<<", i):
                m = _HEREDOC.match(t, i)
                if m:
                    tag = m.group(1)
                    j = m.end()
                    while j < self.n:
                        eol = t.find("\n", j)
                        eol = self.n if eol < 0 else eol
                        if t[j:eol].strip() == tag:
                            j = eol
                            break
                        j = eol + 1
                    i = j
                    continue
            if c in "([{":
                depth += 1
            elif c in ")]}":
                if depth == 0:
                    break
                depth -= 1
            elif c == "#" or t.startswith("//", i):
                parts.append(t[seg:i])
                i = self._comment(i)
                seg = i
                continue
            elif t.startswith("/*", i):
                end = t.find("*/", i + 2)
                if end < 0:
                    raise self.err("unterminated comment", i)
                parts.append(t[seg:i])
                i = end + 2
                seg = i
                continue
            elif (c == "\n" and depth == 0) or (c == "," and depth == 0 and stop_comma):
                break
            i += 1
        parts.append(t[seg:i])
        self.i = i
        return "".join(parts)
