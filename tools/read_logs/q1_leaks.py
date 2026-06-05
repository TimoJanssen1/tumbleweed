"""Q1 post-mortem analyzer for Tumble-Weed.

Walks every match in `match history/`, identifies Tumble-Weed's seat,
replays every hand and records what TW did at each decision point.

Outputs:
  - Per-round / per-stack / per-phase action mix
  - Bust-hand catalogue (what was the final hand of each match we busted in)
  - Big-loss-hand catalogue (single hands where TW lost >= 5k)
  - Per-street action mix
  - Position-tagged action mix (open vs facing-raise vs in BB etc.)
  - Action-vs-stack-depth breakdown (deep / mid / short)

Reads:   match history/*.json
Writes:  prints a report to stdout. Also dumps a CSV at
         analysis/q1_postmortem_decisions.csv with one row per TW decision.
"""

from __future__ import annotations

import csv
import glob
import json
import os
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Iterable

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MATCH_DIR = os.path.join(ROOT, "match history")
OUT_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "q1_postmortem_decisions.csv")

TW_NAME = "Tumble-Weed"
STARTING_STACK = 10000
BB = 100
SB = 50

BLIND_ACTIONS = {"small_blind", "big_blind", "post"}
DECISION_ACTIONS = {"fold", "check", "call", "raise", "all_in", "bet"}


@dataclass
class Decision:
    match_id: str
    round_num: int | None
    hand_num: int
    street: str
    seat: int
    n_active_at_decision: int
    pot_before: int
    amount_to_call: int  # chips owed to continue
    my_bet_this_street: int
    my_stack: int  # before this decision
    n_raises_this_street: int  # count of raise/all_in actions before me on this street
    n_callers_this_street: int  # call actions before me on this street
    action: str
    amount: int
    is_aggression: bool  # raise or bet or all_in
    is_call: bool
    is_fold: bool
    is_check: bool
    facing_bet: bool
    open_opportunity: bool  # n_raises == 0 and we aren't in BB with no raises
    in_blind: bool
    hand_class: str | None  # if hole cards revealed
    hole_cards: str | None
    revealed: bool
    chip_delta_this_hand: int  # at hand end
    bust_hand: bool


def load_match(fp: str) -> dict:
    with open(fp) as f:
        return json.load(f)


def find_tw(bots: list[dict]) -> tuple[int | None, str | None]:
    """Return (seat, bot_id) for TW in this match, or (None, None)."""
    for b in bots:
        if b.get("bot_name") == TW_NAME:
            return b.get("seat"), b.get("bot_id")
    return None, None


STREET_ORDER = ["preflop", "flop", "turn", "river"]


