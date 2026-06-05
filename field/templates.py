"""
Bot template strings for the synthetic field generator.

Each template is Python source code with `{name}`-style placeholders.
The generator (analysis/generate_field.py) fills in placeholders to
materialize each generated bot.py as a self-contained module.
"""

from analysis.preflop_table import render_eq_table_source


# ============================================================================
# Common header — equity table + helpers — embedded into many bot templates
# ============================================================================

COMMON_HEADER = '''
import eval7
import random
from collections import defaultdict
from itertools import combinations

BOT_NAME = "{display_name}"

RANKS = "23456789TJQKA"
SUITS = "shdc"
RANK_VAL = {{r: i for i, r in enumerate(RANKS, start=2)}}

{equity_table}

def hand_class(cards):
    r1, s1 = cards[0][0], cards[0][1]
    r2, s2 = cards[1][0], cards[1][1]
    if RANK_VAL[r1] < RANK_VAL[r2]:
        r1, r2 = r2, r1
        s1, s2 = s2, s1
    if r1 == r2:
        return (r1, r2, False)
    return (r1, r2, s1 == s2)

def preflop_equity(cards):
    return PREFLOP_EQ.get(hand_class(cards), 0.40)
'''


# ============================================================================
# Equity computation helpers
# ============================================================================

MC_EQUITY_HELPERS = '''
def expand_combos(range_classes, blocked=()):
    blocked_set = set(blocked)
    combos = []
    for r1, r2, suited in range_classes:
        if r1 == r2:
            for s1, s2 in combinations(SUITS, 2):
                c1, c2 = r1 + s1, r2 + s2
                if c1 not in blocked_set and c2 not in blocked_set:
                    combos.append((c1, c2))
        elif suited:
            for s in SUITS:
                c1, c2 = r1 + s, r2 + s
                if c1 not in blocked_set and c2 not in blocked_set:
                    combos.append((c1, c2))
        else:
            for s1 in SUITS:
                for s2 in SUITS:
                    if s1 != s2:
                        c1, c2 = r1 + s1, r2 + s2
                        if c1 not in blocked_set and c2 not in blocked_set:
                            combos.append((c1, c2))
    return combos

def equity_vs_range(my_hole, board, opp_combos, n_trials):
    if not opp_combos:
        return 0.5
    my = [eval7.Card(c) for c in my_hole]
    bd = [eval7.Card(c) for c in board]
    used = set(my_hole) | set(board)
    deck_strs = [r + s for r in RANKS for s in SUITS if (r + s) not in used]
    wins = ties = total = 0
    need = 5 - len(board)
    for _ in range(n_trials):
        c1, c2 = random.choice(opp_combos)
        if c1 in used or c2 in used:
            continue
        opp_used = used | {c1, c2}
        remaining = [c for c in deck_strs if c not in opp_used]
        if need > 0:
            extras = random.sample(remaining, need)
        else:
            extras = []
        full_board = bd + [eval7.Card(c) for c in extras]
        opp_cards = [eval7.Card(c1), eval7.Card(c2)]
        my_score = eval7.evaluate(my + full_board)
        opp_score = eval7.evaluate(opp_cards + full_board)
        if my_score > opp_score: wins += 1
        elif my_score == opp_score: ties += 1
        total += 1
    if total == 0:
        return 0.5
    return (wins + ties / 2.0) / total

def _build_range(min_eq):
    return [k for k, v in PREFLOP_EQ.items() if v >= min_eq]

RANGE_PREMIUM = _build_range(0.70)
RANGE_STRONG = _build_range(0.62)
RANGE_TIGHT = _build_range(0.55)
RANGE_STANDARD = _build_range(0.50)
RANGE_WIDE = _build_range(0.46)
'''


# ============================================================================
# Safety wrapper (used by every generated bot)
# ============================================================================

