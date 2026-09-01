import QtQuick
import QtQuick.Layouts
import theme 1.0
import "../components"

AppCard {
    id: root
    property string mode: "full"
    property string vendor: "auto"
    property bool busy: false
    signal openRequested()
    signal pasteRequested()
    signal analyzeRequested()
    signal clearRequested()
    signal exportRequested()
    signal modeSelected(string value)
    signal vendorSelected(string value)
    implicitHeight: 84

    function modeLabel() {
        if (mode === "snippet") return i18n.catalog["mode.snippet"]
        if (mode === "snapshot") return i18n.catalog["mode.snapshot"]
        return i18n.catalog["mode.full"]
    }

    function vendorLabel() {
        return vendor === "huawei" ? i18n.catalog["vendor.huawei"] : i18n.catalog["vendor.auto"]
    }

    RowLayout {
        anchors.fill: parent
        spacing: Spacing.sm

        AppButton { text: i18n.catalog["toolbar.open"]; onClicked: root.openRequested() }
        AppButton { text: i18n.catalog["toolbar.paste"]; onClicked: root.pasteRequested() }
        AppButton {
            text: root.busy ? i18n.catalog["toolbar.analyzing"] : i18n.catalog["toolbar.analyze"]
            prominent: true
            enabled: !root.busy
            onClicked: root.analyzeRequested()
        }
        AppButton { text: i18n.catalog["toolbar.clear"]; enabled: !root.busy; onClicked: root.clearRequested() }
        AppButton { text: i18n.catalog["toolbar.export"]; onClicked: root.exportRequested() }
        Item { Layout.fillWidth: true }
        SelectionField {
            id: modeField
            objectName: "modeSelectionField"
            Layout.preferredWidth: 174
            Layout.minimumWidth: 160
            label: i18n.catalog["toolbar.mode"]
            valueText: root.modeLabel()
            onClicked: modeDialog.open()
        }
        SelectionField {
            id: vendorField
            objectName: "vendorSelectionField"
            Layout.preferredWidth: 174
            Layout.minimumWidth: 160
            label: i18n.catalog["toolbar.vendor"]
            valueText: root.vendorLabel()
            onClicked: vendorDialog.open()
        }
    }

    SelectionDialog {
        id: modeDialog
        objectName: "modeSelectionDialog"
        optionObjectPrefix: "modeOption-"
        title: i18n.catalog["mode.choose"]
        selectedValue: root.mode
        options: [
            {
                label: i18n.catalog["mode.snippet"], value: "snippet",
                description: i18n.catalog["mode.snippet.detail"]
            },
            {
                label: i18n.catalog["mode.full"], value: "full",
                description: i18n.catalog["mode.full.detail"]
            },
            {
                label: i18n.catalog["mode.snapshot"], value: "snapshot",
                description: i18n.catalog["mode.snapshot.detail"]
            }
        ]
        onValueSelected: value => root.modeSelected(value)
    }
    SelectionDialog {
        id: vendorDialog
        objectName: "vendorSelectionDialog"
        optionObjectPrefix: "vendorOption-"
        title: i18n.catalog["vendor.choose"]
        selectedValue: root.vendor
        options: [
            {
                label: i18n.catalog["vendor.auto"], value: "auto",
                description: i18n.catalog["vendor.auto.detail"]
            },
            {
                label: i18n.catalog["vendor.huawei"], value: "huawei",
                description: i18n.catalog["vendor.huawei.detail"]
            }
        ]
        onValueSelected: value => root.vendorSelected(value)
    }
}
