# Windows packaging and signing

`scripts/build_windows.ps1` creates a standalone directory with Qt/Python resources addressed
relative to the executable. The post-build stage removes unused Qt modules and plug-ins, walks
the PE import graph recursively with `pefile`, copies only reachable PySide6/Shiboken DLLs, and
fails on unresolved non-system imports.

`scripts/build_msi.ps1` uses WiX Toolset 3.14. Without a certificate it deliberately emits an
artifact ending in `-unsigned.msi`. This prevents an unsigned test build from being confused with
a trusted release.

For a signed release, install the Windows SDK signing tools and place a valid code-signing
certificate with private key in the current user's certificate store. Then run:

```powershell
.\scripts\build_msi.ps1 -CertificateThumbprint '<certificate-thumbprint>' -SkipAppBuild
```

The script signs the copied application executable before WiX harvest, signs the final MSI with
SHA-256 Authenticode, uses an RFC 3161 timestamp, and verifies that Windows reports a Valid
signature. It stops instead of
publishing when the certificate, private key, SignTool, timestamp, or final validation is missing.

Certificate files, private keys, PINs, tokens, and thumbprints must never be committed. CI signing
should use a protected code-signing service or hardware-backed identity with environment-scoped
approval and no pull-request access.
