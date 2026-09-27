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
    AppMenuItem {
        objectName: "editorSearchMenuItem"
        visible: menu.zoomTarget !== null
        height: visible ? implicitHeight : 0
        text: i18n.catalog["editor.search"]
        icon.source: Qt.resolvedUrl("../../../resources/icons/edit-search.svg")
        onTriggered: menu.zoomTarget.searchOpenRequested()
    }
    MenuSeparator { visible: menu.zoomTarget !== null; height: visible ? implicitHeight : 0 }
    AppMenuItem { objectName: "editorUndoMenuItem"; text: i18n.catalog["edit.undo"]; icon.source: Qt.resolvedUrl("../../../resources/icons/edit-undo.svg"); enabled: menu.editor.canUndo; onTriggered: menu.editor.undo() }
    AppMenuItem { text: i18n.catalog["edit.redo"]; icon.source: Qt.resolvedUrl("../../../resources/icons/edit-redo.svg"); enabled: menu.editor.canRedo; onTriggered: menu.editor.redo() }
    MenuSeparator { }
    AppMenuItem { text: i18n.catalog["edit.cut"]; icon.source: Qt.resolvedUrl("../../../resources/icons/edit-cut.svg"); enabled: menu.editor.selectedText.length > 0 && !menu.editor.readOnly; onTriggered: menu.editor.cut() }
    AppMenuItem { text: i18n.catalog["edit.copy"]; icon.source: Qt.resolvedUrl("../../../resources/icons/edit-copy.svg"); enabled: menu.editor.selectedText.length > 0; onTriggered: menu.editor.copy() }
    AppMenuItem { text: i18n.catalog["edit.paste"]; icon.source: Qt.resolvedUrl("../../../resources/icons/edit-paste.svg"); enabled: menu.editor.canPaste && !menu.editor.readOnly; onTriggered: menu.editor.paste() }
    AppMenuItem { text: i18n.catalog["edit.select_all"]; icon.source: Qt.resolvedUrl("../../../resources/icons/edit-select-all.svg"); enabled: menu.editor.length > 0; onTriggered: menu.zoomTarget !== null ? menu.zoomTarget.selectAllWithoutScroll() : menu.editor.selectAll() }
    MenuSeparator { visible: menu.zoomTarget !== null; height: visible ? implicitHeight : 0 }
    AppMenuItem {
        objectName: "editorClearMenuItem"
        visible: menu.zoomTarget !== null
        height: visible ? implicitHeight : 0
        text: i18n.catalog["edit.clear"]
        icon.source: Qt.resolvedUrl("../../../resources/icons/edit-clear.svg")
        enabled: !menu.editor.readOnly && menu.editor.length > 0
        onTriggered: menu.editor.clear()
    }
    MenuSeparator { visible: menu.zoomTarget !== null && menu.zoomTarget.zoomModified; height: visible ? implicitHeight : 0 }
    AppMenuItem {
        objectName: "resetEditorZoom"
        visible: menu.zoomTarget !== null && menu.zoomTarget.zoomModified
        height: visible ? implicitHeight : 0
        text: i18n.catalog["edit.reset_zoom"]
        icon.source: Qt.resolvedUrl("../../../resources/icons/edit-reset-zoom.svg")
        onTriggered: menu.zoomTarget.resetZoom()
    }
}
