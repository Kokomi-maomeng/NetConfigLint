# NetConfigLint v1.0 Beta

> A fast, offline, extensible static analyzer for network device configurations.

NetConfigLint is a local static-analysis tool for network engineers. It parses supported
configuration constructs into a normalized model, evaluates versioned rules, and returns
source-linked diagnostics to the CLI and a QML desktop application through one shared API.

NetConfigLint is **not** a complete VRP emulator, network simulator, configuration migration
engine, or replacement for vendor validation and lab testing.

## Status and supported scope

v1.0 Beta currently supports a conservative subset of Huawei Enterprise/CloudEngine-style
VRP configuration:

- vendor/OS/platform-family detection without guessing a model;
- VLANs, interfaces, Eth-Trunk membership, IPv4 static routes;
- BGP peers, policies, IPv4 network statements and VPN address-families;
- OSPF area/network associations;
- ACL, route-policy, ip-prefix and VPN-instance references;
- sensitive-keyword detection without returning the sensitive value;
- snippet, full configuration, and snapshot-framework analysis modes.

Unknown commands are retained in source mapping and do not make parsing fail. H3C, Juniper,
Cisco, complete command compatibility, and runtime routing validation are not yet supported.

## Privacy and security

All analysis runs locally. NetConfigLint has no cloud backend and does not upload source text.
Default logs must not contain the complete configuration. Diagnostics may contain object names
and line numbers, but the sensitive-data rule never copies a detected secret value.

Treat exported reports as potentially sensitive because interface names, policy names, and
addresses can still reveal network design.

## Requirements and installation

- Python 3.12 or newer
- Windows, macOS, or Linux
- PySide6 only when using the GUI

PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e '.[dev,gui]'
```

POSIX shell:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev,gui]'
```

The core and CLI have no runtime third-party dependency.

## CLI

```console
netconfiglint check examples/huawei-basic.cfg
netconfiglint check config.txt --mode snippet --vendor auto --format text
netconfiglint check config.txt --mode full --vendor huawei --format json
netconfiglint check snapshot.txt --mode snapshot
```

Exit codes are `0` when no ERROR diagnostic is produced, `1` when at least one ERROR is
reported, and `2` for input/usage/vendor-detection failures. JSON output is stable enough for
beta CI and editor integration experiments; additions may still occur before v1.0 final.

## Desktop GUI

```console
netconfiglint-gui
```

The desktop application uses PySide6, QML, Qt Quick Controls 2, and Material style. It provides:

- file open, paste, edit, drag/drop, analyze, clear, and JSON report export;
- Snippet / Full / Snapshot mode and Auto / Huawei vendor selection;
- conservative device detection details;
- line-numbered monospaced editor, Ctrl+F search, Ctrl+G line jump;
- severity filters, expandable diagnostic cards, and click-to-source navigation;
- Light, Dark, and System themes without restart;
- responsive navigation rail and horizontal/vertical analysis layouts.

History is intentionally non-persistent in this beta. Rule Library and Settings are functional
foundations; richer P2 behavior remains planned.

### Screenshot

_Screenshot placeholder: release screenshots will be added under `docs/screenshots/` after the
first signed Windows artifact is produced._

## Analysis modes

- **Snippet**: missing references become UNKNOWN because the definition may exist outside the
  supplied text. Unused-object checks are suppressed.
- **Full**: the source is treated as a complete candidate configuration, enabling definitive
  normalized reference checks.
- **Snapshot**: the data model is reserved for configuration plus operational output. v1.0 Beta
  currently has only configuration evidence and therefore remains conservative.

## Rule catalog

| Rule ID | Default | Purpose |
|---|---:|---|
| `HUA-VLAN-001` | ERROR | Trunk VLAN referenced but not defined |
| `HUA-VLAN-002` | ERROR | Access VLAN referenced but not defined |
| `HUA-VLAN-003` | INFO | Defined VLAN has no supported reference |
| `HUA-IF-001` | WARNING | Shutdown interface contains apparent business configuration |
| `HUA-IF-002` | ERROR | VLAN command conflicts with interface link type |
| `HUA-IF-003` | ERROR | Eth-Trunk member references an undefined Eth-Trunk |
| `HUA-ROUTE-001` | ERROR | Static route cannot be normalized as an IPv4 route |
| `HUA-ROUTE-002` | WARNING | Static route has an unusual next-hop address class |
| `HUA-BGP-001` | ERROR | BGP peer references an undefined route-policy |
| `HUA-BGP-002` | WARNING | BGP network cannot be proven from configured route candidates |
| `HUA-RPOL-001` | ERROR | Route-policy references an undefined ip-prefix |
| `HUA-RPOL-002` | INFO | Route-policy has no supported consumer reference |
| `HUA-OSPF-001` | ERROR | OSPF network lacks a valid area/network association |
| `HUA-OSPF-002` | WARNING | No interface can be shown to participate in OSPF |
| `HUA-ACL-001` | ERROR | ACL is referenced but not defined |
| `HUA-VPN-001` | ERROR | Interface references an undefined VPN instance |
| `HUA-VPN-002` | ERROR | BGP VPN address-family references an undefined VPN instance |
| `HUA-SEC-001` | INFO | Potentially sensitive configuration keywords detected |

