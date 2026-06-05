
"""Broken Slow — occasionally times out by sleeping past 2s budget."""
import random
import time
BOT_NAME = "Broken Slow"

def decide(state):
    if state.get("type") == "warmup":
        return {"action": "fold"}
    if random.random() < 0.03:
        time.sleep(3.0)   # past timeout
    if state.get("can_check"):
        return {"action": "check"}
    return {"action": "fold"}
