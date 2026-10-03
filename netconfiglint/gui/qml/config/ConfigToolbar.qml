pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import theme 1.0
import "../components"
AppCard {
    id: root
    property var controller
    signal openRequested()
    signal exportRequested()
    signal temporaryExportRequested()
    implicitWidth: 0
    implicitHeight: Math.max(40, toolbarFlow.implicitHeight)
    padding: 0
    color: "transparent"
    border.color: "transparent"
    function vendorOptions() {
        return controller.vendorOptions.map(function(option) {
            return { value: option.value, label: i18n.catalog["vendor." + option.value] || option.label }
        })
    }
    function vendorLabel() {
        var choices = vendorOptions()
        for (var i = 0; i < choices.length; ++i) if (choices[i].value === controller.vendor) return choices[i].label
        return controller.vendor
    }
    Flow {
        id: toolbarFlow
        width: root.width
        spacing: 8
        AppButton { objectName: "openButton"; implicitHeight: 40; font: Typography.body; text: i18n.catalog["toolbar.open"]; onClicked: root.openRequested() }
        AppButton { objectName: "saveConfigButton"; implicitHeight: 40; text: i18n.catalog["file.save"]; onClicked: root.controller.saveConfiguration() }
        AppButton { objectName: "exportButton"; implicitHeight: 40; font: Typography.body; text: i18n.catalog["toolbar.export"]; enabled: root.controller.sourceText.trim().length > 0; onClicked: root.exportRequested() }
        SelectionField {
            objectName: "modeSelectionField"
            implicitHeight: 40
            font: Typography.body
            label: i18n.catalog["toolbar.mode"]
            valueText: i18n.catalog["mode." + root.controller.mode]
            onClicked: modeDialog.open()
        }
        SelectionField {
            objectName: "vendorSelectionField"
            implicitHeight: 40
            font: Typography.body
            label: i18n.catalog["toolbar.vendor"]
            valueText: root.vendorLabel()
            onClicked: vendorDialog.open()
        }
        AppButton {
            objectName: "completionButton"
            implicitHeight: 40
            font: Typography.body
            text: i18n.catalog["completion.title"] + ": " + (commandCompletion.automatic
                  ? i18n.catalog["vendor.auto"] : commandCompletion.selectedVendors.join(" + "))
            onClicked: completionDialog.open()
        }
        AppButton {
            id: moreButton
            objectName: "toolbarMoreButton"
            implicitHeight: 40
            text: i18n.catalog["toolbar.more"]
            onClicked: moreMenu.open()
            AppMenu {
                id: moreMenu
                y: moreButton.height + 6
                width: Math.min(360, root.Window.width - 40)
                MenuItem { objectName: "saveAsConfigButton"; text: i18n.catalog["file.save_as"]; onTriggered: root.controller.saveAsRequested("configuration") }
                MenuItem { objectName: "initialViewField"; visible: root.controller.mode === "snippet"; text: i18n.catalog["view.context"] + ": " + (root.controller.initialView || i18n.catalog["view.system"]); onTriggered: contextDialog.open() }
                MenuItem { objectName: "exampleButton"; text: i18n.catalog["editor.example"]; onTriggered: root.controller.requestAction("example", "") }
                MenuItem { objectName: "undoExampleButton"; visible: root.controller.exampleAvailable; text: i18n.catalog["editor.undo_example"]; onTriggered: root.controller.requestAction("undo_example", "") }
                MenuItem { objectName: "newSourceButton"; text: i18n.catalog["file.new"]; onTriggered: root.controller.requestAction("clear", "") }
                MenuItem { objectName: "supportScopeButton"; text: i18n.catalog["support.title"]; onTriggered: supportDialog.open() }
                MenuSeparator {}
                MenuItem { objectName: "temporaryExportButton"; text: i18n.catalog["temporary.export"]; onTriggered: root.temporaryExportRequested() }
                MenuItem { objectName: "temporaryCopyButton"; text: i18n.catalog["temporary.to_configuration"]; onTriggered: root.controller.requestAction("scratch", "") }
                MenuItem { objectName: "storageInfoButton"; text: i18n.catalog["storage.locations"]; onTriggered: storageDialog.open() }
            }
        }
        AppButton {
            id: panelsButton
            objectName: "panelsButton"
            implicitHeight: 40
            font: Typography.body
            text: i18n.catalog["panels.show"]
            onClicked: panelsMenu.open()
            AppMenu {
                id: panelsMenu
                y: panelsButton.height + 6
                width: 240
                Repeater {
                    model: ["diagnostics", "temporary"]
                    delegate: MenuItem {
                        required property string modelData
                        objectName: "panelToggle-" + modelData
                        text: i18n.catalog["panel." + modelData]
                        checkable: true
                        checked: preferences.values.panels.indexOf(modelData) >= 0
                        onTriggered: {
                            var visiblePanels = preferences.values.panels.slice()
                            var index = visiblePanels.indexOf(modelData)
                            if (index >= 0) visiblePanels.splice(index, 1)
                            else visiblePanels.push(modelData)
                            preferences.setValue("panels", visiblePanels)
                        }
                    }
                }
            }
        }
    }
    AppDialog {
        id: storageDialog
        title: i18n.catalog["storage.locations"]
        contentItem: SelectableText { wrapMode: TextEdit.WrapAnywhere; text: i18n.catalog["temporary.scope"] + "\n" + root.controller.temporaryPath + "\n\n" + i18n.catalog["settings.history"] + ": " + root.controller.historyPath }
    }
    SelectionDialog {
        id: modeDialog
        objectName: "modeSelectionDialog"
        optionObjectPrefix: "modeOption-"
        title: i18n.catalog["mode.choose"]
        selectedValue: root.controller.mode
        options: [
            { label: i18n.catalog["mode.snippet"], value: "snippet", description: i18n.catalog["mode.snippet.detail"] },
            { label: i18n.catalog["mode.message"], value: "message", description: i18n.catalog["mode.message.detail"] },
            { label: i18n.catalog["mode.view"], value: "view", description: i18n.catalog["mode.view.detail"] },
            { label: i18n.catalog["mode.full"], value: "full", description: i18n.catalog["mode.full.detail"] },
        ]
        onValueSelected: value => root.controller.mode = value
    }
    SelectionDialog {
        id: vendorDialog
        objectName: "vendorSelectionDialog"
        optionObjectPrefix: "vendorOption-"
        title: i18n.catalog["vendor.choose"]
        selectedValue: root.controller.vendor
        options: root.vendorOptions()
        onValueSelected: value => root.controller.vendor = value
    }
    AppDialog {
        id: supportDialog
        objectName: "supportDialog"
        title: i18n.catalog["support.title"]
        height: Math.min(620, root.Window.height - 60)
        contentItem: ColumnLayout {
            Label { Layout.fillWidth: true; wrapMode: Text.Wrap; font: Typography.body; color: Colors.textSecondary; text: i18n.catalog["support.boundary"] }
            Label { Layout.fillWidth: true; wrapMode: Text.Wrap; font: Typography.caption; color: Colors.textSecondary; text: "H3C: " + root.controller.supportSummary.vendors.h3c.completion_references.join(" · ") + "\nHuawei: " + root.controller.supportSummary.vendors.huawei.completion_references.join(" · ") }
            TextField { id: supportSearch; objectName: "supportSearch"; Layout.fillWidth: true; placeholderText: i18n.catalog["support.search"] }
            ListView {
                objectName: "supportMissingList"
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                model: root.controller.supportSummary.msr7.missing_root_titles.filter(function(title) { return title.toLowerCase().indexOf(supportSearch.text.toLowerCase()) >= 0 })
                ScrollBar.vertical: AppScrollBar {}
                delegate: Label { required property string modelData; width: ListView.view.width; text: modelData; font: Typography.body; color: Colors.textPrimary; padding: 4; wrapMode: Text.Wrap }
            }
            AppButton { text: i18n.catalog["support.export"]; onClicked: supportSaveDialog.open() }
        }
    }
    FileDialog {
        id: supportSaveDialog
        title: i18n.catalog["support.export"]
        fileMode: FileDialog.SaveFile
        defaultSuffix: "json"
        onAccepted: root.controller.exportSupportInventory(String(selectedFile))
    }
    AppDialog {
        id: contextDialog
        objectName: "contextDialog"
        title: i18n.catalog["view.context"]
        contentItem: ColumnLayout {
            Label { Layout.fillWidth: true; text: i18n.catalog["view.help"]; wrapMode: Text.Wrap; font: Typography.body; color: Colors.textSecondary }
            TextField { id: contextInput; objectName: "contextInput"; Layout.fillWidth: true; placeholderText: "bgp 65000 / interface GigabitEthernet1/0/1"; text: root.controller.initialView; maximumLength: 160 }
            Flow {
                Layout.fillWidth: true
                spacing: 6
                AppButton { text: i18n.catalog["view.system"]; onClicked: contextInput.text = "" }
                AppButton { text: "BGP"; onClicked: contextInput.text = "bgp 65000" }
                AppButton { text: "OSPF"; onClicked: contextInput.text = "ospf 1" }
                AppButton { text: i18n.catalog["view.interface"]; onClicked: contextInput.text = "interface GigabitEthernet1/0/1" }
            }
            AppButton { text: i18n.catalog["common.done"]; onClicked: { root.controller.initialView = contextInput.text; contextDialog.close() } }
        }
    }
    AppDialog {
        id: completionDialog
        objectName: "completionDialog"
        title: i18n.catalog["completion.title"]
        contentItem: ColumnLayout {
            spacing: 12
            Label {
                Layout.fillWidth: true
                text: i18n.catalog["completion.help"]
                wrapMode: Text.Wrap
                color: Colors.textSecondary
                font: Typography.body
            }
            RadioButton {
                objectName: "completionOption-auto"
                text: i18n.catalog["vendor.auto"]
                checked: commandCompletion.automatic
                onClicked: commandCompletion.toggleVendor("auto")
            }
            Repeater {
                model: root.controller.vendorOptions.filter(option => option.value !== "auto")
                delegate: CheckBox {
                    required property var modelData
                    objectName: "completionOption-" + modelData.value
                    text: modelData.label
                    checked: commandCompletion.selectedVendors.indexOf(modelData.value) >= 0
                    onClicked: commandCompletion.toggleVendor(modelData.value)
                }
            }
            AppButton {
                Layout.alignment: Qt.AlignRight
                text: i18n.catalog["common.close"]
                onClicked: completionDialog.close()
            }
        }
    }
}
