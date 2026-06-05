"""
Gunslinger — my bot for the final round of the Fullhouse 2026 poker competition
(6-max No-Limit Texas Hold'em).

  * a Monte-Carlo equity estimate. Every decision, it deals out a few hundred
    random run-outs against the hands the opponent could actually have and counts
    how often I win, with a board-texture check so it won't stack off one pair
    into an obvious flush or straight.
  * a live read on each opponent, rebuilt from the public action log every match:
    how often they 3-bet, fold to a c-bet, fold to a 4-bet, how aggressive they
    are. It reads behaviour, never identity — nothing is keyed to a specific bot,
    and the read resets when the match does.
  * extra preflop pressure. The qualifier logs showed the field folding to a
    re-raise far more often than it should, so this version 3-bets and 4-bets a
    lot more than the earlier ones, which mostly just flat-called and gave that up.
"""

import eval7
import random
from collections import defaultdict
from itertools import combinations

BOT_NAME = "tumbleweeddutch_v24"

STARTING_STACK = 10000
BB = 100
SB = 50

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


RANGE_PREMIUM   = _build_range(0.70)
RANGE_STRONG    = _build_range(0.62)
RANGE_TIGHT     = _build_range(0.55)
RANGE_STANDARD  = _build_range(0.50)
RANGE_WIDE      = _build_range(0.46)
RANGE_VERY_WIDE = _build_range(0.40)


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


# --- Board-texture awareness ------------------------------------------------
# Preflop equity is blind to the board, so when I'm facing a bet I re-rank the
# opponent's range by how strong each holding actually is on THIS board, and flag
# when the board itself is scary (flush / straight / paired) so I don't pay off
# the obvious nuts with one pair.

HANDRANK = {
    "High Card": 0, "Pair": 1, "Two Pair": 2, "Trips": 3, "Straight": 4,
    "Flush": 5, "Full House": 6, "Quads": 7, "Straight Flush": 8,
}


def _made_rank(hole, board):
    try:
        cs = [eval7.Card(c) for c in hole] + [eval7.Card(c) for c in board]
        return HANDRANK.get(str(eval7.handtype(eval7.evaluate(cs))), 0)
    except Exception:
        return 0


def _board_danger(board):
    danger = set()
    if len(board) < 3:
        return danger
    suits = [c[1] for c in board]
    if max(suits.count(s) for s in set(suits)) >= 3:
        danger.add("flush")
    ranks = [c[0] for c in board]
    if len(set(ranks)) < len(ranks):
        danger.add("boat")
    vals = sorted({RANK_VAL[r] for r in ranks})
    if 14 in vals:
        vals = sorted(set(vals) | {1})
    for i in range(len(vals)):
        if len([v for v in vals if vals[i] <= v <= vals[i] + 4]) >= 3:
            danger.add("straight")
            break
    return danger


def _vulnerable(my_rank, danger):
    if "flush" in danger and my_rank < HANDRANK["Flush"]:
        return True
    if "boat" in danger and my_rank <= HANDRANK["Trips"]:
        return True
    if "straight" in danger and my_rank < HANDRANK["Straight"]:
        return True
    return False


def _board_condition_range(opp_combos, board, bet_ratio):
    if len(board) < 3 or len(opp_combos) <= 8:
        return opp_combos
    if   bet_ratio >= 1.0: keep = 0.40
    elif bet_ratio >= 0.7: keep = 0.55
    elif bet_ratio >= 0.4: keep = 0.72
    else:                  keep = 0.90
    bd = [eval7.Card(c) for c in board]
    def rank(c):
        return eval7.evaluate([eval7.Card(c[0]), eval7.Card(c[1])] + bd)
    ranked = sorted(opp_combos, key=rank, reverse=True)
    return ranked[:max(8, int(len(ranked) * keep))]


OPP = defaultdict(lambda: {
    "actions": 0, "raises": 0, "calls": 0, "folds": 0, "checks": 0,
    "pf_raises": 0, "pf_voluntary": 0, "pf_actions": 0,
    "post_raises": 0, "post_actions": 0,
    "hands_seen": set(),
})

