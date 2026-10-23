import QtQuick
import RostrumKit

// The right-click menu (SPEC §3.5): six entries at most, only those that apply now, from one Python list
// (screen3d/context_menu.py). openAt(source, x, y, id): id is the item under the pointer, "" for empty space.
Item {
    id: ctx
    property string itemId: ""
    function openAt(source, x, y, id) {
        const list = backend.contextEntries(id)
        if (list.length === 0) return
        itemId = id
        spot.parent = source; spot.x = x; spot.y = y
        menu.entries = list
        menu.openFrom(spot, "left")
    }
    Item { id: spot; width: 1; height: 1 }
    Menu {
        id: menu
        width: 216
        onPicked: (v) => backend.contextRun(ctx.itemId, v)
    }
}
