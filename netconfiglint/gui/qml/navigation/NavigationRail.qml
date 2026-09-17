pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import theme 1.0
import "../components"
Rectangle {
    id: root
    property int currentIndex: 0
    property bool compact: root.Window.width < 1180
    property bool expandedInCompact: false
    property bool expanded: preferences.values.sidebarExpanded && (!compact || expandedInCompact)
    onCompactChanged: expandedInCompact = false
    signal pageSelected(int index)
    signal settingsRequested()
    color: Colors.surfaceContainerLow
    clip: true
    Behavior on Layout.preferredWidth { NumberAnimation { duration: Theme.motionMedium; easing.type: Easing.OutCubic } }
    Rectangle { anchors.right: parent.right; height: parent.height; width: 1; color: Qt.alpha(Colors.outlineVariant, 0.55) }
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 14
        spacing: Spacing.xs
        NavigationItem {
            objectName: "sidebarToggle"
            Layout.fillWidth: true
            text: root.expanded ? i18n.catalog["nav.collapse"] : i18n.catalog["nav.expand"]
            iconSource: Qt.resolvedUrl("../../../resources/icons/menu.svg")
            expanded: root.expanded
            onClicked: {
                var nextExpanded = !root.expanded
                root.expandedInCompact = nextExpanded
                preferences.setValue("sidebarExpanded", nextExpanded)
            }
        }
        Repeater {
            model: [
                { label: i18n.catalog["nav.check"], icon: "check.svg" },
                { label: i18n.catalog["nav.history"], icon: "history.svg" },
                { label: i18n.catalog["nav.about"], icon: "about.svg" }
            ]
            delegate: NavigationItem {
                required property int index
                required property var modelData
                objectName: "navigation-" + index
                Layout.fillWidth: true
                text: modelData.label
                iconSource: Qt.resolvedUrl("../../../resources/icons/" + modelData.icon)
                expanded: root.expanded
                selected: root.currentIndex === index
                onClicked: root.pageSelected(index)
            }
        }
        Item { Layout.fillHeight: true }
        NavigationItem {
            objectName: "settingsButton"
            Layout.fillWidth: true
            text: i18n.catalog["nav.settings"]
            iconSource: Qt.resolvedUrl("../../../resources/icons/settings.svg")
            expanded: root.expanded
            onClicked: root.settingsRequested()
        }
    }
}
