pragma Singleton
import QtQuick

QtObject {
    // 0 = System, 1 = Light, 2 = Dark
    property int mode: 0
    readonly property bool dark: mode === 2
                                 || (mode === 0 && Application.styleHints.colorScheme === Qt.Dark)
}

