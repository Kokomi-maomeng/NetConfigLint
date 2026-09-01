import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import theme 1.0
import "../components"

Item {
    id: root
    property var controller
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Spacing.lg
        spacing: Spacing.md
        SelectableText {
            text: i18n.catalog["page.settings"]
            color: Colors.textPrimary
            font: Typography.display
        }
        AppCard {
            Layout.fillWidth: true
            implicitHeight: 160
            ColumnLayout {
                anchors.fill: parent
                SelectableText {
                    text: i18n.catalog["settings.appearance"]
                    color: Colors.textPrimary
                    font: Typography.subtitle
                }
                RowLayout {
                    SelectableText {
                        text: i18n.catalog["settings.theme"]
                        color: Colors.textSecondary
                        font: Typography.body
                    }
                    Item { Layout.fillWidth: true }
                    ComboBox {
                        model: [i18n.catalog["settings.system"], i18n.catalog["settings.light"], i18n.catalog["settings.dark"]]
                        currentIndex: Theme.mode
                        onActivated: Theme.mode = currentIndex
                    }
                }
                RowLayout {
                    Layout.fillWidth: true
                    SelectableText {
                        text: i18n.catalog["settings.language"]
                        color: Colors.textSecondary
                        font: Typography.body
                    }
                    Item { Layout.fillWidth: true }
                    ComboBox {
                        model: i18n.availableLanguages
                        textRole: "label"
                        valueRole: "code"
                        currentIndex: i18n.language === "zh_CN" ? 1 : 0
                        onActivated: i18n.language = currentValue
                    }
                }
            }
        }
        AppCard {
            Layout.fillWidth: true
            implicitHeight: 180
            ColumnLayout {
                anchors.fill: parent
                SelectableText {
                    text: i18n.catalog["settings.privacy"]
                    color: Colors.textPrimary
                    font: Typography.subtitle
                }
                SelectableText {
                    Layout.fillWidth: true
                    text: i18n.catalog["settings.privacy_detail"]
                    color: Colors.textSecondary
                    font: Typography.body
                    wrapMode: Text.Wrap
                }
                RowLayout {
                    Layout.fillWidth: true
                    ColumnLayout {
                        Layout.fillWidth: true
                        SelectableText {
                            text: i18n.catalog["settings.history"]
                            color: Colors.textPrimary
                            font: Typography.body
                        }
                        SelectableText {
                            Layout.fillWidth: true
                            text: i18n.catalog["settings.history_detail"]
                            color: Colors.textSecondary
                            font: Typography.caption
                            wrapMode: Text.Wrap
                        }
                    }
                    Switch {
                        checked: root.controller.historyEnabled
                        onToggled: root.controller.historyEnabled = checked
                    }
                }
            }
        }
        Item { Layout.fillHeight: true }
    }
}
