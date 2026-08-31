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
            Text { text: i18n.catalog["page.history"]; color: Colors.textPrimary; font: Typography.display }
            Item { Layout.fillWidth: true }
            AppButton {
                text: i18n.catalog["history.clear"]
                enabled: historyList.count > 0
                onClicked: root.controller.clearHistory()
            }
        }
        EmptyState {
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: !root.controller.historyEnabled
            title: i18n.catalog["history.disabled"]
            description: i18n.catalog["history.disabled_detail"]
        }
        EmptyState {
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: root.controller.historyEnabled && historyList.count === 0
            title: i18n.catalog["history.empty"]
            description: i18n.catalog["history.empty_detail"]
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
                required property string platform
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
                        Text { text: timestamp; color: Colors.textPrimary; font: Typography.label }
                        Text {
                            text: vendor + " · " + platform + " · " + mode
                            color: Colors.textSecondary
                            font: Typography.body
                        }
                        Text {
                            text: ruleIds.join(", ")
                            color: Colors.textSecondary
                            font: Typography.caption
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }
                    }
                    ColumnLayout {
                        Text {
                            text: diagnosticCount + " " + i18n.catalog["history.issues"]
                            color: Colors.textPrimary
                            font: Typography.label
                        }
                        Text {
                            text: sourceLineCount + " " + i18n.catalog["history.lines"]
                            color: Colors.textSecondary
                            font: Typography.caption
                        }
                    }
                }
            }
            ScrollBar.vertical: ScrollBar { }
        }
    }
}