def replay_hand(hand: dict, tw_seat: int, tw_bot_id: str | None,
                pre_stack: dict[int, int]) -> tuple[list[Decision], dict[int, int]]:
    """Replay a single hand.

    Returns (TW decisions list, post-hand stacks dict).
    `pre_stack` maps seat -> stack at hand start.
    """
    decisions: list[Decision] = []
    log = hand.get("action_log") or []
    board = hand.get("community_cards") or []

    # Map streets by counting community cards: 0 -> preflop, 3 -> flop, 4 -> turn, 5 -> river.
    # We walk the action log, tracking which street each action is on. The engine emits
    # streets in order; community_cards is the final board, so we infer the street boundary
    # from the action sequence and pot evolution. Simpler approach: street boundaries
    # are wherever a check or non-blind action follows a non-blind action without the
    # required amount changing. The most reliable signal is: each street has its own
    # contribution slate. We'll approximate by tracking voluntary contributions per street.

    # Robust street tracker: each "street" has a current_bet (max bet faced on this
    # street) and per-seat contribution. A street ends when all remaining players
    # have matched. We walk and track this.
    current_street = 0  # 0=pre, 1=flop, 2=turn, 3=river
    street_contrib = defaultdict(int)  # seat -> chips this street
    current_bet = 0
    active_seats = set()  # who is still in the hand (not folded, not all-in 0)
    initial_stacks = dict(pre_stack)  # seat -> stack at hand start
    cur_stack = dict(initial_stacks)
    # Find who participated (all seats that have any action or blind)
    for a in log:
        active_seats.add(a["seat"])

    folded = set()
    last_aggressor = None
    pf_first_raise_done = False

    def street_name(s: int) -> str:
        return STREET_ORDER[s] if 0 <= s < 4 else "unknown"

    # Compute revealed cards for TW (if shown at showdown)
    rev = hand.get("revealed_cards") or {}
    tw_hole = None
    if tw_bot_id and tw_bot_id in rev:
        tw_hole = rev[tw_bot_id]
    # Some matches put it by seat or name — try other keys
    if tw_hole is None:
        # try seat-based
        if str(tw_seat) in rev:
            tw_hole = rev[str(tw_seat)]

    def is_new_street(action: str, amount: int) -> bool:
        return False  # handled inline below

    # Track preflop blinds first to seed contributions
    blinds_done = False
    i = 0
    n = len(log)
    while i < n:
        a = log[i]
        seat = a["seat"]
        act = a["action"]
        amt = a["amount"]

        # Apply blinds: just contribute, don't advance street
        if act in BLIND_ACTIONS:
            street_contrib[seat] += amt
            cur_stack[seat] = cur_stack.get(seat, STARTING_STACK) - amt
            if amt > current_bet:
                current_bet = amt
            i += 1
            continue

        # Detect street boundary BEFORE recording this action. The engine emits actions
        # in street order; a street ends when everyone owing has matched/folded. We
        # peek: if the previous action closed the street (all active seats have equal
        # contribution and at least one check happened or all bets are matched), and
        # the current action is from someone who was first-to-act on the new street,
        # we increment. The simplest reliable signal is: when the current action is a
        # `check` and current_bet for this street is 0 from someone who has 0 contrib —
        # we're at a new street. Or: when an action's seat has 0 contribution this
        # street but current_bet > 0 from previous street — new street started.
        #
        # Instead of guessing, use the fact that `street_ended` tells us where the hand
        # finished. And we can detect street boundaries by checking: between actions,
        # if the action sequence "closes" (all active non-folded seats have matched),
        # the NEXT action starts a new street.

        # Record TW's decision BEFORE applying it
        if seat == tw_seat and seat not in folded:
            n_active = sum(1 for s in active_seats if s not in folded)
            owed = max(0, current_bet - street_contrib[seat])

            # Count raises this street so far (before this decision)
            n_raises_this_street = 0
            n_callers_this_street = 0
            for j in range(i - 1, -1, -1):
                prev = log[j]
                if prev["action"] in BLIND_ACTIONS:
                    break
                # We don't know exactly when street starts — approximate by walking back
                # until contribution suggests start. For simplicity here, just count
                # forward in current_street block. We'll do a forward pass instead.
                break
            # Forward pass: walk from start of current street
            # Find start of current street by scanning back from i
            street_start = 0
            contrib_seen = defaultdict(int)
            running_current_bet = 0
            running_contrib = defaultdict(int)
            running_bet = 0
            # Walk from 0 to i-1, advancing streets when street closes
            cs = 0
            cs_contrib = defaultdict(int)
            cs_bet = 0
            cs_active = set(active_seats)
            cs_folded = set()
            for j in range(i):
                pa = log[j]
                ps = pa["seat"]
                pact = pa["action"]
                pamt = pa["amount"]
                if pact in BLIND_ACTIONS:
                    cs_contrib[ps] += pamt
                    if pamt > cs_bet:
                        cs_bet = pamt
                    continue
                # Apply action
                if pact == "fold":
                    cs_folded.add(ps)
                elif pact == "check":
                    pass
                elif pact == "call":
                    add = pamt  # 'amount' on call is the chips added
                    cs_contrib[ps] += add
                elif pact in ("raise", "bet", "all_in"):
                    # `amount` on raise = total bet on this street (to-amount)
                    # all_in's amount might be the chip add. Inspect by comparing.
                    target = pamt
                    cs_contrib[ps] = target
                    if target > cs_bet:
                        cs_bet = target
                # Check street closure: all active non-folded seats have contributed >= cs_bet
                # and at least one non-blind action happened. We use a simpler heuristic:
                # if there was a check from the BB after callers, or after a raise everyone
                # called/folded, the street closes. We approximate by: after each action,
                # check if all (active - folded) seats have contrib == cs_bet AND last
                # action was not a check that opens decision to next player.
                still_in = cs_active - cs_folded
                if still_in and all(cs_contrib.get(s, 0) == cs_bet for s in still_in):
                    # Street might be closed; we'd advance. But for accuracy we need
                    # to know if next action is on the next street. Cheap signal: if
                    # next action's seat has lower contrib in cs_contrib (i.e. starts
                    # fresh), street advanced.
                    if j + 1 < len(log):
                        nxt = log[j + 1]
                        nxt_seat = nxt["seat"]
                        nxt_act = nxt["action"]
                        if nxt_act not in BLIND_ACTIONS:
                            # If next action is a check or call with 0 owed, OR a bet/raise
                            # to fresh amount, and this seat already matched cs_bet — likely new street.
                            if nxt_act == "check" or (nxt_act in ("bet", "raise", "all_in") and pact in ("call", "check")):
                                cs += 1
                                cs_contrib = defaultdict(int)
                                cs_bet = 0

            # Now cs is the street index AT action i
            decision_street = STREET_ORDER[cs] if cs < 4 else "unknown"
            n_raises = sum(1 for k in range(i) if log[k]["action"] in ("raise", "all_in", "bet")
                           and (cs_at_action(log, k) == cs))
            n_callers = sum(1 for k in range(i) if log[k]["action"] == "call"
                            and cs_at_action(log, k) == cs)

            facing_bet = owed > 0
            in_blind = (cs == 0 and seat in (0, 1))  # approximate; correct seat is later
            open_opp = (cs == 0 and n_raises == 0)
            is_agg = act in ("raise", "all_in", "bet")
            is_call = act == "call"
            is_fold = act == "fold"
            is_check = act == "check"

            decisions.append(Decision(
                match_id="",
                round_num=None,
                hand_num=hand.get("hand_num", -1),
                street=decision_street,
                seat=seat,
                n_active_at_decision=n_active,
                pot_before=sum(cs_contrib.values()),
                amount_to_call=owed,
                my_bet_this_street=cs_contrib.get(seat, 0),
                my_stack=cur_stack.get(seat, STARTING_STACK),
                n_raises_this_street=n_raises,
                n_callers_this_street=n_callers,
                action=act,
                amount=amt,
                is_aggression=is_agg,
                is_call=is_call,
                is_fold=is_fold,
                is_check=is_check,
                facing_bet=facing_bet,
                open_opportunity=open_opp,
                in_blind=in_blind,
                hand_class=hand_class_str(tw_hole) if tw_hole else None,
                hole_cards=" ".join(tw_hole) if tw_hole else None,
                revealed=bool(tw_hole),
                chip_delta_this_hand=0,  # filled later
                bust_hand=False,  # filled later
            ))

        # Apply the action to our running state
        if act == "fold":
            folded.add(seat)
        elif act == "call":
            street_contrib[seat] += amt
            cur_stack[seat] -= amt
        elif act in ("raise", "bet", "all_in"):
            # raise amount semantics: 'amount' is the new total bet target on this street
            # so chips added = target - current contrib
            target = amt
            add = target - street_contrib[seat]
            street_contrib[seat] += add
            cur_stack[seat] -= add
            if target > current_bet:
                current_bet = target

        i += 1

    return decisions, cur_stack


