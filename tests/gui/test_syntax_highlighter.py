from PySide6.QtGui import QTextDocument

from netconfiglint.gui.bridge import HuaweiConfigHighlighter


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
