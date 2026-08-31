import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import theme 1.0
import "../components"

Item {
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Spacing.lg
        spacing: Spacing.md
        Text { text: "Settings"; color: Colors.textPrimary; font: Typography.display }
        AppCard {
            Layout.fillWidth: true
            implicitHeight: 110
            ColumnLayout {
                anchors.fill: parent
                Text { text: "Appearance"; color: Colors.textPrimary; font: Typography.subtitle }
                RowLayout {
                    Text { text: "Theme"; color: Colors.textSecondary; font: Typography.body }
                    Item { Layout.fillWidth: true }
                    ComboBox {
                        model: ["System", "Light", "Dark"]
                        currentIndex: Theme.mode
                        onActivated: Theme.mode = currentIndex
                    }
                }
            }
        }
        AppCard {
            Layout.fillWidth: true
            implicitHeight: 96
            ColumnLayout {
                anchors.fill: parent
                Text { text: "Privacy"; color: Colors.textPrimary; font: Typography.subtitle }
                Text {
                    Layout.fillWidth: true
                    text: "Analysis is offline. Full configurations are not written to logs or history by default."
                    color: Colors.textSecondary
                    font: Typography.body
                    wrapMode: Text.Wrap
                }
            }
        }
        Item { Layout.fillHeight: true }
    }
}
