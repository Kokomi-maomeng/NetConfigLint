# Huawei rule source map

NetConfigLint stores only URLs and small structured command facts. It does not redistribute
Huawei manuals. Sources were accessed on 2026-09-01 unless a machine-readable catalog entry says
otherwise.

| Coverage | Primary Huawei source |
|---|---|
| VLAN hybrid/PVID command forms | [port hybrid pvid vlan](https://support.huawei.com/enterprise/zh/doc/EDOC1100064377/1327376) |
| Bridge-domain, VXLAN and VNI commands | [VXLAN Configuration Commands](https://support.huawei.com/enterprise/en/doc/EDOC1100459384/10e85233/vxlan-configuration-commands) |
| IPv4 VPN static routes | [ip route-static vpn-instance](https://info.support.huawei.com/hedex/api/pages/EDOC1100331435/AEM10132/04/resources/dc/ip_route-static_vpn-instance.html) |
| IS-IS process, interface enable and NET | [IS-IS Configuration Commands](https://info.support.huawei.com/enterprise/en/doc/EDOC1100381010/4e0b2b50/is-is-configuration-commands) |
| STP edge-port protection | [STP/RSTP/MSTP Configuration](https://support.huawei.com/enterprise/en/doc/EDOC1100466171/c9a6630d/stp-rstp-mstp-configuration) |
| SSH server parameters | [SSH server configuration](https://support.huawei.com/enterprise/en/doc/EDOC1100290937/379d8aea/configuring-the-ssh-server-function-and-related-parameters) |
| SSH-only VTY example | [STelnet local authentication example](https://info.support.huawei.com/enterprise/en/doc/EDOC1100411465/4bda9dd6/example-for-configuring-stelnet-login-for-ipv4-users-local-authentication) |
| SNMPv3 USM | [SNMPv3 communication](https://support.huawei.com/enterprise/en/doc/EDOC1100468733/f596198f/configuring-a-device-to-communicate-with-an-nms-through-snmpv3-usm-user) |
| NTP authentication/access control | [NTP access control](https://support.huawei.com/enterprise/en/doc/EDOC1100380861/75f06349/fundamentals-of-ntp-access-control) |
| ACL configuration | [Configuring an ACL](https://info.support.huawei.com/enterprise/en/doc/EDOC1100411634/3b8682c3/configuring-an-acl) |
| FTP security risk | [Feature-package transfer guidance](https://support.huawei.com/enterprise/en/doc/EDOC1100262564/1bf40fcc/uploading-or-downloading-a-feature-package-to-a-device) |

Earlier routing-table, BGP, interface, IPv6, OSPF, ACL6/traffic-policy, and platform catalog
sources remain in `netconfiglint/vendors/huawei/profiles/catalog.json`. Product support varies by
device family and software release; source linkage therefore proves a command family exists, not
universal availability.
