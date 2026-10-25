pragma Singleton
import QtQuick

// Who owns a key right now: the window's shortcuts ask here before they run (KeyMap, AppShell, an app's own Shortcut).
//   OpenPopups.count              how many kit popups (SmallPopup and everything built on it) are open
//   OpenPopups.top                the one opened last whose Esc closes it (`escCloses`): Esc closes that one
//   OpenPopups.takes(keys)        true when an open popup, or the focused control, uses one of these keys itself
//                                 ("Esc" while any popup is open; a menu's Up / Down / Enter; a clicked slider's Left / Right)
// A popup lists the keys it uses in `ownKeys`; a control does the same with `ownKeys` and is asked while it has the keyboard
// (AppShell keeps `focused` up to date). Every other key stays the window's: Ctrl+Z and Space work with a menu open.
QtObject {
    property var open: []                       // the open kit popups, oldest first
    readonly property int count: open.length
    readonly property var top: { for (let i = open.length - 1; i >= 0; i--) if (open[i].escCloses) return open[i]; return null }
    property Item focused: null                 // the window's activeFocusItem (AppShell)

    function add(p) { if (open.indexOf(p) < 0) open = open.concat([p]) }
    function remove(p) { if (open.indexOf(p) >= 0) open = open.filter(o => o !== p) }

    function spell(k) {                         // one spelling per key, as the key map writes it (keymap.normal)
        const s = String(k)
        return s === "Escape" ? "Esc" : s === "Return" ? "Enter" : s.replace("+Escape", "+Esc").replace("+Return", "+Enter")
    }
    function owns(list, keys) {
        if (!list || !list.length) return false
        const mine = list.map(spell)
        for (const k of keys) if (mine.indexOf(spell(k)) >= 0) return true
        return false
    }
    function takes(keys) {
        const ks = (keys || []).map(spell)
        if (ks.indexOf("Esc") >= 0 && top) return true          // its Esc closes it (BrushFlyout leaves Esc to the app)
        for (const p of open) if (owns(p.ownKeys, ks)) return true
        for (let it = focused; it; it = it.parent) if (it.ownKeys !== undefined && owns(it.ownKeys, ks)) return true
        return false
    }
}
