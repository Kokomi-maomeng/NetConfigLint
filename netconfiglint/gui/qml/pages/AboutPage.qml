pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import theme 1.0
import "../components"
Item {
    id: root
    property var sections: [{"title": "about.project", "links": [{"url": "https://github.com/Kokomi-maomeng/NetConfigLint", "en": "Kokomi-maomeng/NetConfigLint", "zh": "Kokomi-maomeng/NetConfigLint"}, {"url": "https://github.com/Kokomi-maomeng", "en": "github.com/Kokomi-maomeng", "zh": "github.com/Kokomi-maomeng"}]}, {"title": "about.components", "links": [{"url": "https://www.python.org/psf/license/", "en": "Python", "zh": "Python"}, {"url": "https://doc.qt.io/qtforpython-6/", "en": "PySide6 / Qt 6", "zh": "PySide6 / Qt 6"}, {"url": "https://nuitka.net/", "en": "Nuitka", "zh": "Nuitka"}]}, {"title": "about.sources", "links": [{"url": "https://support.huawei.com/enterprise/en/doc/EDOC1100459384/10e85233/vxlan-configuration-commands", "en": "Huawei VXLAN command reference", "zh": "Huawei VXLAN 命令参考"}, {"url": "https://support.huawei.com/enterprise/en/doc/EDOC1100290937/379d8aea/configuring-the-ssh-server-function-and-related-parameters", "en": "Huawei SSH security configuration", "zh": "Huawei SSH 安全配置"}, {"url": "https://support.huawei.com/enterprise/en/doc/EDOC1100468733/f596198f/configuring-a-device-to-communicate-with-an-nms-through-snmpv3-usm-user", "en": "Huawei SNMPv3 configuration", "zh": "Huawei SNMPv3 配置"}, {"url": "https://support.huawei.com/enterprise/en/doc/EDOC1100380861/75f06349/fundamentals-of-ntp-access-control", "en": "Huawei NTP access control", "zh": "Huawei NTP 访问控制"}]}]
    ScrollView {
        id: scroll
        anchors.fill: parent
        anchors.margins: 24
        clip: true
        ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
        ScrollBar.vertical: AppScrollBar { }
        ColumnLayout {
            width: scroll.availableWidth
            spacing: 20
            SelectableText { text: i18n.catalog["nav.about"]; font: Typography.display }
            RowLayout {
                Layout.fillWidth: true
                Rectangle {
                    width: 64; height: 64; radius: 22; color: Colors.primary
                    Text { anchors.centerIn: parent; text: "N"; color: Colors.primaryForeground; font: Typography.title }
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
                                    Behavior on color { ColorAnimation { duration: 180 } }
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
