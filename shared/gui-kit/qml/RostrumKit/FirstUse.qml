import QtQuick

// A part made the first time it is wanted, then kept (H65): a dialog, a sheet or a panel that starts closed costs
// nothing at start. `get()` makes it (once) and returns it; `when` (a binding: the part is open) makes it too.
// `ahead`: a part a person opens with one click (the brush panel): made bit by bit while the app is idle, a moment
// after the window shows, so even its first opening is instant (wanted before that, it is finished at once).
//     FirstUse { id: about; sourceComponent: Component { NoticesDialog { … } } }      about.get().open()
Loader {
    id: use
    property bool when: false
    property bool ahead: false
    active: false
    onWhenChanged: if (when) now()
    Component.onCompleted: if (when) now()
    function now() { asynchronous = false; active = true }     // an unfinished making ahead completes here
    function close() { if (item && typeof item.close === "function") item.close() }   // (a Panel closes the other sheets by this)
    function get() { now(); return item }
    property Timer idle: Timer {
        running: use.ahead && !use.active; interval: 1500
        onTriggered: { use.asynchronous = true; use.active = true }
    }
}
