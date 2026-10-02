"""User-visible shell completion and vendor ambiguity counterexamples."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from time import perf_counter

import pytest

from netconfiglint.commands.completion import Command, _next_tokens, commands, complete, detect_vendors
from scripts.audit_release import audit_archive


def texts(source: str, vendor: str = "", cursor: int | None = None) -> set[str]:
    result = complete(source, len(source) if cursor is None else cursor, (vendor,) if vendor else ())
    return {str(row["text"]) for row in result["items"]}


@pytest.mark.parametrize(
    "source",
    [
        "",
        "sysname test",
        "vlan 10\n" * 100,
        "system-view\nvlan 10\ninterface GigabitEthernet1/0/1\n shutdown",
        "description Huawei H3C\n# irf member 1 priority 32\n! stelnet server enable",
    ],
)
def test_shared_syntax_and_annotations_never_choose_a_vendor(source: str) -> None:
    assert set(detect_vendors(source)) == {"h3c", "huawei"}


@pytest.mark.parametrize(
    "source,vendor",
    [
        ("irf member 1 priority 32", "h3c"),
        ("port access vlan 10", "h3c"),
        ("stp global enable\nlldp global enable", "h3c"),
        ("interface Bridge-Aggregation1", "h3c"),
        ("line vty 0 63", "h3c"),
        ("version 7.1.070, Release 6715", "h3c"),
        ("port default vlan 10", "huawei"),
        ("stelnet server enable", "huawei"),
        ("interface Eth-Trunk1", "huawei"),
        ("eth-trunk 1", "huawei"),
        ("!Software Version V200R024C00SPC500", "huawei"),
    ],
)
def test_distinctive_syntax_identifies_vendor(source: str, vendor: str) -> None:
    assert detect_vendors(source) == (vendor,)


def test_mixed_vendor_and_forward_context() -> None:
    assert set(detect_vendors("irf member 1 priority 32\nport default vlan 10")) == {"h3c", "huawei"}
    result = complete("sys\nport access vlan 10", 3)
    assert result["vendors"] == ["H3C"]
    assert "system-view" in {row["text"] for row in result["items"]}
    assert set(complete("sys\nport access vlan 10\nport default vlan 20", 3)["vendors"]) == {"H3C", "Huawei"}


def test_repeated_shared_evidence_cannot_outvote_one_distinctive_stanza() -> None:
    assert detect_vendors("vlan 10\nsysname test\n" * 5000 + "port default vlan 10") == ("huawei",)


def test_long_mixed_buffer_is_not_sampled() -> None:
    padding = "description shared text\n" * 10000
    source = padding + "irf member 1 priority 32\n" + padding + "port default vlan 10\n" + padding
    assert set(detect_vendors(source)) == {"h3c", "huawei"}


@pytest.mark.parametrize("vendor", ["h3c", "huawei"])
def test_linux_prefix_ambiguity_parameters_and_undo(vendor: str) -> None:
    assert {"sysname", "system-view"} <= texts("sys", vendor)
    assert "route-static" in texts("ip rou", vendor)
    assert "as-number" in texts("peer 192.0.2.1 as", vendor)
    assert "vlan" in texts("undo port " + ("access" if vendor == "h3c" else "default") + " v", vendor)
    result = complete("sysnam", 6, (vendor,))
    assert result["insert"] == "sysname "
    assert "preference" in texts("ip route-static 198.51.100.0 24 192.0.2.1 pre", vendor)
    assert complete("sysname ", 8, (vendor,))["arguments"]


def test_whitespace_and_middle_token_preserve_surroundings() -> None:
    result = complete("  sysnam-old suffix\nnext", 7, ("h3c",))
    assert (result["start"], result["end"], result["insert"]) == (2, 12, "sysname")
    assert texts("\tIP\tROU", "h3c") >= {"route-static"}
    assert not complete("# sys", 5)["items"]
    assert not complete('description "sys', 16)["items"]


def test_unicode_qml_offsets_and_empty_caret() -> None:
    source = "description 🐱 中文\nsysnam"
    cursor = len(source.encode("utf-16-le")) // 2
    result = complete(source, cursor, ("h3c",))
    assert result["end"] == cursor
    assert result["start"] == cursor - 6
    assert result["insert"] == "sysname "
    result = complete("sysname", 0, ("h3c",))
    assert result["start"] == 0 and result["end"] == 7


def test_nested_choices_optional_parameters_and_repetition() -> None:
    entry = Command(
        "h3c", "test [ vpn-instance <name> ] { permit | deny } <value> [ to <end> ] *", (), "", ()
    )
    assert _next_tokens(entry, ["test"]) == {"vpn-instance", "permit", "deny"}
    assert _next_tokens(entry, ["test", "vpn-instance", "example"]) == {"permit", "deny"}
    assert _next_tokens(entry, ["test", "permit", "10"]) == {"to"}
    assert _next_tokens(entry, ["test", "permit", "10", "to", "20"]) == {"to"}


def test_catalog_has_independent_provenance_and_no_user_values() -> None:
    for vendor, minimum in (("h3c", 8000), ("huawei", 20000)):
        entries = [entry for entry in commands() if entry.vendor == vendor]
        assert len(entries) > minimum
        assert all(entry.source.startswith("https://") and vendor in entry.source for entry in entries)
        assert all(not entry.syntax.startswith(("For ", "In ", "System view")) for entry in entries)
        assert not any("<>" in entry.syntax for entry in entries)
        raw = json.loads(
            (Path(__file__).parents[2] / f"netconfiglint/commands/data/{vendor}.json").read_text("utf8")
        )
        assert raw["vendor"] == vendor and raw["manuals"]


def test_warm_completion_remains_responsive() -> None:
    complete("undo port a", 11, ("h3c",))
    started = perf_counter()
    for _ in range(10):
        assert texts("undo port a", "h3c")
    assert perf_counter() - started < 2.5


@pytest.mark.parametrize("vendor", ["h3c", "huawei"])
def test_interface_types_and_declared_objects(vendor: str) -> None:
    assert "GigabitEthernet" in texts("interface G", vendor)
    source = "ip vpn-instance synthetic\ninterface GigabitEthernet1/0/1\n ip binding vpn-instance syn"
    assert "synthetic" in texts(source, vendor)
    source = "local-user SECRET password cipher PRIVATE\npassword PRIVATE\n sysname "
    assert not texts(source, vendor)


def test_manual_override_and_two_vendor_deduplication() -> None:
    result = complete("sys\nport access vlan 10", 3, ("huawei",))
    assert result["vendors"] == ["Huawei"]
    result = complete("sys", 3, ("h3c", "huawei"))
    names = [row["text"] for row in result["items"]]
    assert len(names) == len(set(names))
    assert next(row for row in result["items"] if row["text"] == "sysname")["vendors"] == ["H3C", "Huawei"]


def test_release_audit_checks_catalog_against_source(tmp_path: Path) -> None:
    relative = "netconfiglint/commands/data/h3c.json"
    source = tmp_path / relative
    source.parent.mkdir(parents=True)
    source.write_text('{"vendor": "h3c"}', encoding="utf-8")
    archive = tmp_path / "portable.zip"
    with zipfile.ZipFile(archive, "w") as package:
        package.write(source, "runtime/" + relative)
    assert audit_archive(tmp_path, archive)["passed"]
    source.write_text('{"vendor": "huawei"}', encoding="utf-8")
    result = audit_archive(tmp_path, archive)
    assert not result["passed"] and result["resource_mismatches"] == [relative]
    with zipfile.ZipFile(archive, "w"):
        pass
    result = audit_archive(tmp_path, archive)
    assert not result["passed"] and result["missing_resources"] == [relative]
