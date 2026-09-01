import QtQuick
import theme 1.0

TextEdit {
    id: control
    property color linkColor: Colors.primary
    readOnly: true
    selectByMouse: true
    persistentSelection: true
    activeFocusOnPress: true
    color: Colors.textPrimary
    font: Typography.body
    selectionColor: Colors.primaryContainer
    selectedTextColor: Colors.textPrimary
    wrapMode: TextEdit.Wrap
    textFormat: TextEdit.AutoText
    Keys.onPressed: event => {
        if (event.matches(StandardKey.Copy)) {
            control.copy()
            event.accepted = true
        }
    }
    onLinkActivated: link => Qt.openUrlExternally(link)
}
