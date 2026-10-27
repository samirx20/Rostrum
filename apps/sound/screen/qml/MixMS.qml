import QtQuick
import QtQuick.Layouts
import RostrumKit

// A strip's R M S row, in the arrangement header's order and colours: record arm (red, tracks only), mute (amber when
// on), solo (green, tracks only). Each keeps its place when absent (a group has no R), so the letters line up across
// the strips as they do down the arrangement's rows. Arming is the recorder's screen state (recorder.arm), not an edit.
RowLayout {
    id: r
    required property var strip
    readonly property var m: strip.model
    spacing: Theme.grid
    Item { Layout.fillWidth: true; Layout.preferredWidth: 1; implicitHeight: 22
        MixSwitch { objectName: "mixArm:" + r.m.id; anchors.fill: parent; visible: r.m.canArm; text: "R"; on: recorder.armed === r.m.id; tint: Theme.danger
                    tip: on ? "Armed: press Record (R) to record on this track. Click to disarm." : "Arm this track for recording"
                    onToggled: recorder.arm(r.m.id) } }
    Item { Layout.fillWidth: true; Layout.preferredWidth: 1; implicitHeight: 22
        MixSwitch { objectName: "mixMute:" + r.m.id; anchors.fill: parent; visible: r.m.canMute; text: "M"; on: r.m.mute; tint: Theme.warn; tip: "Mute"
                    onToggled: { r.strip.pick(); backend.toggleTrack(r.m.id, "mute") } } }
    Item { Layout.fillWidth: true; Layout.preferredWidth: 1; implicitHeight: 22
        MixSwitch { objectName: "mixSolo:" + r.m.id; anchors.fill: parent; visible: r.m.canSolo; text: "S"; on: r.m.solo; tint: Theme.ok; tip: "Solo"
                    onToggled: { r.strip.pick(); backend.toggleTrack(r.m.id, "solo") } } }
}
