from __future__ import annotations

from pathlib import Path

import pytest

from tfpolicy.fmt import check_paths, check_text

GOOD = """\
resource "azurerm_resource_group" "this" {
  name     = "rg"
  location = "westeurope"
  tags     = var.tags

  identity {
    type = "SystemAssigned"
  }
}

locals {
  tags = merge(var.tags, {
    owner = "x"
  })
  list = [
    "a",
    "b",
  ]
}
"""


def messages(text: str) -> list[str]:
    return [i.message for i in check_text(text, "f.tf")]


def test_canonical_text_passes() -> None:
    assert messages(GOOD) == []


def test_multi_line_attribute_is_not_aligned_with_neighbours() -> None:
    text = 'r "t" "n" {\n  name = "x"\n  tags = {\n    a = 1\n  }\n}\n'
    assert messages(text) == []


@pytest.mark.parametrize(
    ("text", "needle"),
    [
        ('r "t" "n" {\n    name = "x"\n}\n', "indent"),
        ('r "t" "n" {\nname = "x"\n}\n', "indent"),
        ('r "t" "n" {\n  name = "x"\n  location = "y"\n}\n', "aligned"),
        ('r "t" "n" {\n  name     = "x"\n  location = "y"\n  a    = 1\n}\n', "aligned"),
        ('r "t" "n" {\n  name  = "x"\n}\n', "aligned"),
        ('r "t" "n" {\n\tname = "x"\n}\n', "tab"),
        ('r "t" "n" {\n  name = "x" \n}\n', "trailing"),
        ('r "t" "n" {\n  name = "x"\n}', "newline"),
        ('r "t" "n" {\n  name = "x"\n}\n\n', "blank"),
        ('r "t" "n" {\n  name = "x"\n\n\n  b = 1\n}\n', "consecutive"),
        ('r "t" "n" {\n  tags = {\n  a = 1\n  }\n}\n', "indent"),
    ],
)
def test_detects_formatting_problems(text: str, needle: str) -> None:
    assert any(needle in m for m in messages(text)), messages(text)


def test_blank_lines_and_comments_separate_alignment_groups() -> None:
    text = 'r "t" "n" {\n  a = 1\n\n  bbbb = 2\n  # note\n  cc = 3\n}\n'
    assert messages(text) == []


def test_heredoc_bodies_are_not_checked() -> None:
    text = 'r "t" "n" {\n  a = <<-EOT\n\tanything   goes\n   here   \n  EOT\n  b = 1\n}\n'
    assert not any("tab" in m or "trailing" in m for m in messages(text))


def test_brackets_in_strings_and_comments_are_ignored() -> None:
    text = 'r "t" "n" {\n  a = "{ not a block"\n  b = 1 # ) also not\n}\n'
    assert messages(text) == []


def test_closing_and_reopening_lines() -> None:
    text = 'r "t" "n" {\n  a = [\n    {\n      k = 1\n    },\n    {\n      k = 2\n    },\n  ]\n}\n'
    assert messages(text) == []


def test_check_paths_reads_tf_and_tfvars(tmp_path: Path) -> None:
    (tmp_path / "ok.tf").write_text(GOOD, encoding="utf-8")
    (tmp_path / "bad.tfvars").write_text("a = 1\nbbb = 2\n", encoding="utf-8")
    skipped = tmp_path / ".terraform"
    skipped.mkdir()
    (skipped / "x.tf").write_text("bad  =  1", encoding="utf-8")
    issues = check_paths([tmp_path])
    assert {Path(i.file).name for i in issues} == {"bad.tfvars"}
    assert check_paths([tmp_path / "ok.tf"]) == []