SEEN = set()


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
    _absorb_advanced(log)


def estimate_opp_tightness(bid):
    """0 = loose/aggressive, 1 = tight/passive. 0.5 = uninformative."""
    s = OPP.get(bid)
    if not s or s["actions"] < 6:
        return 0.5
    raise_freq = s["raises"] / max(1, s["actions"])
    fold_freq = s["folds"] / max(1, s["actions"])
    tightness = 0.5 + 0.5 * fold_freq - 0.5 * raise_freq
    return max(0.05, min(0.95, tightness))


# --- Per-opponent reads (3-bet / c-bet / fold-to-pressure / aggression) ------
# The catch: the log only gives voluntary actions — {hand_num, seat, bot_id,
# action, amount}, no blinds, no street labels, no pot, and only the last ~200
# entries. So to get street-specific stats like fold-to-3bet I replay each
# finished hand and work out the streets from the betting itself. Every stat
# defaults to a neutral guess and only kicks in once there's a real sample, so the
# rough edges on limped or half-logged pots don't matter.

PROCESSED_HANDS = set()


def _absorb_advanced(log):
    by_hand = defaultdict(list)
    for e in log:
        by_hand[e.get("hand_num", 0)].append(e)
    if not by_hand:
        return
    max_h = max(by_hand)
    for h in by_hand:
        if h in PROCESSED_HANDS or h >= max_h:
            continue  # skip already-processed hands and the in-progress latest hand
        _process_hand(by_hand[h])
        PROCESSED_HANDS.add(h)


def _process_hand(acts):
    """Reconstruct streets for one completed hand and update OPP exploit stats."""
    street = 0            # 0=pre 1=flop 2=turn 3=river
    contrib = {}          # seat -> chips committed this street
    bet = 0               # current max contribution this street
    acted = set()
    folded = set()
    allin = set()
    # Full participant set (every seat that acts in the hand). Needed so a
    # betting round doesn't "close" prematurely right after the first actor —
    # blinds aren't in the stream, so we otherwise can't tell who is still to
    # act. With the full set, the round only closes once everyone still in has
    # matched the bet.
    participants = set(e.get("seat") for e in acts if e.get("seat") is not None)
    n_raises = 0          # voluntary raises this street so far
    pf_aggressor = None   # bot_id of last preflop raiser
    for e in acts:
        seat = e.get("seat")
        bid = e.get("bot_id")
        act = e.get("action")
        amt = e.get("amount") or 0
        if seat is None or bid is None or act is None:
            continue
        facing = contrib.get(seat, 0) < bet
        s = OPP[bid]

        if street == 0:
            if n_raises == 1 and facing:            # facing the open -> 3-bet spot
                s["tb_opp"] = s.get("tb_opp", 0) + 1
                if act in ("raise", "all_in"):
                    s["tb_made"] = s.get("tb_made", 0) + 1
            elif n_raises == 2 and facing:          # facing a 3-bet -> fold-to-3bet
                s["f3_opp"] = s.get("f3_opp", 0) + 1
                if act == "fold":
                    s["f3_fold"] = s.get("f3_fold", 0) + 1
            elif n_raises >= 3 and facing:          # facing a 4-bet+ -> fold-to-4bet
                # this is what lets me bluff-4bet safely later: only do it against
                # someone who's actually shown they'll fold to one
                s["f4_opp"] = s.get("f4_opp", 0) + 1
                if act == "fold":
                    s["f4_fold"] = s.get("f4_fold", 0) + 1
        elif street == 1:
            if bid == pf_aggressor and n_raises == 0 and not facing:   # c-bet spot
                s["cb_opp"] = s.get("cb_opp", 0) + 1
                if act in ("raise", "bet", "all_in"):
                    s["cb_made"] = s.get("cb_made", 0) + 1
            elif pf_aggressor is not None and bid != pf_aggressor and facing and n_raises >= 1:
                s["fc_opp"] = s.get("fc_opp", 0) + 1   # faced a flop bet (c-bet proxy)
                if act == "fold":
                    s["fc_fold"] = s.get("fc_fold", 0) + 1

        if act in ("raise", "bet", "all_in"):
            s["agg"] = s.get("agg", 0) + 1
        elif act == "call":
            s["cal"] = s.get("cal", 0) + 1

        # apply the action to the street state
        if act in ("raise", "bet", "all_in"):
            contrib[seat] = amt
            bet = max(bet, amt)
            n_raises += 1
            acted = {seat}
            if act == "all_in":
                allin.add(seat)
            if street == 0:
                pf_aggressor = bid
        elif act == "call":
            contrib[seat] = bet
            acted.add(seat)
        elif act == "check":
            acted.add(seat)
        elif act == "fold":
            folded.add(seat)
            acted.add(seat)

        rem = participants - folded - allin
        if rem and all(x in acted for x in rem) and all(contrib.get(x, 0) == bet for x in rem):
            street += 1
            contrib = {}
            bet = 0
            acted = set()
            n_raises = 0


