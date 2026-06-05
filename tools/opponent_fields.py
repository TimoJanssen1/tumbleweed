"""
Field registry — discovers all bots in bots/field/ and provides weighted
sampling functions for benchmarks and Swiss simulations.

Tier weights are calibrated to my estimated qualifier-field distribution:

    Tier       Estimated % of qualifier   Reasoning
    -----------------------------------------------------------------------
    elite          7  %    Real MC + opp modelling / MCCFR / strong solver
    strong        20  %    Real-time MC equity bots (the bulk of "decent")
    mid           38  %    Hand-chart + heuristic / LLM-generated boilerplate
    weak          30  %    Templates, naive aggressors, simple rules
    broken         5  %    Bots with crash/timeout/illegal-action bugs

These numbers come from:
  - hackathon profile (400+ entrants, top UK unis, ~20-day build window)
  - what students realistically ship under time pressure
  - distribution of effort across a recruiting-event submission pool
"""

from pathlib import Path
import random

REPO = Path(__file__).resolve().parent.parent

TIER_WEIGHTS = {
    "elite":  0.07,
    "strong": 0.20,
    "mid":    0.38,
    "weak":   0.30,
    "broken": 0.05,
}

# Survivor / finalist field: models a Q2 field of qualifiers — elite-heavy,
# no weak/broken. This is the field on which the fork decision was made
# (mentor_v2 sweeps it) and the primary acceptance surface for tumbleweeddutch.
# Needed because swiss_sim's built-in elite-shift only reaches ~17% elite at
# rounds=5, far short of the ~40% that actually models Q2.
SURVIVOR_WEIGHTS = {
    "elite":  0.40,
    "strong": 0.40,
    "mid":    0.20,
}


def apply_survivor(field):
    """Drop weak/broken tiers and return (field, SURVIVOR_WEIGHTS) for an
    elite-heavy finalist field. `field` is a dict from discover_field()."""
    field = {t: b for t, b in field.items() if t in SURVIVOR_WEIGHTS}
    return field, dict(SURVIVOR_WEIGHTS)


def discover_field():
    """Walk bots/field/* and return {tier: [bot_dir_path, ...]}.

    Returns paths relative to repo root (suitable for sandbox/match.py)."""
    field = {}
    base = REPO / "bots" / "field"
    if not base.is_dir():
        return field
    for tier_dir in sorted(base.iterdir()):
        if not tier_dir.is_dir():
            continue
        tier = tier_dir.name
        if tier not in TIER_WEIGHTS:
            continue
        bots = []
        for bot_dir in sorted(tier_dir.iterdir()):
            if (bot_dir / "bot.py").is_file():
                bots.append(str(bot_dir.relative_to(REPO)))
        if bots:
            field[tier] = bots
    return field


def sample_opponents(field, n=5, weights=None, exclude=()):
    """Sample n opponents from the field, weighted by tier.

    `field`:    dict from discover_field()
    `n`:        number of opponents to sample (typically 5 for 6-max)
    `weights`:  dict tier -> weight (defaults to TIER_WEIGHTS)
    `exclude`:  iterable of bot paths to exclude (e.g. the hero itself)

    Returns a list of n bot paths.
    """
    if weights is None:
        weights = TIER_WEIGHTS
    exclude = set(exclude)

    # Build flat sampling pool: each bot gets weight = tier_weight / n_bots_in_tier
    pool = []
    pool_weights = []
    for tier, bots in field.items():
        if tier not in weights or not bots:
            continue
        w = weights[tier] / len(bots)
        for bot in bots:
            if bot in exclude:
                continue
            pool.append(bot)
            pool_weights.append(w)

    if len(pool) < n:
        raise ValueError(f"Not enough bots in field: {len(pool)} available, need {n}")

    # Sample without replacement, respecting weights
    selected = []
    available = list(zip(pool, pool_weights))
    for _ in range(n):
        total = sum(w for _, w in available)
        r = random.uniform(0, total)
        cum = 0.0
        chosen_idx = 0
        for i, (b, w) in enumerate(available):
            cum += w
            if r <= cum:
                chosen_idx = i
                break
        selected.append(available[chosen_idx][0])
        available.pop(chosen_idx)
    return selected


def sample_field_seeded(field, seed, n=5, weights=None, exclude=()):
    """Deterministic version of sample_opponents using a specific seed."""
    rng = random.Random(seed)
    saved_state = random.getstate()
    random.setstate(rng.getstate())
    try:
        return sample_opponents(field, n=n, weights=weights, exclude=exclude)
    finally:
        random.setstate(saved_state)


def summarize(field):
    """Return human-readable summary string."""
    lines = ["=== Field summary ==="]
    total = sum(len(b) for b in field.values())
    lines.append(f"  total bots: {total}")
    for tier in TIER_WEIGHTS:
        bots = field.get(tier, [])
        w = TIER_WEIGHTS.get(tier, 0)
        lines.append(f"  {tier:8} ({100*w:>4.0f}% weight)  {len(bots):2} bots")
        for b in bots:
            name = Path(b).name
            lines.append(f"      - {name}")
    return "\n".join(lines)


if __name__ == "__main__":
    field = discover_field()
    print(summarize(field))
    print()
    # Smoke test: sample 5 opponents
    sample = sample_opponents(field, n=5)
    print(f"Sample of 5 opponents:")
    for s in sample:
        print(f"  {s}")
