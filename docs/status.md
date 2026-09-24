# v2.1 implementation status

## Current scope

- The GUI offers configuration snippet, message, View, and full-configuration modes. The CLI
  continues accepting `snapshot` for older scripts.
- Huawei VRP and H3C Comware retain source-linked, conservative diagnostics. H3C adds common IRF
  command recognition and an inferred peer-port warning; operational LLDP rows expose observed
  neighbor edges. Message interpretation covers bounded event families and leaves unclassified
  text explicit.
- Full mode combines supported configuration, display and log evidence. Hidden defaults, physical
  cabling, and device behavior remain outside static verification.
- History is on by default, stores source and diagnostics locally, and can restore an earlier
  workspace. Turning it off confirms deletion. The Windows portable ZIP places application-owned
  settings, history, cache and temporary data beside the executable.
- The desktop uses a top toolbar, collapsible history rail, unified Material cards, and live
  syntax highlighting in both editors. Configuration content remains a required card.

## Release boundary

The v2.1 GitHub Release publishes only a Windows x64 portable ZIP and its SHA-256 checksum.
Linux, macOS, and Windows installer builds remain CI validation paths. Cross-platform CI, the
Windows extracted-package acceptance, and the source/archive privacy scan are release gates.
The command families are bounded by documented fixtures; device-specific acceptance requires
the matching platform, software release, and a controlled network validation.

See [v2.1 scope](v2.1-change-scope.md), [H3C support](h3c-command-support.md), and the
[v2.0 acceptance record](v2.0-acceptance.md) for prior release evidence.
