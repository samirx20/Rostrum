"""A stand-in for `rostrum3d-core serve`: JSON lines in, JSON lines out. camera "nocam" is refused; frame 7 kills the process."""
import base64
import json
import sys

PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4z8DwHwAFAAH/q842iQAAAABJRU5ErkJggg==")

for line in sys.stdin:
    name, req = next(iter(json.loads(line).items()))
    if name == "render" and req["camera"] == "nocam":
        out = {"ok": False, "error": 'render: no camera "nocam". Accepted: cam'}
    elif name == "render" and req["frame"] == 7:
        sys.exit(3)
    elif name == "render":
        open(req["png"], "wb").write(PNG)
        out = {"ok": True, "frames": [{"frame": req["frame"], "png": req["png"], "ms": 5}], "renderer": req["renderer"], "timing": {}}
    else:
        out = {"ok": True}
    print(json.dumps(out), flush=True)
