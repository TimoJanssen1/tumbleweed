"""Calibrated FINALIST over-folder — models the measured Q2 top-64 aggregate.

Built from MY independent analysis of the 40 real Q2 matches (handoff package/
matchhistoryq2): the top-64 field opens ~41%, 3-bets ~7%, **folds ~93% of its
opens to a 3-bet and ~88% to a 4-bet**, c-bets ~54%, folds-to-c-bet ~24%, AF ~3.6.
That over-folding to preflop re-raises is the field's defining, exploitable trait
and is exactly what v21/v22 never punished. This bot reproduces it so the
benchmark can MEASURE the EV of v23's 3-bet/4-bet pressure (the sim field of
"realistic" bots can't, because it doesn't over-fold — see CODER_HANDOFF §11).

NOT used as a real opponent / not hardcoded into the submission — a validation
instrument only. Fast (no MC). BOT_NAME is overwritten per-instance.
"""
import random

BOT_NAME = "FinalistOverfolder3"
HIGH = {r: v for v, r in enumerate("23456789TJQKA", start=2)}


def _strength(hole):
    """Cheap 0..1 preflop strength percentile-ish (no MC)."""
    a, b = sorted((HIGH[hole[0][0]], HIGH[hole[1][0]]), reverse=True)
    suited = hole[0][1] == hole[1][1]
    if a == b:                                   # pair: 22->0.50 .. AA->1.0
        return 0.50 + (a - 2) / 12.0 * 0.50
    s = (a * 0.62 + b * 0.38) / 14.0 * 0.66      # high-card weighted
    gap = a - b
    if gap == 1:
        s += 0.05
    elif gap == 2:
        s += 0.02
    if suited:
        s += 0.06
    return min(0.99, s)


def _made(hole, board):
    """0=high card .. 7=quads, via eval7 if available; else crude."""
    try:
        import eval7
        cs = [eval7.Card(c) for c in hole] + [eval7.Card(c) for c in board]
        names = {"High Card": 0, "Pair": 1, "Two Pair": 2, "Trips": 3, "Straight": 4,
                 "Flush": 5, "Full House": 6, "Quads": 7, "Straight Flush": 8}
        return names.get(str(eval7.handtype(eval7.evaluate(cs))), 0)
    except Exception:
        ranks = [c[0] for c in hole] + [c[0] for c in board]
        return 1 if len(ranks) != len(set(ranks)) else 0


def decide(state):
    if state.get("type") == "warmup":
        return {"action": "fold"}
    try:
        if "your_cards" not in state or len(state["your_cards"]) < 2:
            return {"action": "fold"}
        return _inner(state)
    except Exception:
        return {"action": "check"} if state.get("can_check") else {"action": "fold"}


def _inner(state):
    hole = state["your_cards"]
    board = state.get("community_cards") or []
    pot = state["pot"]
    owed = state["amount_owed"]
    stack = state["your_stack"]
    can_check = state["can_check"]
    bet_this = state["your_bet_this_street"]
    min_raise = state["min_raise_to"]
    al = state.get("action_log") or []
    my_seat = state.get("seat_to_act")
    n_raises = sum(1 for e in al if e.get("action") in ("raise", "all_in"))
    we_raised = any(e.get("seat") == my_seat and e.get("action") in ("raise", "all_in")
                    for e in al)

    def raise_to(x):
        return {"action": "raise", "amount": min(stack + bet_this, max(min_raise, int(x)))}

    if state["street"] == "preflop":
        s = _strength(hole)
        if n_raises == 0:
            if can_check:                                  # BB option
                return raise_to(pot * 2) if s >= 0.78 else {"action": "check"}
            return raise_to(pot * 2.0) if s >= 0.50 else {"action": "fold"}   # open ~40%
        if n_raises == 1 and not we_raised:                # facing a single open
            if s >= 0.82:
                return raise_to(state["current_bet"] * 3)  # 3-bet ~top
            if s >= 0.62 and owed <= pot * 0.6:
                return {"action": "call"}
            return {"action": "fold"}
        if we_raised and n_raises >= 2:                    # WE opened, face a 3-bet/4-bet
            # THE calibrated trait: fold ~90% to a 3-bet, ~88% to a 4-bet.
            thresh = 0.86 if n_raises == 2 else 0.90
            if s >= thresh:
                return {"action": "call"} if owed > pot else raise_to(state["current_bet"] * 2.2)
            return {"action": "fold"}
        # we 3-bet and face a 4-bet, or other multi-raise: premiums only
        if s >= 0.88 and owed <= pot:
            return {"action": "call"}
        return {"action": "fold"}

    # postflop
    made = _made(hole, board)
    if can_check:
        if we_raised and random.random() < 0.54:           # c-bet ~54% as aggressor
            return raise_to(pot * 0.5)
        # STAB/float into a check when we're NOT the aggressor — this is the real
        # field's defining 2nd trait (AF 3.6): it PUNISHES a passive checker. A
        # bot that checks 80% of flops (v21/v22) bleeds here; one that takes the
        # lead (v23) denies it. Without this the field can't reward fixing passivity.
        if not we_raised and random.random() < 0.45:
            return raise_to(pot * 0.5)
        if made >= 2 and random.random() < 0.6:
            return raise_to(pot * 0.6)
        return {"action": "check"}
    ratio = owed / max(1, pot)
    if made >= 3:
        return raise_to(pot * 0.8 + state["current_bet"]) if ratio <= 0.7 else {"action": "call"}
    if made == 2:
        return {"action": "call"} if ratio <= 1.0 else {"action": "fold"}
    if made == 1:
        return {"action": "call"} if ratio <= 0.45 else {"action": "fold"}
    if random.random() < 0.24 and ratio <= 0.4:            # fold-to-cbet ~24% sticky floats
        return {"action": "call"}
    return {"action": "fold"}
