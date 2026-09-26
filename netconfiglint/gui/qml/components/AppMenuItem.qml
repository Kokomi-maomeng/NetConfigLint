import QtQuick
import QtQuick.Controls
import QtQuick.Controls.impl
import theme 1.0

MenuItem {
    id: control
    implicitHeight: 40
    hoverEnabled: true
    leftPadding: 12
    rightPadding: 12
    font: Typography.body
    icon.width: 20
    icon.height: 20
    icon.color: control.enabled ? Colors.textSecondary : Colors.outlineVariant
    contentItem: IconLabel {
        icon: control.icon
        text: control.text
        font: control.font
        display: AbstractButton.TextBesideIcon
        spacing: 12
        alignment: Qt.AlignLeft
        color: control.enabled ? Colors.textPrimary : Colors.textSecondary
    }
    background: Rectangle {
        radius: 10
        color: control.down ? Colors.surfaceContainerHighest
            : control.highlighted || control.hovered ? Colors.surfaceVariant : "transparent"
    }
}
