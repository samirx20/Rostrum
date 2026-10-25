pragma Singleton
import QtQuick

// How many SmallPopups are open now: while one is, the window's own Esc key (step back) waits, so Esc closes the popup.
QtObject { property int count: 0 }
