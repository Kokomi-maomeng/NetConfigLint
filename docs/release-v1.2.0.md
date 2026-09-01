# NetConfigLint v1.2.0

NetConfigLint v1.2.0 promotes the Huawei analyzer from beta to a stable, local-first desktop
release.

Highlights:

- 50 Huawei checks spanning Layer 2, interfaces, routing, policy, VPN, VXLAN/EVPN, IS-IS, STP,
  and management-plane security.
- Generic source-mapped retention of every Huawei configuration block plus expanded normalized
  models and 24 new fixture-backed rules.
- Aggregate-only validation of 40 locally supplied production-derived Huawei exports without
  copying or logging their content.
- Rebuilt Material Design workspace with card-based actions, diagnostics, analyzed/temporary
  editors, custom mode/vendor choice dialogs, text selection, animations, and bilingual labels.
- Local history stored in `history/history.json` beside the portable program when enabled.
- Windows x64 portable ZIP with `NetConfigLint.exe` using the GUI subsystem, so no console window
  is opened.

Limitations and safety notes are documented in the README and Huawei validation notes. The
portable binary is unsigned unless a trusted external Authenticode certificate is supplied.