def cs_at_action(log: list[dict], idx: int) -> int:
    """Recompute current street at log index `idx`. Best-effort heuristic.

    Walks from 0..idx-1 and detects street boundaries by closure: when all
    non-folded seats have matched the current bet, the next non-blind action
    that starts at 0-contribution begins the next street.
    """
    cs = 0
    cs_contrib = defaultdict(int)
    cs_bet = 0
    active = set(a["seat"] for a in log)
    folded = set()
    for j in range(idx):
        pa = log[j]
        ps = pa["seat"]
        pact = pa["action"]
        pamt = pa["amount"]
        if pact in BLIND_ACTIONS:
            cs_contrib[ps] += pamt
            if pamt > cs_bet:
                cs_bet = pamt
            continue
        if pact == "fold":
            folded.add(ps)
        elif pact == "call":
            cs_contrib[ps] += pamt
        elif pact in ("raise", "bet", "all_in"):
            cs_contrib[ps] = pamt
            if pamt > cs_bet:
                cs_bet = pamt
        # Detect street close
        still_in = active - folded
        if still_in and all(cs_contrib.get(s, 0) == cs_bet for s in still_in):
            if j + 1 < len(log):
                nxt = log[j + 1]
                if nxt["action"] not in BLIND_ACTIONS:
                    if nxt["action"] == "check" or (nxt["action"] in ("bet", "raise", "all_in") and pact in ("call", "check")):
                        cs += 1
                        cs_contrib = defaultdict(int)
                        cs_bet = 0
    return cs


