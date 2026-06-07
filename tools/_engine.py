"""Locate the external fullhouse-engine so the benchmark tools can find the
dealer (sandbox/match.py), its analysis/* modules, and the field bots.

The engine isn't part of this repo (it's the competition's harness). It's found
via $FULLHOUSE_ENGINE, or failing that a sibling folder ../fullhouse-engine.
Importing this puts both the repo and the engine on sys.path.
"""
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ENGINE = Path(os.environ.get("FULLHOUSE_ENGINE", REPO.parent / "fullhouse-engine"))
MATCH = str(ENGINE / "sandbox" / "match.py")

for _p in (str(REPO), str(ENGINE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# environment for match.py subprocesses: engine on PYTHONPATH so its imports resolve
ENV = {**os.environ, "PYTHONPATH": os.pathsep.join(
    p for p in (str(ENGINE), os.environ.get("PYTHONPATH", "")) if p)}


def resolve_bot(path):
    """Make a bot path absolute so cwd doesn't matter. My own bots (bots/…) live
    in this repo; the field opponents (bots/field/…) live in the engine. Try this
    repo first, then the engine; fall back to the raw string so match.py reports a
    clear error if neither has it."""
    s = str(path)
    for base in (REPO, ENGINE):
        if (base / s).exists():
            return str(base / s)
    return s
