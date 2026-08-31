import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import theme 1.0

Button {
    id: control
    property url iconSource
    property bool selected: false
    property bool expanded: true
    implicitHeight: 48
    hoverEnabled: true

    contentItem: RowLayout {
        spacing: Spacing.sm
        Image {
            source: control.iconSource
            sourceSize.width: 22
            sourceSize.height: 22
            opacity: control.selected ? 1 : 0.72
        }
        Text {
            Layout.fillWidth: true
            visible: control.expanded
            text: control.text
            color: control.selected ? Colors.primary : Colors.textPrimary
            font: Typography.label
            elide: Text.ElideRight
        }
    }
    background: Rectangle {
        color: control.selected ? Colors.primaryContainer
                                : (control.hovered ? Colors.surfaceContainer : "transparent")
        radius: Spacing.radiusLarge
        Behavior on color { ColorAnimation { duration: 120 } }
    }
    ToolTip.visible: hovered && !expanded
    ToolTip.text: text
    ToolTip.delay: 400
}
