import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import theme 1.0
import "../components"
AppCard {
    id: root
    property alias text: editor.text
    property alias readOnly: editor.readOnly
    property alias editor: editor
    property string editorObjectName: "configEditorTextArea"
    property string title: i18n.catalog["editor.configuration"]
    property string titleObjectName: ""
    property bool showAnalyze: false
    property bool showSave: false
    property bool analysisBusy: false
    property bool searchActive: false
    property int searchCaretPosition: -1
    property real savedSelectionViewX: 0
    property real savedSelectionViewY: 0
    signal analyzeRequested()
    signal saveRequested(string value)
    signal searchOpenRequested()
    property int currentLine: 1
    property int editorFontSize: Typography.monospace.pixelSize
    property bool zoomModified: false
    readonly property int selectionWindowStart: scrollView.contentItem
        ? editor.positionAt(editor.leftPadding,
            Math.max(0, scrollView.contentItem.contentY - 2 * monoMetrics.height)) : 0
    readonly property int selectionWindowEnd: scrollView.contentItem
        ? (scrollView.contentItem.contentY + scrollView.height + 2 * monoMetrics.height
            >= editor.topPadding + editor.contentHeight ? editor.length
            : editor.positionAt(editor.leftPadding,
                scrollView.contentItem.contentY + scrollView.height + 2 * monoMetrics.height))
        : editor.length
    readonly property real headerMinimumWidth: Math.ceil(header.requiredWidth + 4)
    signal textEdited(string value)
    signal dragStarted(real sceneX)
    signal dragMoved(real sceneX)
    signal dragFinished(real sceneX)
    signal stepRequested(int direction)
    padding: 0
    function resetZoom() { editorFontSize = Typography.monospace.pixelSize; zoomModified = false }
    function zoom(delta) { editorFontSize = Math.max(9, Math.min(40, editorFontSize + delta)); zoomModified = true }
    function selectedWhitespaceRanges() {
        var start = Math.max(editor.selectionStart, selectionWindowStart)
        var lastVisibleLineEnd = editor.text.indexOf("\n", selectionWindowEnd)
        var end = Math.min(editor.selectionEnd,
            lastVisibleLineEnd < 0 ? editor.length : lastVisibleLineEnd + 1)
        var value = editor.text
        if (start === end) return []
        var ranges = []
        var offset = start === 0 ? 0 : value.lastIndexOf("\n", start - 1) + 1
        while (offset < end) {
            var next = value.indexOf("\n", offset)
            if (next < 0) next = value.length
            if (next === offset && next + 1 > start) {
                ranges.push({ start: offset, end: offset, blank: true })
            } else {
                var position = Math.max(start, offset)
                var selectedEnd = Math.min(end, next)
                while (position < selectedEnd) {
                    if (!/[^\S\r\n]/.test(value[position])) { position++; continue }
                    var runStart = position
                    do { position++ } while (position < selectedEnd && /[^\S\r\n]/.test(value[position]))
                    ranges.push({ start: runStart, end: position, blank: false })
                }
            }
            if (next === value.length) break
            offset = next + 1
        }
        return ranges
    }
    function lineNumberText() {
        var result = []
        for (var i = 1; i <= Math.max(1, editor.lineCount); ++i) result.push(i)
        return result.join("\n")
    }
    function updateCurrentLine() {
        currentLine = editor.text.slice(0, editor.cursorPosition).split("\n").length
    }
    function jumpToLine(line) {
        if (!isFinite(line)) return
        var safeLine = Math.max(1, Math.min(Math.floor(line), editor.lineCount))
        var position = 0
        var lines = editor.text.split("\n")
        for (var i = 1; i < safeLine; ++i) position += lines[i - 1].length + 1
        editor.cursorPosition = position
        editor.forceActiveFocus()
        Qt.callLater(function() {
            scrollView.contentItem.contentY = Math.max(0, Math.min(scrollView.contentItem.contentHeight - scrollView.height, editor.cursorRectangle.y - scrollView.height / 3))
        })
    }
    function selectAllWithoutScroll() {
        var flickable = scrollView.contentItem
        savedSelectionViewX = flickable.contentX
        savedSelectionViewY = flickable.contentY
        editor.selectAll()
        flickable.contentX = savedSelectionViewX
        flickable.contentY = savedSelectionViewY
        restoreSelectionView.restart()
    }
    function clampEditorViewport() {
        var flickable = scrollView.contentItem
        if (!flickable) return
        var maxY = Math.max(0, editor.contentHeight + editor.topPadding
            + editor.bottomPadding - scrollView.height)
        if (flickable.contentY > maxY) flickable.contentY = maxY
    }
    Timer {
        id: restoreSelectionView
        interval: 30
        onTriggered: {
            scrollView.contentItem.contentX = root.savedSelectionViewX
            scrollView.contentItem.contentY = root.savedSelectionViewY
            root.clampEditorViewport()
        }
    }
    Connections {
        target: editor
        function onContentHeightChanged() { Qt.callLater(root.clampEditorViewport) }
    }
    FontMetrics { id: monoMetrics; font: editor.font }
    ColumnLayout {
        anchors.fill: parent
        spacing: 0
        CardHeader {
            id: header
            objectName: root.editorObjectName + "Header"
            Layout.fillWidth: true
            Layout.preferredHeight: implicitHeight
            title: root.title
            titleObjectName: root.titleObjectName
            actionText: root.showAnalyze ? (root.analysisBusy ? i18n.catalog["toolbar.analyzing"] : i18n.catalog["toolbar.analyze"]) : (root.showSave ? i18n.catalog["common.save"] : "")
            actionObjectName: root.showSave ? "temporarySaveButton" : "analyzeButton"
            actionEnabled: root.showSave || (!root.analysisBusy && root.text.trim().length > 0)
            onActionClicked: { if (root.showSave) root.saveRequested(root.text); else root.analyzeRequested() }
            detail: root.currentLine + " / " + Math.max(1, editor.lineCount)
            minimumDetailDigits: Math.max(5, String(root.currentLine).length, String(Math.max(1, editor.lineCount)).length)
            onDragStarted: sceneX => root.dragStarted(sceneX)
            onDragMoved: sceneX => root.dragMoved(sceneX)
            onDragFinished: sceneX => root.dragFinished(sceneX)
            onStepRequested: direction => root.stepRequested(direction)
        }
        Item {
            id: editorBody
            objectName: root.editorObjectName + "Viewport"
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.bottomMargin: 16
            clip: true
            ScrollView {
                id: scrollView
                objectName: root.editorObjectName + "ScrollView"
                anchors.fill: parent
                clip: true
                ScrollBar.horizontal: AppScrollBar {
                    parent: scrollView
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                }
                ScrollBar.vertical: AppScrollBar {
                    parent: scrollView
                    anchors.top: parent.top
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                }
                TextArea {
                    id: editor
            WheelHandler {
                target: null
                acceptedModifiers: Qt.ControlModifier
                onWheel: event => { if (event.angleDelta.y !== 0) root.zoom(event.angleDelta.y > 0 ? 1 : -1); event.accepted = true }
            }

                    objectName: root.editorObjectName
                    width: Math.max(scrollView.availableWidth, implicitWidth)
                    height: Math.max(scrollView.availableHeight, implicitHeight)
                    leftPadding: lineNumberGutter.width + 8
                    rightPadding: 16
                    topPadding: 12
                    bottomPadding: 12
                    wrapMode: TextEdit.NoWrap
                    textFormat: TextEdit.PlainText
                    selectByMouse: true
                    Keys.priority: Keys.BeforeItem
                    Keys.onPressed: event => {
                        if (event.matches(StandardKey.SelectAll)) {
                            root.selectAllWithoutScroll()
                            event.accepted = true
                        }
                    }
                    persistentSelection: Theme.selectionLocked || root.searchActive
                    renderType: Text.QtRendering
                    color: Colors.textPrimary
                    selectionColor: Colors.primaryContainer
                    selectedTextColor: Colors.textPrimary
                    font: fontPalette.editorFont(root.editorFontSize)
                    background: Item {
                        Repeater {
                            model: root.selectedWhitespaceRanges()
                            Rectangle {
                                required property var modelData
                                property rect startRect: {
                                    root.editorFontSize
                                    return editor.positionToRectangle(modelData.start)
                                }
                                property rect endRect: editor.positionToRectangle(modelData.end)
                                property point visualOrigin: editor.mapToItem(parent, startRect.x, startRect.y)
                                objectName: modelData.blank ? "selectedBlankLine" : "selectedWhitespace"
                                x: visualOrigin.x
                                y: visualOrigin.y
                                width: modelData.blank ? Math.max(12, Math.ceil(monoMetrics.advanceWidth(" ") + 4))
                                    : Math.max(1, endRect.x - startRect.x)
                                height: startRect.height
                                radius: 3
                                color: editor.selectionColor
                            }
                        }
                    }
                    Rectangle {
                        objectName: root.editorObjectName + "SearchCaret"
                        property rect matchRect: root.searchCaretPosition >= 0
                            ? editor.positionToRectangle(root.searchCaretPosition) : Qt.rect(0, 0, 0, 0)
                        visible: root.searchActive && root.searchCaretPosition >= 0
                        x: matchRect.x
                        y: matchRect.y
                        width: 2
                        height: matchRect.height
                        radius: 1
                        color: Colors.primary
                        z: 3
                    }
                    ContextMenu.menu: TextEditMenu { editor: root.editor; zoomTarget: root }
                    onTextChanged: { root.textEdited(text); Qt.callLater(root.updateCurrentLine) }
                    onCursorPositionChanged: Qt.callLater(root.updateCurrentLine)
                }
            }
            Rectangle {
                id: lineNumberGutter
                objectName: root.editorObjectName + "Gutter"
                anchors.left: parent.left
                anchors.top: parent.top
                anchors.bottom: parent.bottom
                width: Math.ceil(monoMetrics.advanceWidth(String(Math.max(1, editor.lineCount)))) + 12
                color: Colors.surfaceContainerLow
                clip: true
                z: 2
                Text {
                    x: 6
                    y: editor.topPadding - scrollView.contentItem.contentY
                    width: lineNumberGutter.width - 12
                    text: root.lineNumberText()
                    color: Colors.textSecondary
                    font: editor.font
                    renderType: Text.QtRendering
                    horizontalAlignment: Text.AlignRight
                }
            }
        }
    }
    Shortcut { sequence: "Ctrl+G"; enabled: root.visible && editor.activeFocus; onActivated: jumpDialog.open() }
    Shortcut { sequences: ["Ctrl++", "Ctrl+="]; enabled: root.visible && editor.activeFocus; onActivated: root.zoom(1) }
    Shortcut { sequence: "Ctrl+-"; enabled: root.visible && editor.activeFocus; onActivated: root.zoom(-1) }
    Component.onCompleted: { syntaxHighlighter.attach(editor.textDocument); syntaxHighlighter.setDark(Theme.dark) }
    Connections { target: Theme; function onDarkChanged() { syntaxHighlighter.setDark(Theme.dark) } }
    Connections {
        target: analysisController
        function onResultCurrentChanged() {
            if (root.showAnalyze) syntaxHighlighter.setUnsupportedLinesFor(
                editor.textDocument, analysisController.coverage.unsupported_lines || [])
        }
    }
    AppDialog {
        id: jumpDialog
        title: i18n.catalog["editor.goto"]
        contentItem: AppTextField {
            id: lineField
            implicitHeight: 44
            placeholderText: i18n.catalog["editor.line_number"]
            validator: IntValidator { bottom: 1; top: editor.lineCount }
            inputMethodHints: Qt.ImhDigitsOnly
            onAccepted: if (acceptableInput) { root.jumpToLine(Number(text)); jumpDialog.close() }
        }
    }
}
