"""
Swiss-tournament simulator — estimates cumulative chip-delta distribution
for the hero over 3 Swiss rounds, with proper pairing.

Round 1: random 5 opponents drawn weighted from the field.
Round 2+: opponents drawn weighted from the top X% of round-1 finishers
          (Swiss winners-meet-winners dynamic).

After N simulations, reports:
  - mean / median / std of cumulative chip delta
  - distribution histogram
  - P(cumulative > threshold) for top-64 estimation (threshold ~80k for 400-bot field)

Usage:
    python3 analysis/swiss_sim.py <hero> [--sims 100] [--rounds 3] [--hands 400]
"""
import argparse
import json
import random
import statistics
import subprocess
import sys
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from math import erf, sqrt
from pathlib import Path

from _engine import REPO, ENGINE, MATCH, ENV, resolve_bot

from analysis.field_registry import discover_field, sample_field_seeded, TIER_WEIGHTS, apply_survivor


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


# Simulated qualifier: assume top 16% advance (top 64 of ~400).
# Pairing: after round k, top half meet, bottom half meet (simplified Swiss).
# Tier weights skew toward "stronger" in later rounds.

def shifted_weights(round_idx, total_rounds):
    """As rounds progress, the field we face shifts toward the elite tiers."""
    if round_idx == 0:
        return TIER_WEIGHTS
    # Round 1 onward: increase elite/strong, decrease weak/broken.
    progress = round_idx / max(1, total_rounds - 1)   # 0 (round 0) → 1 (last)
    new = {}
    for tier, w in TIER_WEIGHTS.items():
        if tier in ("elite", "strong"):
            new[tier] = w * (1.0 + 1.5 * progress)
        elif tier == "mid":
            new[tier] = w  # roughly stable
        else:  # weak, broken
            new[tier] = w * (1.0 - 0.7 * progress)
    total = sum(new.values())
    return {k: v / total for k, v in new.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("hero")
    ap.add_argument("--sims", type=int, default=100,
                    help="number of independent Swiss simulations")
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--hands", type=int, default=400)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--seed-base", type=int, default=200000)
    ap.add_argument("--top64-threshold", type=int, default=80000,
                    help="cumulative chip delta to count as 'Top 64'")
    ap.add_argument("--survivor", action="store_true",
                    help="fixed elite-heavy finalist field every round "
                         "(elite/strong/mid ~40/40/20, no weak/broken) — models Q2; "
                         "overrides the gentler built-in elite-shift")
    args = ap.parse_args()

    field = discover_field()
    survivor_w = None
    if args.survivor:
        field, survivor_w = apply_survivor(field)
    h_id = hero_id(args.hero)

    # Build all jobs upfront: sims × rounds matches
    # For each (sim, round) draw opponents using round-shifted weights.
    jobs = []
    job_meta = []   # parallel list of (sim_idx, round_idx)
    for sim in range(args.sims):
        for r in range(args.rounds):
            seed = args.seed_base + sim * 100 + r
            weights = survivor_w if args.survivor else shifted_weights(r, args.rounds)
            # Use seeded sampling for reproducibility
            rng = random.Random(seed)
            saved = random.getstate()
            try:
                random.setstate(rng.getstate())
                from analysis.field_registry import sample_opponents
                opps = sample_opponents(field, n=5, weights=weights,
                                         exclude=[args.hero])
            finally:
                random.setstate(saved)
            jobs.append(([args.hero] + opps, seed, args.hands))
            job_meta.append((sim, r))

    print(f"Running {len(jobs)} matches ({args.sims} sims × {args.rounds} rounds)"
          + ("  [SURVIVOR field: elite/strong/mid 40/40/20 every round]" if args.survivor else "")
          + " ...")
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        results = list(ex.map(run_match, jobs))

    # Aggregate per sim
    sim_cumulative = defaultdict(int)
    sim_round_deltas = defaultdict(dict)
    errors = 0
    for (sim, r), (seed, bots, res) in zip(job_meta, results):
        if "chip_delta" not in res:
            errors += 1
            continue
        # Hero delta in this match
        for k, v in res["chip_delta"].items():
            base = k.rsplit("_", 1)[0] if (k.endswith("_0") or k.endswith("_1")) else k
            if base == h_id:
                sim_cumulative[sim] += v
                sim_round_deltas[sim][r] = v
                break

    cumulative_list = [sim_cumulative[s] for s in range(args.sims) if s in sim_cumulative]
    n = len(cumulative_list)
    if n == 0:
        print("No completed sims", file=sys.stderr)
        sys.exit(1)

    avg = sum(cumulative_list) / n
    med = statistics.median(cumulative_list)
    sd = statistics.stdev(cumulative_list) if n > 1 else 0
    sem = sd / (n ** 0.5)

    # P(cumulative > threshold)
    above = sum(1 for c in cumulative_list if c > args.top64_threshold)
    p_top64_empirical = above / n
    z = (args.top64_threshold - avg) / sd if sd > 0 else 0
    p_top64_theoretical = 0.5 * (1 - erf(z / sqrt(2)))

    print(f"\n=== Swiss Simulation: {h_id} ===")
    print(f"  Sims:                {n}")
    print(f"  Rounds per sim:      {args.rounds}")
    print(f"  Hands per match:     {args.hands}")
    print(f"  Top-64 threshold:    +{args.top64_threshold:,}")
    print()
    print(f"  Cumulative Δ mean:   {avg:+9.0f}   (95% CI: ±{1.96*sem:.0f})")
    print(f"  Cumulative Δ median: {med:+9.0f}")
    print(f"  Cumulative Δ stddev: {sd:9.0f}")
    print(f"  Range:               {min(cumulative_list):+,} .. {max(cumulative_list):+,}")
    print()
    print(f"  P(cumulative > +{args.top64_threshold:,}):")
    print(f"    Empirical:   {100*p_top64_empirical:5.1f}%  ({above}/{n})")
    print(f"    Theoretical: {100*p_top64_theoretical:5.1f}%  (Gaussian fit)")

    # Per-round means
    print(f"\n=== Per-round means ===")
    for r in range(args.rounds):
        round_deltas = [sim_round_deltas[s].get(r) for s in range(args.sims)
                        if r in sim_round_deltas.get(s, {})]
        if round_deltas:
            r_avg = sum(round_deltas) / len(round_deltas)
            r_sd = statistics.stdev(round_deltas) if len(round_deltas) > 1 else 0
            print(f"  Round {r+1}:  mean Δ {r_avg:+8.0f}  SD {r_sd:7.0f}")

    # Histogram of cumulative deltas
    print(f"\n=== Cumulative-delta histogram ===")
    buckets = [(-50000, 0), (0, 20000), (20000, 40000), (40000, 60000),
               (60000, 80000), (80000, 100000), (100000, 150000), (150000, 999999)]
    for lo, hi in buckets:
        count = sum(1 for c in cumulative_list if lo <= c < hi)
        bar = "█" * (count * 40 // max(1, n))
        print(f"  [{lo:+7d}, {hi:+7d}): {count:3} {bar}")


if __name__ == "__main__":
    main()
