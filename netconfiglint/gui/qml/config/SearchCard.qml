import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import theme 1.0
import "../components"

Item {
    id: root
    objectName: "editorSearchOverlay"
    visible: false
    property var targetCard: null
    readonly property var targetEditor: targetCard ? targetCard.editor : null
    property real panelOpacity: 1
    property point dragOrigin: Qt.point(0, 0)
    property rect startGeometry: Qt.rect(0, 0, 0, 0)
    readonly property var searchResult: collectMatches()
    onWidthChanged: if (visible) surface.x = Math.max(0, Math.min(surface.x, width - surface.width))
    onHeightChanged: if (visible) surface.y = Math.max(0, Math.min(surface.y, height - surface.height))

    function openFor(card) {
        if (targetCard && targetCard !== card) targetCard.searchActive = false
        targetCard = card
        card.searchActive = true
        if (!visible) {
            surface.width = Math.min(560, Math.max(360, width - 24))
            surface.height = 142
            surface.x = Math.max(0, Math.round((width - surface.width) / 2))
            surface.y = 24
        }
        visible = true
        searchField.forceActiveFocus()
        searchField.selectAll()
    }
    function closeSearch() {
        if (targetCard) targetCard.searchActive = false
        visible = false
        if (targetEditor) targetEditor.forceActiveFocus()
    }
    function collectMatches() {
        var result = { positions: [], error: "" }
        if (!targetEditor || !searchField.text.length) return result
        var source = targetEditor.text
        var query = searchField.text
        var pattern = regexCheck.checked ? query : query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
        var expression
        try { expression = new RegExp(pattern, "g" + (caseCheck.checked ? "" : "i")) }
        catch (error) { result.error = String(error); return result }
        var match
        while ((match = expression.exec(source)) !== null) {
            result.positions.push({ start: match.index, end: match.index + match[0].length })
            if (match[0].length === 0) expression.lastIndex++
        }
        return result
    }
    function find(direction) {
        if (!targetEditor || searchResult.error || !searchResult.positions.length) return
        var positions = searchResult.positions
        var start = direction > 0 ? targetEditor.selectionEnd : targetEditor.selectionStart
        var index = direction > 0 ? 0 : positions.length - 1
        if (direction > 0) {
            while (index < positions.length && positions[index].start < start) index++
            if (index === positions.length) index = 0
        } else {
            while (index >= 0 && positions[index].end > start) index--
            if (index < 0) index = positions.length - 1
        }
        var hit = positions[index]
        targetEditor.select(hit.start, hit.end)
        searchField.forceActiveFocus()
    }
    function beginResize(point) {
        dragOrigin = point
        startGeometry = Qt.rect(surface.x, surface.y, surface.width, surface.height)
    }
    function resize(edge, point) {
        var dx = point.x - dragOrigin.x
        var dy = point.y - dragOrigin.y
        var left = startGeometry.x
        var top = startGeometry.y
        var right = left + startGeometry.width
        var bottom = top + startGeometry.height
        if (edge.indexOf("l") >= 0) left = Math.max(0, Math.min(right - 360, left + dx))
        if (edge.indexOf("r") >= 0) right = Math.min(root.width, Math.max(left + 360, right + dx))
        if (edge.indexOf("t") >= 0) top = Math.max(0, Math.min(bottom - 112, top + dy))
        if (edge.indexOf("b") >= 0) bottom = Math.min(root.height, Math.max(top + 112, bottom + dy))
        surface.x = left; surface.y = top
        surface.width = right - left; surface.height = bottom - top
    }

    Rectangle {
        id: surface
        objectName: "editorSearchCard"
        width: 560
        height: 142
        radius: 18
        color: Colors.surfaceContainerHigh
        border.color: Colors.outlineVariant
        border.width: 1
        opacity: root.panelOpacity

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 12
            spacing: 7
            Item {
                Layout.fillWidth: true
                Layout.preferredHeight: 42
                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.OpenHandCursor
                    property point origin: Qt.point(0, 0)
                    property point start: Qt.point(0, 0)
                    onPressed: mouse => {
                        origin = mapToItem(root, mouse.x, mouse.y)
                        start = Qt.point(surface.x, surface.y)
                    }
                    onPositionChanged: mouse => {
                        if (!pressed) return
                        var point = mapToItem(root, mouse.x, mouse.y)
                        surface.x = Math.max(0, Math.min(root.width - surface.width, start.x + point.x - origin.x))
                        surface.y = Math.max(0, Math.min(root.height - surface.height, start.y + point.y - origin.y))
                    }
                }
                RowLayout {
                    anchors.fill: parent
                    spacing: 5
                    Grid {
                        Layout.preferredWidth: 18
                        columns: 2
                        spacing: 3
                        Repeater {
                            model: 6
                            Rectangle { width: 3; height: 3; radius: 2; color: Colors.textSecondary }
                        }
                    }
                    AppTextField {
                        id: searchField
                        objectName: "editorSearchField"
                        Layout.fillWidth: true
                        implicitHeight: 40
                        placeholderText: i18n.catalog["editor.search"]
                        onAccepted: root.find(1)
                        Keys.onEscapePressed: root.closeSearch()
                    }
                    AppButton { objectName: "editorFindPrevious"; text: "↑"; Layout.preferredWidth: 42; onClicked: root.find(-1) }
                    AppButton { objectName: "editorFindNext"; text: "↓"; Layout.preferredWidth: 42; onClicked: root.find(1) }
                    AppButton { objectName: "editorSearchOpacityButton"; text: "◐"; Layout.preferredWidth: 42; Accessible.name: i18n.catalog["editor.opacity"]; onClicked: opacityPopup.open() }
                    AppButton { objectName: "editorSearchClose"; text: "×"; Layout.preferredWidth: 42; Accessible.name: i18n.catalog["common.close"]; onClicked: root.closeSearch() }
                }
            }
            RowLayout {
                Layout.fillWidth: true
                CheckBox { id: caseCheck; objectName: "editorMatchCase"; text: i18n.catalog["editor.match_case"] }
                CheckBox { id: regexCheck; objectName: "editorRegex"; text: i18n.catalog["editor.regex"] }
                Item { Layout.fillWidth: true }
                Text {
                    objectName: "editorSearchStatus"
                    text: root.searchResult.error ? i18n.catalog["editor.invalid_regex"]
                        : (searchField.text.length ? String(root.searchResult.positions.length) + " " + i18n.catalog["editor.matches"] : "")
                    color: root.searchResult.error ? Colors.error : Colors.textSecondary
                    font: Typography.caption
                }
            }
            Item { Layout.fillHeight: true }
        }
        Popup {
            id: opacityPopup
            objectName: "editorOpacityPopup"
            x: Math.max(0, surface.width - width - 12)
            y: 48
            width: 210
            height: 76
            padding: 12
            background: Rectangle { radius: 12; color: Colors.surfaceContainerHighest; border.color: Colors.outlineVariant }
            contentItem: ColumnLayout {
                Text { text: i18n.catalog["editor.opacity"]; color: Colors.textPrimary; font: Typography.label }
                Slider { objectName: "editorOpacitySlider"; Layout.fillWidth: true; from: 0.55; to: 1; value: root.panelOpacity; onMoved: root.panelOpacity = value }
            }
        }
        Repeater {
            model: ["l", "r", "t", "b", "lt", "rt", "lb", "rb"]
            MouseArea {
                required property string modelData
                readonly property bool horizontal: modelData.indexOf("l") >= 0 || modelData.indexOf("r") >= 0
                readonly property bool vertical: modelData.indexOf("t") >= 0 || modelData.indexOf("b") >= 0
                x: modelData.indexOf("l") >= 0 ? 0 : modelData.indexOf("r") >= 0 ? surface.width - width : 10
                y: modelData.indexOf("t") >= 0 ? 0 : modelData.indexOf("b") >= 0 ? surface.height - height : 10
                width: horizontal ? 8 : surface.width - 20
                height: vertical ? 8 : surface.height - 20
                cursorShape: horizontal && vertical ? (modelData === "lt" || modelData === "rb" ? Qt.SizeFDiagCursor : Qt.SizeBDiagCursor)
                    : horizontal ? Qt.SizeHorCursor : Qt.SizeVerCursor
                onPressed: mouse => root.beginResize(mapToItem(root, mouse.x, mouse.y))
                onPositionChanged: mouse => { if (pressed) root.resize(modelData, mapToItem(root, mouse.x, mouse.y)) }
            }
        }
    }
}
