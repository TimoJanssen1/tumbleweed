
"""Broken Illegal — returns illegal actions sometimes."""
import random
BOT_NAME = "Broken Illegal"

def decide(state):
    if state.get("type") == "warmup":
        return {"action": "fold"}
    r = random.random()
    if r < 0.05:
        return {"action": "invalid_action"}
    if r < 0.10:
        return {"action": "raise"}   # missing amount
    if r < 0.15:
        return "not a dict"
    if state.get("can_check"):
        return {"action": "check"}
    return {"action": "fold"}
