import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import theme 1.0
import "../components"

Item {
    id: root
    property var controller
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Spacing.lg
        spacing: Spacing.md
        Text { text: "Rule Library"; color: Colors.textPrimary; font: Typography.display }
        Text {
            text: "Huawei VRP beta rules currently registered in the shared analysis engine."
            color: Colors.textSecondary
            font: Typography.body
        }
        ListView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: Spacing.xs
            clip: true
            model: root.controller.ruleCatalog
            delegate: AppCard {
                required property var modelData
                width: ListView.view.width
                implicitHeight: 64
                RowLayout {
                    anchors.fill: parent
                    StatusBadge { label: modelData.severity }
                    ColumnLayout {
                        Layout.fillWidth: true
                        Text { text: modelData.ruleId; color: Colors.textPrimary; font: Typography.label }
                        Text { text: modelData.title; color: Colors.textSecondary; font: Typography.body }
                    }
                    Text { text: modelData.vendor; color: Colors.textSecondary; font: Typography.caption }
                }
            }
            ScrollBar.vertical: ScrollBar { }
        }
    }
}
