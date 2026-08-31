# v1.0 Beta implementation status

## Stable architecture

- `analyze(source, mode, vendor) -> AnalysisResult` public boundary.
- Vendor-neutral configuration, source range, diagnostic, severity, and confidence models.
- Detector/parser/rule protocols and unique-ID rule engine.
- Shared result consumption by CLI and GUI.
- QML-first GUI boundary using QObject, Property, Signal, Slot, and QAbstractListModel.
- Package-relative QML and SVG resource loading.
- Synthetic-fixture and no-production-data contribution policy.

## Beta implementation

- Huawei VRP line/block parser for the documented v1.0 subset.
- Eighteen Huawei rules and their mode-aware behavior.
- Huawei detection confidence and conservative metadata.
- CLI text/JSON rendering and exit codes.
- Material-inspired desktop pages, editor, diagnostics, filters, themes, file/report actions, and
  async controller.
- Windows standalone build with a runtime-DLL fallback for builders without `dumpbin`.

## Experimental / TODO

- Snapshot operational-output parsing.
- Command tree/profile data beyond demonstration structures.
- Syntax highlighting and richer editor behavior.
- Persistent history (disabled by design in this beta).
- Exact platform/model/version compatibility rules.
- Optimized Windows DLL dependency closure and signed installers.
- Linux/macOS packaged artifact tests; CI currently validates source/QML execution.

## H3C reuse boundary

Directly reusable: analyzer result contract, analysis modes, diagnostics/confidence, source mapping,
normalized models, rule engine, CLI formatters, GUI controller/list model/QML, tests patterns, and
CI.

H3C-specific additions: detector signatures, Comware lexer/parser grammar, platform/version
profiles, command tree overlays, rule registry, and fixtures. Shared models may gain optional
vendor-neutral fields, but H3C support must not add parsing or rules to GUI code.

