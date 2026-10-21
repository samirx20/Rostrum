"""Shared layout for the canal painting: one vanishing point, wall planes, colour mixing.

Plain numbers only (no pixels): every script paints through `doc`.
"""
VP = (1000, 600)          # eye level / vanishing point
W, H = 1920, 1080


def right_y(y_near, x):
    """y on the right wall plane at screen x, for a line that sits at y_near at x=1920."""
    return VP[1] + (y_near - VP[1]) * (x - VP[0]) / (W - VP[0])


def left_y(y_near, x):
    """y on the left wall plane at screen x, for a line that sits at y_near at x=0."""
    return VP[1] + (y_near - VP[1]) * (VP[0] - x) / VP[0]


def mix(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


# palette of the place (one time of day: last glow after sunset)
SKY_TOP = (0.12, 0.17, 0.30)
SKY_MID = (0.36, 0.38, 0.55)
SKY_GLOW = (0.98, 0.66, 0.40)
SKY_HOT = (1.00, 0.84, 0.58)
WALL_L = (0.17, 0.17, 0.24)
WALL_R = (0.22, 0.20, 0.27)
FAR = (0.50, 0.42, 0.52)
BRIDGE = (0.20, 0.17, 0.22)
WATER = (0.16, 0.19, 0.27)
LAMP = (1.00, 0.72, 0.36)
