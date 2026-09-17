from __future__ import annotations

import re
from typing import Any

from PySide6.QtCore import QObject, Slot
from PySide6.QtGui import QColor, QSyntaxHighlighter, QTextCharFormat, QTextDocument


class NetworkConfigHighlighter(QSyntaxHighlighter):
    """Huawei/H3C highlighter with source-mapped unsupported-line feedback."""

    _BLOCK = re.compile(
        r"^\s*(aaa|acl|arp|bfd|bgp|bridge-domain|clock|dfs-group|domain|evpn|ftth|"
        r"info-center|interface|ip vpn-instance|isis|line|local-user|m-lag|mpls|ntp(?:-service)?|"
        r"onu|ospf|role|route-policy|scheduler|security-enhanced|snmp-agent|stp|sysname|system-working-mode|"
        r"tcsm|telemetry|traffic (?:classifier|behavior|policy)|user-group|user-interface|"
        r"version|vlan(?: batch)?|vni|xbar|mdc)\b",
        re.IGNORECASE,
    )
    _KEYWORDS = re.compile(
        r"\b(access|address-family|area|authentication|authorization-attribute|behavior|bridge|"
        r"classifier|description|destination|dhcp|disable|edge(?:d-port)?|enable|eth-trunk|export|"
        r"filter|group|import|inbound|l2vpn-family|lacp-static|link-aggregation|link-mode|network|"
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
    _SENSITIVE = re.compile(
        r"\b(password|cipher|community|pre-shared-key|secret|private-key)\b", re.IGNORECASE
    )
    _CURRENT_CONFIG_HEADER = re.compile(r"^\s*=+\s*display current-configuration\s*=+\s*$", re.IGNORECASE)
    _SECTION_BOUNDARY = re.compile(r"^\s*=+\s*$")

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

        def apply(start: int, end: int, kind: str) -> None:
            self.setFormat(offsets[start], offsets[end] - offsets[start], self._formats[kind])

        if self.currentBlock().blockNumber() + 1 in self._unsupported_lines:
            apply(0, len(text), "unsupported")
        if text.strip() in {"#", "return"}:
            apply(0, len(text), "section")
            return
        if match := self._BLOCK.search(text):
            apply(match.start(), match.end(), "block")
        for match in self._KEYWORDS.finditer(text):
            apply(match.start(), match.end(), "keyword")
        for match in self._ADDRESS.finditer(text):
            apply(match.start(), match.end(), "address")
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

    @Slot("QVariantList")
    def setUnsupportedLines(self, lines: list[object]) -> None:
        parsed = {int(value) for value in lines if isinstance(value, int) and value > 0}
        for highlighter in self._highlighters:
            highlighter.set_unsupported_lines(parsed)
