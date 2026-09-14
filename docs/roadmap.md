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

## v1.4 — delivered Material desktop and export workflow

- Persistent themes, sidebar, panel visibility/order, and isolated scratch editor.
- Localized UI and diagnostic prose, editor menus, zoom, and explicit export scopes.

## v1.5 — delivered audit repair and Huawei correctness

Closed all 26 v1.4 findings with per-finding regression evidence and integrated 17 Huawei
follow-up repairs. Scoped snapshots and ACL identities, diagnostic virtualization, input
resilience, parser coverage and release verification are covered by the
[repair report](v1.5-audit-repairs.md) and [acceptance evidence](v1.5-acceptance.md).

## Future work (unversioned; not implemented promises)

- Extend the Huawei graph and documented platform profiles after fixture-backed semantic review.
- H3C Comware and Juniper Junos plugins with independent parser/profile/rule contracts.
- Versioned JSON/SARIF integration and optional offline configuration comparison.
- Signed distribution and independently tested additional architectures.

## Longer term

Dependency/topology visualization, Batfish-assisted validation, configuration migration, and
digital-twin features should consume normalized models and explicit evidence. They must remain
optional and local-first; remote processing requires a separate, explicit privacy design.
