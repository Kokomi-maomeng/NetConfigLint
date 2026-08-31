# Huawei VRP validation notes

v1.0 Beta intentionally uses a bounded, generic interpretation of Huawei-style configuration.
The following items require future validation using licensed official documentation and, where
appropriate, a lab device for each supported platform/version profile.

## Heuristic or generic behavior

- Huawei detection uses VRP banners and a small set of Huawei-style configuration signatures.
- `CloudEngine` is emitted only when explicit CloudEngine/CE-family text exists; model remains
  Unknown.
- VLAN ranges accept `N to M` for 1–4094; advanced keywords and service references are not parsed.
- Interface link-type checks cover clear access/trunk/hybrid conflicts only.
- An Eth-Trunk reference is resolved by normalized `Eth-Trunk<ID>` naming.
- Static-route parsing covers common IPv4 destination/mask/prefix plus next-hop forms. Interface-
  only, preference, tag, description, BFD, track, and advanced VPN forms need expansion.
- Next-hop warnings are limited to unspecified, multicast, or loopback address classes. Interface
  names and special keywords are left unjudged.
- BGP network evidence is inferred from exact normalized static or connected candidate networks;
  this is not a real RIB check.
- OSPF participation is inferred by matching interface IPv4 addresses to area network/wildcard
  statements. Interface-mode activation and advanced OSPF features are not modeled.
- ACL parsing recognizes common `acl`, `acl number`, and `acl name` definitions plus a bounded set
  of traffic-filter/route-policy references.
- “Unused VLAN/route-policy” means unused by supported normalized consumers, not proven globally
  unused.
- Sensitive detection is keyword-based and deliberately returns only a count and first line.

## Commands/behavior needing device or official-document validation

1. Exact `port trunk allow-pass vlan` and `vlan batch` variants across VRP and CloudEngine releases.
2. Hybrid-port VLAN semantics and interaction with default/PVID commands.
3. Eth-Trunk membership command availability and naming across device families.
4. Static-route grammar for outbound-interface, VPN, IPv6, BFD/track, preference, and special
   discard next hops.
5. BGP peer route-policy syntax inside each address-family and group inheritance behavior.
6. BGP `network` mask defaults, VPN address-family forms, and per-release RIB eligibility rules.
7. Route-policy node, `if-match ip-prefix`/ACL, and apply/continue semantics.
8. OSPF area/network syntax, interface-mode activation, silent-interface, and process inheritance.
9. ACL named/numbered ranges, advanced ACL variants, and all feature reference sites.
10. VPN-instance definitions and BGP VPN address-family relationships across VRP versions.
11. Shortest-unique-prefix behavior and ambiguity for real command trees.
12. Platform/model/version overlay precedence and commands removed or added by release.

Until validated evidence is added to a profile, compatibility findings must remain GENERIC,
INFERRED, LOW, or UNKNOWN rather than presenting an absolute platform error.

