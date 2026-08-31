import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import theme 1.0
import "../components"

AppCard {
    id: root
    property string severity: "INFO"
    property string ruleId: ""
    property int line: 1
    property string objectName: ""
    property string message: ""
    property string explanation: ""
    property string suggestedFix: ""
    property string confidence: "GENERIC"
    property bool expanded: false
    signal jumpRequested()
    padding: Spacing.md
    implicitHeight: cardContent.implicitHeight + padding * 2

    Rectangle {
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        width: 4
        radius: 2
        color: Colors.severity(root.severity)
    }
    MouseArea {
        anchors.fill: parent
        cursorShape: Qt.PointingHandCursor
        onClicked: root.jumpRequested()
    }
    ColumnLayout {
        id: cardContent
        anchors.fill: parent
        anchors.leftMargin: Spacing.xs
        spacing: Spacing.xs
        RowLayout {
            Layout.fillWidth: true
            StatusBadge { label: root.severity }
            Text { text: root.ruleId; color: Colors.textSecondary; font: Typography.caption }
            Item { Layout.fillWidth: true }
            Text { text: "Line " + root.line; color: Colors.primary; font: Typography.label }
        }
        Text {
            Layout.fillWidth: true
            text: root.message
            color: Colors.textPrimary
            font: Typography.label
            wrapMode: Text.Wrap
        }
        Text {
            Layout.fillWidth: true
            text: root.objectName + "  ·  " + root.confidence
            color: Colors.textSecondary
            font: Typography.caption
            elide: Text.ElideRight
        }
        ColumnLayout {
            Layout.fillWidth: true
            visible: root.expanded
            spacing: Spacing.xs
            Text { text: "Explanation"; color: Colors.textPrimary; font: Typography.label }
            Text {
                Layout.fillWidth: true
                text: root.explanation
                color: Colors.textSecondary
                font: Typography.body
                wrapMode: Text.Wrap
            }
            Text { text: "Suggested fix"; color: Colors.textPrimary; font: Typography.label }
            Text {
                Layout.fillWidth: true
                text: root.suggestedFix
                color: Colors.textSecondary
                font: Typography.body
                wrapMode: Text.Wrap
            }
        }
        RowLayout {
            Layout.fillWidth: true
            AppButton { text: "Go to line"; onClicked: root.jumpRequested() }
            Item { Layout.fillWidth: true }
            AppButton {
                text: root.expanded ? "Less" : "Details"
                onClicked: root.expanded = !root.expanded
            }
        }
    }
    Behavior on implicitHeight { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }
}
