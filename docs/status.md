# v1.1 Beta implementation status

## Stable architecture

- `analyze(source, mode, vendor) -> AnalysisResult` integration boundary.
- Vendor-neutral configuration, operational evidence, source range, diagnostic, severity, and
  confidence models.
- Detector/parser/rule protocols, registry boundaries, and unique-ID rule engine.
- Shared result consumption by CLI, GUI, and future integrations.
- QML-first GUI using QObject, Property, Signal, Slot, and QAbstractListModel.
- Package-relative QML, translation, profile, and SVG resource loading.
- Synthetic-fixture, local-only processing, and no-production-data contribution policy.
- Base/platform/model/version profile inheritance with auditable source references.

## Beta implementation

- Huawei VRP bounded line/block parser plus recognized operational snapshot sections.
- 26 mode-aware Huawei rules, each with valid and invalid synthetic fixtures.
- IPv4/IPv6 RIB exact-prefix evidence, BGP peer state, and interface state parsing.
- IPv6 static/address checks, BGP groups, interface OSPF, ACL6 and traffic-policy references.
- CLI text/JSON rendering and documented exit codes.
- Material-inspired bilingual desktop shell, editor, diagnostics, themes, async analysis,
  incremental highlighting, and optional privacy-minimized history.
- Synthetic large-configuration regression benchmark.
- Recursive Windows PE dependency closure and Inno Setup installer workflow.

## Experimental / TODO

- Exact Huawei command availability outside the documented catalog facts.
- Complete snapshot output variants and explicit section/container schema.
- Active/inactive route selection, recursive next-hop resolution, and hardware FIB evidence.
- Complete BGP group inheritance and address-family activation semantics.
- Complete OSPF/OSPFv3, ACL/QoS/policy consumer graph, and IPv6 command coverage.
- Localized rule messages; v1.1 translates the GUI shell and controls.
- Trusted Windows signing; the build supports it but needs an external certificate/private key
  and Windows SDK SignTool.
- Linux/macOS packaged artifact tests; CI validates source/QML execution on all three platforms.

## H3C reuse boundary

Directly reusable: public analyzer/result contract, modes, operational-evidence containers,
diagnostics/confidence, source mapping, normalized models, rule engine, CLI formatters, GUI
controller/list models/QML, translation/history infrastructure, fixture patterns, benchmark,
and CI.

H3C-specific additions: detector signatures, Comware parser/grammar, operational-output parser,
platform/version profiles, command overlays, vendor rule registry, and synthetic fixtures. Shared
models may gain optional vendor-neutral fields, but Comware knowledge must not enter GUI code.
