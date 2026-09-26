import QtQuick
import theme 1.0

Rectangle {
    id: root
    property string message: ""
    width: Math.min(parent ? parent.width - Spacing.xl * 2 : 420, 420)
    height: toastText.implicitHeight + Spacing.md * 2
    radius: Spacing.radiusMedium
    color: Colors.textPrimary
    opacity: 0
    visible: false
    z: 1000

    function show(text) {
        message = text
        hideAnimation.stop()
        visible = true
        opacity = 0.96
        hideTimer.restart()
    }

    Text {
        renderType: Text.QtRendering
        id: toastText
        anchors.fill: parent
        anchors.margins: Spacing.md
        text: root.message
        color: Colors.surface
        font: Typography.body
        wrapMode: Text.Wrap
    }
    Timer { id: hideTimer; interval: 3500; onTriggered: hideAnimation.restart() }
    NumberAnimation {
        id: hideAnimation
        target: root
        property: "opacity"
        to: 0
        duration: Theme.motionMedium
        easing.type: Easing.InCubic
        onFinished: root.visible = false
    }
    Behavior on opacity { NumberAnimation { duration: Theme.motionShort } }
}
