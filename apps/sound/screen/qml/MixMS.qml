import QtQuick
import QtQuick.Layouts
import RostrumKit

// A strip's M S R row: mute (amber when on), solo (green, tracks only) and record arm (red, tracks only), the same
// colours as the arrangement's track header. Arming is the recorder's screen state (recorder.arm), not an edit.
RowLayout {
    id: r
    required property var strip
    readonly property var m: strip.model
    spacing: Theme.grid
    MixSwitch { Layout.fillWidth: true; visible: r.m.canMute; text: "M"; on: r.m.mute; tint: Theme.warn; tip: "Mute"
                onToggled: { r.strip.pick(); backend.toggleTrack(r.m.id, "mute") } }
    MixSwitch { Layout.fillWidth: true; visible: r.m.canSolo; text: "S"; on: r.m.solo; tint: Theme.ok; tip: "Solo"
                onToggled: { r.strip.pick(); backend.toggleTrack(r.m.id, "solo") } }
    MixSwitch { Layout.fillWidth: true; visible: r.m.canArm; text: "R"; on: recorder.armed === r.m.id; tint: Theme.danger
                tip: on ? "Armed: press Record (R) to record on this track. Click to disarm." : "Arm this track for recording"
                onToggled: recorder.arm(r.m.id) }
}
