import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import theme 1.0

AppDialog {
    id: root
    property var options: []
    property string selectedValue: ""
    signal valueSelected(string value)
    width: Math.min(520, parent ? parent.width - Spacing.xl * 2 : 520)

    contentItem: ColumnLayout {
        spacing: Spacing.sm
        Repeater {
            model: root.options
            delegate: Button {
                id: optionButton
                required property var modelData
                Accessible.name: modelData.label + ". " + (modelData.description || "")
                Layout.fillWidth: true
                implicitHeight: optionContent.implicitHeight + Spacing.md * 2
                hoverEnabled: true
                onClicked: {
                    root.valueSelected(optionButton.modelData.value)
                    root.close()
                }
                contentItem: ColumnLayout {
                    id: optionContent
                    spacing: Spacing.xxs
                    Text {
                        Layout.fillWidth: true
                        text: optionButton.modelData.label
                        color: optionButton.modelData.value === root.selectedValue ? Colors.primary : Colors.textPrimary
                        font: Typography.subtitle
                    }
                    Text {
                        Layout.fillWidth: true
                        text: optionButton.modelData.description || ""
                        color: Colors.textSecondary
                        font: Typography.body
                        wrapMode: Text.Wrap
                    }
                }
                background: Rectangle {
                    radius: Spacing.radiusLarge
                    color: optionButton.modelData.value === root.selectedValue
                           ? Colors.primaryContainer
                           : (optionButton.hovered ? Colors.surfaceContainerHigh : Colors.surfaceContainer)
                    border.color: optionButton.modelData.value === root.selectedValue ? Colors.primary : Colors.outlineVariant
                    Behavior on color { ColorAnimation { duration: 130 } }
                }
            }
        }
    }
}