RANKS = "23456789TJQKA"
RANK_VAL = {r: i for i, r in enumerate(RANKS, start=2)}


def hand_class_str(hole: list[str] | None) -> str | None:
    if not hole or len(hole) < 2:
        return None
    r1, s1 = hole[0][0], hole[0][1]
    r2, s2 = hole[1][0], hole[1][1]
    if RANK_VAL[r1] < RANK_VAL[r2]:
        r1, r2 = r2, r1
        s1, s2 = s2, s1
    if r1 == r2:
        return f"{r1}{r2}"
    suf = "s" if s1 == s2 else "o"
    return f"{r1}{r2}{suf}"


def collect_decisions() -> tuple[list[Decision], dict]:
    """Walk all matches and return (decisions, match-level summary)."""
    files = sorted(glob.glob(os.path.join(MATCH_DIR, "*.json")))
    all_decisions: list[Decision] = []
    summary = {
        "n_matches": 0,
        "n_complete_with_hands": 0,
        "tw_participation": 0,
        "tw_chip_delta_total": 0,
        "tw_busted": 0,
        "tw_capped": 0,
        "per_round": defaultdict(lambda: {"n": 0, "delta": 0, "busted": 0, "capped": 0}),
        "per_stack_actions": defaultdict(lambda: Counter()),  # (stack_bucket) -> action counter
        "per_phase_actions": defaultdict(lambda: Counter()),
        "per_street_actions": defaultdict(lambda: Counter()),
        "bust_hands": [],
        "big_loss_hands": [],
        "big_win_hands": [],
    }

    for fp in files:
        d = load_match(fp)
        summary["n_matches"] += 1
        if d.get("status") != "complete" or not (d.get("hands") or []):
            continue
        summary["n_complete_with_hands"] += 1

        tw_seat, tw_bot_id = find_tw(d.get("bots") or [])
        if tw_seat is None:
            continue
        summary["tw_participation"] += 1

        tw_delta = None
        for b in d["bots"]:
            if b["seat"] == tw_seat:
                tw_delta = b.get("chip_delta")
                break
        if tw_delta is not None:
            summary["tw_chip_delta_total"] += tw_delta
            r = d.get("round")
            summary["per_round"][r]["n"] += 1
            summary["per_round"][r]["delta"] += tw_delta
            if tw_delta == -STARTING_STACK:
                summary["tw_busted"] += 1
                summary["per_round"][r]["busted"] += 1
            if tw_delta == 50000:
                summary["tw_capped"] += 1
                summary["per_round"][r]["capped"] += 1

        # Track running stack across the match
        seat_stack = {b["seat"]: STARTING_STACK for b in d["bots"]}
        n_hands = len(d["hands"])
        for h_idx, h in enumerate(d["hands"]):
            pre_stacks = dict(seat_stack)
            decisions, post_stacks = replay_hand(h, tw_seat, tw_bot_id, pre_stacks)
            # Compute TW chip delta this hand
            tw_pre = pre_stacks.get(tw_seat, STARTING_STACK)
            tw_post = post_stacks.get(tw_seat, tw_pre)
            # Add winnings if TW won
            for w in h.get("winners") or []:
                if w.get("bot_id") == tw_bot_id:
                    tw_post += w.get("amount", 0)
            hand_delta = tw_post - tw_pre
            seat_stack[tw_seat] = tw_post
            # Update other seats (best-effort: from final pot distributions)
            for s in seat_stack:
                if s == tw_seat:
                    continue
                seat_stack[s] = post_stacks.get(s, seat_stack[s])
                for w in h.get("winners") or []:
                    bot_at_seat = None
                    for b in d["bots"]:
                        if b["seat"] == s:
                            bot_at_seat = b["bot_id"]
                    if w.get("bot_id") == bot_at_seat:
                        seat_stack[s] += w.get("amount", 0)

            is_bust = (h_idx == n_hands - 1) and tw_delta == -STARTING_STACK
            for dec in decisions:
                dec.match_id = d["match_id"]
                dec.round_num = d.get("round")
                dec.chip_delta_this_hand = hand_delta
                dec.bust_hand = is_bust
                all_decisions.append(dec)
                stack_bucket = stack_bucket_name(dec.my_stack)
                phase = phase_name(dec.hand_num, n_hands)
                summary["per_stack_actions"][stack_bucket][dec.action] += 1
                summary["per_phase_actions"][phase][dec.action] += 1
                summary["per_street_actions"][dec.street][dec.action] += 1

            if hand_delta <= -5000:
                summary["big_loss_hands"].append((d["match_id"], h["hand_num"], hand_delta, h, tw_seat, tw_bot_id))
            if hand_delta >= 5000:
                summary["big_win_hands"].append((d["match_id"], h["hand_num"], hand_delta, h, tw_seat, tw_bot_id))

        # Identify the bust hand (last hand where TW had final_stack=0)
        if tw_delta == -STARTING_STACK and d["hands"]:
            last = d["hands"][-1]
            summary["bust_hands"].append((d["match_id"], last["hand_num"], last, tw_seat, tw_bot_id, d.get("round")))

    return all_decisions, summary


