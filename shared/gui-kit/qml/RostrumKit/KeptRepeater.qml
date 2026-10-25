import QtQuick

// A Repeater that keeps its delegates: its model is how many it has made so far, never fewer, and `needed` is how many
// show now. A Repeater remakes every delegate whenever its model changes (a new list, or a new count), so a list whose
// length follows the selection (its actions, a kind's folded groups) remade all its buttons and their tips on every
// pick; this one shows or hides the ones it has, and makes only the ones it never had.
// The made ones are rows of a list model that only grows (a row added makes one delegate): a plain count as the model
// remade every delegate each time it grew (a drawing's cells: each New remade all of them, slower with every drawing).
// Each delegate reads its data by index and hides past `needed`: `visible: index < <this>.needed` (a positioner leaves
// a hidden item out).
Repeater {
    id: kept
    property int needed: 0
    readonly property int made: slots.count
    function grow() { while (slots.count < needed) slots.append({}) }
    onNeededChanged: grow()
    Component.onCompleted: grow()
    model: ListModel { id: slots }
}
