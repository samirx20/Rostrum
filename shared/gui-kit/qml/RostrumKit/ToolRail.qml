import QtQuick
import "."

// The kit's tool rail (design v2 §2.1): icons only, its own column left of the work area, never over it. The app fills
// it from `groups`; the kit draws it, tracks each group's last-used tool and opens the flyouts.
//   group: { id, name, items: [entry] }  or a divider { sep: true, when: bool }  (a group with no items is left out)
//   entry: { name, icon, job (key map job: the key shown), help, tool (a tool that stays on) or act (happens now),
//            kind (an icon the app draws: iconKinds) }
//   A group with one entry is a plain button; with more it opens a flyout beside the rail, its icon the last-used tool.
//   A group with `panel: true` opens the app's own panel instead (2D's brush panel): the rail only emits
//   panelRequested(group) / panelCloseRequested() and the app says whether it is open (panelOpen).
// `current` is the active tool's name (the app binds it, so a key moves the icon too). A pick closes the flyout and
// emits picked(entry); the app switches the tool or does the act.
Rectangle {
    id: rail
    property var groups: []
    property string current: ""
    property var iconKinds: ({})                    // kind -> Component (an Item with `name` and `ink`)
    property bool panelOpen: false
    property bool menuAvoid: true                   // menus and flyouts open beside the rail, not over it (MenuPlace.js)
    property var last: ({})                         // group id -> its last-used tool (screen state)
    signal picked(var entry)
    signal panelRequested(var group)
    signal panelCloseRequested()
    signal groupOpening(string id)                  // before any group opens or closes the flyout ("" = close): the app closes its own panel
    width: 48
    color: Theme.panel; radius: Theme.radiusPanel
    readonly property var usable: groups.filter(g => g.sep ? g.when !== false : g.items.length > 0)   // what is usable now
    readonly property bool flyoutOpen: flyout.visible || panelOpen
    readonly property bool menuOpen: flyout.visible   // a group's menu; a group's own panel is part of its tool, not a menu

    function groupOf(tool) { return rail.usable.find(g => !g.sep && g.items.some(e => e.tool === tool)) }
    function shown(g) {        // the entry on the group's icon: its last-used tool, else the first
        return g.items.find(e => e.tool && e.tool === rail.last[g.id]) || g.items[0]
    }
    onCurrentChanged: {
        const g = rail.groupOf(rail.current)
        if (g && g.items.length > 1) { const l = Object.assign({}, rail.last); l[g.id] = rail.current; rail.last = l }
    }
    function buttonOf(id) { return buttons.itemAt(rail.usable.findIndex(g => g.id === id)) }   // a group's button (a panel opens beside it)
    function pick(e) { flyout.close(); rail.picked(e) }
    function openGroup(id) {   // the flyout of group `id` (scripted steps, a key), or "" to close it
        const i = rail.usable.findIndex(g => g.id === id)
        if (i >= 0 && rail.usable[i].panel) { flyout.close(); rail.panelRequested(rail.usable[i]); return true }
        rail.groupOpening(id)
        if (i < 0 || rail.usable[i].items.length < 2) { flyout.close(); return false }
        flyout.show(rail.usable[i], buttons.itemAt(i))
        return true
    }
    function closeFlyout() { flyout.close() }

    Column {
        id: column
        x: (rail.width - Theme.button - 8) / 2; y: 6
        spacing: 4
        Repeater {
            id: buttons
            model: rail.usable
            delegate: Item {
                id: slot
                required property var modelData
                readonly property var g: modelData
                readonly property var e: g.sep ? null : rail.shown(g)
                readonly property bool many: !!(!g.sep && g.items.length > 1)
                readonly property bool on: !g.sep && g.items.some(x => x.tool && x.tool === rail.current) || (flyout.visible && flyout.group === g.id)
                readonly property bool panel: !!g.panel
                width: Theme.button + 8; height: g.sep ? 9 : Theme.button + 8
                objectName: g.sep ? "" : "rail_" + g.id
                Rectangle { visible: !!slot.g.sep; anchors.centerIn: parent; width: parent.width - 8; height: 1; color: Theme.popupEdge }
                Rectangle {
                    visible: !slot.g.sep
                    anchors.fill: parent; radius: Theme.radiusCtl
                    color: area.pressed || slot.on ? Theme.active : hover.hovered ? Theme.hover : "transparent"
                    Behavior on color { ColorAnimation { duration: Theme.fast } }
                }
                RailIcon { visible: !slot.g.sep; anchors.centerIn: parent; entry: slot.e; kinds: rail.iconKinds
                           ink: slot.on || hover.hovered ? Theme.fg : Theme.fg2 }
                Canvas {   // the corner mark of a group with a flyout
                    visible: slot.many || slot.panel
                    anchors { right: parent.right; bottom: parent.bottom; margins: 3 }
                    width: 5; height: 5
                    onPaint: { const c = getContext("2d"); c.reset(); c.fillStyle = Theme.fg3
                               c.beginPath(); c.moveTo(5, 0); c.lineTo(5, 5); c.lineTo(0, 5); c.closePath(); c.fill() }
                }
                HoverHandler { id: hover; enabled: !slot.g.sep; cursorShape: Qt.PointingHandCursor }
                MouseArea {
                    id: area
                    anchors.fill: parent; enabled: !slot.g.sep
                    onClicked: slot.panel ? (rail.panelOpen ? rail.panelCloseRequested() : rail.panelRequested(slot.g))
                             : slot.many ? (flyout.visible && flyout.group === slot.g.id ? flyout.close() : rail.openGroup(slot.g.id))
                                         : rail.pick(slot.e)
                    pressAndHoldInterval: 350
                    onPressAndHold: if (slot.many) rail.openGroup(slot.g.id)
                }
                HoverTip {   // beside the rail: the name and the key
                    x: slot.width + 6; y: (slot.height - height) / 2
                    text: slot.many ? (slot.g.name || slot.e.name) : slot.e ? slot.e.name : ""
                    help: !slot.many && slot.e && slot.e.help ? slot.e.help : ""
                    key: slot.e && slot.e.job && slot.Window.window && slot.Window.window.keyFor ? slot.Window.window.keyFor(slot.many && slot.g.job ? slot.g.job : slot.e.job) : ""
                    hovered: hover.hovered && !rail.flyoutOpen; pressed: area.pressed
                }
            }
        }
    }
    ToolFlyout { id: flyout; current: rail.current; kinds: rail.iconKinds; onPicked: (e) => rail.pick(e) }
}
