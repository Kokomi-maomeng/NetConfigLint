from __future__ import annotations

import re
from bisect import bisect_right
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QObject, QTimer, Slot
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
        r"member|network|priority|renumber|persistent|mode|mstp|rstp|global|sys-info|version|v1|v2c|v3|"
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
    _ANNOTATION = re.compile(r"^\s*(?:#|!|//|(?:说明|备注|注意)\s*[:：])")  # noqa: RUF001
    _DESCRIPTION = re.compile(r"^\s*(?:<[^>]+>|\[[^]]+\])?\s*(?:undo\s+)?description\b", re.I)
    _SECURITY_COMMAND = re.compile(
        r"^\s*(?:<[^>]+>|\[[^]]+\])?\s*(?:undo\s+)?"
        r"(?:password|local-user|snmp-agent|authentication|radius|radius-server|hwtacacs|"
        r"tacacs-server|ike|ipsec|pre-shared-key|keychain|key|secret|private-key|"
        r"peer\s+\S+\s+password)\b",
        re.I,
    )

    def __init__(self, document: QTextDocument, *, dark: bool = False) -> None:
        super().__init__(document)
        self._dark = dark
        self._unsupported_lines: set[int] = set()
        self._diagnostics: dict[int, dict[str, Any]] = {}
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
            "error": "#5B2020" if self._dark else "#FFF0EE",
            "warning": "#514022" if self._dark else "#FFF4DA",
            "notice": "#243F58" if self._dark else "#EAF2FF",
        }
        formats = {}
        for name, color in colors.items():
            value = QTextCharFormat()
            if name in {"unsupported", "error", "warning", "notice"}:
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

    def set_diagnostics(self, diagnostics: dict[int, dict[str, Any]]) -> None:
        if diagnostics != self._diagnostics:
            self._diagnostics = diagnostics
            self.rehighlight()

    def highlightBlock(self, text: str) -> None:
        # Running every semantic regex over hundreds of thousands of operational
        # output lines blocks the GUI. In a large diagnostic bundle, keep the
        # highlighter source-mapped but restrict it to the current-config section.
        if self.document().characterCount() > 250_000:
            # Large text stays fully editable/searchable; skip costly full-document coloring.
            self.setCurrentBlockState(0)
            return
        offsets = [0]
        for character in text:
            offsets.append(offsets[-1] + (2 if ord(character) > 0xFFFF else 1))

        unsupported = self.currentBlock().blockNumber() + 1 in self._unsupported_lines
        diagnostic = self._diagnostics.get(self.currentBlock().blockNumber() + 1)
        severity = str(diagnostic.get("severity", "notice")).lower() if diagnostic else ""
        decoration = "error" if severity == "error" else "warning" if severity == "warning" else "notice"

        def apply(start: int, end: int, kind: str) -> None:
            value = QTextCharFormat(self._formats[kind])
            if unsupported and kind != "unsupported":
                value.setBackground(self._formats["unsupported"].background())
            if diagnostic:
                value.setBackground(self._formats[decoration].background())
            self.setFormat(offsets[start], offsets[end] - offsets[start], value)

        if unsupported:
            apply(0, len(text), "unsupported")
        if diagnostic:
            apply(0, len(text), decoration)
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
        if match := self._DESCRIPTION.match(text):
            apply(match.end(), len(text), "quoted")
            return
        quoted = list(self._QUOTED.finditer(text))

        def in_quote(match: re.Match[str]) -> bool:
            return any(match.start() < span.end() and match.end() > span.start() for span in quoted)

        for match in self._KEYWORDS.finditer(text):
            if not in_quote(match):
                apply(match.start(), match.end(), "keyword")
        for match in self._ADDRESS.finditer(text):
            if not in_quote(match):
                apply(match.start(), match.end(), "address")
        for match in self._NUMBER.finditer(text):
            if not in_quote(match):
                apply(match.start(), match.end(), "number")
        for match in quoted:
            apply(match.start(), match.end(), "quoted")
        if self._SECURITY_COMMAND.match(text):
            for match in self._SENSITIVE.finditer(text):
                if not in_quote(match):
                    apply(match.start(), match.end(), "sensitive")
        if diagnostic and isinstance(diagnostic.get("column"), int):
            start = max(0, min(len(text), diagnostic["column"] - 1))
            length = diagnostic.get("length")
            if not isinstance(length, int):
                end_column = diagnostic.get("end_column")
                length = max(1, end_column - diagnostic["column"] + 1) if isinstance(end_column, int) else 1
            end = min(len(text), start + max(1, length))
            for index in range(start, end):
                value = self.format(offsets[index])
                value.setUnderlineStyle(QTextCharFormat.UnderlineStyle.WaveUnderline)
                value.setUnderlineColor(QColor("#FFB4AB" if self._dark else "#BA1A1A"))
                self.setFormat(offsets[index], offsets[index + 1] - offsets[index], value)


