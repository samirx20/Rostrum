pragma Singleton
import QtQuick

// How many times a panel has been scrolled by the wheel (WheelScroll bumps it). A number box or a slider that takes the
// wheel itself notes the count when it gets the keyboard and gives the wheel back to the panel once the count has moved:
// the panel scrolled it under the pointer, so the next notch is for the panel, not for the value under it.
QtObject {
    property int moves: 0
}
