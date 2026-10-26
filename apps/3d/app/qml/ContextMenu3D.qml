import QtQuick
import RostrumKit

// The right-click menu (SPEC §3.5): the action hub's own list (backend.actions.menu(): screen3d/actions3d.py), so it
// holds exactly what the settings panel, Ctrl+K and the keys run, only what applies now, with the keys the key map
// gives them; six entries at most. openAt(source, x, y, id): id is the item under the pointer ("" for empty space).
// An item outside the selection is selected alone first (as 2D's layers); one inside it keeps the selection.
// The kit's ActionMenu runs the choice once it has closed (`choose`: an action with amounts opens its popover).
Item {
    id: ctx
    function openAt(source, x, y, id) {
        if (id === "" ? backend.selection.length > 0 : backend.selection.indexOf(id) < 0) backend.select(id)
        const list = backend.actions.menu()
        if (list.length === 0) return
        const g = source.mapToItem(null, x, y)
        menu.entries = list
        menu.openAt(g.x, g.y)
    }
    ActionMenu {
        id: menu
        objectName: "contextMenu3d"
        onPicked: (v) => backend.actions.choose(v)
    }
}
