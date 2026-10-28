"""What an agent session relies on at start (rostrum_core/agent_start.py): with no --project the server never opens the
person's last project; a resumed session gets its own back; the first reply (and only the first) says what is open and whose."""
from pathlib import Path
from types import SimpleNamespace

from rostrum_core import Who, agent_last, agent_start, recent
from rostrum_core.mcp import App, Runtime, Tools, Reply
from rostrum_core.mcp.server import build_server

EXT = ".mtn"


def doc(folder, item="main"):
    f = folder / "docs" / f"{item}{EXT}"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("{}", encoding="utf-8")
    return str(folder)


import pytest


@pytest.fixture(autouse=True)
def no_session_id(monkeypatch):
    for v in agent_last.SESSION_VARS:          # the agent running these tests has its own session id
        monkeypatch.delenv(v, raising=False)


def choose(project=None):
    return agent_start.choose("rostrum-test", EXT, project, None, lambda folder, explicit: "main")


def test_no_options_never_opens_the_persons_last_project_and_a_resumed_session_gets_its_own(tmp_path, monkeypatch):
    monkeypatch.setenv("ROSTRUM_SCRIPTED_HOME", str(tmp_path / "home"))
    monkeypatch.chdir(tmp_path)
    person = doc(tmp_path / "person")
    recent.remember("2d", EXT, person, "main", "person")             # the person's Open recent has a project
    start = choose()
    assert start.whose == "scratch" and start.folder != person
    assert str(agent_start.scratch_root()) in start.folder and "not the person's work" in start.sentence()
    agent_last.remember("rostrum-test", doc(tmp_path / "mine"), "main")    # this session opened its own project
    again = choose()
    assert again.whose == "resumed" and again.folder == str((tmp_path / "mine").resolve())
    assert "your project from earlier in this session" in again.sentence()
    assert choose(person).whose == "asked"                                 # --project still opens what it names


def test_settle_saves_and_remembers_a_scratch_project_so_the_next_start_resumes_it(tmp_path, monkeypatch):
    monkeypatch.setenv("ROSTRUM_SCRIPTED_HOME", str(tmp_path / "home"))
    monkeypatch.chdir(tmp_path)
    start = choose()
    saved = []
    d = SimpleNamespace(kind=SimpleNamespace(ext=EXT), save=lambda: saved.append(doc(Path(start.folder))))
    app = SimpleNamespace(name="rostrum-test", folder=start.folder, documents={"main": d}, opened="")
    agent_start.settle(app, start)
    assert saved and app.opened == start.sentence()
    assert choose().folder == str(Path(start.folder).resolve())


def test_the_first_reply_and_the_instructions_say_what_is_open(tmp_path):
    tools = Tools()

    @tools.tool("inspect_thing", {})
    def inspect_thing(ctx, args):
        """A thing."""
        return Reply("Thing.")
    app = App("rostrum-test", {}, folder=str(tmp_path), opened="Open: a fresh scratch project made for you at X.")
    rt = Runtime(app, tools)
    first, _ = rt.call("inspect_thing", {}, Who.agent("t"))
    second, _ = rt.call("inspect_thing", {}, Who.agent("t"))
    assert first["summary"].startswith("Open: a fresh scratch project") and second["summary"] == "Thing."
    assert "Open: a fresh scratch project" in build_server(app, runtime=rt).instructions


def test_tidy_removes_only_old_scratch_projects_that_never_changed(tmp_path, monkeypatch):
    import time
    monkeypatch.setenv("ROSTRUM_AGENT_HOME", str(tmp_path / "agent"))
    made = []
    for session in ("one", "two"):                         # two sessions (working folders), so the second doesn't resume the first
        (tmp_path / session).mkdir()
        monkeypatch.chdir(tmp_path / session)
        start = choose()
        doc(Path(start.folder))
        agent_start.settle(SimpleNamespace(name="rostrum-test", folder=start.folder, documents={}, opened=""), start)
        made.append(Path(start.folder))
    untouched, changed = made
    (changed / "docs" / "main.mtn").write_text('{"x": 1}', encoding="utf-8")   # a change: kept forever
    agent_start.tidy(now=time.time() + 1000)                                   # too young: both stay
    assert untouched.is_dir() and changed.is_dir()
    agent_start.tidy(now=time.time() + agent_start.UNTOUCHED_S + 60)
    assert not untouched.exists() and changed.is_dir()


def test_another_agent_in_the_same_folder_never_gets_this_agents_project(tmp_path, monkeypatch):
    """Agent Hub starts every child agent in one worktree: the 2026-10-28 proof run was told an earlier agent's scratch
    project was 'your project from earlier in this session'. The record is per session, never per folder alone."""
    monkeypatch.setenv("ROSTRUM_SCRIPTED_HOME", str(tmp_path / "home"))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "agent-a")
    agent_last.remember("rostrum-test", doc(tmp_path / "a"), "main")
    assert choose().whose == "resumed"                                     # agent A, server started again: its own back
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "agent-b")
    assert choose().whose == "scratch"                                     # agent B, same folder: a fresh project
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID")
    monkeypatch.setattr("os.getppid", lambda: 999999)                      # no session id: another agent process
    assert choose().whose == "scratch"
