import QtQuick
import RostrumKit

// M and S on a group's header: mute the group (bus.set mute), or solo every track in it (track.set solo), the way the
// same two buttons act on one track. Lit when on; "S" is lit when all the group's tracks are soloed.
Row {
    id: r
    property var track
    spacing: 2
    HeaderButton { letter: "M"; lit: !!r.track.mute; litColor: Theme.warn; tip: "Mute the whole group"
                   onClicked: backend.toggleGroupMS(r.track.id, "mute") }
    HeaderButton { letter: "S"; lit: !!r.track.solo; litColor: Theme.ok; tip: "Solo every track in the group"
                   onClicked: backend.toggleGroupMS(r.track.id, "solo") }
}
