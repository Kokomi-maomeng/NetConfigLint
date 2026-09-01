import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import theme 1.0
import "../components"

AppCard {
    id: root
    property var diagnosticsModel
    property var detection: ({ "vendor": "Unknown", "os": "Unknown" })
    property var summary: ({ "ERROR": 0, "WARNING": 0, "INFO": 0, "UNKNOWN": 0 })
    signal issueActivated(int row)
    padding: 0

    ColumnLayout {
        anchors.fill: parent
        spacing: 0
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 96
            color: Colors.surfaceContainer
            radius: Spacing.radiusCard
            ColumnLayout {
                anchors.fill: parent
                anchors.margins: Spacing.sm
                spacing: Spacing.xs
                RowLayout {
                    Layout.fillWidth: true
                    SelectableText {
                        text: i18n.catalog["analysis.diagnostics"]
                        color: Colors.textPrimary
                        font: Typography.subtitle
                    }
                    Item { Layout.fillWidth: true }
                    ComboBox {
                        id: filterBox
                        model: [
                            { label: i18n.catalog["analysis.all"], value: "ALL" },
                            { label: i18n.catalog["analysis.error"], value: "ERROR" },
                            { label: i18n.catalog["analysis.warning"], value: "WARNING" },
                            { label: i18n.catalog["analysis.info"], value: "INFO" },
                            { label: i18n.catalog["analysis.unknown"], value: "UNKNOWN" }
                        ]
                        textRole: "label"
                        valueRole: "value"
                        Layout.preferredWidth: 116
                    }
                }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: Spacing.sm
                    SelectableText {
                        text: i18n.catalog["device.detected_vendor"] + ": "
                              + (root.detection.vendor || "Unknown")
                        color: Colors.textPrimary
                        font: Typography.label
                    }
                    Rectangle { width: 1; Layout.fillHeight: true; color: Colors.outlineVariant }
                    SelectableText {
                        text: i18n.catalog["device.os"] + ": " + (root.detection.os || "Unknown")
                        color: Colors.textSecondary
                        font: Typography.body
                    }
                    Item { Layout.fillWidth: true }
                }
            }
        }
        RowLayout {
            Layout.fillWidth: true
            Layout.margins: Spacing.sm
            spacing: Spacing.xs
            Repeater {
                model: ["ERROR", "WARNING", "INFO", "UNKNOWN"]
                delegate: StatusBadge {
                    required property string modelData
                    label: modelData + " " + (root.summary[modelData] || 0)
                    statusColor: Colors.severity(modelData)
                }
            }
        }
        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true
            IssueList {
                id: issueList
                anchors.fill: parent
                anchors.leftMargin: Spacing.sm
                anchors.rightMargin: Spacing.sm
                anchors.bottomMargin: Spacing.sm
                model: root.diagnosticsModel
                severityFilter: filterBox.currentValue
                onIssueActivated: row => root.issueActivated(row)
            }
            EmptyState {
                anchors.fill: parent
                visible: issueList.count === 0
                title: i18n.catalog["analysis.empty"]
                description: i18n.catalog["analysis.empty_detail"]
            }
        }
    }
}
