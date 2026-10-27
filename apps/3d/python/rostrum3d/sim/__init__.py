"""Rigid-body simulation (brief 25, SPEC §10): items that Fall or Stay still, computed once by the core (Jolt) into the
shared cache (kind "sim") and read back when the scene is compiled.

    fields.py   the Simulation fields (items and shots)
    inputs.py   the bodies, the core's `simulate` request and the result's key
    result.py   reading a stored result: bodies.bin, turns, Timing and Simplify
    state.py    stored / out of date / not computed, in words for the timeline row
    compute.py  computing (its own engine process) and `ready`, the render paths' "compute first"
    overlay.py  the stored result laid over a compiled scene (compile.describe's `sim`)
    ops.py      sim.body, sim.set, sim.run, sim.status, sim.to_keys

This file imports nothing: the fields table (item_fields.py) reads sim.fields while compile.py is still loading.
"""
