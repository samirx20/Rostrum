import QtQuick
import RostrumKit

// A track's sends and ducks, one block: the reverb send, the group sends, "+ Send", its ducks and "+ Duck". On the
// strip in a tall dock; in a low one the same block opens from the strip's "Sends" button (MixStrip).
Column {
    id: r
    required property var strip
    readonly property var m: strip.model
    spacing: 2
    MixSends { width: r.width; ownerId: r.m.id; sends: r.m.sends; targets: r.m.sendTargets
               reverb: r.m.reverb === undefined ? null : r.m.reverb; onPick: r.strip.pick() }
    MixDucks { width: r.width; ownerId: r.m.id; ducks: r.m.ducks; targets: r.m.duckTargets }
}
