#!/usr/bin/env python
"""
tk — the Tumble-Weed test kit. One front door for the benchmark suite, because
the tools underneath grew one question at a time and nobody should have to
remember all their names.

    python tk.py <command> [args...]
    python tk.py compare bots/gunslinger bots/tumbleweeddutch_v21 --crn --survivor --seeds 300
    python tk.py audit   bots/gunslinger --survivor --seeds 80
    python tk.py --help

Everything except `make-figures` runs against the competition harness
(fullhouse-engine) — clone it alongside this folder. `--help` after any command
forwards to that tool's own options.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# command -> (script path relative to here, one-line description)
COMMANDS = {
    "compare":     ("tools/compare_bots.py",          "CRN paired A/B between two bots"),
    "audit":       ("tools/audit_bot.py",             "behavioural fingerprint of one bot (3-bet%, c-bet%, AF, busts)"),
    "tournament":  ("tools/tournament_sim.py",        "full Swiss-tournament simulation"),
    "crossval":    ("tools/cross_validate.py",         "does an edge generalise to a held-out field?"),
    "overfolders": ("tools/bench_vs_overfolders.py",   "A/B a bot against the calibrated over-folders"),
    "field":       ("field/generate.py",               "(re)generate the synthetic opponent field"),
    "profile":     ("tools/read_logs/field_profile.py","measure the field's fold rates from real match logs"),
    "results":     ("tools/read_logs/my_results.py",   "my chip-Δ by opponent strength, from real match logs"),
    "make-figures":("figures/make_figures.py",         "redraw the README charts (needs only matplotlib)"),
}


def usage():
    print(__doc__.strip().split("\n\n")[0])
    print("\ncommands:")
    for name, (_, desc) in COMMANDS.items():
        print(f"  {name:<13} {desc}")
    print("\n  python tk.py <command> --help    # that tool's own flags")


def main(argv):
    if not argv or argv[0] in ("-h", "--help", "help"):
        usage()
        return 0
    cmd, rest = argv[0], argv[1:]
    if cmd not in COMMANDS:
        print(f"tk: unknown command '{cmd}'\n")
        usage()
        return 2
    script = os.path.join(HERE, COMMANDS[cmd][0])
    return subprocess.call([sys.executable, script] + rest)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
