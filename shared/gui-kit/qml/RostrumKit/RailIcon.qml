import QtQuick
import "."

// One rail or flyout icon. An entry is drawn by the kit's ToolIcon (`entry.icon`), or, when it names a `kind`, by the
// app's component for that kind (ToolRail.iconKinds: kind -> Component of an Item with `name` and `ink`; 2D's shape
// and paint-tool icons). The component may ignore `name` (the paint icon follows the tool last used).
Loader {
    id: icon
    property var entry: null
    property var kinds: ({})
    property color ink: Theme.fg2
    sourceComponent: entry && entry.kind && kinds[entry.kind] ? kinds[entry.kind] : plain
    Component { id: plain; ToolIcon { } }
    Binding { target: icon.item; property: "name"; value: icon.entry ? icon.entry.icon : ""; when: !!icon.item }
    Binding { target: icon.item; property: "ink"; value: icon.ink; when: !!icon.item }
}
