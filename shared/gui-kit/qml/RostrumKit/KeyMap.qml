import QtQuick
import "."

// The window's shortcuts, made from the key map. `hub.keys` is [{job, keys: [sequences], label}]; a pressed key
// calls hub.key(job). Put one in the root window. `skip`: jobs the host handles itself (a text field's own keys).
// A hold key (`hold`) fires once on the press, never auto-repeats; its release reaches hub.keyUp(job) (keyhold.py).
// `enabled: false` turns every shortcut off (a dialog with its own typing). The keys the window's AppShell binds itself
// (`shell`: undo, redo, Ctrl+K, History, guides, the key list, F6, Ctrl+\, export) are always left to it. A key an open
// popup or the focused control uses itself waits (OpenPopups.takes: Esc closes the popup, a menu's arrows move in it).
Instantiator {
    id: km
    property var hub
    property bool enabled: true
    property var skip: []
    // `typing`: a text field has the keys, so the window's keys wait. `whileTyping`: the jobs that still answer then
    // (a panel's own toggle key: Ctrl+L must close the Library whose search box has the keyboard).
    // In a kit field (FieldFrame: a number or a setting, in a panel or a popover) only the keys a text box uses itself wait:
    // a Ctrl command it has no use for (Ctrl+G, Ctrl+D, F2 …) lets the field go, which keeps what was typed, then runs
    // (critic 2d-r11: Ctrl+G with Stagger's number in edit did nothing, without a word). A key that types (a letter, Space,
    // Delete, Home) never leaves a box for the window, a number box's included: a letter it can't hold is said there
    // ("Type a number", NumberField.saysLetter), never run as M (a marker) or Delete (the layer) (critic 2d-final row 1).
    property bool typing: false
    property var whileTyping: []
    readonly property bool inField: typing && !!OpenPopups.focused && OpenPopups.focused.pending !== undefined
    function textKey(keys) {        // does a text box use one of these keys itself (letters, Delete, Ctrl+C, Shift+Left …)
        const edit = ["A", "C", "V", "X", "Z", "Y", "Left", "Right", "Up", "Down", "Home", "End", "Backspace", "Delete", "Ins"]
        for (const k of keys) {
            const parts = String(k).split("+"), key = parts[parts.length - 1] || "+", mods = parts.slice(0, -1)
            if (mods.indexOf("Alt") >= 0 || mods.indexOf("Meta") >= 0) return true      // AltGr types characters
            if (mods.indexOf("Ctrl") < 0 && !/^F[0-9]+$/.test(key)) return true            // a plain or shifted key types
            if (mods.indexOf("Ctrl") >= 0 && edit.indexOf(key) >= 0) return true
        }
        return false
    }
    // the jobs the kit's AppShell binds itself (and the app's own Export through it), never made here
    readonly property var shell: ["undo", "redo", "command_box", "history", "guides", "key_list", "next_area",
                                  "fold_panels", "export", "export_again", "go_to_time"]
    model: hub ? hub.keys : []
    delegate: KeyShortcut {
        required property var modelData
        sequences: modelData.sequences || modelData.keys      // every spelling a key may arrive in (keymap.typed: Ctrl+Shift+= is Ctrl++)
        autoRepeat: !modelData.hold
        readonly property bool passes: !km.textKey(modelData.keys)       // answers even in a kit field (above)
        enabled: km.enabled && !OpenPopups.takes(modelData.keys) && (!km.typing || km.whileTyping.indexOf(modelData.job) >= 0 || (km.inField && passes)) && km.skip.indexOf(modelData.job) < 0 && km.shell.indexOf(modelData.job) < 0
        onActivated: {
            if (km.inField) OpenPopups.focused.focus = false     // the field lets go first: what was typed is kept (FieldFrame)
            km.hub.key(modelData.job)
        }
    }
}
