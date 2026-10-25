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
    property bool typing: false
    property var whileTyping: []
    // the jobs the kit's AppShell binds itself (and the app's own Export through it), never made here
    readonly property var shell: ["undo", "redo", "command_box", "history", "guides", "key_list", "next_area",
                                  "fold_panels", "export", "export_again"]
    model: hub ? hub.keys : []
    delegate: Shortcut {
        required property var modelData
        sequences: modelData.keys
        context: Qt.WindowShortcut
        autoRepeat: !modelData.hold
        enabled: km.enabled && !OpenPopups.takes(modelData.keys) &&(!km.typing || km.whileTyping.indexOf(modelData.job) >= 0) && km.skip.indexOf(modelData.job) < 0 && km.shell.indexOf(modelData.job) < 0
        onActivated: km.hub.key(modelData.job)
    }
}
