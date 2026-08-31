import QtQuick
import QtQuick.Controls
import theme 1.0

Dialog {
    id: control
    modal: true
    anchors.centerIn: Overlay.overlay
    padding: Spacing.lg
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    background: Rectangle {
        color: Colors.surface
        border.color: Colors.outlineVariant
        radius: Spacing.radiusLarge
    }
}
