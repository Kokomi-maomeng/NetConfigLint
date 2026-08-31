import QtQuick
import theme 1.0

Rectangle {
    id: root
    property string message: ""
    width: Math.min(parent ? parent.width - Spacing.xl * 2 : 420, 420)
    height: toastText.implicitHeight + Spacing.md * 2
    radius: Spacing.radiusMedium
    color: Colors.textPrimary
    opacity: visible ? 0.96 : 0
    visible: false
    z: 1000

    function show(text) {
        message = text
        visible = true
        hideTimer.restart()
    }

    Text {
        id: toastText
        anchors.fill: parent
        anchors.margins: Spacing.md
        text: root.message
        color: Colors.surface
        font: Typography.body
        wrapMode: Text.Wrap
    }
    Timer { id: hideTimer; interval: 3500; onTriggered: root.visible = false }
    Behavior on opacity { NumberAnimation { duration: 150 } }
}
