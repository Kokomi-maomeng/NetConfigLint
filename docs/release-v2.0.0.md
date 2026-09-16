# NetConfigLint v2.0.0

## Added

- H3C Comware 7 detection, source-preserving parsing, common command normalization, 43 H3C rules,
  and explicit per-line UNKNOWN accounting for commands without implemented semantics.
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

Trusted package signatures are conditional on external Windows and Apple signing identities. Unsigned
outputs are named as such and must not be represented as signed.
