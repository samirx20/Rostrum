import QtQuick
import "."

// The selection's actions at the top of the settings panel (SPEC 2d-design-v2 §8.3, "actions first"): the app's one
// action list as `hub.panel` (rostrum_gui/action_views.panel) — only what this selection allows, in its order. Compact
// like a pro tool's (H49): actions sharing a bar name whose every action has an icon are one tight run of small icon
// buttons (Align: six; Combine: four; the name on hover); a bar without icons is one "Mask ▾" button with its menu;
// the rest small buttons. The icon runs come first, so they start at the panel's left edge whatever buttons the
// selection has; the slots are fixed in the data (action_views.panel: what applies to one item first, so a second item
// only adds after). The runs flow on the panel grid, a wider gap between runs, wrapping when the panel is narrow. The
// less used ones (secondary) are one "⋯" at the end of the row, folded like right-click; no main action, no row.
// Resting on an action (about 250 ms) shows its would-be result on the canvas, recorded nowhere (hub.previewStart; H63);
// moving off (or the row changing, or a click) takes it back. An app whose hub has no preview shows nothing.
Item {
    id: section
    property var hub: null
    readonly property var rows: hub ? hub.panel.rows : []
    readonly property var more: hub ? hub.panel.more : []
    // the units that flow: an icon run, a folded bar, or ONE small button (so a row of long names wraps button by button
    // instead of running under the ⋯)
    readonly property var units: rows.reduce((all, r) => all.concat(
        r.items.every(i => !!i.icon) ? [{ items: r.items, icons: true, title: "" }]
        : r.title !== "" ? [{ items: r.items, icons: false, title: r.title }]
        : r.items.map(i => ({ items: [i], icons: false, title: "" }))), [])
    readonly property int size: Theme.field
    visible: rows.length > 0
    height: visible ? runs.height + Theme.pad : 0
    property string resting: ""          // the action the pointer is on; its preview starts after the delay
    function rest(id) { resting = id; delay.restart() }
    function leave() { resting = ""; delay.stop(); if (hub) hub.previewEnd() }
    Timer { id: delay; interval: 250; onTriggered: if (section.resting !== "" && section.hub) section.hub.previewStart(section.resting) }
    onRowsChanged: leave()                // another selection: whatever was shown goes back
    function openMenu(button, entries) {
        const g = button.mapToItem(null, 0, button.height)
        menu.entries = entries; menu.openAt(g.x, g.y)
    }
    Flow {
        id: runs
        width: section.width
        spacing: 3 * Theme.grid
        Repeater {
            model: section.units
            delegate: Row {
                id: run
                required property var modelData
                readonly property bool icons: modelData.icons
                readonly property bool folded: modelData.title !== ""
                spacing: icons ? 2 : Theme.grid
                Repeater {      // an icon run
                    model: run.icons ? run.modelData.items : []
                    delegate: IconButton {
                        required property var modelData
                        objectName: "action:" + modelData.id
                        width: section.size; height: section.size
                        icon: modelData.icon; kind: "ghost"; tip: modelData.full || modelData.label
                        help: modelData.keys ? "Key: " + modelData.keys : ""
                        onHoveredChanged: hovered ? section.rest(modelData.id) : section.leave()
                        onClicked: { delay.stop(); section.hub.run(modelData.id) }
                    }
                }
                Repeater {      // the untitled actions: small buttons
                    model: run.icons || run.folded ? [] : run.modelData.items
                    delegate: Button {
                        required property var modelData
                        objectName: "action:" + modelData.id
                        implicitHeight: section.size; text: modelData.label; tip: modelData.label
                        help: modelData.keys ? modelData.label + " (" + modelData.keys + ")" : ""
                        onHoveredChanged: hovered ? section.rest(modelData.id) : section.leave()
                        onClicked: { delay.stop(); section.hub.run(modelData.id) }
                    }
                }
                Button {        // a bar without icons: one button, its actions in a menu
                    id: barButton
                    visible: run.folded
                    objectName: "actionBar:" + run.modelData.title
                    implicitHeight: section.size; text: run.modelData.title; chevron: true
                    onClicked: section.openMenu(barButton, run.modelData.items.map(i => ({ value: i.id, label: i.label,
                                                                                             keys: i.keys, group: "", sub: [] })))
                }
            }
        }
        IconButton {    // "⋯" last in the row, the same icon button as the context bar's (More is the Song panel's fold)
        id: moreButton
        objectName: "actionsMore"
        visible: section.more.length > 0
        width: section.size; height: section.size
        kind: "ghost"; glyph: "⋯"; tip: "More"; help: "The other actions for this selection"
        onClicked: section.openMenu(moreButton, section.more)
        }
    }
    ActionMenu { id: menu; onPicked: (v) => { delay.stop(); section.hub.run(v) }; onRested: (v) => v === "" ? section.leave() : section.rest(v) }
}
