import QtQuick
import QtQuick.Controls
import theme 1.0

TextField {
    id: control
    ContextMenu.menu: TextEditMenu { editor: control }
    color: Colors.textPrimary
    placeholderTextColor: Colors.textSecondary
    selectionColor: Colors.primaryContainer
    selectedTextColor: Colors.textPrimary
    font: Typography.body
    leftPadding: Spacing.sm
    rightPadding: Spacing.sm
    background: Rectangle {
        color: Colors.surfaceContainer
        border.color: control.activeFocus ? Colors.primary : Colors.outlineVariant
        border.width: control.activeFocus ? 2 : 1
        radius: Spacing.radiusMedium
        Behavior on border.color { ColorAnimation { duration: 120 } }
    }
}