Severity can change by mode. Severity and confidence are independent: VERIFIED, DOCUMENTED,
INFERRED, GENERIC, and LOW describe evidence quality, not operational impact.

## Public API

```python
from netconfiglint import analyze

result = analyze(source, mode="full", vendor="auto")
for diagnostic in result.diagnostics:
    print(diagnostic.rule_id, diagnostic.source.line, diagnostic.message)
```

CLI and GUI call this same API. See [architecture](docs/architecture.md) for dependency rules
and extension points.

## Development and tests

```powershell
.venv\Scripts\python.exe -m pytest
.venv\Scripts\ruff.exe format --check netconfiglint tests
.venv\Scripts\ruff.exe check netconfiglint tests
.venv\Scripts\mypy.exe netconfiglint
```

Headless GUI smoke tests use `QT_QPA_PLATFORM=offscreen`. Every registered rule has a valid and
invalid regression case. Synthetic test data is mandatory; see [CONTRIBUTING.md](CONTRIBUTING.md).

## Windows packaging

The project uses Qt's recommended `pyside6-deploy` path with Nuitka standalone mode:

```powershell
.\scripts\build_windows.ps1 -DryRun
.\scripts\build_windows.ps1
```

The build script enables UTF-8 for Chinese paths, generates the `.ico` from the project SVG,
preserves the portable spec file, includes QML/SVG resources, and verifies that an executable
was produced. With PySide6 6.11 on a builder without Visual Studio `dumpbin`, deployment may
omit wheel runtime DLLs; the script copies the official wheel-provided PySide6/Shiboken DLLs as
a reliability fallback. This makes the current standalone directory large and is a documented
beta packaging tradeoff.

## Dependencies and licenses

NetConfigLint source is Apache-2.0 licensed. Runtime/build dependencies are intentionally small:

| Dependency | Scope | License information | Reason |
|---|---|---|---|
| PySide6 / Qt for Python | Optional GUI/runtime | LGPLv3, GPLv3, or Qt commercial | Official Qt 6 Python/QML bindings |
| Nuitka via `pyside6-deploy` | Build only | See the installed Nuitka distribution and upstream terms | Produces Windows standalone artifacts |
| pytest, Ruff, mypy | Development only | MIT | Tests, linting, and static typing |

The SVG icons in this repository are original project assets under Apache-2.0; no vendor icon
pack or copied vendor documentation is included. Redistributors must independently satisfy Qt,
Python, Nuitka, and bundled third-party license obligations. This section is informational, not
legal advice.

## Known limitations

- The parser covers a bounded VRP subset and is not a CLI emulator.
- Model and version identification stay Unknown unless explicit evidence exists.
- Command availability by exact platform/version is not asserted yet.
- BGP local-RIB and OSPF runtime-state checks cannot be proven from configuration alone.
- “Unused” means no reference recognized by the beta parser; unsupported consumers may exist.
- IPv6 and advanced route/policy constructs are incomplete.
- Snapshot operational-output parsers are placeholders.
- Syntax highlighting and persistent history are not implemented.
- Current Windows standalone output favors reliable DLL inclusion over package size.

Detailed heuristic and device-validation items are tracked in
[Huawei validation notes](docs/huawei-validation.md) and implementation maturity is recorded in
[project status](docs/status.md).

## Roadmap

### v1.0 Beta

Huawei VRP static analysis, shared rule engine, CLI, and Material desktop GUI.

### v1.1

More Huawei rules, validated command compatibility profiles, parser coverage, package-size
reduction, GUI usability, and syntax highlighting.

### v1.5

H3C Comware detector, parser, profile overlays, and rules using the existing core.

### v2.0

Juniper Junos support.

### Future

Snapshot analysis, VS Code extension, topology visualization, Batfish integration, CI/CD
configuration validation, dependency graph, configuration diff, and migration assistance.

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md). New rules require a unique Rule ID, valid and invalid
synthetic fixtures, expected diagnostics, conservative confidence, and documentation. New vendor
support must plug into detection/parser/rule boundaries rather than introduce vendor conditionals
into GUI or shared diagnostics.

## Disclaimer

NetConfigLint performs static analysis and cannot guarantee that a configuration will operate
correctly on physical hardware.

Always validate production network changes using vendor-supported procedures and appropriate lab
or staging environments.