SAFE_DECIDE_WRAPPER = '''
def decide(state):
    if state.get("type") == "warmup":
        return {"action": "fold"}
    try:
        if "your_cards" not in state or len(state["your_cards"]) < 2:
            return {"action": "fold"}
        action = _decide_inner(state)
        if not isinstance(action, dict) or "action" not in action:
            return {"action": "fold"}
        if action["action"] == "raise" and "amount" not in action:
            return {"action": "fold"}
        return action
    except Exception:
        if state.get("can_check"):
            return {"action": "check"}
        return {"action": "fold"}
'''


# ============================================================================
# Template: real-time MC equity bot (used by strong/elite tier variants)
# ============================================================================

MC_EQUITY_BOT = '''
"""{display_name} — real-time MC equity vs estimated range.

Tier: {tier}
Strategy: classic equity-based TAG. Preflop chart + MC postflop equity.
Parameters: open_thresh={open_thresh}, three_bet_thresh={three_bet_thresh},
            cbet_freq={cbet_freq}, n_trials={n_trials}.
"""
{common_header}
{mc_helpers}

OPEN_THRESH = {open_thresh}
THREE_BET_THRESH = {three_bet_thresh}
CALL_THRESH = {call_thresh}
CBET_FREQ = {cbet_freq}
N_TRIALS = {n_trials}
VALUE_BET_EQ = {value_bet_eq}
SIZING_MENU = {sizing_menu}

def _est_range(action_log, n_players):
    n_raises = sum(1 for e in action_log if e.get("action") in ("raise", "all_in"))
    if n_raises >= 2:
        return RANGE_PREMIUM
    if n_raises == 1:
        return RANGE_STRONG
    return RANGE_STANDARD

def _decide_inner(state):
    street = state["street"]
    hole = state["your_cards"]
    pot = state["pot"]
    owed = state["amount_owed"]
    stack = state["your_stack"]
    can_check = state["can_check"]
    bet_this = state["your_bet_this_street"]
    min_raise = state["min_raise_to"]
    n_players = len(state["players"])

    if street == "preflop":
        eq = preflop_equity(hole)
        log = state.get("action_log", [])
        n_raises = sum(1 for e in log if e.get("action") in ("raise", "all_in"))
        if n_raises == 0:
            if can_check:
                if eq >= OPEN_THRESH + 0.05:
                    size = max(min_raise, int(pot * 1.5))
                    return {{"action": "raise", "amount": min(stack + bet_this, size)}}
                return {{"action": "check"}}
            if eq >= OPEN_THRESH:
                size = max(min_raise, int(pot * 2.5))
                return {{"action": "raise", "amount": min(stack + bet_this, size)}}
            return {{"action": "fold"}}
        if n_raises == 1:
            if eq >= THREE_BET_THRESH:
                size = max(min_raise, int(state["current_bet"] * 3))
                return {{"action": "raise", "amount": min(stack + bet_this, size)}}
            if eq >= CALL_THRESH and owed <= pot * 0.5:
                return {{"action": "call"}}
            return {{"action": "fold"}}
        # 3-bet+
        if eq >= 0.78:
            return {{"action": "all_in"}}
        if eq >= 0.70 and owed <= pot * 0.7:
            return {{"action": "call"}}
        return {{"action": "fold"}}

    # Postflop
    opp_range = expand_combos(_est_range(state.get("action_log", []), n_players))
    eq = equity_vs_range(hole, state["community_cards"], opp_range, N_TRIALS)
    n_active = sum(1 for p in state["players"]
                   if p["state"] == "active" and p["seat"] != state["seat_to_act"])
    if n_active > 1:
        eq = eq ** (1 + 0.4 * (n_active - 1))

    odds_needed = owed / max(1, pot + owed)

    if can_check:
        if eq >= VALUE_BET_EQ:
            if random.random() < CBET_FREQ:
                size_pct = random.choice(SIZING_MENU)
                size = max(min_raise, int(pot * size_pct))
                return {{"action": "raise", "amount": min(stack + bet_this, size)}}
        return {{"action": "check"}}

    if eq >= 0.80:
        size = max(min_raise, int(pot * 1.0) + state["current_bet"])
        return {{"action": "raise", "amount": min(stack + bet_this, size)}}
    if eq >= odds_needed + 0.05:
        return {{"action": "call"}}
    return {{"action": "fold"}}

{safe_decide}
'''


