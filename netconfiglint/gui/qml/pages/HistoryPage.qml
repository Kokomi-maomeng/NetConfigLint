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
        RowLayout {
            Layout.fillWidth: true
            SelectableText {
                text: i18n.catalog["page.history"]
                color: Colors.textPrimary
                font: Typography.display
            }
            Item { Layout.fillWidth: true }
            AppButton {
                text: i18n.catalog["history.clear"]
                enabled: historyList.count > 0
                onClicked: root.controller.clearHistory()
            }
        }
        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: historyList.count === 0
            EmptyState {
                anchors.centerIn: parent
                width: Math.min(parent.width, 520)
                height: Math.min(parent.height, 300)
                title: root.controller.historyEnabled
                       ? i18n.catalog["history.empty"] : i18n.catalog["history.disabled"]
                description: root.controller.historyEnabled
                             ? "" : ""
            }
        }
        ListView {
            id: historyList
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: root.controller.historyEnabled && count > 0
            model: root.controller.historyModel
            spacing: Spacing.sm
            clip: true
            delegate: AppCard {
                required property string timestamp
                required property string mode
                required property string vendor
                required property int diagnosticCount
                required property int sourceLineCount
                required property var summary
                required property var ruleIds
                width: ListView.view.width
                implicitHeight: 92
                RowLayout {
                    anchors.fill: parent
                    ColumnLayout {
                        Layout.fillWidth: true
                        SelectableText { text: timestamp; color: Colors.textPrimary; font: Typography.label }
                        SelectableText {
                            text: vendor + " 路 " + mode
                            color: Colors.textSecondary
                            font: Typography.body
                        }
                        SelectableText {
                            text: ruleIds.join(", ")
                            color: Colors.textSecondary
                            font: Typography.caption
                            Layout.fillWidth: true
                        }
                    }
                    ColumnLayout {
                        SelectableText {
                            text: diagnosticCount + " " + i18n.catalog["history.issues"]
                            color: Colors.textPrimary
                            font: Typography.label
                        }
                        SelectableText {
                            text: sourceLineCount + " " + i18n.catalog["history.lines"]
                            color: Colors.textSecondary
                            font: Typography.caption
                        }
                    }
                }
            }
            ScrollBar.vertical: AppScrollBar { }
        }
    }
}
