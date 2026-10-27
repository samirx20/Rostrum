"""Lip sync… listening fails loudly (2D final critic row 4: the sheet sat at "Step 1 of 3" for minutes, no error): a
listening process that says nothing within the stall time is ended and the wait raises in plain words."""
import pytest

from rostrum_gui import listen_proc


def test_a_silent_listening_process_is_stopped_and_said(tmp_path):
    with pytest.raises(RuntimeError, match="stopped answering"):
        listen_proc.listen(tmp_path / "none.wav", None, lambda *a: None, stall=0.05)


def test_a_failing_listen_says_why(tmp_path):
    with pytest.raises(RuntimeError, match="No such file|is not a file"):
        listen_proc.listen(tmp_path / "none.wav", None, lambda *a: None, stall=60)
