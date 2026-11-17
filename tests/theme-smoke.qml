import QtQuick
import Quickshell
import qs.Commons as Commons
import "@PLUGIN_URL@" as Plugin

ShellRoot {
    Item { id: host; width: 400; height: 300 }
    Component { id: labelComponent; Plugin.PlainText { text: "Theme" } }
    Component { id: buttonComponent; Plugin.ThemedButton { text: "Button" } }
    Component { id: toggleComponent; Plugin.ThemedToggle { width: 350; label: "Toggle"; description: "Help text" } }
    Component { id: cardComponent; Plugin.SectionCard { width: 350; highlighted: true } }
    Component { id: badgeComponent; Plugin.StatusBadge { text: "Running"; active: true } }

    function same(actual, expected, label) {
        if (String(actual) !== String(expected)) throw new Error(label + ": " + actual + " != " + expected)
    }
    function child(item, name) {
        if (item.objectName === name) return item
        for (var i = 0; i < item.children.length; i++) {
            var found = child(item.children[i], name)
            if (found) return found
        }
        return null
    }
    function palette(text, background, accent) {
        // Different desktop/popup roles catch controls using the wrong palette.
        Commons.Color.loadColors('foreground = "#ff00ff"\nbackground = "' + background + '"\naccent = "' + accent + '"')
        Commons.Color.loadShell('[popups]\ntext = "' + text + '"\nbackground = "' + background + '"\n[controls]\nselected-color = "foreground"\n')
    }
    Timer {
        interval: 300
        running: true
        onTriggered: {
            try {
                palette("#eeeeee", "#202020", "#88aaff")
                var label = labelComponent.createObject(host)
                var button = buttonComponent.createObject(host)
                var toggle = toggleComponent.createObject(host)
                var card = cardComponent.createObject(host)
                var badge = badgeComponent.createObject(host)
                if (!label || !button || !toggle || !card || !badge) throw new Error("A component did not load")
                same(label.color, Qt.color("#eeeeee"), "dark text")
                same(button.foreground, Qt.color("#eeeeee"), "dark button")
                same(toggle.foreground, Qt.color("#eeeeee"), "dark toggle")
                same(child(toggle, "description").color, Qt.alpha("#eeeeee", 0.70), "dark help")
                same(card.border.color, Qt.alpha("#88aaff", 0.28), "dark card")
                same(badge.tint, Qt.color("#88aaff"), "dark badge")

                // Reuse the same controls: a restart would conceal stale bindings.
                palette("#223344", "#f5f5f5", "#006655")
                same(label.color, Qt.color("#223344"), "light text")
                same(button.foreground, Qt.color("#223344"), "light button")
                same(toggle.foreground, Qt.color("#223344"), "light toggle")
                same(child(toggle, "description").color, Qt.alpha("#223344", 0.70), "light help")
                same(card.border.color, Qt.alpha("#006655", 0.28), "light card")
                same(badge.tint, Qt.color("#006655"), "light badge")
                console.log("POE2_THEME_TEST: PASS")
            } catch (error) {
                console.error("POE2_THEME_TEST: FAIL " + error)
            }
            Qt.quit()
        }
    }
}
