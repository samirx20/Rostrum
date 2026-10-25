pragma Singleton
import QtQuick

// Who owns a key right now: the window's shortcuts ask here before they run (KeyMap, AppShell, an app's own Shortcut).
//   OpenPopups.count              how many kit popups (SmallPopup and everything built on it) are open
//   OpenPopups.top                the one opened last whose Esc closes it (`escCloses`): Esc closes that one
//   OpenPopups.closeTop()         the window's ONE Esc (AppShell, while `escWanted`): closes `top`, after its `escaped()`
// Popups add themselves (SmallPopup, modal dialogs included); a panel or sheet that is not a popup but closes on Esc
// (the guides drawer, History, Export, Sound's Library, the start screen) is added by an EscCloses while it is open.
// So Esc closes the newest open thing wherever the keyboard is, one level per press (a side menu, then its menu).
//   OpenPopups.takes(keys)        true when an open popup, or the focused control, uses one of these keys itself
//                                 ("Esc" while any popup is open; a menu's Up / Down / Enter; a clicked slider's Left / Right)
// A popup lists the keys it uses in `ownKeys`; a control does the same with `ownKeys` and is asked while it has the keyboard
// (AppShell keeps `focused` up to date). Every other key stays the window's: Ctrl+Z and Space work with a menu open.
//   OpenPopups.covered            a screen over the whole work is open (`covers`: the start screen): every key is its own,
//                                 so `takes` is true for all of them; only its own Shortcuts (New, Open) and Esc still run
QtObject {
    property var open: []                       // the open kit popups, oldest first
    readonly property int count: open.length
    readonly property bool covered: open.some(p => !!p.covers)
    readonly property var top: { for (let i = open.length - 1; i >= 0; i--) if (open[i].escCloses) return open[i]; return null }
    property Item focused: null                 // the window's activeFocusItem (AppShell)
    readonly property bool typing: !!focused && focused.cursorPosition !== undefined && focused.selectByMouse !== undefined
    // Esc closes `top`, except while a text box outside it has the keys: there Esc drops the typing first (a name box)
    readonly property bool escWanted: !!top && !(typing && !holds(top, focused))
    function holds(p, item) {                   // is `item` inside the open popup / panel `p`
        for (let it = item; it; it = it.parent) if (it === p.contentItem || (!!p.area && it === p.area)) return true
        return false
    }
    function closeTop() {
        const p = top
        if (!p) return false
        if (typeof p.escaped === "function") p.escaped()
        p.close()
        return true
    }

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
        if (covered) return true                                  // nothing behind the start screen hears a key
        const ks = (keys || []).map(spell)
        if (ks.indexOf("Esc") >= 0 && top) return true          // its Esc closes it (BrushFlyout leaves Esc to the app)
        for (const p of open) if (owns(p.ownKeys, ks)) return true
        for (let it = focused; it; it = it.parent) if (it.ownKeys !== undefined && owns(it.ownKeys, ks)) return true
        return false
    }
}