HuaweiConfigHighlighter = NetworkConfigHighlighter


@dataclass
class _TextPreview:
    text: str
    ranges: list[tuple[int, int, int]]
    total_lines: int
    page: int = 0

    @classmethod
    def create(cls, text: str) -> _TextPreview:
        ranges = []
        start, line = 0, 1
        while start < len(text):
            end = min(len(text), start + 50_000)
            if end < len(text):
                boundary = text.find("\n", end, min(len(text), end + 32_768))
                if boundary >= 0:
                    end = boundary + 1
            ranges.append((start, end, line))
            line += text.count("\n", start, end)
            start = end
        return cls(text, ranges, line)

    def visible_text(self) -> str:
        start, end, _ = self.ranges[self.page]
        return self.text[start:end]

    def replace_visible(self, text: str) -> None:
        start, end, line = self.ranges[self.page]
        previous = self.text[start:end]
        if text == previous:
            return
        self.text = self.text[:start] + text + self.text[end:]
        delta = len(text) - len(previous)
        line_delta = text.count("\n") - previous.count("\n")
        self.ranges[self.page] = (start, end + delta, line)
        for index in range(self.page + 1, len(self.ranges)):
            first, last, first_line = self.ranges[index]
            self.ranges[index] = (first + delta, last + delta, first_line + line_delta)
        self.total_lines += line_delta


