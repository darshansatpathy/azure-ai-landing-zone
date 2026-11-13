"""Rule registry, module loading, suppressions and the check runner."""

from __future__ import annotations

import re
import tomllib
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

from .hcl import Block, HclError, HclFile, parse_file

SEVERITIES = ("info", "low", "medium", "high", "critical")
_SUPPRESS = re.compile(r"tfpolicy:ignore\s+(TFP\d{3})(?:\s+reason=\"([^\"]*)\")?")
_SKIP_DIRS = {".terraform", ".git", "node_modules", ".venv", "__pycache__"}


def severity_rank(sev: str) -> int:
    return SEVERITIES.index(sev)


@dataclass(frozen=True)
class RuleInfo:
    id: str
    title: str
    severity: str
    rationale: str
    remediation: str
    benchmark: str


@dataclass(frozen=True)
class Hit:
    """What a rule reports. The engine turns it into a Finding."""

    message: str
    block: Block | None = None
    line: int | None = None
    file: Path | None = None


@dataclass(frozen=True)
class Finding:
    rule_id: str
    severity: str
    message: str
    file: str
    line: int
    resource: str
    suppressed: bool = False
    reason: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "rule": self.rule_id,
            "severity": self.severity,
            "message": self.message,
            "file": self.file,
            "line": self.line,
            "resource": self.resource,
            "suppressed": self.suppressed,
            "reason": self.reason,
        }


@dataclass
class Config:
    paths: list[str] = field(default_factory=lambda: ["terraform"])
    required_tags: list[str] = field(
        default_factory=lambda: ["environment", "owner", "cost-center", "data-classification"]
    )
    fail_on: str = "medium"
    disabled: dict[str, str] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path | None) -> Config:
        cfg = cls()
        if path is None or not path.exists():
            return cfg
        data = tomllib.loads(path.read_text(encoding="utf-8")).get("tfpolicy", {})
        cfg.paths = list(data.get("paths", cfg.paths))
        cfg.required_tags = list(data.get("required_tags", cfg.required_tags))
        cfg.fail_on = str(data.get("fail_on", cfg.fail_on))
        if cfg.fail_on not in SEVERITIES:
            raise ValueError(f"fail_on must be one of {SEVERITIES}")
        disabled = data.get("disabled", {})
        for rule_id, reason in disabled.items():
            if not str(reason).strip():
                raise ValueError(f"disabling {rule_id} requires a written reason")
        cfg.disabled = {str(k): str(v) for k, v in disabled.items()}
        return cfg


@dataclass
class ModuleView:
    """All Terraform in one directory, parsed."""

    path: Path
    files: list[HclFile]
    other_files: dict[Path, str]

    @property
    def blocks(self) -> list[Block]:
        return [b for f in self.files for b in f.blocks]

    def resources(self, *types: str) -> list[Block]:
        return [
            b
            for b in self.blocks
            if b.type == "resource" and (not types or (b.labels and b.labels[0] in types))
        ]

    def of_type(self, block_type: str) -> list[Block]:
        return [b for b in self.blocks if b.type == block_type]

    def comments_for(self, block: Block) -> dict[int, str]:
        for f in self.files:
            if f.path == block.file:
                return f.comments
        return {}


RuleFn = Callable[[ModuleView, Config], Iterable[Hit]]
_REGISTRY: list[tuple[RuleInfo, RuleFn]] = []


def rule(
    id: str,
    title: str,
    severity: str,
    rationale: str,
    remediation: str,
    benchmark: str,
) -> Callable[[RuleFn], RuleFn]:
    assert severity in SEVERITIES

    def deco(fn: RuleFn) -> RuleFn:
        _REGISTRY.append((RuleInfo(id, title, severity, rationale, remediation, benchmark), fn))
        return fn

    return deco


def all_rules() -> list[RuleInfo]:
    from . import rules as _rules  # noqa: F401  (registers rules on import)

    return sorted((info for info, _ in _REGISTRY), key=lambda r: r.id)


