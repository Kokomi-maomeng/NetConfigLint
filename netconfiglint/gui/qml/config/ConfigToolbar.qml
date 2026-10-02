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
    implicitHeight: 40
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
    Flickable {
        id: toolbarScroll
        anchors.fill: parent
        contentWidth: toolbarFlow.implicitWidth
        contentHeight: height
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        flickableDirection: Flickable.HorizontalFlick
        ScrollBar.horizontal: AppScrollBar {}
    RowLayout {
        id: toolbarFlow
        width: Math.max(toolbarScroll.width, implicitWidth)
        height: toolbarScroll.height
        spacing: 8
        AppButton { objectName: "openButton"; implicitHeight: 40; font: Typography.body; text: i18n.catalog["toolbar.open"]; onClicked: root.openRequested() }
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
            text: i18n.catalog["completion.title"]
            onClicked: completionDialog.open()
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
        Item { Layout.fillWidth: true }
    }
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
