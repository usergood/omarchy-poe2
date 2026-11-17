import QtQuick
import qs.Commons as Commons
import qs.Ui
import "ShortcutKeys.js" as ShortcutKeys

Column {
    id: root
    property string value: "0xDC"
    property bool available: false
    property bool panelOpen: false
    property string mode: "idle"
    property string candidate: ""
    property string candidateLabel: ""
    property string errorKey: ""
    signal applyRequested(string code)
    spacing: Commons.Style.space(10)

    Commons.Translations { id: strings; directory: Qt.resolvedUrl("i18n") }
    function reset() { mode = "idle"; candidate = ""; candidateLabel = ""; errorKey = "" }
    function begin() {
        if (!available) return
        candidate = ""
        candidateLabel = ""
        errorKey = ""
        mode = "listening"
        Qt.callLater(function() { if (root.mode === "listening") captureArea.forceActiveFocus() })
    }
    function cancel() {
        reset()
        Qt.callLater(function() { if (root.visible && root.panelOpen) changeButton.forceActiveFocus() })
    }
    function accept() {
        if (!available || mode !== "review" || !candidate) return
        var code = candidate
        reset()
        applyRequested(code)
    }
    function record(event) {
        event.accepted = true
        if (event.isAutoRepeat) return
        var result = ShortcutKeys.fromKey(event.key, event.modifiers)
        if (result.cancel) { cancel(); return }
        if (result.ignore) return
        if (result.error) { errorKey = result.error; return }
        candidate = result.code
        candidateLabel = result.label
        errorKey = ""
        mode = "review"
        Qt.callLater(function() { if (root.mode === "review") acceptButton.forceActiveFocus() })
    }
    onValueChanged: reset()
    onAvailableChanged: if (!available) reset()
    onPanelOpenChanged: if (!panelOpen) reset()
    onVisibleChanged: if (!visible) reset()
    Keys.onEscapePressed: function(event) {
        if (root.mode !== "idle") { event.accepted = true; root.cancel() }
        else event.accepted = false
    }

    Row {
        width: parent.width
        spacing: Commons.Style.space(10)
        Column {
            width: parent.width - currentKey.width - changeButton.width - parent.spacing * 2
            anchors.verticalCenter: parent.verticalCenter
            spacing: Commons.Style.space(3)
            PlainText { width: parent.width; text: strings.t("menuShortcut"); font.weight: Font.Medium }
            PlainText {
                width: parent.width
                text: "OptiScaler"
                font.pixelSize: Commons.Style.font.caption
                color: Qt.alpha(Commons.Color.popups.text, 0.70)
            }
        }
        Rectangle {
            id: currentKey
            anchors.verticalCenter: parent.verticalCenter
            implicitWidth: currentLabel.implicitWidth + Commons.Style.space(20)
            implicitHeight: currentLabel.implicitHeight + Commons.Style.space(12)
            color: Qt.alpha(Commons.Color.popups.text, 0.04)
            border.width: 1
            border.color: Qt.alpha(Commons.Color.popups.text, 0.18)
            radius: Commons.Style.cornerRadius
            PlainText {
                id: currentLabel
                anchors.centerIn: parent
                text: ShortcutKeys.name(root.value)
                font.weight: Font.DemiBold
                wrapMode: Text.NoWrap
            }
        }
        Button {
            id: changeButton
            anchors.verticalCenter: parent.verticalCenter
            text: strings.t("changeShortcut")
            focusable: true
            bordered: true
            enabled: root.available && root.mode === "idle"
            opacity: enabled ? 1 : 0.42
            onClicked: root.begin()
        }
    }
    SectionCard {
        width: parent.width
        visible: root.mode !== "idle"
        highlighted: true
        padding: Commons.Style.space(12)
        FocusScope {
            id: captureArea
            width: parent.width
            implicitHeight: captureText.implicitHeight
            Keys.priority: Keys.BeforeItem
            Keys.onShortcutOverride: function(event) { if (root.mode === "listening") event.accepted = true }
            Keys.onPressed: function(event) {
                if (root.mode === "listening") root.record(event)
            }
            Keys.onReleased: function(event) { if (root.mode !== "idle") event.accepted = true }
            PlainText {
                id: captureText
                width: parent.width
                text: root.mode === "listening" ? strings.t("pressShortcut") : strings.t("proposedShortcut").arg(root.candidateLabel).arg(root.candidate)
                color: Commons.Color.accent
                font.weight: Font.DemiBold
            }
        }
        PlainText {
            width: parent.width
            text: root.errorKey ? strings.t(root.errorKey) : strings.t(root.mode === "listening" ? "shortcutCaptureHint" : "shortcutConfirmHint")
            font.pixelSize: Commons.Style.font.bodySmall
            color: root.errorKey ? Commons.Color.urgent : Qt.alpha(Commons.Color.popups.text, 0.70)
        }
        Row {
            width: parent.width
            spacing: Commons.Style.space(6)
            Button {
                id: acceptButton
                visible: root.mode === "review"
                text: strings.t("acceptShortcut")
                selected: true
                focusable: true
                enabled: root.available && root.candidate !== ""
                onClicked: root.accept()
                // Holding Enter/Space while recording must not auto-confirm it.
                Keys.onReturnPressed: function(event) { event.accepted = true; if (!event.isAutoRepeat) root.accept() }
                Keys.onEnterPressed: function(event) { event.accepted = true; if (!event.isAutoRepeat) root.accept() }
                Keys.onSpacePressed: function(event) { event.accepted = true; if (!event.isAutoRepeat) root.accept() }
            }
            Button {
                visible: root.mode === "review"
                text: strings.t("retryShortcut")
                focusable: true
                onClicked: root.begin()
            }
            Button {
                text: strings.t("cancelShortcut")
                focusable: true
                onClicked: root.cancel()
            }
        }
    }
    PlainText {
        width: parent.width
        visible: root.mode === "idle"
        text: strings.t("shortcutHint")
        font.pixelSize: Commons.Style.font.bodySmall
        color: Qt.alpha(Commons.Color.popups.text, 0.70)
    }
}
