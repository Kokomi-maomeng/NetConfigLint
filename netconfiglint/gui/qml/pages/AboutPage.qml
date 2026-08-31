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
            text: i18n.catalog["app.title"]
            color: Colors.textPrimary
            font: Typography.display
        }
        Text {
            Layout.fillWidth: true
            text: i18n.catalog["page.about.tagline"]
            color: Colors.textSecondary
            font: Typography.body
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.Wrap
        }
        Text {
            Layout.fillWidth: true
            text: i18n.catalog["about.disclaimer"]
            color: Colors.warning
            font: Typography.body
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.Wrap
        }
    }
}
