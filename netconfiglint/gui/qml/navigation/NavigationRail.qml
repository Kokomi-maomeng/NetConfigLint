import QtQuick
import QtQuick.Layouts
import theme 1.0

Rectangle {
    id: root
    property int currentIndex: 0
    property bool expanded: width >= 180
    signal pageSelected(int index)
    color: Colors.surface
    border.color: Colors.outlineVariant
    implicitWidth: expanded ? 224 : 72

    Behavior on implicitWidth { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Spacing.sm
        spacing: Spacing.xs

        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: 56
            Rectangle {
                width: 38; height: 38; radius: Spacing.radiusMedium
                color: Colors.primary
                Text {
                    anchors.centerIn: parent
                    text: "N"
                    color: Colors.onPrimary
                    font: Typography.title
                }
            }
            Text {
                Layout.fillWidth: true
                visible: root.expanded
                text: "NetConfigLint"
                color: Colors.textPrimary
                font: Typography.subtitle
                elide: Text.ElideRight
            }
        }

        Repeater {
            model: [
                { label: "Configuration Check", icon: "check.svg" },
                { label: "History", icon: "history.svg" },
                { label: "Rule Library", icon: "rules.svg" },
                { label: "Settings", icon: "settings.svg" },
                { label: "About", icon: "about.svg" }
            ]
            delegate: NavigationItem {
                required property int index
                required property var modelData
                Layout.fillWidth: true
                text: modelData.label
                iconSource: Qt.resolvedUrl("../../../resources/icons/" + modelData.icon)
                expanded: root.expanded
                selected: root.currentIndex === index
                onClicked: root.pageSelected(index)
            }
        }
        Item { Layout.fillHeight: true }
        Text {
            Layout.fillWidth: true
            visible: root.expanded
            text: "Offline analysis"
            color: Colors.success
            font: Typography.caption
            horizontalAlignment: Text.AlignHCenter
        }
    }
}
