"""
Tumble-Weed — my first bot for the Fullhouse 2026 poker competition
(6-max No-Limit Texas Hold'em). This is the one that played Q1.

The core is tight-aggressive poker on a Monte-Carlo equity estimate: deal out a few
hundred random run-outs against the range I'd put the opponent on, count how often I
win, and bet or fold off that. The plan was deliberately plain — play solid, don't
punt, let a soft field pay me off. It finished #28, comfortably inside the top 10%.

"""

import eval7
import random
from collections import defaultdict
from itertools import combinations

BOT_NAME = "Tumble-Weed"

STARTING_STACK = 10000
BB = 100

RANKS = "23456789TJQKA"
SUITS = "shdc"
RANK_VAL = {r: i for i, r in enumerate(RANKS, start=2)}

PREFLOP_EQ = {
    ('2','2',False): 0.49, ('3','2',False): 0.315, ('3','2',True): 0.362,
    ('3','3',False): 0.53, ('4','2',False): 0.366, ('4','2',True): 0.366,
    ('4','3',False): 0.3555, ('4','3',True): 0.393, ('4','4',False): 0.555,
    ('5','2',False): 0.3605, ('5','2',True): 0.385, ('5','3',False): 0.3565,
    ('5','3',True): 0.3855, ('5','4',False): 0.392, ('5','4',True): 0.417,
    ('5','5',False): 0.6165, ('6','2',False): 0.3225, ('6','2',True): 0.347,
    ('6','3',False): 0.329, ('6','3',True): 0.3815, ('6','4',False): 0.368,
    ('6','4',True): 0.424, ('6','5',False): 0.4125, ('6','5',True): 0.4285,
    ('6','6',False): 0.625, ('7','2',False): 0.322, ('7','2',True): 0.4105,
    ('7','3',False): 0.358, ('7','3',True): 0.3925, ('7','4',False): 0.382,
    ('7','4',True): 0.421, ('7','5',False): 0.417, ('7','5',True): 0.419,
    ('7','6',False): 0.4225, ('7','6',True): 0.4475, ('7','7',False): 0.657,
    ('8','2',False): 0.361, ('8','2',True): 0.394, ('8','3',False): 0.3655,
    ('8','3',True): 0.437, ('8','4',False): 0.4005, ('8','4',True): 0.4145,
    ('8','5',False): 0.4185, ('8','5',True): 0.4595, ('8','6',False): 0.405,
    ('8','6',True): 0.442, ('8','7',False): 0.467, ('8','7',True): 0.465,
    ('8','8',False): 0.695, ('9','2',False): 0.4045, ('9','2',True): 0.451,
    ('9','3',False): 0.3825, ('9','3',True): 0.441, ('9','4',False): 0.4,
    ('9','4',True): 0.45, ('9','5',False): 0.4375, ('9','5',True): 0.4545,
    ('9','6',False): 0.422, ('9','6',True): 0.48, ('9','7',False): 0.48,
    ('9','7',True): 0.475, ('9','8',False): 0.472, ('9','8',True): 0.509,
    ('9','9',False): 0.7225, ('A','2',False): 0.5395, ('A','2',True): 0.5885,
    ('A','3',False): 0.509, ('A','3',True): 0.592, ('A','4',False): 0.5545,
    ('A','4',True): 0.5835, ('A','5',False): 0.593, ('A','5',True): 0.5945,
    ('A','6',False): 0.5515, ('A','6',True): 0.58, ('A','7',False): 0.567,
    ('A','7',True): 0.626, ('A','8',False): 0.6005, ('A','8',True): 0.6,
    ('A','9',False): 0.62, ('A','9',True): 0.6255, ('A','A',False): 0.853,
    ('A','J',False): 0.6695, ('A','J',True): 0.662, ('A','K',False): 0.643,
    ('A','K',True): 0.6535, ('A','Q',False): 0.5985, ('A','Q',True): 0.656,
    ('A','T',False): 0.622, ('A','T',True): 0.649, ('J','2',False): 0.447,
    ('J','2',True): 0.487, ('J','3',False): 0.4725, ('J','3',True): 0.4645,
    ('J','4',False): 0.468, ('J','4',True): 0.495, ('J','5',False): 0.476,
    ('J','5',True): 0.5065, ('J','6',False): 0.4585, ('J','6',True): 0.4745,
    ('J','7',False): 0.4985, ('J','7',True): 0.502, ('J','8',False): 0.529,
    ('J','8',True): 0.518, ('J','9',False): 0.5185, ('J','9',True): 0.553,
    ('J','J',False): 0.75, ('J','T',False): 0.5835, ('J','T',True): 0.5955,
    ('K','2',False): 0.506, ('K','2',True): 0.5195, ('K','3',False): 0.503,
    ('K','3',True): 0.5325, ('K','4',False): 0.523, ('K','4',True): 0.555,
    ('K','5',False): 0.5365, ('K','5',True): 0.5735, ('K','6',False): 0.526,
    ('K','6',True): 0.5865, ('K','7',False): 0.548, ('K','7',True): 0.5785,
    ('K','8',False): 0.5395, ('K','8',True): 0.5745, ('K','9',False): 0.563,
    ('K','9',True): 0.6115, ('K','J',False): 0.59, ('K','J',True): 0.6155,
    ('K','K',False): 0.819, ('K','Q',False): 0.6195, ('K','Q',True): 0.649,
    ('K','T',False): 0.6035, ('K','T',True): 0.6155, ('Q','2',False): 0.456,
    ('Q','2',True): 0.529, ('Q','3',False): 0.504, ('Q','3',True): 0.505,
    ('Q','4',False): 0.4835, ('Q','4',True): 0.513, ('Q','5',False): 0.5215,
    ('Q','5',True): 0.5325, ('Q','6',False): 0.5085, ('Q','6',True): 0.5515,
    ('Q','7',False): 0.5225, ('Q','7',True): 0.5345, ('Q','8',False): 0.565,
    ('Q','8',True): 0.56, ('Q','9',False): 0.5535, ('Q','9',True): 0.563,
    ('Q','J',False): 0.582, ('Q','J',True): 0.6, ('Q','Q',False): 0.787,
    ('Q','T',False): 0.592, ('Q','T',True): 0.599, ('T','2',False): 0.424,
    ('T','2',True): 0.4465, ('T','3',False): 0.4315, ('T','3',True): 0.459,
    ('T','4',False): 0.4355, ('T','4',True): 0.4895, ('T','5',False): 0.4495,
    ('T','5',True): 0.4595, ('T','6',False): 0.459, ('T','6',True): 0.512,
    ('T','7',False): 0.5155, ('T','7',True): 0.503, ('T','8',False): 0.49,
    ('T','8',True): 0.539, ('T','9',False): 0.544, ('T','9',True): 0.547,
    ('T','T',False): 0.752,
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


def _build_range(min_eq):
    return [k for k, v in PREFLOP_EQ.items() if v >= min_eq]


RANGE_PREMIUM     = _build_range(0.70)
RANGE_STRONG      = _build_range(0.62)
RANGE_TIGHT       = _build_range(0.55)
RANGE_STANDARD    = _build_range(0.50)
RANGE_WIDE        = _build_range(0.46)
RANGE_VERY_WIDE   = _build_range(0.40)


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


def equity_vs_range(my_hole, board, opp_combos, n_trials=160):
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
        extras = random.sample(remaining, need) if need > 0 else []
        full_board = bd + [eval7.Card(c) for c in extras]
        opp_cards = [eval7.Card(c1), eval7.Card(c2)]
        my_score = eval7.evaluate(my + full_board)
        opp_score = eval7.evaluate(opp_cards + full_board)
        if my_score > opp_score:
            wins += 1
        elif my_score == opp_score:
            ties += 1
        total += 1
    if total == 0:
        return 0.5
    return (wins + ties / 2.0) / total


OPP = defaultdict(lambda: {
    "actions": 0, "raises": 0, "calls": 0, "folds": 0, "checks": 0,
    "pf_raises": 0, "pf_voluntary": 0, "pf_actions": 0,
    "post_raises": 0, "post_actions": 0,
    "hands_seen": set(),
})

SEEN = set()

HAND_STATE = {"hand_id": None, "eq": {}}


def _reset_hand(hid):
    HAND_STATE["hand_id"] = hid
    HAND_STATE["eq"] = {}


def _eq_delta(current_eq, street):
    order = ["preflop", "flop", "turn", "river"]
    if street not in order:
        return 0.0
    idx = order.index(street)
    for s in reversed(order[:idx]):
        if s in HAND_STATE["eq"]:
            return current_eq - HAND_STATE["eq"][s]
    return 0.0


def absorb_log(state):
    log = state.get("match_action_log", []) or []
    seq = defaultdict(int)
    for e in log:
        h = e.get("hand_num", 0)
        i = seq[h]
        seq[h] += 1
        key = (h, i)
        if key in SEEN:
            continue
        SEEN.add(key)
        bid = e.get("bot_id")
        a = e.get("action")
        s = OPP[bid]
        s["actions"] += 1
        s["hands_seen"].add(h)
        if a == "fold":
            s["folds"] += 1
        elif a == "check":
            s["checks"] += 1
        elif a == "call":
            s["calls"] += 1
        elif a == "raise":
            s["raises"] += 1
        elif a == "all_in":
            s["all_ins"] = s.get("all_ins", 0) + 1
            s["raises"] += 1


def estimate_opp_tightness(bid):
    s = OPP.get(bid)
    if not s or s["actions"] < 6:
        return 0.5
    raise_freq = s["raises"] / max(1, s["actions"])
    fold_freq = s["folds"] / max(1, s["actions"])
    tightness = 0.5 + 0.5 * fold_freq - 0.5 * raise_freq
    return max(0.05, min(0.95, tightness))


def opp_range(bid, was_raiser, was_caller):
    tight = estimate_opp_tightness(bid)
    if was_raiser:
        if tight > 0.70: return RANGE_PREMIUM
        if tight > 0.55: return RANGE_STRONG
        if tight > 0.40: return RANGE_TIGHT
        return RANGE_STANDARD
    if was_caller:
        if tight > 0.60: return RANGE_TIGHT
        return RANGE_STANDARD
    if tight > 0.50: return RANGE_WIDE
    return RANGE_VERY_WIDE


def _hand_num_from_state(state):
    hid = state.get("hand_id") or ""
    if "_h" in hid:
        try:
            return int(hid.split("_h")[-1])
        except Exception:
            pass
    log = state.get("match_action_log", []) or []
    if log:
        try:
            return max((e.get("hand_num", 0) for e in log), default=0) + 1
        except Exception:
            pass
    return 0


def _classify_phase(hand_num):
    if hand_num < 100:
        return "early"
    if hand_num < 280:
        return "mid"
    return "late"


def _classify_stack(my_stack):
    if my_stack >= 13000: return "winning_big"
    if my_stack >= 11000: return "winning"
    if my_stack >=  8500: return "even"
    if my_stack >=  6500: return "losing"
    if my_stack >=  3500: return "behind"
    return "short"


def _variance_mode(hand_num, my_stack):
    phase  = _classify_phase(hand_num)
    status = _classify_stack(my_stack)

    if status == "short":
        return phase, status, "push_fold"
    if phase == "late":
        if status in ("winning_big", "winning"):
            return phase, status, "lock_in"
        if status == "losing":
            return phase, status, "press"
        if status == "behind":
            return phase, status, "variance"
    return phase, status, "standard"


def _identify_opponents(state):
    last_raiser_seat = None
    pre_callers = set()
    for e in state.get("action_log", []) or []:
        a = e.get("action")
        seat = e.get("seat")
        if a == "raise" or a == "all_in":
            last_raiser_seat = seat
            pre_callers = set()
        elif a == "call":
            pre_callers.add(seat)

    primary_bid = None
    is_raiser = False
    is_caller = False
    if last_raiser_seat is not None:
        for p in state["players"]:
            if p["seat"] == last_raiser_seat and p["state"] == "active":
                primary_bid = p["bot_id"]
                is_raiser = True
                break
    if primary_bid is None and pre_callers:
        for p in state["players"]:
            if p["seat"] in pre_callers and p["state"] == "active":
                primary_bid = p["bot_id"]
                is_caller = True
                break
    return primary_bid, is_raiser, is_caller


def _preflop_decision(state, mode, opp_tight):
    hole = state["your_cards"]
    pot = state["pot"]
    owed = state["amount_owed"]
    stack = state["your_stack"]
    can_check = state["can_check"]
    bet_this = state["your_bet_this_street"]
    min_raise = state["min_raise_to"]

    eq = preflop_equity(hole)
    n_raises = sum(1 for e in (state.get("action_log") or [])
                   if e.get("action") in ("raise", "all_in"))

    if mode == "push_fold":
        if eq >= 0.62:
            return {"action": "all_in"}
        if n_raises == 0 and can_check:
            return {"action": "check"}
        return {"action": "fold"}

    if mode == "lock_in":
        open_floor, three_floor, call_floor, four_floor = 0.55, 0.76, 0.64, 0.82
    elif mode == "press":
        open_floor, three_floor, call_floor, four_floor = 0.46, 0.66, 0.54, 0.76
    elif mode == "variance":
        open_floor, three_floor, call_floor, four_floor = 0.42, 0.60, 0.50, 0.72
    else:
        open_floor, three_floor, call_floor, four_floor = 0.50, 0.70, 0.58, 0.78

    if n_raises == 0:
        if can_check:
            iso_thresh = 0.62 if mode == "lock_in" else 0.55
            if eq >= iso_thresh:
                target = max(min_raise, int(pot * 1.2))
                return {"action": "raise", "amount": min(stack + bet_this, target)}
            return {"action": "check"}
        open_thresh = open_floor - 0.10 * (1 - opp_tight)
        if eq >= open_thresh:
            if   mode == "variance": mult = 3.0
            elif mode == "lock_in":  mult = 2.0
            else:                    mult = 2.5
            target = max(min_raise, int(pot * mult))
            return {"action": "raise", "amount": min(stack + bet_this, target)}
        return {"action": "fold"}

    if n_raises == 1:
        three_thresh = three_floor - 0.08 * (1 - opp_tight)
        call_thresh  = call_floor  - 0.10 * (1 - opp_tight)
        if eq >= three_thresh:
            if   mode == "variance": mult = 3.5
            elif mode == "lock_in":  mult = 2.4
            else:                    mult = 3.0
            target = max(min_raise, int(state["current_bet"] * mult))
            return {"action": "raise", "amount": min(stack + bet_this, target)}
        if eq >= call_thresh and owed <= pot * 0.6:
            return {"action": "call"}
        return {"action": "fold"}

    if eq >= four_floor:
        target = max(min_raise, int(state["current_bet"] * 2.4))
        return {"action": "raise", "amount": min(stack + bet_this, target)}
    if eq >= 0.68 and owed <= pot * 0.7:
        return {"action": "call"}
    return {"action": "fold"}


def _postflop_decision(state, primary_bid, is_raiser, is_caller):
    hole = state["your_cards"]
    board = state["community_cards"]
    pot = state["pot"]
    owed = state["amount_owed"]
    stack = state["your_stack"]
    can_check = state["can_check"]
    bet_this = state["your_bet_this_street"]
    min_raise = state["min_raise_to"]
    street = state["street"]
    my_seat = state["seat_to_act"]

    opp_range_classes = opp_range(primary_bid, is_raiser, is_caller)
    opp_combos = expand_combos(opp_range_classes,
                                blocked=set(hole) | set(board))
    if owed > 0 and len(opp_combos) > 10:
        bet_ratio = owed / max(1, pot)
        if   bet_ratio >= 1.0: keep = 0.30
        elif bet_ratio >= 0.7: keep = 0.50
        elif bet_ratio >= 0.4: keep = 0.70
        else:                  keep = 1.0
        if keep < 1.0:
            def combo_eq(c):
                r1, r2 = c[0][0], c[1][0]
                if RANK_VAL[r1] < RANK_VAL[r2]:
                    r1, r2 = r2, r1
                suited = (c[0][1] == c[1][1]) and (r1 != r2)
                return PREFLOP_EQ.get((r1, r2, False if r1 == r2 else suited), 0.4)
            opp_combos = sorted(opp_combos, key=combo_eq, reverse=True)
            opp_combos = opp_combos[:max(8, int(len(opp_combos) * keep))]

    eq = equity_vs_range(hole, board, opp_combos, n_trials=160)

    n_active = sum(1 for p in state["players"]
                   if p["state"] == "active" and p["seat"] != my_seat)
    if n_active > 1:
        eq = eq ** (1 + 0.35 * (n_active - 1))

    eq_delta = _eq_delta(eq, street)
    HAND_STATE["eq"][street] = eq

    odds_needed = owed / max(1, pot + owed)
    if eq_delta < -0.04:
        odds_needed += min(0.10, abs(eq_delta) * 0.30)
    elif eq_delta > 0.04:
        odds_needed -= min(0.06, eq_delta * 0.20)
    odds_needed = max(0.05, odds_needed)

    if can_check:
        if eq >= 0.75:
            ot = estimate_opp_tightness(primary_bid) if primary_bid else 0.5
            size_frac = 0.75 if ot > 0.5 else 1.0
            size = max(min_raise, int(pot * size_frac))
            return {"action": "raise", "amount": min(stack + bet_this, size)}
        if eq >= 0.55 and random.random() < 0.4:
            size = max(min_raise, int(pot * 0.5))
            return {"action": "raise", "amount": min(stack + bet_this, size)}
        if eq < 0.30 and random.random() < 0.12:
            size = max(min_raise, int(pot * 0.66))
            return {"action": "raise", "amount": min(stack + bet_this, size)}
        return {"action": "check"}

    if eq >= 0.78:
        size = max(min_raise, int(pot * 1.0) + state["current_bet"])
        return {"action": "raise", "amount": min(stack + bet_this, size)}
    if eq >= odds_needed + 0.04:
        if eq < 0.35 and owed > pot:
            return {"action": "fold"}
        return {"action": "call"}
    return {"action": "fold"}


def _decide_inner(state):
    absorb_log(state)

    hand_num = _hand_num_from_state(state)
    _, _, mode = _variance_mode(
        hand_num,
        state["your_stack"] + state.get("your_bet_this_street", 0),
    )

    primary_bid, is_raiser, is_caller = _identify_opponents(state)
    opp_tight = estimate_opp_tightness(primary_bid) if primary_bid else 0.5

    if state["street"] == "preflop":
        return _preflop_decision(state, mode, opp_tight)
    return _postflop_decision(state, primary_bid, is_raiser, is_caller)


def decide(state):
    if state.get("type") == "warmup":
        return {"action": "fold"}
    try:
        if "your_cards" not in state or len(state["your_cards"]) < 2:
            return {"action": "fold"}
        hid = state.get("hand_id")
        if hid != HAND_STATE.get("hand_id"):
            _reset_hand(hid)
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
