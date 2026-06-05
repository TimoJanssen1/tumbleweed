"""
Cross-validation against the original reference bots.

The synthetic field in bots/field/ was MY construction. To check whether
champion is overfit to it (the same disease that bit phase_hunter on the
in-repo field), we test champion against ONLY the bots that came with
the repo: aggressor, mathematician, ref_bot_2, shark, template.

These bots are not in the synthetic field — they are an independent
out-of-distribution test set.

If champion still wins against them (and beats phase_hunter on the same
field), the pivot is genuine. If champion underperforms phase_hunter here,
champion is overfit to my synthetic field and we should reconsider.

Usage:
    python3 analysis/cross_validate.py [--seeds 60]
"""
import argparse
import json
import statistics
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

REFERENCE_FIELD = [
    "bots/aggressor",
    "bots/mathematician",
    "bots/ref_bot_2",
    "bots/shark",
    "bots/template",
]

HEROES = [
    "bots/tumbleweeddutch",                 # Q2 candidate (must generalize here)
    "bots/tumbleweed_mentor_v2",            # frozen baseline / fork source
    "bots/champion",
    "bots/phase_hunter",
    "bots/field/elite/opponent_modeler",   # the unaltered champion ancestor
]


def run_match(args):
    bots, seed, hands = args
    cmd = [sys.executable, "sandbox/match.py", *bots,
           "--hands", str(hands), "--seed", str(seed), "--json"]
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO))
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
    print(f"Field (unchanged from repo): {[hero_id(b) for b in REFERENCE_FIELD]}\n")

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

    print("=== 6-MAX VS REFERENCE FIELD (60 seeds × 400 hands) ===")
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

    # Paired test: champion vs phase_hunter on these same matches
    if "bots/champion" in by_hero and "bots/phase_hunter" in by_hero:
        c = by_hero["bots/champion"]
        ph = by_hero["bots/phase_hunter"]
        n = min(len(c), len(ph))
        if n >= 5:
            # Unpaired comparison since they use different seed bases
            from math import sqrt
            c_avg = sum(c[:n]) / n
            ph_avg = sum(ph[:n]) / n
            c_sd = statistics.stdev(c[:n]) if n > 1 else 0
            ph_sd = statistics.stdev(ph[:n]) if n > 1 else 0
            diff = c_avg - ph_avg
            se = sqrt(c_sd**2/n + ph_sd**2/n)
            z = diff / se if se > 0 else 0
            print(f"=== UNPAIRED DIFFERENCE: champion − phase_hunter on reference field ===")
            print(f"  champion mean:      {c_avg:+9.0f}")
            print(f"  phase_hunter mean:  {ph_avg:+9.0f}")
            print(f"  diff:               {diff:+9.0f}  (z={z:.2f}, SE={se:.0f})")
            print(f"  {'INTERPRETATION':30s}")
            if abs(z) >= 1.96:
                winner = "champion" if diff > 0 else "phase_hunter"
                print(f"    {winner} wins on reference field, p < 0.05")
                if diff > 0:
                    print(f"    Champion's improvement generalizes — not overfit.")
                else:
                    print(f"    WARNING: champion underperforms phase_hunter on reference field.")
                    print(f"    Possible overfit to synthetic field.")
            else:
                print(f"    not statistically distinguishable on reference field")
                print(f"    Champion at least doesn't LOSE — but improvement may be specific to synthetic field.")


if __name__ == "__main__":
    main()
