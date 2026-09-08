pragma Singleton
import QtQuick
QtObject {
    readonly property font display: fontPalette.fonts.display
    readonly property font title: fontPalette.fonts.title
    readonly property font subtitle: fontPalette.fonts.subtitle
    readonly property font body: fontPalette.fonts.body
    readonly property font label: fontPalette.fonts.label
    readonly property font caption: fontPalette.fonts.caption
    readonly property font monospace: fontPalette.fonts.monospace
}
