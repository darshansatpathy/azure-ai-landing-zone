from __future__ import annotations

from pathlib import Path

import pytest

from tfpolicy.hcl import HclError, parse_text


def test_parses_blocks_labels_and_attributes() -> None:
    f = parse_text(
        'resource "azurerm_key_vault" "this" {\n  name = "kv"\n  sku  = var.sku\n}\n'
        'variable "x" {}\n'
    )
    kv, var = f.blocks
    assert kv.type == "resource" and kv.labels == ("azurerm_key_vault", "this")
    assert kv.address == "azurerm_key_vault.this"
    assert kv.expr("name") is not None and kv.expr("name").string() == "kv"  # type: ignore[union-attr]
    assert var.address == "var.x"
    assert (kv.line, kv.end_line) == (1, 4)


def test_nested_blocks_and_walk() -> None:
    f = parse_text('a "b" {\n  c {\n    d = 1\n    e {\n      g = true\n    }\n  }\n}\n')
    top = f.blocks[0]
    assert [b.type for b in top.walk()] == ["a", "c", "e"]
    assert top.child("c") is not None and top.child("zzz") is None
    assert top.children("c")[0].expr("d").number() == 1.0  # type: ignore[union-attr]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("true", (True, True)),
        ("false", (True, False)),
        ("null", (True, None)),
        ("42", (True, 42)),
        ("-7", (True, -7)),
        ("3.5", (True, 3.5)),
        ('"plain"', (True, "plain")),
        ('"a \\"quoted\\" word"', (True, 'a "quoted" word')),
        ('"has ${var.x} inside"', (False, None)),
        ("var.name", (False, None)),
        ('"a" + "b"', (False, None)),
    ],
)
def test_literals(raw: str, expected: tuple[bool, object]) -> None:
    f = parse_text(f"x {{\n  v = {raw}\n}}\n")
    assert f.blocks[0].expr("v").literal() == expected  # type: ignore[union-attr]


def test_literal_helpers() -> None:
    f = parse_text('x {\n  a = true\n  b = false\n  c = "s"\n  d = 2\n  e = var.q\n}\n')
    b = f.blocks[0]
    assert b.expr("a").is_true() and not b.expr("a").is_false()  # type: ignore[union-attr]
    assert b.expr("b").is_false()  # type: ignore[union-attr]
    assert b.expr("c").string() == "s" and b.expr("d").string() is None  # type: ignore[union-attr]
    assert b.expr("d").number() == 2.0 and b.expr("c").number() is None  # type: ignore[union-attr]
    assert b.expr("e").is_literal is False and b.expr("e").value is None  # type: ignore[union-attr]


def test_comments_are_ignored_and_recorded() -> None:
    text = (
        "# top comment\n"
        'resource "r" "n" { # trailing\n'
        '  a = "x" # keep out of the value\n'
        "  // slash comment\n"
        "  /* block\n     comment */\n"
        "  b = [\n    1, # one\n    2,\n  ]\n"
        "}\n"
    )
    f = parse_text(text)
    b = f.blocks[0]
    assert b.expr("a").string() == "x"  # type: ignore[union-attr]
    assert [e.raw for e in b.expr("b").as_list()] == ["1", "2"]  # type: ignore[union-attr]
    assert 1 in f.comments and 3 in f.comments


def test_strings_with_interpolation_and_nested_quotes() -> None:
    f = parse_text('x {\n  a = "${var.p}-${upper("z")}-end"\n  b = "next"\n}\n')
    assert f.blocks[0].expr("b").string() == "next"  # type: ignore[union-attr]
    assert f.blocks[0].expr("a").is_literal is False  # type: ignore[union-attr]


def test_escaped_interpolation_is_literal() -> None:
    f = parse_text('x {\n  a = "cost: $${not_interpolated}"\n}\n')
    assert f.blocks[0].expr("a").string() == "cost: ${not_interpolated}"  # type: ignore[union-attr]


def test_heredoc_is_one_expression() -> None:
    text = "x {\n  a = <<-EOT\n    line = one\n    } not a block end\n  EOT\n  b = 1\n}\n"
    b = parse_text(text).blocks[0]
    assert "not a block end" in b.expr("a").raw  # type: ignore[union-attr]
    assert b.expr("b").number() == 1.0  # type: ignore[union-attr]


