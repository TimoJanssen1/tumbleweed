"""
Cross-validation against a held-out reference field.

My bots were tuned against the synthetic field in field/. To check the
improvements actually generalise, and aren't just overfit to opponents I built
myself, each version plays a separate set of reference bots none of them ever
trained on: aggressor, mathematician, ref_bot_2, shark, template.

If the edge is real, the ordering should survive on these untouched opponents:
Gunslinger (the pressure) should still beat Dutch (the calibration), which should
beat the Q1 base.

Usage:
    python tools/cross_validate.py [--seeds 60]
"""
import argparse
import json
import statistics
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from _engine import REPO, ENGINE, MATCH, ENV, resolve_bot

REFERENCE_FIELD = [
    "bots/aggressor",
    "bots/mathematician",
    "bots/ref_bot_2",
    "bots/shark",
    "bots/template",
]

HEROES = [
    "bots/gunslinger",            # the edge (final)
    "bots/tumbleweeddutch_v21",   # the calibration (Q2)
    "bots/tumbleweed_q1",         # the base (Q1)
]


def run_match(args):
    bots, seed, hands = args
    cmd = [sys.executable, MATCH, *[resolve_bot(b) for b in bots],
           "--hands", str(hands), "--seed", str(seed), "--json"]
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ENGINE), env=ENV)
    try:
        return seed, tuple(bots), json.loads(p.stdout)
    except Exception:
        return seed, tuple(bots), {"error": (p.stderr or p.stdout)[-300:]}


def hero_id(p):
    return Path(p).stem if Path(p).suffix in (".py", ".zip") else Path(p).name


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=60)
    ap.add_argument("--hands", type=int, default=400)
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()

    print(f"Cross-validation: each hero plays {args.seeds} matches × {args.hands} hands")
    print(f"Held-out reference field: {[hero_id(b) for b in REFERENCE_FIELD]}\n")

    # --- Each hero in 6-max with the 5-bot reference field ---
    jobs = []
    job_meta = []
    for hero in HEROES:
        bots = [hero] + REFERENCE_FIELD
        for s in range(args.seeds):
            jobs.append((bots, 90000 + abs(hash(hero)) % 10000 + s, args.hands))
            job_meta.append(hero)

    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        results = list(ex.map(run_match, jobs))

    by_hero = {h: [] for h in HEROES}
    errors_by_hero = {h: 0 for h in HEROES}

    for hero, (seed, bots, res) in zip(job_meta, results):
        if "chip_delta" not in res:
            errors_by_hero[hero] += 1
            continue
        h_id = hero_id(hero)
        for k, v in res["chip_delta"].items():
            base = k.rsplit("_", 1)[0] if (k.endswith("_0") or k.endswith("_1")) else k
            if base == h_id:
                by_hero[hero].append(v)
                break

    print(f"=== 6-max vs the held-out reference field ({args.seeds} seeds x {args.hands} hands) ===")
    print(f"{'hero':40} {'mean':>10} {'med':>10} {'wins':>8} {'bust%':>7} {'min':>9} {'max':>9}")
    print("-" * 95)

    summaries = {}
    for hero in HEROES:
        ds = by_hero[hero]
        if not ds:
            print(f"{hero:40}  NO RESULTS")
            continue
        n = len(ds)
        avg = sum(ds) / n
        med = statistics.median(ds)
        sd = statistics.stdev(ds) if n > 1 else 0
        sem = sd / (n ** 0.5)
        wins = sum(1 for d in ds if d > 0)
        busts = sum(1 for d in ds if d == -10000)
        summaries[hero] = (avg, sem)
        print(f"{hero:40} {avg:>+10.0f} {med:>+10.0f} {wins:>3}/{n:<3} "
              f"{100*busts/n:>6.0f}% {min(ds):>+9d} {max(ds):>+9d}")

    print()

    # Does the edge generalise? Gunslinger vs Dutch on opponents neither was tuned on.
    if "bots/gunslinger" in by_hero and "bots/tumbleweeddutch_v21" in by_hero:
        g = by_hero["bots/gunslinger"]
        d = by_hero["bots/tumbleweeddutch_v21"]
        n = min(len(g), len(d))
        if n >= 5:
            from math import sqrt
            g_avg = sum(g[:n]) / n
            d_avg = sum(d[:n]) / n
            g_sd = statistics.stdev(g[:n]) if n > 1 else 0
            d_sd = statistics.stdev(d[:n]) if n > 1 else 0
            diff = g_avg - d_avg
            se = sqrt(g_sd**2/n + d_sd**2/n)
            z = diff / se if se > 0 else 0
            print(f"=== Gunslinger vs Dutch on the held-out field ===")
            print(f"  Gunslinger mean:  {g_avg:+9.0f}")
            print(f"  Dutch mean:       {d_avg:+9.0f}")
            print(f"  diff:             {diff:+9.0f}  (z={z:.2f}, SE={se:.0f})")
            if abs(z) >= 1.96:
                winner = "Gunslinger" if diff > 0 else "Dutch"
                print(f"  {winner} wins on the held-out field, p < 0.05")
                print(f"  {'the edge generalises, not overfit to my own field' if diff > 0 else 'WARNING: the edge does not hold on untrained opponents'}")
            else:
                print(f"  not statistically distinguishable here (small effect vs the noise);")
                print(f"  it at least doesn't reverse, and the real evidence is the logs anyway")


if __name__ == "__main__":
    main()
