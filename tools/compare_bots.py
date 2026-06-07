"""
Paired statistical comparison of two heroes on the SAME sampled fields.

For each seed, samples the same 5 opponents (excluding both heroes) and
runs both heroes through that same field, allowing a paired-difference
test that's much more powerful than an independent-samples test.

Usage:
    python3 analysis/paired_compare.py <hero_a> <hero_b> [--seeds 200]
"""
import argparse
import json
import statistics
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor
from math import sqrt, erf
from pathlib import Path

from _engine import REPO, ENGINE, MATCH, ENV, resolve_bot

from analysis.field_registry import discover_field, sample_field_seeded, apply_survivor


def run_match(args):
    bots, seed, hands = args
    cmd = [sys.executable, MATCH, *[resolve_bot(b) for b in bots],
           "--hands", str(hands), "--seed", str(seed), "--json"]
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ENGINE), env=ENV)
    try:
        return seed, tuple(bots), json.loads(p.stdout)
    except Exception:
        return seed, tuple(bots), {"error": (p.stderr or p.stdout)[-400:]}


def hero_id(path: str) -> str:
    return Path(path).stem if Path(path).suffix in (".py", ".zip") else Path(path).name


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("hero_a")
    ap.add_argument("hero_b")
    ap.add_argument("--seeds", type=int, default=200)
    ap.add_argument("--hands", type=int, default=400)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--seed-base", type=int, default=80000)
    ap.add_argument("--exclude-tier", action="append", default=[],
                    help="exclude this tier from sampling (can repeat)")
    ap.add_argument("--survivor", action="store_true",
                    help="elite-heavy finalist field (elite/strong/mid ~40/40/20, "
                         "no weak/broken) — models the Q2 survivor field")
    ap.add_argument("--crn", action="store_true",
                    help="common random numbers: both heroes play the SAME cards "
                         "(paired on cards, not just opponents). Cancels card-luck "
                         "variance — far more powerful for detecting small edges.")
    args = ap.parse_args()

    a_id, b_id = hero_id(args.hero_a), hero_id(args.hero_b)

    # Sample SAME opponents for each seed (excluding BOTH heroes)
    field = discover_field()
    for tier in args.exclude_tier:
        field.pop(tier, None)
    weights = None
    if args.survivor:
        field, weights = apply_survivor(field)
    samples = []
    for s in range(args.seeds):
        seed = args.seed_base + s
        opps = sample_field_seeded(field, seed, n=5, weights=weights,
                                    exclude=[args.hero_a, args.hero_b])
        samples.append((seed, opps))

    # Build jobs: each seed × each hero
    jobs = []
    for seed, opps in samples:
        # --crn: B plays the SAME seed (=> same hole cards + board run-out as A),
        # so the paired diff isolates the DECISION difference and card-luck cancels
        # — a large variance reduction. Default: different cards for B.
        b_seed = seed if args.crn else seed + 1000000
        jobs.append(([args.hero_a] + opps, seed, args.hands))
        jobs.append(([args.hero_b] + opps, b_seed, args.hands))

    print(f"Paired comparison: {a_id} vs {b_id}")
    print(f"Running {len(jobs)} matches ({args.seeds} fields × 2 heroes)")

    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        results = list(ex.map(run_match, jobs))

    # Aggregate per seed
    a_by_seed, b_by_seed = {}, {}
    for seed, bots, res in results:
        if "chip_delta" not in res:
            continue
        base_seed = seed if seed < 1000000 else seed - 1000000
        for k, v in res["chip_delta"].items():
            base = k.rsplit("_", 1)[0] if (k.endswith("_0") or k.endswith("_1")) else k
            if base == a_id and bots[0] == args.hero_a:
                a_by_seed[base_seed] = v
            elif base == b_id and bots[0] == args.hero_b:
                b_by_seed[base_seed] = v

    # Compute paired diffs
    diffs = []
    a_vals, b_vals = [], []
    for seed in sorted(set(a_by_seed) & set(b_by_seed)):
        a_vals.append(a_by_seed[seed])
        b_vals.append(b_by_seed[seed])
        diffs.append(a_by_seed[seed] - b_by_seed[seed])

    n = len(diffs)
    if n == 0:
        print("No paired matches", file=sys.stderr)
        sys.exit(1)

    diff_avg = sum(diffs) / n
    diff_sd = statistics.stdev(diffs) if n > 1 else 0
    diff_sem = diff_sd / (n ** 0.5)
    z = diff_avg / diff_sem if diff_sem > 0 else 0
    p_val = 2 * (1 - 0.5 * (1 + erf(abs(z) / sqrt(2))))

    a_avg = sum(a_vals) / n
    b_avg = sum(b_vals) / n

    print(f"\n=== Paired comparison ({n} paired matches × {args.hands} hands) ===")
    print(f"  {a_id} mean:         {a_avg:+8.0f}")
    print(f"  {b_id} mean:         {b_avg:+8.0f}")
    print(f"  Paired diff (A−B):   {diff_avg:+8.0f}  ± {1.96*diff_sem:.0f} (95% CI)")
    print(f"  z-score:             {z:8.2f}")
    print(f"  p-value (two-sided): {p_val:8.4f}")
    a_wins = sum(1 for d in diffs if d > 0)
    print(f"  {a_id} wins:         {a_wins}/{n} ({100*a_wins/n:.0f}%)")

    if abs(z) >= 1.96:
        winner = a_id if diff_avg > 0 else b_id
        print(f"\n  RESULT: {winner} wins paired comparison, p < 0.05")
    else:
        print(f"\n  RESULT: not statistically significant (p >= 0.05)")


if __name__ == "__main__":
    main()
