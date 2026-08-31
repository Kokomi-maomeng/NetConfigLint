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
    width: 1280
    height: 800
    minimumWidth: 960
    minimumHeight: 600
    title: i18n.catalog["app.title"]
    color: Colors.background
    Material.theme: Theme.dark ? Material.Dark : Material.Light
    Material.accent: Colors.primary
    property int currentPage: 0

    RowLayout {
        anchors.fill: parent
        spacing: 0
        NavigationRail {
            id: navigation
            Layout.fillHeight: true
            Layout.preferredWidth: window.width < 1080 ? 72 : 224
            currentIndex: window.currentPage
            onPageSelected: index => window.currentPage = index
        }
        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: window.currentPage
            ConfigCheckPage { controller: analysisController }
            HistoryPage { controller: analysisController }
            RuleLibraryPage { controller: analysisController }
            SettingsPage { controller: analysisController }
            AboutPage { }
        }
    }

    AppToast {
        id: toast
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: Spacing.lg
    }
    Connections {
        target: analysisController
        function onToastRequested(message) { toast.show(message) }
    }
}
