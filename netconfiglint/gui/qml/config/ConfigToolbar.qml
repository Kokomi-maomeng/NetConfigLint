import QtQuick
import QtQuick.Controls
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
    implicitHeight: 68

    RowLayout {
        anchors.fill: parent
        spacing: Spacing.xs

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
        Text { text: i18n.catalog["toolbar.mode"]; color: Colors.textSecondary; font: Typography.caption }
        ComboBox {
            id: modeBox
            model: [
                { label: i18n.catalog["mode.snippet"], value: "snippet" },
                { label: i18n.catalog["mode.full"], value: "full" },
                { label: i18n.catalog["mode.snapshot"], value: "snapshot" }
            ]
            textRole: "label"
            valueRole: "value"
            currentIndex: root.mode === "snippet" ? 0 : root.mode === "snapshot" ? 2 : 1
            onActivated: root.modeSelected(currentValue)
            Layout.preferredWidth: 118
        }
        Text { text: i18n.catalog["toolbar.vendor"]; color: Colors.textSecondary; font: Typography.caption }
        ComboBox {
            id: vendorBox
            model: [
                { label: i18n.catalog["vendor.auto"], value: "auto" },
                { label: i18n.catalog["vendor.huawei"], value: "huawei" }
            ]
            textRole: "label"
            valueRole: "value"
            currentIndex: root.vendor === "huawei" ? 1 : 0
            onActivated: root.vendorSelected(currentValue)
            Layout.preferredWidth: 110
        }
    }
}
