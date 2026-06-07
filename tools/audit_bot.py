"""
Decision audit — behavioral profile of ANY bot over fresh seeded matches.

Runs the hero against a sampled field (default tiers, --survivor, or
--exclude-tier) with sandbox/match.py --full-json, then parses each hand's
structured `events` stream (street-tagged, bot_id-tagged, with running pot +
stacks) to report the metrics that drive the Q2 plan:

  - per-street fold/call/raise mix
  - preflop vs SINGLE open   (the call% leak, W2)
  - preflop vs 3-BET+        (fold-to-3bet, the #1 lever, W1)
  - 3-bet% / c-bet% / fold-to-flop-bet (cbet proxy) / fold-to-pot-bet
  - aggression factor (AF)
  - scoop rate (Δ>=+40k and ==+50k), bust rate (Δ==-10k)
  - all-in win-rate, split into uncalled (fold-equity) vs showdown WR
        — the showdown WR is the +EV-stack-off proof the plan gates on
  - BOTH cumulative Δ and chip-Δ/100h (the two candidate ranking metrics)

Parsing `events` (not action_log) makes street + 3-bet/c-bet detection exact
rather than heuristic. seat→bot mapping is unnecessary: events carry bot_id.

Usage:
    python3 analysis/decision_audit.py <hero> [--seeds 80] [--hands 400]
            [--survivor] [--exclude-tier weak --exclude-tier mid] [--workers 6]
"""
import argparse
import json
import statistics
import subprocess
import sys
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from _engine import REPO, ENGINE, MATCH, ENV, resolve_bot

from analysis.field_registry import (discover_field, sample_field_seeded,
                                      TIER_WEIGHTS, apply_survivor)

BUST = -10000
SCOOP = 50000
NEAR_SCOOP = 40000
BB = 100
AGG = ("raise", "bet", "all_in")


def run_one_match(args):
    bots, seed, hands = args
    cmd = [sys.executable, MATCH, *[resolve_bot(b) for b in bots],
           "--hands", str(hands), "--seed", str(seed), "--full-json"]
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ENGINE), env=ENV)
    try:
        return seed, tuple(bots), json.loads(p.stdout)
    except Exception:
        return seed, tuple(bots), {"error": (p.stderr or p.stdout)[-400:]}


def hero_id(path: str) -> str:
    return Path(path).stem if Path(path).suffix in (".py", ".zip") else Path(path).name


# ---------------------------------------------------------------------------
# Per-hand event parsing
# ---------------------------------------------------------------------------

def parse_hand(hand: dict, hero: str):
    """Parse one hand's `events` for the hero. Returns (decisions, allin).

    decisions: list of dicts (one per hero decision) with keys:
        street, action, owed, pot_before, bet_ratio, n_raises_before,
        is_pf_aggressor, faced_flop_bet, position
    allin: None, or dict {won: bool, showdown: bool} if the hero was all-in.
    """
    events = hand.get("events") or []
    winners = {w.get("bot_id") for w in (hand.get("winners") or [])}
    showdown = bool(hand.get("showdown"))

    decisions = []
    street = "preflop"
    contrib = defaultdict(int)        # bot_id -> chips committed THIS street
    street_bet = 0                    # max committed this street
    n_raises = 0                      # voluntary raises/bets this street so far
    pf_aggressor = None               # last preflop raiser bot_id
    sb_bot = bb_bot = None
    cur_pot = 0                       # running pot (before the next action)
    hero_allin = False

    for ev in events:
        t = ev.get("type")
        if t == "street_start":
            street = ev.get("street", street)
            contrib = defaultdict(int)
            street_bet = 0
            n_raises = 0
            cur_pot = ev.get("pot", cur_pot)
            continue
        if t == "blind":
            bid = ev.get("bot_id")
            contrib[bid] += ev.get("amount", 0)
            street_bet = max(street_bet, contrib[bid])
            if ev.get("action") == "small_blind":
                sb_bot = bid
            elif ev.get("action") == "big_blind":
                bb_bot = bid
            cur_pot = ev.get("pot_after", ev.get("pot", cur_pot))
            continue
        if t != "action":
            # uncontested_win / showdown / misc — refresh pot then skip
            cur_pot = ev.get("pot_after", ev.get("pot", cur_pot))
            continue

        bid = ev.get("bot_id")
        act = ev.get("action")
        amt = ev.get("amount", 0) or 0
        owed = max(0, street_bet - contrib[bid])

        if bid == hero:
            pos = "SB" if hero == sb_bot else "BB" if hero == bb_bot else "other"
            decisions.append({
                "street": street,
                "action": act,
                "owed": owed,
                "pot_before": cur_pot,
                "bet_ratio": (owed / cur_pot) if cur_pot > 0 else 0.0,
                "n_raises_before": n_raises,
                "is_pf_aggressor": (pf_aggressor == hero),
                "faced_flop_bet": (street == "flop" and owed > 0
                                   and pf_aggressor is not None and pf_aggressor != hero),
                "position": pos,
            })

        # apply the action to street state
        if act == "fold":
            pass
        elif act == "check":
            pass
        elif act == "call":
            contrib[bid] = max(contrib[bid], street_bet)
        elif act in AGG:
            contrib[bid] = max(contrib[bid], amt)
            street_bet = max(street_bet, contrib[bid])
            n_raises += 1
            if street == "preflop":
                pf_aggressor = bid
        if act == "all_in" and bid == hero:
            hero_allin = True
        if bid == hero and ev.get("stack_after") == 0:
            hero_allin = True
        cur_pot = ev.get("pot_after", ev.get("pot", cur_pot))

    allin = None
    if hero_allin:
        allin = {"won": hero in winners, "showdown": showdown}
    return decisions, allin


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def pct(num, den):
    return (100.0 * num / den) if den else 0.0


