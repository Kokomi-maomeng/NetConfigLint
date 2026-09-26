import QtQuick
import QtQuick.Controls
import theme 1.0

ScrollBar {
    id: control
    policy: ScrollBar.AsNeeded
    hoverEnabled: true
    padding: 3
    implicitWidth: 10
    implicitHeight: 10
    minimumSize: 0.08
    visible: policy === ScrollBar.AlwaysOn || (policy !== ScrollBar.AlwaysOff && size < 0.999
             && (orientation === Qt.Vertical ? height > 32 : width > 32))
    opacity: visible && (active || hovered) ? 1 : (visible ? 0.58 : 0)
    Behavior on opacity { NumberAnimation { duration: Theme.motionShort } }
    contentItem: Rectangle {
        implicitWidth: 8
        implicitHeight: 8
        radius: 4
        color: control.pressed || control.hovered ? Colors.primary : Colors.outline
        opacity: 1
        Behavior on color { ColorAnimation { duration: Theme.motionShort } }
    }
    background: Item { }
}
