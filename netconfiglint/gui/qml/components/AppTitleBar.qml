import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import theme 1.0
import "../config"

Item {
    id: root
    property var controller
    signal toggleRequested()
    signal openRequested()
    signal exportRequested()
    signal aboutRequested()
    signal minimizeRequested()
    signal maximizeRequested()
    implicitHeight: 52

    Rectangle { anchors.fill: parent; color: Colors.surfaceContainerLow }

    DragHandler {
        target: null
        acceptedButtons: Qt.LeftButton
        onActiveChanged: if (active) root.Window.window.startSystemMove()
    }
    TapHandler {
        acceptedButtons: Qt.LeftButton
        onDoubleTapped: {
            root.maximizeRequested()
        }
    }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 12
        anchors.rightMargin: 8
        spacing: 8
        ToolButton {
            objectName: "sidebarToggle"
            Layout.preferredWidth: 42
            Layout.preferredHeight: 42
            icon.source: Qt.resolvedUrl("../../../resources/icons/menu.svg")
            icon.color: Colors.textSecondary
            Accessible.name: i18n.catalog["nav.collapse"]
            onClicked: root.toggleRequested()
        }
        ConfigToolbar {
            objectName: "topConfigToolbar"
            Layout.fillWidth: true
            Layout.preferredHeight: 40
            controller: root.controller
            onOpenRequested: root.openRequested()
            onExportRequested: root.exportRequested()
        }
        ToolButton {
            objectName: "brandAboutButton"
            Layout.preferredWidth: 42
            Layout.preferredHeight: 42
            icon.source: Qt.resolvedUrl("../../../resources/icons/about.svg")
            icon.color: Colors.textSecondary
            Accessible.name: i18n.catalog["nav.about"]
            onClicked: root.aboutRequested()
        }
        RowLayout {
            spacing: 0
            ToolButton {
                objectName: "minimizeWindowButton"
                Layout.preferredWidth: 44
                Layout.preferredHeight: 40
                Accessible.name: i18n.catalog["window.minimize"] || "Minimize"
                onClicked: root.minimizeRequested()
                contentItem: Item {
                    Rectangle { anchors.centerIn: parent; width: 12; height: 1; color: Colors.textSecondary }
                }
                background: Rectangle { radius: 8; color: parent.hovered ? Colors.surfaceContainerHigh : "transparent" }
            }
            ToolButton {
                objectName: "maximizeWindowButton"
                Layout.preferredWidth: 44
                Layout.preferredHeight: 40
                Accessible.name: i18n.catalog["window.maximize"] || "Maximize"
                onClicked: root.maximizeRequested()
                contentItem: Item {
                    Rectangle {
                        anchors.centerIn: parent
                        width: 12; height: 10
                        color: "transparent"
                        border.color: Colors.textSecondary
                        border.width: 1
                    }
                    Rectangle {
                        visible: root.Window.visibility === Window.Maximized
                        x: parent.width / 2 - 4
                        y: parent.height / 2 - 7
                        width: 12; height: 10
                        color: "transparent"
                        border.color: Colors.textSecondary
                        border.width: 1
                        z: -1
                    }
                }
                background: Rectangle { radius: 8; color: parent.hovered ? Colors.surfaceContainerHigh : "transparent" }
            }
            ToolButton {
                objectName: "closeWindowButton"
                Layout.preferredWidth: 44
                Layout.preferredHeight: 40
                Accessible.name: i18n.catalog["window.close"] || "Close"
                onClicked: root.Window.window.close()
                contentItem: Item {
                    Rectangle { anchors.centerIn: parent; width: 14; height: 1; rotation: 45; color: Colors.textSecondary }
                    Rectangle { anchors.centerIn: parent; width: 14; height: 1; rotation: -45; color: Colors.textSecondary }
                }
                background: Rectangle { radius: 8; color: parent.hovered ? Colors.error : "transparent" }
            }
        }
    }
}
