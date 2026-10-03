"""Public, source-scoped command inventory; never a device compatibility claim."""

from __future__ import annotations

import copy
import json
from functools import lru_cache
from importlib.resources import files
from pathlib import Path
from typing import Any


def _key(vendor: str) -> str:
    return {"vrp": "huawei", "comware": "h3c", "comware7": "h3c"}.get(vendor.lower(), vendor.lower())


@lru_cache(maxsize=1)
def _inventory() -> dict[str, Any]:
    value = json.loads(files("netconfiglint.vendors").joinpath("support_matrix.json").read_text("utf-8"))
    if not isinstance(value, dict) or value.get("schema") != 1:
        raise ValueError("Invalid command support inventory")
    return value


def support_scope(vendor: str = "auto") -> dict[str, Any]:
    """Summarize named references and known gaps for display inside the product."""
    data = _inventory()
    key = _key(vendor)
    selected = [key] if key in {"h3c", "huawei"} else ["h3c", "huawei"]
    result: dict[str, Any] = {
        "schema": 1,
        "scope": data["scope"],
        "status_definitions": copy.deepcopy(data["status_definitions"]),
        "vendors": {item: copy.deepcopy(data["vendors"][item]) for item in selected},
    }
    if "h3c" in selected:
        result["msr7"] = copy.deepcopy(data["msr7_summary"])
        result["legacy"] = copy.deepcopy(data["legacy_summary"])
    return result


def support_inventory(vendor: str = "auto") -> dict[str, Any]:
    """Return every MSR index anchor and legacy syntax row with its status/source.

    Exact catalogue presence is recomputed from the installed catalogues, so a
    historical audit's prefix match cannot become a v3 completion support claim.
    Catalogue presence still does not validate parameters, views, or semantics.
    """
    result = support_scope(vendor)
    if "h3c" not in result["vendors"]:
        return result
    syntax = {
        " ".join(row["syntax"].split()).casefold()
        for row in json.loads(files("netconfiglint.commands").joinpath("data/h3c.json").read_text("utf-8"))[
            "commands"
        ]
    }
    result["msr7_entries"] = copy.deepcopy(_inventory()["msr7_entries"])
    result["legacy_forms"] = copy.deepcopy(_inventory()["legacy_forms"])
    for row in result["legacy_forms"]:
        row["catalogue_status"] = (
            "catalogued_form" if " ".join(row["syntax"].split()).casefold() in syntax else "not_catalogued"
        )
    result["legacy"]["catalogued_forms"] = sum(
        row["catalogue_status"] == "catalogued_form" for row in result["legacy_forms"]
    )
    result["legacy"]["not_catalogued_forms"] = (
        result["legacy"]["forms"] - result["legacy"]["catalogued_forms"]
    )
    return result


def export_support_inventory(path: str | Path, vendor: str = "auto") -> Path:
    """Write only public manual metadata and command forms, with no input config."""
    target = Path(path)
    target.write_text(json.dumps(support_inventory(vendor), ensure_ascii=False, indent=2) + "\n", "utf-8")
    return target
