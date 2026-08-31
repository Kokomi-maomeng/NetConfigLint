import QtQuick
import QtQuick.Controls
import theme 1.0

ToolButton {
    id: control
    property url iconSource
    property string toolTip
    implicitWidth: 38
    implicitHeight: 38
    hoverEnabled: true

    contentItem: Image {
        source: control.iconSource
        sourceSize.width: 20
        sourceSize.height: 20
        fillMode: Image.PreserveAspectFit
        opacity: control.enabled ? (control.hovered ? 1.0 : 0.78) : 0.35
    }
    background: Rectangle {
        radius: Spacing.radiusMedium
        color: control.hovered ? Colors.surfaceVariant : "transparent"
        Behavior on color { ColorAnimation { duration: 120 } }
    }
    ToolTip.visible: hovered && toolTip.length > 0
    ToolTip.text: toolTip
    ToolTip.delay: 500
}
