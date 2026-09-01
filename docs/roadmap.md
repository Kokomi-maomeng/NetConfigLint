# Executable product roadmap

This roadmap orders work by evidence quality and reusable architecture, not by rule count.

## v1.2 — delivered

1. Expanded the Huawei analyzer from 26 to 50 fixture-backed rules.
2. Added generic source-mapped blocks and privacy-safe production-derived aggregate validation.
3. Rebuilt the QML workspace around Material cards, dialogs, selectable text, a temporary editor,
   portable history, and a no-console Windows ZIP.
4. Kept source/QML tests on Windows, Linux, and macOS.

Remaining localization, snapshot-evidence, and signed provenance work moves forward without
weakening the conservative Unknown behavior.

## v1.3 — delivered desktop layout and readability repair

1. Reordered the main workspace into three left-to-right resizable cards.
2. Replaced the diagnostic dropdown with four toggleable severity chips.
3. Rebuilt mode/vendor dialogs and removed the cramped trailing arrows.
4. Corrected editor gutters, header allocation, placeholder rendering, scrolling, and long-line
   sizing in analyzed and temporary editors.
5. Normalized the complete application typography scale and added runtime QML geometry,
   filtering, dialog, and editor regressions.
6. Produced a no-console Windows x64 portable ZIP and retained three-platform source/QML CI.

## v1.4 — Huawei configuration graph

1. Normalize route-targets, community filters, AS-path filters, policy nodes, and redistribution.
2. Add OSPFv3/interface cost/passive behavior and more IPv6 consumers.
3. Build an internal reference graph shared by unused/missing/cycle rules and future visualization.
4. Add configuration-diff API with stable object identities and source-aware changes.
5. Expand official profiles by platform/release only after source review and synthetic fixtures.
6. Move rule messages, explanations, and suggested fixes into typed English/Chinese catalogs.
7. Introduce explicit snapshot command/capture boundaries and reject truncated evidence
   conservatively.

Exit criteria: graph consistency tests, no rule rescans raw source when normalized data exists,
and documented false-positive budgets for every new rule family.

## v1.5 — H3C Comware

1. Add detector, profile catalog, parser, operational snapshot parser, and vendor rule registry.
2. Reuse the core model, diagnostics, analysis modes, CLI/JSON, GUI, history, translations, and CI.
3. Add cross-vendor contract tests proving Huawei behavior does not change.

Exit criteria: representative synthetic Comware coverage, at least 15 conservative rules, and
zero H3C command parsing in shared GUI/core orchestration modules.

## v1.6 — integrations

1. Publish a versioned JSON schema and SARIF formatter.
2. Add a VS Code extension using the CLI/core contract without embedding rule logic.
3. Add CI examples for GitHub Actions and pre-change validation.
4. Provide opt-in anonymized local performance tracing with no source text.

Exit criteria: schema compatibility tests, editor jump/range tests, and documented privacy model.

## v2.0 — Juniper Junos

1. Add hierarchical Junos parsing and set-format normalization behind the same vendor boundary.
2. Add Junos profiles, rules, snapshots, and fixtures.
3. Generalize only genuinely shared concepts; do not force VRP syntax into the Junos model.

Exit criteria: Huawei/H3C/Junos contract suite, migration guide for the public API, and a stable
plugin registration interface.

## Longer term

Dependency/topology visualization, Batfish-assisted validation, configuration migration, and
digital-twin features should consume normalized models and explicit evidence. They must remain
optional and local-first; remote processing requires a separate, explicit privacy design.
