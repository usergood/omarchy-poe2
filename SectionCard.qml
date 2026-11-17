import QtQuick
import qs.Commons as Commons

Rectangle {
    id: root
    default property alias content: body.data
    property bool highlighted: false
    property real padding: Commons.Style.space(14)
    property alias spacing: body.spacing
    implicitHeight: body.implicitHeight + padding * 2
    color: Qt.alpha(highlighted ? Commons.Color.accent : Commons.Color.popups.text, highlighted ? 0.06 : 0.025)
    border.width: 1
    border.color: Qt.alpha(highlighted ? Commons.Color.accent : Commons.Color.popups.text, highlighted ? 0.28 : 0.10)
    radius: Commons.Style.cornerRadius

    data: Column {
        id: body
        x: root.padding
        y: root.padding
        width: Math.max(0, root.width - root.padding * 2)
        spacing: Commons.Style.space(10)
    }
}
