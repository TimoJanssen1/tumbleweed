"""Smoke tests: every module imports, every advertised tk.py command starts.

This is the test that would have caught the broken import layer: every script
under tools/ and field/ is imported (so a stale `import x` fails loudly), every
bot module under bots/ and field/ is loaded the way the engine loads it, and
every command tk.py advertises answers `--help` with exit code 0 — without the
engine, without the match logs.
"""
import glob
import importlib
import importlib.util
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TK = os.path.join(ROOT, "tk.py")

# ---------------------------------------------------------------------------
# 1. Every script module imports (siblings resolve exactly as when run as a
#    script: with the file's own directory on sys.path).
# ---------------------------------------------------------------------------

SCRIPT_MODULES = sorted(
    glob.glob(os.path.join(ROOT, "tools", "*.py"))
    + glob.glob(os.path.join(ROOT, "tools", "read_logs", "*.py"))
    + [p for p in glob.glob(os.path.join(ROOT, "field", "*.py"))]
    + [os.path.join(ROOT, "figures", "make_figures.py")]
)


@pytest.mark.parametrize("path", SCRIPT_MODULES,
                         ids=[os.path.relpath(p, ROOT) for p in SCRIPT_MODULES])
def test_script_module_imports(path):
    parent = os.path.dirname(path)
    stem = os.path.splitext(os.path.basename(path))[0]
    sys.path.insert(0, parent)
    try:
        mod = importlib.import_module(stem)
        importlib.reload(mod)  # re-exec so a broken sibling import can't hide
    finally:
        sys.path.remove(parent)


# ---------------------------------------------------------------------------
# 2. Every bot module loads the way the engine loads it (standalone file).
# ---------------------------------------------------------------------------

BOT_FILES = sorted(
    glob.glob(os.path.join(ROOT, "bots", "*", "bot.py"))
    + glob.glob(os.path.join(ROOT, "field", "*", "*", "bot.py"))
)


@pytest.mark.parametrize("path", BOT_FILES,
                         ids=[os.path.relpath(p, ROOT) for p in BOT_FILES])
def test_bot_module_loads(path):
    spec = importlib.util.spec_from_file_location("smoke_bot", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert callable(getattr(mod, "decide", None)), f"{path}: no decide()"
    assert isinstance(getattr(mod, "BOT_NAME", None), str)


def test_full_field_size():
    """The README's field arithmetic: 26 generated + 4 elite + 5 over-folders,
    plus the 3 hero bots."""
    field_bots = [p for p in BOT_FILES if os.sep + "field" + os.sep in p]
    hero_bots = [p for p in BOT_FILES if os.sep + "bots" + os.sep in p]
    assert len(field_bots) == 35
    assert len(hero_bots) == 3


# ---------------------------------------------------------------------------
# 3. Every advertised tk.py command starts: `--help` answers with rc=0,
#    without the engine and without any match logs.
# ---------------------------------------------------------------------------

def _tk_commands():
    spec = importlib.util.spec_from_file_location("tk_smoke", TK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.COMMANDS


def _clean_env():
    env = {k: v for k, v in os.environ.items()
           if k not in ("Q1_MATCH_DIR", "Q2_MATCH_DIR", "FULLHOUSE_ENGINE")}
    # Point the engine somewhere that doesn't exist so --help can't silently
    # depend on a sibling clone being present.
    env["FULLHOUSE_ENGINE"] = os.path.join(ROOT, "no_such_engine")
    return env


def test_tk_command_scripts_exist():
    for name, (rel, _desc) in _tk_commands().items():
        assert os.path.isfile(os.path.join(ROOT, rel)), f"{name} -> {rel} missing"


@pytest.mark.parametrize("command", sorted(_tk_commands()))
def test_tk_help_forwards(command):
    p = subprocess.run([sys.executable, TK, command, "--help"],
                       capture_output=True, text=True, cwd=ROOT, env=_clean_env())
    assert p.returncode == 0, f"tk.py {command} --help rc={p.returncode}\n{p.stderr}"
    assert "usage" in (p.stdout + p.stderr).lower()


def test_tk_own_help():
    p = subprocess.run([sys.executable, TK, "--help"],
                       capture_output=True, text=True, cwd=ROOT, env=_clean_env())
    assert p.returncode == 0
    for name in _tk_commands():
        assert name in p.stdout, f"tk.py --help doesn't list {name}"


def test_tk_unknown_command():
    p = subprocess.run([sys.executable, TK, "definitely-not-a-command"],
                       capture_output=True, text=True, cwd=ROOT, env=_clean_env())
    assert p.returncode == 2


# ---------------------------------------------------------------------------
# 4. The log tools fail fast (and say why) when the logs aren't there.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("command,var", [("profile", "Q2_MATCH_DIR"),
                                         ("results", "Q2_MATCH_DIR"),
                                         ("q1-leaks", "Q1_MATCH_DIR")])
def test_log_tools_fail_fast_without_logs(command, var):
    p = subprocess.run([sys.executable, TK, command],
                       capture_output=True, text=True, cwd=ROOT, env=_clean_env())
    assert p.returncode != 0, f"tk.py {command} should fail without logs"
    assert var in p.stdout + p.stderr, f"error should name {var}"