def audit(results, hero):
    deltas = []
    total_hands = 0
    street_mix = defaultdict(Counter)          # street -> action counter
    vs_open = Counter()                         # preflop facing single raise
    vs_3bet = Counter()                         # preflop facing 3-bet+
    threebet_opp = threebet_made = 0            # hero 3-bet chances / taken
    cbet_opp = cbet_made = 0                    # hero c-bet chances / taken
    foldcbet_faced = foldcbet_folded = 0        # hero faces flop bet as non-aggressor
    pot_bet_faced = pot_bet_folded = 0          # facing ~pot-sized bet (postflop)
    agg_actions = call_actions = 0              # for AF
    allin_n = allin_show_n = allin_show_won = allin_uncalled = 0
    pos_mix = defaultdict(Counter)

    for seed, bots, res in results:
        if "chip_delta" not in res or "hands" not in res:
            continue
        d = res["chip_delta"].get(hero)
        if d is None:
            continue
        deltas.append(d)
        total_hands += res.get("n_hands", 0)

        for hand in res["hands"]:
            decs, allin = parse_hand(hand, hero)
            if allin is not None:
                allin_n += 1
                if allin["showdown"]:
                    allin_show_n += 1
                    allin_show_won += int(allin["won"])
                elif allin["won"]:
                    allin_uncalled += 1
            for x in decs:
                st, act = x["street"], x["action"]
                street_mix[st][act] += 1
                pos_mix[x["position"]][act] += 1
                if act in AGG:
                    agg_actions += 1
                elif act == "call":
                    call_actions += 1
                if st == "preflop":
                    if x["n_raises_before"] == 1:
                        vs_open[act] += 1
                        threebet_opp += 1
                        if act in ("raise", "all_in"):
                            threebet_made += 1
                    elif x["n_raises_before"] >= 2:
                        vs_3bet[act] += 1
                if x["is_pf_aggressor"] and st == "flop" and x["n_raises_before"] == 0:
                    cbet_opp += 1
                    if act in ("raise", "bet", "all_in"):
                        cbet_made += 1
                if x["faced_flop_bet"]:
                    foldcbet_faced += 1
                    foldcbet_folded += int(act == "fold")
                if st in ("flop", "turn", "river") and x["owed"] > 0 and 0.67 <= x["bet_ratio"] <= 1.5:
                    pot_bet_faced += 1
                    pot_bet_folded += int(act == "fold")

    return {
        "deltas": deltas, "total_hands": total_hands,
        "street_mix": street_mix, "pos_mix": pos_mix,
        "vs_open": vs_open, "vs_3bet": vs_3bet,
        "threebet_opp": threebet_opp, "threebet_made": threebet_made,
        "cbet_opp": cbet_opp, "cbet_made": cbet_made,
        "foldcbet_faced": foldcbet_faced, "foldcbet_folded": foldcbet_folded,
        "pot_bet_faced": pot_bet_faced, "pot_bet_folded": pot_bet_folded,
        "agg_actions": agg_actions, "call_actions": call_actions,
        "allin_n": allin_n, "allin_show_n": allin_show_n,
        "allin_show_won": allin_show_won, "allin_uncalled": allin_uncalled,
    }


