from PySide6.QtGui import QTextDocument

from netconfiglint.gui.bridge import HuaweiConfigHighlighter, NetworkConfigHighlighter


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