def stack_bucket_name(stack: int) -> str:
    if stack < 2000:
        return "ultra_short(<20bb)"
    if stack < 4000:
        return "short(20-40bb)"
    if stack < 7000:
        return "below_avg(40-70bb)"
    if stack < 13000:
        return "around_starting(70-130bb)"
    if stack < 25000:
        return "ahead(130-250bb)"
    return "very_ahead(250+bb)"


def phase_name(hand_num: int, n_hands: int) -> str:
    if hand_num < 0.25 * n_hands:
        return "early"
    if hand_num < 0.75 * n_hands:
        return "mid"
    return "late"


def write_csv(decisions: list[Decision]) -> None:
    with open(OUT_CSV, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "match_id", "round", "hand_num", "street", "seat",
            "n_active", "pot_before", "amount_to_call", "my_bet_this_street",
            "my_stack", "n_raises_this_street", "n_callers_this_street",
            "action", "amount", "facing_bet", "open_opp", "in_blind",
            "hand_class", "hole_cards", "revealed",
            "chip_delta_this_hand", "bust_hand",
        ])
        for d in decisions:
            w.writerow([
                d.match_id, d.round_num, d.hand_num, d.street, d.seat,
                d.n_active_at_decision, d.pot_before, d.amount_to_call, d.my_bet_this_street,
                d.my_stack, d.n_raises_this_street, d.n_callers_this_street,
                d.action, d.amount, d.facing_bet, d.open_opportunity, d.in_blind,
                d.hand_class, d.hole_cards, d.revealed,
                d.chip_delta_this_hand, d.bust_hand,
            ])


