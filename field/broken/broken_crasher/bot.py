
"""Broken Crasher — crashes randomly. Tests engine's auto-fold-on-exception."""
import random
BOT_NAME = "Broken Crasher"

def decide(state):
    if state.get("type") == "warmup":
        return {"action": "fold"}
    if random.random() < 0.10:
        raise RuntimeError("simulated bot crash")
    # Otherwise play minimally
    if state.get("can_check"):
        return {"action": "check"}
    if state.get("amount_owed", 0) <= state.get("pot", 1) * 0.2:
        return {"action": "call"}
    return {"action": "fold"}
