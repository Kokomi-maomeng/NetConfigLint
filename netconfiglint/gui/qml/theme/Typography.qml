pragma Singleton
import QtQuick

QtObject {
    readonly property var sansFamilies: ["Segoe UI Variable", "Inter", "Noto Sans", "Arial"]
    readonly property var monoFamilies: ["Cascadia Mono", "SFMono-Regular", "Noto Sans Mono", "monospace"]
    readonly property font display: Qt.font({ families: sansFamilies, pixelSize: 30, weight: Font.DemiBold })
    readonly property font title: Qt.font({ families: sansFamilies, pixelSize: 22, weight: Font.DemiBold })
    readonly property font subtitle: Qt.font({ families: sansFamilies, pixelSize: 17, weight: Font.DemiBold })
    readonly property font body: Qt.font({ families: sansFamilies, pixelSize: 15 })
    readonly property font label: Qt.font({ families: sansFamilies, pixelSize: 15, weight: Font.Medium })
    readonly property font caption: Qt.font({ families: sansFamilies, pixelSize: 13 })
    readonly property font monospace: Qt.font({ families: monoFamilies, pixelSize: 15 })
}
