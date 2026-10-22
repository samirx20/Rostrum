import QtQuick
import QtQuick.Layouts
import RostrumKit

// A strip's mute / solo pair (a letter button each, lit while on). `compact`: the small pair beside the name in a low dock.
RowLayout {
    id: r
    required property var strip
    property bool compact: false
    spacing: Theme.grid
    MixSwitch { Layout.fillWidth: true; compact: r.compact; text: "M"; on: r.strip.model.mute; tint: Theme.warn
                onToggled: (v) => { r.strip.pick(); backend.setValue("mute", v) } }
    MixSwitch { Layout.fillWidth: true; compact: r.compact; visible: r.strip.model.canSolo; text: "S"; on: r.strip.model.solo; tint: Theme.accent
                onToggled: (v) => { r.strip.pick(); backend.setValue("solo", v) } }
}
