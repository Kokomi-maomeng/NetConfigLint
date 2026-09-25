pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import theme 1.0
import "../components"
AppDialog {
    id: root
    property var controller
    title: i18n.catalog["page.settings"]
    width: Overlay.overlay ? Math.min(640, Overlay.overlay.width - 48) : 640
    height: Overlay.overlay ? Math.min(760, Overlay.overlay.height - 48) : 760
    onOpened: titleField.text = preferences.values.panelTitle
    contentItem: ScrollView {
        id: settingsScroll
        clip: true
        ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
        ScrollBar.vertical: AppScrollBar { }
        ColumnLayout {
            width: settingsScroll.availableWidth
            spacing: 20
            SelectableText { text: i18n.catalog["settings.general"]; font: Typography.subtitle }
            RowLayout {
                Layout.fillWidth: true
                SelectableText { text: i18n.catalog["settings.language"]; Layout.fillWidth: true }
                SelectionField {
                    label: i18n.catalog["settings.language"]
                    valueText: i18n.language === "zh_CN" ? "简体中文" : "English"
                    onClicked: languageDialog.open()
                }
            }
            ColumnLayout {
                Layout.fillWidth: true
                SelectableText { text: i18n.catalog["settings.panel_title"] }
                RowLayout {
                    Layout.fillWidth: true
                    AppTextField {
                        id: titleField
                        objectName: "panelTitleField"
                        Layout.fillWidth: true
                        maximumLength: 40
                        onAccepted: preferences.setValue("panelTitle", text)
                    }
                    AppButton {
                        text: i18n.catalog["common.save"]
                        enabled: titleField.text.trim().length > 0
                        onClicked: preferences.setValue("panelTitle", titleField.text)
                    }
                }
            }
            Rectangle { Layout.fillWidth: true; height: 1; color: Colors.outlineVariant }
            SelectableText { text: i18n.catalog["settings.appearance"]; font: Typography.subtitle }
            RowLayout {
                Layout.fillWidth: true
                SelectableText { text: i18n.catalog["settings.theme"]; Layout.fillWidth: true }
                SelectionField {
                    label: i18n.catalog["settings.theme"]
                    valueText: i18n.catalog[["settings.system", "settings.light", "settings.dark"][Theme.mode]]
                    onClicked: themeDialog.open()
                }
            }
            SelectableText { text: i18n.catalog["settings.color"] }
            GridLayout {
                Layout.fillWidth: true
                columns: 5
                columnSpacing: 6
                rowSpacing: 10
                Repeater {
                    model: ["violet", "blue", "green", "rose", "amber", "teal", "cyan", "indigo", "coral", "slate"]
                    delegate: Button {
                        id: colorButton
                        required property string modelData
                        objectName: "themeColor-" + modelData
                        Layout.fillWidth: true
                        implicitHeight: 70
                        hoverEnabled: true
                        Accessible.name: i18n.catalog["color." + modelData]
                        onClicked: preferences.setValue("themeColor", modelData)
                        background: Rectangle {
                            radius: 16
                            color: colorButton.hovered ? Colors.surfaceContainerHigh : Colors.surface
                            border.color: Theme.accent === colorButton.modelData ? Colors.primary : Colors.outlineVariant
                            border.width: Theme.accent === colorButton.modelData ? 2 : 1
                        }
                        contentItem: ColumnLayout {
                            spacing: 4
                            Rectangle {
                                Layout.alignment: Qt.AlignHCenter
                                width: 24; height: 24; radius: 12
                                color: Colors.palettes[colorButton.modelData][Theme.dark ? 2 : 0]
                            }
                            Text {
                                Layout.alignment: Qt.AlignHCenter
                                text: i18n.catalog["color." + colorButton.modelData]
                                font: Typography.caption
                                color: Colors.textPrimary
                            }
                        }
                    }
                }
            }
            Rectangle { Layout.fillWidth: true; height: 1; color: Colors.outlineVariant }
            RowLayout {
                Layout.fillWidth: true
                SelectableText { text: i18n.catalog["settings.history"]; Layout.fillWidth: true }
                Switch {
                    objectName: "historySwitch"
                    checked: root.controller.historyEnabled
                    onClicked: {
                        if (checked) root.controller.historyEnabled = true
                        else { checked = true; disableHistoryDialog.open() }
                    }
                }
            }
            AppButton {
                text: i18n.catalog["history.clear"]
                onClicked: root.controller.clearHistory()
            }
        }
    }
    footer: DialogButtonBox {
        AppButton { text: i18n.catalog["common.done"]; DialogButtonBox.buttonRole: DialogButtonBox.AcceptRole }
        onAccepted: root.close()
        background: Item { }
    }
    SelectionDialog {
        id: languageDialog
        title: i18n.catalog["settings.language"]
        selectedValue: i18n.language
        options: [{label:"English",value:"en"},{label:"简体中文",value:"zh_CN"}]
        onValueSelected: value => i18n.language = value
    }
    SelectionDialog {
        id: themeDialog
        title: i18n.catalog["settings.theme"]
        selectedValue: String(Theme.mode)
        options: [{label:i18n.catalog["settings.system"],value:"0"}, {label:i18n.catalog["settings.light"],value:"1"}, {label:i18n.catalog["settings.dark"],value:"2"}]
        onValueSelected: value => preferences.setValue("themeMode", Number(value))
    }
    AppDialog {
        id: disableHistoryDialog
        objectName: "disableHistoryDialog"
        title: i18n.catalog["settings.history"]
        width: 440
        contentItem: SelectableText { text: i18n.catalog["history.disable_confirm"]; wrapMode: TextEdit.WordWrap }
        footer: DialogButtonBox {
            Button { objectName: "disableHistoryCancel"; text: i18n.catalog["common.cancel"]; DialogButtonBox.buttonRole: DialogButtonBox.RejectRole }
            Button { objectName: "disableHistoryConfirm"; text: i18n.catalog["common.confirm"]; DialogButtonBox.buttonRole: DialogButtonBox.AcceptRole }
            onAccepted: { root.controller.historyEnabled = false; disableHistoryDialog.close() }
            onRejected: disableHistoryDialog.close()
        }
    }
}
