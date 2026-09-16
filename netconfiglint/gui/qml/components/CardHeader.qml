import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import theme 1.0
Rectangle {
    id: root
    property string title
    property string detail: ""
    signal dragStarted(real sceneX)
    signal dragMoved(real sceneX)
    signal dragFinished(real sceneX)
    signal stepRequested(int direction)
    implicitHeight: 60
    color: Colors.surfaceContainerLow
    topLeftRadius: Spacing.radiusCard
    topRightRadius: Spacing.radiusCard
    RowLayout {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 6
        Item {
            id: grip
            objectName: root.objectName + "Grip"
            Layout.preferredWidth: 24
            Layout.fillHeight: true
            activeFocusOnTab: true
            Accessible.name: i18n.catalog["panels.reorder"] + " " + root.title
            Accessible.role: Accessible.Grip
            Grid {
                anchors.centerIn: parent
                columns: 2
                spacing: 3
                Repeater {
                    model: 6
                    Rectangle {
                        required property int index
                        width: 3
                        height: 3
                        radius: 2
                        color: gripHover.hovered || handler.active ? Colors.primary : Colors.outline
                        scale: handler.active ? 1.25 : 1
                        Behavior on color { ColorAnimation { duration: Theme.motionShort } }
                        Behavior on scale { NumberAnimation { duration: Theme.motionShort } }
                    }
                }
            }
            HoverHandler { id: gripHover; cursorShape: handler.active ? Qt.ClosedHandCursor : Qt.OpenHandCursor }
            DragHandler {
                id: handler
                target: null
                onActiveChanged: {
                    if (active) root.dragStarted(centroid.scenePosition.x)
                    else root.dragFinished(centroid.scenePosition.x)
                }
                onCentroidChanged: if (active) root.dragMoved(centroid.scenePosition.x)
            }
            Keys.onLeftPressed: root.stepRequested(-1)
            Keys.onRightPressed: root.stepRequested(1)
            ToolTip.visible: gripHover.hovered
            ToolTip.text: i18n.catalog["panels.reorder"]
        }
        SelectableText { text: root.title; Layout.fillWidth: true; font: Typography.subtitle; wrapMode: TextEdit.NoWrap; clip: true }
        SelectableText { text: root.detail; visible: text.length > 0; color: Colors.textSecondary; font: Typography.caption }
    }
}
