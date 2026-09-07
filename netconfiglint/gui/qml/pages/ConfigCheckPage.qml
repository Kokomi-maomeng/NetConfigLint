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
    objectName: "configCheckPage"
    property var controller
    property string draggedKey: ""
    property real dragSceneX: 0
    property int dropIndex: -1
    function panel(key) { return key === "configuration" ? configEditor : (key === "diagnostics" ? analysisPanel : temporaryEditor) }
    function syncOrder() {
        var order = preferences.values.panelOrder
        for (var i = 0; i < order.length; ++i) {
            for (var j = 0; j < workspaceSplit.count; ++j) {
                if (workspaceSplit.itemAt(j).panelKey === order[i]) { workspaceSplit.moveItem(j, i); break }
            }
        }
    }
    function movePanel(key, target) {
        var from = -1
        for (var i = 0; i < workspaceSplit.count; ++i) if (workspaceSplit.itemAt(i).panelKey === key) from = i
        if (from < 0 || target < 0 || target >= workspaceSplit.count) return
        workspaceSplit.moveItem(from, target)
        var order = []
        for (var j = 0; j < workspaceSplit.count; ++j) order.push(workspaceSplit.itemAt(j).panelKey)
        preferences.setValue("panelOrder", order)
    }
    function startDrag(key) { draggedKey = key; dropIndex = -1 }
    function updateDrag(sceneX) {
        dragSceneX = sceneX
        var x = workspaceSplit.mapFromItem(null, sceneX, 0).x
        var target = -1
        for (var i = 0; i < workspaceSplit.count; ++i) {
            var item = workspaceSplit.itemAt(i)
            if (item.visible && x >= item.x && x <= item.x + item.width) target = i
        }
        dropIndex = target
    }
    function finishDrag(sceneX) {
        updateDrag(sceneX)
        var key = draggedKey
        draggedKey = ""
        if (dropIndex >= 0) movePanel(key, dropIndex)
        dropIndex = -1
    }
    function step(key, direction) {
        var order = preferences.values.panelOrder
        movePanel(key, Math.max(0, Math.min(2, order.indexOf(key) + direction)))
    }
    function showConfiguration() {
        var panels = preferences.values.panels.slice()
        if (panels.indexOf("configuration") < 0) { panels.push("configuration"); preferences.setValue("panels", panels) }
    }
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 24
        spacing: 20
        RowLayout {
            Layout.fillWidth: true
            SelectableText { objectName: "checkPageTitle"; text: i18n.catalog["page.check"]; font: Typography.display }
            Item { Layout.fillWidth: true }
            SelectableText {
                Layout.maximumWidth: Math.max(160, root.width * 0.34)
                text: root.controller.fileName
                visible: text.length > 0
                color: Colors.textSecondary
                font: Typography.caption
                wrapMode: TextEdit.NoWrap
                clip: true
            }
        }
        ConfigToolbar {
            Layout.fillWidth: true
            controller: root.controller
            onOpenRequested: openDialog.open()
            onAnalyzeRequested: root.controller.analyzeConfig()
            onExportRequested: exportOptions.open()
        }
        SplitView {
            id: workspaceSplit
            objectName: "workspaceSplitView"
            Layout.fillWidth: true
            Layout.fillHeight: true
            orientation: Qt.Horizontal
            handle: Item {
                implicitWidth: 16
                Rectangle {
                    anchors.centerIn: parent
                    width: 3; height: Math.min(parent.height, 64); radius: 2
                    color: parent.SplitHandle.pressed ? Colors.primary : (parent.SplitHandle.hovered ? Colors.outline : Colors.outlineVariant)
                    Behavior on color { ColorAnimation { duration: 150 } }
                }
            }
            ConfigEditor {
                id: configEditor
                property string panelKey: "configuration"
                objectName: "configurationEditor"
                editorObjectName: "configurationTextArea"
                visible: preferences.values.panels.indexOf(panelKey) >= 0
                SplitView.preferredWidth: 300
                SplitView.minimumWidth: 240
                title: i18n.catalog["editor.configuration"]
                text: root.controller.sourceText
                onTextEdited: value => { if (root.controller.sourceText !== value) root.controller.sourceText = value }
                onDragStarted: root.startDrag(panelKey)
                onDragMoved: sceneX => root.updateDrag(sceneX)
                onDragFinished: sceneX => root.finishDrag(sceneX)
                onStepRequested: direction => root.step(panelKey, direction)
                opacity: root.draggedKey === panelKey ? 0.5 : 1
                Behavior on opacity { NumberAnimation { duration: 180 } }
                Behavior on x { enabled: !workspaceSplit.resizing; NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }
            }
            AnalysisPanel {
                id: analysisPanel
                property string panelKey: "diagnostics"
                objectName: "analysisPanel"
                visible: preferences.values.panels.indexOf(panelKey) >= 0
                SplitView.fillWidth: true
                SplitView.minimumWidth: 240
                diagnosticsModel: root.controller.diagnosticsModel
                detection: root.controller.detection
                summary: root.controller.summary
                statusKey: root.controller.statusMessage
                resultCurrent: root.controller.resultCurrent
                busy: root.controller.busy
                onIssueActivated: row => { root.showConfiguration(); root.controller.requestJump(row) }
                onDragStarted: root.startDrag(panelKey)
                onDragMoved: sceneX => root.updateDrag(sceneX)
                onDragFinished: sceneX => root.finishDrag(sceneX)
                onStepRequested: direction => root.step(panelKey, direction)
                opacity: root.draggedKey === panelKey ? 0.5 : 1
                Behavior on opacity { NumberAnimation { duration: 180 } }
                Behavior on x { enabled: !workspaceSplit.resizing; NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }
            }
            ConfigEditor {
                id: temporaryEditor
                property string panelKey: "temporary"
                objectName: "temporaryEditor"
                editorObjectName: "temporaryTextArea"
                visible: preferences.values.panels.indexOf(panelKey) >= 0
                SplitView.preferredWidth: 300
                SplitView.minimumWidth: 240
                title: i18n.catalog["editor.temporary"]
                onDragStarted: root.startDrag(panelKey)
                onDragMoved: sceneX => root.updateDrag(sceneX)
                onDragFinished: sceneX => root.finishDrag(sceneX)
                onStepRequested: direction => root.step(panelKey, direction)
                opacity: root.draggedKey === panelKey ? 0.5 : 1
                Behavior on opacity { NumberAnimation { duration: 180 } }
                Behavior on x { enabled: !workspaceSplit.resizing; NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }
            }
        }
    }
    Rectangle {
        visible: root.draggedKey.length > 0
        x: Math.max(0, Math.min(root.width - width, root.mapFromItem(null, root.dragSceneX, 0).x - width / 2))
        y: workspaceSplit.y - 8
        width: 180; height: 52; radius: 20
        color: Colors.primaryContainer
        border.color: Colors.primary
        z: 10
        Text { anchors.centerIn: parent; text: i18n.catalog["panel." + root.draggedKey] || ""; color: Colors.primary; font: Typography.label }
    }
    Rectangle {
        visible: root.draggedKey.length > 0 && root.dropIndex >= 0
        x: workspaceSplit.x + (root.dropIndex >= 0 ? workspaceSplit.itemAt(root.dropIndex).x : 0)
        y: workspaceSplit.y
        width: root.dropIndex >= 0 ? workspaceSplit.itemAt(root.dropIndex).width : 0
        height: workspaceSplit.height
        radius: 24; color: "transparent"; border.color: Colors.primary; border.width: 2
        Behavior on x { NumberAnimation { duration: 180 } }
    }
    FileDialog {
        id: openDialog
        title: i18n.catalog["dialog.open"]
        nameFilters: [i18n.catalog["file.config_filter"], i18n.catalog["file.all_filter"]]
        onAccepted: root.controller.loadFile(selectedFile)
    }
    ExportDialog {
        id: exportOptions
        objectName: "exportOptionsDialog"
        controller: root.controller
        onSaveRequested: format => {
            saveDialog.defaultSuffix = format
            saveDialog.nameFilters = [format === "json" ? "JSON (*.json)" : (format === "md" ? "Markdown (*.md)" : i18n.catalog["file.txt_filter"])]
            saveDialog.selectedFile = ""
            saveDialog.open()
        }
    }
    FileDialog {
        id: saveDialog
        objectName: "exportSaveDialog"
        title: i18n.catalog["dialog.export"]
        fileMode: FileDialog.SaveFile
        onAccepted: root.controller.exportReport(selectedFile)
        onRejected: root.controller.cancelExport()
    }
    DropArea { anchors.fill: parent; onDropped: drop => { if (drop.urls.length > 0) root.controller.loadFile(drop.urls[0]) } }
    Connections { target: root.controller; function onJumpToLine(line, endLine) { Qt.callLater(function() { configEditor.jumpToLine(line) }) } }
    Component.onCompleted: Qt.callLater(syncOrder)
}