# ============================================================================
# Template: abstraction (MCCFR-style) bot
# ============================================================================

ABSTRACTION_BOT = '''
"""{display_name} — MCCFR-style abstraction bot.

Tier: {tier}
Strategy: discretizes bet sizes into a small tree, uses bucketed strategy tables.
Mimics a Slumbot-style blueprint trained on simplified game.

Critically: when faced with off-tree bet sizes (e.g. opponent overbets),
translates to nearest tree node. This translation is the documented exploit
that breaker_sniper/phase_hunter overbet branches are designed to attack.
"""
{common_header}
{mc_helpers}

# Bet abstraction (fractions of pot)
BET_TREE = [0.33, 0.66, 1.0, 2.0]

# Equity buckets for hand strength
EQUITY_BUCKETS = [0.20, 0.40, 0.55, 0.70, 0.85]

# Pre-computed mixed strategy by (street_idx, equity_bucket, facing_bet)
# Values are dicts of {{action: probability}}
STRATEGY = {{
    # Preflop, low equity, not facing bet
    (0, 0, 0): {{"check": 1.0}},
    (0, 1, 0): {{"check": 0.7, "raise_0.33": 0.3}},
    (0, 2, 0): {{"raise_0.33": 0.5, "raise_0.66": 0.5}},
    (0, 3, 0): {{"raise_0.66": 0.6, "raise_1.0": 0.4}},
    (0, 4, 0): {{"raise_1.0": 0.7, "raise_2.0": 0.3}},
    # Preflop, facing bet
    (0, 0, 1): {{"fold": 1.0}},
    (0, 1, 1): {{"fold": 0.7, "call": 0.3}},
    (0, 2, 1): {{"call": 0.7, "raise_0.66": 0.3}},
    (0, 3, 1): {{"call": 0.4, "raise_1.0": 0.6}},
    (0, 4, 1): {{"raise_1.0": 0.6, "raise_2.0": 0.4}},
    # Flop, no bet
    (1, 0, 0): {{"check": 0.85, "raise_0.33": 0.15}},
    (1, 1, 0): {{"check": 0.6, "raise_0.33": 0.4}},
    (1, 2, 0): {{"raise_0.33": 0.4, "raise_0.66": 0.6}},
    (1, 3, 0): {{"raise_0.66": 0.7, "raise_1.0": 0.3}},
    (1, 4, 0): {{"raise_0.66": 0.5, "raise_1.0": 0.5}},
    # Flop, facing bet
    (1, 0, 1): {{"fold": 0.9, "call": 0.1}},
    (1, 1, 1): {{"fold": 0.6, "call": 0.4}},
    (1, 2, 1): {{"call": 0.7, "raise_0.66": 0.3}},
    (1, 3, 1): {{"call": 0.4, "raise_1.0": 0.6}},
    (1, 4, 1): {{"raise_1.0": 0.7, "raise_2.0": 0.3}},
    # Turn, no bet
    (2, 0, 0): {{"check": 0.9, "raise_0.33": 0.1}},
    (2, 1, 0): {{"check": 0.6, "raise_0.66": 0.4}},
    (2, 2, 0): {{"raise_0.66": 0.5, "raise_1.0": 0.5}},
    (2, 3, 0): {{"raise_1.0": 0.6, "raise_2.0": 0.4}},
    (2, 4, 0): {{"raise_1.0": 0.5, "raise_2.0": 0.5}},
    # Turn, facing bet
    (2, 0, 1): {{"fold": 0.95, "call": 0.05}},
    (2, 1, 1): {{"fold": 0.7, "call": 0.3}},
    (2, 2, 1): {{"call": 0.7, "raise_1.0": 0.3}},
    (2, 3, 1): {{"call": 0.4, "raise_2.0": 0.6}},
    (2, 4, 1): {{"raise_2.0": 0.8, "call": 0.2}},
    # River, no bet
    (3, 0, 0): {{"check": 0.85, "raise_0.66": 0.15}},  # rare river bluffs
    (3, 1, 0): {{"check": 0.7, "raise_0.66": 0.3}},
    (3, 2, 0): {{"raise_0.66": 0.6, "raise_1.0": 0.4}},
    (3, 3, 0): {{"raise_1.0": 0.5, "raise_2.0": 0.5}},
    (3, 4, 0): {{"raise_2.0": 0.7, "raise_1.0": 0.3}},
    # River, facing bet
    (3, 0, 1): {{"fold": 0.95, "call": 0.05}},
    (3, 1, 1): {{"fold": 0.7, "call": 0.3}},
    (3, 2, 1): {{"call": 0.65, "raise_1.0": 0.35}},
    (3, 3, 1): {{"call": 0.5, "raise_2.0": 0.5}},
    (3, 4, 1): {{"raise_2.0": 0.85, "call": 0.15}},
}}

def _equity_bucket(eq):
    for i, threshold in enumerate(EQUITY_BUCKETS):
        if eq < threshold:
            return i
    return len(EQUITY_BUCKETS) - 1

def _street_idx(street):
    return {{"preflop": 0, "flop": 1, "turn": 2, "river": 3}}.get(street, 0)

def _sample_action(strat):
    r = random.random()
    cum = 0.0
    for action, prob in strat.items():
        cum += prob
        if r < cum:
            return action
    return list(strat.keys())[0]

def _decide_inner(state):
    street = state["street"]
    hole = state["your_cards"]
    board = state["community_cards"]
    pot = state["pot"]
    owed = state["amount_owed"]
    stack = state["your_stack"]
    can_check = state["can_check"]
    bet_this = state["your_bet_this_street"]
    min_raise = state["min_raise_to"]

    # Compute equity
    if street == "preflop":
        eq = preflop_equity(hole)
    else:
        opp_range = expand_combos(RANGE_STANDARD)
        eq = equity_vs_range(hole, board, opp_range, n_trials=120)

    bucket = _equity_bucket(eq)
    s_idx = _street_idx(street)
    facing = 0 if can_check else 1

    strat = STRATEGY.get((s_idx, bucket, facing), {{"fold": 1.0}})
    action_name = _sample_action(strat)

    if action_name == "fold":
        return {{"action": "fold"}}
    if action_name == "check":
        if can_check:
            return {{"action": "check"}}
        # Translate "check" when facing bet -> call cheap, else fold
        if owed <= pot * 0.2:
            return {{"action": "call"}}
        return {{"action": "fold"}}
    if action_name == "call":
        return {{"action": "call"}}
    if action_name.startswith("raise_"):
        frac = float(action_name.split("_")[1])
        target = max(min_raise, int(pot * frac))
        if not can_check:
            target = max(min_raise, int(pot * frac) + state["current_bet"])
        return {{"action": "raise", "amount": min(stack + bet_this, target)}}
    return {{"action": "fold"}}

{safe_decide}
'''


