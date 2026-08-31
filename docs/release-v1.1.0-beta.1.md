# NetConfigLint v1.1.0 Beta 1

This release adds:

- auditable Huawei profile/version facts backed by official-source records;
- IPv4/IPv6 RIB, BGP peer, and interface operational snapshot parsing;
- exact BGP network-to-RIB checks when matching evidence is supplied;
- IPv6, BGP group, interface OSPF, ACL6, and traffic-policy coverage;
- eight new rules for a total of 26;
- English/Simplified Chinese GUI shell with system-language selection and English fallback;
- incremental syntax highlighting and optional privacy-minimized local history;
- a synthetic large-configuration benchmark and performance regression test;
- recursive PE dependency closure and an Inno Setup installer/signing workflow.

Rule-generated diagnostic prose remains English. An installer whose filename ends in
`-unsigned.exe` has no trusted Authenticode signature and is published only for transparent beta
testing. A certificate-backed artifact is produced only when the build validates the signature.
