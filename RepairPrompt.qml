import QtQuick
import qs.Commons as Commons
import qs.Ui

Column {
    id: root
    property bool gameRunning: false
    property bool steamRunning: false
    property bool busy: false
    property bool repairing: false
    property string profileName: ""
    signal actionRequested(string action)
    spacing: Commons.Style.space(10)

    Commons.Translations { id: strings; directory: Qt.resolvedUrl("i18n") }
    PlainText {
        width: parent.width
        text: strings.t(root.gameRunning ? "repairCloseGame" : root.steamRunning ? "repairCloseSteam" : "repairReady").arg(root.profileName)
        font.pixelSize: Commons.Style.font.bodySmall
    }
    Button {
        width: parent.width
        text: root.busy ? strings.t(root.repairing ? "repairingProfile" : "working")
            : root.gameRunning ? strings.t("exitGameBeforeRepair")
            : root.steamRunning ? strings.t("exitSteamToRepair")
            : strings.t("repairProfileAction").arg(root.profileName)
        foreground: Commons.Color.accent
        background: Qt.alpha(Commons.Color.accent, 0.16)
        focusable: true
        verticalPadding: Commons.Style.space(9)
        enabled: !root.busy && !root.gameRunning
        opacity: enabled ? 1 : 0.42
        onClicked: {
            if (root.busy || root.gameRunning) return
            root.actionRequested(root.steamRunning ? "exit-steam" : "repair")
        }
    }
    PlainText {
        width: parent.width
        text: strings.t("repairLocalHint")
        font.pixelSize: Commons.Style.font.caption
        color: Qt.alpha(Commons.Color.popups.text, 0.70)
    }
}
