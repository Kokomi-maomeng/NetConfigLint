pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import theme 1.0

AppDialog {
    id: root
    property var options: []
    property string selectedValue: ""
    property string optionObjectPrefix: "selectionOption-"
    signal valueSelected(string value)

    contentItem: ColumnLayout {
        spacing: Spacing.md
        Repeater {
            model: root.options
            delegate: Button {
                id: optionButton
                required property var modelData
                objectName: root.optionObjectPrefix + modelData.value
                Accessible.name: modelData.label + ". " + (modelData.description || "")
                Layout.fillWidth: true
                implicitHeight: Math.max(52, optionContent.implicitHeight + Spacing.sm * 2)
                hoverEnabled: true
                topInset: 0
                bottomInset: 0
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
                        visible: text.length > 0
                        color: Colors.textSecondary
                        font: Typography.body
                        wrapMode: Text.Wrap
                    }
                }
                background: Rectangle {
                    radius: Spacing.radiusLarge
                    color: optionButton.modelData.value === root.selectedValue
                           ? Qt.alpha(Colors.primaryContainer, 0.88)
                           : (optionButton.hovered ? Colors.surfaceContainerHigh : Colors.surfaceContainer)
                    border.color: optionButton.modelData.value === root.selectedValue ? Colors.primary : Colors.outlineVariant
                    border.width: optionButton.modelData.value === root.selectedValue ? 2 : 1
                    Behavior on color { ColorAnimation { duration: 130 } }
                }
            }
        }
    }
}
