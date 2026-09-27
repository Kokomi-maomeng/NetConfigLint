"""Command-family inventory must distinguish known syntax from semantic proof."""

import json
from pathlib import Path

import pytest

from netconfiglint import analyze
from netconfiglint.commands.catalog import H3C_FAMILIES, HUAWEI_FAMILIES, catalogued_family, is_annotation


@pytest.mark.parametrize(
    ("vendor", "commands"),
    [
        (
            "h3c",
            [
                "stp global enable",
                "stp mode mstp",
                "info-center loghost 192.0.2.1",
                "info-center source default loghost level informational",
                "lldp timer tx-interval 30",
                "igmp-snooping enable",
                "qos apply policy EXAMPLE inbound",
            ],
        ),
        (
            "huawei",
            [
                "stp enable",
                "stp mode mstp",
                "info-center loghost 192.0.2.1",
                "info-center source default channel 2 log level informational",
                "lldp enable",
                "igmp-snooping enable",
                "qos car inbound cir 1000",
            ],
        ),
    ],
)
def test_documented_command_families_are_identified(vendor: str, commands: list[str]) -> None:
    assert all(catalogued_family(vendor, command) is not None for command in commands)


@pytest.mark.parametrize("vendor", ["h3c", "huawei"])
def test_unknown_spelling_is_not_assumed_supported(vendor: str) -> None:
    assert catalogued_family(vendor, "stp unicorn enable") is None
    assert catalogued_family(vendor, "info-center imaginary 192.0.2.1") is None


@pytest.mark.parametrize("vendor,stp", [("h3c", "stp global enable"), ("huawei", "stp mode mstp")])
def test_annotations_are_not_commands_and_catalogue_is_not_semantic_proof(vendor: str, stp: str) -> None:
    source = f"{stp}\ninfo-center loghost 192.0.2.1\n备注\uff1a此行为人工说明\n"
    result = analyze(source, mode="full", vendor=vendor)
    assert result.coverage["ignored"] == 1
    assert result.coverage["unsupported"] == 0
    assert result.coverage["unparsed"] == 0
    assert result.coverage["catalogued"] >= 1
    assert result.coverage["semantic_complete"] is False
    assert not any(item.rule_id == "H3C-CMD-001" for item in result.diagnostics)


def test_annotation_keeps_chinese_arguments_as_command_data() -> None:
    assert is_annotation("说明\uff1a这是一行文字")
    assert not is_annotation("description 中文办公网")


def test_annotation_with_sensitive_keyword_is_still_inventoried() -> None:
    result = analyze("备注\uff1a请勿记录 password 值", mode="full", vendor="huawei")
    assert result.coverage["ignored"] == 1
    assert [item.line for item in result.config.sensitive_lines] == [1]


def test_h3c_system_command_in_interface_view_stays_unknown() -> None:
    result = analyze(
        "interface GigabitEthernet1/0/1\n info-center loghost 192.0.2.1\n",
        mode="full",
        vendor="h3c",
    )
    assert result.coverage["unsupported_lines"] == [2]
    assert any(item.rule_id == "H3C-CMD-001" and item.source.line == 2 for item in result.diagnostics)


def test_h3c_catalog_does_not_inherit_huawei_family_accounting() -> None:
    result = analyze(
        "stp global enable\ninfo-center loghost 192.0.2.1\n",
        mode="full",
        vendor="h3c",
    )
    assert result.coverage["catalogued_lines"] == [1, 2]
    assert result.coverage["catalogued_families"] == [
        {"family": "info_center", "count": 1},
        {"family": "stp", "count": 1},
    ]


def test_every_family_has_vendor_source_and_bilingual_label() -> None:
    root = Path(__file__).parents[2] / "netconfiglint/gui/i18n"
    catalogs = [json.loads((root / name).read_text(encoding="utf-8")) for name in ("en.json", "zh_CN.json")]
    for vendor, families, domain in (
        ("h3c", H3C_FAMILIES, "h3c.com"),
        ("huawei", HUAWEI_FAMILIES, "huawei.com"),
    ):
        assert len(families) >= 10, vendor
        for family in families:
            assert family.source.startswith("https://") and domain in family.source
            assert all(f"command.family.{family.name}" in catalog for catalog in catalogs)
