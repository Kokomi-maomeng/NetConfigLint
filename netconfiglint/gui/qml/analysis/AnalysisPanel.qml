pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import theme 1.0
import "../components"
AppCard {
    id: root
    property var diagnosticsModel
    property var detection: ({ vendor: "Unknown" })
    property var summary: ({ ERROR: 0, WARNING: 0, INFO: 0, UNKNOWN: 0 })
    property string severityFilter: "ALL"
    property string statusKey: ""
    property bool resultCurrent: false
    property bool busy: false
    signal issueActivated(int row)
    signal dragStarted()
    signal dragMoved(real sceneX)
    signal dragFinished(real sceneX)
    signal stepRequested(int direction)
    padding: 0
    onResultCurrentChanged: severityFilter = "ALL"
    function totalCount() { return (summary.ERROR || 0) + (summary.WARNING || 0) + (summary.INFO || 0) + (summary.UNKNOWN || 0) }
    function filteredCount() { return severityFilter === "ALL" ? totalCount() : (summary[severityFilter] || 0) }
    ColumnLayout {
        anchors.fill: parent
        spacing: 0
        CardHeader {
            objectName: "diagnosticsHeader"
            Layout.fillWidth: true
            Layout.preferredHeight: 60
            title: i18n.catalog["analysis.diagnostics"]
            onDragStarted: root.dragStarted()
            onDragMoved: sceneX => root.dragMoved(sceneX)
            onDragFinished: sceneX => root.dragFinished(sceneX)
            onStepRequested: direction => root.stepRequested(direction)
        }
        ColumnLayout {
            Layout.fillWidth: true
            Layout.margins: 12
            spacing: 8
            SelectableText {
                objectName: "analysisStatus"
                Layout.fillWidth: true
                visible: root.statusKey.length > 0
                text: i18n.catalog[root.statusKey] || ""
                color: root.statusKey === "analysis.failed" || root.statusKey === "analysis.unsupported" ? Colors.error : Colors.primary
                font: Typography.caption
            }
            ProgressBar { Layout.fillWidth: true; visible: root.busy; indeterminate: root.busy }
            RowLayout {
                Layout.fillWidth: true
                visible: root.resultCurrent
                SelectableText { text: i18n.catalog["device.detected_vendor"]; color: Colors.textSecondary; font: Typography.caption }
                SelectableText {
                    Layout.fillWidth: true
                    text: i18n.catalog["vendor." + String(root.detection.vendor).toLowerCase()] || root.detection.vendor || i18n.catalog["analysis.unknown"]
                    font: Typography.label
                }
            }
            GridLayout {
                Layout.fillWidth: true
                columns: root.width >= 470 ? 4 : 2
                columnSpacing: 6
                rowSpacing: 6
                Repeater {
                    model: ["ERROR", "WARNING", "INFO", "UNKNOWN"]
                    delegate: StatusBadge {
                        required property string modelData
                        objectName: "severityFilter-" + modelData
                        Layout.fillWidth: true
                        label: i18n.catalog["analysis." + modelData.toLowerCase()] + " " + (root.summary[modelData] || 0)
                        statusColor: Colors.severity(modelData)
                        interactive: true
                        selected: root.severityFilter === modelData
                        onClicked: root.severityFilter = root.severityFilter === modelData ? "ALL" : modelData
                    }
                }
            }
            SelectableText {
                objectName: "activeSeverityFilter"
                Layout.fillWidth: true
                visible: root.severityFilter !== "ALL"
                text: i18n.catalog["analysis.filtering"] + " " + (i18n.catalog["analysis." + root.severityFilter.toLowerCase()] || "")
                color: Colors.primary
                font: Typography.caption
            }
        }
        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true
            IssueList {
                anchors.fill: parent
                anchors.margins: 12
                model: root.diagnosticsModel
                severityFilter: root.severityFilter
                onIssueActivated: row => root.issueActivated(row)
            }
            EmptyState {
                objectName: "analysisEmptyState"
                anchors.fill: parent
                visible: root.filteredCount() === 0
                title: root.totalCount() > 0 ? i18n.catalog["analysis.filter_empty"] : (root.resultCurrent ? i18n.catalog["analysis.no_issues"] : "")
            }
        }
    }
}
