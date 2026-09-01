import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import theme 1.0
import "../components"

Item {
    ScrollView {
        id: aboutScroll
        anchors.fill: parent
        anchors.margins: Spacing.lg
        clip: true
        ScrollBar.horizontal: AppScrollBar { policy: ScrollBar.AlwaysOff }
        ScrollBar.vertical: AppScrollBar { }

        ColumnLayout {
            width: Math.max(560, aboutScroll.availableWidth)
            spacing: Spacing.md

            RowLayout {
                Layout.fillWidth: true
                spacing: Spacing.md
                Rectangle {
                    Layout.preferredWidth: 64
                    Layout.preferredHeight: 64
                    radius: Spacing.radiusLarge
                    color: Colors.primary
                    Text { anchors.centerIn: parent; text: "N"; color: Colors.onPrimary; font: Typography.display }
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: Spacing.xxs
                    SelectableText {
                        text: i18n.catalog["app.title"]
                        color: Colors.textPrimary
                        font: Typography.display
                    }
                    SelectableText {
                        text: i18n.catalog["about.version"]
                        color: Colors.primary
                        font: Typography.label
                    }
                    SelectableText {
                        Layout.fillWidth: true
                        text: i18n.catalog["page.about.tagline"]
                        color: Colors.textSecondary
                        font: Typography.body
                    }
                }
            }

            AppCard {
                Layout.fillWidth: true
                implicitHeight: projectContent.implicitHeight + Spacing.lg * 2
                ColumnLayout {
                    id: projectContent
                    anchors.fill: parent
                    spacing: Spacing.sm
                    SelectableText { text: i18n.catalog["about.project"]; font: Typography.title }
                    SelectableText {
                        Layout.fillWidth: true
                        textFormat: TextEdit.RichText
                        text: i18n.catalog["about.github.links"]
                        color: Colors.textPrimary
                        linkColor: Colors.primary
                        font: Typography.body
                    }
                    SelectableText {
                        Layout.fillWidth: true
                        text: i18n.catalog["about.license"]
                        color: Colors.textSecondary
                        font: Typography.body
                    }
                }
            }

            AppCard {
                Layout.fillWidth: true
                implicitHeight: componentContent.implicitHeight + Spacing.lg * 2
                ColumnLayout {
                    id: componentContent
                    anchors.fill: parent
                    spacing: Spacing.sm
                    SelectableText { text: i18n.catalog["about.components"]; font: Typography.title }
                    SelectableText {
                        Layout.fillWidth: true
                        textFormat: TextEdit.RichText
                        text: i18n.catalog["about.components.links"]
                        color: Colors.textSecondary
                        linkColor: Colors.primary
                        font: Typography.body
                    }
                }
            }

            AppCard {
                Layout.fillWidth: true
                implicitHeight: sourceContent.implicitHeight + Spacing.lg * 2
                ColumnLayout {
                    id: sourceContent
                    anchors.fill: parent
                    spacing: Spacing.sm
                    SelectableText { text: i18n.catalog["about.sources"]; font: Typography.title }
                    SelectableText {
                        Layout.fillWidth: true
                        text: i18n.catalog["about.sources.detail"]
                        color: Colors.textSecondary
                        font: Typography.body
                    }
                    SelectableText {
                        Layout.fillWidth: true
                        textFormat: TextEdit.RichText
                        text: i18n.catalog["about.sources.links"]
                        color: Colors.textSecondary
                        linkColor: Colors.primary
                        font: Typography.body
                    }
                }
            }

            AppCard {
                Layout.fillWidth: true
                implicitHeight: disclaimer.implicitHeight + Spacing.lg * 2
                SelectableText {
                    id: disclaimer
                    anchors.fill: parent
                    text: i18n.catalog["about.disclaimer"]
                    color: Colors.warning
                    font: Typography.body
                }
            }
        }
    }
}
