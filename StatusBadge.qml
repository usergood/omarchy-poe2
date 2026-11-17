import QtQuick
import qs.Commons as Commons

Rectangle {
    id: root
    property string text: ""
    property bool active: false
    property bool warning: false
    readonly property color tint: warning ? Commons.Color.urgent : active ? Commons.Color.accent : Qt.alpha(Commons.Color.popups.text, 0.70)
    implicitWidth: content.implicitWidth + Commons.Style.space(16)
    implicitHeight: content.implicitHeight + Commons.Style.space(10)
    color: Qt.alpha(tint, 0.10)
    radius: Math.min(height / 2, Commons.Style.cornerRadius)

    Row {
        id: content
        anchors.centerIn: parent
        spacing: Commons.Style.space(6)
        Rectangle {
            anchors.verticalCenter: parent.verticalCenter
            width: Commons.Style.space(5)
            height: width
            radius: width / 2
            color: root.tint
        }
        PlainText {
            text: root.text
            color: root.tint
            font.pixelSize: Commons.Style.font.caption
            font.weight: Font.Medium
            wrapMode: Text.NoWrap
        }
    }
}
