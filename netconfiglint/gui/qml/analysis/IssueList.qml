import QtQuick
import QtQuick.Controls
import theme 1.0
import "../components"

ListView {
    id: root
    property string severityFilter: "ALL"
    signal issueActivated(int row)
    clip: true
    spacing: Spacing.sm
    boundsBehavior: Flickable.StopAtBounds
    ScrollBar.vertical: AppScrollBar { }
    delegate: Item {
        id: issueRow
        required property int index
        required property string severity
        required property string ruleId
        required property int line
        required property string targetObject
        required property string message
        required property string explanation
        required property string suggestedFix
        width: ListView.view.width - (ListView.view.ScrollBar.vertical.visible ? 14 : 2)
        visible: root.severityFilter === "ALL" || root.severityFilter === severity
        height: visible ? issueCard.implicitHeight : 0
        IssueCard {
            id: issueCard
            anchors.fill: parent
            severityValue: issueRow.severity
            ruleIdentifier: issueRow.ruleId
            sourceLine: issueRow.line
            targetName: issueRow.targetObject
            diagnosticMessage: issueRow.message
            diagnosticExplanation: issueRow.explanation
            diagnosticFix: issueRow.suggestedFix
            onJumpRequested: root.issueActivated(issueRow.index)
        }
    }
}
