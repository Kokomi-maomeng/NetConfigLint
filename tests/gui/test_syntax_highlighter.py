from PySide6.QtCore import QObject
from PySide6.QtGui import QTextDocument

from netconfiglint.gui.app.main import create_engine
from netconfiglint.gui.bridge import (
    HuaweiConfigHighlighter,
    NetworkConfigHighlighter,
    SyntaxHighlighterBridge,
)
from netconfiglint.gui.controllers import AnalysisController


def test_huawei_syntax_highlighter_formats_incremental_blocks(qapp: object) -> None:
    document = QTextDocument("interface Vlanif10\n ip address 192.0.2.1 255.255.255.0")
    highlighter = HuaweiConfigHighlighter(document)
    highlighter.rehighlight()

    assert document.firstBlock().layout().formats()
    second = document.findBlockByNumber(1)
    assert second.layout().formats()

    document.setPlainText("bgp 65000\n peer 2001:db8::2 as-number 65001")
    highlighter.rehighlight()
    assert document.firstBlock().layout().formats()

    document.setPlainText("bridge-domain 100\n vxlan vni 50100\n password simple SYNTHETIC")
    highlighter.rehighlight()
    assert document.firstBlock().layout().formats()
    assert document.findBlockByNumber(1).layout().formats()
    assert document.findBlockByNumber(2).layout().formats()


def test_h3c_keywords_and_unsupported_lines_are_highlighted(qapp: object) -> None:
    document = QTextDocument(
        "interface GigabitEthernet1/0/1\n port link-mode bridge\n port access vlan 58\n"
        " arp filter source 192.0.2.1\nundo ssl version tls1.0 disable"
    )
    highlighter = NetworkConfigHighlighter(document)
    highlighter.set_unsupported_lines({4})
    highlighter.rehighlight()

    assert all(document.findBlockByNumber(index).layout().formats() for index in range(5))
    unsupported = document.findBlockByNumber(3).layout().formats()
    assert any(item.format.background().color().isValid() for item in unsupported)


def test_both_live_editors_rehighlight_irf_while_typing(qapp: object) -> None:
    controller = AnalysisController(async_enabled=False)
    engine = create_engine(controller)
    window = engine.rootObjects()[0]
    bridge = engine.rootContext().contextProperty("syntaxHighlighter")
    assert len(bridge._highlighters) == 2
    controller.sourceText = "irf-port 1/1\n port group interface Ten-GigabitEthernet1/0/1"
    temporary = window.findChild(QObject, "temporaryTextArea")
    assert temporary is not None
    temporary.setProperty("text", "sys\nirf member 1 priority 32")
    for highlighter in bridge._highlighters:
        document = highlighter.document()
        assert document.firstBlock().layout().formats()
    window.close()
    controller.close()


def test_unsupported_line_feedback_only_marks_source_editor(qapp: object) -> None:
    source = QTextDocument("unknown command")
    temporary = QTextDocument("unknown command")
    bridge = SyntaxHighlighterBridge()
    bridge.attach(source)
    bridge.attach(temporary)
    bridge.setUnsupportedLinesFor(source, [1])
    marked = source.firstBlock().layout().formats()
    unmarked = temporary.firstBlock().layout().formats()
    assert any(item.format.background().color().isValid() for item in marked)
    assert not any(item.format.background().color().isValid() for item in unmarked)
