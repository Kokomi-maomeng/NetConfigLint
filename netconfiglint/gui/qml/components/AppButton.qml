import QtQuick
import QtQuick.Controls
import theme 1.0

Button {
    id: control
    property bool prominent: false
    implicitHeight: 42
    implicitWidth: Math.max(64, contentItem.implicitWidth + leftPadding + rightPadding)
    topInset: 0
    bottomInset: 0
    leftPadding: Spacing.md
    rightPadding: Spacing.md
    font: Typography.label
    hoverEnabled: true
    opacity: enabled ? 1 : 0.38

    contentItem: Text {
        text: control.text
        font: control.font
        color: control.prominent ? Colors.primaryForeground : Colors.textPrimary
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }
    background: Rectangle {
        radius: 22
        color: control.prominent
               ? (control.down ? Qt.darker(Colors.primary, 1.12) : Colors.primary)
               : (control.hovered ? Colors.surfaceVariant : Colors.surfaceContainer)
        border.color: control.activeFocus ? Colors.primary : (control.prominent ? "transparent" : Colors.outlineVariant)
        border.width: control.activeFocus ? 2 : 1
        Behavior on color { ColorAnimation { duration: Theme.motionShort } }
    }
    scale: control.down ? 0.97 : 1
    Behavior on scale { NumberAnimation { duration: Theme.motionShort; easing.type: Easing.OutCubic } }
}
