import QtQuick
import QtQuick.Controls
import QtQuick.Controls.impl
import theme 1.0
Button {
    id: control
    property url iconSource
    property bool selected: false
    property bool expanded: true
    property bool expandable: false
    property bool expandedState: false
    implicitHeight: 48
    topInset: 0
    bottomInset: 0
    leftPadding: 16
    rightPadding: 16
    hoverEnabled: true
    font: Typography.label
    icon.source: iconSource
    icon.width: 22
    icon.height: 22
    icon.color: selected ? Colors.primary : Colors.textSecondary
    display: expanded ? AbstractButton.TextBesideIcon : AbstractButton.IconOnly
    palette.buttonText: selected ? Colors.primary : Colors.textSecondary
    contentItem: IconLabel {
        icon: control.icon
        text: control.text
        font: control.font
        display: control.display
        spacing: 14
        alignment: control.expanded ? Qt.AlignLeft : Qt.AlignHCenter
        color: control.selected ? Colors.primary : Colors.textSecondary
    }
    background: Rectangle {
        color: control.selected ? Colors.primaryContainer : (control.hovered ? Colors.surfaceContainerHigh : "transparent")
        radius: 24
        border.color: control.activeFocus ? Colors.primary : "transparent"
        Behavior on color { ColorAnimation { duration: Theme.motionShort } }
    }
    Item {
        width: 14; height: 14
        anchors.right: parent.right
        anchors.rightMargin: 18
        anchors.verticalCenter: parent.verticalCenter
        visible: control.expanded && control.expandable
        rotation: control.expandedState ? 0 : -90
        Behavior on rotation { NumberAnimation { duration: Theme.motionShort } }
        Rectangle {
            x: 2; y: 6; width: 7; height: 2; radius: 1
            rotation: 45; color: Colors.textSecondary
        }
        Rectangle {
            x: 7; y: 6; width: 7; height: 2; radius: 1
            rotation: -45; color: Colors.textSecondary
        }
    }
    scale: down ? 0.97 : 1
    Behavior on scale { NumberAnimation { duration: Theme.motionShort; easing.type: Easing.OutCubic } }
    ToolTip.visible: hovered && !expanded
    ToolTip.text: text
    ToolTip.delay: 400
}
