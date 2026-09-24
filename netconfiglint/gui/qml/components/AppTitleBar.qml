import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import theme 1.0
import "../config"

Item {
    id: root
    property real navigationWidth: 260
    property var controller
    signal toggleRequested()
    signal openRequested()
    signal exportRequested()
    signal aboutRequested()
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
                ToolButton {
                    objectName: "sidebarToggle"
                    icon.source: Qt.resolvedUrl("../../../resources/icons/menu.svg")
                    icon.color: Colors.textPrimary
                    Accessible.name: i18n.catalog["nav.collapse"]
                    onClicked: root.toggleRequested()
                }
            }
        }
        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.leftMargin: Spacing.lg
            Layout.rightMargin: Math.max(Spacing.lg, SafeArea.margins.right + Spacing.sm)
            spacing: Spacing.sm
            ConfigToolbar {
                id: topToolbar
                Layout.preferredWidth: implicitWidth
                Layout.preferredHeight: 42
                controller: root.controller
                onOpenRequested: root.openRequested()
                onExportRequested: root.exportRequested()
            }
            Item { Layout.fillWidth: true }
            Button {
                objectName: "brandAboutButton"
                flat: true
                onClicked: root.aboutRequested()
                Accessible.name: i18n.catalog["nav.about"]
                contentItem: RowLayout {
                    spacing: 8
                    Image {
                        source: Qt.resolvedUrl("../../../resources/icons/app-master.png")
                        sourceSize.width: 28; sourceSize.height: 28
                        Layout.preferredWidth: 28; Layout.preferredHeight: 28
                        fillMode: Image.PreserveAspectFit
                        smooth: true; mipmap: true
                    }
                    Text {
                        text: preferences.values.panelTitle
                        color: Colors.textPrimary
                        font: Typography.label
                        elide: Text.ElideRight
                    }
                }
            }
        }
    }
}
