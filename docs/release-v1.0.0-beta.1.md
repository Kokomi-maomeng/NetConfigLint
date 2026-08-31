# NetConfigLint v1.0.0 Beta 1

Initial public beta baseline:

- offline Huawei VRP static analysis with 18 rules;
- shared analyzer API, CLI text/JSON, and conservative Snippet/Full/Snapshot framework;
- QML-first PySide6 Material desktop GUI with source-linked diagnostics;
- Light/Dark/System themes and Windows standalone build;
- synthetic tests across parser, model, rules, CLI, GUI bridge, and QML loading.

Known limitations include a generic profile scaffold, no operational snapshot parser, no IPv6
rules, no persistent history, no syntax highlighting, and a large conservative Windows runtime.

The Windows ZIP is an unsigned beta artifact. Verify its published SHA-256 before use.
