import QtQuick
import RostrumKit
import "MixFormat.js" as F

// A thin level bar under a track's header: the track's peak in the last render, drawn by the Mixer's own meter
// (MixMeter: the same scale and colours), laid on its side. Absent until a render has measured the track.
Item {
    id: m
    property string trackId
    readonly property var peak: {
        var ts = (backend.lastRender || {}).tracks || []
        for (var i = 0; i < ts.length; i++)
            if (ts[i].id === trackId && ts[i].peak > 0) return Math.round(F.dbOf(ts[i].peak) * 10) / 10
        return null
    }
    height: 3
    MixMeter { anchors.centerIn: parent; width: parent.height; height: parent.width; rotation: 90; peak: m.peak }
}
