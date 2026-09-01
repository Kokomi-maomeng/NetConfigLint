import QtQuick
import QtQuick.Layouts
import theme 1.0

TextEdit {
    id: control
    property color linkColor: Colors.primary
    Layout.preferredWidth: Math.max(1, Math.ceil(contentWidth))
    Layout.preferredHeight: Math.max(1, Math.ceil(contentHeight))
    readOnly: true
    selectByMouse: true
    persistentSelection: true
    activeFocusOnPress: true
    color: Colors.textPrimary
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
