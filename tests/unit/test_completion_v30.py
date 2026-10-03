"""Completion fixes exercised through the same public API used by both editors."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from netconfiglint.commands.completion import commands, complete
from netconfiglint.commands.objects import declared


def result(text: str, vendor: str) -> dict[str, object]:
    return complete(text, len(text.encode("utf-16-le")) // 2, (vendor,))


def names(text: str, vendor: str) -> set[str]:
    rows = result(text, vendor)["items"]
    assert isinstance(rows, list)
    return {row["text"] for row in rows}


def test_exact_keywords_lock_across_catalog_branches() -> None:
    assert names("port trunk a", "huawei") == {"allow-pass"}
    data = result("interface GigabitEthernet 1/0/1 ", "h3c")
    assert isinstance(data["items"], list)
    assert all(not item["syntax"].startswith("interface-peer") for item in data["items"])
    assert "<as-number>" not in data["arguments"]
    assert names("sys", "h3c") >= {"sysname", "system-view"}


@pytest.mark.parametrize("vendor", ["h3c", "huawei"])
@pytest.mark.parametrize("prompt", ["[SW] ", "<SW> ", "[~SW] ", "[*SW] "])
def test_terminal_prompt_unicode_replacement_preserves_original(prompt: str, vendor: str) -> None:
    text = "# 中文 🐱\n" + prompt + "sysnam"
    data = result(text, vendor)
    assert data["insert"] == "sysname "
    assert data["start"] == len(text.encode("utf-16-le")) // 2 - 6
    assert not names("# sysnam", vendor)


@pytest.mark.parametrize("vendor", ["h3c", "huawei"])
def test_effective_complete_declarations_and_case_sensitive_names(vendor: str) -> None:
    assert not names("ip vpn-instance BLUE\nundo ip vpn-instance BLUE\nip binding vpn-instance B", vendor)
    assert not names("route-policy PARTIAL\npeer 192.0.2.1 route-policy P", vendor)
    text = "route-policy VALID permit node 10\nroute-policy VALID deny node 20\n"
    text += "undo route-policy VALID permit node 10\npeer 192.0.2.1 route-policy V"
    assert "VALID" in names(text, vendor)
    policy = "qos policy" if vendor == "h3c" else "traffic policy"
    reference = "qos apply policy" if vendor == "h3c" else "traffic-policy"
    assert {"Mixed", "mixed"} <= names(f"{policy} Mixed\n{policy} mixed\n{reference} mi", vendor)
    assert "Mixed" not in names(f"{policy} Mixed\nssl server-policy M", vendor)


@pytest.mark.parametrize("vendor", ["h3c", "huawei"])
@pytest.mark.parametrize("separator", [" ", "  ", "\t"])
def test_spacing_and_interface_numbers_are_normalized(vendor: str, separator: str) -> None:
    text = f"ip{separator}vpn-instance NAME\ninterface{separator}GigabitEthernet{separator}1/0/1\n"
    text += "interface 10GE 2/0/1\n" if vendor == "huawei" else "interface Twenty-FiveGigE 2/0/1\n"
    assert "NAME" in names(text + "ip binding vpn-instance N", vendor)
    reference = "ping -i Gi" if vendor == "huawei" else "display ipv6 neighbors statistics interface Gi"
    assert "GigabitEthernet1/0/1" in names(text + reference, vendor)
    assert names(text + "display interface GigabitEthernet 1/0/", vendor) == {"1/0/1"}
    assert "2/0/1" not in names(text + "display interface GigabitEthernet ", vendor)


@pytest.mark.parametrize(
    "vendor,line,expected",
    [
        ("h3c", "import route-policy OBJ", "OBJECT_ROUTE"),
        ("huawei", "aggregate 192.0.2.0 24 attribute-policy OBJ", "OBJECT_ROUTE"),
        ("h3c", "if-match acl name OBJ", "OBJECT_ACL"),
        ("huawei", "if-match acl OBJ", "OBJECT_ACL"),
        ("h3c", "if-match ip address prefix-list OBJ", "OBJECT_PREFIX"),
        ("huawei", "if-match ip-prefix OBJ", "OBJECT_PREFIX"),
        ("h3c", "rule 10 permit ip time-range OBJ", "OBJECT_TIME"),
        ("huawei", "rule 10 permit ip time-range OBJ", "OBJECT_TIME"),
        ("h3c", "dhcp server apply ip-pool OBJ", "OBJECT_POOL"),
        ("h3c", "ssl server-policy OBJ", "OBJECT_SERVER"),
        ("huawei", "ssl policy OBJ", "OBJECT_SSL"),
        ("h3c", "peer OBJ", "OBJECT_GROUP"),
        ("huawei", "peer OBJ", "OBJECT_GROUP"),
    ],
)
def test_parameter_aliases_and_separate_document_namespaces(vendor: str, line: str, expected: str) -> None:
    source = "\n".join(
        [
            "route-policy OBJECT_ROUTE permit node 10",
            "acl name OBJECT_ACL basic",
            "ip ip-prefix OBJECT_PREFIX index 10 permit 192.0.2.0 24",
            "ip prefix-list OBJECT_PREFIX index 10 permit 192.0.2.0 24",
            "time-range OBJECT_TIME 08:00 to 18:00 daily",
            "dhcp server ip-pool OBJECT_POOL",
            "ssl server-policy OBJECT_SERVER",
            "ssl client-policy OBJECT_CLIENT",
            "ssl policy OBJECT_SSL",
            "bgp 65000",
            " group OBJECT_GROUP external",
            "#",
            "wlan group OBJECT_WLAN",
            "#",
            "",
        ]
    )
    candidates = names(source + line, vendor)
    assert expected in candidates
    assert "OBJECT_WLAN" not in candidates
    if "ssl" in line:
        assert "OBJECT_ROUTE" not in candidates and "OBJECT_CLIENT" not in candidates


@pytest.mark.parametrize("vendor", ["h3c", "huawei"])
def test_acl_category_namespaces_do_not_cross(vendor: str) -> None:
    objects = declared(
        "acl number 2001\nacl number 3001\nacl ipv6 name IPV6 basic\nacl name IPV4 basic", vendor
    )
    assert objects["acl-basic-number"] == ("2001",)
    assert objects["acl-advanced-number"] == ("3001",)
    assert objects["acl-ipv6-name"] == ("IPV6",)
    assert objects["acl-ipv4-name"] == ("IPV4",)


@pytest.mark.parametrize(
    "vendor,prefix,expected",
    [
        ("h3c", "interface Twenty", "Twenty-FiveGigE"),
        ("h3c", "display interface Fifty", "FiftyGigE"),
        ("huawei", "display interface Multi", "MultiGE"),
        ("huawei", "interface nv", "Nve"),
        ("huawei", "interface lo", "LoopBack"),
        ("h3c", "interface lo", "LoopBack"),
        ("h3c", "interface Vlan", "Vlan-interface"),
    ],
)
def test_documented_interface_domains_and_cli_case_deduplication(
    vendor: str, prefix: str, expected: str
) -> None:
    data = result(prefix, vendor)
    matching = [item for item in data["items"] if item["text"].lower() == expected.lower()]
    assert len(matching) == 1
    assert matching[0]["text"] == expected
    assert data["insert"] == expected + " "


@pytest.mark.parametrize("undo", ["", "undo "])
def test_shared_arp_prefix_keeps_both_real_source_branches(undo: str) -> None:
    prefix = undo + "arp static 192.0.2.1 0000-0000-0001 vni 100 "
    assert names(prefix + "so", "huawei") == {"source-ip", "source-ipv6"}
    assert "peer-ipv6" in names(prefix + "source-ipv6 2001:db8::1 pe", "huawei")
    assert not names("source-ipv6 ", "huawei")
    assert not names("-kc ", "huawei")
    assert "permit" in names("perm", "huawei")


def test_format_annotations_are_metadata_and_not_insertable_cli() -> None:
    assert not names("assign resource-mode enhanced-mac all ", "huawei")
    selected = next(
        entry
        for entry in commands()
        if entry.syntax.startswith("assign resource-mode ")
        and "enhanced-mac" in entry.syntax
        and "all" in entry.syntax
    )
    assert selected.annotations and all("(" not in entry.syntax for entry in [selected])


def test_exact_missing_manual_forms_and_multisource_provenance() -> None:
    for undo in ("", "undo "):
        assert "querier-election" in names("vlan 10\n" + undo + "igmp-snooping q", "h3c")
    sysname = next(
        entry for entry in commands() if entry.vendor == "huawei" and entry.syntax == "sysname <host-name>"
    )
    assert len(sysname.sources) == 3
    item = next(row for row in result("sysnam", "huawei")["items"] if row["text"] == "sysname")
    assert item["syntaxDetails"] and len(item["sources"]) == 3
    data = result("peer ", "huawei")
    assert data["argumentDetails"]
    assert set(data["arguments"]) == {alias for row in data["argumentDetails"] for alias in row["aliases"]}


def test_complete_historical_chapters_remain_scoped_and_unverified() -> None:
    folder = Path(__file__).parents[2] / "netconfiglint/commands/data"
    supplement = json.loads((folder / "h3c_legacy.json").read_text("utf-8"))
    current = {entry.syntax: entry for entry in commands() if entry.vendor == "h3c"}
    assert len(supplement["commands"]) == 450
    for row in supplement["commands"]:
        assert row["syntax"] in current
        assert any("not implemented" in note for origin in row["sources"] for note in origin["annotations"])
    assert "ipx" not in names("", "h3c")
    assert "wlan-radio" not in {name.casefold() for name in names("interface ", "h3c")}
    assert "wlan-bss" not in {name.casefold() for name in names("interface ", "h3c")}
    assert names("ipx ", "h3c")
