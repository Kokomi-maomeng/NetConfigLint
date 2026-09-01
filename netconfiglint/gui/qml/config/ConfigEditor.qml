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
    property string subtitle: ""
    property string placeholderText: ""
    property int currentLine: 1
    signal textEdited(string value)
    padding: 0

    function lineNumberText() {
        var count = Math.max(1, editor.lineCount)
        var result = ""
        for (var i = 1; i <= count; ++i) result += i + (i < count ? "\n" : "")
        return result
    }

    function updateCurrentLine() {
        var prefix = editor.text.slice(0, editor.cursorPosition)
        currentLine = prefix.split("\n").length
    }

    function jumpToLine(line) {
        var safeLine = Math.max(1, Math.min(line, editor.lineCount))
        var position = 0
        var lines = editor.text.split("\n")
        for (var i = 1; i < safeLine; ++i) position += lines[i - 1].length + 1
        editor.cursorPosition = position
        editor.forceActiveFocus()
        root.updateCurrentLine()
        Qt.callLater(function() {
            scrollView.contentItem.contentY = Math.max(0, editor.cursorRectangle.y - scrollView.height / 3)
        })
    }

    function findNext() {
        var query = searchField.text
        if (!query.length) return
        var start = Math.min(editor.cursorPosition + 1, editor.length)
        var index = editor.text.toLowerCase().indexOf(query.toLowerCase(), start)
        if (index < 0) index = editor.text.toLowerCase().indexOf(query.toLowerCase())
        if (index >= 0) {
            editor.select(index, index + query.length)
            editor.forceActiveFocus()
        }
    }

    function measuredTextWidth() {
        var lines = editor.text.split("\n")
        var widest = 0
        for (var i = 0; i < lines.length; ++i) {
            var units = 0
            for (var j = 0; j < lines[i].length; ++j) {
                var character = lines[i].charAt(j)
                units += character === "\t" ? 4 : (character.charCodeAt(0) > 255 ? 1 : 0.62)
            }
            widest = Math.max(widest, units * Typography.monospace.pixelSize)
        }
        return widest
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        Rectangle {
            id: editorHeader
            objectName: root.editorObjectName + "Header"
            Layout.fillWidth: true
            Layout.preferredHeight: headerContent.implicitHeight + Spacing.sm * 2
            color: Colors.surfaceContainer
            topLeftRadius: Spacing.radiusCard
            topRightRadius: Spacing.radiusCard
            clip: true

            ColumnLayout {
                id: headerContent
                anchors.fill: parent
                anchors.margins: Spacing.sm
                spacing: Spacing.xs

                RowLayout {
                    Layout.fillWidth: true
                    spacing: Spacing.sm
                    SelectableText {
                        Layout.fillWidth: true
                        text: root.title
                        color: Colors.textPrimary
                        font: Typography.subtitle
                        wrapMode: TextEdit.NoWrap
                        clip: true
                    }
                    SelectableText {
                        text: i18n.catalog["editor.line"] + " " + root.currentLine
                              + " / " + Math.max(1, editor.lineCount)
                        color: Colors.textSecondary
                        font: Typography.caption
                        wrapMode: TextEdit.NoWrap
                    }
                }

                SelectableText {
                    Layout.fillWidth: true
                    visible: root.subtitle.length > 0
                    text: root.subtitle
                    color: Colors.textSecondary
                    font: Typography.caption
                    wrapMode: TextEdit.NoWrap
                    clip: true
                }

                RowLayout {
                    Layout.fillWidth: true
                    visible: searchField.visible
                    spacing: Spacing.xs
                    AppTextField {
                        id: searchField
                        visible: false
                        Layout.fillWidth: true
                        placeholderText: i18n.catalog["editor.find"]
                        onAccepted: root.findNext()
                    }
                    AppButton {
                        text: i18n.catalog["editor.next"]
                        onClicked: root.findNext()
                    }
                }
            }
        }

        Item {
            id: editorBody
            objectName: root.editorObjectName + "Viewport"
            Layout.fillWidth: true
            Layout.fillHeight: true
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
                    objectName: root.editorObjectName
                    width: Math.max(scrollView.availableWidth,
                                    root.measuredTextWidth() + leftPadding + rightPadding)
                    height: Math.max(scrollView.availableHeight,
                                     editor.lineCount * Typography.monospace.pixelSize * 1.35
                                     + topPadding + bottomPadding)
                    leftPadding: lineNumberGutter.width + Spacing.md
                    rightPadding: Spacing.md
                    topPadding: Spacing.md
                    bottomPadding: Spacing.md
                    wrapMode: TextEdit.NoWrap
                    selectByMouse: true
                    persistentSelection: true
                    color: Colors.textPrimary
                    selectionColor: Colors.primaryContainer
                    selectedTextColor: Colors.textPrimary
                    font: Typography.monospace
                    background: Rectangle { color: Colors.editorBackground }
                    onTextChanged: root.textEdited(text)
                    onCursorPositionChanged: root.updateCurrentLine()
                }
            }

            Text {
                anchors.left: parent.left
                anchors.leftMargin: lineNumberGutter.width + Spacing.md
                anchors.right: parent.right
                anchors.rightMargin: Spacing.md
                anchors.top: parent.top
                anchors.topMargin: Spacing.md
                visible: editor.length === 0 && !editor.activeFocus
                text: root.placeholderText
                color: Colors.textSecondary
                font: Typography.monospace
                elide: Text.ElideRight
                clip: true
                z: 3
            }

            Rectangle {
                id: lineNumberGutter
                anchors.left: parent.left
                anchors.top: parent.top
                anchors.bottom: parent.bottom
                width: Math.max(52, lineNumbers.implicitWidth + Spacing.md)
                color: Colors.surfaceContainer
                border.color: Colors.outlineVariant
                border.width: 1
                clip: true
                z: 2

                Text {
                    id: lineNumbers
                    x: Spacing.xs
                    y: editor.topPadding - scrollView.contentItem.contentY
                    width: lineNumberGutter.width - Spacing.md
                    text: root.lineNumberText()
                    color: Colors.textSecondary
                    font: Typography.monospace
                    horizontalAlignment: Text.AlignRight
                }
            }
        }
    }

    Shortcut {
        sequences: [StandardKey.Find]
        onActivated: {
            searchField.visible = true
            searchField.forceActiveFocus()
            searchField.selectAll()
        }
    }
    Shortcut { sequence: "Ctrl+G"; onActivated: jumpDialog.open() }
    Component.onCompleted: {
        syntaxHighlighter.attach(editor.textDocument)
        syntaxHighlighter.setDark(Theme.dark)
    }
    Connections {
        target: Theme
        function onDarkChanged() { syntaxHighlighter.setDark(Theme.dark) }
    }
    AppDialog {
        id: jumpDialog
        title: i18n.catalog["editor.goto"]
        contentItem: AppTextField {
            id: lineField
            implicitHeight: 44
            placeholderText: i18n.catalog["editor.line_number"]
            inputMethodHints: Qt.ImhDigitsOnly
            onAccepted: { root.jumpToLine(parseInt(text)); jumpDialog.close() }
        }
    }
}
