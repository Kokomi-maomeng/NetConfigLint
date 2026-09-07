pragma Singleton
import QtQuick
QtObject {
    property int mode: preferences.values.themeMode
    property string accent: preferences.values.themeColor
    property bool selectionLocked: false
    readonly property bool dark: mode === 2 || (mode === 0 && Application.styleHints.colorScheme === Qt.Dark)
    readonly property int motion: 280
}
