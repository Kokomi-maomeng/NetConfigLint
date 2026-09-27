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
    icon.color: control.enabled ? Colors.textPrimary : Colors.textDisabled
    scale: control.enabled && control.down ? 0.985 : 1
    Behavior on scale { NumberAnimation { duration: Theme.motionShort; easing.type: Easing.OutCubic } }
    contentItem: IconLabel {
        icon: control.icon
        text: control.text
        font: control.font
        display: AbstractButton.TextBesideIcon
        spacing: 12
        alignment: Qt.AlignLeft
        color: control.enabled ? Colors.textPrimary : Colors.textDisabled
    }
    background: Rectangle {
        radius: 10
        color: "transparent"
        Rectangle {
            objectName: "menuItemHoverOverlay"
            anchors.fill: parent
            radius: parent.radius
            color: control.down
                ? Qt.tint(Colors.surfaceContainerHigh, Qt.alpha(Colors.textPrimary, Theme.dark ? 0.24 : 0.18))
                : Qt.tint(Colors.surfaceContainerHigh, Qt.alpha(Colors.textPrimary, Theme.dark ? 0.14 : 0.11))
            opacity: control.enabled && (control.hovered || control.down) ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: Theme.motionShort; easing.type: Easing.OutCubic } }
            Behavior on color { ColorAnimation { duration: Theme.motionShort; easing.type: Easing.OutCubic } }
        }
    }
}
