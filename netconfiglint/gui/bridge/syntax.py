from __future__ import annotations

import re
from typing import Any

from PySide6.QtCore import QObject, Slot
from PySide6.QtGui import QColor, QSyntaxHighlighter, QTextCharFormat, QTextDocument


class HuaweiConfigHighlighter(QSyntaxHighlighter):
    """Block highlighter; Qt automatically re-highlights only changed text blocks."""

    _BLOCK = re.compile(
        r"^\s*(aaa|acl|bfd|bgp|bridge-domain|dfs-group|evpn|interface|ip vpn-instance|"
        r"isis|mpls|ntp(?:-service)?|ospf|route-policy|snmp-agent|stp|traffic "
        r"(?:classifier|behavior|policy)|user-interface|vlan(?: batch)?|vni)\b",
        re.IGNORECASE,
    )
    _KEYWORDS = re.compile(
        r"\b(address-family|area|authentication|behavior|classifier|description|destination|"
        r"dhcp|enable|eth-trunk|export|group|import|inbound|l2vpn-family|lacp-static|network|"
        r"network-entity|outbound|peer|permit|deny|policy|route-distinguisher|route-policy|"
        r"shutdown|source|static|undo|vpn-instance|vpn-target|vni|vxlan)\b",
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

    def __init__(self, document: QTextDocument, *, dark: bool = False) -> None:
        super().__init__(document)
        self._dark = dark
        self._formats = self._make_formats()

    def _make_formats(self) -> dict[str, QTextCharFormat]:
        colors = {
            "keyword": "#9BCBFF" if self._dark else "#315F9B",
            "block": "#D3B8F6" if self._dark else "#71558E",
            "address": "#83D5A5" if self._dark else "#1B6D43",
            "section": "#8C9199" if self._dark else "#74777F",
            "sensitive": "#FFB4AB" if self._dark else "#BA1A1A",
        }
        formats = {}
        for name, color in colors.items():
            value = QTextCharFormat()
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

    def highlightBlock(self, text: str) -> None:
        offsets = [0]
        for character in text:
            offsets.append(offsets[-1] + (2 if ord(character) > 0xFFFF else 1))

        def apply(start: int, end: int, kind: str) -> None:
            self.setFormat(offsets[start], offsets[end] - offsets[start], self._formats[kind])

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


class SyntaxHighlighterBridge(QObject):
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._highlighters: list[HuaweiConfigHighlighter] = []

    @Slot(QObject)
    def attach(self, value: QObject) -> None:
        document: Any = value
        if hasattr(value, "textDocument"):
            document = value.textDocument()
        if not isinstance(document, QTextDocument):
            return
        if any(item.document() is document for item in self._highlighters):
            return
        self._highlighters.append(HuaweiConfigHighlighter(document))

    @Slot(bool)
    def setDark(self, dark: bool) -> None:
        for highlighter in self._highlighters:
            highlighter.set_dark(dark)
