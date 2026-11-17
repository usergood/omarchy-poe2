import QtQuick
import QtQuick.Controls as Controls
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
    property string activeAction: ""
    property int tab: 0
    readonly property string script: decodeURIComponent(Qt.resolvedUrl("backend.py").toString().replace(/^file:\/\//, ""))
    readonly property bool busy: action.running
    readonly property bool initialized: snapshot.ok === true
    readonly property var apps: snapshot.running || []
    readonly property var prefs: snapshot.preferences || ({})
    readonly property bool gameRunning: apps.indexOf("game") >= 0
    readonly property bool scalpelRunning: apps.indexOf("scalpel") >= 0
    readonly property bool steamRunning: apps.indexOf("steam") >= 0
    readonly property bool profileNeedsAttention: ["needs_repair", "unmanaged"].indexOf(snapshot.profile) >= 0
    readonly property bool repairRequired: snapshot.profile === "needs_repair" && snapshot.configured === true
    readonly property bool scalpelAvailable: !!snapshot.scalpel && snapshot.scalpel.available === true
    readonly property bool scalpelNeedsSetup: scalpelAvailable && snapshot.scalpel.setup !== "ready"
    readonly property bool canChange: initialized && snapshot.game_installed && !busy && !gameRunning && !steamRunning
    implicitWidth: button.implicitWidth
    implicitHeight: button.implicitHeight

    Commons.Translations { id: strings; directory: Qt.resolvedUrl("i18n") }
    function refresh() { if (!probe.running && !action.running) probe.running = true }
    function run(args) {
        if (busy) return
        activeAction = args[0]
        feedbackTimer.stop()
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
                feedbackTimer.stop()
                message = String(result.error || strings.t("error")).slice(0, 400)
                failed = true
                return
            }
            if (result.busy === true) return
            snapshot = result
            if (mutation) {
                message = String(result.message || strings.t("done")).slice(0, 400)
                failed = false
                feedbackTimer.restart()
            }
        } catch (e) { feedbackTimer.stop(); message = strings.t("error"); failed = true }
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
    Timer { id: feedbackTimer; interval: 6000; onTriggered: root.message = "" }
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
        text: ""
        iconComponent: Component {
            Image {
                source: Qt.resolvedUrl("assets/poe2-icon.png")
                width: button.opticalSize
                height: width
                sourceSize: Qt.size(Math.ceil(button.opticalSize * 2), Math.ceil(button.opticalSize * 2))
                fillMode: Image.PreserveAspectFit
                smooth: true
                mipmap: true
            }
        }
        tooltipText: ""
        onPressed: root.toggle()
    }
    // Native controls keep theme focus, hover and motion behavior.
    component ActionButton: ThemedButton {
        focusable: true
        verticalPadding: Commons.Style.space(9)
        opacity: enabled ? 1 : 0.42
        Behavior on opacity { NumberAnimation { duration: Commons.Style.duration(120) } }
    }
    component Caption: PlainText {
        font.pixelSize: Commons.Style.font.bodySmall
        color: Qt.alpha(Commons.Color.popups.text, 0.70)
    }
    component SectionLabel: PlainText {
        font.pixelSize: Commons.Style.font.caption
        font.weight: Font.DemiBold
        font.letterSpacing: 1.2
        color: Qt.alpha(Commons.Color.popups.text, 0.62)
    }
    component CardTitle: PlainText {
        font.pixelSize: Commons.Style.font.title
        font.weight: Font.DemiBold
    }
    component Rule: Rectangle {
        implicitHeight: 1
        color: Qt.alpha(Commons.Color.popups.text, 0.10)
    }

    KeyboardPanel {
        id: popup
        anchorItem: button
        owner: root
        bar: root.bar
        open: root.opened
        padding: Commons.Style.space(18)
        contentWidth: popup.fittedContentWidth(Commons.Style.space(470))
        // Only the page scrolls when the available screen height is exhausted.
        contentHeight: popup.fittedContentHeight(Math.ceil(header.implicitHeight + layout.spacing + column.implicitHeight
            + (feedback.visible ? feedback.implicitHeight + layout.spacing : 0)))
        focusTarget: scroll
        Column {
            id: layout
            anchors.fill: parent
            spacing: Commons.Style.space(16)
            Keys.onEscapePressed: root.close()
            Column {
                id: header
                width: parent.width
                spacing: Commons.Style.space(16)
                Row {
                    width: parent.width
                    spacing: Commons.Style.space(14)
                    Image {
                        id: emblem
                        width: Commons.Style.space(54)
                        height: width
                        anchors.verticalCenter: parent.verticalCenter
                        source: Qt.resolvedUrl("assets/poe2-icon.png")
                        sourceSize: Qt.size(160, 160)
                        fillMode: Image.PreserveAspectFit
                        mipmap: true
                        smooth: true
                    }
                    Column {
                        width: parent.width - emblem.width - closeButton.width - parent.spacing * 2
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: Commons.Style.space(3)
                        SectionLabel { text: strings.t("headerEyebrow") }
                        PlainText {
                            width: parent.width
                            text: strings.t("title")
                            font.pixelSize: Commons.Style.font.heading + Commons.Style.space(2)
                            font.weight: Font.DemiBold
                        }
                        Caption { width: parent.width; text: strings.t("headerSubtitle") }
                    }
                    ActionButton {
                        id: closeButton
                        width: Commons.Style.space(26)
                        anchors.verticalCenter: parent.verticalCenter
                        text: "×"
                        fontSize: Commons.Style.font.heading
                        horizontalPadding: 0
                        verticalPadding: Commons.Style.space(3)
                        foreground: Qt.alpha(Commons.Color.popups.text, 0.70)
                        Accessible.name: strings.t("closePanel")
                        onClicked: root.close()
                    }
                }

                Rectangle {
                    width: parent.width
                    implicitHeight: tabs.implicitHeight + Commons.Style.space(6)
                    color: Qt.alpha(Commons.Color.popups.text, 0.035)
                    radius: Commons.Style.cornerRadius
                    Row {
                        id: tabs
                        x: Commons.Style.space(3)
                        y: x
                        width: parent.width - x * 2
                        spacing: Commons.Style.space(3)
                        Repeater {
                            model: ["play", "tools", "settings"]
                            ActionButton {
                                required property string modelData
                                required property int index
                                width: (tabs.width - tabs.spacing * 2) / 3
                                text: strings.t(modelData)
                                selected: root.tab === index
                                onClicked: { root.tab = index; scroll.contentY = 0 }
                            }
                        }
                    }
                }

                Row {
                    width: parent.width
                    spacing: Commons.Style.space(8)
                    SectionLabel {
                        width: parent.width - sessionBadge.width - parent.spacing
                        anchors.verticalCenter: parent.verticalCenter
                        text: strings.t(["sessionHeading", "toolsHeading", "settingsHeading"][root.tab])
                    }
                    StatusBadge {
                        id: sessionBadge
                        text: strings.t(!root.initialized ? "checkingStatus" : root.steamRunning ? "steamRunning" : "steamClosed")
                        active: root.steamRunning
                    }
                }
            }
            Flickable {
                id: scroll
                width: parent.width
                height: Math.max(0, layout.height - header.height - layout.spacing
                    - (feedback.visible ? feedback.height + layout.spacing : 0))
                contentWidth: width
                contentHeight: Math.ceil(column.implicitHeight)
                readonly property bool overflows: contentHeight > height + 1
                clip: true
                boundsBehavior: Flickable.StopAtBounds
                flickableDirection: Flickable.VerticalFlick
                focus: true
                Keys.onEscapePressed: root.close()
                Controls.ScrollBar.vertical: Controls.ScrollBar {
                    policy: scroll.overflows ? Controls.ScrollBar.AsNeeded : Controls.ScrollBar.AlwaysOff
                    contentItem: Rectangle {
                        implicitWidth: Commons.Style.space(3)
                        implicitHeight: Commons.Style.space(24)
                        radius: width / 2
                        color: Qt.alpha(Commons.Color.popups.text, 0.35)
                    }
                    background: Item {}
                }
                Column {
                    id: column
                    width: scroll.width - (scroll.overflows ? Commons.Style.space(12) : 0)
                    spacing: Commons.Style.space(16)
                    Column {
                        visible: root.tab === 0
                        width: parent.width
                        spacing: Commons.Style.space(12)
                        SectionCard {
                            width: parent.width
                            Row {
                                width: parent.width
                                spacing: Commons.Style.space(8)
                                CardTitle {
                                    width: parent.width - gameBadge.width - parent.spacing
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: strings.t("gameName")
                                }
                                StatusBadge {
                                    id: gameBadge
                                    text: strings.t(!root.initialized ? "checkingStatus" : root.gameRunning ? "inGame" : !root.snapshot.game_installed ? "notInstalled" : root.profileNeedsAttention ? "attentionNeeded" : "readyToPlay")
                                    active: root.gameRunning
                                    warning: root.profileNeedsAttention
                                }
                            }
                            Caption {
                                width: parent.width
                                text: strings.t("gameSummary").arg(strings.t(root.snapshot.profile || "loading"))
                            }
                            PlainText {
                                width: parent.width
                                visible: root.profileNeedsAttention
                                text: String(root.snapshot.detail || "").slice(0, 300)
                                font.pixelSize: Commons.Style.font.bodySmall
                                color: Commons.Color.urgent
                            }
                            RepairPrompt {
                                width: parent.width
                                visible: root.repairRequired
                                gameRunning: root.gameRunning
                                steamRunning: root.steamRunning
                                busy: root.busy
                                repairing: root.activeAction === "repair"
                                profileName: strings.t(root.snapshot.selected === "fsr4" ? "fsr4Button" : "originalButton")
                                onActionRequested: function(action) { root.run([action]) }
                            }
                            ActionButton {
                                width: parent.width
                                visible: !root.repairRequired
                                text: strings.t(root.gameRunning ? "gameRunningButton" : !root.snapshot.game_installed ? "installGame" : root.prefs.auto_scalpel === true && root.scalpelNeedsSetup ? "setupScalpelFirst" : "launchGame")
                                iconText: root.gameRunning ? "󰄬" : "󰐊"
                                background: Qt.alpha(Commons.Color.accent, 0.16)
                                foreground: Commons.Color.accent
                                enabled: root.initialized && !root.busy && !root.gameRunning && (!root.snapshot.game_installed || ["original", "fsr4"].indexOf(root.snapshot.profile) >= 0)
                                onClicked: root.run([root.snapshot.game_installed ? "launch" : "install-game"])
                            }
                        }
                        SectionCard {
                            width: parent.width
                            Row {
                                width: parent.width
                                spacing: Commons.Style.space(8)
                                CardTitle {
                                    width: parent.width - scalpelBadge.width - parent.spacing
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: "Scalpel"
                                }
                                StatusBadge {
                                    id: scalpelBadge
                                    text: strings.t(!root.initialized ? "checkingStatus" : root.scalpelRunning ? "running" : !root.scalpelAvailable ? "notInstalled" : root.scalpelNeedsSetup ? "setupNeeded" : "notRunning")
                                    active: root.scalpelRunning
                                    warning: root.scalpelNeedsSetup && !root.scalpelRunning
                                }
                            }
                            Caption {
                                width: parent.width
                                text: strings.t(root.scalpelAvailable && !root.scalpelNeedsSetup ? "scalpelReadySummary" : "scalpelSummary")
                            }
                            PlainText {
                                width: parent.width
                                visible: root.scalpelNeedsSetup
                                text: strings.t("scalpelSetup_" + (root.snapshot.scalpel ? root.snapshot.scalpel.setup : "unknown"))
                                font.pixelSize: Commons.Style.font.bodySmall
                                color: Commons.Color.urgent
                            }
                            Caption {
                                width: parent.width
                                visible: root.initialized && !root.scalpelAvailable
                                text: strings.t("scalpelMissingHint")
                            }
                            ActionButton {
                                width: parent.width
                                text: strings.t(!root.scalpelAvailable ? "getScalpel" : root.scalpelNeedsSetup ? "setupScalpel" : root.scalpelRunning ? "showScalpel" : "launchScalpel")
                                bordered: true
                                enabled: root.initialized && !root.busy
                                onClicked: { if (root.scalpelAvailable) root.run(["launch-scalpel"]); else root.tab = 1 }
                            }
                        }
                        Row {
                            width: parent.width
                            spacing: Commons.Style.space(12)
                            Column {
                                width: parent.width - tradeButton.width - parent.spacing
                                anchors.verticalCenter: parent.verticalCenter
                                spacing: Commons.Style.space(3)
                                PlainText { text: strings.t("tradeHeading"); font.weight: Font.Medium }
                                Caption { width: parent.width; text: strings.t("tradeSummary") }
                            }
                            ActionButton {
                                id: tradeButton
                                anchors.verticalCenter: parent.verticalCenter
                                text: strings.t("openTrade")
                                iconText: "↗"
                                bordered: true
                                enabled: !root.busy
                                onClicked: root.run(["trade"])
                            }
                        }
                        Rule { width: parent.width }
                        Column {
                            width: parent.width
                            spacing: Commons.Style.space(10)
                            Row {
                                width: parent.width
                                spacing: Commons.Style.space(8)
                                SectionLabel {
                                    width: parent.width - profileLabel.implicitWidth - parent.spacing
                                    text: strings.t("renderingHeading")
                                }
                                Caption {
                                    id: profileLabel
                                    text: strings.t(root.snapshot.selected === "fsr4" ? "fsr4Button" : "originalButton")
                                    color: Commons.Color.accent
                                }
                            }
                            Row {
                                width: parent.width
                                spacing: Commons.Style.space(6)
                                Repeater {
                                    model: ["original", "fsr4"]
                                    ActionButton {
                                        required property string modelData
                                        width: (parent.width - Commons.Style.space(6)) / 2
                                        text: strings.t(modelData + "Button")
                                        selected: root.snapshot.selected === modelData
                                        enabled: root.canChange && root.snapshot.configured
                                        bordered: true
                                        onClicked: root.run([modelData])
                                    }
                                }
                            }
                            Caption {
                                width: parent.width
                                visible: root.initialized && root.snapshot.game_installed && (root.gameRunning || root.steamRunning) && !root.repairRequired
                                text: strings.t("closeFirst")
                            }
                            ActionButton {
                                width: parent.width
                                visible: root.steamRunning && !root.repairRequired
                                text: strings.t("exitSteam")
                                foreground: Qt.alpha(Commons.Color.popups.text, 0.70)
                                enabled: !root.busy && !root.gameRunning
                                onClicked: root.run(["exit-steam"])
                            }
                        }
                    }

                    Column {
                        visible: root.tab === 1
                        width: parent.width
                        spacing: Commons.Style.space(12)
                        SectionCard {
                            width: parent.width
                            CardTitle { text: "OptiScaler / FSR4" }
                            Caption { width: parent.width; text: strings.t("optiVersion").arg(String(root.snapshot.optiscaler || strings.t("notInstalled"))) }
                            Caption { width: parent.width; text: root.checkedVersion("optiscaler") }
                            ActionButton {
                                width: parent.width
                                text: strings.t("installOpti")
                                background: Qt.alpha(Commons.Color.accent, 0.12)
                                foreground: Commons.Color.accent
                                enabled: root.canChange
                                onClicked: root.run(["install-optiscaler"])
                            }
                            Row {
                                width: parent.width
                                spacing: Commons.Style.space(6)
                                ActionButton {
                                    width: (parent.width - parent.spacing) / 2
                                    text: strings.t("repairShort")
                                    enabled: root.canChange && root.snapshot.configured
                                    bordered: true
                                    onClicked: root.run(["repair"])
                                }
                                ActionButton {
                                    width: (parent.width - parent.spacing) / 2
                                    text: strings.t("rollbackShort")
                                    enabled: root.canChange && root.snapshot.can_rollback
                                    bordered: true
                                    onClicked: root.run(["rollback"])
                                }
                            }
                        }
                        SectionCard {
                            width: parent.width
                            CardTitle { text: "Scalpel" }
                            Caption { width: parent.width; text: strings.t("scalpelVersion").arg(root.snapshot.scalpel ? String(root.snapshot.scalpel.version || strings.t("notInstalled")) : strings.t("notInstalled")) }
                            Caption { width: parent.width; text: root.checkedVersion("scalpel") }
                            ActionButton {
                                width: parent.width
                                text: strings.t("installScalpel")
                                enabled: root.initialized && !root.busy && !root.scalpelRunning
                                bordered: true
                                onClicked: root.run(["install-scalpel"])
                            }
                            Caption { width: parent.width; text: strings.t("managedHint") }
                        }
                        Caption {
                            width: parent.width
                            visible: root.initialized && (root.gameRunning || root.steamRunning)
                            text: strings.t("closeFirst")
                        }
                        ActionButton {
                            width: parent.width
                            text: strings.t("updates")
                            iconText: "↻"
                            enabled: !root.busy
                            bordered: true
                            onClicked: root.run(["check-updates"])
                        }
                        Caption { width: parent.width; text: strings.t("networkHint") }
                        SectionCard {
                            width: parent.width
                            visible: (root.snapshot.warnings || []).length > 0
                            SectionLabel { text: strings.t("setupNotes") }
                            Repeater {
                                model: root.snapshot.warnings || []
                                PlainText {
                                    required property string modelData
                                    width: parent.width
                                    text: modelData
                                    font.pixelSize: Commons.Style.font.bodySmall
                                    color: Commons.Color.urgent
                                }
                            }
                        }
                    }

                    Column {
                        visible: root.tab === 2
                        width: parent.width
                        spacing: Commons.Style.space(12)
                        SectionCard {
                            width: parent.width
                            SectionLabel { text: strings.t("startupHeading") }
                            ThemedToggle {
                                width: parent.width
                                label: strings.t("autoScalpel")
                                description: strings.t("autoScalpelHint")
                                checked: root.prefs.auto_scalpel === true
                                enabled: root.canChange
                                opacity: enabled ? 1 : 0.42
                                onClicked: root.option("auto-scalpel", checked ? "off" : "on")
                            }
                        }
                        SectionCard {
                            width: parent.width
                            SectionLabel { text: strings.t("imageQualityHeading") }
                            Caption { width: parent.width; text: strings.t("qualityHint") }
                            Row {
                                width: parent.width
                                spacing: Commons.Style.space(4)
                                Repeater {
                                    model: ["Quality", "Balanced", "Performance"]
                                    ActionButton {
                                        required property string modelData
                                        width: (parent.width - Commons.Style.space(8)) / 3
                                        text: strings.t(modelData)
                                        selected: root.prefs.quality === modelData
                                        enabled: root.canChange
                                        bordered: true
                                        horizontalPadding: Commons.Style.space(4)
                                        onClicked: root.option("quality", modelData)
                                    }
                                }
                            }
                            ThemedToggle {
                                width: parent.width
                                label: strings.t("watermark")
                                description: strings.t("watermarkHint")
                                checked: root.prefs.watermark === true
                                enabled: root.canChange
                                opacity: enabled ? 1 : 0.42
                                onClicked: root.option("watermark", checked ? "off" : "on")
                            }
                        }
                        SectionCard {
                            width: parent.width
                            SectionLabel { text: strings.t("diagnosticsHeading") }
                            ThemedToggle {
                                width: parent.width
                                label: strings.t("diagnostics")
                                description: strings.t("diagnosticsHint")
                                checked: root.prefs.diagnostics === true
                                enabled: root.canChange
                                opacity: enabled ? 1 : 0.42
                                onClicked: root.option("diagnostics", checked ? "off" : "on")
                            }
                            Rule { width: parent.width }
                            ShortcutRecorder {
                                width: parent.width
                                value: String(root.prefs.menu_key || "0xDC")
                                available: root.canChange
                                panelOpen: root.opened
                                onApplyRequested: function(code) { root.option("menu-key", code) }
                            }
                        }
                        Caption {
                            width: parent.width
                            visible: root.initialized && (root.gameRunning || root.steamRunning)
                            text: strings.t("closeFirst")
                        }
                        Caption { width: parent.width; text: strings.t("fgHint") }
                        Caption { width: parent.width; text: strings.t("gpuHint") }
                    }
                }
            }
            SectionCard {
                id: feedback
                width: parent.width
                visible: root.message !== ""
                padding: Commons.Style.space(10)
                PlainText {
                    width: parent.width
                    text: root.message
                    font.pixelSize: Commons.Style.font.bodySmall
                    color: root.failed ? Commons.Color.urgent : Commons.Color.accent
                }
            }
        }
    }
}
