pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import theme 1.0
import "../components"

ListView {
    id: root
    objectName: "diagnosticIssueList"
    property string severityFilter: "ALL"
    onSeverityFilterChanged: { if (model) model.setSeverityFilter(severityFilter) }
    onModelChanged: { if (model) model.setSeverityFilter(severityFilter) }
    signal issueActivated(int row)
    clip: true
    spacing: 0
    boundsBehavior: Flickable.StopAtBounds
    ScrollBar.vertical: AppScrollBar { }
    delegate: Item {
        id: issueRow
        required property int index
        required property int sourceRow
        required property string severity
        required property string ruleId
        required property int line
        required property string targetObject
        required property string message
        required property string explanation
        required property string suggestedFix
        width: ListView.view.width - (ListView.view.ScrollBar.vertical.visible ? 14 : 2)
        height: issueCard.implicitHeight + Spacing.sm
        IssueCard {
            id: issueCard
            anchors.fill: parent
            anchors.bottomMargin: Spacing.sm
            severityValue: issueRow.severity
            ruleIdentifier: issueRow.ruleId
            sourceLine: issueRow.line
            targetName: issueRow.targetObject
            diagnosticMessage: issueRow.message
            diagnosticExplanation: issueRow.explanation
            diagnosticFix: issueRow.suggestedFix
            onJumpRequested: root.issueActivated(issueRow.sourceRow)
        }
    }
}
