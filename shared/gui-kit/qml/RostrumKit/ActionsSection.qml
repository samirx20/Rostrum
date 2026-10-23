import QtQuick
import "."

// The selection's actions at the top of the settings panel (SPEC 2d-design-v2 §8.3, "actions first"): the app's one
// action list as `hub.panel` (rostrum_gui/action_views.panel) — only what this selection allows, in its order. Actions
// sharing a bar name are one titled row ("Combine": Union · Subtract · Intersect · Exclude); the rest one row first.
// On the settings grid: buttons across the wide row (Theme.wideFor), as many a line as the names fit (`cols`, up to
// four). The less used ones (secondary) are one "More" menu under them, folded like right-click.
// No hover preview yet: drawing a would-be result needs the engine to render one (left for later, said in H48).
Column {
    id: section
    property var hub: null
    readonly property var rows: hub ? hub.panel.rows : []
    readonly property var more: hub ? hub.panel.more : []
    readonly property real wide: Theme.wideFor(width)
    visible: rows.length + more.length > 0
    bottomPadding: visible ? Theme.gap : 0
    Repeater {
        model: section.rows
        delegate: Column {
            id: line
            required property var modelData
            width: section.width
            readonly property int cols: Math.max(1, modelData.cols)
            Text { visible: line.modelData.title !== ""; text: line.modelData.title; height: Theme.row
                   verticalAlignment: Text.AlignVCenter; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label }
            Item { width: 1; height: line.modelData.title === "" ? Theme.gap / 2 : 0 }
            Grid {
                columns: line.cols; spacing: 4
                readonly property real cell: Math.floor((section.wide - (line.cols - 1) * spacing) / line.cols)
                Repeater {
                    model: line.modelData.items
                    delegate: Button {
                        required property var modelData
                        objectName: "action:" + modelData.id
                        width: parent.cell; implicitHeight: Theme.button
                        text: modelData.label; tip: modelData.label
                        help: modelData.keys ? modelData.label + " (" + modelData.keys + ")" : ""
                        onClicked: section.hub.run(modelData.id)
                    }
                }
            }
            Item { width: 1; height: 4 }
        }
    }
    Button {
        id: moreButton
        objectName: "actionsMore"
        visible: section.more.length > 0
        kind: "ghost"; text: "More  ▾"; help: "The other actions for this selection"
        onClicked: { const g = moreButton.mapToItem(null, 0, moreButton.height); moreMenu.entries = section.more; moreMenu.openAt(g.x, g.y) }
    }
    ActionMenu { id: moreMenu; onPicked: (v) => section.hub.run(v) }
}
