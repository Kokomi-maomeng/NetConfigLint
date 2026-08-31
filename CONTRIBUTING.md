# Contributing to NetConfigLint

## Engineering rules

- Keep core analysis independent of PySide6 and QML.
- Extend normalized models before making multiple rules rescan raw source.
- Give every rule a unique, documented Rule ID.
- Add at least one valid and one invalid regression case for every rule.
- Preserve one-based source locations and do not fabricate unsupported semantics.
- Use UNKNOWN or conservative confidence when the supplied evidence is incomplete.
- Run pytest, Ruff, and mypy before submitting a change.

## Configuration-data safety

Only synthetic or fully desensitized fixtures may be committed. Do not submit real enterprise
running configurations or operational command output.

Fixtures must not contain real:

- public IP addresses or BGP peers;
- passwords, cipher text, SNMP communities, secrets, or private keys;
- device hostnames, customer names, circuit names, or VPN keys;
- production interface descriptions or topology identifiers.

Use documentation ranges such as `192.0.2.0/24`, `198.51.100.0/24`, and `203.0.113.0/24`, plus
obvious names such as `SYNTHETIC-LAB`, `TEST-POLICY`, and `EXAMPLE-VPN`. A fake secret fixture
must be visibly synthetic and should only test that its value is not repeated in diagnostics.

## Adding a vendor

Implement a detector, parser, optional profile overlays/grammar, and vendor rules. Register them
through the core interfaces. CLI, GUI, diagnostics, and the rule engine should not need vendor-
specific branches beyond registry wiring.

## Adding a rule

1. Confirm the behavior using vendor-supported documentation or mark it GENERIC/TODO.
2. Prefer normalized objects and source ranges.
3. Define severity and confidence independently.
4. Define Snippet/Full/Snapshot behavior.
5. Add valid, invalid, and mode-boundary tests.
6. Add the Rule ID to the README catalog.

