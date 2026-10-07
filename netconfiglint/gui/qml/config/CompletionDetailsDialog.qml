import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import theme 1.0
import "../components"

AppDialog {
    id: root
    property string ownerName: ""
    property var detail: ({ rows: [], page: 0, pages: 1, total: 0 })
    property bool busy: false
    property int requestId: -1
    property string scopeNote: ""
    signal detailLoaded(var value)
    objectName: ownerName + "CompletionDetails"
    title: i18n.catalog["completion.details"]
    height: Math.min(620, Overlay.overlay ? Overlay.overlay.height - 32 : 620)

    function show(source, cursor, row, note) {
        commandCompletion.cancelDetails(ownerName)
        filter.text = ""
        scopeNote = note || ""
        detail = { text: row.text || (row.aliases || [row.token || ""]).join(" / "),
            token: row.token || "", status: row.status || "", description: row.description || "",
            syntaxes: row.syntaxes || [row.syntax || ""], views: row.views || [],
            rows: [], page: 0, pages: 1, total: 0 }
        busy = !!row.detailKey
        open()
        if (row.detailKey) requestId = commandCompletion.requestDetails(ownerName, source, cursor, row.detailKey)
        else {
            var incoming = row.syntaxDetails || []
            // Compatibility for callers supplying an existing small detail.
            if (!incoming.length) incoming = (row.syntaxes || [row.syntax || ""]).map(function(syntax) {
                return { syntax: syntax, sources: row.sources || [], views: row.views || [],
                    scopes: row.scopes || [], annotations: row.annotations || [] }
            })
            detail.rows = incoming.slice(0, 40)
            detail.total = incoming.length
            detailLoaded(detail)
        }
    }
    function page(index) {
        if (busy || requestId < 0) return
        detail = commandCompletion.detailPage(ownerName, filter.text, index)
        detailLoaded(detail)
        detailList.positionViewAtBeginning()
    }
    onClosed: {
        filterTimer.stop()
        commandCompletion.cancelDetails(ownerName)
        requestId = -1
        busy = false
        detail = ({ rows: [], page: 0, pages: 1, total: 0 })
    }
    Connections {
        target: commandCompletion
        function onDetailReady(owner, serial, value) {
            if (!root.visible || owner !== root.ownerName || serial !== root.requestId) return
            root.detail = value
            root.busy = false
            root.detailLoaded(value)
            if (filter.text) root.page(0)
        }
    }
    Timer { id: filterTimer; interval: 160; onTriggered: root.page(0) }
    footer: DialogButtonBox {
        AppButton {
            objectName: root.ownerName + "CompletionDetailsClose"
            text: i18n.catalog["common.close"]
            DialogButtonBox.buttonRole: DialogButtonBox.RejectRole
        }
        onRejected: root.close()
    }
    contentItem: ColumnLayout {
        spacing: 8
        SelectableText {
            Layout.fillWidth: true
            text: root.detail.text || (root.detail.aliases || [root.detail.token || ""]).join(" / ")
            font: fontPalette.editorFont(16)
            color: Colors.textPrimary
            wrapMode: TextEdit.Wrap
        }
        SelectableText {
            objectName: root.ownerName + "CompletionSyntaxes"
            Layout.fillWidth: true
            text: (root.detail.syntaxes || [""])[0] || ""
            font: fontPalette.editorFont(13)
            color: Colors.textPrimary
            wrapMode: TextEdit.Wrap
        }
        Label {
            objectName: root.ownerName + "CompletionViews"
            Layout.fillWidth: true
            text: i18n.catalog["completion.views"] + " " + (root.detail.views || []).join(" / ")
            color: Colors.textSecondary
            wrapMode: Text.Wrap
        }
        Label {
            Layout.fillWidth: true
            text: i18n.catalog["completion.scope_note"] || root.scopeNote
            color: Colors.textSecondary
            font: Typography.caption
            wrapMode: Text.Wrap
        }
        Label {
            objectName: root.ownerName + "CompletionParameterDescription"
            Layout.fillWidth: true
            visible: !!root.detail.token
            text: i18n.catalog["completion.parameter_description." + root.detail.status] || root.detail.description || ""
            color: Colors.textSecondary
            wrapMode: Text.Wrap
        }
        AppTextField {
            id: filter
            objectName: root.ownerName + "CompletionDetailFilter"
            Layout.fillWidth: true
            placeholderText: i18n.catalog["editor.search"]
            onTextChanged: if (root.visible && !root.busy) filterTimer.restart()
            onAccepted: { filterTimer.stop(); root.page(0) }
        }
        RowLayout {
            Layout.fillWidth: true
            BusyIndicator { running: root.busy; visible: running; Layout.preferredWidth: 28; Layout.preferredHeight: 28 }
            Label {
                Layout.fillWidth: true
                text: root.busy ? "…" : root.detail.total + " · " + (root.detail.page + 1) + " / " + root.detail.pages
                color: Colors.textSecondary
            }
            AppButton { text: "‹"; enabled: !root.busy && root.detail.page > 0; onClicked: root.page(root.detail.page - 1) }
            AppButton { text: "›"; enabled: !root.busy && root.detail.page + 1 < root.detail.pages; onClicked: root.page(root.detail.page + 1) }
        }
        ListView {
            id: detailList
            objectName: root.ownerName + "CompletionDetailList"
            Layout.fillWidth: true
            Layout.fillHeight: true
            model: root.detail.rows || []
            clip: true
            spacing: 12
            reuseItems: true
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: AppScrollBar {}
            delegate: Column {
                required property var modelData
                width: ListView.view.width
                spacing: 6
                SelectableText {
                    width: parent.width
                    text: modelData.syntax
                    font: fontPalette.editorFont(13)
                    color: Colors.textPrimary
                    wrapMode: TextEdit.Wrap
                }
                SelectableText {
                    width: parent.width
                    text: (modelData.views || []).join(" / ") + "\n" + (modelData.scopes || []).join("\n")
                        + "\n" + (modelData.annotations || []).join("\n")
                    color: Colors.textSecondary
                    font: Typography.caption
                    wrapMode: TextEdit.Wrap
                }
                Repeater {
                    model: modelData.sources || []
                    AppButton {
                        required property string modelData
                        required property int index
                        width: parent.width
                        text: i18n.catalog["completion.open_source"] + " " + (index + 1)
                        ToolTip.visible: hovered
                        ToolTip.text: modelData
                        onClicked: Qt.openUrlExternally(modelData)
                    }
                }
            }
        }
        Label {
            Layout.fillWidth: true
            visible: !root.busy && !!root.detail.error
            text: i18n.catalog["completion.failed"]
            color: Colors.textSecondary
            wrapMode: Text.Wrap
        }
    }
}
