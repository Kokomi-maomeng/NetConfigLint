import QtQuick
import QtQuick.Layouts
import theme 1.0
import "../components"

AppCard {
    id: root
    objectName: "diagnosticIssueCard"
    property string severityValue: "INFO"
    property string ruleIdentifier: ""
    property int sourceLine: 1
    property string targetName: ""
    property string diagnosticMessage: ""
    property string diagnosticExplanation: ""
    property string diagnosticFix: ""
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
        color: Colors.severity(root.severityValue)
    }
    ColumnLayout {
        id: cardContent
        anchors.fill: parent
        anchors.leftMargin: Spacing.xs
        spacing: Spacing.xs
        RowLayout {
            Layout.fillWidth: true
            StatusBadge { label: root.severityValue }
            SelectableText {
                text: root.ruleIdentifier
                color: Colors.textSecondary
                font: Typography.caption
            }
            Item { Layout.fillWidth: true }
            SelectableText {
                text: i18n.catalog["issue.line"] + " " + root.sourceLine
                color: Colors.primary
                font: Typography.label
            }
        }
        SelectableText {
            Layout.fillWidth: true
            text: root.diagnosticMessage
            color: Colors.textPrimary
            font: Typography.label
            wrapMode: TextEdit.Wrap
        }
        SelectableText {
            Layout.fillWidth: true
            text: root.targetName
            color: Colors.textSecondary
            font: Typography.caption
        }
        ColumnLayout {
            Layout.fillWidth: true
            visible: root.expanded
            spacing: Spacing.xs
            SelectableText {
                text: i18n.catalog["issue.explanation"]
                color: Colors.textPrimary
                font: Typography.label
            }
            SelectableText {
                Layout.fillWidth: true
                text: root.diagnosticExplanation
                color: Colors.textSecondary
                font: Typography.body
                wrapMode: TextEdit.Wrap
            }
            SelectableText {
                text: i18n.catalog["issue.fix"]
                color: Colors.textPrimary
                font: Typography.label
            }
            SelectableText {
                Layout.fillWidth: true
                text: root.diagnosticFix
                color: Colors.textSecondary
                font: Typography.body
                wrapMode: TextEdit.Wrap
            }
        }
        RowLayout {
            Layout.fillWidth: true
            AppButton { text: i18n.catalog["issue.goto"]; onClicked: root.jumpRequested() }
            Item { Layout.fillWidth: true }
            AppButton {
                text: root.expanded ? i18n.catalog["issue.less"] : i18n.catalog["issue.details"]
                onClicked: root.expanded = !root.expanded
            }
        }
    }
    Behavior on implicitHeight { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }
}
