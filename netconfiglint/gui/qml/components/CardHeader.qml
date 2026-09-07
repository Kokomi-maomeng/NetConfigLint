import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import theme 1.0
Rectangle {
    id: root
    property string title
    property string detail: ""
    signal dragStarted()
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
            Text { anchors.centerIn: parent; text: "⠿"; color: gripHover.hovered ? Colors.primary : Colors.outline; font.pixelSize: 22 }
            HoverHandler { id: gripHover; cursorShape: handler.active ? Qt.ClosedHandCursor : Qt.OpenHandCursor }
            DragHandler {
                id: handler
                target: null
                onActiveChanged: {
                    if (active) root.dragStarted()
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
