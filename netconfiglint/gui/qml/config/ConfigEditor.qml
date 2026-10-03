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
    property var diagnosticMarkers: []
    readonly property var diagnosticsByLine: {
        var result = ({})
        var markers = diagnosticMarkers || []
        for (var i = 0; i < markers.length; ++i) {
            var marker = markers[i]
            if (!result[marker.line] || marker.severity === "ERROR") result[marker.line] = marker
        }
        return result
    }
    readonly property int totalLineCount: editor.pagedPreview ? editor.previewTotalLines : Math.max(1, editor.lineCount)
    onDiagnosticMarkersChanged: refreshDiagnosticMarkers()
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
    property string completionSourceText: ""
    property int completionCursor: -1
    property var completionDetail: ({})
    property string completionDetailScopeNote: ""
    property var queryResult: ({ items: [], arguments: [] })
    function openCommandQuery() {
        commandQuery.open()
        queryField.forceActiveFocus()
        queryTimer.restart()
    }
    function refreshCommandQuery() {
        queryResult = commandCompletion.request(queryField.text, queryField.text.length)
    }
    function showQueryDetail(index) {
        if (index < 0 || index >= queryResult.items.length) return
        completionDetail = queryResult.items[index]
        completionDetailScopeNote = queryResult.scopeNote || ""
        completionDetails.open()
    }
    function refreshDiagnosticMarkers() {
        syntaxHighlighter.setDiagnosticMarkersFor(editor.textDocument, diagnosticMarkers || [], editor.previewStartLine)
        if (root.showAnalyze) syntaxHighlighter.setUnsupportedLinesFor(editor.textDocument,
            analysisController.resultCurrent ? (analysisController.coverage.unsupported_lines || []) : [], editor.previewStartLine)
    }
    function diagnosticAt(line) {
        return diagnosticsByLine[line] || null
    }
    function argumentRows() {
        var details = completionResult.argumentDetails || []
        if (details.length) return details
        return (completionResult.arguments || []).map(function(token) {
            return { token: token, aliases: [token], description: "", sources: [], syntaxes: [] }
        })
    }
    function argumentDescription(detail) {
        return i18n.catalog["completion.parameter_description." + detail.status] || detail.description || ""
    }
    function filteredArguments() {
        var query = argumentFilter.text.toLowerCase()
        return argumentRows().filter(function(row) {
            return !query || (row.token + " " + (row.aliases || []).join(" ") + " " + root.argumentDescription(row)).toLowerCase().indexOf(query) >= 0
        })
    }
    function showArgumentDetail(detail) {
        completionDetail = { text: (detail.aliases || [detail.token]).join(" / "),
            syntaxes: detail.syntaxes || [], sources: detail.sources || [], views: [], scopes: [],
            annotations: [argumentDescription(detail)] }
        completionDetailScopeNote = completionResult.scopeNote || ""
        completionDetails.open()
    }
    function showCompletionDetail() {
        if (completionList.currentIndex < 0) return
        completionDetail = completionResult.items[completionList.currentIndex]
        completionDetailScopeNote = completionResult.scopeNote || ""
        completionDetails.open()
    }
    function requestCompletion() { requestCompletionInternal(false) }
    function requestCompletionInternal(viewOnly) {
        if ((editor.readOnly && !viewOnly) || editor.selectionStart !== editor.selectionEnd) return
        if (root.completionActive && completionList.count > 0) {
            completionList.currentIndex = (completionList.currentIndex + 1) % completionList.count
            completionList.positionViewAtIndex(completionList.currentIndex, ListView.Contain)
            return
        }
        completionResult = commandCompletion.request(syntaxHighlighter.fullText(editor), syntaxHighlighter.globalPosition(editor, editor.cursorPosition))
        if (editor.pagedPreview) {
            var pageOffset = syntaxHighlighter.globalPosition(editor, 0)
            completionResult.start -= pageOffset
            completionResult.end -= pageOffset
        }
        if (completionResult.insert.length > 0 && !editor.readOnly) {
            var unique = completionResult.items.length === 1
            applyingCompletion = true
            commandCompletion.replace(editor, completionResult.start, completionResult.end, completionResult.insert)
            applyingCompletion = false
            if (unique) { completionPopup.close(); return }
            completionResult = commandCompletion.request(syntaxHighlighter.fullText(editor), syntaxHighlighter.globalPosition(editor, editor.cursorPosition))
            if (editor.pagedPreview) {
                var offset = syntaxHighlighter.globalPosition(editor, 0)
                completionResult.start -= offset
                completionResult.end -= offset
            }
            // Unique keyword completion advances to its argument; no popup is needed yet.
            if (completionResult.start === editor.cursorPosition) return
        }
        completionList.currentIndex = completionResult.items.length > 0 ? 0 : -1
        completionSourceText = editor.text
        completionCursor = editor.cursorPosition
        completionPopup.open()
    }
    function acceptCompletion(index) {
        if (!completionActive || editor.text !== completionSourceText
            || editor.cursorPosition !== completionCursor) return
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
    function selectGlobalRange(start, end) {
        var localStart = syntaxHighlighter.positionInPreview(editor, start)
        editor.select(localStart, Math.min(editor.length, localStart + end - start))
        Qt.callLater(function() {
            scrollView.contentItem.contentY = Math.max(0, Math.min(scrollView.contentItem.contentHeight - scrollView.height,
                editor.positionToRectangle(localStart).y - scrollView.height / 3))
        })
        return localStart
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
            actionText: root.showAnalyze ? (root.analysisBusy ? i18n.catalog["toolbar.analyzing"] : i18n.catalog["toolbar.analyze"]) : (root.showSave ? i18n.catalog["temporary.save_draft"] : "")
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
            Layout.fillWidth: true
            Layout.leftMargin: 12
            Layout.rightMargin: 12
            ToolButton {
                objectName: root.editorObjectName + "CommandQueryButton"
                text: i18n.catalog["completion.query"]
                onClicked: root.openCommandQuery()
            }
            Label {
                Layout.fillWidth: true
                text: editor.pagedPreview ? i18n.catalog["editor.preview_hint"] : i18n.catalog["completion.query_shortcut"]
                color: Colors.textSecondary
                font: Typography.caption
                wrapMode: Text.Wrap
            }
            ToolButton {
                objectName: root.editorObjectName + "PagePrevious"
                text: "‹"
                visible: editor.pagedPreview
                enabled: editor.previewPage > 1
                onClicked: syntaxHighlighter.stepPreviewPage(editor, -1)
            }
            Label { visible: editor.pagedPreview; text: editor.previewPage + " / " + editor.previewPageCount; color: Colors.textSecondary }
            ToolButton {
                objectName: root.editorObjectName + "PageNext"
                text: "›"
                visible: editor.pagedPreview
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
                    property bool previewLoading: false
                    property int previewPage: 1
                    property int previewPageCount: 1
                    property int previewStartLine: 1
                    property int previewTotalLines: 1
                    readOnly: root.readOnly
                    onPreviewStartLineChanged: root.refreshDiagnosticMarkers()
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
                        if (event.key === Qt.Key_Shift || event.key === Qt.Key_Control
                            || event.key === Qt.Key_Alt || event.key === Qt.Key_Meta) return
                        if (event.key === Qt.Key_Space && (event.modifiers & Qt.ControlModifier) && (event.modifiers & Qt.ShiftModifier)) {
                            root.openCommandQuery(); event.accepted = true; return
                        }
                        if (event.key === Qt.Key_Space && (event.modifiers & Qt.ControlModifier)) {
                            root.requestCompletionInternal(true); event.accepted = true; return
                        }
                        if ((event.key === Qt.Key_Tab || event.key === Qt.Key_Backtab)
                            && (event.modifiers & Qt.ControlModifier)) {
                            completionPopup.close()
                            var previous = event.key === Qt.Key_Backtab || (event.modifiers & Qt.ShiftModifier)
                            var target = editor.nextItemInFocusChain(!previous)
                            if (target) target.forceActiveFocus(Qt.TabFocusReason)
                            event.accepted = true
                            return
                        }
                        if (root.completionActive && event.key === Qt.Key_F1) {
                            root.showCompletionDetail(); event.accepted = true; return
                        }
                        if (root.completionActive && event.key === Qt.Key_F2 && root.argumentRows().length) {
                            argumentDialog.open(); event.accepted = true; return
                        }
                        if ((event.key === Qt.Key_Tab || event.key === Qt.Key_Backtab)
                            && !(event.modifiers & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier))
                            && !editor.readOnly) {
                            if ((event.key === Qt.Key_Backtab || (event.modifiers & Qt.ShiftModifier))
                                && root.completionActive && completionList.count > 0) {
                                completionList.currentIndex = (completionList.currentIndex + completionList.count - 1) % completionList.count
                                completionList.positionViewAtIndex(completionList.currentIndex, ListView.Contain)
                            } else if (event.key === Qt.Key_Backtab || (event.modifiers & Qt.ShiftModifier)) {
                                var previousTarget = editor.nextItemInFocusChain(false)
                                if (previousTarget) previousTarget.forceActiveFocus(Qt.BacktabFocusReason)
                            } else if (editor.selectionStart === editor.selectionEnd) root.requestCompletion()
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
                    onTextChanged: {
                        if (!root.applyingCompletion) completionPopup.close()
                        if (!previewLoading && !root.readOnly) root.textEdited(syntaxHighlighter.commitPreviewText(editor, text))
                        Qt.callLater(root.updateCurrentLine)
                    }
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
                width: Math.ceil(monoMetrics.advanceWidth(String(root.totalLineCount))) + 28
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
                        readonly property int globalLine: lineNumberGutter.firstLine + index + editor.previewStartLine
                        readonly property var marker: root.diagnosticAt(globalLine)
                        objectName: root.editorObjectName + "Line" + globalLine
                        x: 22
                        y: editor.topPadding + (lineNumberGutter.firstLine + index) * lineNumberGutter.lineHeight
                            - scrollView.contentItem.contentY
                        width: lineNumberGutter.width - 28
                        height: lineNumberGutter.lineHeight
                        text: globalLine
                        color: Colors.textSecondary
                        font: editor.font
                        renderType: Text.QtRendering
                        horizontalAlignment: Text.AlignRight
                        Text {
                            objectName: root.editorObjectName + "Diagnostic" + parent.globalLine
                            x: -18
                            width: 16
                            height: parent.height
                            visible: parent.marker !== null
                            text: parent.marker && parent.marker.severity === "ERROR" ? "!" : "•"
                            color: parent.marker ? Colors.severity(parent.marker.severity) : Colors.textSecondary
                            font.bold: true
                            horizontalAlignment: Text.AlignHCenter
                            HoverHandler { id: diagnosticHover }
                            AppToolTip { visible: diagnosticHover.hovered; text: parent.parent.marker
                                ? parent.parent.marker.rule_id + " · " + parent.parent.marker.message : "" }
                        }
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
        height: Math.min(360, contentColumn.preferredHeight + padding * 2, parent ? parent.height - 24 : 360)
        property point caretPoint: editor.mapToItem(parent, editor.cursorRectangle.x, editor.cursorRectangle.y)
        x: parent ? Math.max(12, Math.min(parent.width - width - 12, caretPoint.x)) : 0
        y: parent ? Math.max(12, Math.min(parent.height - height - 12, caretPoint.y + editor.cursorRectangle.height + 4)) : 0
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        background: Rectangle { color: Colors.surfaceContainerHigh; radius: 12; border.color: Colors.outline }
        contentItem: ColumnLayout {
            id: contentColumn
            spacing: 8
            // Derive desired rows independently of the layout's allocated height.
            // Native layouts can otherwise collapse a fill-height ListView to zero.
            readonly property real preferredHeight: completionHeading.implicitHeight
                + completionActions.implicitHeight + spacing
                + (completionEmpty.visible ? completionEmpty.implicitHeight + spacing : 0)
                + (completionList.count > 0 ? Math.min(280, completionList.count * 64) + spacing : 0)
            Label {
                id: completionHeading
                Layout.fillWidth: true
                font: Typography.caption
                color: Colors.textSecondary
                text: (root.completionResult.vendors || []).join(" / ") + " · " + i18n.catalog["completion.keys"]
                wrapMode: Text.Wrap
            }
            RowLayout {
                id: completionActions
                Layout.fillWidth: true
                AppButton {
                    objectName: root.editorObjectName + "CompletionDetailsButton"
                    text: i18n.catalog["completion.details"] + " · F1"
                    enabled: completionList.currentIndex >= 0
                    onClicked: root.showCompletionDetail()
                }
                AppButton {
                    objectName: root.editorObjectName + "AllArgumentsButton"
                    text: i18n.catalog["completion.all_arguments"] + " (" + (root.completionResult.arguments || []).length + ") · F2"
                    visible: root.argumentRows().length > 0
                    onClicked: argumentDialog.open()
                }
                Item { Layout.fillWidth: true }
            }
            Label {
                id: completionEmpty
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
                Layout.preferredHeight: Math.min(280, count * 64)
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
    AppDialog {
        id: completionDetails
        objectName: root.editorObjectName + "CompletionDetails"
        title: i18n.catalog["completion.details"]
        height: Math.min(620, Overlay.overlay ? Overlay.overlay.height - 32 : 620)
        standardButtons: Dialog.Close
        contentItem: ScrollView {
            id: detailScroll
            clip: true
            contentWidth: availableWidth
            Column {
                id: detailContent
                width: detailScroll.availableWidth
                spacing: 12
                SelectableText { width: parent.width; text: root.completionDetail.text || ""; font: fontPalette.editorFont(16); color: Colors.textPrimary; wrapMode: TextEdit.Wrap }
                SelectableText { objectName: root.editorObjectName + "CompletionSyntaxes"; width: parent.width; text: (root.completionDetail.syntaxes || [root.completionDetail.syntax || ""]).join("\n\n"); font: fontPalette.editorFont(13); color: Colors.textPrimary; wrapMode: TextEdit.Wrap }
                SelectableText { objectName: root.editorObjectName + "CompletionViews"; width: parent.width; text: i18n.catalog["completion.views"] + " " + (root.completionDetail.views || []).join(" / "); color: Colors.textSecondary; wrapMode: TextEdit.Wrap }
                SelectableText { width: parent.width; text: i18n.catalog["completion.scope"] + "\n" + (root.completionDetail.scopes || []).join("\n") + "\n" + (i18n.catalog["completion.scope_note"] || root.completionDetailScopeNote); color: Colors.textSecondary; wrapMode: TextEdit.Wrap }
                SelectableText { width: parent.width; text: (root.completionDetail.annotations || []).join("\n"); color: Colors.textSecondary; wrapMode: TextEdit.Wrap }
                Repeater {
                    model: (root.completionDetail.syntaxDetails || []).length ? []
                        : root.completionDetail.sources || (root.completionDetail.source ? [root.completionDetail.source] : [])
                    AppButton {
                        required property string modelData
                        required property int index
                        width: parent.width
                        text: i18n.catalog["completion.open_source"] + " " + (index + 1)
                        ToolTip.visible: hovered
                        ToolTip.text: modelData
                        onClicked: Qt.openUrlExternally(modelData)
                    }
                }
                Repeater {
                    model: root.completionDetail.syntaxDetails || []
                    Column {
                        required property var modelData
                        width: parent.width
                        spacing: 6
                        SelectableText { width: parent.width; text: modelData.syntax; font: fontPalette.editorFont(13); color: Colors.textPrimary; wrapMode: TextEdit.Wrap }
                        SelectableText { width: parent.width; text: (modelData.views || []).join(" / ") + "\n" + (modelData.scopes || []).join("\n") + "\n" + (modelData.annotations || []).join("\n"); color: Colors.textSecondary; wrapMode: TextEdit.Wrap }
                        Repeater {
                            model: modelData.sources || []
                            AppButton { required property string modelData; required property int index; width: parent.width; text: i18n.catalog["completion.open_source"] + " " + (index + 1); ToolTip.visible: hovered; ToolTip.text: modelData; onClicked: Qt.openUrlExternally(modelData) }
                        }
                    }
                }
            }
        }
        onClosed: {
            if (argumentDialog.visible) argumentFilter.forceActiveFocus()
            else if (commandQuery.visible) queryField.forceActiveFocus()
            else editor.forceActiveFocus()
        }
    }
    Timer { id: queryTimer; interval: 160; onTriggered: root.refreshCommandQuery() }
    AppDialog {
        id: commandQuery
        objectName: root.editorObjectName + "CommandQuery"
        title: i18n.catalog["completion.query"]
        height: Math.min(640, Overlay.overlay ? Overlay.overlay.height - 32 : 640)
        standardButtons: Dialog.Close
        contentItem: ColumnLayout {
            AppTextField {
                id: queryField
                objectName: root.editorObjectName + "CommandQueryField"
                Layout.fillWidth: true
                implicitHeight: 44
                placeholderText: ""
                Text {
                    anchors.left: parent.left
                    anchors.leftMargin: queryField.leftPadding
                    anchors.right: parent.right
                    anchors.rightMargin: queryField.rightPadding
                    anchors.verticalCenter: parent.verticalCenter
                    visible: queryField.text.length === 0
                    text: i18n.catalog["completion.query_placeholder"]
                    color: Colors.textSecondary
                    font: queryField.font
                    elide: Text.ElideRight
                }
                onTextChanged: queryTimer.restart()
                onAccepted: { root.refreshCommandQuery(); if (queryList.count) root.showQueryDetail(Math.max(0, queryList.currentIndex)) }
                Keys.onDownPressed: { queryList.forceActiveFocus(); if (queryList.count) queryList.currentIndex = 0 }
            }
            Label { Layout.fillWidth: true; text: i18n.catalog["completion.query_scope_note"]; color: Colors.textSecondary; font: Typography.caption; wrapMode: Text.Wrap }
            Label { Layout.fillWidth: true; text: queryList.count + " · " + i18n.catalog["completion.query_narrow_hint"]; color: Colors.textSecondary; font: Typography.caption; wrapMode: Text.Wrap }
            ListView {
                id: queryList
                objectName: root.editorObjectName + "CommandQueryList"
                Layout.fillWidth: true
                Layout.fillHeight: true
                model: root.queryResult.items || []
                activeFocusOnTab: true
                keyNavigationEnabled: true
                clip: true
                boundsBehavior: Flickable.StopAtBounds
                ScrollBar.vertical: AppScrollBar {}
                Keys.onReturnPressed: root.showQueryDetail(currentIndex)
                Keys.onEnterPressed: root.showQueryDetail(currentIndex)
                Keys.onEscapePressed: queryField.forceActiveFocus()
                delegate: ItemDelegate {
                    required property var modelData
                    required property int index
                    width: ListView.view.width
                    height: 64
                    highlighted: ListView.isCurrentItem
                    onClicked: root.showQueryDetail(index)
                    contentItem: Column {
                        spacing: 3
                        Label { width: parent.width; text: modelData.text + " · " + modelData.vendors.join(" / "); font: fontPalette.editorFont(14); color: Colors.textPrimary; elide: Text.ElideRight }
                        Label { width: parent.width; text: (modelData.views || []).join(" / ") + " · " + modelData.syntax; font: Typography.caption; color: Colors.textSecondary; elide: Text.ElideRight }
                    }
                }
            }
        }
    }
    AppDialog {
        id: argumentDialog
        objectName: root.editorObjectName + "ArgumentDialog"
        title: i18n.catalog["completion.all_arguments"] + " (" + (root.completionResult.arguments || []).length + ")"
        height: Math.min(640, Overlay.overlay ? Overlay.overlay.height - 32 : 640)
        standardButtons: Dialog.Close
        onOpened: argumentFilter.forceActiveFocus()
        onClosed: editor.forceActiveFocus()
        contentItem: ColumnLayout {
            AppTextField {
                id: argumentFilter
                objectName: root.editorObjectName + "ArgumentFilter"
                Layout.fillWidth: true
                implicitHeight: 44
                placeholderText: ""
                Text {
                    anchors.left: parent.left
                    anchors.leftMargin: argumentFilter.leftPadding
                    anchors.right: parent.right
                    anchors.rightMargin: argumentFilter.rightPadding
                    anchors.verticalCenter: parent.verticalCenter
                    visible: argumentFilter.text.length === 0
                    text: i18n.catalog["completion.filter_arguments"]
                    color: Colors.textSecondary
                    font: argumentFilter.font
                    elide: Text.ElideRight
                }
            }
            Label { Layout.fillWidth: true; text: i18n.catalog["completion.argument_source_note"]; wrapMode: Text.Wrap; font: Typography.caption; color: Colors.textSecondary }
            ListView {
                id: argumentList
                objectName: root.editorObjectName + "ArgumentList"
                Layout.fillWidth: true
                Layout.fillHeight: true
                model: root.filteredArguments()
                activeFocusOnTab: true
                keyNavigationEnabled: true
                highlight: Rectangle { color: Colors.primaryContainer; radius: 6; opacity: 0.35 }
                Keys.onReturnPressed: if (currentIndex >= 0) root.showArgumentDetail(root.filteredArguments()[currentIndex])
                Keys.onEnterPressed: if (currentIndex >= 0) root.showArgumentDetail(root.filteredArguments()[currentIndex])
                clip: true
                boundsBehavior: Flickable.StopAtBounds
                ScrollBar.vertical: AppScrollBar {}
                delegate: Item {
                    required property var modelData
                    width: ListView.view.width
                    height: argumentRow.implicitHeight + 20
                    Column {
                        id: argumentRow
                        width: parent.width
                        spacing: 6
                        SelectableText { width: parent.width; text: (modelData.aliases || [modelData.token]).join(" / "); font: fontPalette.editorFont(14); color: Colors.textPrimary; wrapMode: TextEdit.Wrap }
                        SelectableText { width: parent.width; text: root.argumentDescription(modelData); color: Colors.textSecondary; wrapMode: TextEdit.Wrap }
                        AppButton { width: parent.width; text: i18n.catalog["completion.details"] + " (" + (modelData.syntaxes || []).length + ")"; onClicked: root.showArgumentDetail(modelData) }
                    }
                }
            }
        }
    }
    Connections { target: commandCompletion; function onChanged() { completionPopup.close() } }
    Shortcut { sequence: Qt.platform.os === "osx" ? "Meta+G" : "Ctrl+G"; enabled: root.visible && editor.activeFocus; onActivated: jumpDialog.open() }
    Shortcut { sequences: [StandardKey.ZoomIn, Qt.platform.os === "osx" ? "Meta+=" : "Ctrl+="]; enabled: root.visible && editor.activeFocus; onActivated: root.zoom(1) }
    Shortcut { sequences: [StandardKey.ZoomOut]; enabled: root.visible && editor.activeFocus; onActivated: root.zoom(-1) }
    Component.onCompleted: { syntaxHighlighter.attach(editor.textDocument); syntaxHighlighter.setDark(Theme.dark); refreshDiagnosticMarkers() }
    Connections { target: Theme; function onDarkChanged() { syntaxHighlighter.setDark(Theme.dark) } }
    Connections {
        target: analysisController
        function onResultCurrentChanged() {
            root.refreshDiagnosticMarkers()
        }
    }
    AppDialog {
        id: jumpDialog
        objectName: root.editorObjectName + "JumpDialog"
        title: i18n.catalog["editor.goto"]
        contentItem: AppTextField {
            id: lineField
            objectName: root.editorObjectName + "LineField"
            implicitHeight: 44
            placeholderText: i18n.catalog["editor.line_number"]
            validator: IntValidator { bottom: 1; top: root.totalLineCount }
            inputMethodHints: Qt.ImhDigitsOnly
            onAccepted: if (acceptableInput) { root.jumpToLine(Number(text)); jumpDialog.close() }
        }
    }
}