def _ratio(num, den, default, min_den):
    return (num / den) if den >= min_den else default


def opp_threebet_freq(bid, default=0.10):
    """How often this opp re-raises preflop when facing a single open."""
    s = OPP.get(bid) or {}
    return _ratio(s.get("tb_made", 0), s.get("tb_opp", 0), default, 9)


def opp_fold_to_threebet(bid, default=0.55):
    """How often this opp folds to a 3-bet (informational; observed-only)."""
    s = OPP.get(bid) or {}
    return _ratio(s.get("f3_fold", 0), s.get("f3_opp", 0), default, 3)


def opp_fold_to_fourbet(bid, default=0.50):
    """How often this opponent folds to a 4-bet. I only bluff-4bet someone whose
    number here is high — i.e. who's proven they fold. Needs a fair few samples
    (4-bet spots are rare) and defaults neutral, so the bluff stays off until then."""
    s = OPP.get(bid) or {}
    return _ratio(s.get("f4_fold", 0), s.get("f4_opp", 0), default, 6)


def opp_cbet_freq(bid, default=0.55):
    s = OPP.get(bid) or {}
    return _ratio(s.get("cb_made", 0), s.get("cb_opp", 0), default, 3)


def opp_fold_to_cbet(bid, default=0.45):
    s = OPP.get(bid) or {}
    return _ratio(s.get("fc_fold", 0), s.get("fc_opp", 0), default, 7)


def opp_af(bid, default=2.0):
    """Aggression factor (raise+bet+allin)/call. <1 ~ station, >3 ~ maniac."""
    s = OPP.get(bid) or {}
    agg, cal = s.get("agg", 0), s.get("cal", 0)
    if agg + cal < 6:
        return default
    return agg / max(1, cal)


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


def _identify_opponents(state):
    """Return (primary_bid, is_raiser, is_caller). Most recent raiser, or
    first active caller, or None."""
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


def _safe_preflop_raise(amount, stack, bet_this):
    """Preflop raise cap.  Never preflop-raise to more than 0.85x of
    effective stack: that's the safety net that prevents the Q1
    a4da672f-style full-stack shoves. If we genuinely want to shove
    preflop, the short-stack premium branch uses action=all_in
    explicitly.
    """
    effective = stack + bet_this
    hard_cap = max(BB, int(effective * 0.85))
    return min(effective, amount, hard_cap)


def _safe_postflop_raise(amount, stack, bet_this):
    """Postflop raise cap.  Strong hands can and should extract max
    value, so we only cap at effective stack — no 85 % guardrail
    here. The Q1 all-in spiral was a preflop pattern, not postflop.
    """
    return min(stack + bet_this, amount)


