import QtQuick
import "."
import "MenuPlace.js" as Place

// Opens an ActionMenu from a button by the kit's one placement rule (MenuPlace.js): under `anchor`, clear of the tool rail,
// the settings panel and the timeline's names column where there is room, inside the window always.
//   MenuSpot { id: spot; anchor: button; menu: menu; align: "right" }      spot.open(entries)
QtObject {
    id: spot
    property Item anchor: null
    property var menu: null
    property string align: "left"
    property real x0: NaN                   // a fixed left edge instead of the button's
    function open(entries) { menu.entries = entries; menu.openAt(0, 0); Qt.callLater(place) }    // its size settles a moment later
    function place() {
        if (!menu || !anchor || !anchor.Window.window) return
        const q = Place.near(anchor, menu.width, menu.height, anchor.Window.window.contentItem, menu.parent, { align: align, x: x0 })
        menu.at = { px: q.x, py: q.y }
        menu.place()
    }
    function floorBelow(x, w, y) {      // the lowest a panel at [x, x + w) starting at y may reach: above the timeline's names, else the window's bottom
        const ov = anchor.Window.window.contentItem
        return Place.floorBelow(ov, ov, x, w, y, 8)
    }
    property Connections size: Connections {
        target: spot.menu
        function onHeightChanged() { if (spot.menu.opened) spot.place() }
        function onWidthChanged() { if (spot.menu.opened) spot.place() }
    }
}
