import QtQuick

// A part made the first time it is wanted, then kept (H65): a dialog, a sheet or a panel that starts closed costs
// nothing at start. `get()` makes it (once) and returns it; `when` (a binding: the part is open) makes it too.
//     FirstUse { id: about; sourceComponent: Component { NoticesDialog { … } } }      about.get().open()
Loader {
    property bool when: false
    active: false
    onWhenChanged: if (when) active = true
    Component.onCompleted: if (when) active = true
    function get() { active = true; return item }
}
