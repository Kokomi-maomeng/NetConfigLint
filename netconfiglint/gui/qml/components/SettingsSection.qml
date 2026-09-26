import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import theme 1.0

ColumnLayout {
    id: root
    default property alias sectionContent: body.data
    property string title: ""
    property string detail: ""
    property bool expanded: true
    spacing: 4

    Button {
        id: headerButton
        objectName: root.objectName + "-header"
        Layout.fillWidth: true
        implicitHeight: 58
        topInset: 0
        bottomInset: 0
        leftInset: 0
        rightInset: 0
        topPadding: 0
        bottomPadding: 0
        leftPadding: 0
        rightPadding: 0
        hoverEnabled: true
        onClicked: root.expanded = !root.expanded
        Accessible.name: root.title
        background: Rectangle {
            anchors.fill: parent
            radius: 12
            color: headerButton.down ? Colors.surfaceContainerHighest
                 : headerButton.hovered ? Colors.surfaceContainerHigh : "transparent"
        }
        contentItem: Item {
            Text {
                x: 16
                y: 8
                height: 24
                width: parent.width - 64
                verticalAlignment: Text.AlignVCenter
                elide: Text.ElideRight
                text: root.title
                color: Colors.textPrimary
                font: Typography.subtitle
            }
            Text {
                x: 16
                y: 33
                height: 18
                width: parent.width - 64
                verticalAlignment: Text.AlignVCenter
                elide: Text.ElideRight
                text: root.detail
                color: Colors.textSecondary
                font: Typography.caption
            }
            Item {
                width: 20
                height: 20
                x: parent.width - width - 16
                y: (parent.height - height) / 2
                rotation: root.expanded ? 180 : 0
                Behavior on rotation { NumberAnimation { duration: Theme.motionMedium; easing.type: Easing.OutCubic } }
                Rectangle { x: 3; y: 9; width: 9; height: 2; radius: 1; rotation: 45; color: Colors.textSecondary }
                Rectangle { x: 9; y: 9; width: 9; height: 2; radius: 1; rotation: -45; color: Colors.textSecondary }
            }
        }
    }
    Item {
        id: bodyContainer
        objectName: root.objectName + "-body"
        Layout.fillWidth: true
        Layout.leftMargin: 16
        Layout.rightMargin: 16
        Layout.preferredHeight: root.expanded ? body.implicitHeight : 0
        clip: true
        Behavior on Layout.preferredHeight { NumberAnimation { duration: Theme.motionMedium; easing.type: Easing.OutCubic } }
        ColumnLayout {
            id: body
            width: parent.width
            height: implicitHeight
            spacing: 10
            opacity: root.expanded ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: Theme.motionMedium } }
        }
    }
}
