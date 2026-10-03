"""Independent manual markup fixtures guard against repeating extraction defects."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def importer():
    pytest.importorskip("bs4", reason="Official manual importer uses optional catalog tooling")
    pytest.importorskip("defusedxml", reason="Official manual importer uses optional catalog tooling")
    from scripts import import_completion_catalog

    return import_completion_catalog


def test_h3c_boldtext_syntax_is_imported_and_unmarked_text_is_queued(tmp_path: Path, importer) -> None:
    page = tmp_path / "igmp-election.htm"
    page.write_text(
        '<html><title>IGMP snooping</title><p class="Command">Syntax</p>'
        '<p><span class="BoldText">igmp-snooping querier-election</span></p>'
        '<p><span class="BoldText">undo igmp-snooping querier-election</span></p>'
        '<p>A descriptive unmarked paragraph</p><p class="Command">Views</p>'
        "<p>VLAN view</p><p>VSI view</p>"
        '<p class="Command">Predefined user roles</p><p>network-admin</p></html>',
        encoding="utf-8",
    )
    review = []
    rows = importer.h3c_rows(page, review)
    assert [row["syntax"] for row in rows] == [
        "igmp-snooping querier-election",
        "undo igmp-snooping querier-election",
    ]
    assert all(row["views"] == ["VLAN view", "VSI view"] for row in rows)
    assert len(review) == 1 and review[0]["paragraph"] == 3


def test_inline_annotations_are_retained_conditionally_without_stripping_real_parentheses(importer) -> None:
    clean, annotations = importer.split_annotations("assign resource-mode enhanced-mac all ( S6730-H )")
    assert clean == "assign resource-mode enhanced-mac all" and annotations == ["( S6730-H )"]
    assert importer.split_annotations("test expression (1+2)") == ("test expression (1+2)", [])
    entries = {}
    importer.merge_row(
        entries, importer._row("sysname <name>", "System view", "https://example/a", "Manual A", "a"), "h3c"
    )
    importer.merge_row(
        entries, importer._row("sysname <name>", "User view", "https://example/b", "Manual B", "b"), "h3c"
    )
    row = entries["sysname <name>"]
    assert len(row["sources"]) == 2
    assert row["sources"][0]["views"] == ["System view"]
    assert row["sources"][1]["views"] == ["User view"]