def _preflop_decision(state, opp_tight, primary_bid):
    """Preflop branch. Returns the action dict."""
    hole = state["your_cards"]
    pot = state["pot"]
    owed = state["amount_owed"]
    stack = state["your_stack"]
    can_check = state["can_check"]
    bet_this = state["your_bet_this_street"]
    min_raise = state["min_raise_to"]
    current_bet = state["current_bet"]

    eq = preflop_equity(hole)
    effective_stack = stack + bet_this  # chips at risk
    bb_remaining = max(1, effective_stack / BB)

    n_raises = sum(1 for e in (state.get("action_log") or [])
                   if e.get("action") in ("raise", "all_in"))

    # Position: how many active players still have to act behind me this orbit
    # (excluding me). Fewer behind means later position — under-the-gun is ~5, the
    # button ~1-2. No seat arithmetic, just who hasn't acted yet.
    _acted = set(e.get("seat") for e in (state.get("action_log") or [])
                 if e.get("action") not in ("small_blind", "big_blind", "post"))
    _my_seat = state.get("seat_to_act")
    n_behind = sum(1 for p in state["players"]
                   if p.get("state") == "active" and p.get("seat") != _my_seat
                   and p.get("seat") not in _acted)

    short_stack = bb_remaining < 25

    if short_stack and eq >= 0.70 and effective_stack <= 15 * BB:
        return {"action": "all_in"}

    if n_raises == 0:
        if can_check:
            iso_thresh = 0.55
            if eq >= iso_thresh:
                target = max(min_raise, int(pot * 1.2))
                return {"action": "raise", "amount": _safe_preflop_raise(target, stack, bet_this)}
            return {"action": "check"}
        open_thresh = 0.50 - 0.10 * (1 - opp_tight)
        # open a wider range in late position, tighter up front.
        open_thresh += 0.015 * (n_behind - 2)
        open_thresh = max(0.42, min(0.62, open_thresh))
        if eq >= open_thresh:
            target = max(min_raise, int(pot * 2.5))
            return {"action": "raise", "amount": _safe_preflop_raise(target, stack, bet_this)}
        return {"action": "fold"}

    if n_raises == 1:
        bet_ratio = owed / max(1, pot)
        # Facing a single open — this is where the edge lives. The field folds to
        # 3-bets far more than it should, and my earlier bots just flat-called and
        # never punished it. So 3-bet a real value range, plus the odd blocker bluff
        # from position; medium hands still flat or set-mine. If someone 4-bets back,
        # the n_raises>=2 branch below deals with it.
        three_thresh = 0.64 - 0.07 * (1 - opp_tight)   # was 0.70: more value 3-bets
        if bet_ratio <= 0.5:
            call_thresh = 0.48 - 0.08 * (1 - opp_tight)
            call_max_ratio = 0.5
        else:
            call_thresh = 0.55 - 0.08 * (1 - opp_tight)
            call_max_ratio = 0.65

        in_position = (n_behind == 0)
        has_blocker = hole[0][0] in ("A", "K") or hole[1][0] in ("A", "K")

        if eq >= three_thresh:                       # value 3-bet (wider)
            target = max(min_raise, int(current_bet * 3))
            return {"action": "raise", "amount": _safe_preflop_raise(target, stack, bet_this)}
        if (in_position and has_blocker and 0.45 <= eq < three_thresh
                and owed <= pot * 1.2 and random.random() < 0.30):   # 3-bet bluff
            target = max(min_raise, int(current_bet * 3))
            return {"action": "raise", "amount": _safe_preflop_raise(target, stack, bet_this)}
        if eq >= call_thresh and bet_ratio <= call_max_ratio:
            return {"action": "call"}
        # Set-mine: just call with a small pair against a single open when it's
        # cheap and we're deep. You flop a set about 1 in 8.5, and when you do it's
        # often worth someone's whole stack.
        is_pair = len(hole) >= 2 and hole[0][0] == hole[1][0]
        if (is_pair and bb_remaining >= 22 and owed <= 0.06 * effective_stack
                and owed <= pot * 1.2):
            return {"action": "call"}
        return {"action": "fold"}

    # Facing a 3-bet or 4-bet (n_raises >= 2). My old bot folded almost everything
    # here and got bullied — the strong bots noticed and 3-bet me relentlessly. The
    # fix is to value-4-bet a wider range (AK included): it folds a lot out and still
    # has equity when called. The 4-bet *bluff* is the disciplined part — it only
    # fires against someone who's proven they over-fold to 4-bets, never on a hunch.
    # Never 5-bet-bluff (n_raises >= 3 is premiums only), every bluff folds to a
    # shove, and only the genuine top of my range (eq >= 0.78) stacks off.
    tb = opp_threebet_freq(primary_bid)
    f4 = opp_fold_to_fourbet(primary_bid)
    in_position = (n_behind == 0)
    r1, r2 = hole[0][0], hole[1][0]
    has_blocker = r1 in ("A", "K") or r2 in ("A", "K")
    is_AK = {r1, r2} == {"A", "K"}
    big_bet = owed > pot or owed > 0.5 * (stack + bet_this)   # jam / heavy commit

    # Facing a 4-bet+ (we likely already 3-bet): premiums only — NEVER 5-bet-bluff.
    if n_raises >= 3:
        if eq >= 0.80:
            if big_bet:
                return {"action": "call"}
            target = max(min_raise, int(current_bet * 2.2))
            return {"action": "raise", "amount": _safe_preflop_raise(target, stack, bet_this)}
        if eq >= 0.74 and owed <= pot * 0.7:
            return {"action": "call"}
        return {"action": "fold"}

    # Facing exactly a 3-bet (the standard 4-bet spot).
    if eq >= 0.78:                                    # premium: stack off any size
        if big_bet:
            return {"action": "call"}
        target = max(min_raise, int(current_bet * 2.3))
        return {"action": "raise", "amount": _safe_preflop_raise(target, stack, bet_this)}
    if (eq >= 0.70 or is_AK) and not big_bet:        # value 4-bet (incl. AK blockers)
        target = max(min_raise, int(current_bet * 2.3))
        return {"action": "raise", "amount": _safe_preflop_raise(target, stack, bet_this)}
    # 4-bet bluff, gated hard: only against an opponent who's actually folded to
    # 4-bets before (f4 >= 0.55, after at least 6 such spots). An earlier version
    # also fired this just for being in position against a frequent 3-bettor, on the
    # assumption the field folds ~88% to 4-bets. It doesn't — it's more like 40% —
    # so that bluff just bled chips and I cut it. With the fold-history gate it stays
    # off against the normal field and only wakes up for a demonstrable pushover.
    # Folds to a shove either way.
    if (has_blocker and 0.47 <= eq < 0.66 and not big_bet and owed <= pot * 1.0
            and f4 >= 0.55 and random.random() < 0.5):
        target = max(min_raise, int(current_bet * 2.2))
        return {"action": "raise", "amount": _safe_preflop_raise(target, stack, bet_this)}
    if tb >= 0.20 and eq >= 0.56 and owed <= pot * 0.7:  # equity-call vs proven light 3-bettor
        return {"action": "call"}
    if eq >= 0.66 and owed <= pot * 0.7:             # premium flat behind
        return {"action": "call"}
    return {"action": "fold"}


