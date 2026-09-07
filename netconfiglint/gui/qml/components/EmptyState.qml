import QtQuick
import QtQuick.Layouts
import theme 1.0
ColumnLayout {
    id: root
    property string title: ""
    property string description: ""
    spacing: Spacing.xs
    Item { Layout.fillHeight: true }
    SelectableText {
        Layout.fillWidth: true
        Layout.margins: Spacing.md
        text: root.title
        visible: text.length > 0
        horizontalAlignment: Text.AlignHCenter
        color: Colors.textSecondary
        font: Typography.body
    }
    SelectableText {
        Layout.fillWidth: true
        Layout.margins: Spacing.md
        text: root.description
        visible: text.length > 0
        color: Colors.textSecondary
        font: Typography.caption
        horizontalAlignment: Text.AlignHCenter
    }
    Item { Layout.fillHeight: true }
}
