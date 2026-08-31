import QtQuick
import QtQuick.Controls
import theme 1.0

ListView {
    id: root
    property string severityFilter: "ALL"
    signal issueActivated(int row)
    clip: true
    spacing: Spacing.sm
    boundsBehavior: Flickable.StopAtBounds
    ScrollBar.vertical: ScrollBar { }
    delegate: IssueCard {
        required property int index
        required property string severity
        required property string ruleId
        required property int line
        required property string objectName
        required property string message
        required property string explanation
        required property string suggestedFix
        required property string confidence
        width: ListView.view.width - (ListView.view.ScrollBar.vertical.visible ? 14 : 2)
        visible: root.severityFilter === "ALL" || root.severityFilter === severity
        height: visible ? implicitHeight : 0
        onJumpRequested: root.issueActivated(index)
    }
}
