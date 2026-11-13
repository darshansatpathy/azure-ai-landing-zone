from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from tfpolicy.engine import Config, Finding, Report, run

ROOT = Path(__file__).resolve().parent.parent

TERRAFORM_HEADER = """\
terraform {
  required_version = ">= 1.9.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
  }
}

"""


@pytest.fixture
def repo_root() -> Path:
    return ROOT


@pytest.fixture
def scan(tmp_path: Path) -> Callable[..., Report]:
    """Write files into a temp module directory and run the engine on it."""

    def _scan(
        files: dict[str, str] | str, *, header: bool = True, cfg: Config | None = None
    ) -> Report:
        if isinstance(files, str):
            files = {"main.tf": files}
        for old in sorted(tmp_path.rglob("*"), reverse=True):
            old.unlink() if old.is_file() else old.rmdir()
        for name, text in files.items():
            path = tmp_path / name
            path.parent.mkdir(parents=True, exist_ok=True)
            body = TERRAFORM_HEADER + text if header and name == "main.tf" else text
            path.write_text(body, encoding="utf-8")
        return run([tmp_path], cfg or Config(), base=tmp_path)

    return _scan


def ids(report: Report, *, active_only: bool = True) -> list[str]:
    found: list[Finding] = report.active if active_only else report.findings
    return sorted({f.rule_id for f in found})
