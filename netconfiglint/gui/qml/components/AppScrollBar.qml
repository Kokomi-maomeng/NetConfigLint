import QtQuick
import QtQuick.Controls
import theme 1.0

ScrollBar {
    id: control
    policy: ScrollBar.AsNeeded
    hoverEnabled: true
    padding: 3
    contentItem: Rectangle {
        implicitWidth: 8
        implicitHeight: 8
        radius: 4
        color: control.pressed || control.hovered ? Colors.primary : Colors.outline
        opacity: control.active || control.hovered ? 0.9 : 0.55
        Behavior on color { ColorAnimation { duration: 120 } }
        Behavior on opacity { NumberAnimation { duration: 120 } }
    }
    background: Item { }
}
