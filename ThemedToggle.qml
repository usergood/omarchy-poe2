import QtQuick
import qs.Commons as Commons
import qs.Ui

// Keep Omarchy's switch and control chrome, but use popup-aware text roles.
// Darkening foreground makes help text too strong on light themes and too dim
// on dark ones; alpha against the popup works in both directions.
BorderSurface {
    id: root
    property string label: ""
    property string description: ""
    property bool checked: false
    property color foreground: Commons.Color.popups.text
    property color accent: Commons.Color.accent
    signal clicked()
    activeFocusOnTab: true
    implicitWidth: Commons.Style.space(240)
    implicitHeight: Math.max(Commons.Style.space(54), content.implicitHeight + Commons.Style.spacing.huge)
    radius: Commons.Style.cornerRadius
    color: Commons.Style.controlFill(activeFocus, mouse.containsMouse, foreground, accent)
    borderSpec: Commons.Border.controlSpec(activeFocus ? "focus" : mouse.containsMouse ? "hover-cursor" : "normal", foreground, accent)
    Keys.onReturnPressed: root.clicked()
    Keys.onEnterPressed: root.clicked()
    Keys.onSpacePressed: root.clicked()
    Behavior on color { ColorAnimation { duration: Commons.Style.duration(100) } }

    Row {
        id: content
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        anchors.leftMargin: root.borderLeft + Commons.Style.spacing.rowPaddingX
        anchors.rightMargin: root.borderRight + Commons.Style.spacing.rowPaddingX
        spacing: Commons.Style.spacing.rowPaddingX
        Column {
            width: Math.max(0, parent.width - track.width - parent.spacing)
            anchors.verticalCenter: parent.verticalCenter
            spacing: Commons.Style.spacing.xs
            PlainText {
                width: parent.width
                text: root.label
                color: root.foreground
                font.pixelSize: Commons.Style.font.subtitle
                font.weight: Font.DemiBold
            }
            PlainText {
                objectName: "description"
                width: parent.width
                visible: root.description !== ""
                text: root.description
                color: Qt.alpha(root.foreground, 0.70)
                font.pixelSize: Commons.Style.font.caption
            }
        }
        ToggleSwitch {
            id: track
            checked: root.checked
            foreground: root.foreground
            accent: root.accent
            interactive: false
            anchors.verticalCenter: parent.verticalCenter
        }
    }
    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: root.clicked()
    }
}
