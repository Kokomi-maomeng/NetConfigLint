import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import theme 1.0

Item {
    id: root
    property real navigationWidth: 260
    property string pageTitle: ""
    property string detail: ""
    // Expanded client area retains the native Windows caption and its controls.
    // Qt's SafeArea top margin can be zero there, so reserve that caption row.
    readonly property real titleInset: Math.max(SafeArea.margins.top, Qt.platform.os === "windows" ? 32 : 0)
    implicitHeight: 54 + titleInset

    Rectangle {
        anchors.fill: parent
        color: Colors.background
    }
    Rectangle {
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        width: root.navigationWidth
        color: Colors.surfaceContainerLow
        Behavior on width { NumberAnimation { duration: Theme.motionMedium; easing.type: Easing.OutCubic } }
    }
    Rectangle {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: 1
        color: Qt.alpha(Colors.outlineVariant, 0.55)
    }
    Rectangle {
        anchors.left: parent.left
        anchors.leftMargin: root.navigationWidth - 1
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        width: 1
        color: Qt.alpha(Colors.outlineVariant, 0.55)
        Behavior on anchors.leftMargin { NumberAnimation { duration: Theme.motionMedium; easing.type: Easing.OutCubic } }
    }

    Item {
        id: dragSurface
        anchors.fill: parent
        TapHandler {
            acceptedButtons: Qt.LeftButton
            onDoubleTapped: {
                if (root.Window.visibility === Window.Maximized) root.Window.showNormal()
                else root.Window.showMaximized()
            }
        }
        DragHandler {
            target: null
            acceptedButtons: Qt.LeftButton
            onActiveChanged: if (active) root.Window.startSystemMove()
        }
    }

    RowLayout {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.topMargin: root.titleInset
        height: 54
        spacing: 0
        Item {
            Layout.preferredWidth: root.navigationWidth
            Layout.fillHeight: true
            Behavior on Layout.preferredWidth { NumberAnimation { duration: Theme.motionMedium; easing.type: Easing.OutCubic } }
            RowLayout {
                anchors.left: parent.left
                anchors.leftMargin: Math.max(16, SafeArea.margins.left + 12)
                anchors.right: parent.right
                anchors.rightMargin: 14
                anchors.verticalCenter: parent.verticalCenter
                spacing: 10
                Image {
                    source: Qt.resolvedUrl("../../../resources/icons/app-master.png")
                    sourceSize.width: 36
                    sourceSize.height: 36
                    Layout.preferredWidth: 36
                    Layout.preferredHeight: 36
                    fillMode: Image.PreserveAspectFit
                    smooth: true
                    mipmap: true
                }
                Text {
                    Layout.fillWidth: true
                    visible: root.navigationWidth > 120
                    text: preferences.values.panelTitle
                    color: Colors.textPrimary
                    font: Typography.subtitle
                    elide: Text.ElideRight
                }
            }
        }
        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.leftMargin: Spacing.lg
            Layout.rightMargin: Math.max(Spacing.lg, SafeArea.margins.right + Spacing.sm)
            spacing: Spacing.sm
            SelectableText {
                objectName: "checkPageTitle"
                Layout.preferredWidth: implicitWidth
                Layout.maximumWidth: implicitWidth
                text: root.pageTitle
                font: Typography.subtitle
                color: Colors.textPrimary
            }
            Rectangle {
                width: 5
                height: 5
                radius: 3
                color: Colors.primary
                visible: root.detail.length > 0
            }
            SelectableText {
                text: root.detail
                visible: text.length > 0
                color: Colors.textSecondary
                font: Typography.caption
                wrapMode: TextEdit.NoWrap
                clip: true
            }
            Item { Layout.fillWidth: true }
        }
    }
}
