import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import theme 1.0
import "../components"
AppCard {
    id: root
    property alias text: editor.text
    property bool readOnly: false
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
    property var completionResult: ({ items: [], arguments: [] })
    property bool applyingCompletion: false
    property bool completionActive: false
    function requestCompletion() {
        if (editor.readOnly || editor.selectionStart !== editor.selectionEnd) return
        if (root.completionActive && completionList.count > 0) {
            completionList.currentIndex = (completionList.currentIndex + 1) % completionList.count
            completionList.positionViewAtIndex(completionList.currentIndex, ListView.Contain)
            return
        }
        completionResult = commandCompletion.request(editor.text, editor.cursorPosition)
        if (completionResult.insert.length > 0) {
            var unique = completionResult.items.length === 1
            applyingCompletion = true
            commandCompletion.replace(editor, completionResult.start, completionResult.end, completionResult.insert)
            applyingCompletion = false
            if (unique) { completionPopup.close(); return }
            completionResult = commandCompletion.request(editor.text, editor.cursorPosition)
            // Unique keyword completion advances to its argument; no popup is needed yet.
            if (completionResult.start === editor.cursorPosition) return
        }
        completionList.currentIndex = completionResult.items.length > 0 ? 0 : -1
        completionPopup.open()
    }
    function acceptCompletion(index) {
        if (index < 0 || index >= completionResult.items.length) return
        var end = completionResult.end
        var suffix = end < editor.length && /\s/.test(editor.text[end]) ? "" : " "
        applyingCompletion = true
        commandCompletion.replace(editor, completionResult.start, end, completionResult.items[index].text + suffix)
        applyingCompletion = false
        completionPopup.close()
        editor.forceActiveFocus()
    }
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
    function updateCurrentLine() {
        var value = editor.text
        var count = 1
        var offset = value.indexOf("\n")
        while (offset >= 0 && offset < editor.cursorPosition) { count++; offset = value.indexOf("\n", offset + 1) }
        currentLine = count
    }
    function jumpToLine(line) {
        if (!isFinite(line)) return
        var relativeLine = syntaxHighlighter.lineInPreview(editor, Math.floor(line))
        var safeLine = Math.max(1, Math.min(relativeLine, editor.lineCount))
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
            onActionClicked: { if (root.showSave) root.saveRequested(syntaxHighlighter.fullText(editor)); else root.analyzeRequested() }
            detail: (root.currentLine + editor.previewStartLine - 1) + " / " + (editor.pagedPreview ? editor.previewTotalLines : Math.max(1, editor.lineCount))
            minimumDetailDigits: Math.max(5, String(root.currentLine).length, String(Math.max(1, editor.lineCount)).length)
            onDragStarted: sceneX => root.dragStarted(sceneX)
            onDragMoved: sceneX => root.dragMoved(sceneX)
            onDragFinished: sceneX => root.dragFinished(sceneX)
            onStepRequested: direction => root.stepRequested(direction)
        }
        RowLayout {
            visible: editor.pagedPreview
            Layout.fillWidth: true
            Layout.leftMargin: 12
            Layout.rightMargin: 12
            Label {
                Layout.fillWidth: true
                text: i18n.catalog["editor.preview_hint"]
                color: Colors.textSecondary
                font: Typography.caption
                wrapMode: Text.Wrap
            }
            ToolButton {
                objectName: root.editorObjectName + "PagePrevious"
                text: "‹"
                enabled: editor.previewPage > 1
                onClicked: syntaxHighlighter.stepPreviewPage(editor, -1)
            }
            Label { text: editor.previewPage + " / " + editor.previewPageCount; color: Colors.textSecondary }
            ToolButton {
                objectName: root.editorObjectName + "PageNext"
                text: "›"
                enabled: editor.previewPage < editor.previewPageCount
                onClicked: syntaxHighlighter.stepPreviewPage(editor, 1)
            }
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
                    property bool pagedPreview: false
                    property int previewPage: 1
                    property int previewPageCount: 1
                    property int previewStartLine: 1
                    property int previewTotalLines: 1
                    readOnly: root.readOnly || pagedPreview
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
                        if ((event.key === Qt.Key_Tab || event.key === Qt.Key_Backtab)
                            && !(event.modifiers & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier))
                            && !editor.readOnly) {
                            if (event.key === Qt.Key_Backtab && root.completionActive && completionList.count > 0) {
                                completionList.currentIndex = (completionList.currentIndex + completionList.count - 1) % completionList.count
                                completionList.positionViewAtIndex(completionList.currentIndex, ListView.Contain)
                            } else root.requestCompletion()
                            event.accepted = true
                            return
                        }
                        if (root.completionActive) {
                            if (event.key === Qt.Key_Escape) {
                                completionPopup.close(); event.accepted = true; return
                            }
                            if ((event.key === Qt.Key_Return || event.key === Qt.Key_Enter) && completionList.currentIndex >= 0) {
                                root.acceptCompletion(completionList.currentIndex); event.accepted = true; return
                            }
                            if ((event.key === Qt.Key_Down || event.key === Qt.Key_Up) && completionList.count > 0) {
                                var direction = event.key === Qt.Key_Down ? 1 : -1
                                completionList.currentIndex = (completionList.currentIndex + direction + completionList.count) % completionList.count
                                completionList.positionViewAtIndex(completionList.currentIndex, ListView.Contain)
                                event.accepted = true; return
                            }
                            completionPopup.close()
                        }
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
                    onTextChanged: { if (!root.applyingCompletion) completionPopup.close(); if (!pagedPreview) root.textEdited(text); Qt.callLater(root.updateCurrentLine) }
                    onCursorPositionChanged: { if (!root.applyingCompletion) completionPopup.close(); Qt.callLater(root.updateCurrentLine) }
                    onActiveFocusChanged: if (!activeFocus) completionPopup.close()
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
                readonly property real lineHeight: Math.max(1, editor.positionToRectangle(0).height)
                readonly property int firstLine: Math.max(0, Math.floor((scrollView.contentItem.contentY - editor.topPadding) / lineHeight))
                Repeater {
                    model: Math.max(0, Math.min(editor.lineCount - lineNumberGutter.firstLine,
                        Math.ceil(lineNumberGutter.height / lineNumberGutter.lineHeight) + 3))
                    Text {
                        required property int index
                        x: 6
                        y: editor.topPadding + (lineNumberGutter.firstLine + index) * lineNumberGutter.lineHeight
                            - scrollView.contentItem.contentY
                        width: lineNumberGutter.width - 12
                        height: lineNumberGutter.lineHeight
                        text: lineNumberGutter.firstLine + index + 1
                        color: Colors.textSecondary
                        font: editor.font
                        renderType: Text.QtRendering
                        horizontalAlignment: Text.AlignRight
                    }
                }
            }
        }
    }
    Popup {
        id: completionPopup
        objectName: root.editorObjectName + "CompletionPopup"
        parent: Overlay.overlay
        popupType: Popup.Item
        modal: false
        focus: false
        onAboutToShow: root.completionActive = true
        onAboutToHide: root.completionActive = false
        padding: 12
        width: parent ? Math.min(520, parent.width - 24) : 520
        height: Math.min(360, contentColumn.implicitHeight + padding * 2, parent ? parent.height - 24 : 360)
        property point caretPoint: editor.mapToItem(parent, editor.cursorRectangle.x, editor.cursorRectangle.y)
        x: parent ? Math.max(12, Math.min(parent.width - width - 12, caretPoint.x)) : 0
        y: parent ? Math.max(12, Math.min(parent.height - height - 12, caretPoint.y + editor.cursorRectangle.height + 4)) : 0
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        background: Rectangle { color: Colors.surfaceContainerHigh; radius: 12; border.color: Colors.outline }
        contentItem: ColumnLayout {
            id: contentColumn
            spacing: 8
            Label {
                Layout.fillWidth: true
                font: Typography.caption
                color: Colors.textSecondary
                text: (root.completionResult.vendors || []).join(" / ") + " · " + i18n.catalog["completion.keys"]
                wrapMode: Text.Wrap
            }
            Label {
                Layout.fillWidth: true
                visible: (root.completionResult.arguments || []).length > 0
                text: i18n.catalog["completion.argument"] + " " + (root.completionResult.arguments || []).slice(0, 8).join(" / ")
                textFormat: Text.PlainText
                color: Colors.textSecondary
                font: Typography.caption
                wrapMode: Text.Wrap
            }
            Label {
                Layout.fillWidth: true
                visible: completionList.count === 0 && (root.completionResult.arguments || []).length === 0
                text: i18n.catalog["completion.no_match"]
                color: Colors.textSecondary
                font: Typography.body
                wrapMode: Text.Wrap
            }
            ListView {
                id: completionList
                objectName: root.editorObjectName + "CompletionList"
                Layout.fillWidth: true
                Layout.fillHeight: true
                implicitHeight: Math.min(280, count * 64)
                model: root.completionResult.items
                clip: true
                boundsBehavior: Flickable.StopAtBounds
                ScrollBar.vertical: AppScrollBar {}
                delegate: ItemDelegate {
                    required property var modelData
                    required property int index
                    width: ListView.view.width
                    height: 64
                    focusPolicy: Qt.NoFocus
                    highlighted: ListView.isCurrentItem
                    onClicked: root.acceptCompletion(index)
                    contentItem: Column {
                        spacing: 3
                        Label { width: parent.width; text: modelData.text + "    " + modelData.vendors.join(" / "); textFormat: Text.PlainText; font: fontPalette.editorFont(14); color: Colors.textPrimary; elide: Text.ElideRight }
                        Label { width: parent.width; text: modelData.syntax; textFormat: Text.PlainText; font: Typography.caption; color: Colors.textSecondary; elide: Text.ElideRight }
                    }
                }
            }
        }
    }
    Connections { target: commandCompletion; function onChanged() { completionPopup.close() } }
    Shortcut { sequence: Qt.platform.os === "osx" ? "Meta+G" : "Ctrl+G"; enabled: root.visible && editor.activeFocus; onActivated: jumpDialog.open() }
    Shortcut { sequences: [StandardKey.ZoomIn, Qt.platform.os === "osx" ? "Meta+=" : "Ctrl+="]; enabled: root.visible && editor.activeFocus; onActivated: root.zoom(1) }
    Shortcut { sequences: [StandardKey.ZoomOut]; enabled: root.visible && editor.activeFocus; onActivated: root.zoom(-1) }
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