@dataclass
class Report:
    findings: list[Finding]
    modules: list[str]
    rules_run: list[str]
    disabled: dict[str, str]

    @property
    def active(self) -> list[Finding]:
        return [f for f in self.findings if not f.suppressed]

    @property
    def suppressed(self) -> list[Finding]:
        return [f for f in self.findings if f.suppressed]

    def failing(self, fail_on: str) -> list[Finding]:
        threshold = severity_rank(fail_on)
        return [f for f in self.active if severity_rank(f.severity) >= threshold]


def discover_modules(paths: Iterable[Path]) -> list[Path]:
    found: set[Path] = set()
    for root in paths:
        if root.is_file():
            found.add(root.parent)
            continue
        for tf in root.rglob("*.tf"):
            if any(part in _SKIP_DIRS for part in tf.parts):
                continue
            found.add(tf.parent)
    return sorted(found)


def load_module(directory: Path) -> tuple[ModuleView, list[Finding]]:
    files: list[HclFile] = []
    errors: list[Finding] = []
    for tf in sorted(directory.glob("*.tf")):
        try:
            files.append(parse_file(tf))
        except HclError as exc:
            errors.append(
                Finding("TFP-PARSE", "critical", str(exc), str(tf), exc.line, "parse", False, "")
            )
    other: dict[Path, str] = {}
    for pattern in ("*.xml", "*.xml.tftpl", "*.tfvars", "*.tftpl", "*.json"):
        for f in sorted(directory.glob(pattern)):
            other[f] = f.read_text(encoding="utf-8")
    return ModuleView(directory, files, other), errors


def _suppressions(
    view: ModuleView, block: Block | None, file: Path | None
) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    if block is not None:
        comments = view.comments_for(block)
        for line in (block.line - 1, block.line):
            for m in _SUPPRESS.finditer(comments.get(line, "")):
                out.append((m.group(1), m.group(2) or ""))
    elif file is not None and file in view.other_files:
        for m in re.finditer(
            r"tfpolicy:ignore\s+(TFP\d{3})(?:\s+reason=\"([^\"]*)\")?", view.other_files[file]
        ):
            out.append((m.group(1), m.group(2) or ""))
    return out


def _relative(path: Path | None, base: Path) -> str:
    if path is None:
        return ""
    try:
        return str(path.resolve().relative_to(base.resolve()))
    except ValueError:
        return str(path)


def _iter_hits(view: ModuleView, cfg: Config) -> Iterator[tuple[RuleInfo, Hit]]:
    from . import rules as _rules  # noqa: F401

    for info, fn in _REGISTRY:
        if info.id in cfg.disabled:
            continue
        for hit in fn(view, cfg):
            yield info, hit


def run(paths: Iterable[Path], cfg: Config, base: Path | None = None) -> Report:
    from . import rules as _rules  # noqa: F401

    base = base or Path.cwd()
    findings: list[Finding] = []
    modules: list[str] = []
    for directory in discover_modules(paths):
        view, parse_errors = load_module(directory)
        findings.extend(parse_errors)
        modules.append(_relative(directory, base))
        for info, hit in _iter_hits(view, cfg):
            file = hit.block.file if hit.block else hit.file
            line = hit.line or (hit.block.line if hit.block else 1)
            resource = hit.block.address if hit.block else ""
            sup = [r for rid, r in _suppressions(view, hit.block, hit.file) if rid == info.id]
            suppressed = False
            reason = ""
            if sup:
                if sup[0].strip():
                    suppressed, reason = True, sup[0].strip()
                else:
                    findings.append(
                        Finding(
                            "TFP000",
                            "medium",
                            f"suppression of {info.id} has no reason",
                            _relative(file, base),
                            line,
                            resource,
                        )
                    )
            findings.append(
                Finding(
                    info.id,
                    info.severity,
                    hit.message,
                    _relative(file, base),
                    line,
                    resource,
                    suppressed,
                    reason,
                )
            )
    findings.sort(key=lambda f: (-severity_rank(f.severity), f.file, f.line, f.rule_id))
    ids = [i.id for i in all_rules() if i.id not in cfg.disabled]
    return Report(findings, modules, ids, dict(cfg.disabled))
