import QtQuick
import RostrumKit

// A track's buttons on its header, in four FIXED places (as on a desk, so you see at a glance what is armed, muted,
// soloed): R arms it for recording (screen state, not an edit; red when armed; absent where the track cannot record,
// its place stays so M S A line up down the rows), M mutes, S solos (each a track.set; lit when on), A opens its
// automation lane. Selection, hover and the row's height never move them: only their colour changes. (Lock is in the
// header's right-click menu and Ctrl+Shift+L; a locked track shows a small padlock by its name.)
// A click takes only the drawn square (HeaderButton); the 2 px between them and the gap before the name select the
// track. A mute or solo is never silent: the top bar's message line names it and how to take it back.
Row {
    id: r
    property var track
    property bool showAuto: true            // off while the arrangement is slim (its lanes cannot open there)
    readonly property real fullWidth: (showAuto ? 4 : 3) * 22 + (showAuto ? 3 : 2) * spacing    // all of them
    spacing: 2
    function toggle(field, was) {
        const name = r.track.name
        backend.toggleTrack(r.track.id, field)
        backend.say(field === "mute" ? (was ? name + " heard again" : name + " muted — click M again or Ctrl+Z")
                                     : (was ? name + ": solo off" : name + " soloed: only soloed tracks play — click S again or Ctrl+Z"))
    }
    Item {
        width: 22; height: 22
        HeaderButton {
            objectName: "arm_" + r.track.id
            visible: !!r.track.canRecord
            letter: "R"; lit: recorder.armed === r.track.id; litColor: Theme.danger
            tip: lit ? "Armed: press Record (R) to record on this track. Click to disarm."
                     : "Get this track ready to record: then press Record (R)"
            onClicked: recorder.arm(r.track.id)
        }
    }
    HeaderButton { objectName: "trackMute"; letter: "M"; lit: !!r.track.mute; litColor: Theme.warn; tip: lit ? "Muted: click to hear it again" : "Mute this track"
                   onClicked: r.toggle("mute", lit) }
    Item {
        width: 22; height: 22
        HeaderButton { objectName: "trackSolo"; visible: !!r.track.canSolo   // absent for an item that has no solo (a plugin's), its place stays
                       letter: "S"; lit: !!r.track.solo; litColor: Theme.ok; tip: lit ? "Soloed: click to hear every track" : "Solo: hear only this track (and other soloed ones)"
                       onClicked: r.toggle("solo", lit) }
    }
    LaneToggle { visible: r.showAuto && !!r.track.canLane; track: r.track }
}
