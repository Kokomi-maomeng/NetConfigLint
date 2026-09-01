# v1.2 implementation status

## Stable architecture

- `analyze(source, mode, vendor) -> AnalysisResult` remains the shared CLI/GUI/API boundary.
- Vendor-neutral source ranges, normalized configuration objects, diagnostics, modes, and
  operational evidence remain isolated from Huawei-specific parsing and rules.
- Every non-empty Huawei configuration block is retained with line provenance; supported
  constructs additionally populate typed models.
- QML-first PySide6 GUI, package-relative resources, bilingual shell, opt-in private history,
  and synthetic-only test fixtures remain enforced.

## v1.2 delivered scope

- 50 mode-aware Huawei rules with paired valid/invalid/expected synthetic fixtures.
- Added hybrid/PVID/VLANIF, IPv4, static-route VPN, BGP remote-AS, IS-IS, ACL, redistribution,
  VXLAN/EVPN, STP, SSH/Telnet/FTP/SNMP/NTP, plaintext-password, and VTY checks.
- Privacy-safe aggregate validation against 40 locally supplied production-derived Huawei
  configuration exports: all parsed, all returned multiple diagnostics, and no configuration
  text, entry names, addresses, or diagnostic prose was emitted by the validator.
- Material card-based configuration workspace, custom mode/vendor choice cards, analyzed and
  temporary editors, syntax highlighting in both, selectable diagnostic/about/history text,
  adaptive history empty state, and animated navigation/dialogs.
- Rule-library page and device platform/model/version/profile/confidence display removed.
- Windows standalone build uses the GUI subsystem, creates a no-console portable ZIP, and stores
  optional history beside the executable in a dedicated directory.
- Source/QML tests run on Windows, Linux, and macOS in GitHub Actions.

## Conservative boundaries

- This is a broad static analyzer, not a VRP emulator or a proof that a configuration will work
  on a particular chassis, release, patch, or live topology.
- Advanced command variants without enough evidence remain retained but unasserted.
- Operational snapshot parsing covers supported RIB, BGP-peer, and interface layouts only.
- Exact forwarding, recursive resolution, full BGP inheritance, full QoS consumer graphs,
  OSPFv3, advanced EVPN, and all platform-specific feature availability remain incomplete.
- Windows binaries are unsigned unless an external Authenticode certificate is supplied; the
  portable ZIP includes a hash but Windows may still show an unrecognized-publisher warning.

See [Huawei validation notes](huawei-validation.md), [Huawei source map](huawei-rule-sources.md),
and the [roadmap](roadmap.md).
