import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import theme 1.0
import "../components"
AppCard {
    id: root
    property alias text: editor.text
    property alias editor: editor
    property string editorObjectName: "configEditorTextArea"
    property string title: i18n.catalog["editor.configuration"]
    property int currentLine: 1
    property int editorFontSize: Typography.monospace.pixelSize
    property bool zoomModified: false
    signal textEdited(string value)
    signal dragStarted()
    signal dragMoved(real sceneX)
    signal dragFinished(real sceneX)
    signal stepRequested(int direction)
    padding: 0
    function resetZoom() { editorFontSize = Typography.monospace.pixelSize; zoomModified = false }
    function zoom(delta) { editorFontSize = Math.max(9, Math.min(40, editorFontSize + delta)); zoomModified = true }
    function lineNumberText() {
        var result = []
        for (var i = 1; i <= Math.max(1, editor.lineCount); ++i) result.push(i)
        return result.join("\n")
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
    FontMetrics { id: monoMetrics; font: editor.font }
    ColumnLayout {
        anchors.fill: parent
        spacing: 0
        CardHeader {
            objectName: root.editorObjectName + "Header"
            Layout.fillWidth: true
            Layout.preferredHeight: 60
            title: root.title
            detail: root.currentLine + " / " + Math.max(1, editor.lineCount)
            onDragStarted: root.dragStarted()
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
                ScrollBar.horizontal: AppScrollBar { }
                ScrollBar.vertical: AppScrollBar { }
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
                    renderType: Text.NativeRendering
                    color: Colors.textPrimary
                    selectionColor: Colors.primaryContainer
                    selectedTextColor: Colors.textPrimary
                    font: fontPalette.editorFont(root.editorFontSize)
                    background: Item { }
                    ContextMenu.menu: TextEditMenu { editor: root.editor; zoomTarget: root }
                    onTextChanged: root.textEdited(text)
                    onCursorPositionChanged: root.currentLine = text.slice(0, cursorPosition).split("\n").length
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
                Rectangle { anchors.right: parent.right; width: 1; height: parent.height; color: Qt.alpha(Colors.outlineVariant, 0.5) }
                Text {
                    x: 6
                    y: editor.topPadding - scrollView.contentItem.contentY
                    width: lineNumberGutter.width - 12
                    text: root.lineNumberText()
                    color: Colors.textSecondary
                    font: editor.font
                    renderType: Text.NativeRendering
                    horizontalAlignment: Text.AlignRight
                }
            }
        }
    }
    Shortcut {
        sequences: [StandardKey.Find]
        enabled: root.visible && (editor.activeFocus || searchField.activeFocus)
        onActivated: { searchField.visible = true; searchField.forceActiveFocus(); searchField.selectAll() }
    }
    Shortcut { sequence: "Ctrl+G"; enabled: root.visible && editor.activeFocus; onActivated: jumpDialog.open() }
    Component.onCompleted: { syntaxHighlighter.attach(editor.textDocument); syntaxHighlighter.setDark(Theme.dark) }
    Connections { target: Theme; function onDarkChanged() { syntaxHighlighter.setDark(Theme.dark) } }
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
