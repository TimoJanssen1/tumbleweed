
"""Ultra Nit — weak-tier variant.

Tier: weak
Strategy: deliberately bad. Represents a template-tilt or single-rule bot
common in low-effort submissions.
Mode: ultra_nit
"""
import random
BOT_NAME = "Ultra Nit"
MODE = "ultra_nit"

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
    pot = state["pot"]
    owed = state["amount_owed"]
    stack = state["your_stack"]
    can_check = state["can_check"]
    bet_this = state["your_bet_this_street"]
    min_raise = state["min_raise_to"]

    if MODE == "calling_station":
        if can_check:
            return {"action": "check"}
        if owed <= stack:
            return {"action": "call"}
        return {"action": "call"}

    if MODE == "naive_aggressor":
        if random.random() < 0.75:
            target = max(min_raise, int(pot * random.uniform(1.5, 3.5)))
            return {"action": "raise", "amount": min(stack + bet_this, target)}
        if can_check:
            return {"action": "check"}
        return {"action": "call"}

    if MODE == "ultra_nit":
        # Folds almost everything
        r1 = state["your_cards"][0][0]
        r2 = state["your_cards"][1][0]
        is_pair = r1 == r2
        is_premium = r1 in "AKQ" and r2 in "AKQ"
        if is_pair or is_premium:
            if can_check:
                return {"action": "raise", "amount": min(stack + bet_this, int(pot * 2))}
            if owed <= pot * 0.5:
                return {"action": "call"}
            return {"action": "fold"}
        if can_check:
            return {"action": "check"}
        return {"action": "fold"}

    if MODE == "minraise_bot":
        # Always min-raises
        if can_check:
            return {"action": "raise", "amount": min(stack + bet_this, min_raise)}
        if owed <= pot * 0.3:
            return {"action": "raise", "amount": min(stack + bet_this, min_raise)}
        return {"action": "fold"}

    if MODE == "random_action":
        # Pure random
        r = random.random()
        if r < 0.3:
            return {"action": "fold"}
        if r < 0.6:
            if can_check:
                return {"action": "check"}
            return {"action": "call"}
        target = max(min_raise, int(pot * random.uniform(0.5, 2.0)))
        return {"action": "raise", "amount": min(stack + bet_this, target)}

    # default: fold
    if can_check:
        return {"action": "check"}
    return {"action": "fold"}
