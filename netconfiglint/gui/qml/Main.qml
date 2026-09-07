import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Controls.Material
import theme 1.0
import "components"
import "navigation"
import "pages"
ApplicationWindow {
    id: window
    visible: true
    width: 1440
    height: 900
    minimumWidth: 960
    minimumHeight: 600
    title: preferences.values.panelTitle
    font: Typography.body
    color: Colors.background
    Material.theme: Theme.dark ? Material.Dark : Material.Light
    Material.accent: Colors.primary
    Material.primary: Colors.primary
    Material.background: Colors.surfaceContainer
    Material.foreground: Colors.textPrimary
    property int currentPage: 0
    onCurrentPageChanged: pageTransition.restart()
    function clearOtherSelections(item, position) {
        if (!item) return
        if (typeof item.deselect === "function") {
            var local = item.mapFromItem(window.contentItem, position.x, position.y)
            if (!item.visible || local.x < 0 || local.y < 0 || local.x > item.width || local.y > item.height) item.deselect()
        }
        var children = item.children || []
        for (var i = 0; i < children.length; ++i) clearOtherSelections(children[i], position)
    }
    TapHandler {
        acceptedButtons: Qt.LeftButton
        onPressedChanged: if (pressed) {
            if (!Theme.selectionLocked) window.clearOtherSelections(window.contentItem, point.scenePosition)
            if (navigation.compact && point.scenePosition.x > navigation.width) navigation.expandedInCompact = false
        }
    }
    RowLayout {
        anchors.fill: parent
        spacing: 0
        Item {
            z: 2
            Layout.fillHeight: true
            Layout.preferredWidth: navigation.compact ? 80 : (navigation.expanded ? 260 : 80)
            Behavior on Layout.preferredWidth { NumberAnimation { duration: Theme.motion; easing.type: Easing.OutCubic } }
            NavigationRail {
                id: navigation
                objectName: "navigationRail"
                anchors.top: parent.top
                anchors.bottom: parent.bottom
                width: expanded ? 260 : 80
                Behavior on width { NumberAnimation { duration: Theme.motion; easing.type: Easing.OutCubic } }
                currentIndex: window.currentPage
                onPageSelected: index => {
                    window.currentPage = index
                    expandedInCompact = false
                }
                onSettingsRequested: {
                    expandedInCompact = false
                    settingsDialog.open()
                }
            }
        }
        StackLayout {
            id: pageStack
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: window.currentPage
            ConfigCheckPage { controller: analysisController }
            HistoryPage { controller: analysisController }
            AboutPage { }
        }
    }
    SettingsPage { id: settingsDialog; objectName: "settingsDialog"; controller: analysisController }
    AppToast {
        id: toast
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: Spacing.lg
    }
    Connections {
        target: analysisController
        function onToastRequested(key) { toast.show(i18n.catalog[key] || key) }
    }
    NumberAnimation {
        id: pageTransition
        target: pageStack
        property: "opacity"
        from: 0
        to: 1
        duration: Theme.motion
        easing.type: Easing.OutCubic
    }
}
