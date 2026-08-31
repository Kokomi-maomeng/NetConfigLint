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
- `vendors.huawei`: Huawei VRP detection, parsing, profiles, grammar scaffolding, and rules.
- `cli`: text/JSON adapters over the public API.
- `gui`: testable controller/models and a QML-first presentation layer.

## Extending vendors

A new vendor supplies a detector, parser, optional profile overlays, and rules. It registers
through the core registries; the unified model, rule engine, diagnostics, CLI, and GUI remain
unchanged. Vendor-specific command knowledge must not leak into GUI code.

## Parser strategy

The Huawei beta parser is a conservative line-oriented block parser. It recognizes a
bounded set of documented configuration shapes and preserves every source line. Unknown
commands remain available as raw commands and do not cause parse failure. This is not a VRP
CLI emulator. Grammar/profile scaffolding supports future command trees, shortest-unique-
prefix resolution, and base/platform/model/version overlays.

## Analysis modes

- `snippet`: missing global references are not definitive; diagnostics become INFO/UNKNOWN.
- `full`: the supplied configuration is treated as the complete candidate configuration.
- `snapshot`: accepts a snapshot container in the API; v1.0 Beta uses configuration evidence
  and reserves runtime evidence fields for future routing/interface command output.

## Threading and GUI

QML owns layout and interaction. Python exposes QObject controllers and list models. The
controller runs analysis through a worker thread so large inputs cannot freeze the UI.
QML receives display-ready roles and jump targets; it never parses commands or evaluates a
rule.

## Compatibility confidence

Severity describes impact. Confidence describes evidence quality: VERIFIED, DOCUMENTED,
INFERRED, GENERIC, or LOW. Platform/version-specific assertions require a matching profile;
otherwise rules remain generic or return UNKNOWN instead of asserting incompatibility.