def mix_str(counter):
    total = sum(counter.values())
    if not total:
        return "n=0"
    order = ["fold", "check", "call", "raise", "bet", "all_in"]
    bits = [f"{a} {pct(counter.get(a, 0), total):4.1f}%" for a in order if counter.get(a)]
    return f"n={total:>5}  " + "  ".join(bits)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("hero")
    ap.add_argument("--seeds", type=int, default=80)
    ap.add_argument("--hands", type=int, default=400)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--seed-base", type=int, default=80000)
    ap.add_argument("--exclude-tier", action="append", default=[])
    ap.add_argument("--survivor", action="store_true",
                    help="elite-heavy finalist field (models Q2)")
    args = ap.parse_args()

    field = discover_field()
    for tier in args.exclude_tier:
        field.pop(tier, None)
    weights = None
    if args.survivor:
        field, weights = apply_survivor(field)

    h = hero_id(args.hero)
    jobs = []
    for s in range(args.seeds):
        seed = args.seed_base + s
        opps = sample_field_seeded(field, seed, n=5, weights=weights, exclude=[args.hero])
        jobs.append(([args.hero] + opps, seed, args.hands))

    label = "SURVIVOR" if args.survivor else (("excl:" + ",".join(args.exclude_tier)) if args.exclude_tier else "default")
    print(f"Auditing {h}: {args.seeds} matches × {args.hands} hands  [field: {label}]")
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        results = list(ex.map(run_one_match, jobs))

    a = audit(results, h)
    deltas = a["deltas"]
    if not deltas:
        print("No completed matches", file=sys.stderr)
        sys.exit(1)

    n = len(deltas)
    cum = sum(deltas)
    mean = cum / n
    sd = statistics.stdev(deltas) if n > 1 else 0
    sem = sd / (n ** 0.5)
    th = a["total_hands"]
    chips_per_100 = 100.0 * cum / th if th else 0.0
    busts = sum(1 for d in deltas if d == BUST)
    scoops = sum(1 for d in deltas if d == SCOOP)
    near = sum(1 for d in deltas if d >= NEAR_SCOOP)
    wins = sum(1 for d in deltas if d > 0)

    print(f"\n=== {h} — outcome ({n} matches, {th} hands) ===")
    print(f"  Mean Δ/match:   {mean:+9.0f}  ± {1.96*sem:.0f} (95% CI)")
    print(f"  Median Δ:       {statistics.median(deltas):+9.0f}")
    print(f"  Cumulative Δ:   {cum:+9.0f}")
    print(f"  chip-Δ/100h:    {chips_per_100:+9.1f}   (BB/100 = {chips_per_100/BB:+.2f})")
    print(f"  Win rate:       {wins}/{n} ({pct(wins,n):.0f}%)")
    print(f"  Bust rate:      {busts}/{n} ({pct(busts,n):.0f}%)   (Δ=={BUST})")
    print(f"  Scoop rate:     ==50k {scoops}/{n} ({pct(scoops,n):.0f}%)  |  >=40k {near}/{n} ({pct(near,n):.0f}%)")

    af = a["agg_actions"] / a["call_actions"] if a["call_actions"] else float("inf")
    print(f"\n=== aggression / exploit profile ===")
    print(f"  Aggression factor (raise+bet+allin)/call:  {af:.2f}")
    print(f"  Preflop vs SINGLE open:  {mix_str(a['vs_open'])}")
    print(f"  Preflop vs 3-BET+:       {mix_str(a['vs_3bet'])}   <- fold-to-3bet (W1)")
    print(f"  3-bet% (facing single open):   {pct(a['threebet_made'], a['threebet_opp']):.1f}%  ({a['threebet_made']}/{a['threebet_opp']})")
    print(f"  c-bet% (as PF aggressor, flop): {pct(a['cbet_made'], a['cbet_opp']):.1f}%  ({a['cbet_made']}/{a['cbet_opp']})")
    print(f"  fold-to-flop-bet (cbet proxy):  {pct(a['foldcbet_folded'], a['foldcbet_faced']):.1f}%  ({a['foldcbet_folded']}/{a['foldcbet_faced']})")
    print(f"  fold-to-pot-bet (postflop):     {pct(a['pot_bet_folded'], a['pot_bet_faced']):.1f}%  ({a['pot_bet_folded']}/{a['pot_bet_faced']})")

    print(f"\n=== all-in (stack-off EV) ===")
    print(f"  All-in hands:        {a['allin_n']}")
    print(f"  Uncalled (fold eq):  {a['allin_uncalled']}")
    print(f"  Showdown all-ins:    {a['allin_show_n']}   WON {a['allin_show_won']}  "
          f"({pct(a['allin_show_won'], a['allin_show_n']):.1f}% showdown WR)  <- +EV stack-off proof")

    print(f"\n=== per-street action mix ===")
    for st in ("preflop", "flop", "turn", "river"):
        print(f"  {st:8}: {mix_str(a['street_mix'][st])}")

    print(f"\n=== by position (preflop+postflop) ===")
    for p in ("SB", "BB", "other"):
        print(f"  {p:6}: {mix_str(a['pos_mix'][p])}")


if __name__ == "__main__":
    main()
