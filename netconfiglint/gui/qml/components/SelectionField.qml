import QtQuick
import QtQuick.Controls
import theme 1.0
AppButton {
    property string label: ""
    property string valueText: ""
    text: label + " - " + valueText + "  ⌄"
    implicitWidth: Math.max(130, contentItem.implicitWidth + leftPadding + rightPadding)
    Accessible.name: label + ": " + valueText
}
