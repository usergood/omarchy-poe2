import QtQuick
import Quickshell.Io
import qs.Commons as Commons
import qs.Ui

Panel {
    id: root
    moduleName: "usergood.poe2"
    manageIpc: false
    property var snapshot: ({})
    property string message: ""
    property bool failed: false
    property int tab: 0
    readonly property string script: decodeURIComponent(Qt.resolvedUrl("backend.py").toString().replace(/^file:\/\//, ""))
    readonly property bool busy: action.running || probe.running
    readonly property bool initialized: snapshot.ok === true
    readonly property var apps: snapshot.running || []
    readonly property var prefs: snapshot.preferences || ({})
    readonly property bool canChange: initialized && snapshot.game_installed && !busy && apps.indexOf("game") < 0 && apps.indexOf("steam") < 0
    implicitWidth: button.implicitWidth
    implicitHeight: button.implicitHeight

    Commons.Translations { id: strings; directory: Qt.resolvedUrl("i18n") }
    function refresh() { if (!probe.running && !action.running) probe.running = true }
    function run(args) {
        if (busy) return
        message = strings.t("working")
        failed = false
        action.command = ["python3", root.script].concat(args)
        action.running = true
    }
    function consume(raw, mutation) {
        try {
            if (raw.length > 32768) throw new Error("Response too large")
            var result = JSON.parse(raw)
            if (!result.ok) {
                message = String(result.error || strings.t("error")).slice(0, 400)
                failed = true
                return
            }
            if (result.busy === true) return
            snapshot = result
            if (mutation) {
                message = String(result.message || strings.t("done")).slice(0, 400)
                failed = false
            }
        } catch (e) { message = strings.t("error"); failed = true }
    }
    function option(name, value) { run(["configure", "--" + name, value]) }
    function checkedVersion(name) {
        var entry = snapshot.updates ? snapshot.updates[name] : null
        if (!entry) return strings.t("notChecked")
        return entry.latest ? strings.t("latest").arg(String(entry.latest).slice(0, 40)) : strings.t("checkFailed")
    }
    onOpenedChanged: if (opened) refresh()
    Component.onCompleted: refresh()
    Timer { interval: 5000; repeat: true; running: root.opened; onTriggered: root.refresh() }
    Process {
        id: probe
        command: ["python3", root.script, "status"]
        stdout: StdioCollector { onStreamFinished: root.consume(text, false) }
    }
    Process {
        id: action
        stdout: StdioCollector { onStreamFinished: root.consume(text, true) }
        onExited: Qt.callLater(root.refresh)
    }
    BarIconButton {
        id: button
        anchors.fill: parent
        bar: root.bar
        text: "󰊴"
        tooltipText: ""
        onPressed: root.toggle()
    }
    KeyboardPanel {
        id: popup
        anchorItem: button
        owner: root
        bar: root.bar
        open: root.opened
        contentWidth: popup.fittedContentWidth(Commons.Style.space(390))
        contentHeight: popup.fittedContentHeight(Math.min(column.implicitHeight, Commons.Style.space(650)))
        focusTarget: scroll
        Flickable {
            id: scroll
            anchors.fill: parent
            contentWidth: width
            contentHeight: column.implicitHeight
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            focus: true
            Keys.onEscapePressed: root.close()
            Column {
                id: column
                width: parent.width
                spacing: Commons.Style.space(10)
                PlainText { width: parent.width; text: strings.t("title"); font.pixelSize: Commons.Style.font.body + 4; font.bold: true }
                PlainText {
                    width: parent.width
                    text: strings.t(root.snapshot.profile || "loading")
                    color: root.snapshot.profile === "needs_repair" ? Commons.Color.urgent : Commons.Color.accent
                }
                Row {
                    width: parent.width
                    spacing: Commons.Style.space(4)
                    Repeater {
                        model: ["play", "tools", "settings"]
                        Button {
                            required property string modelData
                            required property int index
                            width: (column.width - Commons.Style.space(8)) / 3
                            text: strings.t(modelData)
                            selected: root.tab === index
                            focusable: true
                            onClicked: { root.tab = index; scroll.contentY = 0 }
                        }
                    }
                }
                Column {
                    visible: root.tab === 0
                    width: parent.width
                    spacing: Commons.Style.space(8)
                    PlainText { width: parent.width; text: String(root.snapshot.detail || "").slice(0, 300) }
                    Button {
                        width: parent.width
                        text: strings.t("launchGame")
                        enabled: root.initialized && !root.busy && root.snapshot.game_installed && ["original", "fsr4"].indexOf(root.snapshot.profile) >= 0 && root.apps.indexOf("game") < 0
                        focusable: true; bordered: true
                        onClicked: root.run(["launch"])
                    }
                    Button {
                        width: parent.width
                        visible: !root.snapshot.game_installed && root.initialized
                        text: strings.t("installGame")
                        enabled: !root.busy
                        focusable: true; bordered: true
                        onClicked: root.run(["install-game"])
                    }
                    Button {
                        width: parent.width
                        text: strings.t("launchScalpel")
                        enabled: !root.busy && !!root.snapshot.scalpel && root.snapshot.scalpel.available === true && root.apps.indexOf("scalpel") < 0
                        focusable: true; bordered: true
                        onClicked: root.run(["launch-scalpel"])
                    }
                    Button {
                        width: parent.width
                        text: strings.t("trade")
                        enabled: !root.busy
                        focusable: true; bordered: true
                        onClicked: root.run(["trade"])
                    }
                    PlainText { width: parent.width; text: strings.t("profileHint") }
                    Row {
                        width: parent.width
                        spacing: Commons.Style.space(6)
                        Button {
                            width: (column.width - Commons.Style.space(6)) / 2
                            text: strings.t("originalButton")
                            selected: root.snapshot.selected === "original"
                            enabled: root.canChange && root.snapshot.configured
                            focusable: true; bordered: true
                            onClicked: root.run(["original"])
                        }
                        Button {
                            width: (column.width - Commons.Style.space(6)) / 2
                            text: strings.t("fsr4Button")
                            selected: root.snapshot.selected === "fsr4"
                            enabled: root.canChange && root.snapshot.configured
                            focusable: true; bordered: true
                            onClicked: root.run(["fsr4"])
                        }
                    }
                    PlainText { width: parent.width; visible: !root.canChange && root.initialized && root.snapshot.game_installed; text: strings.t("closeFirst") }
                    Button {
                        width: parent.width
                        text: strings.t("exitSteam")
                        enabled: !root.busy && root.apps.indexOf("steam") >= 0 && root.apps.indexOf("game") < 0
                        focusable: true
                        onClicked: root.run(["exit-steam"])
                    }
                }
                Column {
                    visible: root.tab === 1
                    width: parent.width
                    spacing: Commons.Style.space(8)
                    PlainText { width: parent.width; text: strings.t("optiVersion").arg(String(root.snapshot.optiscaler || strings.t("notInstalled"))) }
                    PlainText { width: parent.width; text: root.checkedVersion("optiscaler") }
                    Button {
                        width: parent.width; text: strings.t("installOpti")
                        enabled: root.canChange; focusable: true; bordered: true
                        onClicked: root.run(["install-optiscaler"])
                    }
                    Button {
                        width: parent.width; text: strings.t("repair")
                        enabled: root.canChange && root.snapshot.configured; focusable: true; bordered: true
                        onClicked: root.run(["repair"])
                    }
                    Button {
                        width: parent.width; text: strings.t("rollback")
                        enabled: root.canChange && root.snapshot.can_rollback; focusable: true
                        onClicked: root.run(["rollback"])
                    }
                    PlainText { width: parent.width; text: strings.t("scalpelVersion").arg(root.snapshot.scalpel ? String(root.snapshot.scalpel.version || strings.t("notInstalled")) : strings.t("notInstalled")) }
                    PlainText { width: parent.width; text: root.checkedVersion("scalpel") }
                    Button {
                        width: parent.width; text: strings.t("installScalpel")
                        enabled: !root.busy && root.apps.indexOf("scalpel") < 0; focusable: true; bordered: true
                        onClicked: root.run(["install-scalpel"])
                    }
                    PlainText { width: parent.width; text: strings.t("managedHint") }
                    Button {
                        width: parent.width; text: strings.t("updates")
                        enabled: !root.busy; focusable: true; bordered: true
                        onClicked: root.run(["check-updates"])
                    }
                    PlainText { width: parent.width; text: strings.t("networkHint") }
                    Repeater {
                        model: root.snapshot.warnings || []
                        PlainText { required property string modelData; width: column.width; text: modelData; color: Commons.Color.urgent }
                    }
                }
                Column {
                    visible: root.tab === 2
                    width: parent.width
                    spacing: Commons.Style.space(8)
                    Toggle {
                        width: parent.width; label: strings.t("autoScalpel")
                        checked: root.prefs.auto_scalpel === true
                        enabled: root.canChange
                        onClicked: root.option("auto-scalpel", checked ? "off" : "on")
                    }
                    PlainText { width: parent.width; text: strings.t("qualityHint") }
                    Row {
                        width: parent.width
                        spacing: Commons.Style.space(4)
                        Repeater {
                            model: ["Quality", "Balanced", "Performance"]
                            Button {
                                required property string modelData
                                width: (column.width - Commons.Style.space(8)) / 3
                                text: strings.t(modelData)
                                selected: root.prefs.quality === modelData
                                enabled: root.canChange
                                focusable: true; bordered: true
                                onClicked: root.option("quality", modelData)
                            }
                        }
                    }
                    Toggle {
                        width: parent.width; label: strings.t("watermark")
                        description: strings.t("watermarkHint")
                        checked: root.prefs.watermark === true
                        enabled: root.canChange
                        onClicked: root.option("watermark", checked ? "off" : "on")
                    }
                    Toggle {
                        width: parent.width; label: strings.t("diagnostics")
                        description: strings.t("diagnosticsHint")
                        checked: root.prefs.diagnostics === true
                        enabled: root.canChange
                        onClicked: root.option("diagnostics", checked ? "off" : "on")
                    }
                    PlainText { width: parent.width; text: strings.t("keyHint").arg(String(root.prefs.menu_key || "0xDC")) }
                    PlainText { width: parent.width; text: strings.t("fgHint") }
                    PlainText { width: parent.width; text: strings.t("gpuHint") }
                }
                PlainText {
                    width: parent.width
                    text: root.message
                    visible: text !== ""
                    color: root.failed ? Commons.Color.urgent : Commons.Color.foreground
                }
            }
        }
    }
}
