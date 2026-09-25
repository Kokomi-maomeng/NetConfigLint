from __future__ import annotations

import re
from typing import Any

from PySide6.QtCore import QObject, Slot
from PySide6.QtGui import QColor, QSyntaxHighlighter, QTextCharFormat, QTextDocument


class NetworkConfigHighlighter(QSyntaxHighlighter):
    """Huawei/H3C highlighter with source-mapped unsupported-line feedback."""

    _COMMAND_HEAD = re.compile(r"^\s*(?:<[^>]+>|\[[^]]+\])?\s*((?:undo\s+)?[A-Za-z][\w-]*)")
    _BLOCK = re.compile(
        r"^\s*(?:<[^>]+>|\[[^]]+\])?\s*(aaa|acl|arp|bfd|bgp|bridge-domain|clock|"
        r"display|dfs-group|domain|evpn|ftth|irf|irf-port(?:-configuration)?|"
        r"info-center|interface|ip vpn-instance|isis|line|local-user|m-lag|mpls|ntp(?:-service)?|"
        r"onu|ospf|role|route-policy|scheduler|security-enhanced|snmp-agent|stp|sysname|system-working-mode|"
        r"port group interface|reset|sys|system-view|tcsm|telemetry|"
        r"traffic (?:classifier|behavior|policy)|user-group|user-interface|"
        r"version|vlan(?: batch)?|vni|xbar|mdc)\b",
        re.IGNORECASE,
    )
    _KEYWORDS = re.compile(
        r"\b(access|active|address-family|area|authentication|authorization-attribute|behavior|bridge|"
        r"classifier|description|destination|dhcp|disable|edge(?:d-port)?|enable|eth-trunk|export|"
        r"filter|group|import|inbound|irf|l2vpn-family|lacp-static|link-aggregation|link-mode|"
        r"member|network|priority|renumber|persistent|"
        r"network-entity|outbound|peer|permit|deny|policy|route-distinguisher|route-policy|"
        r"server|service-type|shutdown|source|ssl|static|telnet|tls1\.[0123]|trunk|undo|user-role|"
        r"vpn-instance|vpn-target|vni|vxlan)\b",
        re.IGNORECASE,
    )
    _ADDRESS = re.compile(
        r"(?<![\w:])(?:\d{1,3}(?:\.\d{1,3}){3}(?:/\d{1,2})?|"
        r"[0-9a-f]{0,4}:[0-9a-f:]+(?:/\d{1,3})?)(?![\w:])",
        re.IGNORECASE,
    )
    _NUMBER = re.compile(r"(?<![\w./:])\d+(?:\.\d+)?(?![\w./:])")
    _QUOTED = re.compile(r"(?:\"(?:[^\"\\]|\\.)*\"|'(?:[^'\\]|\\.)*')")
    _SENSITIVE = re.compile(
        r"\b(password|cipher|community|pre-shared-key|secret|private-key)\b", re.IGNORECASE
    )
    _CURRENT_CONFIG_HEADER = re.compile(r"^\s*=+\s*display current-configuration\s*=+\s*$", re.IGNORECASE)
    _SECTION_BOUNDARY = re.compile(r"^\s*=+\s*$")
    _ANNOTATION = re.compile(r"^\s*(?:#|!|//|(?:说明|备注|注意)\s*[:：])")  # noqa: RUF001

    def __init__(self, document: QTextDocument, *, dark: bool = False) -> None:
        super().__init__(document)
        self._dark = dark
        self._unsupported_lines: set[int] = set()
        self._formats = self._make_formats()

    def _make_formats(self) -> dict[str, QTextCharFormat]:
        colors = {
            "keyword": "#9BCBFF" if self._dark else "#315F9B",
            "block": "#D3B8F6" if self._dark else "#71558E",
            "address": "#83D5A5" if self._dark else "#1B6D43",
            "number": "#E2BD82" if self._dark else "#8A5B17",
            "quoted": "#C5D98B" if self._dark else "#42691A",
            "section": "#8C9199" if self._dark else "#74777F",
            "sensitive": "#FFB4AB" if self._dark else "#BA1A1A",
            "unsupported": "#5B2020" if self._dark else "#FFF0EE",
        }
        formats = {}
        for name, color in colors.items():
            value = QTextCharFormat()
            if name == "unsupported":
                value.setBackground(QColor(color))
            else:
                value.setForeground(QColor(color))
            if name in {"block", "keyword", "sensitive"}:
                value.setFontWeight(600)
            formats[name] = value
        return formats

    def set_dark(self, dark: bool) -> None:
        if dark != self._dark:
            self._dark = dark
            self._formats = self._make_formats()
            self.rehighlight()

    def set_unsupported_lines(self, lines: set[int]) -> None:
        if lines != self._unsupported_lines:
            self._unsupported_lines = lines
            self.rehighlight()

    def highlightBlock(self, text: str) -> None:
        # Running every semantic regex over hundreds of thousands of operational
        # output lines blocks the GUI. In a large diagnostic bundle, keep the
        # highlighter source-mapped but restrict it to the current-config section.
        if self.document().characterCount() > 4_000_000:
            if self._CURRENT_CONFIG_HEADER.fullmatch(text):
                self.setCurrentBlockState(1)
                return
            if self.previousBlockState() == 1:
                if self._SECTION_BOUNDARY.fullmatch(text):
                    self.setCurrentBlockState(0)
                    return
                self.setCurrentBlockState(1)
            else:
                self.setCurrentBlockState(0)
                return
        offsets = [0]
        for character in text:
            offsets.append(offsets[-1] + (2 if ord(character) > 0xFFFF else 1))

        unsupported = self.currentBlock().blockNumber() + 1 in self._unsupported_lines

        def apply(start: int, end: int, kind: str) -> None:
            value = QTextCharFormat(self._formats[kind])
            if unsupported and kind != "unsupported":
                value.setBackground(self._formats["unsupported"].background())
            self.setFormat(offsets[start], offsets[end] - offsets[start], value)

        if unsupported:
            apply(0, len(text), "unsupported")
        if text.strip() in {"#", "return"}:
            apply(0, len(text), "section")
            return
        if self._ANNOTATION.match(text):
            apply(0, len(text), "section")
            return
        if match := self._COMMAND_HEAD.search(text):
            apply(match.start(1), match.end(1), "keyword")
        if match := self._BLOCK.search(text):
            apply(match.start(), match.end(), "block")
        for match in self._KEYWORDS.finditer(text):
            apply(match.start(), match.end(), "keyword")
        for match in self._ADDRESS.finditer(text):
            apply(match.start(), match.end(), "address")
        for match in self._NUMBER.finditer(text):
            apply(match.start(), match.end(), "number")
        for match in self._QUOTED.finditer(text):
            apply(match.start(), match.end(), "quoted")
        for match in self._SENSITIVE.finditer(text):
            apply(match.start(), match.end(), "sensitive")


HuaweiConfigHighlighter = NetworkConfigHighlighter


class SyntaxHighlighterBridge(QObject):
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._highlighters: list[NetworkConfigHighlighter] = []

    @Slot(QObject)
    def attach(self, value: QObject) -> None:
        document: Any = value
        if hasattr(value, "textDocument"):
            document = value.textDocument()
        if not isinstance(document, QTextDocument):
            return
        if any(item.document() is document for item in self._highlighters):
            return
        self._highlighters.append(NetworkConfigHighlighter(document))

    @Slot(bool)
    def setDark(self, dark: bool) -> None:
        for highlighter in self._highlighters:
            highlighter.set_dark(dark)

    @Slot(QObject, "QVariantList")
    def setUnsupportedLinesFor(self, document: QObject, lines: list[object]) -> None:
        parsed = {int(value) for value in lines if isinstance(value, int) and value > 0}
        for highlighter in self._highlighters:
            if highlighter.document() is document:
                highlighter.set_unsupported_lines(parsed)
                break
