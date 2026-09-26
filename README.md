# NetConfigLint v2.2

Project versions, local release files, rollback records, and the consolidated task entry are mapped in [PROJECT_INDEX.md](PROJECT_INDEX.md).

> A fast, offline, extensible static analyzer for network device configurations.

NetConfigLint is a local static-analysis tool for network engineers. It converts supported
configuration constructs into a normalized model, evaluates versioned rules, and returns
source-linked diagnostics to the CLI and QML desktop application through one shared API.

It is not a complete VRP emulator, network simulator, migration engine, or replacement for
vendor-supported validation and lab testing.

See the [v2.2 GUI acceptance notes](docs/v2.2-gui-acceptance.md), [v2.1 change scope](docs/v2.1-change-scope.md), [H3C coverage contract](docs/h3c-command-support.md),
and [v2.0 acceptance report](docs/v2.0-acceptance.md) for earlier release evidence.

## Desktop v2.2

The desktop puts its existing controls in one compact top bar, with a rounded workspace surface,
collapsible Settings sections, palette-tinted cards, and bundled Noto Sans SC text.
Roboto and Noto Sans SC ship as static Regular and SemiBold font files for consistent weight
selection across Qt platforms. Platform font rasterizers still differ.

- The top bar holds sidebar collapse, Open, Export, Mode, Vendor, Display, About, and window
  controls. Analyze stays inside Configuration. The sidebar header shows the app title.
- Settings opens from the bottom-left sidebar. Its sections fold independently; display mode uses
  preview cards and the ten named colors use swatches. Panel title, language, and local history
  remain configurable. History entries expand in the sidebar.
- Use Display to hide or restore Diagnostics and Temporary Editor; Configuration remains visible.
  Drag the dotted header grip to pick up a live
  image of the complete card, move it horizontally, and let Material motion settle it into its new
  position; keyboard arrow reordering remains available. Drag separators to resize cards. Hiding/reordering
  retains text and editor zoom; panel visibility/order and appearance persist between launches.
- Ctrl+mouse wheel zooms the active editor. Its localized context menu includes Restore default text
  size after zooming. Line-number gutters grow with the digit count. Ctrl+F and Ctrl+G act only in
  the focused editor. The scratch editor is never analyzed or included in exports/history.
- Empty input disables Analyze. Editing source or changing mode/vendor invalidates old diagnostics;
  results from an outdated background analysis are discarded. Status appears within Diagnostics.
- Export configuration plus diagnostics, configuration only, or diagnostics only as JSON, Markdown,
  or text. Full exports put complete source first by default. Diagnostics-first exports annotate code
  lines with severity counts. Confirmation opens a Qt Quick save dialog; Cancel/outside click aborts.
  Reports containing diagnostics require a current analysis and always include all severities.
- Imported H3C diagnostic bundles use a responsive read-only running-configuration preview and append
  source-mapped operational evidence excerpts after analysis. Configuration-only export selects the
  running configuration; Full export retains the complete bundle.
- Diagnostic prose follows the selected language; commands, source text, identifiers, addresses,
  and object names retain their original values. The OS detection field was removed from GUI,
  CLI output, vendor plugins, and the API model in v1.4.
- The custom title bar shares one surface and divider system with the navigation rail and workspace.
  The app/about/title-bar icon is an original scalable sakura-network mark, with generated 16–1024 px
  PNG variants plus Windows ICO and macOS ICNS packaging inputs.

## Supported scope

The Huawei VRP implementation includes:

- registry-driven vendor detection in the desktop interface;
- an auditable profile catalog whose facts link to official Huawei documents;
- VLAN, interface, Eth-Trunk, IPv4/IPv6 static route, BGP peer/group/network, OSPF,
  IS-IS, ACL/ACL6, route-policy, prefix-list, traffic-policy, VPN-instance, STP, and
  VXLAN/EVPN checks;
- a generic source-mapped block index that retains every non-empty configuration command for
  rule families that do not yet require a dedicated normalized object;
- operational snapshot parsing for IPv4/IPv6 RIB, BGP peer, and interface state;
- exact BGP network-to-RIB checks when the matching routing table is supplied;
- Snippet, Message, View, and Full analysis semantics;
- 50 Huawei rules with synthetic valid/invalid regression fixtures.

Unknown commands retain source mapping and do not make parsing fail. Unsupported vendors,
platforms, and releases remain Unknown rather than being guessed.

The v2.0 H3C Comware plugin adds conservative Comware 7 detection, original-text preservation,
common documented Comware-to-normalized command forms, 47 registered H3C rule evaluators, and a source-linked
`H3C-CMD-001` UNKNOWN for every unmodeled command line. It does not claim that one finite parser can
semantically emulate every H3C product/release command. It also recognizes bounded H3C diagnostic
bundles without treating operational output as configuration. See the exact
[H3C support matrix](docs/h3c-command-support.md).

## Privacy

All analysis runs locally. NetConfigLint has no cloud backend and does not upload configuration
text. Default logs do not contain the complete configuration. Sensitive-data diagnostics expose
only a rule, line, and generic warning, never the detected value.

Local history is enabled by default and stores configuration text and full diagnostics so a
past analysis can be reopened. This file can contain passwords and network details; keep the
portable folder private. Disable history in Settings to delete all stored entries. An unchanged
historical input reanalysis keeps the original entry; editing it creates a new entry.
In the Windows portable package, history is kept in `history/history.json` and the temporary
editor writes `temporary/editor.txt` beside the executable only when Save is clicked. Both may
contain sensitive text and should stay with a private backup of the portable folder.

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
See the [v2.0 validation and platform boundaries](docs/v2.0-acceptance.md).

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
providing the whole device configuration and any available operational output. Use **View**
for operational output without configuration, or **Message** for logs and command errors.