def print_report(decisions: list[Decision], summary: dict) -> None:
    n = len(decisions)
    print("=" * 78)
    print("Q1 POSTMORTEM — Tumble-Weed")
    print("=" * 78)
    print(f"Match files processed:       {summary['n_matches']}")
    print(f"Complete matches with hands: {summary['n_complete_with_hands']}")
    print(f"TW participated in:          {summary['tw_participation']}")
    print(f"TW cumulative chip-Δ:        {summary['tw_chip_delta_total']:+,}")
    print(f"TW busted matches:           {summary['tw_busted']}")
    print(f"TW capped (+50k) matches:    {summary['tw_capped']}")
    print()

    print("Per-round performance")
    print("-" * 78)
    for r in sorted(summary["per_round"].keys(), key=lambda x: (x is None, x)):
        s = summary["per_round"][r]
        print(f"  Round {r}: n={s['n']:>2}  Δ={s['delta']:+,}  busted={s['busted']}  capped={s['capped']}")
    print()

    if n == 0:
        print("No decisions parsed — abort report.")
        return

    print(f"Total TW decisions recorded: {n}")
    print()

    print("Action mix by street")
    print("-" * 78)
    for street in STREET_ORDER:
        c = summary["per_street_actions"][street]
        total = sum(c.values())
        if total == 0:
            continue
        bits = ", ".join(f"{a}={cnt} ({cnt/total*100:4.1f}%)" for a, cnt in sorted(c.items(), key=lambda x: -x[1]))
        print(f"  {street:8} (n={total:>5}): {bits}")
    print()

    print("Action mix by stack bucket")
    print("-" * 78)
    order = [
        "ultra_short(<20bb)", "short(20-40bb)", "below_avg(40-70bb)",
        "around_starting(70-130bb)", "ahead(130-250bb)", "very_ahead(250+bb)"
    ]
    for bucket in order:
        c = summary["per_stack_actions"][bucket]
        total = sum(c.values())
        if total == 0:
            continue
        bits = ", ".join(f"{a}={cnt} ({cnt/total*100:4.1f}%)" for a, cnt in sorted(c.items(), key=lambda x: -x[1]))
        print(f"  {bucket:26} (n={total:>5}): {bits}")
    print()

    print("Action mix by phase")
    print("-" * 78)
    for phase in ["early", "mid", "late"]:
        c = summary["per_phase_actions"][phase]
        total = sum(c.values())
        if total == 0:
            continue
        bits = ", ".join(f"{a}={cnt} ({cnt/total*100:4.1f}%)" for a, cnt in sorted(c.items(), key=lambda x: -x[1]))
        print(f"  {phase:6} (n={total:>5}): {bits}")
    print()

    # Focus on facing-bet decisions: where the binary fold/call decision lives
    facing = [d for d in decisions if d.facing_bet]
    print(f"Facing-bet decisions: {len(facing)} (where call vs fold tradeoff matters)")
    print("-" * 78)
    by_ratio_action = defaultdict(Counter)
    for d in facing:
        if d.pot_before <= 0:
            ratio = "?"
        else:
            r = d.amount_to_call / d.pot_before
            if r <= 0.33: ratio = "small (<= 1/3 pot)"
            elif r <= 0.66: ratio = "medium (1/3-2/3 pot)"
            elif r <= 1.1: ratio = "pot-sized"
            else: ratio = "overbet (>pot)"
        by_ratio_action[ratio][d.action] += 1
    for ratio in ["small (<= 1/3 pot)", "medium (1/3-2/3 pot)", "pot-sized", "overbet (>pot)"]:
        c = by_ratio_action.get(ratio, Counter())
        total = sum(c.values())
        if total == 0:
            continue
        bits = ", ".join(f"{a}={cnt} ({cnt/total*100:4.1f}%)" for a, cnt in sorted(c.items(), key=lambda x: -x[1]))
        print(f"  {ratio:22} (n={total:>4}): {bits}")
    print()

    # Biggest single-hand losses
    print("Top 10 single-hand losses")
    print("-" * 78)
    summary["big_loss_hands"].sort(key=lambda x: x[2])
    for mid, hn, delta, h, seat, bid in summary["big_loss_hands"][:10]:
        tw_actions = [a for a in h["action_log"] if a["seat"] == seat and a["action"] not in BLIND_ACTIONS]
        rev = (h.get("revealed_cards") or {}).get(bid, [])
        win = h.get("winners") or []
        win_summary = [(w.get("bot_id", "?")[:8], w.get("amount")) for w in win]
        print(f"  {mid[:8]} h{hn}: Δ={delta:+,}  board={h.get('community_cards')}  hole={rev}")
        print(f"    TW actions: {[(a['action'], a['amount']) for a in tw_actions]}")
        print(f"    Winners: {win_summary}")
    print()

    # Biggest single-hand wins
    print("Top 10 single-hand wins")
    print("-" * 78)
    summary["big_win_hands"].sort(key=lambda x: -x[2])
    for mid, hn, delta, h, seat, bid in summary["big_win_hands"][:10]:
        rev = (h.get("revealed_cards") or {}).get(bid, [])
        print(f"  {mid[:8]} h{hn}: Δ=+{delta:,}  board={h.get('community_cards')}  hole={rev}")
    print()

    # Bust hands
    print(f"Bust hands ({len(summary['bust_hands'])} total)")
    print("-" * 78)
    for mid, hn, h, seat, bid, rd in summary["bust_hands"]:
        tw_actions = [a for a in h["action_log"] if a["seat"] == seat and a["action"] not in BLIND_ACTIONS]
        rev = (h.get("revealed_cards") or {}).get(bid, [])
        print(f"  R{rd} {mid[:8]} h{hn}: board={h.get('community_cards')}  hole={rev}")
        print(f"    TW actions: {[(a['action'], a['amount']) for a in tw_actions]}")
    print()


def main():
    decisions, summary = collect_decisions()
    write_csv(decisions)
    print_report(decisions, summary)
    print(f"\nWrote {len(decisions)} decisions to {OUT_CSV}")


if __name__ == "__main__":
    main()
