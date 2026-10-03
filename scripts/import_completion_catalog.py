"""Import functional CLI syntax from official offline manuals, retaining provenance.

Install constraints/catalog.txt in a tooling environment. H3C input is a decompiled
official CHM directory. Huawei input is the directory of cached main-content HTML
and catalogue XML fetched by --download. No manual prose or device configs is copied.
"""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import re
import urllib.parse
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup, NavigableString, Tag
from defusedxml.ElementTree import fromstring

if __package__:
    from .completion_syntax import normalize_syntax
else:
    from completion_syntax import normalize_syntax

HUAWEI_MANUALS = {
    "EDOC1100459368": "CloudEngine S8700 V600R024C10",
    "EDOC1100410645": "S300/S500/S2700/S5700/S6700 V200R024C00",
    "EDOC1100420140": "CloudEngine 9800/8800/6800/5800 V200R024C00",
}
H3C_MANUAL = "S6805/S6825/S6850/S9850 Comware 7 Release 6715-6W100"
H3C_SOURCE = (
    "https://www.h3c.com/en/Support/Resource_Center/EN/Home/Public/00-Public/"
    "Technical_Documents/Reference_Guides/Command_References/"
    "H3C_S6805_S9850_CRs_Release_6715-18388/00/"
)
HUAWEI_API_PATH = "/supportgateway/view/v1/enterprise/doc/"


def _read(endpoint: str, nid: str, part: str = "") -> bytes:
    if endpoint not in {"catalogue", "main-content"} or nid not in HUAWEI_MANUALS:
        raise ValueError("Unsupported official reference")
    if part and not re.fullmatch(r"j[0-9a-z]+", part):
        raise ValueError("Invalid reference chapter")
    query = {"nid": nid}
    if part:
        query["partNo"] = part
    connection = http.client.HTTPSConnection("support.huawei.com", timeout=45)
    try:
        connection.request("GET", HUAWEI_API_PATH + endpoint + "?" + urllib.parse.urlencode(query))
        response = connection.getresponse()
        if response.status != 200:
            raise OSError(f"Official reference returned {response.status}")
        contents = response.read(20_000_001)
        if len(contents) > 20_000_000:
            raise ValueError("Reference chapter exceeds the import bound")
        return contents
    finally:
        connection.close()


def _syntax(paragraph: Tag) -> str:
    for variable in paragraph.select("i, em, .commandparameter, .commandarguments, .commandvariables"):
        variable_text = re.sub(r"(&<\d+-\d+>)", r" \1 ", variable.get_text(" ", strip=True))
        names = re.findall(r"&<\d+-\d+>|[\[\]{}|*]|[^\s\[\]{}|*]+", variable_text)
        following = variable.next_sibling
        # 'port-id' in italics followed by a plain '1' is one metavariable.
        if len(names) == 1 and isinstance(following, NavigableString):
            suffix = re.match(r"^\d+", str(following))
            if suffix:
                names[0] += suffix[0]
                following.replace_with(str(following)[len(suffix[0]) :])
        variable.replace_with(
            " "
            + " ".join(
                name if name in {"[", "]", "{", "}", "|", "*"} or name.startswith("&<") else f"<{name}>"
                for name in names
            )
            + " "
        )
    syntax = re.sub(r"\s+", " ", paragraph.get_text(" ", strip=True)).strip()
    syntax = re.sub(r"&\s*<\d+-\d+>", " * ", syntax)
    syntax = syntax.replace("^{*}", "*").replace("^ *", "*")
    # View/model labels within a Format section are prose, not commands.
    if not re.match(r"^[a-z][a-z0-9-]*\b", syntax) or syntax.endswith(":"):
        return ""
    return syntax


def split_annotations(syntax: str) -> tuple[str, list[str]]:
    """Separate documented applicability prose, while retaining real CLI parentheses."""
    for match in re.finditer(r"\s*\(", syntax):
        tail = syntax[match.start() :].strip()
        note = tail.lstrip("( ")
        if (
            re.match(r"(?:S\d|CE\d|V\d{3}R\d|0:\s*visit\s+level\b)", note, re.I)
            or re.search(
                r"\b(?:supported?|supports?|this command|interface views?|port group view|VLAN view)\b",
                note,
                re.I,
            )
            or note.lower().startswith("if vpn-instance ")
        ):
            return syntax[: match.start()].strip(), [tail]
    return syntax, []


def _row(
    syntax: str, view: str | list[str], source: str, manual: str, chapter: str, title: str = ""
) -> dict[str, Any]:
    syntax, annotations = split_annotations(syntax)
    views = [view] if isinstance(view, str) else view
    return {
        "syntax": syntax,
        "views": views,
        "source": source,
        "sources": [
            {
                "url": source,
                "manual": manual,
                "views": views,
                "chapter": chapter,
                "title": title,
                "annotations": annotations,
            }
        ],
    }


def merge_row(entries: dict[str, dict[str, Any]], row: dict[str, Any], vendor: str) -> None:
    syntax = normalize_syntax(vendor, row["syntax"])
    row["syntax"] = syntax
    if syntax in entries:
        current = entries[syntax]
        # The view union is used only for ranking. Each source retains its own
        # applicability and view conditions; these are never unioned as validation.
        current["views"] = sorted(set(current["views"] + row["views"]))
        current["sources"].extend(value for value in row["sources"] if value not in current["sources"])
        if not row.get("legacy", False):
            current.pop("legacy", None)
    else:
        entries[syntax] = row


