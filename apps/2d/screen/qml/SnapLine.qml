import QtQuick

// A thin line showing what a drag snapped to (INTERACTION 1.11): the one place 2D's snap colour lives. The canvas's lines
// (Stage.qml) and the timeline's time-snap line (LayerTimeline.qml) are both this. (The colour belongs in the kit's
// Theme once Team Sam adds it there.)
Rectangle {
    color: "#ff2fd0"            // INTERACTION 1.11's snap magenta
}