def test_multiline_expressions_and_conditionals() -> None:
    text = 'x {\n  a = var.c ? {\n    k = 1\n  } : {}\n  b = merge(\n    var.t,\n    { n = "v" },\n  )\n}\n'
    b = parse_text(text).blocks[0]
    assert set(b.attrs) == {"a", "b"}
    assert b.expr("b").raw.startswith("merge(")  # type: ignore[union-attr]


def test_as_object_and_as_list() -> None:
    text = (
        'x {\n  t = {\n    environment = "dev"\n    "cost-center" = var.cc\n    cost-code = 1\n  }\n'
        '  one = { a = 1, b = "two" }\n  l = ["a", "b", var.c]\n  f = { for k, v in var.m : k => v }\n'
        "  n = var.other\n}\n"
    )
    b = parse_text(text).blocks[0]
    obj = b.expr("t").as_object()  # type: ignore[union-attr]
    assert obj is not None and set(obj) == {"environment", "cost-center", "cost-code"}
    inline = b.expr("one").as_object()  # type: ignore[union-attr]
    assert inline is not None and inline["b"].string() == "two"
    items = b.expr("l").as_list()  # type: ignore[union-attr]
    assert items is not None and [i.raw for i in items] == ['"a"', '"b"', "var.c"]
    assert b.expr("f").as_object() is None  # type: ignore[union-attr]
    assert b.expr("n").as_object() is None and b.expr("n").as_list() is None  # type: ignore[union-attr]


def test_colon_separated_object_entries() -> None:
    b = parse_text('x {\n  j = { "a": 1, "b": 2 }\n}\n').blocks[0]
    obj = b.expr("j").as_object()  # type: ignore[union-attr]
    assert obj is not None and obj["a"].number() == 1.0


def test_references() -> None:
    b = parse_text(
        'x {\n  a = azurerm_key_vault.this.id\n  b = "${var.prefix}-${local.suffix}"\n'
        '  c = "not_a.reference"\n  d = module.net.subnet_ids["apim"]\n  e = data.azurerm_client_config.current.tenant_id\n}\n'
    ).blocks[0]
    assert ("azurerm_key_vault", "this") in b.expr("a").refs()  # type: ignore[union-attr]
    assert {("var", "prefix"), ("local", "suffix")} <= set(b.expr("b").refs())  # type: ignore[union-attr]
    assert b.expr("c").refs() == []  # type: ignore[union-attr]
    assert ("module", "net", "subnet_ids") in b.expr("d").traversals()  # type: ignore[union-attr]
    assert ("data.azurerm_client_config", "current", "tenant_id") in b.expr("e").traversals()  # type: ignore[union-attr]


def test_dynamic_blocks_and_block_without_labels() -> None:
    f = parse_text(
        'locals {\n  a = 1\n}\nr "t" "n" {\n  dynamic "rule" {\n    for_each = var.x\n    content {\n      p = rule.value\n    }\n  }\n}\n'
    )
    assert f.blocks[0].address == "locals"
    assert f.blocks[1].child("dynamic") is not None


def test_data_and_module_addresses() -> None:
    f = parse_text(
        'data "azurerm_client_config" "current" {}\nmodule "net" {\n  source = "./x"\n}\noutput "o" {\n  value = 1\n}\nprovider "azurerm" {}\n'
    )
    assert [b.address for b in f.blocks] == [
        "data.azurerm_client_config.current",
        "module.net",
        "output.o",
        "provider.azurerm",
    ]


def test_line_numbers_are_one_based_and_attribute_aware() -> None:
    f = parse_text('r "t" "n" {\n  a = 1\n\n  b = 2\n}\n')
    assert f.blocks[0].attrs["b"].line == 4


@pytest.mark.parametrize(
    "text",
    [
        'r "t" "n" {\n  a = "unterminated\n}\n',
        'r "t" "n" {\n  a = 1\n',
        "a = 1\n",
        'r "t" "n"\n',
        "r {\n  a = (1\n}\n",
        "r {\n  /* never closed\n}\n",
        "r {\n  $ = 1\n}\n",
    ],
)
def test_syntax_errors_raise_with_location(text: str) -> None:
    with pytest.raises(HclError) as err:
        parse_text(text, Path("bad.tf"))
    assert "bad.tf" in str(err.value) and err.value.line >= 1
