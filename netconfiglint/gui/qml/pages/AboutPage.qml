pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import theme 1.0
import "../components"
Item {
    id: root
    property var sections: [{"title": "about.project", "links": [{"url": "https://github.com/Kokomi-maomeng/NetConfigLint", "en": "Kokomi-maomeng/NetConfigLint", "zh": "Kokomi-maomeng/NetConfigLint"}, {"url": "https://github.com/Kokomi-maomeng", "en": "github.com/Kokomi-maomeng", "zh": "github.com/Kokomi-maomeng"}]}, {"title": "about.components", "links": [{"url": "https://www.python.org/psf/license/", "en": "Python", "zh": "Python"}, {"url": "https://doc.qt.io/qtforpython-6/", "en": "PySide6 / Qt 6", "zh": "PySide6 / Qt 6"}, {"url": "https://nuitka.net/", "en": "Nuitka", "zh": "Nuitka"}]}, {"title": "about.sources", "links": [{"url": "https://support.huawei.com/enterprise/en/doc/EDOC1100459384/10e85233/vxlan-configuration-commands", "en": "Huawei VRP command references", "zh": "华为 VRP 命令参考"}, {"url": "https://www.h3c.com/en/Support/Resource_Center/EN/Home/Public/00-Public/Technical_Documents/Reference_Guides/Command_References/H3C_S6805_S9850_CRs_Release_6715-18388/00/", "en": "H3C Comware 7 command references", "zh": "H3C Comware 7 命令参考"}]}]
    ScrollView {
        id: scroll
        anchors.fill: parent
        anchors.margins: 24
        clip: true
        ScrollBar.horizontal: AppScrollBar {
            objectName: "aboutHorizontalScrollBar"
            policy: ScrollBar.AlwaysOff
        }
        ScrollBar.vertical: AppScrollBar { objectName: "aboutVerticalScrollBar" }
        ColumnLayout {
            width: scroll.availableWidth
            spacing: 20
            SelectableText { text: i18n.catalog["nav.about"]; font: Typography.display }
            RowLayout {
                Layout.fillWidth: true
                Image {
                    Layout.preferredWidth: 72
                    Layout.preferredHeight: 72
                    source: Qt.resolvedUrl("../../../resources/icons/app-master.png")
                    sourceSize.width: 144
                    sourceSize.height: 144
                    fillMode: Image.PreserveAspectFit
                    smooth: true
                    mipmap: true
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    SelectableText { text: "NetConfigLint"; font: Typography.title }
                    SelectableText { text: i18n.catalog["about.version"]; color: Colors.primary; font: Typography.label }
                    SelectableText { Layout.fillWidth: true; text: i18n.catalog["page.about.tagline"]; color: Colors.textSecondary }
                }
            }
            Repeater {
                model: root.sections
                delegate: AppCard {
                    id: section
                    required property var modelData
                    Layout.fillWidth: true
                    implicitHeight: content.implicitHeight + 40
                    padding: 20
                    ColumnLayout {
                        id: content
                        anchors.fill: parent
                        spacing: 12
                        SelectableText { text: i18n.catalog[section.modelData.title]; font: Typography.subtitle }
                        Repeater {
                            model: section.modelData.links
                            delegate: AppButton {
                                required property var modelData
                                Layout.fillWidth: true
                                implicitHeight: 48
                                text: (i18n.language === "zh_CN" ? modelData.zh : modelData.en) + "   ↗"
                                onClicked: Qt.openUrlExternally(modelData.url)
                                background: Rectangle {
                                    radius: 16
                                    color: parent.hovered ? Colors.primaryContainer : Colors.surface
                                    border.color: Colors.outlineVariant
                                    Behavior on color { ColorAnimation { duration: Theme.motionShort } }
                                }
                            }
                        }
                    }
                }
            }
            SelectableText { Layout.fillWidth: true; text: i18n.catalog["about.license"]; color: Colors.textSecondary; font: Typography.caption }
            SelectableText { Layout.fillWidth: true; text: i18n.catalog["about.disclaimer"]; color: Colors.textSecondary; font: Typography.caption }
        }
    }
}
