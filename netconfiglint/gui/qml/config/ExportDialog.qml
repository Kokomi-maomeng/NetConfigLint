pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import theme 1.0
import "../components"
AppDialog {
    id: root
    property var controller
    property string scope: "full"
    property string format: "json"
    property bool diagnosticsFirst: false
    signal saveRequested(string format)
    title: i18n.catalog["dialog.export"]
    onOpened: controller.cancelExport()
    contentItem: ColumnLayout {
        spacing: 12
        SelectableText { text: i18n.catalog["export.content"]; font: Typography.subtitle }
        ButtonGroup { id: scopeGroup }
        Repeater {
            model: ["full", "configuration", "diagnostics"]
            delegate: RadioButton {
                required property string modelData
                objectName: "exportScope-" + modelData
                Layout.fillWidth: true
                text: i18n.catalog["export." + modelData]
                checked: root.scope === modelData
                ButtonGroup.group: scopeGroup
                onClicked: root.scope = modelData
            }
        }
        CheckBox {
            objectName: "exportDiagnosticsFirst"
            Layout.fillWidth: true
            visible: root.scope === "full"
            text: i18n.catalog["export.diagnostics_first"]
            checked: root.diagnosticsFirst
            onToggled: root.diagnosticsFirst = checked
        }
        SelectableText { text: i18n.catalog["export.format"]; font: Typography.subtitle }
        RowLayout {
            ButtonGroup { id: formatGroup }
            Repeater {
                model: ["json", "md", "txt"]
                delegate: RadioButton {
                    required property string modelData
                    objectName: "exportFormat-" + modelData
                    text: modelData === "md" ? "Markdown" : modelData.toUpperCase()
                    checked: root.format === modelData
                    ButtonGroup.group: formatGroup
                    onClicked: root.format = modelData
                }
            }
        }
        SelectableText {
            Layout.fillWidth: true
            visible: root.scope !== "configuration" && !root.controller.resultCurrent
            text: i18n.catalog["export.needs_analysis"]
            color: Colors.warning
            font: Typography.caption
        }
        RowLayout {
            Layout.fillWidth: true
            Item { Layout.fillWidth: true }
            AppButton { objectName: "exportCancel"; text: i18n.catalog["common.cancel"]; onClicked: root.reject() }
            AppButton {
                objectName: "exportConfirm"
                text: i18n.catalog["common.confirm"]
                prominent: true
                enabled: root.controller.sourceText.trim().length > 0 && (root.scope === "configuration" || root.controller.resultCurrent)
                onClicked: {
                    if (root.controller.prepareExport(root.scope, root.format, root.diagnosticsFirst)) {
                        root.close()
                        root.saveRequested(root.format)
                    }
                }
            }
        }
    }
}