```console
netconfiglint check examples/huawei-basic.cfg
netconfiglint check config.txt --mode snippet --vendor auto --format text
netconfiglint check config.txt --mode full --vendor huawei --format json
netconfiglint check h3c.cfg --mode full --vendor h3c --format json
netconfiglint check log.txt --mode message --vendor h3c
netconfiglint check display.txt --mode view --vendor huawei
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
  Ctrl+F, Ctrl+G, incremental Huawei/H3C syntax highlighting, source-mapped unsupported-line
  highlighting, and selectable text;
- detected vendor/OS inside the diagnostic card, severity filters, expandable issues, and
  source-line navigation;
- a left-to-right analyzed configuration, diagnostics, and temporary-editor workspace with two
  mouse-draggable split areas;
- click-to-filter ERROR/WARNING/INFO/UNKNOWN severity chips that toggle back to the full result;
- default-enabled, source-restorable history beside the executable in portable mode, or in the
  operating system application-data location after installation; disabling clears saved entries;
- asynchronous analysis so large configuration input does not block the GUI thread.

### Screenshot

_Release screenshots are reserved for `docs/screenshots/`._

## Analysis modes

- **Snippet**: unresolved definitions become UNKNOWN because they may exist outside the input;
  unused-object rules are suppressed.
- **Message**: interprets recognized prompts, logs, and errors; possible causes are hypotheses.
- **View**: inspects supported route, peer, interface, LLDP, and H3C operational output without
  assuming configuration access.
- **Full**: treats the supplied configuration as a complete candidate for supported reference
  checks and combines recognized `display` output and log messages.
  The older CLI `snapshot` value remains accepted for existing scripts.

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

## Native packages and signing

The standalone build uses `pyside6-deploy`/Nuitka, then resolves the recursive PE import graph
from only the required PySide6/Shiboken roots. It prunes unused QML modules and Qt plug-ins before
checking the final dependency closure.

```powershell
.\scripts\build_windows.ps1
.\scripts\build_portable.ps1 -SkipAppBuild
.\scripts\build_msi.ps1 -SkipAppBuild
```

The portable command creates `release/NetConfigLint-2.2.0-windows-x64-portable.zip`. Extract the
single top-level folder and start `NetConfigLint.exe`; the Nuitka build uses the Windows GUI
subsystem and therefore does not open a console window.

The WiX MSI lets the user choose the base installation directory (the `NetConfigLint` child is
appended automatically), Start-menu shortcuts, and a desktop shortcut. Its Start menu exposes
separate uninstall entries for keeping history or deleting all current-user data.

Unsigned installers are named `*-unsigned.msi` or `*-unsigned.pkg`. A trusted signed build requires a valid code
signing certificate with private key and Windows SDK SignTool:

```powershell
.\scripts\build_msi.ps1 -CertificateThumbprint '<certificate-thumbprint>' -SkipAppBuild
```

The script signs the contained executable before MSI assembly and then signs the MSI with SHA-256,
uses an RFC 3161 timestamp, and fails
the build unless Authenticode validation succeeds. See [Windows signing](docs/windows-signing.md).

On Linux, run `python scripts/build_desktop.py` followed by `python scripts/build_linux_deb.py`;
the package includes `netconfiglint-gui` and an interactive `netconfiglint-uninstall` keep/delete
helper. On macOS, run `python scripts/build_desktop.py` and `python scripts/build_macos_pkg.py`;
Developer ID signing and notarization activate only when the documented protected identities exist.

## Dependencies and licenses

NetConfigLint is Apache-2.0 licensed.

| Dependency | Scope | License information | Purpose |
|---|---|---|---|
| PySide6 / Qt for Python | Optional GUI/runtime | LGPLv3, GPLv3, or Qt commercial | Official Qt 6 Python/QML bindings |
| Nuitka 4.2 | Compiler and generated runtime | AGPLv3 + Runtime Library Exception 1.0 | Complete texts and exception are included; independent compiled modules retain their own terms |
| pefile | Build only | MIT | Verifiable recursive Windows PE import resolution |
| WiX Toolset 3 | Build machine | Microsoft Reciprocal License | Windows MSI generation |
| pytest, Ruff, mypy | Development only | MIT | Test, lint, and type validation |

Original project SVG assets are Apache-2.0. No vendor firmware, private software, documentation
copies, credentials, or production configurations are included. Redistributors must satisfy the
licenses of their selected Python/Qt distribution and packaging toolchain.
Every Windows standalone/portable release assembles full license material and an actual-file
`SBOM.json`; the final ZIP is verified after compression. Missing/changed legal
material or unknown native components fail the gate. See [notices and source/library
replacement instructions](THIRD_PARTY_NOTICES.md).

## Known limitations

- The parsers and rules are bounded static analyzers, not complete VRP/Comware command-line emulators.
  All configuration blocks retain source mapping, but not every Huawei or H3C feature has a semantic
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
- **v2.0**: H3C Comware plugin, live card dragging, integrated title/navigation surface, animation
  unification, original sakura icon, MSI/DEB/PKG packaging, and explicit keep/delete uninstall paths.
- **v2.1**: four visible analysis modes, source-restorable history, IRF peer-port check, LLDP view
  evidence, combined config/display input, revised toolbar and portable state paths.
- **v2.2 local build**: repaired window geometry persistence, integrated menu and workspace,
  collapsible Settings, palette-tinted cards, unified text rendering, and a Windows portable ZIP.
- **Future**: Juniper Junos plugin, VS Code integration, configuration diff,
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
