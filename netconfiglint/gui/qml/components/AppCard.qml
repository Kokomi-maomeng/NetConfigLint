import QtQuick
import theme 1.0

Rectangle {
    id: root
    default property alias contentData: content.data
    property int padding: Spacing.md
    color: Colors.surfaceContainerLow
    border.width: 0
    radius: Spacing.radiusCard
    Behavior on color { ColorAnimation { duration: Theme.motionShort } }
    implicitWidth: content.implicitWidth + padding * 2
    implicitHeight: content.implicitHeight + padding * 2

    Item {
        id: content
        anchors.fill: parent
        anchors.margins: root.padding
    }
}
