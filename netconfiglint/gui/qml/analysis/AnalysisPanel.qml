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
    property string resultTimestamp: ""
    property var summary: ({ ERROR: 0, WARNING: 0, INFO: 0, UNKNOWN: 0 })
    property string severityFilter: "ALL"
    property string statusKey: ""
    property bool resultCurrent: false
    property bool busy: false
    property var coverage: ({})
    property bool coverageExpanded: false
    signal pendingLineActivated(int line)
    signal cancelRequested()
    signal issueActivated(int row)
    signal dragStarted(real sceneX)
    signal dragMoved(real sceneX)
    signal dragFinished(real sceneX)
    signal stepRequested(int direction)
    padding: 0
    onResultCurrentChanged: severityFilter = "ALL"
    function pendingCount() { return (coverage.catalogued || 0) + (coverage.unparsed || 0) + (coverage.unsupported || 0) }
    function totalCount() { return (summary.ERROR || 0) + (summary.WARNING || 0) + (summary.INFO || 0) + (summary.UNKNOWN || 0) }
    function filteredCount() { return severityFilter === "ALL" ? totalCount() : (summary[severityFilter] || 0) }
    function catalogFamilies() {
        return (coverage.catalogued_families || []).map(function(item) {
            return (i18n.catalog["command.family." + item.family] || item.family) + ": " + item.count
        }).join(" · ")
    }
    ColumnLayout {
        anchors.fill: parent
        spacing: 0
        CardHeader {
            objectName: "diagnosticsHeader"
            Layout.fillWidth: true
            Layout.preferredHeight: 60
            title: i18n.catalog["analysis.diagnostics"]
            onDragStarted: sceneX => root.dragStarted(sceneX)
            onDragMoved: sceneX => root.dragMoved(sceneX)
            onDragFinished: sceneX => root.dragFinished(sceneX)
            onStepRequested: direction => root.stepRequested(direction)
        }
        ScrollView {
            id: metadataScroll
            objectName: "analysisMetadataScroll"
            Layout.fillWidth: true
            Layout.preferredHeight: Math.min(metadataColumn.implicitHeight, Math.max(80, root.height * 0.48))
            Layout.margins: 12
            clip: true
            ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
            ColumnLayout {
                id: metadataColumn
                width: metadataScroll.availableWidth
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
            AppButton {
                visible: root.busy
                text: i18n.catalog["analysis.cancel"]
                onClicked: root.cancelRequested()
            }
            Label {
                objectName: "coverageSummary"
                Layout.fillWidth: true
                visible: root.resultCurrent
                wrapMode: Text.Wrap
                font: Typography.caption
                color: root.pendingCount() ? Colors.warning : Colors.primary
                text: i18n.catalog["analysis.semantic_checked"] + ": " + (root.coverage.recognized || 0)
                      + " · " + i18n.catalog["analysis.catalogued"] + ": " + (root.coverage.catalogued || 0)
                      + " · " + i18n.catalog["analysis.pending"] + ": " + root.pendingCount()
            }
            AppButton {
                objectName: "coverageToggle"
                Layout.fillWidth: true
                visible: root.resultCurrent
                text: i18n.catalog["analysis.coverage"] + (root.coverageExpanded ? " ▴" : " ▾")
                onClicked: root.coverageExpanded = !root.coverageExpanded
            }
            AppButton {
                objectName: "pendingLinesButton"
                Layout.fillWidth: true
                visible: root.resultCurrent && root.pendingCount() > 0
                text: i18n.catalog["analysis.pending_list"] + " (" + root.pendingCount() + ")"
                onClicked: pendingDialog.open()
            }
            SelectableText {
                objectName: "coverageDetails"
                Layout.fillWidth: true
                visible: root.resultCurrent && root.coverageExpanded
                font: Typography.caption
                text: i18n.catalog["analysis.coverage_scope"] + "\n"
                      + i18n.catalog["analysis.semantic_checked"] + ": " + (root.coverage.recognized || 0) + "\n"
                      + i18n.catalog["analysis.catalogued"] + ": " + (root.coverage.catalogued || 0) + "\n"
                      + root.catalogFamilies() + (root.catalogFamilies() ? "\n" : "")
                      + i18n.catalog["analysis.unparsed"] + ": " + (root.coverage.unparsed || 0) + "\n"
                      + i18n.catalog["analysis.unsupported_lines"] + ": " + (root.coverage.unsupported || 0) + "\n"
                      + i18n.catalog["issue.line"] + ": "
                      + (root.coverage.unparsed_lines || []).concat(root.coverage.unsupported_lines || []).slice(0, 80).join(", ")
                      + (((root.coverage.unparsed || 0) + (root.coverage.unsupported || 0)) > 80 ? " …" : "")
            }
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
            SelectableText {
                objectName: "analysisTimestamp"
                Layout.fillWidth: true
                visible: root.resultCurrent && root.resultTimestamp.length > 0
                text: root.resultTimestamp
                color: Colors.textSecondary
                font: Typography.caption
            }
            Flow {
                objectName: "severityFilters"
                Layout.fillWidth: true
                Layout.preferredHeight: implicitHeight
                spacing: 4
                Repeater {
                    model: ["ERROR", "WARNING", "INFO", "UNKNOWN"]
                    delegate: StatusBadge {
                        required property string modelData
                        objectName: "severityFilter-" + modelData
                        width: implicitWidth
                        height: implicitHeight
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
        }
        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: Math.min(160, root.height * 0.28)
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
                title: root.totalCount() > 0 ? i18n.catalog["analysis.filter_empty"] : (root.resultCurrent ? (root.pendingCount() ? i18n.catalog["analysis.no_issues_pending"].replace("{count}", root.pendingCount()) : i18n.catalog["analysis.no_issues"]) : "")
            }
        }
    }
    AppDialog {
        id: pendingDialog
        objectName: "pendingLinesDialog"
        title: i18n.catalog["analysis.pending_list"]
        height: Math.min(550, root.Window.height - 60)
        contentItem: ListView {
            clip: true
            model: root.coverage.pending_line_details || []
            ScrollBar.vertical: AppScrollBar {}
            delegate: ItemDelegate {
                required property var modelData
                width: ListView.view.width
                text: i18n.catalog["issue.line"] + " " + modelData.line + " · " + (i18n.catalog["pending." + modelData.status] || modelData.status || "")
                onClicked: { root.pendingLineActivated(modelData.line); pendingDialog.close() }
            }
        }
    }
}
