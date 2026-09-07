import QtQuick
import theme 1.0

Rectangle {
    id: root
    default property alias contentData: content.data
    property int padding: Spacing.md
    color: Colors.surface
    border.color: cardHover.hovered ? Qt.alpha(Colors.primary, 0.5) : Colors.outlineVariant
    border.width: 1
    radius: Spacing.radiusCard
    Behavior on color { ColorAnimation { duration: 160 } }
    Behavior on border.color { ColorAnimation { duration: 160 } }
    implicitWidth: content.implicitWidth + padding * 2
    implicitHeight: content.implicitHeight + padding * 2
    HoverHandler { id: cardHover }

    Item {
        id: content
        anchors.fill: parent
        anchors.margins: root.padding
    }
}