def _postflop_decision(state, primary_bid, is_raiser, is_caller):
    """Postflop branch."""
    hole = state["your_cards"]
    board = state["community_cards"]
    pot = state["pot"]
    owed = state["amount_owed"]
    stack = state["your_stack"]
    can_check = state["can_check"]
    bet_this = state["your_bet_this_street"]
    min_raise = state["min_raise_to"]
    current_bet = state["current_bet"]
    my_seat = state["seat_to_act"]

    opp_range_classes = opp_range(primary_bid, is_raiser, is_caller)
    opp_combos = expand_combos(opp_range_classes,
                               blocked=set(hole) | set(board))
    # Re-rank the opponent's range on the actual board (not just its preflop
    # strength) before measuring equity against it.
    if owed > 0:
        bet_ratio = owed / max(1, pot)
        opp_combos = _board_condition_range(opp_combos, board, bet_ratio)

    eq = equity_vs_range(hole, board, opp_combos, n_trials=160)

    # Board-texture commitment brake.
    my_rank = _made_rank(hole, board)
    danger = _board_danger(board)
    vulnerable = _vulnerable(my_rank, danger)
    commit_frac = owed / max(1, stack + bet_this)
    big_commit = (owed > pot) or (commit_frac > 0.45)

    n_active = sum(1 for p in state["players"]
                   if p["state"] == "active" and p["seat"] != my_seat)
    if n_active > 1:
        # Multiway discount: shrink my equity when more than one opponent is still
        # in. Beating one random hand is easy; beating three at once is a lot harder,
        # and the raw number badly overstates how often I'm actually winning.
        eq = eq ** (1 + 0.35 * (n_active - 1))

    odds_needed = owed / max(1, pot + owed)

    # Now lean on the opponent read. Until there's a real sample these sit at
    # neutral defaults (af=2.0, fc=0.45), so against an unknown opponent this plays
    # like a plain solid bot; it only starts adjusting once I've seen them act.
    af = opp_af(primary_bid)
    fc = opp_fold_to_cbet(primary_bid)
    station = af < 1.0          # passive caller: never bluff; value thinner + bigger
    overfolder = fc >= 0.60     # folds to c-bets: barrel more

    if can_check:
        if eq >= 0.75 or (station and eq >= 0.62):       # value (thinner vs stations)
            ot = estimate_opp_tightness(primary_bid) if primary_bid else 0.5
            size_frac = 0.75 if (ot > 0.5 and not station) else 1.0
            if vulnerable:
                size_frac = min(size_frac, 0.5)
            size = max(min_raise, int(pot * size_frac))
            return {"action": "raise", "amount": _safe_postflop_raise(size, stack, bet_this)}
        # How often to (semi-)bluff: never into a calling station, more often
        # against someone who folds too much, normal otherwise.
        semibluff_p = 0.0 if station else (0.55 if overfolder else 0.4)
        bluff_p = 0.0 if station else (0.22 if overfolder else 0.12)
        # Heads-up on a dry board, take the betting lead far more often. My earlier
        # bots checked ~80% of flops as the preflop raiser and handed the pot to
        # anyone who stabbed at it. So c-bet a lot more — but only heads-up, only on
        # boards that aren't scary, and never into a calling station, which is
        # exactly where a stab actually wins the pot.
        hu_dry = (n_active == 1 and not danger and not station)
        if hu_dry:
            semibluff_p = max(semibluff_p, 0.80)   # eq>=0.55 -> almost always bet
            bluff_p = max(bluff_p, 0.50)           # eq<0.30  -> bluff far more
            # also bet the medium hands (the 0.45-0.75 "check and give up" zone)
            # small, instead of checking and folding the pot away.
            if 0.45 <= eq < 0.75 and not vulnerable and random.random() < 0.65:
                size = max(min_raise, int(pot * 0.4))
                return {"action": "raise", "amount": _safe_postflop_raise(size, stack, bet_this)}
        # ---------------------------------------------------------------------
        if eq >= 0.55 and random.random() < semibluff_p:
            size = max(min_raise, int(pot * 0.5))
            return {"action": "raise", "amount": _safe_postflop_raise(size, stack, bet_this)}
        if eq < 0.30 and not danger and random.random() < bluff_p:
            size = max(min_raise, int(pot * 0.66))
            return {"action": "raise", "amount": _safe_postflop_raise(size, stack, bet_this)}
        return {"action": "check"}

    # Facing a bet. Don't raise/re-raise a vulnerable made hand into a big commitment.
    if eq >= 0.78 and not (vulnerable and big_commit):
        size = max(min_raise, int(pot * 1.0) + current_bet)
        return {"action": "raise", "amount": _safe_postflop_raise(size, stack, bet_this)}

    call_buffer = 0.02
    if eq >= odds_needed + call_buffer:
        bet_ratio = owed / max(1, pot)
        if eq < 0.30 and bet_ratio > 1.5:
            return {"action": "fold"}
        # Don't call off a large stack fraction with a hand the obvious nuts beat.
        if big_commit and vulnerable and eq < odds_needed + 0.12:
            return {"action": "fold"}
        return {"action": "call"}
    return {"action": "fold"}


def _decide_inner(state):
    absorb_log(state)
    primary_bid, is_raiser, is_caller = _identify_opponents(state)
    opp_tight = estimate_opp_tightness(primary_bid) if primary_bid else 0.5

    if state["street"] == "preflop":
        return _preflop_decision(state, opp_tight, primary_bid)
    return _postflop_decision(state, primary_bid, is_raiser, is_caller)


def decide(state):
    """Engine-visible entry point. Must never raise."""
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
