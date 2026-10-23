import QtQuick
import RostrumKit
import "MixFormat.js" as F

// A thin level bar under a track's header: the track's live level while the song plays, drawn by the Mixer's own
// meter (MixMeter: the same engine levels, scale, colours, held peak and fall), laid on its side. Stopped, it falls
// to an empty well.
Item {
    id: m
    property string trackId
    height: 3
    MixMeter { anchors.centerIn: parent; width: parent.height; height: parent.width; rotation: 90; live: mixer.live[m.trackId] || null }
}
