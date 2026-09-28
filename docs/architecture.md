# NetConfigLint Architecture

## Goals and boundaries

NetConfigLint is an offline static analyzer. Configuration text never leaves the local
process and is never written to logs by default. Static analysis cannot prove runtime
forwarding behavior, hardware support, licensing, or exact version compatibility without
additional evidence; those cases produce conservative diagnostics and confidence values.

The dependency direction is deliberately one-way:

```text
Configuration source
  -> vendor detector
  -> vendor parser
  -> unified DeviceConfig model
  -> rule engine
  -> AnalysisResult / Diagnostic
  -> CLI | GUI bridge | future integrations
```

The core package has no dependency on PySide6. Both CLI and GUI call the same public
`analyze(source, mode, vendor)` API.

## Public API boundary

`netconfiglint.analyze(source, mode=AnalysisMode.FULL, vendor="auto") -> AnalysisResult`
is the stable integration boundary. Inputs and results are immutable-enough dataclasses
containing only serializable values. Consumers must not import a vendor parser directly.

`AnalysisResult` contains detection metadata, normalized configuration objects,
diagnostics, elapsed time, and source line count. Diagnostics include independent severity
and confidence dimensions and retain source ranges without retaining secrets in logs.

## Modules

- `core.model`: cross-vendor configuration and source-location models.
- `core.detector`: detector protocol and conservative detector registry.
- `core.parser`: parser protocol and dispatch registry.
- `core.analyzer`: orchestration API and analysis modes.
- `core.diagnostics`: diagnostic data types and serialization.
- `core.lexer`: vendor-neutral source line/token helpers.
- `rules`: rule protocol, metadata, context, and engine.
- `vendors.registry`: vendor plugin descriptors and auto/explicit vendor resolution.
- `vendors.huawei`: Huawei VRP detection, parsing, evidence-scoped profiles, and rules.
- `cli`: text/JSON adapters over the public API.
- `gui`: testable controller/models and a QML-first presentation layer.

## Extending vendors

A new vendor supplies a detector, parser, optional documented profile facts, and rules. It registers
through the core registries; the unified model, rule engine, diagnostics, CLI, and GUI remain
unchanged. Vendor-specific command knowledge must not leak into GUI code.

## Parser strategy

The Huawei parser is a conservative line-oriented block parser. It recognizes a
bounded set of documented configuration shapes and preserves every source line. Unknown
commands remain available as raw commands and do not cause parse failure. This is not a VRP
CLI emulator. CommandTree, CommandProfile and ProfileOverlay remain explicitly experimental APIs.
They do not validate product input or establish platform command compatibility. The active
ProfileDatabase resolves source-linked metadata only; the capability repair is tracked as F22.

## Analysis modes

- `snippet` (default in GUI, CLI, and API): missing global references are not definitive;
  diagnostics become INFO/UNKNOWN.
- `message`: interprets bounded log, prompt, and command-error event families with source lines
  and investigative causes. Unmatched input remains visible as needing attention.
- `view`: parses available operational evidence without assuming hidden configuration is faulty.
- `full`: combines configuration, display output, and recognized log events in one source-mapped
  result. The supplied configuration remains a candidate, not a device-behavior proof.
- `snapshot` remains a CLI/API compatibility value for older scripts. The parsers handle
  bounded Huawei IPv4/IPv6 RIB, BGP peer, and interface-status sections, plus
  bounded H3C diagnostic-bundle hardware/environment, aggregation, M-LAG/DRCP, OSPF, route-count,
  LLDP, transceiver-alarm, and log-buffer evidence.
  Exact prefix evidence must match the VPN and address family. Absence requires a successful,
  complete, unfiltered capture with a recognized table and a closing device prompt. Failed,
  filtered, paginated, unterminated, or mixed-device captures cannot verify absence.

## Threading and GUI

QML owns layout and interaction. Python exposes QObject controllers and list models. The
controller runs analysis through a worker thread with cooperative resource limits. Large
documents use explicit read-only preview pages, bounded native text layout and visible line
numbers. Source text remains complete in the controller; diagnostic jumps select the matching
preview page and exports/history never consume the shortened display. Preview search covers
the current page.
QML receives display-ready roles and jump targets; it never parses commands or evaluates a
rule.

Translation catalogs, default-on source-restorable history, and block-based syntax highlighting
also sit behind QObject/list-model boundaries. QML does not access the filesystem directly.

## Version/profile evidence

Huawei profile facts are data in `vendors/huawei/profiles/catalog.json`. Each fact names one or
more official-source records and is inherited through base/platform/version overlays. Profile
resolution is conservative: a model-specific release fact requires both model and
version evidence from identity/banner positions, never descriptions. An exact S7700
version match changes the SSH omitted-source check using the cited vendor default;
unmatched versions/models produce UNKNOWN for that fact. Other profile metadata
alone does not imply device-specific validation of all commands. The catalog records
facts needed by this analyzer, not complete copies of vendor documentation.

## Compatibility confidence

Severity describes impact. Confidence describes evidence quality: VERIFIED, DOCUMENTED,
INFERRED, GENERIC, or LOW. Platform/version-specific assertions require a matching profile;
otherwise rules remain generic or return UNKNOWN instead of asserting incompatibility.


## Analysis budgets, coverage and experimental grammar

A per-call ContextVar carries cooperative cancellation and byte, character, line, line-length,
work, diagnostic, VLAN-membership and elapsed-time limits. Parser state belongs to
DeviceConfig, so independent vendor parsers cannot cross-contaminate OSPF area context.
Partial rule output remains available with SYS-LIMIT-001; parse-stage limits return
an explicit incomplete result. Cancellation raises AnalysisCancelled and the GUI
publishes no result/history for cancelled work. The built-in analyzer checks during
work; legacy injected analyzers are only checked before and after their call.

Coverage counts and source lines are exported by default and displayed even when
there are no diagnostics. Recognized does not mean every device syntax or runtime
condition has been checked. Description/banner metadata is explicitly ignored.
An optional initial_view is available to API/CLI snippet callers; the original source
and line numbers are retained. Unsupported undo forms and OSPFv3 remain explicit
unsupported coverage, not guessed effective configuration.

File adapters share one bounded decoder. A UTF-16 BOM is decoded explicitly; otherwise strict
UTF-8 is attempted first, then strict GB18030. UTF-32 and NUL-containing binary input are rejected;
remaining invalid bytes are rendered as visible byte markers rather than silently dropped. Newlines
are normalized before analysis and the original encoding/newline classification is carried into
explicit exports. H3C diagnostic bundles retain full source line numbers while an analysis-line set
restricts configuration coverage to the running-configuration section.

CommandTree and CommandProfile/ProfileOverlay are isolated in
experiments/huawei_grammar, outside the shipped package. They have no active parser
or rule consumer and do not advertise production grammar coverage.

## Independent vendor extension contract (v2.5)

Each `vendors/<vendor>/` package owns detection, configuration/snapshot parsing, effective-command
reduction, semantics, rules, profile facts and vendor-specific message hypotheses. A vendor must
not import another vendor package or convert its input to another vendor's CLI. An AST regression
guard enforces this for the shipped implementations. Shared models, protocol-neutral input/error
handling, resource limits, message rendering and RuleEngine are infrastructure.

Register one VendorPlugin with its aliases, parser, rules, snapshot parser and view rules. Optional
input_preview and message_events are supplied by that vendor. Core/GUI dispatch does not branch on
vendor keys. Add its localized name/profile data and independent positive/negative fixtures. A new
vendor must not be described as supported until those cases and source-preserving UNKNOWN behavior
are qualified. Current model-specific defaults remain vendor-owned.
