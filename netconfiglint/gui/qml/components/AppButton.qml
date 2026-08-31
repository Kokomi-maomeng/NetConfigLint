import QtQuick
import QtQuick.Controls
import theme 1.0

Button {
    id: control
    property bool prominent: false
    implicitHeight: 38
    leftPadding: Spacing.md
    rightPadding: Spacing.md
    font: Typography.label
    hoverEnabled: true

    contentItem: Text {
        text: control.text
        font: control.font
        color: control.prominent ? Colors.onPrimary : Colors.textPrimary
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }
    background: Rectangle {
        radius: Spacing.radiusMedium
        color: control.prominent
               ? (control.down ? Qt.darker(Colors.primary, 1.12) : Colors.primary)
               : (control.hovered ? Colors.surfaceVariant : Colors.surfaceContainer)
        border.color: control.prominent ? "transparent" : Colors.outlineVariant
        Behavior on color { ColorAnimation { duration: 120 } }
    }
}
