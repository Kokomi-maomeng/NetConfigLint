# NetConfigLint v1.5

> A fast, offline, extensible static analyzer for network device configurations.

NetConfigLint is a local static-analysis tool for network engineers. It converts supported
configuration constructs into a normalized model, evaluates versioned rules, and returns
source-linked diagnostics to the CLI and QML desktop application through one shared API.

It is not a complete VRP emulator, network simulator, migration engine, or replacement for
vendor-supported validation and lab testing.

See the [v1.5 audit repair report](docs/v1.5-audit-repairs.md) for all 26 findings,
fixes and retained validation evidence.

## Desktop v1.5

The desktop adopts the Material 3 typography, palettes, rounded navigation, cards, and motion
of [Material-Design-CastoriceUI](https://github.com/Kokomi-maomeng/Material-Design-CastoriceUI).
Roboto and Noto Sans SC are bundled for offline use. Platform font rasterizers still differ.

- Open and Export sit together; Mode and Vendor show their current values; Analyze is on the right.
- Settings opens from the bottom-left sidebar. Customize the panel title, language, system/light/dark
  appearance, and ten theme colors. About remains a separate page with link cards.
- Use View to hide or restore each workspace card. Drag the dotted header grip to reorder the three
  cards, or focus the grip and use arrow keys. Drag separators to resize cards. Hiding/reordering
  retains text and editor zoom; panel visibility/order and appearance persist between launches.
- Ctrl+mouse wheel zooms the active editor. Its localized context menu includes Restore default text
  size after zooming. Line-number gutters grow with the digit count. Ctrl+F and Ctrl+G act only in
  the focused editor. The scratch editor is never analyzed or included in exports/history.
- Empty input disables Analyze. Editing source or changing mode/vendor invalidates old diagnostics;
  results from an outdated background analysis are discarded. Status appears within Diagnostics.
- Export configuration plus diagnostics, configuration only, or diagnostics only as JSON, Markdown,
  or text. Full exports put complete source first by default. Diagnostics-first exports annotate code
  lines with severity counts. Confirmation opens the native save flow; Cancel/outside click aborts.
  Reports containing diagnostics require a current analysis and always include all severities.
- Diagnostic prose follows the selected language; commands, source text, identifiers, addresses,
  and object names retain their original values. The OS detection field was removed from GUI,
  CLI output, vendor plugins, and the API model in v1.4.

## Supported scope

The v1.5 Huawei VRP implementation includes:

- registry-driven vendor detection in the desktop interface;
- an auditable profile catalog whose facts link to official Huawei documents;
- VLAN, interface, Eth-Trunk, IPv4/IPv6 static route, BGP peer/group/network, OSPF,
  IS-IS, ACL/ACL6, route-policy, prefix-list, traffic-policy, VPN-instance, STP, and
  VXLAN/EVPN checks;
- a generic source-mapped block index that retains every non-empty configuration command for
  rule families that do not yet require a dedicated normalized object;
- operational snapshot parsing for IPv4/IPv6 RIB, BGP peer, and interface state;
- exact BGP network-to-RIB checks when the matching routing table is supplied;
- Snippet, Full Configuration, and Snapshot analysis semantics;
- 50 Huawei rules with synthetic valid/invalid regression fixtures.

Unknown commands retain source mapping and do not make parsing fail. Unsupported vendors,
platforms, and releases remain Unknown rather than being guessed.

## Privacy

All analysis runs locally. NetConfigLint has no cloud backend and does not upload configuration
text. Default logs do not contain the complete configuration. Sensitive-data diagnostics expose
only a rule, line, and generic warning, never the detected value.

Local history is optional and disabled by default. When enabled it stores only time, mode,
detected vendor, source line count, diagnostic counts, and Rule IDs. It does not store
configuration text, filenames, object names, or network addresses.

Explicit configuration/full exports contain the requested source text. Diagnostic reports can
also disclose network design; review exported files before sharing.

## Install from source

Requirements: Python 3.12–3.13; PySide6 >=6.9,<6.12 is optional for CLI-only use.
The release toolchain is pinned in `constraints/release.txt` (Python 3.13.2,
Qt/PySide6 6.11.2, Nuitka 4.2). `scripts/check_build_environment.py` rejects drift.
The quality matrix covers Python 3.12.10/3.13.2 across Windows/Linux/macOS and
3.12.14 on Linux, with Qt 6.9.0/6.11.2. GitHub's 3.12.14 manifest contains no
Windows/macOS artifacts. Native platform support is qualified only after the
actual compiled desktop smoke gates pass; authored CI is not a passed test.
See the [final v1.5 validation and platform boundaries](docs/v1.5-acceptance.md).

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e '.[dev,gui]'
```

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev,gui]'
```

## CLI

The desktop, CLI, and Python API default to **Snippet** mode. Paste part of a configuration
to check it without treating omitted settings as confirmed missing. Select **Full** when
providing the whole device configuration, or **Snapshot** when also providing supported
route, peer, or interface command output.

```console
netconfiglint check examples/huawei-basic.cfg
netconfiglint check config.txt --mode snippet --vendor auto --format text
netconfiglint check config.txt --mode full --vendor huawei --format json
netconfiglint check snapshot.txt --mode snapshot
```

Exit code `0` means no ERROR diagnostic, `1` means at least one ERROR, and `2` means an
input, usage, or vendor-detection failure. Text output uses terminal colors; JSON uses the same
diagnostic model consumed by the GUI.

## Desktop GUI

```console
netconfiglint-gui
```

The QML-first PySide6 desktop application provides:

- Material Design card layout, animated interactions and dialogs, custom scrollbars,
  Light/Dark/System themes, and high-DPI support;
- English and Simplified Chinese UI, selected from the system locale on first run;
- unsupported system languages falling back to English and instant manual language switching;
- file open, paste/edit, drag/drop, analyze, clear, and JSON export;
- separate analyzed configuration and non-analyzed temporary editors, both with line numbers,
  Ctrl+F, Ctrl+G, incremental Huawei syntax highlighting, and selectable text;
- detected vendor/OS inside the diagnostic card, severity filters, expandable issues, and
  source-line navigation;
- a left-to-right analyzed configuration, diagnostics, and temporary-editor workspace with two
  visible mouse-draggable split handles;
- click-to-filter ERROR/WARNING/INFO/UNKNOWN severity chips that toggle back to the full result;
- optional privacy-minimized local history stored in a dedicated `history` directory beside the
  portable executable, with an explicit clear action;
- asynchronous analysis so large configuration input does not block the GUI thread.

### Screenshot

_Release screenshots are reserved for `docs/screenshots/`._

## Analysis modes

- **Snippet**: unresolved definitions become UNKNOWN because they may exist outside the input;
  unused-object rules are suppressed.
- **Full**: input is treated as a complete candidate configuration, enabling definitive
  normalized reference checks.
- **Snapshot**: configuration plus recognized `display` output can prove RIB presence, peer
  state, and interface state. Missing operational sections remain unknown rather than failing.

## Rule catalog

| Rule ID | Default | Purpose |
|---|---:|---|
| `HUA-VLAN-001` | ERROR | Trunk VLAN referenced but not defined |
| `HUA-VLAN-002` | ERROR | Access VLAN referenced but not defined |
| `HUA-VLAN-003` | INFO | Defined VLAN has no supported reference |
| `HUA-VLAN-004` | ERROR | Hybrid tagged/untagged VLAN referenced but not defined |
| `HUA-VLAN-005` | ERROR | Interface PVID VLAN referenced but not defined |
| `HUA-IF-001` | WARNING | Shutdown interface contains apparent business configuration |
| `HUA-IF-002` | ERROR | VLAN command conflicts with interface link type |
| `HUA-IF-003` | ERROR | Eth-Trunk member references an undefined Eth-Trunk |
| `HUA-IF-004` | WARNING | Snapshot reports a business-configured interface down |
| `HUA-IF-005` | ERROR | Interface IPv4 address cannot be normalized |
| `HUA-IF-006` | ERROR | VLANIF references a VLAN that is not defined |
| `HUA-ROUTE-001` | ERROR | IPv4 static route cannot be normalized |
| `HUA-ROUTE-002` | WARNING | IPv4 static route has an unusual next-hop class |
| `HUA-ROUTE-003` | ERROR | Static route references an undefined VPN instance |
| `HUA-IPV6-001` | ERROR | IPv6 static route cannot be normalized |
| `HUA-IPV6-002` | ERROR | Interface IPv6 address cannot be normalized |
| `HUA-BGP-001` | ERROR | BGP peer/group references an undefined route-policy |
| `HUA-BGP-002` | WARNING | BGP network is not proven by configuration or supplied RIB |
| `HUA-BGP-003` | ERROR | Snapshot reports a configured BGP peer not Established |
| `HUA-BGP-004` | ERROR | BGP peer references an undefined group |
| `HUA-BGP-005` | ERROR | BGP peer/group has no remote AS |
| `HUA-ISIS-001` | ERROR | Interface references an undefined IS-IS process |
| `HUA-ISIS-002` | ERROR | IS-IS process has no network entity |
| `HUA-RPOL-001` | ERROR | Route-policy references an undefined prefix-list |
| `HUA-RPOL-002` | INFO | Route-policy has no supported consumer reference |
| `HUA-RPOL-003` | ERROR | Redistribution references an undefined route-policy |
| `HUA-OSPF-001` | ERROR | OSPF network lacks a valid area association |
| `HUA-OSPF-002` | WARNING | No interface can be shown to participate in OSPF |
| `HUA-OSPF-003` | ERROR | Interface OSPF binding references an undefined process |
| `HUA-ACL-001` | ERROR | ACL/ACL6 is referenced but not defined |
| `HUA-ACL-002` | WARNING | ACL broadly permits any source to any destination |
| `HUA-ACL-003` | WARNING | Referenced ACL contains no rules |
| `HUA-POL-001` | ERROR | Traffic policy references an undefined classifier/behavior |
| `HUA-POL-002` | ERROR | Interface applies an undefined traffic policy |
| `HUA-VPN-001` | ERROR | Interface references an undefined VPN instance |
| `HUA-VPN-002` | ERROR | BGP VPN address-family references an undefined VPN instance |
| `HUA-EVPN-001` | ERROR | VXLAN VNI is outside its valid range |
| `HUA-EVPN-002` | ERROR | Bridge-domain references an undefined EVPN VNI |
| `HUA-EVPN-003` | ERROR | VNI is bound to multiple bridge-domains |
| `HUA-STP-001` | WARNING | Edge port is configured without BPDU protection |
| `HUA-SEC-001` | INFO | Potentially sensitive configuration keywords detected |
| `HUA-SEC-002` | WARNING | Telnet server is enabled |
| `HUA-SEC-003` | WARNING | FTP server is enabled |
| `HUA-SEC-004` | ERROR | Plaintext password command is present |
| `HUA-SEC-005` | WARNING | Legacy SNMP community is configured |
| `HUA-SEC-006` | WARNING | NTP peer/server lacks authentication |
| `HUA-SEC-007` | WARNING | SSH listens on all interfaces |
| `HUA-SEC-008` | WARNING | Local user permits Telnet |
| `HUA-SEC-009` | WARNING | VTY permits Telnet or all protocols |
| `HUA-SEC-010` | WARNING | VTY uses password authentication instead of AAA |

Severity and confidence are independent. Confidence is VERIFIED, DOCUMENTED, INFERRED,
GENERIC, or LOW. Rule severity can change with the analysis mode and available evidence.

## Public API

```python
from netconfiglint import analyze

result = analyze(source, mode="full", vendor="auto")
for diagnostic in result.diagnostics:
    print(diagnostic.rule_id, diagnostic.source.line, diagnostic.message)
```

CLI and GUI use this same entry point. See [architecture](docs/architecture.md).

## Development, tests, and benchmark

```powershell
.venv\Scripts\python.exe -m pytest
.venv\Scripts\ruff.exe format --check netconfiglint tests benchmarks scripts
.venv\Scripts\ruff.exe check netconfiglint tests benchmarks scripts
.venv\Scripts\mypy.exe netconfiglint
.venv\Scripts\python.exe benchmarks\benchmark_large_config.py
```

The benchmark is synthetic and contains no production data. It measures parser/analyzer
throughput, not device behavior. Headless GUI tests use the Qt offscreen platform.

## Windows packaging and signing

The standalone build uses `pyside6-deploy`/Nuitka, then resolves the recursive PE import graph
from only the required PySide6/Shiboken roots. It prunes unused QML modules and Qt plug-ins before
checking the final dependency closure.

```powershell
.\scripts\build_windows.ps1
.\scripts\build_portable.ps1 -SkipAppBuild
.\scripts\build_installer.ps1 -SkipAppBuild
```

The portable command creates `release/NetConfigLint-1.5.0-windows-x64-portable.zip`. Extract the
single top-level folder and start `NetConfigLint.exe`; the Nuitka build uses the Windows GUI
subsystem and therefore does not open a console window.

Unsigned builds are named `*-setup-unsigned.exe`. A trusted signed build requires a valid code
signing certificate with private key and Windows SDK SignTool:

```powershell
.\scripts\build_installer.ps1 -CertificateThumbprint '<certificate-thumbprint>'
```

The script signs the installer and uninstaller with SHA-256, uses an RFC 3161 timestamp, and fails
the build unless Authenticode validation succeeds. See [Windows signing](docs/windows-signing.md).

## Dependencies and licenses

NetConfigLint is Apache-2.0 licensed.

| Dependency | Scope | License information | Purpose |
|---|---|---|---|
| PySide6 / Qt for Python | Optional GUI/runtime | LGPLv3, GPLv3, or Qt commercial | Official Qt 6 Python/QML bindings |
| Nuitka 4.2 | Compiler and generated runtime | AGPLv3 + Runtime Library Exception 1.0 | Complete texts and exception are included; independent compiled modules retain their own terms |
| pefile | Build only | MIT | Verifiable recursive Windows PE import resolution |
| Inno Setup | Build machine | Modified BSD-style | Windows installer generation |
| pytest, Ruff, mypy | Development only | MIT | Test, lint, and type validation |

Original project SVG assets are Apache-2.0. No vendor firmware, private software, documentation
copies, credentials, or production configurations are included. Redistributors must satisfy the
licenses of their selected Python/Qt distribution and packaging toolchain.
Every Windows standalone/portable release assembles full license material and an actual-file
`SBOM.json`; the final ZIP is verified after compression. Missing/changed legal
material or unknown native components fail the gate. See [notices and source/library
replacement instructions](THIRD_PARTY_NOTICES.md).

## Known limitations

- The parser and rules are a bounded static analyzer, not a complete VRP command-line emulator.
  All configuration blocks retain source mapping, but not every Huawei feature has a semantic
  rule; unknown facts remain unasserted instead of being guessed.
- Profile matches require explicit model/version evidence; generic VRP stays generic.
- Profile facts prove only cited command forms, not every model/version combination.
- Snapshot parsing covers recognized table/detail layouts and is not a general screen-scraper.
- Exact RIB checks compare route prefixes; route preference, active/invalid state, recursive
  resolution, and forwarding hardware are not fully modeled.
- BGP group inheritance, advanced EVPN, ACL/QoS/policy consumers, IPv6, OSPF/OSPFv3, and
  multi-process IS-IS semantics remain partial.
- “Unused” means no consumer recognized by this parser; an unsupported feature may reference it.
- English and Simplified Chinese diagnostic prose are available; unsupported vendor semantics remain explicit.
- Release binaries are unsigned unless a valid external code-signing identity is supplied.

See [Huawei validation notes](docs/huawei-validation.md), [status](docs/status.md), and the
[executable roadmap](docs/roadmap.md).

## Roadmap

- **v1.3**: three-column draggable workspace, severity-chip filtering, repaired editors and
  dialogs, unified larger typography, portable history, and no-console Windows ZIP.
- **v1.4**: Material desktop, appearance settings, and the export workflow.
- **v1.5**: all 26 audit findings repaired, Huawei correctness fixes, default Snippet mode,
  and qualified desktop builds with a Windows portable release.
- **Future**: H3C Comware and Juniper Junos plugins, VS Code integration, configuration diff,
  topology/dependency graph, Batfish
  integration, CI validation, and migration assistance.

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md). Every rule requires a unique Rule ID, valid and invalid
synthetic fixtures, expected diagnostics, conservative confidence, and documentation. Do not
commit real enterprise configurations or personal/sensitive data.

## Disclaimer

NetConfigLint performs static analysis and cannot guarantee that a configuration will operate
correctly on physical hardware.

Always validate production network changes using vendor-supported procedures and appropriate lab
or staging environments.


For a synthetic-only GUI and export smoke run (also supported by the portable executable):

```powershell
.\NetConfigLint.exe --smoke-test .\acceptance-output
```

This opt-in check uses isolated settings, disables history, writes synthetic reports/screenshots,
and exits with a machine-readable `smoke-result.json`. It does not read user configuration.
