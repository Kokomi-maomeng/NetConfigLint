import QtQuick
import theme 1.0

Rectangle {
    id: root
    property string label: "INFO"
    property color statusColor: Colors.severity(label)
    implicitWidth: badgeText.implicitWidth + Spacing.sm * 2
    implicitHeight: 24
    radius: height / 2
    color: Qt.alpha(statusColor, 0.14)
    border.color: Qt.alpha(statusColor, 0.4)

    Text {
        id: badgeText
        anchors.centerIn: parent
        text: root.label
        color: root.statusColor
        font: Typography.caption
    }
}
