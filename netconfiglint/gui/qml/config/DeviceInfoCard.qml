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
            Text { text: "Detected device"; color: Colors.textSecondary; font: Typography.caption }
            Text {
                text: root.detection.vendor || "Unknown"
                color: Colors.textPrimary
                font: Typography.subtitle
            }
        }
        Repeater {
            model: [
                ["OS", root.detection.os || "Unknown"],
                ["Platform", root.detection.platform_family || "Unknown"],
                ["Model", root.detection.model || "Unknown"],
                ["Version", root.detection.version || "Unknown"],
                ["Confidence", Number(root.detection.confidence || 0).toFixed(2)]
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