def huawei_rows(path: Path, source: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(path.read_bytes(), "html.parser")
    rows = []
    for section in soup.select('[class$="cliformatbody"]'):
        topic = section.find_parent("div", class_=re.compile(r"(?:nested[0-9]+|topic)$"))
        viewbody = topic.select_one('[class$="cliviewbody"]') if topic else None
        view = viewbody.get_text(" ", strip=True) if viewbody else "Any view"
        for paragraph in section.find_all("p", recursive=False):
            if not paragraph.select_one('[class$="cmdname"], strong, b'):
                continue
            syntax = _syntax(paragraph)
            if syntax:
                nid = next((nid for nid in HUAWEI_MANUALS if nid in source), "")
                heading = topic.select_one('[class$="title"]') if topic else None
                rows.append(
                    _row(
                        syntax,
                        view,
                        source,
                        HUAWEI_MANUALS.get(nid, nid),
                        path.name,
                        heading.get_text(" ", strip=True) if heading else "",
                    )
                )
    return rows


def h3c_rows(path: Path, review: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    soup = BeautifulSoup(path.read_bytes(), "html.parser")
    heading = soup.find(string=lambda value: value is not None and value.strip() == "Syntax")
    if not heading:
        return []
    viewheading = soup.find(string=lambda value: value is not None and value.strip() == "Views")
    view = ["Any view"]
    if viewheading:
        parent = viewheading.find_parent("p")
        views = []
        while parent:
            parent = parent.find_next_sibling()
            if not parent or parent.get("class") == ["Command"]:
                break
            text = parent.get_text(" ", strip=True)
            if text:
                views.append(text)
        if views:
            view = views
    paragraph = heading.find_parent("p")
    rows = []
    ordinal = 0
    while paragraph:
        paragraph = paragraph.find_next_sibling()
        if not paragraph or paragraph.get("class") == ["Command"]:
            break
        ordinal += 1
        if not paragraph.select_one(".commandkeywords, .BoldText"):
            if review is not None and paragraph.get_text(" ", strip=True):
                review.append(
                    {"paragraph": ordinal, "reason": "Syntax paragraph has no recognized keyword style"}
                )
            continue
        syntax = _syntax(paragraph)
        if syntax:
            rows.append(
                _row(
                    syntax,
                    view,
                    H3C_SOURCE,
                    H3C_MANUAL,
                    path.name,
                    soup.title.get_text(" ", strip=True) if soup.title else "",
                )
            )
    return rows


def download(cache: Path, nid: str) -> ET.Element:
    tree_path = cache / f"{nid}-tree.xml"
    if not tree_path.exists():
        tree_path.write_bytes(_read("catalogue", nid))
    tree = fromstring(tree_path.read_bytes())

    def fetch(node: ET.Element) -> None:
        part = node.attrib["partNo"]
        target = cache / f"{nid}-{part}.html"
        if target.exists():
            return
        for attempt in range(3):
            try:
                target.write_bytes(_read("main-content", nid, part))
                return
            except OSError:
                if attempt == 2:
                    raise

    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(fetch, (node for node in tree.iter("file") if not list(node))))
    return tree


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vendor", choices=("h3c", "huawei"), required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--download", action="store_true")
    parser.add_argument(
        "--supplement", type=Path, help="Reviewed scoped chapter rows; never treated as semantic support"
    )
    args = parser.parse_args()
    args.input.mkdir(parents=True, exist_ok=True)
    entries: dict[str, dict[str, Any]] = {}
    inventory = []
    jobs = []
    if args.vendor == "huawei":
        for nid in HUAWEI_MANUALS:
            tree = (
                download(args.input, nid)
                if args.download
                else fromstring((args.input / f"{nid}-tree.xml").read_bytes())
            )
            for node in tree.iter("file"):
                if not list(node):
                    jobs.append(
                        (
                            args.input / f"{nid}-{node.attrib['partNo']}.html",
                            f"https://support.huawei.com/enterprise/en/doc/{nid}/{node.attrib['topicId']}",
                        )
                    )
    else:
        jobs = [(path, H3C_SOURCE) for path in sorted(args.input.rglob("*.htm"))]
    for path, source in jobs:
        review: list[dict[str, Any]] = []
        rows = huawei_rows(path, source) if args.vendor == "huawei" else h3c_rows(path, review)
        for row in rows:
            merge_row(entries, row, args.vendor)
        inventory.append(
            {
                "file": path.name,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "syntaxes": len(rows),
                "review_queue": review,
            }
        )
    if args.supplement:
        supplement = json.loads(args.supplement.read_text(encoding="utf-8"))
        if supplement.get("vendor") != args.vendor:
            raise ValueError("Supplement vendor mismatch")
        for row in supplement["commands"]:
            if not row.get("sources") or not all(value.get("manual") for value in row["sources"]):
                raise ValueError("Supplement requires scoped provenance")
            merge_row(entries, row, args.vendor)
    payload = {
        "schema": 2,
        "vendor": args.vendor,
        "manuals": list(HUAWEI_MANUALS.values()) if args.vendor == "huawei" else [H3C_MANUAL],
        "commands": sorted(entries.values(), key=lambda row: row["syntax"]),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.evidence.parent.mkdir(parents=True, exist_ok=True)
    args.evidence.write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"vendor": args.vendor, "pages": len(jobs), "syntaxes": len(entries)}))


if __name__ == "__main__":
    main()
