pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import theme 1.0
import "../components"

AppCard {
    id: root
    property var diagnosticsModel
    property var detection: ({ "vendor": "Unknown", "os": "Unknown" })
    property var summary: ({ "ERROR": 0, "WARNING": 0, "INFO": 0, "UNKNOWN": 0 })
    property string severityFilter: "ALL"
    signal issueActivated(int row)
    padding: 0

    function totalCount() {
        return (summary.ERROR || 0) + (summary.WARNING || 0)
                + (summary.INFO || 0) + (summary.UNKNOWN || 0)
    }

    function filteredCount() {
        return severityFilter === "ALL" ? totalCount() : (summary[severityFilter] || 0)
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 126
            color: Colors.surfaceContainer
            radius: Spacing.radiusCard
            ColumnLayout {
                anchors.fill: parent
                anchors.margins: Spacing.md
                spacing: Spacing.xs
                RowLayout {
                    Layout.fillWidth: true
                    SelectableText {
                        text: i18n.catalog["analysis.diagnostics"]
                        color: Colors.textPrimary
                        font: Typography.subtitle
                    }
                    Item { Layout.fillWidth: true }
                    SelectableText {
                        text: root.severityFilter === "ALL"
                              ? i18n.catalog["analysis.showing_all"]
                              : i18n.catalog["analysis.filtering"] + " " + root.severityFilter
                        color: root.severityFilter === "ALL" ? Colors.textSecondary : Colors.primary
                        font: Typography.caption
                    }
                }
                GridLayout {
                    Layout.fillWidth: true
                    columns: 2
                    columnSpacing: Spacing.sm
                    rowSpacing: Spacing.xxs
                    SelectableText {
                        text: i18n.catalog["device.detected_vendor"]
                        color: Colors.textSecondary
                        font: Typography.caption
                    }
                    SelectableText {
                        Layout.fillWidth: true
                        text: root.detection.vendor || "Unknown"
                        color: Colors.textPrimary
                        font: Typography.label
                        wrapMode: TextEdit.NoWrap
                        clip: true
                    }
                    SelectableText {
                        text: i18n.catalog["device.os"]
                        color: Colors.textSecondary
                        font: Typography.caption
                    }
                    SelectableText {
                        Layout.fillWidth: true
                        text: root.detection.os || "Unknown"
                        color: Colors.textPrimary
                        font: Typography.label
                        wrapMode: TextEdit.NoWrap
                        clip: true
                    }
                }
            }
        }
        GridLayout {
            id: severityFilters
            Layout.fillWidth: true
            Layout.margins: Spacing.sm
            Layout.preferredHeight: columns === 4 ? 36 : 80
            columns: root.width >= 430 ? 4 : 2
            columnSpacing: Spacing.xs
            rowSpacing: Spacing.xs
            Repeater {
                model: ["ERROR", "WARNING", "INFO", "UNKNOWN"]
                delegate: StatusBadge {
                    required property string modelData
                    objectName: "severityFilter-" + modelData
                    Layout.fillWidth: true
                    label: modelData + " " + (root.summary[modelData] || 0)
                    statusColor: Colors.severity(modelData)
                    interactive: true
                    selected: root.severityFilter === modelData
                    onClicked: root.severityFilter = root.severityFilter === modelData ? "ALL" : modelData
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
                severityFilter: root.severityFilter
                onIssueActivated: row => root.issueActivated(row)
            }
            EmptyState {
                objectName: "analysisEmptyState"
                anchors.fill: parent
                visible: root.filteredCount() === 0
                title: root.totalCount() === 0
                       ? i18n.catalog["analysis.empty"] : i18n.catalog["analysis.filter_empty"]
                description: root.totalCount() === 0
                             ? i18n.catalog["analysis.empty_detail"]
                             : i18n.catalog["analysis.filter_empty_detail"]
            }
        }
    }
}
