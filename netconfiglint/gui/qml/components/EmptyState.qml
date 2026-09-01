import QtQuick
import QtQuick.Layouts
import theme 1.0

ColumnLayout {
    property string title: "Nothing here yet"
    property string description: ""
    spacing: Spacing.xs
    Item { Layout.fillHeight: true }
    Rectangle {
        Layout.alignment: Qt.AlignHCenter
        width: 44; height: 44; radius: 22
        color: Colors.primaryContainer
        SelectableText { anchors.centerIn: parent; text: "—"; color: Colors.primary; font: Typography.title }
    }
    SelectableText {
        Layout.alignment: Qt.AlignHCenter
        text: parent.title
        color: Colors.textPrimary
        font: Typography.subtitle
    }
    SelectableText {
        Layout.alignment: Qt.AlignHCenter
        Layout.maximumWidth: 360
        text: parent.description
        color: Colors.textSecondary
        font: Typography.body
        horizontalAlignment: Text.AlignHCenter
        wrapMode: TextEdit.Wrap
    }
    Item { Layout.fillHeight: true }
}
