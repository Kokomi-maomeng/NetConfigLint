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
    property real dragStartSceneX: 0
    property real dragSourceX: 0
    property real dragProxyX: 0
    property real dragProxyY: 0
    property real dragProxyWidth: 0
    property real dragProxyHeight: 0
    property real dragProxyScale: 1
    property var dragSourceItem: null
    property int dropIndex: -1
    property int pendingDropIndex: -1
    property string pendingDropKey: ""
    function openFileDialog() { openDialog.open() }
    function openExportDialog() { exportOptions.open() }
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
    function startDrag(key, sceneX) {
        var item = panel(key)
        if (!item || !item.visible) return
        settleAnimation.stop()
        draggedKey = key
        dragSourceItem = item
        dragStartSceneX = sceneX
        dragSceneX = sceneX
        var position = item.mapToItem(root, 0, 0)
        dragSourceX = position.x
        dragProxyX = position.x
        dragProxyY = position.y
        dragProxyWidth = item.width
        dragProxyHeight = item.height
        dragProxyScale = 0.985
        updateDrag(sceneX)
    }
    function updateDrag(sceneX) {
        if (!dragSourceItem) return
        dragSceneX = sceneX
        dragProxyX = Math.max(0, Math.min(root.width - dragProxyWidth, dragSourceX + sceneX - dragStartSceneX))
        var x = workspaceSplit.mapFromItem(null, sceneX, 0).x
        var target = -1
        for (var i = 0; i < workspaceSplit.count; ++i) {
            var item = workspaceSplit.itemAt(i)
            if (item.visible && x >= item.x && x <= item.x + item.width) {
                target = i
                break
            }
        }
        dropIndex = target
    }
    function finishDrag(sceneX) {
        if (!dragSourceItem) return
        updateDrag(sceneX)
        pendingDropKey = draggedKey
        pendingDropIndex = dropIndex
        var target = dropIndex >= 0 ? workspaceSplit.itemAt(dropIndex) : dragSourceItem
        var position = target.mapToItem(root, 0, 0)
        dropIndex = -1
        settleX.from = dragProxyX
        settleX.to = position.x
        settleY.from = dragProxyY
        settleY.to = position.y
        settleScale.from = dragProxyScale
        settleScale.to = 1
        settleAnimation.restart()
    }
    function resetDrag() {
        draggedKey = ""
        dragSourceItem = null
        dragProxyScale = 1
    }
    function step(key, direction) {
        var order = preferences.values.panelOrder
        movePanel(key, Math.max(0, Math.min(2, order.indexOf(key) + direction)))
    }
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 24
        spacing: 20
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
                    Behavior on color { ColorAnimation { duration: Theme.motionShort } }
                }
            }
            ConfigEditor {
                id: configEditor
                property string panelKey: "configuration"
                objectName: "configurationEditor"
                editorObjectName: "configurationTextArea"
                visible: true
                SplitView.preferredWidth: 300
                SplitView.minimumWidth: 240
                title: root.controller.editorReadOnly ? i18n.catalog["editor.bundle_preview"] : i18n.catalog["editor.configuration"]
                titleObjectName: "checkPageTitle"
                text: root.controller.editorText
                readOnly: root.controller.editorReadOnly
                showAnalyze: true
                analysisBusy: root.controller.busy
                onAnalyzeRequested: root.controller.analyzeConfig()
                onTextEdited: value => { if (!readOnly && root.controller.sourceText !== value) root.controller.sourceText = value }
                onDragStarted: sceneX => root.startDrag(panelKey, sceneX)
                onDragMoved: sceneX => root.updateDrag(sceneX)
                onDragFinished: sceneX => root.finishDrag(sceneX)
                onStepRequested: direction => root.step(panelKey, direction)
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
                coverage: root.controller.coverage
                onCancelRequested: root.controller.cancelAnalysis()
                resultCurrent: root.controller.resultCurrent
                busy: root.controller.busy
                onIssueActivated: row => root.controller.requestJump(row)
                onDragStarted: sceneX => root.startDrag(panelKey, sceneX)
                onDragMoved: sceneX => root.updateDrag(sceneX)
                onDragFinished: sceneX => root.finishDrag(sceneX)
                onStepRequested: direction => root.step(panelKey, direction)
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
                onDragStarted: sceneX => root.startDrag(panelKey, sceneX)
                onDragMoved: sceneX => root.updateDrag(sceneX)
                onDragFinished: sceneX => root.finishDrag(sceneX)
                onStepRequested: direction => root.step(panelKey, direction)
            }
        }
    }
    Item {
        id: dragProxy
        objectName: "panelDragProxy"
        visible: root.draggedKey.length > 0
        x: root.dragProxyX
        y: root.dragProxyY
        width: root.dragProxyWidth
        height: root.dragProxyHeight
        scale: root.dragProxyScale
        z: 100
        transformOrigin: Item.Center
        Rectangle {
            anchors.fill: parent
            anchors.topMargin: 12
            anchors.leftMargin: 8
            anchors.rightMargin: -8
            anchors.bottomMargin: -12
            radius: Spacing.radiusCard
            color: Qt.alpha("#000000", Theme.dark ? 0.34 : 0.15)
        }
        Rectangle {
            anchors.fill: parent
            anchors.topMargin: 5
            anchors.leftMargin: 3
            anchors.rightMargin: -3
            anchors.bottomMargin: -5
            radius: Spacing.radiusCard
            color: Qt.alpha("#000000", Theme.dark ? 0.24 : 0.10)
        }
        ShaderEffectSource {
            anchors.fill: parent
            sourceItem: root.dragSourceItem
            hideSource: root.draggedKey.length > 0
            live: true
            recursive: true
            smooth: true
        }
    }
    ParallelAnimation {
        id: settleAnimation
        NumberAnimation { id: settleX; target: root; property: "dragProxyX"; duration: Theme.motionMedium; easing.type: Easing.OutCubic }
        NumberAnimation { id: settleY; target: root; property: "dragProxyY"; duration: Theme.motionMedium; easing.type: Easing.OutCubic }
        NumberAnimation { id: settleScale; target: root; property: "dragProxyScale"; duration: Theme.motionMedium; easing.type: Easing.OutCubic }
        onFinished: {
            if (root.pendingDropIndex >= 0) root.movePanel(root.pendingDropKey, root.pendingDropIndex)
            root.pendingDropIndex = -1
            root.pendingDropKey = ""
            root.resetDrag()
        }
    }
    FileDialog {
        id: openDialog
        options: FileDialog.DontUseNativeDialog
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
        options: FileDialog.DontUseNativeDialog
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
