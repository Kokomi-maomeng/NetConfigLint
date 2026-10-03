"""Every audited external command has a public, conservative capability status."""

from __future__ import annotations

import json
from pathlib import Path

from netconfiglint.core.support import export_support_inventory, support_inventory, support_scope


def test_product_scope_identifies_reference_versions_and_unsupported_msr_inventory() -> None:
    result = support_scope("h3c")
    assert result["msr7"]["anchors"] == 6476
    assert result["msr7"]["distinct_titles"] == 5445
    assert len(result["msr7"]["missing_root_titles"]) == 1404
    assert len(result["msr7"]["missing_roots"]) == 602
    assert not result["vendors"]["h3c"]["full_device_coverage"]
    assert result["vendors"]["h3c"]["unverified_scopes"]
    assert not support_scope("huawei")["vendors"]["huawei"]["full_device_coverage"]


def test_all_msr_anchors_and_all_450_legacy_forms_have_status_and_official_sources() -> None:
    result = support_inventory("h3c")
    assert len(result["msr7_entries"]) == 6476
    assert len({row["id"] for row in result["msr7_entries"]}) == 6476
    assert len(result["legacy_forms"]) == 450
    assert len({row["id"] for row in result["legacy_forms"]}) == 450
    for row in result["msr7_entries"]:
        assert row["head"] and row["source"].startswith("https://www.h3c.com/")
        assert row["status"] == "index_only_unverified"
    for row in result["legacy_forms"]:
        assert row["syntax"] and row["location"]
        assert row["analysis_status"] == "semantic_unverified"
        assert row["catalogue_status"] in {"catalogued_form", "not_catalogued"}
        assert "h3c.com/" in row["source"]
    assert result["legacy"]["catalogued_forms"] + result["legacy"]["not_catalogued_forms"] == 450
    assert result["legacy"]["semantic_verified_forms"] == 0


def test_support_export_contains_public_data_and_vendor_specific_scope(tmp_path: Path) -> None:
    target = export_support_inventory(tmp_path / "support.json", "auto")
    text = target.read_text("utf-8")
    assert json.loads(text)["legacy"]["forms"] == 450
    assert "build\\" not in text and "C:\\Users" not in text
    only_huawei = support_inventory("vrp")
    assert set(only_huawei["vendors"]) == {"huawei"}
    assert "msr7_entries" not in only_huawei


def test_caller_mutation_cannot_change_the_installed_inventory() -> None:
    scope = support_scope("h3c")
    scope["msr7"]["missing_roots"].clear()
    assert len(support_scope("h3c")["msr7"]["missing_roots"]) == 602
