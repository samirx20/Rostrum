"""Plain Python in every app's script (rostrum_core/script_python.py): imports, classes, all built-ins, print back,
a seeded random, no stdin, exit() keeps what was made."""
import pytest

from rostrum_core import script_python as SP
from rostrum_core.seeded import SeededRandom


def run(src, name="s.py", limit=SP.PRINT_LIMIT):
    lines, scope = [], SP.globals_for(name)
    with SP.running(lines, name, limit) as ran:
        exec(compile(src, name, "exec"), scope)
    return scope, lines, ran


def test_imports_classes_and_builtins():
    scope, lines, _ = run("import itertools, json\nfrom dataclasses import dataclass\n@dataclass\nclass P:\n    x: int\n"
                          "    def twice(self):\n        return self.x * 2\nout = (P(3).twice(), hasattr(P, 'twice'), "
                          "json.dumps(list(itertools.repeat(1, 2))), type(3).__name__, getattr(P(1), 'x'))\n")
    assert scope["out"] == (6, True, "[1, 1]", "int", 1)


def test_numpy_from_the_venv():
    pytest.importorskip("numpy")
    scope, *_ = run("import numpy as np\nm = float(np.mean([1, 2, 3]))")
    assert scope["m"] == 2.0


def test_random_is_seeded_and_is_pythons_own():
    src = "import random\nfrom random import Random, choice\na = random.random()\nb = random.Random(7).random()\nc = Random(7).random()\nd = choice([1, 2, 3])"
    one, two = run(src)[0], run(src)[0]
    assert (one["a"], one["d"]) == (two["a"], two["d"]) == (SeededRandom(1).random(), one["d"])
    assert one["b"] == one["c"]
    assert isinstance(one["random"], SeededRandom)


def test_print_and_stdout_come_back_capped():
    _, lines, _ = run("import sys\nprint('a', 1)\nprint('b', end='')\nprint('c')\nsys.stdout.write('d' + chr(10))\nprint('tail', end='')")
    assert lines == ["a 1", "bc", "d", "tail"]
    _, lines, _ = run("for i in range(10):\n    print(i)", limit=3)
    assert lines == ["0", "1", "2", "… (more print lines left out)"]


def test_no_typed_input_and_stdin_is_empty():
    with pytest.raises(RuntimeError, match="can't ask for typed input"):
        run("input('name? ')")
    scope, *_ = run("import sys\ngot = sys.stdin.read()")
    assert scope["got"] == ""


def test_exit_ends_the_script_and_keeps_what_was_made():
    scope, _, ran = run("made = 1\nimport sys\nsys.exit()\nmade = 2")
    assert scope["made"] == 1 and ran.exited == "line 3"
    assert SP.exit_note(ran) == ["the script ended at exit() on line 3; what it made before that is kept"]
    assert SP.exit_note(run("x = 1")[2]) == []


def test_errors_keep_the_script_line():
    with pytest.raises(ZeroDivisionError) as e:
        run("x = 1\ny = x / 0", name="mine.py")
    import traceback
    assert [fr.lineno for fr in traceback.extract_tb(e.value.__traceback__) if fr.filename == "mine.py"] == [2]
