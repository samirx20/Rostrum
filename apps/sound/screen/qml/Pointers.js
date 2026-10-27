.pragma library
// The pointer for each zone of Sound's canvases (CANVAS.md §4), by name. A local stand-in for the kit's pointer
// table (Team Hem's, PLAN K4): when it lands, only this file changes. Stock shapes for now; the name says what a
// press there does, so every canvas asks for "trim" or "fade", never for a Qt shape.
var shapes = {
    pick: Qt.OpenHandCursor,           // a body: press moves it
    moving: Qt.ClosedHandCursor,       // while a move runs
    copy: Qt.DragCopyCursor,           // Alt on a body: press copies it
    trim: Qt.SizeHorCursor,            // a left / right edge: length / trim
    stretch: Qt.SplitHCursor,          // Alt on a clip edge: stretches in time
    fade: Qt.SizeBDiagCursor,          // a clip's top corner: fade in / out (the badge says which)
    fadeOut: Qt.SizeFDiagCursor,
    level: Qt.SizeVerCursor,           // a clip's top edge / a velocity bar's top: level
    draw: Qt.CrossCursor,              // empty space with Draw: a click makes what the ghost shows
    erase: Qt.ForbiddenCursor,         // over a note or hit that a click removes (it lights red)
    point: Qt.PointingHandCursor       // a plain button-like target
}
function of(name) { return shapes[name] !== undefined ? shapes[name] : Qt.ArrowCursor }
