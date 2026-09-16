# H3C Comware command support contract

NetConfigLint v2.0 preserves every non-empty H3C configuration line and never rejects a file merely
because it contains an unknown command. This is complete **content retention**, not a claim that a
finite static analyzer can emulate every command across every H3C model, card, license, and Comware
release.

The current evidence baseline is the official H3C S6805/S9850 Comware 7 Release 6715 command-reference
set. A detected device is assigned the generic `h3c-comware7-generic` profile unless model/release
evidence supports a narrower future profile.

## Directly normalized Comware forms

- `port trunk permit vlan`, hybrid tagged/untagged VLAN forms, and `packet-filter` bindings;
- `port link-aggregation group` with `Bridge-Aggregation` definitions;
- `Vlan-interface`, interface IPv4/IPv6, VPN, STP, and interface OSPF bindings;
- IPv4/IPv6 static routes, BGP peers/groups/address families, OSPF, IS-IS, ACL/ACL6;
- route-policy/prefix-list, traffic classifier/behavior/policy, VPN instance, VXLAN/EVPN;
- Telnet/FTP/SSH service settings, VTY protocols/authentication, SNMP community, NTP authentication,
  plaintext passwords, and local-user Telnet service scope.

The plugin exposes 43 registered `H3C-*` rules. Shared normalized checks are wrapped with H3C-only
IDs and wording; H3C analysis never emits a `HUA-*` rule ID.

## Explicit unsupported-command behavior

For each line without a registered semantic parser, `H3C-CMD-001` records the original line number
and an UNKNOWN result. `H3C-CMD-002` summarizes those lines. `coverage.complete` means input
processing finished; `coverage.semantic_complete` is false whenever unmodeled lines remain.

Acceptance requires exact source preservation, deterministic detection, no Huawei/H3C cross-detection,
supported-command valid/invalid fixtures, and source-linked UNKNOWN output for all unmodeled lines.
Hardware behavior, hidden defaults, feature licensing, and release-specific syntax still require the
matching H3C reference and lab/device validation.
