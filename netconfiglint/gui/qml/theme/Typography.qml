pragma Singleton
import QtQuick

QtObject {
    readonly property var sansFamilies: ["Segoe UI Variable", "Inter", "Noto Sans", "Arial"]
    readonly property var monoFamilies: ["Cascadia Mono", "SFMono-Regular", "Noto Sans Mono", "monospace"]
    readonly property font display: Qt.font({ families: sansFamilies, pixelSize: 28, weight: Font.DemiBold })
    readonly property font title: Qt.font({ families: sansFamilies, pixelSize: 20, weight: Font.DemiBold })
    readonly property font subtitle: Qt.font({ families: sansFamilies, pixelSize: 15, weight: Font.DemiBold })
    readonly property font body: Qt.font({ families: sansFamilies, pixelSize: 14 })
    readonly property font label: Qt.font({ families: sansFamilies, pixelSize: 13, weight: Font.Medium })
    readonly property font caption: Qt.font({ families: sansFamilies, pixelSize: 12 })
    readonly property font monospace: Qt.font({ families: monoFamilies, pixelSize: 14 })
}

