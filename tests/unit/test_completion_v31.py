"""Bounded interactive metadata and complete, on-demand official provenance."""

from __future__ import annotations

import json

import pytest

from netconfiglint.commands.completion import CompletionCancelled, complete


def test_empty_interactive_query_keeps_all_candidates_without_bulk_details() -> None:
    result = complete("", 0, include_details=False)
    assert len(result["items"]) > 2000
    assert len(json.dumps(result)) < 2_000_000
    assert all(
        row["detailKey"]
        and not row["syntaxDetails"]
        and not row["sourceDetails"]
        and len(row["syntaxes"]) <= 1
        for row in result["items"]
    )
    assert "Recognition does not prove" in result["scopeNote"]


def test_worst_group_details_are_complete_and_loaded_only_for_selected_item() -> None:
    compact = complete("undo", 4, include_details=False)
    item = next(row for row in compact["items"] if row["text"] == "undo")
    assert not item["syntaxDetails"]
    rich = complete("undo", 4, detail_key=item["detailKey"])["items"]
    assert len(rich) == 1 and len(rich[0]["syntaxDetails"]) > 20_000
    assert len(rich[0]["syntaxes"]) > 13_000
    assert all(
        row["sources"] and all(url.startswith("https://") for url in row["sources"])
        for row in rich[0]["syntaxDetails"]
    )


@pytest.mark.parametrize("source", ["sysname ", "ip binding vpn-instance "])
def test_parameter_only_queries_keep_capability_and_reference_details(source: str) -> None:
    compact = complete(source, len(source), ("huawei",), include_details=False)
    assert not compact["items"] and compact["argumentDetails"]
    parameter = compact["argumentDetails"][0]
    assert parameter["aliases"] and parameter["description"] and parameter["sources"]
    rich = complete(source, len(source), ("huawei",), detail_key=parameter["detailKey"])
    detail = next(row for row in rich["argumentDetails"] if row["detailKey"] == parameter["detailKey"])
    assert detail["syntaxDetails"]
    assert set(parameter["aliases"]) <= set(detail["aliases"])


def test_cancelled_request_stops_during_catalog_iteration() -> None:
    polls = 0

    def cancelled() -> bool:
        nonlocal polls
        polls += 1
        return polls >= 3

    with pytest.raises(CompletionCancelled):
        complete("", 0, include_details=False, cancelled=cancelled)
    assert polls == 3
