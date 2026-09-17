# NetConfigLint v2.0.0

## Added

- H3C Comware 7 detection, source-preserving parsing, common command normalization, 47 H3C rule
  evaluators,
  and explicit per-line UNKNOWN accounting for commands without implemented semantics.
- Bounded UTF-8/GB18030 import with visible invalid-byte recovery, mixed-newline normalization, and
  source-mapped large H3C diagnostic-bundle analysis.
- H3C operational checks for hardware/environment, aggregation, M-LAG/DRCP, OSPF, routes, LLDP,
  transceiver alarms, running/saved consistency, and log-buffer evidence.
- Native H3C checks for writable/legacy SNMP communities, SSH-only VTY posture, legacy TLS versions,
  and conservative OSPF adjacency/authentication review.
- Original sakura-network application icon at UI, ICO, PNG (16–1024), and macOS ICNS inputs.
- Configurable Windows WiX MSI, Linux amd64 DEB, macOS PKG, and retained Windows portable ZIP.
- Installed-data cleanup command plus keep-history/delete-all uninstall choices.

## Changed

- Rebuilt the app chrome so the title bar continues the navigation surface into the workspace.
- Card reordering now drags a live image of the complete card with lift/settle motion.
- Centralized interaction timings into Material motion tokens and corrected pressed/hover transitions.
- Installed history now follows platform application-data conventions; only portable builds write beside the executable.

## Fixed

- Removed the nonfunctional tiny About-page horizontal scroll indicator.
- Replaced font-dependent grip/dropdown glyphs with deterministic QML geometry.
- Eliminated the old outline-only drag placeholder and ambiguous semantic-coverage status.
- Stopped operational command output from producing configuration false positives, made JSON export
  schema 2.0 explicit, and added unsupported-line plus complete H3C syntax highlighting.
- Large diagnostic files now use a responsive read-only running-configuration/evidence preview;
  full exports still retain the complete source and configuration-only exports select the running config.
- Pinned every third-party GitHub Action to a full commit and added Bandit, dependency audit, and
  CodeQL workflows.

Trusted package signatures are conditional on external Windows and Apple signing identities. Unsigned
outputs are named as such and must not be represented as signed.