# ============================================================================
# Template: mixed-sizing solver imitator
# ============================================================================

MIXED_SIZING_BOT = '''
"""{display_name} — mixed-sizing solver imitator.

Tier: {tier}
Strategy: simulates a real solver's output: each decision samples bet sizes
from a Gaussian around abstraction nodes (not pure abstraction). Designed to
defeat naive "detect 51% pot bet" heuristics.
"""
{common_header}
{mc_helpers}

import math

SIZING_NODES = [0.33, 0.5, 0.66, 0.75, 1.0, 1.5, 2.0]
SIZING_SIGMA = 0.06

def _gaussian_size(target):
    """Sample size around `target` with Gaussian noise."""
    return max(0.15, min(3.0, random.gauss(target, SIZING_SIGMA)))

def _est_range(action_log):
    n_raises = sum(1 for e in action_log if e.get("action") in ("raise", "all_in"))
    if n_raises >= 2:
        return RANGE_PREMIUM
    if n_raises == 1:
        return RANGE_STRONG
    return RANGE_STANDARD

def _decide_inner(state):
    street = state["street"]
    hole = state["your_cards"]
    board = state["community_cards"]
    pot = state["pot"]
    owed = state["amount_owed"]
    stack = state["your_stack"]
    can_check = state["can_check"]
    bet_this = state["your_bet_this_street"]
    min_raise = state["min_raise_to"]

    if street == "preflop":
        eq = preflop_equity(hole)
    else:
        opp_range = expand_combos(_est_range(state.get("action_log", [])))
        eq = equity_vs_range(hole, board, opp_range, n_trials=140)

    odds_needed = owed / max(1, pot + owed)

    # Pick action based on equity, mixed
    if street == "preflop":
        if can_check:
            if eq >= 0.65 and random.random() < 0.7:
                node = random.choices(SIZING_NODES[:5], weights=[0.1, 0.2, 0.3, 0.25, 0.15])[0]
                size_pct = _gaussian_size(node)
                size = max(min_raise, int(pot * size_pct))
                return {{"action": "raise", "amount": min(stack + bet_this, size)}}
            return {{"action": "check"}}

        n_raises = sum(1 for e in state.get("action_log", [])
                       if e.get("action") in ("raise", "all_in"))
        if n_raises >= 2:
            if eq >= 0.78: return {{"action": "raise", "amount": min(stack + bet_this, int(state["current_bet"] * 2.4))}}
            if eq >= 0.65 and owed <= pot * 0.7: return {{"action": "call"}}
            return {{"action": "fold"}}
        if eq >= 0.72:
            node = random.choices([0.66, 1.0, 1.5], weights=[0.4, 0.4, 0.2])[0]
            size = max(min_raise, int(state["current_bet"] * (1 + node * 2)))
            return {{"action": "raise", "amount": min(stack + bet_this, size)}}
        if eq >= 0.55 and owed <= pot * 0.4:
            return {{"action": "call"}}
        return {{"action": "fold"}}

    # Postflop
    if can_check:
        if eq >= 0.78:
            node = random.choices([0.66, 1.0, 1.5, 2.0], weights=[0.25, 0.35, 0.25, 0.15])[0]
            size_pct = _gaussian_size(node)
            size = max(min_raise, int(pot * size_pct))
            return {{"action": "raise", "amount": min(stack + bet_this, size)}}
        if eq >= 0.55 and random.random() < 0.5:
            node = random.choices([0.33, 0.5, 0.66], weights=[0.3, 0.4, 0.3])[0]
            size = max(min_raise, int(pot * _gaussian_size(node)))
            return {{"action": "raise", "amount": min(stack + bet_this, size)}}
        if eq < 0.30 and random.random() < 0.15:
            # Bluff
            node = random.choices([0.5, 0.75, 1.0], weights=[0.4, 0.4, 0.2])[0]
            size = max(min_raise, int(pot * _gaussian_size(node)))
            return {{"action": "raise", "amount": min(stack + bet_this, size)}}
        return {{"action": "check"}}

    if eq >= 0.82:
        node = random.choices([0.66, 1.0, 1.5], weights=[0.3, 0.4, 0.3])[0]
        size = max(min_raise, int(pot * _gaussian_size(node)) + state["current_bet"])
        return {{"action": "raise", "amount": min(stack + bet_this, size)}}
    if eq >= odds_needed + 0.05:
        return {{"action": "call"}}
    return {{"action": "fold"}}

{safe_decide}
'''


