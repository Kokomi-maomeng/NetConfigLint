# Third-party notices

NetConfigLint and its original SVG/QML assets are provided under the complete
Apache License 2.0 in `LICENSE`. Copyright NetConfigLint contributors.

Each standalone package includes `SBOM.json`: actual relative file paths, SHA256,
sizes, component identities, license copies and corresponding source locations.
`licenses/components.json` is the reviewed catalog, not a claim that every listed
component is shipped. The inventory selects components found in that package.

| Component | Terms and material |
| --- | --- |
| Python 3.13.2 and its bundled extensions | Full PSF/Python and embedded third-party notices in `licenses/Python-3.13.2.txt`; actual interpreter license also copied when present |
| PySide6, Shiboken6 and Qt 6.11.2 | LGPLv3/GPLv3/commercial alternatives; this build uses the LGPL option for the selected Qt Core, GUI, Network, OpenGL, QML, Quick, Quick Controls, SVG and associated plugins |
| Qt source dependencies | Full upstream `LICENSES`, attribution records and every referenced license file under `licenses/upstream`; this is a conservative source-module superset, not proof that every source dependency is linked |
| Nuitka 4.2 generated runtime | AGPLv3 with Runtime Library Exception 1.0; full license, exception and notice in `licenses/Nuitka-4.2-*`. The exception permits eligible independent compiled modules to be conveyed under their own terms |
| OpenSSL / libffi | Actual Windows CPython dependency material in `licenses`; hashes identify the distributed DLLs |
| Microsoft Visual C++ runtime | Full Microsoft 2015–2022 Runtime terms in `licenses/Microsoft-VC-Runtime-2015-2022.txt`; these apply to the Microsoft binaries |
| Mesa llvmpipe / LLVM | Qt's Windows `opengl32sw.dll`; full MIT, Boost and LLVM notices in `licenses/Mesa-llvmpipe.txt` and `licenses/LLVM-Qt-attribution.txt` |
| Roboto / Noto Sans SC | Full SIL OFL 1.1 notices beside the font files in `netconfiglint/resources/fonts` |

Qt is copyright The Qt Company and its contributors. PySide/Shiboken are copyright
The Qt Company and their contributors. Individual third-party copyright statements
are preserved in the upstream attribution and license files.

## Corresponding sources and library replacement

`licenses/sources.json` records the exact Qt 6.11.2 upstream source tree IDs, official
source archive URLs, and hashes of all copied legal material. Download the matching
archives to obtain the corresponding source, including its build files. PySide's
archive includes Shiboken. Python, OpenSSL, Mesa and compiler runtime source references
are in `licenses/components.json`. License-material retrieval date: 2026-09-10.

Qt/PySide libraries are distributed separately in the standalone directory, using
dynamic loading. The package must retain this form: the build gate rejects an absent
external Qt Core library. Users may replace the dynamic Qt/PySide libraries with
ABI-compatible modified builds; retain their names, architecture and dependency
closure. Make a working copy, replace the libraries there, and run the executable
with `--smoke-test <output-directory>` to verify startup and UI behavior. No application
signature check or license term prohibits reverse engineering needed to debug LGPL
library modifications. Compatible replacement still requires an appropriate build
and does not imply arbitrary Qt versions are binary compatible.

Release maintainers must keep the matching source archives available alongside, or
through the recorded accessible source locations for, the distributed version. The
license gate verifies the actual ZIP's complete legal material and file inventory;
it does not certify all legal obligations or third-party binary provenance. Platform
qualification and upstream wheel provenance have separate release gates.

The Material design reference is
[Material-Design-CastoriceUI](https://github.com/Kokomi-maomeng/Material-Design-CastoriceUI).
No vendor firmware, production configuration, credentials or private operational
data is included.
