.pragma library

// Qt keys are not Windows virtual keys. Keep this mapping explicit: e.g.
// section sign U+00A7 must never be saved as VK 0xA7 (Browser Forward).
var shift = 0x02000000
var control = 0x04000000
var alt = 0x08000000
var meta = 0x10000000
var keypad = 0x20000000
var groupSwitch = 0x40000000

var special = {
    0x01000001: [0x09, "Tab"],
    0x01000003: [0x08, "Backspace"],
    0x01000004: [0x0D, "Enter"],
    0x01000005: [0x0D, "Enter"],
    0x01000006: [0x2D, "Insert"],
    0x01000007: [0x2E, "Delete"],
    0x01000008: [0x13, "Pause"],
    0x01000009: [0x2C, "Print Screen"],
    0x01000010: [0x24, "Home"],
    0x01000011: [0x23, "End"],
    0x01000012: [0x25, "Left"],
    0x01000013: [0x26, "Up"],
    0x01000014: [0x27, "Right"],
    0x01000015: [0x28, "Down"],
    0x01000016: [0x21, "Page Up"],
    0x01000017: [0x22, "Page Down"],
    0x20: [0x20, "Space"],
    0xA7: [0xDC, "§"]
}

function hex(code) { return "0x" + ("0" + code.toString(16).toUpperCase()).slice(-2) }

function fromKey(key, modifiers) {
    if (key === 0x01000000) return {cancel: true}
    // Let users release a modifier and then press their intended single key.
    if ([0x01000020, 0x01000021, 0x01000022, 0x01000023, 0x01001103].indexOf(key) >= 0)
        return {ignore: true}
    if (modifiers & (shift | control | alt | meta | groupSwitch))
        return {error: "shortcutSingleKey"}

    var vk = 0
    var label = ""
    if (modifiers & keypad) {
        if (key >= 0x30 && key <= 0x39) {
            vk = 0x60 + key - 0x30
            label = "Num " + String.fromCharCode(key)
        } else {
            var numpad = {0x2A: [0x6A, "Num *"], 0x2B: [0x6B, "Num +"],
                0x2D: [0x6D, "Num −"], 0x2E: [0x6E, "Num ."], 0x2F: [0x6F, "Num /"],
                0x01000005: [0x0D, "Enter"]}
            if (numpad[key]) { vk = numpad[key][0]; label = numpad[key][1] }
        }
    } else if ((key >= 0x41 && key <= 0x5A) || (key >= 0x30 && key <= 0x39)) {
        vk = key
        label = String.fromCharCode(key)
    } else if (key >= 0x01000030 && key <= 0x01000047) {
        vk = 0x70 + key - 0x01000030
        label = "F" + (key - 0x01000030 + 1)
    } else if (special[key]) {
        vk = special[key][0]
        label = special[key][1]
    }
    // Punctuation varies between Windows keyboard layouts. Never guess an OEM key.
    return vk ? {code: hex(vk), label: label} : {error: "shortcutUnsupported"}
}

function name(code) {
    var vk = parseInt(code, 16)
    if ((vk >= 0x41 && vk <= 0x5A) || (vk >= 0x30 && vk <= 0x39)) return String.fromCharCode(vk)
    if (vk >= 0x70 && vk <= 0x87) return "F" + (vk - 0x70 + 1)
    if (vk >= 0x60 && vk <= 0x69) return "Num " + (vk - 0x60)
    var numpad = {0x6A: "Num *", 0x6B: "Num +", 0x6D: "Num −", 0x6E: "Num .", 0x6F: "Num /"}
    if (numpad[vk]) return numpad[vk]
    for (var key in special) if (special[key][0] === vk) return special[key][1]
    return /^0x[0-9a-f]{1,2}$/i.test(code) ? hex(vk) : "—"
}
