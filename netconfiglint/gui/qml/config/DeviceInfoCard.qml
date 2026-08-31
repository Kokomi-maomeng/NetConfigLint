import QtQuick
import QtQuick.Layouts
import theme 1.0
import "../components"

AppCard {
    id: root
    property var detection: ({})
    implicitHeight: 78

    RowLayout {
        anchors.fill: parent
        spacing: Spacing.lg
        ColumnLayout {
            Layout.preferredWidth: 140
            spacing: 2
            Text { text: i18n.catalog["device.detected"]; color: Colors.textSecondary; font: Typography.caption }
            Text {
                text: root.detection.vendor || "Unknown"
                color: Colors.textPrimary
                font: Typography.subtitle
            }
        }
        Repeater {
            model: [
                [i18n.catalog["device.os"], root.detection.os || "Unknown"],
                [i18n.catalog["device.platform"], root.detection.platform_family || "Unknown"],
                [i18n.catalog["device.model"], root.detection.model || "Unknown"],
                [i18n.catalog["device.version"], root.detection.version || "Unknown"],
                [i18n.catalog["device.profile"], root.detection.profile_id || "unresolved"],
                [i18n.catalog["device.confidence"], Number(root.detection.confidence || 0).toFixed(2)]
            ]
            delegate: ColumnLayout {
                required property var modelData
                Layout.fillWidth: true
                spacing: 2
                Text { text: modelData[0]; color: Colors.textSecondary; font: Typography.caption }
                Text {
                    Layout.fillWidth: true
                    text: modelData[1]
                    color: Colors.textPrimary
                    font: Typography.label
                    elide: Text.ElideRight
                }
            }
        }
    }
}
