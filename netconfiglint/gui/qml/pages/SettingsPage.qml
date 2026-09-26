pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import theme 1.0
import "../components"

AppDialog {
    id: root
    property var controller
    signal returnToCheckRequested()
    title: i18n.catalog["page.settings"]
    width: Overlay.overlay ? Math.min(780, Overlay.overlay.width - 40) : 780
    height: Overlay.overlay ? Math.min(820, Overlay.overlay.height - 40) : 820
    onOpened: titleField.text = preferences.values.panelTitle

    contentItem: ScrollView {
        id: settingsScroll
        objectName: "settingsScrollView"
        clip: true
        ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
        ScrollBar.vertical: AppScrollBar {
            objectName: "settingsVerticalScrollBar"
            parent: settingsScroll
            anchors.top: parent.top
            anchors.right: parent.right
            anchors.bottom: parent.bottom
        }
        ColumnLayout {
            width: settingsScroll.availableWidth - 12
            spacing: 4

            SettingsSection {
                objectName: "generalSettingsSection"
                Layout.fillWidth: true
                title: i18n.catalog["settings.general"]
                detail: i18n.catalog["settings.general_detail"]
                expanded: false
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
                    spacing: 8
                    SelectableText { text: i18n.catalog["settings.panel_title"]; font: Typography.label }
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
            }

            SettingsSection {
                objectName: "displaySettingsSection"
                Layout.fillWidth: true
                title: i18n.catalog["settings.theme"]
                detail: i18n.catalog[["settings.system", "settings.light", "settings.dark"][Theme.mode]]
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 12
                    Repeater {
                        model: ["light", "dark", "system"]
                        delegate: Button {
                            id: modeButton
                            required property string modelData
                            readonly property int modeValue: modelData === "system" ? 0 : (modelData === "light" ? 1 : 2)
                            objectName: "displayMode-" + modelData
                            Layout.fillWidth: true
                            Layout.preferredWidth: 1
                            Layout.minimumWidth: 0
                            implicitHeight: 142
                            hoverEnabled: true
                            onClicked: preferences.setValue("themeMode", modeValue)
                            Accessible.name: i18n.catalog["settings." + modelData]
                            background: Rectangle {
                                radius: 18
                                color: modeButton.hovered ? Colors.surfaceContainerHigh : Colors.surfaceContainerLow
                                border.color: Theme.mode === modeButton.modeValue ? Colors.primary : "transparent"
                                border.width: Theme.mode === modeButton.modeValue ? 2 : 0
                            }
                            contentItem: ColumnLayout {
                                anchors.margins: 8
                                spacing: 6
                                Rectangle {
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 82
                                    radius: 10
                                    color: modeButton.modelData === "dark" ? "#1c1d22" : "#ffffff"
                                    border.color: Qt.alpha(Colors.outlineVariant, 0.35)
                                    RowLayout {
                                        anchors.fill: parent
                                        anchors.margins: 8
                                        spacing: 5
                                        Rectangle {
                                            Layout.preferredWidth: 34
                                            Layout.fillHeight: true
                                            radius: 5
                                            color: modeButton.modelData === "dark" ? "#3a3442" : "#eee8f1"
                                        }
                                        ColumnLayout {
                                            Layout.fillWidth: true
                                            Layout.fillHeight: true
                                            spacing: 5
                                            Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 16; radius: 4; color: modeButton.modelData === "dark" ? "#403944" : "#eee8f1" }
                                            Rectangle { Layout.fillWidth: true; Layout.fillHeight: true; radius: 5; color: modeButton.modelData === "dark" ? Colors.primaryContainer : Qt.alpha(Colors.primary, 0.20) }
                                        }
                                    }
                                    Rectangle {
                                        visible: modeButton.modelData === "system"
                                        anchors.top: parent.top
                                        anchors.right: parent.right
                                        anchors.bottom: parent.bottom
                                        width: parent.width / 2
                                        topRightRadius: 10
                                        bottomRightRadius: 10
                                        color: "#1c1d22"
                                        ColumnLayout {
                                            anchors.fill: parent
                                            anchors.margins: 8
                                            spacing: 5
                                            Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 16; radius: 4; color: "#403944" }
                                            Rectangle { Layout.fillWidth: true; Layout.fillHeight: true; radius: 5; color: Colors.primaryContainer }
                                        }
                                    }
                                }
                                Text {
                                    Layout.alignment: Qt.AlignHCenter
                                    text: i18n.catalog["settings." + modeButton.modelData]
                                    font: Typography.body
                                    color: Colors.textPrimary
                                    renderType: Text.QtRendering
                                }
                            }
                        }
                    }
                }
            }

            SettingsSection {
                objectName: "colorSettingsSection"
                Layout.fillWidth: true
                title: i18n.catalog["settings.color"]
                detail: i18n.catalog["settings.color_detail"]
                GridLayout {
                    Layout.fillWidth: true
                    columns: 5
                    columnSpacing: 8
                    rowSpacing: 8
                    Repeater {
                        model: ["violet", "blue", "green", "rose", "amber", "teal", "cyan", "indigo", "coral", "slate"]
                        delegate: Button {
                            id: colorButton
                            required property string modelData
                            objectName: "themeColor-" + modelData
                            Layout.fillWidth: true
                            Layout.preferredWidth: 1
                            Layout.minimumWidth: 0
                            implicitHeight: 92
                            hoverEnabled: true
                            onClicked: preferences.setValue("themeColor", modelData)
                            Accessible.name: i18n.catalog["color." + modelData]
                            background: Rectangle {
                                radius: 16
                                color: colorButton.hovered ? Colors.surfaceContainerHigh : "transparent"
                                border.color: Theme.accent === colorButton.modelData ? Colors.primary : "transparent"
                                border.width: Theme.accent === colorButton.modelData ? 2 : 0
                            }
                            contentItem: ColumnLayout {
                                spacing: 6
                                Rectangle {
                                    Layout.alignment: Qt.AlignHCenter
                                    Layout.preferredWidth: 42
                                    Layout.preferredHeight: 42
                                    radius: 21
                                    color: Colors.palettes[colorButton.modelData][Theme.dark ? 2 : 0]
                                    Text {
                                        anchors.centerIn: parent
                                        visible: Theme.accent === colorButton.modelData
                                        text: "✓"
                                        font: Typography.label
                                        color: "white"
                                        renderType: Text.QtRendering
                                    }
                                }
                                Text {
                                    Layout.alignment: Qt.AlignHCenter
                                    text: i18n.catalog["color." + colorButton.modelData]
                                    font: Typography.body
                                    color: Colors.textPrimary
                                    renderType: Text.QtRendering
                                }
                            }
                        }
                    }
                }
            }

            SettingsSection {
                objectName: "privacySettingsSection"
                Layout.fillWidth: true
                title: i18n.catalog["settings.privacy"]
                detail: i18n.catalog["settings.history"]
                expanded: false
                RowLayout {
                    Layout.fillWidth: true
                    SelectableText { text: i18n.catalog["settings.history"]; Layout.fillWidth: true }
                    Switch {
                        id: historySwitch
                        objectName: "historySwitch"
                        checkable: false
                        checked: root.controller.historyEnabled
                        onClicked: {
                            if (root.controller.historyEnabled) disableHistoryDialog.open()
                            else root.controller.historyEnabled = true
                        }
                    }
                }
                AppButton { objectName: "clearHistoryButton"; text: i18n.catalog["history.clear"]; onClicked: clearHistoryDialog.open() }
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
    AppDialog {
        id: clearHistoryDialog
        objectName: "clearHistoryDialog"
        title: i18n.catalog["history.clear"]
        width: 440
        contentItem: SelectableText { text: i18n.catalog["history.clear_confirm"]; wrapMode: TextEdit.WordWrap }
        footer: DialogButtonBox {
            Button { objectName: "clearHistoryCancel"; text: i18n.catalog["common.cancel"]; DialogButtonBox.buttonRole: DialogButtonBox.RejectRole }
            Button { objectName: "clearHistoryConfirm"; text: i18n.catalog["common.confirm"]; DialogButtonBox.buttonRole: DialogButtonBox.AcceptRole }
            onAccepted: {
                root.controller.clearHistory()
                clearHistoryDialog.close()
                root.close()
                root.returnToCheckRequested()
            }
            onRejected: clearHistoryDialog.close()
        }
    }
}
