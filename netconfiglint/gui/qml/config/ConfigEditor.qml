import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import theme 1.0
import "../components"

AppCard {
    id: root
    property alias text: editor.text
    property alias editor: editor
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

    ColumnLayout {
        anchors.fill: parent
        spacing: 0
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 44
            color: Colors.surfaceContainer
            radius: Spacing.radiusCard
            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: Spacing.md
                anchors.rightMargin: Spacing.md
                Text { text: "Configuration"; color: Colors.textPrimary; font: Typography.subtitle }
                Text {
                    text: "Line " + root.currentLine + " / " + Math.max(1, editor.lineCount)
                    color: Colors.textSecondary
                    font: Typography.caption
                }
                Item { Layout.fillWidth: true }
                AppTextField {
                    id: searchField
                    visible: false
                    Layout.preferredWidth: 220
                    placeholderText: "Find in configuration"
                    onAccepted: root.findNext()
                }
                AppButton {
                    visible: searchField.visible
                    text: "Next"
                    onClicked: root.findNext()
                }
            }
        }
        ScrollView {
            id: scrollView
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            ScrollBar.horizontal.policy: ScrollBar.AsNeeded
            ScrollBar.vertical.policy: ScrollBar.AsNeeded

            Row {
                height: Math.max(scrollView.availableHeight, editor.contentHeight + Spacing.md * 2)
                Rectangle {
                    width: Math.max(48, lineNumbers.implicitWidth + Spacing.md)
                    height: parent.height
                    color: Colors.surfaceContainer
                    Text {
                        id: lineNumbers
                        anchors.top: parent.top
                        anchors.topMargin: Spacing.md
                        anchors.right: parent.right
                        anchors.rightMargin: Spacing.sm
                        text: root.lineNumberText()
                        color: Colors.textSecondary
                        font: Typography.monospace
                        horizontalAlignment: Text.AlignRight
                    }
                }
                TextArea {
                    id: editor
                    width: Math.max(scrollView.availableWidth - 48, contentWidth + Spacing.xl)
                    height: Math.max(scrollView.availableHeight, contentHeight + Spacing.md * 2)
                    leftPadding: Spacing.md
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
        }
    }

    Shortcut {
        sequence: StandardKey.Find
        onActivated: {
            searchField.visible = true
            searchField.forceActiveFocus()
            searchField.selectAll()
        }
    }
    Shortcut { sequence: "Ctrl+G"; onActivated: jumpDialog.open() }
    AppDialog {
        id: jumpDialog
        title: "Go to line"
        contentItem: AppTextField {
            id: lineField
            placeholderText: "Line number"
            inputMethodHints: Qt.ImhDigitsOnly
            onAccepted: { root.jumpToLine(parseInt(text)); jumpDialog.close() }
        }
    }
}
