import QtQuick
import "."

// The selection's actions at the top of the settings panel (SPEC 2d-design-v2 §8.3, "actions first"): the app's one
// action list as `hub.panel` (rostrum_gui/action_views.panel) — only what this selection allows, in its order. Compact
// like a pro tool's (H49): actions sharing a bar name whose every action has an icon are one tight run of small icon
// buttons (Align: six; Combine: four; the name on hover); a bar without icons is one "Mask ▾" button with its menu;
// the rest small buttons. The runs flow on the panel grid, a wider gap between runs, wrapping when the panel is
// narrow. The less used ones (secondary) are one "⋯" menu last, folded like right-click.
// No hover preview yet: drawing a would-be result needs the engine to render one (left for later, said in H48).
Flow {
    id: section
    property var hub: null
    readonly property var rows: hub ? hub.panel.rows : []
    readonly property var more: hub ? hub.panel.more : []
    readonly property int size: Theme.field
    spacing: 3 * Theme.grid
    bottomPadding: visible ? Theme.pad : 0
    visible: rows.length + more.length > 0
    function openMenu(button, entries) {
        const g = button.mapToItem(null, 0, button.height)
        menu.entries = entries; menu.openAt(g.x, g.y)
    }
    Repeater {
        model: section.rows
        delegate: Row {
            id: run
            required property var modelData
            readonly property bool icons: modelData.items.every(i => !!i.icon)
            readonly property bool folded: !icons && modelData.title !== ""
            spacing: icons ? 2 : Theme.grid
            Repeater {      // an icon run
                model: run.icons ? run.modelData.items : []
                delegate: IconButton {
                    required property var modelData
                    objectName: "action:" + modelData.id
                    width: section.size; height: section.size
                    icon: modelData.icon; kind: "ghost"; tip: modelData.full || modelData.label
                    help: modelData.keys ? "Key: " + modelData.keys : ""
                    onClicked: section.hub.run(modelData.id)
                }
            }
            Repeater {      // the untitled actions: small buttons
                model: run.icons || run.folded ? [] : run.modelData.items
                delegate: Button {
                    required property var modelData
                    objectName: "action:" + modelData.id
                    implicitHeight: section.size; text: modelData.label; tip: modelData.label
                    help: modelData.keys ? modelData.label + " (" + modelData.keys + ")" : ""
                    onClicked: section.hub.run(modelData.id)
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
    IconButton {    // "⋯", the same icon button as the context bar's: the word More is the Song panel's fold of fields
        id: moreButton
        objectName: "actionsMore"
        visible: section.more.length > 0
        width: section.size; height: section.size
        kind: "ghost"; glyph: "⋯"; tip: "More"; help: "The other actions for this selection"
        onClicked: section.openMenu(moreButton, section.more)
    }
    ActionMenu { id: menu; onPicked: (v) => section.hub.run(v) }
}
