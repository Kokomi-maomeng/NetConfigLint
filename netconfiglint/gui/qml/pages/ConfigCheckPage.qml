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
            SelectableText {
                text: i18n.catalog["page.check"]
                color: Colors.textPrimary
                font: Typography.display
            }
            Item { Layout.fillWidth: true }
            SelectableText {
                text: root.controller.fileName
                color: Colors.textSecondary
                font: Typography.caption
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
        SplitView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            orientation: root.width < 900 ? Qt.Vertical : Qt.Horizontal

            SplitView {
                SplitView.fillWidth: true
                SplitView.fillHeight: true
                SplitView.preferredWidth: 680
                SplitView.minimumWidth: 380
                SplitView.minimumHeight: 250
                orientation: Qt.Vertical

                ConfigEditor {
                    id: configEditor
                    SplitView.fillWidth: true
                    SplitView.fillHeight: true
                    SplitView.preferredHeight: 430
                    SplitView.minimumHeight: 220
                    title: i18n.catalog["editor.configuration"]
                    subtitle: i18n.catalog["editor.configuration.detail"]
                    placeholderText: i18n.catalog["editor.configuration.placeholder"]
                    text: root.controller.sourceText
                    onTextEdited: value => {
                        if (root.controller.sourceText !== value) root.controller.sourceText = value
                    }
                }
                ConfigEditor {
                    id: temporaryEditor
                    SplitView.fillWidth: true
                    SplitView.fillHeight: true
                    SplitView.preferredHeight: 250
                    SplitView.minimumHeight: 170
                    title: i18n.catalog["editor.temporary"]
                    subtitle: i18n.catalog["editor.temporary.detail"]
                    placeholderText: i18n.catalog["editor.temporary.placeholder"]
                }
            }
            AnalysisPanel {
                SplitView.fillHeight: true
                SplitView.preferredWidth: 440
                SplitView.minimumWidth: 340
                SplitView.minimumHeight: 220
                diagnosticsModel: root.controller.diagnosticsModel
                detection: root.controller.detection
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
                SelectableText {
                    text: root.controller.busy ? "Analyzing locally…" : root.controller.statusMessage
                    wrapMode: TextEdit.NoWrap
                    color: root.controller.busy ? Colors.primary : Colors.textSecondary
                    font: Typography.caption
                }
                Item { Layout.fillWidth: true }
                SelectableText {
                    text: i18n.catalog["status.local"]
                    wrapMode: TextEdit.NoWrap
                    color: Colors.textSecondary
                    font: Typography.caption
                }
            }
        }
    }

    FileDialog {
        id: openDialog
        title: i18n.catalog["dialog.open"]
        nameFilters: ["Configuration files (*.cfg *.conf *.txt)", "All files (*)"]
        onAccepted: root.controller.loadFile(selectedFile)
    }
    FileDialog {
        id: exportDialog
        title: i18n.catalog["dialog.export"]
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