class SyntaxHighlighterBridge(QObject):
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._highlighters: list[NetworkConfigHighlighter] = []
        self._document_proxies: list[QObject] = []
        self._previews: dict[QObject, _TextPreview] = {}

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
        self._document_proxies.append(value)

    @Slot(QObject, str, QObject, result=str)
    def prepareText(self, value: QObject | None, text: str, editor: QObject | None) -> str:
        """Bound native text layout; the complete source stays in the analysis controller."""
        large = len(text) > 250_000
        if editor is not None:
            # The returned page is applied by the QML binding after this call.
            existing = self._previews.get(editor)
            current = existing.text if existing is not None else str(editor.property("text") or "")
            if current != text:
                editor.setProperty("previewLoading", True)
                QTimer.singleShot(0, editor, lambda: editor.setProperty("previewLoading", False))
            editor.setProperty("pagedPreview", large)
        if editor is None:
            return text
        if not large:
            self._previews.pop(editor, None)
            editor.setProperty("previewPage", 1)
            editor.setProperty("previewPageCount", 1)
            editor.setProperty("previewStartLine", 1)
            editor.setProperty("previewTotalLines", text.count("\n") + 1)
            return text
        preview = self._previews.get(editor)
        if preview is None:
            editor.destroyed.connect(lambda: self._previews.pop(editor, None))
        if preview is None or preview.text != text:
            preview = _TextPreview.create(text)
            self._previews[editor] = preview
        self._set_preview_metadata(editor, preview)
        return preview.visible_text()

    @staticmethod
    def _set_preview_metadata(editor: QObject, preview: _TextPreview) -> None:
        editor.setProperty("previewPage", preview.page + 1)
        editor.setProperty("previewPageCount", len(preview.ranges))
        editor.setProperty("previewStartLine", preview.ranges[preview.page][2])
        editor.setProperty("previewTotalLines", preview.total_lines)

    @Slot(QObject, int)
    def stepPreviewPage(self, editor: QObject, delta: int) -> None:
        preview = self._previews.get(editor)
        if preview is None:
            return
        preview.page = max(0, min(len(preview.ranges) - 1, preview.page + delta))
        self._show_preview(editor, preview)

    def _show_preview(self, editor: QObject, preview: _TextPreview) -> None:
        editor.setProperty("previewLoading", True)
        self._set_preview_metadata(editor, preview)
        editor.setProperty("text", preview.visible_text())
        editor.setProperty("previewLoading", False)

    @Slot(QObject, int, result=int)
    def lineInPreview(self, editor: QObject, line: int) -> int:
        preview = self._previews.get(editor)
        if preview is None:
            return line
        line = max(1, min(preview.total_lines, line))
        position = 0
        for _ in range(line - 1):
            position = preview.text.find("\n", position) + 1
        # A user can remove the page's boundary newline. Locate the actual
        # global line beginning, rather than choosing a continuation page.
        preview.page = max(0, bisect_right([row[0] for row in preview.ranges], position) - 1)
        self._show_preview(editor, preview)
        return line - preview.ranges[preview.page][2] + 1

    @Slot(QObject, str, result=str)
    def commitPreviewText(self, editor: QObject, text: str) -> str:
        """Immediately splice edits into the complete source, retaining page-local undo."""
        preview = self._previews.get(editor)
        if preview is None:
            return text
        preview.replace_visible(text)
        self._set_preview_metadata(editor, preview)
        return preview.text

    @Slot(QObject, int, result=int)
    def globalPosition(self, editor: QObject, position: int) -> int:
        preview = self._previews.get(editor)
        prefix = preview.text[: preview.ranges[preview.page][0]] if preview is not None else ""
        return len(prefix.encode("utf-16-le")) // 2 + position

    @Slot(QObject, int, result=int)
    def positionInPreview(self, editor: QObject, position: int) -> int:
        preview = self._previews.get(editor)
        if preview is None:
            return position
        # QML TextEdit and JS string positions are UTF-16 offsets; Python strings are code points.
        encoded = preview.text.encode("utf-16-le")
        safe = max(0, min(len(encoded) // 2, position))
        character = len(encoded[: safe * 2].decode("utf-16-le", errors="ignore"))
        preview.page = max(0, bisect_right([row[0] for row in preview.ranges], character) - 1)
        self._show_preview(editor, preview)
        prefix = preview.text[: preview.ranges[preview.page][0]]
        return safe - len(prefix.encode("utf-16-le")) // 2

    @Slot(QObject, result=str)
    def fullText(self, editor: QObject) -> str:
        preview = self._previews.get(editor)
        return preview.text if preview is not None else str(editor.property("text"))

    @Slot(bool)
    def setDark(self, dark: bool) -> None:
        for highlighter in self._highlighters:
            highlighter.set_dark(dark)

    @Slot(QObject, "QVariantList")
    @Slot(QObject, "QVariantList", int)
    def setUnsupportedLinesFor(self, document: QObject, lines: list[object], start_line: int = 1) -> None:
        parsed = {value - start_line + 1 for value in lines if isinstance(value, int) and value >= start_line}
        for highlighter, proxy in zip(self._highlighters, self._document_proxies, strict=True):
            if proxy is document or highlighter.document() is document:
                highlighter.set_unsupported_lines(parsed)
                break

    @Slot(QObject, "QVariantList", int)
    def setDiagnosticMarkersFor(self, document: QObject, markers: list[object], start_line: int) -> None:
        parsed: dict[int, dict[str, Any]] = {}
        for marker in markers:
            if not isinstance(marker, dict) or not isinstance(marker.get("line"), int):
                continue
            local_line = marker["line"] - start_line + 1
            if local_line < 1:
                continue
            existing = parsed.get(local_line)
            if existing is None or marker.get("severity", "").lower() == "error":
                parsed[local_line] = marker
        for highlighter, proxy in zip(self._highlighters, self._document_proxies, strict=True):
            if proxy is document or highlighter.document() is document:
                highlighter.set_diagnostics(parsed)
                break
