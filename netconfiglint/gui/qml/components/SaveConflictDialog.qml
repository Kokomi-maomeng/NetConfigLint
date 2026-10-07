import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import theme 1.0

AppDialog {
    id: dialog
    objectName: "saveConflictDialog"
    title: i18n.catalog["file.conflict.title"]
    height: Math.min(implicitHeight, Overlay.overlay ? Math.max(160, Overlay.overlay.height - 32) : implicitHeight)
    closePolicy: Popup.CloseOnEscape
    property bool decided: false
    function decide(action) {
        decided = true
        close()
        analysisController.resolveFileConflict(action)
    }
    onClosed: {
        if (!decided) analysisController.resolveFileConflict("cancel")
    }
    Connections {
        target: analysisController
        function onFileConflictRequested() {
            dialog.decided = false
            dialog.open()
        }
    }
    contentItem: ScrollView {
        id: conflictScroll
        objectName: "saveConflictScrollView"
        clip: true
        contentWidth: availableWidth
        implicitHeight: conflictContent.implicitHeight
        ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
        ScrollBar.vertical: AppScrollBar { }
        ColumnLayout {
            id: conflictContent
            width: conflictScroll.availableWidth
            spacing: Spacing.md
            SelectableText {
                objectName: "fileConflictExplanation"
                Layout.fillWidth: true
                text: i18n.catalog["file.conflict." + (analysisController.fileConflict.reason || "changed")]
                wrapMode: TextEdit.Wrap
                color: Colors.textPrimary
            }
            SelectableText {
                objectName: "fileConflictPath"
                Layout.fillWidth: true
                text: analysisController.fileConflict.path || ""
                wrapMode: TextEdit.WrapAnywhere
                color: Colors.textSecondary
            }
            SelectableText {
                objectName: "fileConflictTarget"
                Layout.fillWidth: true
                visible: analysisController.fileConflict.linked || false
                text: i18n.catalog[analysisController.fileConflict.reason === "recovery" ? "file.conflict.recovery_files" : "file.conflict.target"] + " " + (analysisController.fileConflict.target || "")
                wrapMode: TextEdit.WrapAnywhere
                color: Colors.textSecondary
            }
            SelectableText {
                objectName: "fileConflictMetadata"
                Layout.fillWidth: true
                text: i18n.catalog["file.save_metadata"]
                wrapMode: TextEdit.Wrap
                color: Colors.textSecondary
            }
        }
    }
    footer: Flow {
        padding: Spacing.md
        spacing: Spacing.sm
        AppButton {
            objectName: "fileConflictCancel"
            text: i18n.catalog["common.cancel"]
            onClicked: dialog.decide("cancel")
        }
        AppButton {
            objectName: "fileConflictSaveAs"
            text: i18n.catalog["file.conflict.save_as"]
            onClicked: dialog.decide("save_as")
        }
        AppButton {
            objectName: "fileConflictReload"
            visible: analysisController.fileConflict.canReload || false
            text: i18n.catalog["file.conflict.reload"]
            onClicked: dialog.decide("reload")
        }
        AppButton {
            objectName: "fileConflictOverwrite"
            visible: analysisController.fileConflict.canOverwrite || false
            text: i18n.catalog[analysisController.fileConflict.linked ? "file.conflict.update_target" : "file.conflict.overwrite"]
            onClicked: dialog.decide("overwrite")
        }
    }
}
