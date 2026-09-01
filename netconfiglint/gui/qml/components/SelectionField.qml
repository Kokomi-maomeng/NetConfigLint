import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import theme 1.0

Button {
    id: control
    property string label: ""
    property string valueText: ""
    implicitWidth: 150
    implicitHeight: 48
    hoverEnabled: true
    Accessible.name: label + ": " + valueText

    contentItem: RowLayout {
        spacing: Spacing.sm
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 1
            Text {
                text: control.label
                color: Colors.textSecondary
                font: Typography.caption
            }
            Text {
                Layout.fillWidth: true
                text: control.valueText
                color: Colors.textPrimary
                font: Typography.label
                elide: Text.ElideRight
            }
        }
        Text {
            text: "⌄"
            color: Colors.primary
            font: Typography.subtitle
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
