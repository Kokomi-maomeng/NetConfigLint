import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Layouts
import theme 1.0
import "../analysis"
import "../components"
import "../config"

Item {
    id: root
    property var controller

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Spacing.md
        spacing: Spacing.sm

        RowLayout {
            Layout.fillWidth: true
            Text { text: "Configuration Check"; color: Colors.textPrimary; font: Typography.display }
            Item { Layout.fillWidth: true }
            Text {
                text: root.controller.fileName
                color: Colors.textSecondary
                font: Typography.caption
                elide: Text.ElideMiddle
            }
        }
        ConfigToolbar {
            Layout.fillWidth: true
            mode: root.controller.mode
            vendor: root.controller.vendor
            busy: root.controller.busy
            onOpenRequested: openDialog.open()
            onPasteRequested: configEditor.editor.paste()
            onAnalyzeRequested: root.controller.analyzeConfig()
            onClearRequested: root.controller.clear()
            onExportRequested: exportDialog.open()
            onModeSelected: value => root.controller.mode = value
            onVendorSelected: value => root.controller.vendor = value
        }
        DeviceInfoCard {
            Layout.fillWidth: true
            detection: root.controller.detection
        }
        SplitView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            orientation: root.width < 900 ? Qt.Vertical : Qt.Horizontal

            ConfigEditor {
                id: configEditor
                SplitView.fillWidth: true
                SplitView.fillHeight: true
                SplitView.preferredWidth: 680
                SplitView.minimumWidth: 380
                SplitView.minimumHeight: 250
                text: root.controller.sourceText
                onTextEdited: value => {
                    if (root.controller.sourceText !== value) root.controller.sourceText = value
                }
            }
            AnalysisPanel {
                SplitView.fillWidth: true
                SplitView.fillHeight: true
                SplitView.preferredWidth: 440
                SplitView.minimumWidth: 340
                SplitView.minimumHeight: 220
                diagnosticsModel: root.controller.diagnosticsModel
                summary: root.controller.summary
                onIssueActivated: row => root.controller.requestJump(row)
            }
        }
        AppCard {
            Layout.fillWidth: true
            implicitHeight: 42
            padding: Spacing.sm
            RowLayout {
                anchors.fill: parent
                Text {
                    text: root.controller.busy ? "Analyzing locally…" : root.controller.statusMessage
                    color: root.controller.busy ? Colors.primary : Colors.textSecondary
                    font: Typography.caption
                }
                Item { Layout.fillWidth: true }
                Text {
                    text: "Configuration is processed locally and is not uploaded."
                    color: Colors.textSecondary
                    font: Typography.caption
                }
            }
        }
    }

    FileDialog {
        id: openDialog
        title: "Open network configuration"
        nameFilters: ["Configuration files (*.cfg *.conf *.txt)", "All files (*)"]
        onAccepted: root.controller.loadFile(selectedFile)
    }
    FileDialog {
        id: exportDialog
        title: "Export diagnostic report"
        fileMode: FileDialog.SaveFile
        defaultSuffix: "json"
        nameFilters: ["JSON report (*.json)"]
        onAccepted: root.controller.exportReport(selectedFile)
    }
    DropArea {
        anchors.fill: parent
        onDropped: drop => {
            if (drop.urls.length > 0) root.controller.loadFile(drop.urls[0])
        }
    }
    Connections {
        target: root.controller
        function onJumpToLine(line, endLine) { configEditor.jumpToLine(line) }
    }
}
