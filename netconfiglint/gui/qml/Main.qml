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
    color: Colors.surfaceContainerLow
    flags: Qt.Window | Qt.FramelessWindowHint | Qt.WindowMinMaxButtonsHint | Qt.WindowCloseButtonHint
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
    property rect normalGeometry: Qt.rect(0, 0, 1440, 900)
    property bool geometryReady: false
    property bool lastNonMinimizedMaximized: false
    property bool wasMinimized: false
    property bool minimizing: false
    property bool targetMaximized: false
    property bool closingTransition: false
    property bool allowClose: false
    function minimizeWindow() {
        lastNonMinimizedMaximized = visibility === Window.Maximized || lastNonMinimizedMaximized
        minimizing = true
        shell.opacity = 0.72
        shell.scale = 0.992
        minimizeTimer.restart()
    }
    function toggleMaximize() {
        if (windowStateTransition.running || closingTransition || minimizing) return
        targetMaximized = visibility !== Window.Maximized
        windowStateTransition.start()
    }
    Timer {
        id: minimizeTimer
        interval: 110
        onTriggered: window.showMinimized()
    }
    function rememberNormalGeometry() {
        if (geometryReady && !minimizing && !wasMinimized && visibility === Window.Windowed && width >= minimumWidth && height >= minimumHeight)
            normalGeometry = Qt.rect(x, y, width, height)
    }
    Component.onCompleted: {
        var restored = preferences.restoreWindowGeometry(minimumWidth, minimumHeight)
        width = restored.width
        height = restored.height
        x = restored.x
        y = restored.y
        normalGeometry = Qt.rect(x, y, width, height)
        geometryReady = true
        if (preferences.values.windowMaximized) showMaximized()
        openingTransition.start()
    }
    onXChanged: Qt.callLater(rememberNormalGeometry)
    onYChanged: Qt.callLater(rememberNormalGeometry)
    onWidthChanged: Qt.callLater(rememberNormalGeometry)
    onHeightChanged: Qt.callLater(rememberNormalGeometry)
    onVisibilityChanged: function() {
        if (!geometryReady) return
        if (window.visibility === Window.Minimized) {
            wasMinimized = true
            minimizing = false
        } else if (window.visibility === Window.Maximized) {
            lastNonMinimizedMaximized = true
            wasMinimized = false
            if (!windowStateTransition.running && !openingTransition.running) {
                shell.opacity = 1
                shell.scale = 1
            }
        } else if (window.visibility === Window.Windowed) {
            if (wasMinimized && lastNonMinimizedMaximized) {
                Qt.callLater(function() { if (window.visibility === Window.Windowed) window.showMaximized() })
            } else if (!minimizing) {
                lastNonMinimizedMaximized = false
                wasMinimized = false
                Qt.callLater(rememberNormalGeometry)
            }
            if (!windowStateTransition.running && !openingTransition.running) {
                shell.opacity = 1
                shell.scale = 1
            }
        }
    }
    onClosing: close => {
        var normal = visibility === Window.Windowed ? Qt.rect(x, y, width, height) : normalGeometry
        var maximized = visibility === Window.Minimized ? lastNonMinimizedMaximized : visibility === Window.Maximized
        preferences.saveWindowGeometry(normal.x, normal.y, normal.width, normal.height,
                                       maximized)
        if (!allowClose && visibility !== Window.Minimized) {
            close.accepted = false
            if (!closingTransition) {
                closingTransition = true
                openingTransition.stop()
                windowStateTransition.stop()
                closingAnimation.start()
            }
            return
        }
    }
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
        id: shell
        objectName: "applicationShell"
        anchors.fill: parent
        spacing: 0
        transformOrigin: Item.Center
        opacity: 0
        scale: 0.985
        Behavior on opacity { NumberAnimation { duration: Theme.motionShort; easing.type: Easing.OutCubic } }
        Behavior on scale { NumberAnimation { duration: Theme.motionMedium; easing.type: Easing.OutCubic } }
        AppTitleBar {
            objectName: "appTitleBar"
            Layout.fillWidth: true
            Layout.preferredHeight: implicitHeight
            controller: analysisController
            onToggleRequested: {
                var nextExpanded = !navigation.expanded
                navigation.expandedInCompact = nextExpanded
                preferences.setValue("sidebarExpanded", nextExpanded)
            }
            onMinimizeRequested: window.minimizeWindow()
            onMaximizeRequested: window.toggleMaximize()
            onOpenRequested: { window.currentPage = 0; checkPage.openFileDialog() }
            onExportRequested: { window.currentPage = 0; checkPage.openExportDialog() }
            onAboutRequested: {
                window.currentPage = window.currentPage === 1 ? 0 : 1
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
                Layout.preferredWidth: navigation.compact ? 0 : (navigation.expanded ? 260 : 0)
                Behavior on Layout.preferredWidth { NumberAnimation { duration: Theme.motionMedium; easing.type: Easing.OutCubic } }
                NavigationRail {
                    id: navigation
                    objectName: "navigationRail"
                    anchors.top: parent.top
                    anchors.bottom: parent.bottom
                    width: expanded ? 260 : 0
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
                objectName: "workspaceSurface"
                Layout.fillWidth: true
                Layout.fillHeight: true
                color: Colors.surface
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
    MouseArea { x: 0; y: 5; width: 5; height: window.height - 10; z: 10; visible: window.visibility !== Window.Maximized; cursorShape: Qt.SizeHorCursor; onPressed: window.startSystemResize(Qt.LeftEdge) }
    MouseArea { x: window.width - 5; y: 5; width: 5; height: window.height - 10; z: 10; visible: window.visibility !== Window.Maximized; cursorShape: Qt.SizeHorCursor; onPressed: window.startSystemResize(Qt.RightEdge) }
    MouseArea { x: 5; y: 0; width: window.width - 10; height: 5; z: 10; visible: window.visibility !== Window.Maximized; cursorShape: Qt.SizeVerCursor; onPressed: window.startSystemResize(Qt.TopEdge) }
    MouseArea { x: 5; y: window.height - 5; width: window.width - 10; height: 5; z: 10; visible: window.visibility !== Window.Maximized; cursorShape: Qt.SizeVerCursor; onPressed: window.startSystemResize(Qt.BottomEdge) }
    MouseArea { x: 0; y: 0; width: 5; height: 5; z: 10; visible: window.visibility !== Window.Maximized; cursorShape: Qt.SizeFDiagCursor; onPressed: window.startSystemResize(Qt.TopEdge | Qt.LeftEdge) }
    MouseArea { x: window.width - 5; y: 0; width: 5; height: 5; z: 10; visible: window.visibility !== Window.Maximized; cursorShape: Qt.SizeBDiagCursor; onPressed: window.startSystemResize(Qt.TopEdge | Qt.RightEdge) }
    MouseArea { x: 0; y: window.height - 5; width: 5; height: 5; z: 10; visible: window.visibility !== Window.Maximized; cursorShape: Qt.SizeBDiagCursor; onPressed: window.startSystemResize(Qt.BottomEdge | Qt.LeftEdge) }
    MouseArea { x: window.width - 5; y: window.height - 5; width: 5; height: 5; z: 10; visible: window.visibility !== Window.Maximized; cursorShape: Qt.SizeFDiagCursor; onPressed: window.startSystemResize(Qt.BottomEdge | Qt.RightEdge) }
    SettingsPage {
        id: settingsDialog
        objectName: "settingsDialog"
        controller: analysisController
        onReturnToCheckRequested: window.currentPage = 0
    }
    AppToast {
        id: toast
        objectName: "appToast"
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
    ParallelAnimation {
        id: openingTransition
        NumberAnimation { target: shell; property: "opacity"; from: 0; to: 1; duration: Theme.motionMedium; easing.type: Easing.OutCubic }
        NumberAnimation { target: shell; property: "scale"; from: 0.985; to: 1; duration: Theme.motionMedium; easing.type: Easing.OutCubic }
    }
    SequentialAnimation {
        id: windowStateTransition
        NumberAnimation { target: shell; property: "opacity"; to: 0.38; duration: 90; easing.type: Easing.InCubic }
        ScriptAction {
            script: {
                if (window.targetMaximized) {
                    window.lastNonMinimizedMaximized = true
                    window.showMaximized()
                } else {
                    window.lastNonMinimizedMaximized = false
                    window.showNormal()
                }
                shell.scale = 0.985
            }
        }
        ParallelAnimation {
            NumberAnimation { target: shell; property: "opacity"; to: 1; duration: 180; easing.type: Easing.OutCubic }
            NumberAnimation { target: shell; property: "scale"; to: 1; duration: 180; easing.type: Easing.OutCubic }
        }
    }
    ParallelAnimation {
        id: closingAnimation
        NumberAnimation { target: shell; property: "opacity"; to: 0; duration: 170; easing.type: Easing.InCubic }
        NumberAnimation { target: shell; property: "scale"; to: 0.985; duration: 170; easing.type: Easing.InCubic }
        onFinished: {
            window.allowClose = true
            window.close()
        }
    }
}
