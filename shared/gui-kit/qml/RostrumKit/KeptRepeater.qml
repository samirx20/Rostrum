import QtQuick

// A Repeater that keeps its delegates: its model is how many it has made so far, never fewer, and `needed` is how many
// show now. A Repeater remakes every delegate whenever its model changes (a new list, or a new count), so a list whose
// length follows the selection (its actions, a kind's folded groups) remade all its buttons and their tips on every
// pick; this one shows or hides the ones it has, and makes only the ones it never had.
// Each delegate reads its data by index and hides past `needed`: `visible: index < <this>.needed` (a positioner leaves
// a hidden item out).
Repeater {
    property int needed: 0
    property int made: 0
    onNeededChanged: if (needed > made) made = needed
    Component.onCompleted: if (needed > made) made = needed
    model: made
}
