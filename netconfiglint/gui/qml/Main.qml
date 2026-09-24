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
    width: preferences.values.windowWidth
    height: preferences.values.windowHeight
    minimumWidth: 960
    minimumHeight: 600
    title: preferences.values.panelTitle
    font: Typography.body
    color: Colors.background
    flags: Qt.Window | Qt.ExpandedClientAreaHint | Qt.NoTitleBarBackgroundHint
    topPadding: 0
    leftPadding: 0
    rightPadding: 0
    bottomPadding: 0
    Material.theme: Theme.dark ? Material.Dark : Material.Light
    Material.accent: Colors.primary
    Material.primary: Colors.primary
    Material.background: Colors.surfaceContainer
    Material.foreground: Colors.textPrimary
    property int currentPage: 0
    Component.onCompleted: {
        if (preferences.values.windowPositionSaved) {
            x = preferences.values.windowX
            y = preferences.values.windowY
        }
        if (preferences.values.windowMaximized) showMaximized()
    }
    onClosing: preferences.saveWindowGeometry(x, y, width, height, visibility === Window.Maximized)
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
    ColumnLayout {
        anchors.fill: parent
        spacing: 0
        AppTitleBar {
            objectName: "appTitleBar"
            Layout.fillWidth: true
            Layout.preferredHeight: implicitHeight
            navigationWidth: navigationHost.width
            controller: analysisController
            onToggleRequested: {
                var nextExpanded = !navigation.expanded
                navigation.expandedInCompact = nextExpanded
                preferences.setValue("sidebarExpanded", nextExpanded)
            }
            onOpenRequested: { window.currentPage = 0; checkPage.openFileDialog() }
            onExportRequested: { window.currentPage = 0; checkPage.openExportDialog() }
            onAboutRequested: {
                window.currentPage = 1
                navigation.expandedInCompact = false
            }
        }
        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0
            Item {
                id: navigationHost
                z: 2
                Layout.fillHeight: true
                Layout.preferredWidth: navigation.compact ? 80 : (navigation.expanded ? 260 : 80)
                Behavior on Layout.preferredWidth { NumberAnimation { duration: Theme.motionMedium; easing.type: Easing.OutCubic } }
                NavigationRail {
                    id: navigation
                    objectName: "navigationRail"
                    anchors.top: parent.top
                    anchors.bottom: parent.bottom
                    width: expanded ? 260 : 80
                    Behavior on width { NumberAnimation { duration: Theme.motionMedium; easing.type: Easing.OutCubic } }
                    currentIndex: window.currentPage
                    controller: analysisController
                    onHistorySelected: entryId => {
                        analysisController.openHistory(entryId)
                        window.currentPage = 0
                    }
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
            Rectangle {
                id: workspaceSurface
                Layout.fillWidth: true
                Layout.fillHeight: true
                color: Colors.background
                topLeftRadius: 28
                clip: true
                StackLayout {
                    id: pageStack
                    anchors.fill: parent
                    currentIndex: window.currentPage
                    ConfigCheckPage { id: checkPage; controller: analysisController }
                    AboutPage { }
                }
            }
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
    ParallelAnimation {
        id: pageTransition
        NumberAnimation { target: pageStack; property: "opacity"; from: 0.35; to: 1; duration: Theme.motionMedium; easing.type: Easing.OutCubic }
        NumberAnimation { target: pageStack; property: "scale"; from: 0.992; to: 1; duration: Theme.motionMedium; easing.type: Easing.OutCubic }
    }
}
