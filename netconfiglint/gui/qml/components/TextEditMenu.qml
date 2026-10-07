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
    AppMenuItem { objectName: "editorUndoMenuItem"; text: i18n.catalog["edit.undo"]; icon.source: Qt.resolvedUrl("../../../resources/icons/edit-undo.svg"); enabled: !menu.editor.readOnly && (menu.zoomTarget !== null ? menu.editor.documentCanUndo : menu.editor.canUndo); onTriggered: menu.zoomTarget !== null ? menu.zoomTarget.undoDocument() : menu.editor.undo() }
    AppMenuItem { text: i18n.catalog["edit.redo"]; icon.source: Qt.resolvedUrl("../../../resources/icons/edit-redo.svg"); enabled: !menu.editor.readOnly && (menu.zoomTarget !== null ? menu.editor.documentCanRedo : menu.editor.canRedo); onTriggered: menu.zoomTarget !== null ? menu.zoomTarget.redoDocument() : menu.editor.redo() }
    MenuSeparator { }
    AppMenuItem { text: i18n.catalog["edit.cut"]; icon.source: Qt.resolvedUrl("../../../resources/icons/edit-cut.svg"); enabled: (menu.editor.selectedText.length > 0 || (menu.zoomTarget !== null && menu.editor.fullDocumentSelected)) && !menu.editor.readOnly; onTriggered: menu.zoomTarget !== null ? menu.zoomTarget.cutSelection() : menu.editor.cut() }
    AppMenuItem { text: i18n.catalog["edit.copy"]; icon.source: Qt.resolvedUrl("../../../resources/icons/edit-copy.svg"); enabled: menu.editor.selectedText.length > 0 || (menu.zoomTarget !== null && menu.editor.fullDocumentSelected); onTriggered: menu.zoomTarget !== null ? menu.zoomTarget.copySelection() : menu.editor.copy() }
    AppMenuItem { text: i18n.catalog["edit.paste"]; icon.source: Qt.resolvedUrl("../../../resources/icons/edit-paste.svg"); enabled: menu.editor.canPaste && !menu.editor.readOnly; onTriggered: menu.zoomTarget !== null ? menu.zoomTarget.pasteSelection() : menu.editor.paste() }
    AppMenuItem { text: i18n.catalog[menu.zoomTarget !== null ? "edit.select_all_document" : "edit.select_all"]; icon.source: Qt.resolvedUrl("../../../resources/icons/edit-select-all.svg"); enabled: menu.zoomTarget !== null ? menu.editor.documentLength > 0 : menu.editor.length > 0; onTriggered: menu.zoomTarget !== null ? menu.zoomTarget.selectAllWithoutScroll() : menu.editor.selectAll() }
    AppMenuItem { objectName: "editorCopyDocumentMenuItem"; visible: menu.zoomTarget !== null; height: visible ? implicitHeight : 0; text: i18n.catalog["edit.copy_document"]; enabled: menu.zoomTarget !== null && menu.editor.documentLength > 0; onTriggered: menu.zoomTarget.copyDocument() }
    AppMenuItem { objectName: "editorSelectPageMenuItem"; visible: menu.zoomTarget !== null && menu.editor.pagedPreview; height: visible ? implicitHeight : 0; text: i18n.catalog["edit.select_current_page"]; enabled: menu.editor.length > 0; onTriggered: menu.zoomTarget.selectCurrentPage() }
    MenuSeparator { visible: menu.zoomTarget !== null; height: visible ? implicitHeight : 0 }
    AppMenuItem {
        objectName: "editorClearMenuItem"
        visible: menu.zoomTarget !== null
        height: visible ? implicitHeight : 0
        text: i18n.catalog["edit.clear_document"]
        icon.source: Qt.resolvedUrl("../../../resources/icons/edit-clear.svg")
        enabled: !menu.editor.readOnly && menu.zoomTarget !== null && menu.editor.documentLength > 0
        onTriggered: menu.zoomTarget.clearDocument()
    }
    AppMenuItem { objectName: "editorClearPageMenuItem"; visible: menu.zoomTarget !== null && menu.editor.pagedPreview; height: visible ? implicitHeight : 0; text: i18n.catalog["edit.clear_current_page"]; enabled: !menu.editor.readOnly && menu.editor.length > 0; onTriggered: menu.zoomTarget.clearCurrentPage() }
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
