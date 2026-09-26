pragma Singleton
import QtQuick
import theme 1.0
QtObject {
    readonly property var palettes: ({
        violet: ["#7357a3", "#ecdcff", "#cdb5ff", "#41266e", "#5a3f89"],
        blue: ["#38618c", "#d1e4ff", "#a3c9f5", "#003258", "#174a72"],
        green: ["#42664f", "#c4eccf", "#a9d4b4", "#143724", "#2b4e39"],
        rose: ["#88525f", "#ffd9e1", "#f4b7c5", "#50202d", "#6d3946"],
        amber: ["#7b5f21", "#ffdf91", "#ebc466", "#402d00", "#5d4508"],
        teal: ["#006a6a", "#6ff7f6", "#4ddad9", "#003737", "#005050"],
        cyan: ["#00677c", "#aeecff", "#58d6f5", "#003641", "#004e5f"],
        indigo: ["#4b5f9e", "#dce1ff", "#b7c4ff", "#182c67", "#334783"],
        coral: ["#9b442a", "#ffdbd0", "#ffb59f", "#5d1907", "#7c2d16"],
        slate: ["#52606f", "#d5e4f6", "#b9c8da", "#243140", "#3a4857"]
    })
    readonly property var palette: palettes[Theme.accent] || palettes.violet
    readonly property color primary: Theme.dark ? palette[2] : palette[0]
    readonly property color primaryForeground: Theme.dark ? palette[3] : "#ffffff"
    readonly property color primaryContainer: Theme.dark ? palette[4] : palette[1]
    readonly property color secondary: Theme.dark ? palette[2] : palette[0]
    readonly property color surface: Theme.dark ? Qt.tint("#1b1c1f", Qt.alpha(primary, 0.07)) : Qt.tint("#ffffff", Qt.alpha(primary, 0.045))
    readonly property color surfaceVariant: Theme.dark ? Qt.tint("#303136", Qt.alpha(primary, 0.19)) : Qt.tint("#e9e9ed", Qt.alpha(primary, 0.17))
    readonly property color surfaceContainer: Theme.dark ? Qt.tint("#232428", Qt.alpha(primary, 0.15)) : Qt.tint("#f3f3f6", Qt.alpha(primary, 0.13))
    readonly property color surfaceContainerLow: Theme.dark ? Qt.tint("#202126", Qt.alpha(primary, 0.12)) : Qt.tint("#f7f7f9", Qt.alpha(primary, 0.10))
    readonly property color surfaceContainerHigh: Theme.dark ? Qt.tint("#303137", Qt.alpha(primary, 0.19)) : Qt.tint("#eaeaf0", Qt.alpha(primary, 0.18))
    readonly property color surfaceContainerHighest: Theme.dark ? Qt.tint("#393a40", Qt.alpha(primary, 0.22)) : Qt.tint("#e3e3ea", Qt.alpha(primary, 0.20))
    readonly property color background: Theme.dark ? "#18191c" : "#f5f5f7"
    readonly property color outline: Theme.dark ? "#958e99" : "#7b747f"
    readonly property color outlineVariant: Theme.dark ? "#47484e" : "#d8d8df"
    readonly property color error: Theme.dark ? "#ffb4ab" : "#ba1a1a"
    readonly property color warning: Theme.dark ? "#e9c349" : "#7c5d00"
    readonly property color success: Theme.dark ? "#98d5ac" : "#2f6b48"
    readonly property color info: Theme.dark ? "#a9c7ff" : "#3d5f91"
    readonly property color unknown: Theme.dark ? "#d3b8f6" : "#71558e"
    readonly property color textPrimary: Theme.dark ? "#f1f1f3" : "#1c1d21"
    readonly property color textSecondary: Theme.dark ? "#b6b7bd" : "#606169"
    readonly property color editorBackground: surface
    readonly property color scrim: "#80000000"
    function severity(value) {
        if (value === "ERROR") return error
        if (value === "WARNING") return warning
        if (value === "INFO") return info
        if (value === "UNKNOWN") return unknown
        return success
    }
}
