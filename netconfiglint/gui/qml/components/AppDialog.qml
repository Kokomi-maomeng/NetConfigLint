import QtQuick
import QtQuick.Controls
import theme 1.0

Dialog {
    id: control
    modal: true
    popupType: Popup.Item
    font: Typography.body
    anchors.centerIn: Overlay.overlay
    width: Math.min(560, Overlay.overlay.width - Spacing.lg * 2)
    padding: Spacing.lg
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    Overlay.modal: Rectangle { color: Colors.scrim }
    header: Rectangle {
        implicitHeight: 64
        color: Colors.surfaceContainerHigh
        topLeftRadius: Spacing.radiusLarge
        topRightRadius: Spacing.radiusLarge
        SelectableText {
            anchors.fill: parent
            anchors.leftMargin: Spacing.lg
            anchors.rightMargin: Spacing.lg
            verticalAlignment: TextEdit.AlignVCenter
            wrapMode: TextEdit.NoWrap
            clip: true
            text: control.title
            color: Colors.textPrimary
            font: Typography.title
        }
    }
    background: Rectangle {
        color: Colors.surfaceContainer
        border.color: Colors.outlineVariant
        border.width: 1
        radius: Spacing.radiusLarge
    }
    enter: Transition {
        ParallelAnimation {
            NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 170; easing.type: Easing.OutCubic }
            NumberAnimation { property: "scale"; from: 0.96; to: 1; duration: 190; easing.type: Easing.OutCubic }
        }
    }
    exit: Transition {
        ParallelAnimation {
            NumberAnimation { property: "opacity"; from: 1; to: 0; duration: 120; easing.type: Easing.InCubic }
            NumberAnimation { property: "scale"; from: 1; to: 0.98; duration: 120; easing.type: Easing.InCubic }
        }
    }
}
