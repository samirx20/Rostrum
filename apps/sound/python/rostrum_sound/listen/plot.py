"""matplotlib, loaded only when a picture is drawn (the screen and the MCP server start without it), off-screen."""


def pyplot():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    return plt
