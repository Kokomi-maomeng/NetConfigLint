import QtQuick
import QtQuick.Controls
import theme 1.0

Dialog {
    id: control
    modal: true
    anchors.centerIn: Overlay.overlay
    padding: Spacing.lg
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    Overlay.modal: Rectangle { color: Colors.scrim }
    background: Rectangle {
        color: Colors.surface
        border.color: Colors.outlineVariant
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
