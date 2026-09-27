import QtQuick
import QtQuick.Controls
import theme 1.0

ToolTip {
    id: control
    delay: 450
    padding: 8
    font: Typography.caption
    contentItem: Text {
        text: control.text
        font: control.font
        color: Colors.textPrimary
        renderType: Text.QtRendering
    }
    background: Rectangle {
        radius: 10
        color: Colors.surfaceContainerHighest
        border.color: Colors.outlineVariant
    }
}
