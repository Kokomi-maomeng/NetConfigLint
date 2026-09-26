import QtQuick
import QtQuick.Controls
import theme 1.0

Rectangle {
    id: root
    property string title
    property string titleObjectName: ""
    property string detail: ""
    property string actionText: ""
    property string actionObjectName: "analyzeButton"
    property bool actionEnabled: true
    signal actionClicked()
    signal dragStarted(real sceneX)
    signal dragMoved(real sceneX)
    signal dragFinished(real sceneX)
    signal stepRequested(int direction)
    implicitHeight: 60
    color: Colors.surfaceContainerLow
    topLeftRadius: Spacing.radiusCard
    topRightRadius: Spacing.radiusCard

    Item {
        id: grip
        objectName: root.objectName + "Grip"
        x: 4
        y: 10
        width: 40
        height: 40
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
    FontMetrics { id: titleMetrics; font: Typography.subtitle }
    SelectableText {
        id: titleText
        objectName: root.titleObjectName
        x: 46
        y: 12
        height: 36
        width: Math.max(0, Math.min(titleMetrics.advanceWidth(root.title) + 4,
            root.width - x - 6 - (detailText.visible ? detailText.width + 4 : 0)
            - (actionButton.visible ? actionButton.width + 2 : 0)))
        verticalAlignment: TextEdit.AlignVCenter
        wrapMode: TextEdit.NoWrap
        clip: true
        text: root.title
        color: Colors.textPrimary
        font: Typography.subtitle
        Accessible.name: root.title
    }
    AppButton {
        id: actionButton
        objectName: root.actionObjectName
        visible: root.actionText.length > 0
        x: titleText.x + titleText.width + 2
        y: 12
        height: 36
        leftPadding: Spacing.xs
        rightPadding: Spacing.xs
        text: root.actionText
        prominent: true
        enabled: root.actionEnabled
        onClicked: root.actionClicked()
    }
    Text {
        id: detailText
        visible: root.detail.length > 0 && root.width >= titleText.x
                 + titleMetrics.advanceWidth(root.title) + 4
                 + (actionButton.visible ? actionButton.width + 2 : 0)
                 + implicitWidth + 10
        x: root.width - width - 6
        y: 20
        text: root.detail
        color: Colors.textSecondary
        font: Typography.caption
    }
}
