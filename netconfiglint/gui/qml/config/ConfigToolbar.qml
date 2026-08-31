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

        AppButton { text: "Open"; onClicked: root.openRequested() }
        AppButton { text: "Paste"; onClicked: root.pasteRequested() }
        AppButton {
            text: root.busy ? "Analyzing…" : "Analyze"
            prominent: true
            enabled: !root.busy
            onClicked: root.analyzeRequested()
        }
        AppButton { text: "Clear"; enabled: !root.busy; onClicked: root.clearRequested() }
        AppButton { text: "Export"; onClicked: root.exportRequested() }
        Item { Layout.fillWidth: true }
        Text { text: "Mode"; color: Colors.textSecondary; font: Typography.caption }
        ComboBox {
            id: modeBox
            model: ["Snippet", "Full", "Snapshot"]
            currentIndex: root.mode === "snippet" ? 0 : root.mode === "snapshot" ? 2 : 1
            onActivated: root.modeSelected(["snippet", "full", "snapshot"][currentIndex])
            Layout.preferredWidth: 118
        }
        Text { text: "Vendor"; color: Colors.textSecondary; font: Typography.caption }
        ComboBox {
            id: vendorBox
            model: ["Auto", "Huawei"]
            currentIndex: root.vendor === "huawei" ? 1 : 0
            onActivated: root.vendorSelected(currentIndex === 1 ? "huawei" : "auto")
            Layout.preferredWidth: 110
        }
    }
}
