import QtQuick
import QtTest
import "../../ShortcutKeys.js" as ShortcutKeys

TestCase {
    name: "ShortcutKeys"

    function test_mapping_data() {
        return [
            {tag: "Swedish section sign", key: 0xA7, mods: 0, code: "0xDC", label: "§"},
            {tag: "F10", key: Qt.Key_F10, mods: 0, code: "0x79", label: "F10"},
            {tag: "F24", key: Qt.Key_F24, mods: 0, code: "0x87", label: "F24"},
            {tag: "letter", key: Qt.Key_K, mods: 0, code: "0x4B", label: "K"},
            {tag: "digit", key: Qt.Key_7, mods: 0, code: "0x37", label: "7"},
            {tag: "Home", key: Qt.Key_Home, mods: 0, code: "0x24", label: "Home"},
            {tag: "Insert", key: Qt.Key_Insert, mods: 0, code: "0x2D", label: "Insert"},
            {tag: "Tab", key: Qt.Key_Tab, mods: 0, code: "0x09", label: "Tab"},
            {tag: "Enter", key: Qt.Key_Return, mods: 0, code: "0x0D", label: "Enter"},
            {tag: "Space", key: Qt.Key_Space, mods: 0, code: "0x20", label: "Space"},
            {tag: "numpad digit", key: Qt.Key_7, mods: Qt.KeypadModifier, code: "0x67", label: "Num 7"},
            {tag: "numpad plus", key: Qt.Key_Plus, mods: Qt.KeypadModifier, code: "0x6B", label: "Num +"}
        ]
    }
    function test_mapping(data) {
        var result = ShortcutKeys.fromKey(data.key, data.mods)
        compare(result.code, data.code)
        compare(result.label, data.label)
        compare(ShortcutKeys.name(result.code), result.label)
    }
    function test_modifiers_rejected_data() {
        return [
            {tag: "Shift", mod: Qt.ShiftModifier}, {tag: "Ctrl", mod: Qt.ControlModifier},
            {tag: "Alt", mod: Qt.AltModifier}, {tag: "Super", mod: Qt.MetaModifier}
        ]
    }
    function test_modifiers_rejected(data) {
        compare(ShortcutKeys.fromKey(Qt.Key_F10, data.mod).error, "shortcutSingleKey")
    }
    function test_modifier_alone_ignored() {
        compare(ShortcutKeys.fromKey(Qt.Key_Shift, Qt.ShiftModifier).ignore, true)
        compare(ShortcutKeys.fromKey(Qt.Key_Control, Qt.ControlModifier).ignore, true)
    }
    function test_escape_cancels() { compare(ShortcutKeys.fromKey(Qt.Key_Escape, 0).cancel, true) }
    function test_ambiguous_punctuation_is_not_guessed() {
        compare(ShortcutKeys.fromKey(Qt.Key_QuoteLeft, 0).error, "shortcutUnsupported")
        compare(ShortcutKeys.fromKey(Qt.Key_unknown, 0).error, "shortcutUnsupported")
    }
    function test_existing_cli_key_has_safe_fallback() {
        compare(ShortcutKeys.name("0xDB"), "0xDB")
        compare(ShortcutKeys.name("invalid"), "—")
    }
}
