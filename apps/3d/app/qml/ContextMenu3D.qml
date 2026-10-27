import QtQuick
import RostrumKit

// The right-click menu (SPEC §3.5): the action hub's own list (backend.actions.menu(): screen3d/actions3d.py), so it
// holds exactly what the settings panel, Ctrl+K and the keys run, only what applies now, with the keys the key map
// gives them; eight entries at most (six, Make copies ›, Simulate ›). openAt(source, x, y, id): id is the item under the pointer ("" for empty space).
// An item outside the selection is selected alone first (as 2D's layers; backend.menuSelect, which also remembers what was
// selected before, so a right-click on a surface offers "Scatter '<it>' on '<surface>'"); one inside it keeps the selection.
// Make copies and Change near are one row each with the kit's side menu (Line · Grid · Circle · On a surface…; Scale · Turn · Push · Colour);
// so is Simulate (Falls · Stays still · Off; sim_actions.py), the selection's kind ticked (backend.sim.kind).
// The kit's ActionMenu runs the choice once it has closed (`choose`: an action with amounts opens its popover).
Item {
    id: ctx
    function openAt(source, x, y, id) {
        backend.menuSelect(id)
        const list = backend.actions.menu()
        if (list.length === 0) return
        const g = source.mapToItem(null, x, y)
        menu.entries = list.map(e => e.value !== "menu:Simulate" ? e
            : Object.assign({}, e, { sub: e.sub.map(s => Object.assign({}, s, { checked: s.value === "sim:" + backend.sim.kind })) }))
        menu.openAt(g.x, g.y)
        project.openAt(g.x, g.y)          // Project a picture… opens its own short menu at the same place
    }
    ProjectPicture { id: project }
    ActionMenu {
        id: menu
        objectName: "contextMenu3d"
        onPicked: (v) => backend.actions.choose(v)
    }
}
