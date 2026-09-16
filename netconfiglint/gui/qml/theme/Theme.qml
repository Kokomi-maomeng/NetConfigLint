pragma Singleton
import QtQuick
QtObject {
    property int mode: preferences.values.themeMode
    property string accent: preferences.values.themeColor
    property bool selectionLocked: false
    readonly property bool dark: mode === 2 || (mode === 0 && Application.styleHints.colorScheme === Qt.Dark)
    readonly property int motionShort: 100
    readonly property int motionMedium: 250
    readonly property int motionLong: 400
    readonly property int motion: motionMedium
}
