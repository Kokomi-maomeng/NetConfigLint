import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import theme 1.0
import "../components"

AppDialog {
    id: root
    property string ownerName: ""
    property var queryResult: ({ items: [], argumentDetails: [] })
    property bool busy: false
    property int requestId: -1
    property bool openWhenReady: false
    readonly property var rows: (queryResult.items || []).concat(queryResult.argumentDetails || [])
    signal showDetail(string source, int cursor, var row, string scopeNote)
    objectName: ownerName + "CommandQuery"
    title: i18n.catalog["completion.query"]
    height: Math.min(640, Overlay.overlay ? Overlay.overlay.height - 32 : 640)

    function focusQuery() { queryField.forceActiveFocus() }

    function refresh() {
        if (!visible) return
        busy = true
        requestId = commandCompletion.queryAsync(ownerName, queryField.text, queryField.text.length)
    }
    function showDetailAt(index) {
        if (busy || index < 0 || index >= rows.length) return
        showDetail(queryField.text, queryField.text.length, rows[index], queryResult.scopeNote || "")
    }
    onOpened: queryField.forceActiveFocus()
    onVisibleChanged: {
        if (visible) refresh()
        else {
            queryTimer.stop()
            commandCompletion.cancelQuery(ownerName)
            requestId = -1
            busy = false
            openWhenReady = false
        }
    }
    Connections {
        target: commandCompletion
        function onChanged() { if (root.visible) root.refresh() }
        function onQueryReady(owner, serial, value) {
            if (!root.visible || owner !== root.ownerName || serial !== root.requestId) return
            root.queryResult = value
            root.busy = false
            queryList.currentIndex = root.rows.length ? 0 : -1
            if (root.openWhenReady) {
                root.openWhenReady = false
                root.showDetailAt(queryList.currentIndex)
            }
        }
    }
    Timer { id: queryTimer; interval: 160; onTriggered: root.refresh() }
    footer: DialogButtonBox {
        AppButton {
            objectName: root.ownerName + "CommandQueryClose"
            text: i18n.catalog["common.close"]
            DialogButtonBox.buttonRole: DialogButtonBox.RejectRole
        }
        onRejected: root.close()
    }
    contentItem: ColumnLayout {
        AppTextField {
            id: queryField
            objectName: root.ownerName + "CommandQueryField"
            Layout.fillWidth: true
            implicitHeight: 44
            placeholderText: i18n.catalog["completion.query_placeholder"]
            onTextChanged: {
                commandCompletion.cancelQuery(root.ownerName)
                root.requestId = -1
                root.busy = true
                root.queryResult = ({ items: [], argumentDetails: [] })
                root.openWhenReady = false
                if (root.visible) queryTimer.restart()
            }
            onAccepted: {
                queryTimer.stop()
                if (!root.busy && root.rows.length) root.showDetailAt(Math.max(0, queryList.currentIndex))
                else { root.openWhenReady = true; root.refresh() }
            }
            Keys.onDownPressed: { queryList.forceActiveFocus(); if (queryList.count) queryList.currentIndex = 0 }
        }
        Label {
            Layout.fillWidth: true
            text: i18n.catalog["completion.query_scope_note"]
            color: Colors.textSecondary
            font: Typography.caption
            wrapMode: Text.Wrap
        }
        RowLayout {
            Layout.fillWidth: true
            BusyIndicator { running: root.busy; visible: running; Layout.preferredWidth: 28; Layout.preferredHeight: 28 }
            Label {
                Layout.fillWidth: true
                text: (root.busy ? "…" : root.rows.length) + " · " + i18n.catalog["completion.query_narrow_hint"]
                color: Colors.textSecondary
                font: Typography.caption
                wrapMode: Text.Wrap
            }
        }
        ListView {
            id: queryList
            objectName: root.ownerName + "CommandQueryList"
            Layout.fillWidth: true
            Layout.fillHeight: true
            model: root.rows
            activeFocusOnTab: true
            keyNavigationEnabled: true
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            reuseItems: true
            ScrollBar.vertical: AppScrollBar {}
            Keys.onReturnPressed: root.showDetailAt(currentIndex)
            Keys.onEnterPressed: root.showDetailAt(currentIndex)
            delegate: ItemDelegate {
                required property var modelData
                required property int index
                width: ListView.view.width
                height: 68
                highlighted: ListView.isCurrentItem
                onClicked: root.showDetailAt(index)
                contentItem: Column {
                    spacing: 3
                    Label {
                        width: parent.width
                        text: modelData.text || (modelData.aliases || [modelData.token]).join(" / ")
                        textFormat: Text.PlainText
                        font: fontPalette.editorFont(14)
                        color: Colors.textPrimary
                        elide: Text.ElideRight
                    }
                    Label {
                        width: parent.width
                        text: modelData.token ? (i18n.catalog["completion.parameter_description." + modelData.status] || modelData.description || "")
                            : (modelData.vendors || []).join(" / ") + " · " + modelData.syntax
                        textFormat: Text.PlainText
                        font: Typography.caption
                        color: Colors.textSecondary
                        elide: Text.ElideRight
                    }
                }
            }
        }
        Label {
            Layout.fillWidth: true
            visible: !root.busy && root.rows.length === 0
            text: root.queryResult.error ? i18n.catalog["completion.failed"] : i18n.catalog["completion.no_match"]
            color: Colors.textSecondary
            wrapMode: Text.Wrap
        }
    }
}
