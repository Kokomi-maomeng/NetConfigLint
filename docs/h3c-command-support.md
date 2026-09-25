# H3C Comware command support contract

NetConfigLint v2.1 preserves every non-empty H3C configuration line and never rejects a file merely
because it contains an unknown command. This is complete **content retention**, not a claim that a
finite static analyzer can emulate every command across every H3C model, card, license, and Comware
release.

The current evidence baseline is the official H3C S6805/S9850 Comware 7 Release 6715 command-reference
set. A detected device is assigned the generic `h3c-comware7-generic` profile unless model/release
evidence supports a narrower future profile.

## Directly normalized Comware forms

- `port trunk permit vlan`, hybrid tagged/untagged VLAN forms, and `packet-filter` bindings;
- `port link-aggregation group` with `Bridge-Aggregation` definitions;
- `port access vlan`, interface bridge/route mode, source ARP filtering, `Vlan-interface`,
  interface IPv4/IPv6, VPN, STP, and interface OSPF bindings/network type;
- IPv4/IPv6 static routes, BGP peers/groups/address families, OSPF, IS-IS, ACL/ACL6;
- route-policy/prefix-list, traffic classifier/behavior/policy, VPN instance, VXLAN/EVPN;
- Telnet/FTP/SSH service settings, VTY protocols/authentication, read/write SNMP community risk,
  NTP authentication, legacy SSL/TLS enablement, plaintext passwords, local-user Telnet scope,
  broad OSPF adjacency exposure, and OSPF authentication evidence.
- H3C diagnostic bundles with source-mapped running/saved configuration comparison, cards, fans,
  power, temperature, link aggregation, M-LAG/DRCP, OSPF neighbors, IPv4 route counts, LLDP,
  transceiver alarms, and log-buffer overwrite evidence.
- Common IRF member/port/binding commands, session `sys`/`system-view` input, and Chinese annotation
  lines. A two-member input using the same IRF port index on both members produces an inferred
  topology warning. Actual cable endpoints must be verified using `display irf link`.
- LLDP list rows can produce source-linked observed neighbor edges when the documented columns
  are present. Column order varies by release; unsupported layouts remain unverified.

The plugin exposes 47 registered `H3C-*` rule evaluators. Shared normalized checks are wrapped with H3C-only
IDs and wording; H3C analysis never emits a `HUA-*` rule ID.

## Explicit unsupported-command behavior

For each line without a registered semantic parser, `H3C-CMD-001` records the original line number
and an UNKNOWN result. `H3C-CMD-002` summarizes those lines. `coverage.complete` means input
processing finished; `coverage.semantic_complete` is false whenever unmodeled lines remain.
Hardware/release-dependent `system-working-mode`, `xbar`, `ftth`, and `onu` commands instead use
`H3C-PLATFORM-001` when exact target evidence is absent. This is intentional: a filename is not
accepted as device identity or feature-license proof.

Large collection files are decoded as strict UTF-8 or GB18030. If neither decoder can consume every
byte, undecodable bytes are retained as visible `⟦XX⟧` markers and the GUI/CLI warns the user.
CRLF, LF, and bare-CR input is normalized consistently. For a diagnostic bundle, coverage applies
only to the selected `display current-configuration` section; operational output stays available for
snapshot rules without becoming thousands of fake unsupported configuration commands.
The desktop shows a bounded, read-only running-configuration preview and appends source-mapped
evidence excerpts for operational diagnostics. “Configuration only” exports the selected running
configuration; “Full” retains the complete imported diagnostic bundle.

Acceptance requires exact source preservation, deterministic detection, no Huawei/H3C cross-detection,
supported-command valid/invalid fixtures, and source-linked UNKNOWN output for all unmodeled lines.
Hardware behavior, hidden defaults, feature licensing, and release-specific syntax still require the
matching H3C reference and lab/device validation.

IRF numbering and peer-port restrictions follow the official
[H3C IRF configuration guide](https://www.h3c.com/en/d_201906/1192536_294551_0.htm).
The parsed LLDP list columns follow the official
[H3C LLDP command reference](https://www.h3c.com/en/d_202603/2792651_294551_0.htm).
