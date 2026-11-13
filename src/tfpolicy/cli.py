"""Command line interface: tfpolicy check | fmt-check | rules."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from . import __version__, report
from .engine import SEVERITIES, Config, run
from .fmt import check_paths


def _build() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="tfpolicy", description="Policy as code for Terraform.")
    p.add_argument("--version", action="version", version=f"tfpolicy {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("check", help="check Terraform against the policy rules")
    c.add_argument(
        "paths", nargs="*", type=Path, help="directories or files (default: config paths)"
    )
    c.add_argument("--config", type=Path, default=Path("tfpolicy.toml"))
    c.add_argument("--format", choices=["text", "json", "markdown", "sarif"], default="text")
    c.add_argument("--output", type=Path, help="write the report here instead of stdout")
    c.add_argument("--fail-on", choices=SEVERITIES, help="lowest severity that fails the run")

    f = sub.add_parser("fmt-check", help="check canonical Terraform formatting")
    f.add_argument("paths", nargs="+", type=Path)

    r = sub.add_parser("rules", help="list the rules")
    r.add_argument("--format", choices=["text", "markdown"], default="text")
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = _build().parse_args(argv)
    if args.cmd == "rules":
        from .engine import all_rules

        if args.format == "markdown":
            sys.stdout.write(report.rules_markdown())
        else:
            for r in all_rules():
                sys.stdout.write(f"{r.id}  {r.severity:<8} {r.title}\n")
        return 0

    if args.cmd == "fmt-check":
        issues = check_paths(list(args.paths))
        for i in issues:
            sys.stdout.write(f"{i.file}:{i.line}: {i.message}\n")
        sys.stdout.write(f"{len(issues)} formatting issues\n")
        return 1 if issues else 0

    cfg = Config.load(args.config)
    fail_on = args.fail_on or cfg.fail_on
    paths = list(args.paths) or [Path(p) for p in cfg.paths]
    missing = [str(p) for p in paths if not p.exists()]
    if missing:
        sys.stderr.write(f"path not found: {', '.join(missing)}\n")
        return 2
    rep = run(paths, cfg)
    render = {
        "text": report.to_text,
        "json": report.to_json,
        "markdown": report.to_markdown,
        "sarif": report.to_sarif,
    }[args.format]
    text = render(rep, fail_on)
    if args.output:
        args.output.write_text(text, encoding="utf-8")
        sys.stdout.write(report.to_text(rep, fail_on))
    else:
        sys.stdout.write(text)
    return 1 if rep.failing(fail_on) else 0


if __name__ == "__main__":
    raise SystemExit(main())
