import QtQuick
import theme 1.0

Rectangle {
    id: root
    property string label: "INFO"
    property color statusColor: Colors.severity(label)
    property bool interactive: false
    property bool selected: false
    property bool hovered: pointerArea.containsMouse
    signal clicked()
    implicitWidth: badgeText.implicitWidth + Spacing.md * 2
    implicitHeight: interactive ? 36 : 28
    radius: height / 2
    color: Qt.alpha(statusColor, selected ? 0.28 : (hovered && interactive ? 0.20 : 0.12))
    border.color: Qt.alpha(statusColor, selected ? 0.95 : 0.48)
    border.width: selected ? 2 : 1
    activeFocusOnTab: interactive
    Accessible.role: interactive ? Accessible.Button : Accessible.StaticText
    Accessible.name: label
    Accessible.description: interactive ? i18n.catalog["analysis.severity_filter"] : ""

    Text {
        id: badgeText
        anchors.centerIn: parent
        text: root.label
        color: root.statusColor
        font: root.interactive ? Typography.label : Typography.caption
    }

    MouseArea {
        id: pointerArea
        anchors.fill: parent
        enabled: root.interactive
        hoverEnabled: true
        cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
        onClicked: {
            root.forceActiveFocus()
            root.clicked()
        }
    }
    Keys.onSpacePressed: if (interactive) root.clicked()
    Keys.onReturnPressed: if (interactive) root.clicked()
    scale: interactive && pointerArea.pressed ? 0.97 : 1
    Behavior on color { ColorAnimation { duration: Theme.motionShort } }
    Behavior on border.color { ColorAnimation { duration: Theme.motionShort } }
    Behavior on scale { NumberAnimation { duration: Theme.motionShort; easing.type: Easing.OutCubic } }
}
