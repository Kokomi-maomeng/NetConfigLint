# Huawei VRP validation notes

v1.1 Beta separates documented command facts from parser heuristics. The machine-readable
catalog is `netconfiglint/vendors/huawei/profiles/catalog.json`; every documented fact references
an official Huawei source record with URL, document ID, and access date. It stores only the
minimum structured facts needed by NetConfigLint, not copies of vendor documentation.

## Documented facts in the current catalog

- `display ip routing-table` is a supported source of local IPv4 RIB evidence.
- `display ipv6 routing-table` has both brief two-line and detailed field-oriented output forms.
- `display bgp peer` exposes operational peer state.
- `display ip interface brief` exposes physical/protocol interface state.
- BGP peer groups, IPv6 static routes, interface `ospf enable`, and ACL6-based traffic-policy
  constructs exist in the cited Huawei documentation.
- CloudEngine V200R024/V300R024 and S7700 V200R021 overlays are selected only when explicit
  platform/model/version evidence matches catalog patterns.

These facts do not prove that every syntax variant is available on every Huawei platform.

## Generic or heuristic behavior

- Huawei detection uses VRP banners and a bounded set of Huawei-style signatures.
- A model is reported only when an explicit model-shaped token is found; otherwise it is Unknown.
- VLAN ranges accept `N to M` within 1–4094; service-specific VLAN consumers are incomplete.
- Interface link-type checks cover clear access/trunk/hybrid conflicts only.
- Eth-Trunk references normalize the `Eth-Trunk<ID>` form.
- IPv4/IPv6 static-route parsing covers common destination/prefix plus next-hop forms. Advanced
  VPN/topology/BFD/track/preference/tag variants remain partially normalized.
- BGP configuration candidates use exact normalized static/connected prefixes. Snapshot mode
  becomes VERIFIED only when the matching address-family RIB section is present.
- Exact RIB means an exact prefix match, not proof of active forwarding, recursive reachability,
  route preference, or FIB programming.
- BGP peer state is definitive only for peers present in a supplied peer table. An absent row is
  not currently treated as a failed peer because filtered output may have been supplied.
- OSPF participation combines process network statements and interface `ospf enable` bindings;
  OSPFv3 and advanced inheritance are incomplete.
- ACL/ACL6 and traffic-policy parsing covers recognized definitions and selected consumers.
- “Unused” means unused by recognized consumers, not globally proven unused.
- Sensitive detection is keyword-based and never returns the matched secret text.

## Device/document validation still required

1. `port trunk allow-pass vlan`, hybrid/PVID, and `vlan batch` variants across named releases.
2. Eth-Trunk membership and naming across CloudEngine, S-series, and router families.
3. IPv4/IPv6 static-route outbound-interface, VPN/topology, BFD/track, preference, tag, and
   discard-route variants.
4. BGP peer/group inheritance order, address-family activation, route-policy application, and
   peer-state output variants across VRP V200/V300/V800.
5. BGP `network` mask defaults and the precise platform RIB eligibility rules.
6. Route-policy node, ACL/ip-prefix/IPv6-prefix matching, apply/continue, and all redistribution
   reference sites.
7. Interface/process OSPF association, OSPFv3, silent-interface, and process inheritance.
8. ACL named/numbered ranges, advanced ACL6 forms, traffic classifier match rules, policy
   precedence, and all policy application points.
9. VPN-instance address-family relationships, route-target consumers, and VPN-specific RIB output.
10. `display ipv6 routing-table` layouts on additional enterprise switches, especially wrapped
    interfaces and brief output with multiple next hops.
11. `display bgp peer` IPv6/group/VPN output columns and non-negotiated state spellings.
12. `display interface brief` versus `display ip interface brief` administrative-down variants.
13. Shortest-unique-prefix ambiguity against real command trees.
14. Profile overlay precedence and commands added/removed by service packs and patches.

Until evidence is added, compatibility diagnostics remain GENERIC, INFERRED, LOW, or UNKNOWN
instead of asserting an absolute platform error.
