# v2.0 implementation status

## Delivered source scope

- Huawei VRP remains at its v1.5 conservative parser/rule scope.
- H3C Comware 7 has independent detection, parsing, rule IDs, command accounting, and 43 registered rules.
- Every non-empty H3C line is preserved. Lines without implemented semantics are reported as
  source-linked UNKNOWN rather than silently accepted.
- The three workspace cards use a live full-card drag proxy and Material motion. The title bar,
  navigation rail, and workspace form one coherent surface.
- The meaningless About horizontal thumb and text glyph substitutes were removed; scrollbar
  visibility now follows actual overflow.
- The original sakura-network icon has generated 16–1024 px variants and native package assets.
- Portable history stays adjacent to the executable; installed history uses platform app data.
  Uninstall helpers expose keep-history and delete-all-data choices.

## Release boundaries

- Windows portable ZIP and WiX MSI, Linux amd64 DEB, and macOS PKG build paths are automated.
- Trusted Windows/macOS signatures require external code-signing identities. Missing credentials
  produce explicitly named unsigned installers; the build never labels them signed.
- Windows and Debian acceptance require real installed/portable smoke evidence. macOS authored
  packaging or CI smoke is not evidence for user-hardware compatibility.
- Static analysis cannot prove device behavior, every platform-specific command, or live network correctness.

See [H3C support](h3c-command-support.md), [v2.0 release notes](release-v2.0.0.md), and
[v2.0 acceptance](v2.0-acceptance.md).