# ============================================================================
# Template: hand-chart based TAG (mid tier)
# ============================================================================

HAND_CHART_BOT = '''
"""{display_name} — preflop hand-chart + postflop handtype.

Tier: {tier}
Strategy: a typical mid-tier "I read a poker book" bot. Uses preflop chart
plus handtype thresholds postflop. No equity calculation.
Parameters: chart_tightness={chart_tightness}, cbet_freq={cbet_freq}
"""
{common_header}

CHART_TIGHTNESS = {chart_tightness}   # 0.55-0.65 typical
CBET_FREQ = {cbet_freq}

def _decide_inner(state):
    street = state["street"]
    hole = state["your_cards"]
    pot = state["pot"]
    owed = state["amount_owed"]
    stack = state["your_stack"]
    can_check = state["can_check"]
    bet_this = state["your_bet_this_street"]
    min_raise = state["min_raise_to"]

    eq = preflop_equity(hole)

    if street == "preflop":
        if can_check:
            if eq >= CHART_TIGHTNESS + 0.08:
                return {{"action": "raise", "amount": min(stack + bet_this, int(pot * 1.2))}}
            return {{"action": "check"}}
        if eq >= CHART_TIGHTNESS + 0.10:
            return {{"action": "raise", "amount": min(stack + bet_this, int(pot * 2.5))}}
        if eq >= CHART_TIGHTNESS and owed <= pot * 0.3:
            return {{"action": "call"}}
        return {{"action": "fold"}}

    # Postflop: handtype-based
    board = state["community_cards"]
    score = eval7.evaluate([eval7.Card(c) for c in hole + board])
    htype = eval7.handtype(score)

    strong = htype in ("Two Pair", "Trips", "Straight", "Flush", "Full House", "Quads", "Straight Flush")

    if can_check:
        if strong:
            return {{"action": "raise", "amount": min(stack + bet_this, max(min_raise, int(pot * 0.7)))}}
        if htype == "Pair" and random.random() < CBET_FREQ:
            return {{"action": "raise", "amount": min(stack + bet_this, max(min_raise, int(pot * 0.5)))}}
        if random.random() < CBET_FREQ * 0.4:
            return {{"action": "raise", "amount": min(stack + bet_this, max(min_raise, int(pot * 0.5)))}}
        return {{"action": "check"}}

    if strong:
        return {{"action": "call"}}
    if htype == "Pair" and owed <= pot * 0.5:
        return {{"action": "call"}}
    return {{"action": "fold"}}

{safe_decide}
'''


