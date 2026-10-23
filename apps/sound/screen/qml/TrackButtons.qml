import QtQuick
import RostrumKit

// A track's buttons on its header, always there (as on a desk, so you see at a glance what is armed, muted, soloed):
// R arms it for recording (screen state, not an edit; red when armed), M mutes, S solos (each a track.set; lit when
// on), A opens its automation lane, and the lock (track.lock / track.unlock: nobody, agents included, can change it).
// In a short row too narrow for all five next to the name, R M S stay; A and the lock show when on or on hover.
Row {
    id: r
    property var track
    property bool showAuto: true            // off while the arrangement is slim (its lanes cannot open there)
    property bool compact: false            // a short, narrow row: R, A and the lock only when on, in use or under the mouse
    property bool hovered: false            // the pointer is on the row
    readonly property bool all: !compact || hovered
    readonly property real fullWidth: (showAuto ? 5 : 4) * 20 + (showAuto ? 4 : 3) * spacing    // all of them shown
    spacing: 2
    HeaderButton {
        letter: "R"; lit: recorder.armed === r.track.id; litColor: Theme.danger
        tip: lit ? "Armed: press Record (R) to record on this track. Click to disarm."
                 : "Get this track ready to record: then press Record (R)"
        onClicked: recorder.arm(r.track.id)
    }
    HeaderButton { letter: "M"; lit: !!r.track.mute; litColor: Theme.warn; tip: lit ? "Muted: click to hear it again" : "Mute this track"
                   onClicked: backend.toggleTrack(r.track.id, "mute") }
    HeaderButton { letter: "S"; lit: !!r.track.solo; litColor: Theme.ok; tip: lit ? "Soloed: click to hear every track" : "Solo: hear only this track (and other soloed ones)"
                   onClicked: backend.toggleTrack(r.track.id, "solo") }
    LaneToggle { visible: r.showAuto && (r.all || lit || dot); track: r.track }
    HeaderButton {   // the lock: a drawn padlock, lit when locked
        id: lock
        lit: !!r.track.locked; litColor: Theme.warn; visible: r.all || lit
        readonly property color ink: lit ? Theme.app : Theme.fg2
        tip: lit ? "Locked: nobody can change this track, agents included. Click to unlock (Ctrl+Shift+L)"
                 : "Lock this track: nobody can change it, agents included (Ctrl+Shift+L)"
        onClicked: backend.toggleLock(r.track.id)
        Rectangle { x: 7; y: 4; width: 6; height: 7; radius: 3; color: "transparent"; border.width: 1.5; border.color: lock.ink }
        Rectangle { x: 5; y: 8; width: 10; height: 7; radius: 1.5; color: lock.ink }
    }
}
