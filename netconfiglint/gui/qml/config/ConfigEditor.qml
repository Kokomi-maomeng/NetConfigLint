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
    signal analyzeRequested()
    signal saveRequested(string value)
    property int currentLine: 1
    property int editorFontSize: Typography.monospace.pixelSize
    property bool zoomModified: false
    signal textEdited(string value)
    signal dragStarted(real sceneX)
    signal dragMoved(real sceneX)
    signal dragFinished(real sceneX)
    signal stepRequested(int direction)
    padding: 0
    function resetZoom() { editorFontSize = Typography.monospace.pixelSize; zoomModified = false }
    function zoom(delta) { editorFontSize = Math.max(9, Math.min(40, editorFontSize + delta)); zoomModified = true }
    function selectedBlankLineOffsets() {
        var start = editor.selectionStart
        var end = editor.selectionEnd
        var value = editor.text
        if (start === end) return []
        var offsets = []
        var lines = value.split("\n")
        var offset = 0
        for (var i = 0; i < lines.length; ++i) {
            if (lines[i].length === 0 && offset >= start && offset < end)
                offsets.push(offset)
            offset += lines[i].length + 1
        }
        return offsets
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
    function findNext() {
        var query = searchField.text
        if (!query.length) return
        var start = editor.selectionEnd > editor.selectionStart ? editor.selectionEnd : editor.cursorPosition
        var index = editor.text.toLowerCase().indexOf(query.toLowerCase(), start)
        if (index < 0) index = editor.text.toLowerCase().indexOf(query.toLowerCase())
        if (index >= 0) { editor.forceActiveFocus(); editor.select(index, index + query.length) }
    }
    function openSearch() { searchField.visible = true; searchField.forceActiveFocus(); searchField.selectAll() }
    FontMetrics { id: monoMetrics; font: editor.font }
    ColumnLayout {
        anchors.fill: parent
        spacing: 0
        CardHeader {
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
            onDragStarted: sceneX => root.dragStarted(sceneX)
            onDragMoved: sceneX => root.dragMoved(sceneX)
            onDragFinished: sceneX => root.dragFinished(sceneX)
            onStepRequested: direction => root.stepRequested(direction)
        }
        RowLayout {
            Layout.fillWidth: true
            Layout.margins: visible ? 8 : 0
            visible: searchField.visible
            AppTextField {
                id: searchField
                visible: false
                Layout.fillWidth: true
                placeholderText: i18n.catalog["editor.find"]
                onAccepted: root.findNext()
                Keys.onEscapePressed: { visible = false; editor.forceActiveFocus() }
            }
            AppButton { text: i18n.catalog["editor.next"]; onClicked: root.findNext() }
            AppButton { text: "×"; Accessible.name: i18n.catalog["common.close"]; onClicked: { searchField.visible = false; editor.forceActiveFocus() } }
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
                    persistentSelection: Theme.selectionLocked
                    renderType: Text.QtRendering
                    color: Colors.textPrimary
                    selectionColor: Colors.primaryContainer
                    selectedTextColor: Colors.textPrimary
                    font: fontPalette.editorFont(root.editorFontSize)
                    background: Item {
                        Repeater {
                            model: root.selectedBlankLineOffsets()
                            Rectangle {
                                required property int modelData
                                property rect lineRect: {
                                    root.editorFontSize
                                    return editor.positionToRectangle(modelData)
                                }
                                objectName: "selectedBlankLine"
                                x: lineRect.x
                                y: lineRect.y
                                width: Math.max(32, editor.width - lineRect.x - editor.rightPadding)
                                height: lineRect.height
                                radius: 3
                                color: editor.selectionColor
                            }
                        }
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
    Shortcut {
        sequences: [StandardKey.Find]
        enabled: root.visible && (editor.activeFocus || searchField.activeFocus)
        onActivated: root.openSearch()
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