# ============================================================================
# Template: pot-odds bot (mid tier)
# ============================================================================

POT_ODDS_BOT = '''
"""{display_name} — pot-odds-only bot.

Tier: {tier}
Strategy: pure pot odds, no equity calculation. Plays mechanically.
"""
{common_header}

CALL_THRESHOLD = {call_threshold}   # max pot-odds ratio willing to call

def _decide_inner(state):
    street = state["street"]
    hole = state["your_cards"]
    pot = state["pot"]
    owed = state["amount_owed"]
    stack = state["your_stack"]
    can_check = state["can_check"]
    bet_this = state["your_bet_this_street"]
    min_raise = state["min_raise_to"]

    eq = preflop_equity(hole)

    if street == "preflop":
        if eq >= 0.70:
            target = max(min_raise, int(pot * 2.5))
            return {{"action": "raise", "amount": min(stack + bet_this, target)}}
        if can_check:
            return {{"action": "check"}}
        if owed <= pot * CALL_THRESHOLD:
            return {{"action": "call"}}
        return {{"action": "fold"}}

    # Postflop
    board = state["community_cards"]
    score = eval7.evaluate([eval7.Card(c) for c in hole + board])
    htype = eval7.handtype(score)
    strong = htype not in ("High Card", "Pair")

    if can_check:
        if strong:
            return {{"action": "raise", "amount": min(stack + bet_this, max(min_raise, int(pot * 0.66)))}}
        return {{"action": "check"}}

    pot_odds = owed / max(1, pot)
    if strong and pot_odds <= 0.8:
        return {{"action": "call"}}
    if htype == "Pair" and pot_odds <= 0.3:
        return {{"action": "call"}}
    return {{"action": "fold"}}

{safe_decide}
'''


# ============================================================================
# Template: LLM-boilerplate bot (mid tier)
# ============================================================================

