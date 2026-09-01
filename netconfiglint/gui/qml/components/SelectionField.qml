import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import theme 1.0

Button {
    id: control
    property string label: ""
    property string valueText: ""
    implicitWidth: 174
    implicitHeight: 52
    hoverEnabled: true
    clip: true
    Accessible.name: label + ": " + valueText

    contentItem: ColumnLayout {
        spacing: 1
        Text {
            Layout.fillWidth: true
            text: control.label
            color: Colors.textSecondary
            font: Typography.caption
            elide: Text.ElideRight
        }
        Text {
            Layout.fillWidth: true
            text: control.valueText
            color: Colors.textPrimary
            font: Typography.label
            elide: Text.ElideRight
        }
    }
    background: Rectangle {
        radius: Spacing.radiusMedium
        color: control.down ? Colors.primaryContainer
                            : (control.hovered ? Colors.surfaceVariant : Colors.surfaceContainer)
        border.color: control.activeFocus ? Colors.primary : Colors.outlineVariant
        border.width: control.activeFocus ? 2 : 1
        Behavior on color { ColorAnimation { duration: 120 } }
        Behavior on border.color { ColorAnimation { duration: 120 } }
    }
    scale: control.down ? 0.98 : 1
    Behavior on scale { NumberAnimation { duration: 90; easing.type: Easing.OutCubic } }
}
