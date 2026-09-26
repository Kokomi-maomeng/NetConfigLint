pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import theme 1.0
import "../components"
Rectangle {
    id: root
    property int currentIndex: 0
    property var controller
    property bool historyExpanded: true
    property var selectedHistory: []
    property int lastHistoryIndex: -1
    property bool compact: root.Window.width < 1180
    property bool expandedInCompact: false
    property bool expanded: preferences.values.sidebarExpanded && (!compact || expandedInCompact)
    onCompactChanged: expandedInCompact = false
    signal pageSelected(int index)
    signal historySelected(string entryId)
    signal settingsRequested()
    function selectHistory(entryId, row, modifiers) {
        var selected = selectedHistory.slice()
        if (modifiers & Qt.ShiftModifier && lastHistoryIndex >= 0) {
            selected = root.controller.historyIdsBetween(lastHistoryIndex, row)
        } else if (modifiers & Qt.ControlModifier) {
            var existing = selected.indexOf(entryId)
            if (existing >= 0) selected.splice(existing, 1)
            else selected.push(entryId)
        } else {
            selected = []
            root.historySelected(entryId)
        }
        selectedHistory = selected
        lastHistoryIndex = row
    }
    color: Colors.surfaceContainerLow
    clip: true
    Behavior on Layout.preferredWidth { NumberAnimation { duration: Theme.motionMedium; easing.type: Easing.OutCubic } }
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 14
        spacing: Spacing.xs
        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: 48
            spacing: 10
            Image {
                Layout.preferredWidth: 28
                Layout.preferredHeight: 28
                source: Qt.resolvedUrl("../../../resources/icons/app-master.png")
                sourceSize.width: 56
                sourceSize.height: 56
                fillMode: Image.PreserveAspectFit
                smooth: true
                mipmap: true
            }
            Text {
                Layout.fillWidth: true
                visible: root.expanded
                text: preferences.values.panelTitle
                font: Typography.subtitle
                color: Colors.textPrimary
                elide: Text.ElideRight
                renderType: Text.QtRendering
            }
        }
        NavigationItem {
            objectName: "navigation-0"
            Layout.fillWidth: true
            text: i18n.catalog["nav.check"]
            iconSource: Qt.resolvedUrl("../../../resources/icons/check.svg")
            expanded: root.expanded
            selected: root.currentIndex === 0
            onClicked: root.pageSelected(0)
        }
        NavigationItem {
            objectName: "historyToggle"
            Layout.fillWidth: true
            text: i18n.catalog["nav.history"]
            iconSource: Qt.resolvedUrl("../../../resources/icons/history.svg")
            expanded: root.expanded
            expandable: true
            expandedState: root.historyExpanded
            onClicked: root.historyExpanded = !root.historyExpanded
        }
        ToolButton {
            objectName: "deleteSelectedHistoryButton"
            visible: root.expanded && root.selectedHistory.length > 0
            Layout.fillWidth: true
            text: i18n.catalog["history.delete_selected"] + " (" + root.selectedHistory.length + ")"
            onClicked: { root.controller.removeHistories(root.selectedHistory); root.selectedHistory = [] }
        }
        Text {
            renderType: Text.QtRendering
            Layout.fillWidth: true
            visible: root.expanded && root.historyExpanded &&
                     (!root.controller.historyEnabled || historyList.count === 0)
            text: root.controller.historyEnabled ? i18n.catalog["history.empty"] : i18n.catalog["history.disabled"]
            color: Colors.textSecondary
            font: Typography.caption
            wrapMode: Text.WordWrap
        }
        ListView {
            id: historyList
            objectName: "sidebarHistoryList"
            Layout.fillWidth: true
            Layout.fillHeight: root.expanded && root.historyExpanded
            Layout.preferredHeight: root.expanded && root.historyExpanded ? 240 : 0
            visible: root.expanded && root.historyExpanded && root.controller.historyEnabled
            model: root.controller.historyModel
            clip: true
            spacing: 4
            delegate: Rectangle {
                id: historyRow
                objectName: "historyEntry-" + entryId
                required property int index
                required property string entryId
                required property string timestamp
                required property string mode
                required property string vendor
                width: historyList.width
                height: 56
                radius: 16
                color: root.selectedHistory.indexOf(entryId) >= 0 ? Colors.primaryContainer : (rowHover.hovered ? Colors.surfaceContainerHigh : "transparent")
                HoverHandler { id: rowHover }
                MouseArea {
                    anchors.fill: parent
                    onClicked: mouse => root.selectHistory(historyRow.entryId, historyRow.index, mouse.modifiers)
                }
                Column {
                    anchors.left: parent.left
                    anchors.right: deleteButton.left
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.leftMargin: 12
                    spacing: 2
                    Text { width: parent.width; elide: Text.ElideRight; text: historyRow.timestamp; color: Colors.textPrimary; font: Typography.caption; renderType: Text.QtRendering }
                    Text { width: parent.width; elide: Text.ElideRight; text: historyRow.vendor + " · " + (i18n.catalog["mode." + historyRow.mode] || historyRow.mode); color: Colors.textSecondary; font: Typography.caption; renderType: Text.QtRendering }
                }
                ToolButton {
                    id: deleteButton
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    width: 36; height: 36
                    visible: rowHover.hovered
                    text: "×"
                    Accessible.name: i18n.catalog["history.delete"]
                    onClicked: root.controller.removeHistory(historyRow.entryId)
                }
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