LLM_BOILERPLATE_BOT = '''
"""{display_name} — typical LLM-generated boilerplate.

Tier: {tier}
Strategy: imitates a one-shot LLM-generated bot. Lots of if/elif chains,
mediocre but functional. Common in hackathon submissions.
"""
{common_header}

def get_hand_strength(cards):
    """Return strength category: 'premium', 'strong', 'medium', 'weak'."""
    r1 = RANK_VAL[cards[0][0]]
    r2 = RANK_VAL[cards[1][0]]
    suited = cards[0][1] == cards[1][1]
    if r1 < r2:
        r1, r2 = r2, r1
    if r1 == r2 and r1 >= 11:  # JJ+
        return "premium"
    if r1 == 14 and r2 >= 11:  # AJ+
        return "premium"
    if r1 == r2 and r1 >= 8:  # 88-TT
        return "strong"
    if r1 == 14 and r2 >= 8:  # A8+
        return "strong"
    if r1 >= 12 and r2 >= 10 and suited:  # KQs, KJs, QJs
        return "strong"
    if r1 == r2:  # smaller pair
        return "medium"
    if r1 >= 12 and r2 >= 9:  # KQ-KJ-QJ-QT-JT etc
        return "medium"
    if suited and r1 - r2 <= 2 and r2 >= 6:  # suited connectors
        return "medium"
    return "weak"

def _decide_inner(state):
    street = state["street"]
    hole = state["your_cards"]
    pot = state["pot"]
    owed = state["amount_owed"]
    stack = state["your_stack"]
    can_check = state["can_check"]
    bet_this = state["your_bet_this_street"]
    min_raise = state["min_raise_to"]

    strength = get_hand_strength(hole)

    if street == "preflop":
        if strength == "premium":
            target = max(min_raise, int(pot * 3))
            return {{"action": "raise", "amount": min(stack + bet_this, target)}}
        if strength == "strong":
            if owed == 0:
                target = max(min_raise, int(pot * 2.5))
                return {{"action": "raise", "amount": min(stack + bet_this, target)}}
            if owed <= pot * 0.3:
                return {{"action": "call"}}
            return {{"action": "fold"}}
        if strength == "medium":
            if can_check:
                return {{"action": "check"}}
            if owed <= pot * 0.15:
                return {{"action": "call"}}
            return {{"action": "fold"}}
        if can_check:
            return {{"action": "check"}}
        return {{"action": "fold"}}

    # Postflop
    board = state["community_cards"]
    score = eval7.evaluate([eval7.Card(c) for c in hole + board])
    htype = eval7.handtype(score)

    if htype in ("Two Pair", "Trips", "Straight", "Flush", "Full House", "Quads", "Straight Flush"):
        if can_check:
            return {{"action": "raise", "amount": min(stack + bet_this, max(min_raise, int(pot * 0.66)))}}
        return {{"action": "call"}}
    if htype == "Pair":
        if can_check:
            return {{"action": "raise", "amount": min(stack + bet_this, max(min_raise, int(pot * 0.5)))}}
        if owed <= pot * 0.4:
            return {{"action": "call"}}
        return {{"action": "fold"}}
    if can_check:
        return {{"action": "check"}}
    if owed <= pot * 0.1:
        return {{"action": "call"}}
    return {{"action": "fold"}}

{safe_decide}
'''


# ============================================================================
# Template: simple aggressive / passive variants (weak tier)
# ============================================================================

