"""Command-family inventory must distinguish known syntax from semantic proof."""

import pytest

from netconfiglint import analyze
from netconfiglint.commands.catalog import catalogued_family, is_annotation


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
