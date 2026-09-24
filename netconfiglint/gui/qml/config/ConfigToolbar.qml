pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import theme 1.0
import "../components"
AppCard {
    id: root
    property var controller
    signal openRequested()
    signal exportRequested()
    implicitHeight: toolbarFlow.implicitHeight + padding * 2
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
    RowLayout {
        id: toolbarFlow
        anchors.fill: parent
        spacing: 8
        AppButton { objectName: "openButton"; text: i18n.catalog["toolbar.open"]; onClicked: root.openRequested() }
        AppButton { objectName: "exportButton"; text: i18n.catalog["toolbar.export"]; enabled: root.controller.sourceText.trim().length > 0; onClicked: root.exportRequested() }
        SelectionField {
            objectName: "modeSelectionField"
            label: i18n.catalog["toolbar.mode"]
            valueText: i18n.catalog["mode." + root.controller.mode]
            onClicked: modeDialog.open()
        }
        SelectionField {
            objectName: "vendorSelectionField"
            label: i18n.catalog["toolbar.vendor"]
            valueText: root.vendorLabel()
            onClicked: vendorDialog.open()
        }
        AppButton {
            id: panelsButton
            objectName: "panelsButton"
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
        Item { Layout.fillWidth: true }
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
}
