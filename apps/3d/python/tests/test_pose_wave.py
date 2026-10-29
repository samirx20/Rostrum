"""rostrum3d/pose_wave.py and the pose solve's optional clear= (an arm kept off the head only when asked) (gaps7 Hello: judges saw "no wave" when a swing keyed
on the half second showed the same pose in every still one second apart, and a raised arm against the head read as
melted into it); silent on the guide's wave."""
from rostrum_core import Document

from rostrum3d import KIND, ops_pose, run_source
from rostrum3d.compile import shot_info
from rostrum3d.faults import doc_faults

from test_pose import _capsule, _grid, _smin
from test_script_figure import SHAPE, _figure_grid

GUIDE = '''c = clay("buddy", radius=0.07)
c.lump((0, 0.195, 0), 0.055, name="head")
c.lump((0.055, 0.12, 0), 0.02, to=(0.19, 0.06, 0), name="arm")
shot("s", camera=camera("cam", z=0.9, y=0.13), fps=24, start=0, end=4)
'''


def _guide_figure(P):
    d = _capsule(P, [0, .07, 0], [0, .07, 0], .07)
    d = _smin(d, _capsule(P, [0, .195, 0], [0, .195, 0], .055), .0275)
    for s in (1, -1):
        d = _smin(d, _capsule(P, [s * .055, .12, 0], [s * .19, .06, 0], .02), .01)
    return d


def _wave(deg, every):
    keys = ", ".join(f"{0.4 + i * every:.2f}: (0, 0, {deg if i % 2 else -deg})" for i in range(int(5.0 / every) + 1))
    return 'c.bend("arm.R", {0: (0, 0, -60), 6: (0, 0, -60)})\nc.bend("forearm.R", {0: (0, 0, 0), ' + keys + '})\n'


def _found(lines: str) -> dict:
    ops_pose.use_grid(lambda doc, id_, cells: _figure_grid(cells))
    try:
        doc = Document.new(KIND)
        doc.run_script("f.py", run_source(SHAPE + 'shot("s", camera=camera("cam", z=0.9, y=0.15), fps=24, start=0, end=6)\n'
                                          + lines, "f.py"))
    finally:
        ops_pose.use_grid(None)
    return {f["id"]: f for f in doc_faults(doc.data, shot_info(doc.data, "s"))}


def _waves(found):
    return {k: v for k, v in found.items() if k.split(":")[0] in ("wave_small", "wave_in_step", "reads_still")}


def test_a_swing_on_the_half_second_is_in_step_a_small_one_is_small_and_a_0_35_s_one_reads():
    step = _waves(_found(_wave(36, 0.5)))
    assert list(step) == ["wave_in_step:buddy.forearm.R"] and "every 1.00 s" in step["wave_in_step:buddy.forearm.R"]["what"], step
    small = _waves(_found(_wave(10, 0.35)))
    assert list(small) == ["wave_small:buddy.forearm.R"] and "° more" in small["wave_small:buddy.forearm.R"]["fix"], small
    assert not _waves(_found(_wave(36, 0.35)))


def _guide(wave: str):
    ops_pose.use_grid(lambda doc, id_, cells: _grid(_guide_figure, lo=(-.23, -.005, -.08), hi=(.23, .26, .08), cells=cells))
    try:
        tree = run_source(GUIDE + wave, "f.py")
        doc = Document.new(KIND)
        doc.run_script("f.py", tree)
    finally:
        ops_pose.use_grid(None)
    return tree.notes, {f["id"]: f for f in doc_faults(doc.data, shot_info(doc.data, "s"))}


def test_the_guides_wave_reads_and_clear_keeps_a_hand_over_the_head_off_it_only_when_asked():
    notes, found = _guide('''for i in range(8):
    c.pose(0.8 + 0.35 * i, **{"picture-right hand": {"up": 0.17, "out": -0.11, "forward": 0.06} if i % 2 == 0
                              else {"up": 0.12, "out": 0, "forward": 0.06}})
''')
    assert not notes and not _waves(found), (notes, found)
    over = '''for i in range(4):
    c.pose(0.8 + 0.35 * i, **{"picture-right hand": {"up": 0.22, "out": -0.15, "forward": 0.03} if i % 2 == 0
                              else {"up": 0.17, "out": 0, "forward": 0.03}}CLEAR)
'''
    notes, _ = _guide(over.replace("CLEAR", ""))
    assert not notes, notes                                 # never corrected by default: the pose is what the script says
    notes, found = _guide(over.replace("CLEAR", ", clear=0.015"))
    assert notes and all("clear of the head (turned" in n for n in notes), notes
    assert not [k for k in found if k.startswith("through_body:") and "head" in found[k]["what"]], found
