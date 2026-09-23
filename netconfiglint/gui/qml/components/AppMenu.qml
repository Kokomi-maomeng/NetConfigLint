import QtQuick
import QtQuick.Controls
import theme 1.0
Menu {
    id: root
    popupType: Popup.Item
    font: Typography.body
    padding: 6
    implicitWidth: 280
    delegate: MenuItem { font: Typography.body }
    background: Rectangle { radius: 16; color: Colors.surfaceContainerHigh; border.color: Colors.outlineVariant }
    enter: Transition { NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.motionShort } }
    exit: Transition { NumberAnimation { property: "opacity"; from: 1; to: 0; duration: Theme.motionShort } }
}