WEAK_VARIANT_BOT = '''
"""{display_name} — weak-tier variant.

Tier: {tier}
Strategy: deliberately bad. Represents a template-tilt or single-rule bot
common in low-effort submissions.
Mode: {mode}
"""
import random
BOT_NAME = "{display_name}"
MODE = "{mode}"

def decide(state):
    if state.get("type") == "warmup":
        return {{"action": "fold"}}
    try:
        if "your_cards" not in state or len(state["your_cards"]) < 2:
            return {{"action": "fold"}}
        return _inner(state)
    except Exception:
        return {{"action": "check"}} if state.get("can_check") else {{"action": "fold"}}

def _inner(state):
    pot = state["pot"]
    owed = state["amount_owed"]
    stack = state["your_stack"]
    can_check = state["can_check"]
    bet_this = state["your_bet_this_street"]
    min_raise = state["min_raise_to"]

    if MODE == "calling_station":
        if can_check:
            return {{"action": "check"}}
        if owed <= stack:
            return {{"action": "call"}}
        return {{"action": "call"}}

    if MODE == "naive_aggressor":
        if random.random() < 0.75:
            target = max(min_raise, int(pot * random.uniform(1.5, 3.5)))
            return {{"action": "raise", "amount": min(stack + bet_this, target)}}
        if can_check:
            return {{"action": "check"}}
        return {{"action": "call"}}

    if MODE == "ultra_nit":
        # Folds almost everything
        r1 = state["your_cards"][0][0]
        r2 = state["your_cards"][1][0]
        is_pair = r1 == r2
        is_premium = r1 in "AKQ" and r2 in "AKQ"
        if is_pair or is_premium:
            if can_check:
                return {{"action": "raise", "amount": min(stack + bet_this, int(pot * 2))}}
            if owed <= pot * 0.5:
                return {{"action": "call"}}
            return {{"action": "fold"}}
        if can_check:
            return {{"action": "check"}}
        return {{"action": "fold"}}

    if MODE == "minraise_bot":
        # Always min-raises
        if can_check:
            return {{"action": "raise", "amount": min(stack + bet_this, min_raise)}}
        if owed <= pot * 0.3:
            return {{"action": "raise", "amount": min(stack + bet_this, min_raise)}}
        return {{"action": "fold"}}

    if MODE == "random_action":
        # Pure random
        r = random.random()
        if r < 0.3:
            return {{"action": "fold"}}
        if r < 0.6:
            if can_check:
                return {{"action": "check"}}
            return {{"action": "call"}}
        target = max(min_raise, int(pot * random.uniform(0.5, 2.0)))
        return {{"action": "raise", "amount": min(stack + bet_this, target)}}

    # default: fold
    if can_check:
        return {{"action": "check"}}
    return {{"action": "fold"}}
'''


# ============================================================================
# Broken bots (test engine robustness)
# ============================================================================

BROKEN_CRASHER_BOT = '''
"""{display_name} — crashes randomly. Tests engine's auto-fold-on-exception."""
import random
BOT_NAME = "{display_name}"

def decide(state):
    if state.get("type") == "warmup":
        return {{"action": "fold"}}
    if random.random() < 0.10:
        raise RuntimeError("simulated bot crash")
    # Otherwise play minimally
    if state.get("can_check"):
        return {{"action": "check"}}
    if state.get("amount_owed", 0) <= state.get("pot", 1) * 0.2:
        return {{"action": "call"}}
    return {{"action": "fold"}}
'''


BROKEN_ILLEGAL_BOT = '''
"""{display_name} — returns illegal actions sometimes."""
import random
BOT_NAME = "{display_name}"

def decide(state):
    if state.get("type") == "warmup":
        return {{"action": "fold"}}
    r = random.random()
    if r < 0.05:
        return {{"action": "invalid_action"}}
    if r < 0.10:
        return {{"action": "raise"}}   # missing amount
    if r < 0.15:
        return "not a dict"
    if state.get("can_check"):
        return {{"action": "check"}}
    return {{"action": "fold"}}
'''


BROKEN_SLOW_BOT = '''
"""{display_name} — occasionally times out by sleeping past 2s budget."""
import random
import time
BOT_NAME = "{display_name}"

def decide(state):
    if state.get("type") == "warmup":
        return {{"action": "fold"}}
    if random.random() < 0.03:
        time.sleep(3.0)   # past timeout
    if state.get("can_check"):
        return {{"action": "check"}}
    return {{"action": "fold"}}
'''
