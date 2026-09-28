"""Native Comware examples qualify every independently registered H3C rule."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from netconfiglint import analyze
from netconfiglint.vendors.h3c.rules import H3C_RULES

ROOT = Path(__file__).parents[1] / "fixtures" / "h3c" / "rules"
CASES = tuple(sorted(path.name for path in ROOT.iterdir() if path.is_dir()))


@pytest.mark.parametrize("rule_id", CASES)
def test_native_comware_invalid_and_valid_examples(rule_id: str) -> None:
    case = ROOT / rule_id
    expected = json.loads((case / "expected.json").read_text("utf-8"))
    invalid = (case / "invalid.cfg").read_text("utf-8")
    bad = analyze(invalid, expected["mode"], "h3c")
    assert bad.config.source_lines == tuple(invalid.splitlines())
    assert expected["rule_id"] in {item.rule_id for item in bad.diagnostics}
    assert not any(item.rule_id.startswith("HUA-") for item in bad.diagnostics)
    good = analyze((case / "valid.cfg").read_text("utf-8"), expected["mode"], "h3c")
    assert rule_id not in {item.rule_id for item in good.diagnostics}
    assert bad.coverage["complete"] and good.coverage["complete"]


def test_every_h3c_rule_has_its_own_fixture_pair() -> None:
    assert set(CASES) == {rule.metadata.rule_id for rule in H3C_RULES}
    for case in CASES:
        assert {path.name for path in (ROOT / case).iterdir()} == {
            "valid.cfg",
            "invalid.cfg",
            "expected.json",
        }


def test_bgp_vpn_transport_does_not_inherit_public_peer_settings() -> None:
    source = (
        "ip vpn-instance BLUE\n#\nbgp 65000\n peer 192.0.2.2 as-number 65001\n"
        " ip vpn-instance BLUE\n  peer 192.0.2.2 description SYNTHETIC\n"
        "  address-family ipv4 unicast\n   peer 192.0.2.2 enable\n#\n"
    )
    result = analyze(source, "full", "h3c")
    assert any(item.rule_id == "H3C-BGP-005" for item in result.diagnostics)
    fixed = analyze(
        source.replace("  peer 192.0.2.2 description SYNTHETIC", "  peer 192.0.2.2 as-number 65002"),
        "full",
        "h3c",
    )
    assert not any(item.rule_id == "H3C-BGP-005" for item in fixed.diagnostics)
    assert fixed.config.bgp is not None
    assert fixed.config.bgp.vpn_scopes["BLUE"].peers["192.0.2.2"].remote_as == "65002"


def test_native_acl_policy_and_prefix_undo_preserve_effective_scope() -> None:
    source = (
        "acl number 3000\n rule 5 permit tcp destination-port eq 443\n#\n"
        "interface GigabitEthernet1/0/1\n packet-filter 3000 inbound\n"
        " undo packet-filter 3000 inbound\n qos apply policy ABSENT inbound\n"
        " undo qos apply policy inbound\n#\n"
        "route-policy EXPORT permit node 10\n if-match ip address prefix-list ABSENT\n"
        " undo if-match ip address prefix-list ABSENT\n#\n"
        "ip route-static 192.0.2.0 24 Bridge-Aggregation1\n"
    )
    result = analyze(source, "full", "h3c")
    assert not result.config.acl_references
    assert not result.config.interfaces["GigabitEthernet1/0/1"].traffic_policies
    assert not result.config.route_policies["EXPORT"].prefix_references
    assert not any(
        item.rule_id in {"H3C-POL-002", "H3C-RPOL-001", "H3C-ROUTE-001"} for item in result.diagnostics
    )


def test_vrp_forms_do_not_become_comware_facts() -> None:
    result = analyze(
        "interface Vlanif10\n traffic-policy ABSENT inbound\n#\n"
        "bgp 65000\n address-family ipv4 vpn-instance BLUE\n#\n"
        "authentication-mode INVALID\n",
        "full",
        "h3c",
    )
    assert "Vlanif10" not in result.config.interfaces
    assert result.config.bgp is not None and not result.config.bgp.address_families
    assert not result.coverage["semantic_complete"]
