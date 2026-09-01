pragma ComponentBehavior: Bound
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
        spacing: Spacing.md

        RowLayout {
            Layout.fillWidth: true
            SelectableText {
                text: i18n.catalog["page.check"]
                color: Colors.textPrimary
                font: Typography.display
            }
            Item { Layout.fillWidth: true }
            SelectableText {
                Layout.maximumWidth: Math.max(160, root.width * 0.34)
                text: root.controller.fileName
                color: Colors.textSecondary
                font: Typography.caption
                wrapMode: TextEdit.NoWrap
                horizontalAlignment: TextEdit.AlignRight
                clip: true
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
            id: workspaceSplit
            objectName: "workspaceSplitView"
            Layout.fillWidth: true
            Layout.fillHeight: true
            orientation: Qt.Horizontal
            handle: Item {
                implicitWidth: Spacing.md
                implicitHeight: Spacing.md
                Rectangle {
                    anchors.centerIn: parent
                    width: workspaceSplit.orientation === Qt.Horizontal ? 3 : Math.min(parent.width, 96)
                    height: workspaceSplit.orientation === Qt.Horizontal ? Math.min(parent.height - Spacing.lg, 96) : 3
                    radius: 2
                    color: parent.SplitHandle.pressed ? Colors.primary
                           : (parent.SplitHandle.hovered ? Colors.outline : Colors.outlineVariant)
                    Behavior on color { ColorAnimation { duration: 120 } }
                }
            }

            ConfigEditor {
                id: configEditor
                objectName: "configurationEditor"
                editorObjectName: "configurationTextArea"
                SplitView.fillHeight: true
                SplitView.preferredWidth: 300
                SplitView.minimumWidth: 250
                title: i18n.catalog["editor.configuration"]
                subtitle: i18n.catalog["editor.configuration.detail"]
                placeholderText: i18n.catalog["editor.configuration.placeholder"]
                text: root.controller.sourceText
                onTextEdited: value => {
                    if (root.controller.sourceText !== value) root.controller.sourceText = value
                }
            }
            AnalysisPanel {
                id: analysisPanel
                objectName: "analysisPanel"
                SplitView.fillWidth: true
                SplitView.fillHeight: true
                SplitView.preferredWidth: 400
                SplitView.minimumWidth: 280
                diagnosticsModel: root.controller.diagnosticsModel
                detection: root.controller.detection
                summary: root.controller.summary
                onIssueActivated: row => root.controller.requestJump(row)
            }
            ConfigEditor {
                id: temporaryEditor
                objectName: "temporaryEditor"
                editorObjectName: "temporaryTextArea"
                SplitView.fillHeight: true
                SplitView.preferredWidth: 300
                SplitView.minimumWidth: 250
                title: i18n.catalog["editor.temporary"]
                subtitle: i18n.catalog["editor.temporary.detail"]
                placeholderText: i18n.catalog["editor.temporary.placeholder"]
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
