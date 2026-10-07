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
    readonly property real minimumWorkspaceWidth: configEditor.headerMinimumWidth
        + (analysisPanel.visible ? 240 + 16 : 0)
        + (temporaryEditor.visible ? temporaryEditor.headerMinimumWidth + 16 : 0) + 64
    readonly property bool narrow: width < minimumWorkspaceWidth
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
    function openTemporaryExportDialog() { temporaryFileDialog.open() }
    function panel(key) { return key === "configuration" ? configEditor : (key === "diagnostics" ? analysisPanel : temporaryEditor) }
    function savePanelSizes() {
        var key = root.narrow ? "panelHeights" : "panelWidths"
        var sizes = preferences.values[key].slice()
        var keys = ["configuration", "diagnostics", "temporary"]
        for (var i = 0; i < keys.length; ++i) {
            var item = panel(keys[i])
            var value = root.narrow ? item.height : item.width
            if (item.visible && value >= 100) sizes[i] = Math.round(value)
        }
        preferences.setValue(key, sizes)
    }
    function restorePanelSizes() {
        var keys = ["configuration", "diagnostics", "temporary"]
        for (var i = 0; i < keys.length; ++i) {
            var item = panel(keys[i])
            item.SplitView.preferredWidth = preferences.values.panelWidths[i]
            item.SplitView.preferredHeight = preferences.values.panelHeights[i]
        }
    }
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
        if (root.narrow || !item || !item.visible) return
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
    property var focusedEditorCard: null
    function revealEditor(card) {
        focusedEditorCard = card
        revealEditorTimer.restart()
    }
    function revealFocusedEditor() {
        if (configEditor && configEditor.editor && configEditor.editor.activeFocus) root.revealEditor(configEditor)
        else if (temporaryEditor && temporaryEditor.editor && temporaryEditor.editor.activeFocus) root.revealEditor(temporaryEditor)
    }
    onWidthChanged: revealFocusedEditor()
    onHeightChanged: revealFocusedEditor()
    Timer {
        id: revealEditorTimer
        interval: 1
        onTriggered: {
            var card = root.focusedEditorCard
            if (!card || !card.visible || !card.editor.activeFocus || !workspaceScroll.contentItem) return
            var caret = card.editor.cursorRectangle
            var point = card.editor.mapToItem(workspaceScroll, caret.x, caret.y)
            var flickable = workspaceScroll.contentItem
            var viewportTop = flickable.mapToItem(workspaceScroll, 0, 0).y
            var top = viewportTop + 8
            var bottom = viewportTop + flickable.height - 8
            var delta = point.y < top ? point.y - top
                : point.y + caret.height > bottom ? point.y + caret.height - bottom : 0
            if (delta !== 0) {
                flickable.contentY = Math.max(0, Math.min(flickable.contentHeight - flickable.height,
                    flickable.contentY + delta))
            }
        }
    }
    Connections {
        target: configEditor.editor
        function onActiveFocusChanged() { if (target.activeFocus) root.revealEditor(configEditor) }
        function onCursorPositionChanged() { if (target.activeFocus) root.revealEditor(configEditor) }
        function onTextChanged() { if (target.activeFocus) root.revealEditor(configEditor) }
    }
    Connections {
        target: temporaryEditor.editor
        function onActiveFocusChanged() { if (target.activeFocus) root.revealEditor(temporaryEditor) }
        function onCursorPositionChanged() { if (target.activeFocus) root.revealEditor(temporaryEditor) }
        function onTextChanged() { if (target.activeFocus) root.revealEditor(temporaryEditor) }
    }
    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: 20
        anchors.rightMargin: 20
        anchors.topMargin: 20
        anchors.bottomMargin: 20
        spacing: 12
        Label {
            objectName: "sourceIdentityLabel"
            Layout.fillWidth: true
            elide: Text.ElideMiddle
            font: Typography.caption
            color: Colors.textSecondary
            text: (root.controller.fileName || i18n.catalog["file.new"]) + (root.controller.sourceDirty ? " * " + i18n.catalog["file.modified"] : "")
                  + " · " + (i18n.catalog["file.identity." + root.controller.sourceIdentity] || "")
            HoverHandler { id: identityHover }
            ToolTip.visible: identityHover.hovered
            ToolTip.text: root.controller.filePath
        }
        ScrollView {
            id: workspaceScroll
            objectName: "workspaceScrollView"
            Layout.fillWidth: true
            Layout.fillHeight: true
            // The viewport is allocated by its parent, independently of the
            // scrollable content's natural height.
            Layout.minimumHeight: 0
            Layout.preferredHeight: 0
            implicitWidth: 0
            implicitHeight: 0
            padding: 0
            // Reserve the scrollbar gutter even while the scrollbar is hidden:
            // wrapped text must not resize itself through AsNeeded visibility.
            rightPadding: ScrollBar.vertical.implicitWidth
            clip: true
            contentWidth: availableWidth
            contentHeight: workspaceContent.height
            ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
            ScrollBar.vertical.policy: ScrollBar.AsNeeded
            Item {
                id: workspaceContent
                objectName: "workspaceContent"
                width: workspaceScroll.availableWidth
                readonly property int panelCount: 1 + (analysisPanel.visible ? 1 : 0) + (temporaryEditor.visible ? 1 : 0)
                readonly property real panelsHeight: root.narrow
                    ? Math.max(400, preferences.values.panelHeights[0])
                      + (analysisPanel.visible ? Math.max(400, preferences.values.panelHeights[1]) : 0)
                      + (temporaryEditor.visible ? Math.max(400, preferences.values.panelHeights[2]) : 0)
                      + 16 * (panelCount - 1) : 280
                height: Math.max(workspaceScroll.availableHeight, workspacePreamble.height + 12 + panelsHeight)
                Column {
                    id: workspacePreamble
                    objectName: "workspacePreamble"
                    width: parent.width
                    spacing: 12
                    onHeightChanged: root.revealFocusedEditor()
                    Label {
                        objectName: "historyPrivacyNotice"
                        width: parent.width
                        text: i18n.catalog[root.controller.historyEnabled ? "history.notice." + root.controller.historyRetention : "history.disabled"]
                        wrapMode: Text.Wrap
                        font: Typography.caption
                        color: Colors.textSecondary
                    }
                    Label {
                        objectName: "firstUseHelp"
                        width: parent.width
                        visible: root.controller.sourceText.length === 0
                        text: i18n.catalog["editor.get_started"]
                        wrapMode: Text.Wrap
                        font: Typography.body
                        color: Colors.textSecondary
                    }
                }
                SplitView {
                    id: workspaceSplit
                    objectName: "workspaceSplitView"
                    y: workspacePreamble.height + 12
                    width: parent.width
                    height: parent.height - y
                    onYChanged: root.revealFocusedEditor()
                    onHeightChanged: root.revealFocusedEditor()
                    orientation: root.narrow ? Qt.Vertical : Qt.Horizontal
                    onResizingChanged: { if (!resizing) Qt.callLater(root.savePanelSizes) }
                    handle: Item {
                        implicitWidth: 16
                        implicitHeight: 16
                    }
                    ConfigEditor {
                        id: configEditor
                        property string panelKey: "configuration"
                        objectName: "configurationEditor"
                        editorObjectName: "configurationTextArea"
                        visible: true
                        SplitView.preferredWidth: preferences.values.panelWidths[0]
                        SplitView.minimumWidth: root.narrow ? 0 : headerMinimumWidth
                        SplitView.preferredHeight: preferences.values.panelHeights[0]
                        SplitView.minimumHeight: root.narrow ? 400 : 0
                        title: root.controller.editorReadOnly ? i18n.catalog["editor.bundle_preview"] : i18n.catalog["editor.configuration"]
                        titleObjectName: "checkPageTitle"
                        text: syntaxHighlighter.prepareText(configEditor.editor ? configEditor.editor.textDocument : null, root.controller.editorText, configEditor.editor)
                        readOnly: root.controller.editorReadOnly
                        SplitView.fillWidth: true
                        diagnosticMarkers: root.controller.diagnosticMarkers
                        showAnalyze: true
                        analysisBusy: root.controller.busy
                        onAnalyzeRequested: root.controller.analyzeConfig()
                        onTextEdited: value => { if (!readOnly && root.controller.sourceText !== value) root.controller.sourceText = value }
                        onDragStarted: sceneX => root.startDrag(panelKey, sceneX)
                        onDragMoved: sceneX => root.updateDrag(sceneX)
                        onDragFinished: sceneX => root.finishDrag(sceneX)
                        onStepRequested: direction => root.step(panelKey, direction)
                        onSearchOpenRequested: searchCard.openFor(configEditor)
                    }
                    AnalysisPanel {
                        id: analysisPanel
                        property string panelKey: "diagnostics"
                        objectName: "analysisPanel"
                        visible: preferences.values.panels.indexOf(panelKey) >= 0
                        SplitView.preferredWidth: preferences.values.panelWidths[1]
                        SplitView.minimumWidth: root.narrow ? 0 : 240
                        SplitView.fillHeight: root.narrow
                        SplitView.preferredHeight: preferences.values.panelHeights[1]
                        SplitView.minimumHeight: root.narrow ? 400 : 0
                        diagnosticsModel: root.controller.diagnosticsModel
                        detection: root.controller.detection
                        resultTimestamp: root.controller.resultTimestamp
                        summary: root.controller.summary
                        statusKey: root.controller.statusMessage
                        coverage: root.controller.coverage
                        onPendingLineActivated: line => configEditor.jumpToLine(line)
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
                        SplitView.preferredWidth: preferences.values.panelWidths[2]
                        SplitView.minimumWidth: root.narrow ? 0 : headerMinimumWidth
                        SplitView.preferredHeight: preferences.values.panelHeights[2]
                        SplitView.minimumHeight: root.narrow ? 400 : 0
                        title: i18n.catalog["temporary.local_draft"] + (root.controller.temporaryDirty ? " *" : "")
                        text: syntaxHighlighter.prepareText(temporaryEditor.editor ? temporaryEditor.editor.textDocument : null, root.controller.temporaryText, temporaryEditor.editor)
                        showSave: true
                        onSaveRequested: value => root.controller.saveTemporaryText(value)
                        onTextEdited: value => root.controller.updateTemporaryText(value)
                        onSearchOpenRequested: searchCard.openFor(temporaryEditor)
                        onDragStarted: sceneX => root.startDrag(panelKey, sceneX)
                        onDragMoved: sceneX => root.updateDrag(sceneX)
                        onDragFinished: sceneX => root.finishDrag(sceneX)
                        onStepRequested: direction => root.step(panelKey, direction)
                    }
                }
            }
        }
    }
    SearchCard {
        id: searchCard
        anchors.fill: parent
        z: 200
    }
    Shortcut {
        sequences: [StandardKey.Find]
        enabled: root.visible && (configEditor.editor.activeFocus
            || temporaryEditor.editor.activeFocus || searchCard.opened)
        onActivated: {
            var card = configEditor.editor.activeFocus ? configEditor
                : temporaryEditor.editor.activeFocus ? temporaryEditor : searchCard.targetCard
            if (card) searchCard.toggleFor(card)
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
        objectName: "openConfigDialog"
        title: i18n.catalog["dialog.open"]
        nameFilters: [i18n.catalog["file.config_filter"], i18n.catalog["file.all_filter"]]
        onAccepted: root.controller.requestAction("load", String(selectedFile))
    }
    FileDialog {
        id: sourceSaveDialog
        objectName: "sourceSaveDialog"
        title: i18n.catalog["file.save_as"]
        fileMode: FileDialog.SaveFile
        defaultSuffix: "cfg"
        nameFilters: [i18n.catalog["file.config_filter"], i18n.catalog["file.all_filter"]]
        onAccepted: root.controller.saveSourceFile(String(selectedFile))
        onRejected: root.controller.resolveUnsaved("cancel")
    }
    FileDialog {
        id: temporaryFileDialog
        objectName: "temporaryFileDialog"
        title: i18n.catalog["temporary.export"]
        fileMode: FileDialog.SaveFile
        defaultSuffix: "txt"
        onAccepted: root.controller.exportTemporaryFile(String(selectedFile))
    }
    AppDialog {
        id: storageDialog
        title: i18n.catalog["storage.locations"]
        contentItem: SelectableText { wrapMode: TextEdit.WrapAnywhere; text: i18n.catalog["editor.temporary"] + ": " + root.controller.temporaryPath + "\n" + i18n.catalog["settings.history"] + ": " + root.controller.historyPath }
    }
    readonly property var focusedSaveTarget: {
        var item = root.Window.window ? root.Window.window.activeFocusItem : null
        while (item) {
            if (item === configEditor.editor) return configEditor
            if (item === temporaryEditor.editor) return temporaryEditor
            if (item === searchCard) return searchCard.targetCard
            item = item.parent
        }
        return null
    }
    Shortcut {
        sequences: [StandardKey.Save]
        enabled: root.visible && root.focusedSaveTarget !== null
        onActivated: {
            if (root.focusedSaveTarget === temporaryEditor)
                root.controller.saveTemporaryText(syntaxHighlighter.fullText(temporaryEditor.editor))
            else root.controller.saveConfiguration()
        }
    }
    Connections { target: root.controller; function onSaveAsRequested(scope) { if (scope === "configuration") sourceSaveDialog.open() } }
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
    DropArea { anchors.fill: parent; onDropped: drop => { if (drop.urls.length > 0) root.controller.requestAction("load", String(drop.urls[0])) } }
    Connections { target: root.controller; function onJumpToLine(line, endLine) { Qt.callLater(function() { configEditor.jumpToLine(line) }) } }
    Connections {
        target: preferences
        function onLayoutReset() { root.syncOrder(); root.restorePanelSizes() }
    }
    Component.onCompleted: Qt.callLater(syncOrder)
}
