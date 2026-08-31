import QtQuick
import QtQuick.Layouts
import theme 1.0
import "../components"

Item {
    ColumnLayout {
        anchors.centerIn: parent
        width: Math.min(parent.width - Spacing.xl * 2, 640)
        spacing: Spacing.md
        Rectangle {
            Layout.alignment: Qt.AlignHCenter
            width: 72; height: 72; radius: Spacing.radiusLarge
            color: Colors.primary
            Text { anchors.centerIn: parent; text: "N"; color: Colors.onPrimary; font: Typography.display }
        }
        Text {
            Layout.alignment: Qt.AlignHCenter
            text: "NetConfigLint v1.0 Beta"
            color: Colors.textPrimary
            font: Typography.display
        }
        Text {
            Layout.fillWidth: true
            text: "A fast, offline, extensible static analyzer for network device configurations."
            color: Colors.textSecondary
            font: Typography.body
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.Wrap
        }
        Text {
            Layout.fillWidth: true
            text: "Static analysis cannot guarantee that a configuration will operate correctly on physical hardware."
            color: Colors.warning
            font: Typography.body
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.Wrap
        }
    }
}
