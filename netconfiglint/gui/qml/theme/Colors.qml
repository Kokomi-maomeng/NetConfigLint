pragma Singleton
import QtQuick
import theme 1.0

QtObject {
    readonly property color primary: Theme.dark ? "#AFC6FF" : "#315F9B"
    readonly property color onPrimary: Theme.dark ? "#002E67" : "#FFFFFF"
    readonly property color primaryContainer: Theme.dark ? "#15477F" : "#D7E3FF"
    readonly property color secondary: Theme.dark ? "#B9C7DB" : "#526071"
    readonly property color surface: Theme.dark ? "#111318" : "#F9F9FC"
    readonly property color surfaceVariant: Theme.dark ? "#42474F" : "#E1E2E8"
    readonly property color surfaceContainer: Theme.dark ? "#1D2026" : "#EEEFF4"
    readonly property color background: Theme.dark ? "#0F1115" : "#F5F6FA"
    readonly property color outline: Theme.dark ? "#8C9199" : "#74777F"
    readonly property color outlineVariant: Theme.dark ? "#42474F" : "#C4C6CF"
    readonly property color error: Theme.dark ? "#FFB4AB" : "#BA1A1A"
    readonly property color warning: Theme.dark ? "#F3C76B" : "#8A5B00"
    readonly property color success: Theme.dark ? "#83D5A5" : "#1B6D43"
    readonly property color info: Theme.dark ? "#9BCBFF" : "#176B9C"
    readonly property color unknown: Theme.dark ? "#D3B8F6" : "#71558E"
    readonly property color textPrimary: Theme.dark ? "#E3E2E6" : "#1A1C20"
    readonly property color textSecondary: Theme.dark ? "#C3C6CF" : "#44474E"
    readonly property color editorBackground: Theme.dark ? "#15171C" : "#FFFFFF"

    function severity(value) {
        if (value === "ERROR") return error
        if (value === "WARNING") return warning
        if (value === "INFO") return info
        if (value === "UNKNOWN") return unknown
        return success
    }
}
