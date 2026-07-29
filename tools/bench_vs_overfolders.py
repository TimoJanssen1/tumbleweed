"""A/B Gunslinger vs Dutch against the five calibrated over-folders, same seeds
(CRN). The point: the realistic sim field doesn't over-fold, so it structurally
can't reward the preflop pressure. These bots do, so this is where the pressure
should show up as chips if it's worth anything.

    python tk.py overfolders [--seeds 80] [--hands 300] [--seed-base 91000]
"""
import argparse, json, statistics, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from math import sqrt, erf
from pathlib import Path

from _engine import MATCH, ENGINE, ENV, resolve_bot

OPPS = [f"field/overfolders/of{i}" for i in range(1, 6)]
HEROES = {"Gunslinger": "bots/gunslinger", "Dutch": "bots/tumbleweeddutch_v21"}


def run(job):
    hero_key, hero_path, seed, hands = job
    cmd = [sys.executable, MATCH, *[resolve_bot(b) for b in [hero_path, *OPPS]],
           "--hands", str(hands), "--seed", str(seed), "--json"]
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ENGINE), env=ENV)
    try:
        cd = json.loads(p.stdout)["chip_delta"]
        hid = Path(hero_path).name            # match.py keys chip_delta by bot dir name
        val = next((cd[k] for k in cd if k == hid or k.startswith(hid + "_")), None)
        return hero_key, seed, val
    except Exception:
        return hero_key, seed, None


def stats(xs):
    if not xs:
        return 0, 0, 0, 0
    m = statistics.mean(xs); sd = statistics.pstdev(xs)
    return m, sd, sum(1 for x in xs if x == 50000), sum(1 for x in xs if x == -10000)


def paired(by, a, b):
    common = sorted(set(by[a]) & set(by[b]))
    diffs = [by[a][s] - by[b][s] for s in common]
    if not diffs:
        return 0, 0, 0, 1.0, 0
    m = statistics.mean(diffs); sd = statistics.pstdev(diffs)
    se = sd / sqrt(len(diffs)) if diffs else 0
    z = m / se if se else 0
    p = 2 * (1 - 0.5 * (1 + erf(abs(z) / sqrt(2))))
    return m, 1.96 * se, z, p, len(diffs)


def main():
    ap = argparse.ArgumentParser(description=__doc__.strip().split("\n")[0])
    ap.add_argument("--seeds", type=int, default=80)
    ap.add_argument("--hands", type=int, default=300)
    ap.add_argument("--seed-base", type=int, default=91000)
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()

    jobs = [(hk, hp, args.seed_base + s, args.hands)
            for s in range(args.seeds) for hk, hp in HEROES.items()]
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        res = list(ex.map(run, jobs))

    by = {k: {} for k in HEROES}
    for hk, seed, cd in res:
        if cd is not None:
            by[hk][seed] = cd

    print(f"=== vs 5 calibrated over-folders ({args.seeds} seeds x {args.hands}h, CRN) ===")
    for hk in HEROES:
        xs = list(by[hk].values())
        m, sd, sc, bu = stats(xs)
        n = max(1, len(xs))
        print(f"  {hk:<11}: mean {m:+8.0f}  scoop {sc:>2}/{len(xs)} ({100*sc/n:.0f}%)  "
              f"bust {bu:>2} ({100*bu/n:.0f}%)  sd {sd:.0f}")

    m, ci, z, p, n = paired(by, "Gunslinger", "Dutch")
    flag = "  <-- SIGNIFICANT" if p < 0.05 else ""
    print(f"  paired Gunslinger-Dutch: {m:+8.0f} +/- {ci:.0f}  z={z:+.2f} p={p:.3f} (n={n}){flag}")


if __name__ == "__main__":
    main()
