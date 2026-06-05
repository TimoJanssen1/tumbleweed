
"""Abstraction Tight — MCCFR-style abstraction bot.

Tier: strong
Strategy: discretizes bet sizes into a small tree, uses bucketed strategy tables.
Mimics a Slumbot-style blueprint trained on simplified game.

Critically: when faced with off-tree bet sizes (e.g. opponent overbets),
translates to nearest tree node. This translation is the documented exploit
that breaker_sniper/phase_hunter overbet branches are designed to attack.
"""

import eval7
import random
from collections import defaultdict
from itertools import combinations

BOT_NAME = "Abstraction Tight"

RANKS = "23456789TJQKA"
SUITS = "shdc"
RANK_VAL = {r: i for i, r in enumerate(RANKS, start=2)}

PREFLOP_EQ = {
    ('2', '2', False): 0.49,

    ('3', '2', False): 0.315,
    ('3', '2', True): 0.362,
    ('3', '3', False): 0.53,

    ('4', '2', False): 0.366,
    ('4', '2', True): 0.366,
    ('4', '3', False): 0.3555,
    ('4', '3', True): 0.393,
    ('4', '4', False): 0.555,

    ('5', '2', False): 0.3605,
    ('5', '2', True): 0.385,
    ('5', '3', False): 0.3565,
    ('5', '3', True): 0.3855,
    ('5', '4', False): 0.392,
    ('5', '4', True): 0.417,
    ('5', '5', False): 0.6165,

    ('6', '2', False): 0.3225,
    ('6', '2', True): 0.347,
    ('6', '3', False): 0.329,
    ('6', '3', True): 0.3815,
    ('6', '4', False): 0.368,
    ('6', '4', True): 0.424,
    ('6', '5', False): 0.4125,
    ('6', '5', True): 0.4285,
    ('6', '6', False): 0.625,

    ('7', '2', False): 0.322,
    ('7', '2', True): 0.4105,
    ('7', '3', False): 0.358,
    ('7', '3', True): 0.3925,
    ('7', '4', False): 0.382,
    ('7', '4', True): 0.421,
    ('7', '5', False): 0.417,
    ('7', '5', True): 0.419,
    ('7', '6', False): 0.4225,
    ('7', '6', True): 0.4475,
    ('7', '7', False): 0.657,

    ('8', '2', False): 0.361,
    ('8', '2', True): 0.394,
    ('8', '3', False): 0.3655,
    ('8', '3', True): 0.437,
    ('8', '4', False): 0.4005,
    ('8', '4', True): 0.4145,
    ('8', '5', False): 0.4185,
    ('8', '5', True): 0.4595,
    ('8', '6', False): 0.405,
    ('8', '6', True): 0.442,
    ('8', '7', False): 0.467,
    ('8', '7', True): 0.465,
    ('8', '8', False): 0.695,

    ('9', '2', False): 0.4045,
    ('9', '2', True): 0.451,
    ('9', '3', False): 0.3825,
    ('9', '3', True): 0.441,
    ('9', '4', False): 0.4,
    ('9', '4', True): 0.45,
    ('9', '5', False): 0.4375,
    ('9', '5', True): 0.4545,
    ('9', '6', False): 0.422,
    ('9', '6', True): 0.48,
    ('9', '7', False): 0.48,
    ('9', '7', True): 0.475,
    ('9', '8', False): 0.472,
    ('9', '8', True): 0.509,
    ('9', '9', False): 0.7225,

    ('A', '2', False): 0.5395,
    ('A', '2', True): 0.5885,
    ('A', '3', False): 0.509,
    ('A', '3', True): 0.592,
    ('A', '4', False): 0.5545,
    ('A', '4', True): 0.5835,
    ('A', '5', False): 0.593,
    ('A', '5', True): 0.5945,
    ('A', '6', False): 0.5515,
    ('A', '6', True): 0.58,
    ('A', '7', False): 0.567,
    ('A', '7', True): 0.626,
    ('A', '8', False): 0.6005,
    ('A', '8', True): 0.6,
    ('A', '9', False): 0.62,
    ('A', '9', True): 0.6255,
    ('A', 'A', False): 0.853,
    ('A', 'J', False): 0.6695,
    ('A', 'J', True): 0.662,
    ('A', 'K', False): 0.643,
    ('A', 'K', True): 0.6535,
    ('A', 'Q', False): 0.5985,
    ('A', 'Q', True): 0.656,
    ('A', 'T', False): 0.622,
    ('A', 'T', True): 0.649,

    ('J', '2', False): 0.447,
    ('J', '2', True): 0.487,
    ('J', '3', False): 0.4725,
    ('J', '3', True): 0.4645,
    ('J', '4', False): 0.468,
    ('J', '4', True): 0.495,
    ('J', '5', False): 0.476,
    ('J', '5', True): 0.5065,
    ('J', '6', False): 0.4585,
    ('J', '6', True): 0.4745,
    ('J', '7', False): 0.4985,
    ('J', '7', True): 0.502,
    ('J', '8', False): 0.529,
    ('J', '8', True): 0.518,
    ('J', '9', False): 0.5185,
    ('J', '9', True): 0.553,
    ('J', 'J', False): 0.75,
    ('J', 'T', False): 0.5835,
    ('J', 'T', True): 0.5955,

    ('K', '2', False): 0.506,
    ('K', '2', True): 0.5195,
    ('K', '3', False): 0.503,
    ('K', '3', True): 0.5325,
    ('K', '4', False): 0.523,
    ('K', '4', True): 0.555,
    ('K', '5', False): 0.5365,
    ('K', '5', True): 0.5735,
    ('K', '6', False): 0.526,
    ('K', '6', True): 0.5865,
    ('K', '7', False): 0.548,
    ('K', '7', True): 0.5785,
    ('K', '8', False): 0.5395,
    ('K', '8', True): 0.5745,
    ('K', '9', False): 0.563,
    ('K', '9', True): 0.6115,
    ('K', 'J', False): 0.59,
    ('K', 'J', True): 0.6155,
    ('K', 'K', False): 0.819,
    ('K', 'Q', False): 0.6195,
    ('K', 'Q', True): 0.649,
    ('K', 'T', False): 0.6035,
    ('K', 'T', True): 0.6155,

    ('Q', '2', False): 0.456,
    ('Q', '2', True): 0.529,
    ('Q', '3', False): 0.504,
    ('Q', '3', True): 0.505,
    ('Q', '4', False): 0.4835,
    ('Q', '4', True): 0.513,
    ('Q', '5', False): 0.5215,
    ('Q', '5', True): 0.5325,
    ('Q', '6', False): 0.5085,
    ('Q', '6', True): 0.5515,
    ('Q', '7', False): 0.5225,
    ('Q', '7', True): 0.5345,
    ('Q', '8', False): 0.565,
    ('Q', '8', True): 0.56,
    ('Q', '9', False): 0.5535,
    ('Q', '9', True): 0.563,
    ('Q', 'J', False): 0.582,
    ('Q', 'J', True): 0.6,
    ('Q', 'Q', False): 0.787,
    ('Q', 'T', False): 0.592,
    ('Q', 'T', True): 0.599,

    ('T', '2', False): 0.424,
    ('T', '2', True): 0.4465,
    ('T', '3', False): 0.4315,
    ('T', '3', True): 0.459,
    ('T', '4', False): 0.4355,
    ('T', '4', True): 0.4895,
    ('T', '5', False): 0.4495,
    ('T', '5', True): 0.4595,
    ('T', '6', False): 0.459,
    ('T', '6', True): 0.512,
    ('T', '7', False): 0.5155,
    ('T', '7', True): 0.503,
    ('T', '8', False): 0.49,
    ('T', '8', True): 0.539,
    ('T', '9', False): 0.544,
    ('T', '9', True): 0.547,
    ('T', 'T', False): 0.752,
}

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


