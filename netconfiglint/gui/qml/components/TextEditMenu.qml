import QtQuick
import QtQuick.Controls
import theme 1.0
AppMenu {
    id: menu
    property var editor
    property var zoomTarget: null
    objectName: "textEditMenu"
    onAboutToShow: Theme.selectionLocked = true
    onClosed: Theme.selectionLocked = false
    MenuItem { text: i18n.catalog["edit.undo"]; enabled: menu.editor.canUndo; onTriggered: menu.editor.undo() }
    MenuItem { text: i18n.catalog["edit.redo"]; enabled: menu.editor.canRedo; onTriggered: menu.editor.redo() }
    MenuSeparator { }
    MenuItem { text: i18n.catalog["edit.cut"]; enabled: menu.editor.selectedText.length > 0 && !menu.editor.readOnly; onTriggered: menu.editor.cut() }
    MenuItem { text: i18n.catalog["edit.copy"]; enabled: menu.editor.selectedText.length > 0; onTriggered: menu.editor.copy() }
    MenuItem { text: i18n.catalog["edit.paste"]; enabled: menu.editor.canPaste && !menu.editor.readOnly; onTriggered: menu.editor.paste() }
    MenuItem { text: i18n.catalog["edit.select_all"]; enabled: menu.editor.length > 0; onTriggered: menu.editor.selectAll() }
    MenuSeparator { visible: menu.zoomTarget !== null && menu.zoomTarget.zoomModified; height: visible ? implicitHeight : 0 }
    MenuItem {
        objectName: "resetEditorZoom"
        visible: menu.zoomTarget !== null && menu.zoomTarget.zoomModified
        height: visible ? implicitHeight : 0
        text: i18n.catalog["edit.reset_zoom"]
        onTriggered: menu.zoomTarget.resetZoom()
    }
}
