import QtQuick
import RostrumKit

// Only in this shot (PR1, screen3d/bridge_shot_only.py): at the top of the settings, "Changes  All shots | Only <shot>".
// There only while the scene has two or more shots and what is selected can be changed per shot; else absent. On Only,
// every settings edit and gizmo drag changes the shown shot alone; a setting a shot holds its own value for carries a
// "This shot" tag and a "Use all shots" button on its row, whichever side the switch is on.
Item {
    id: root
    readonly property bool applies: backend.shotOnlyShown
    readonly property int labelW: Theme.labelColumnFor(width)
    readonly property string shotName: backend.shotOnlyName.length > 14 ? backend.shotOnlyName.slice(0, 13) + "…" : backend.shotOnlyName
    visible: applies
    width: parent ? parent.width : 0
    height: applies ? Theme.row + Theme.grid : 0

    Text { x: 0; height: Theme.row; verticalAlignment: Text.AlignVCenter; text: "Changes"
           color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body }
    Segmented {
        objectName: "shotOnlySwitch"
        x: root.labelW; y: (Theme.row - height) / 2
        options: [{ value: "all", label: "All shots" }, { value: "shot", label: "Only " + root.shotName }]
        current: backend.shotOnly ? "shot" : "all"
        onPicked: (v) => backend.setShotOnly(v === "shot")
    }
}
