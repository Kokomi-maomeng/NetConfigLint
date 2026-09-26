import QtQuick
import QtQuick.Controls
import theme 1.0
AppButton {
    id: control
    property string label: ""
    property string valueText: ""
    text: label + " - " + valueText
    implicitWidth: Math.max(130, contentItem.implicitWidth + leftPadding + rightPadding)
    Accessible.name: label + ": " + valueText
    contentItem: Row {
        spacing: 8
        Text {
            renderType: Text.QtRendering
            anchors.verticalCenter: parent.verticalCenter
            text: control.text
            font: control.font
            color: Colors.textPrimary
        }
        Item {
            anchors.verticalCenter: parent.verticalCenter
            width: 12
            height: 8
            Rectangle {
                x: 1
                y: 2
                width: 7
                height: 2
                radius: 1
                rotation: 40
                color: Colors.textSecondary
            }
            Rectangle {
                x: 5
                y: 2
                width: 7
                height: 2
                radius: 1
                rotation: -40
                color: Colors.textSecondary
            }
        }
    }
}
