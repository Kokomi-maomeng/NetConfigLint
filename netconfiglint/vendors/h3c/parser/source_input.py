"""Comware diagnostic-bundle preview; the full source remains available to analysis."""

from netconfiglint.vendors.h3c.parser.diagnostic_bundle import extract_h3c_diagnostic_bundle


def configuration_preview(source: str) -> tuple[str, dict[int, int]] | None:
    bundle = extract_h3c_diagnostic_bundle(source)
    if bundle is None:
        return None
    lines = source.splitlines()
    selected = sorted(bundle.analysis_lines)
    preview = "\n".join(lines[number - 1] for number in selected)
    if preview and source.endswith("\n"):
        preview += "\n"
    return preview, {number: index for index, number in enumerate(selected, 1)}