# Bet abstraction (fractions of pot)
BET_TREE = [0.33, 0.66, 1.0, 2.0]

# Equity buckets for hand strength
EQUITY_BUCKETS = [0.20, 0.40, 0.55, 0.70, 0.85]

# Pre-computed mixed strategy by (street_idx, equity_bucket, facing_bet)
# Values are dicts of {action: probability}
STRATEGY = {
    # Preflop, low equity, not facing bet
    (0, 0, 0): {"check": 1.0},
    (0, 1, 0): {"check": 0.7, "raise_0.33": 0.3},
    (0, 2, 0): {"raise_0.33": 0.5, "raise_0.66": 0.5},
    (0, 3, 0): {"raise_0.66": 0.6, "raise_1.0": 0.4},
    (0, 4, 0): {"raise_1.0": 0.7, "raise_2.0": 0.3},
    # Preflop, facing bet
    (0, 0, 1): {"fold": 1.0},
    (0, 1, 1): {"fold": 0.7, "call": 0.3},
    (0, 2, 1): {"call": 0.7, "raise_0.66": 0.3},
    (0, 3, 1): {"call": 0.4, "raise_1.0": 0.6},
    (0, 4, 1): {"raise_1.0": 0.6, "raise_2.0": 0.4},
    # Flop, no bet
    (1, 0, 0): {"check": 0.85, "raise_0.33": 0.15},
    (1, 1, 0): {"check": 0.6, "raise_0.33": 0.4},
    (1, 2, 0): {"raise_0.33": 0.4, "raise_0.66": 0.6},
    (1, 3, 0): {"raise_0.66": 0.7, "raise_1.0": 0.3},
    (1, 4, 0): {"raise_0.66": 0.5, "raise_1.0": 0.5},
    # Flop, facing bet
    (1, 0, 1): {"fold": 0.9, "call": 0.1},
    (1, 1, 1): {"fold": 0.6, "call": 0.4},
    (1, 2, 1): {"call": 0.7, "raise_0.66": 0.3},
    (1, 3, 1): {"call": 0.4, "raise_1.0": 0.6},
    (1, 4, 1): {"raise_1.0": 0.7, "raise_2.0": 0.3},
    # Turn, no bet
    (2, 0, 0): {"check": 0.9, "raise_0.33": 0.1},
    (2, 1, 0): {"check": 0.6, "raise_0.66": 0.4},
    (2, 2, 0): {"raise_0.66": 0.5, "raise_1.0": 0.5},
    (2, 3, 0): {"raise_1.0": 0.6, "raise_2.0": 0.4},
    (2, 4, 0): {"raise_1.0": 0.5, "raise_2.0": 0.5},
    # Turn, facing bet
    (2, 0, 1): {"fold": 0.95, "call": 0.05},
    (2, 1, 1): {"fold": 0.7, "call": 0.3},
    (2, 2, 1): {"call": 0.7, "raise_1.0": 0.3},
    (2, 3, 1): {"call": 0.4, "raise_2.0": 0.6},
    (2, 4, 1): {"raise_2.0": 0.8, "call": 0.2},
    # River, no bet
    (3, 0, 0): {"check": 0.85, "raise_0.66": 0.15},  # rare river bluffs
    (3, 1, 0): {"check": 0.7, "raise_0.66": 0.3},
    (3, 2, 0): {"raise_0.66": 0.6, "raise_1.0": 0.4},
    (3, 3, 0): {"raise_1.0": 0.5, "raise_2.0": 0.5},
    (3, 4, 0): {"raise_2.0": 0.7, "raise_1.0": 0.3},
    # River, facing bet
    (3, 0, 1): {"fold": 0.95, "call": 0.05},
    (3, 1, 1): {"fold": 0.7, "call": 0.3},
    (3, 2, 1): {"call": 0.65, "raise_1.0": 0.35},
    (3, 3, 1): {"call": 0.5, "raise_2.0": 0.5},
    (3, 4, 1): {"raise_2.0": 0.85, "call": 0.15},
}

def _equity_bucket(eq):
    for i, threshold in enumerate(EQUITY_BUCKETS):
        if eq < threshold:
            return i
    return len(EQUITY_BUCKETS) - 1

def _street_idx(street):
    return {"preflop": 0, "flop": 1, "turn": 2, "river": 3}.get(street, 0)

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

    strat = STRATEGY.get((s_idx, bucket, facing), {"fold": 1.0})
    action_name = _sample_action(strat)

    if action_name == "fold":
        return {"action": "fold"}
    if action_name == "check":
        if can_check:
            return {"action": "check"}
        # Translate "check" when facing bet -> call cheap, else fold
        if owed <= pot * 0.2:
            return {"action": "call"}
        return {"action": "fold"}
    if action_name == "call":
        return {"action": "call"}
    if action_name.startswith("raise_"):
        frac = float(action_name.split("_")[1])
        target = max(min_raise, int(pot * frac))
        if not can_check:
            target = max(min_raise, int(pot * frac) + state["current_bet"])
        return {"action": "raise", "amount": min(stack + bet_this, target)}
    return {"action": "fold"}


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

