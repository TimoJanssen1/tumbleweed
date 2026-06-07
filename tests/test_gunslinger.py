"""Tests for bots/gunslinger/bot.py, the final bot.

Two groups:
  - Safety invariants (must never regress): no deep-stack auto-shove, the
    exception boundary, warmup folds, short-stack push/fold, and decide()
    always returning a legal action.
  - Aggression (the preflop pressure fires, and stays disciplined): value-4-bet
    a premium or AK against a 3-bet, never 5-bet-bluff facing a 4-bet, fold a
    bluff to a 5-bet jam, value-3-bet a strong hand against an open, and
    3-bet-bluff in position but never out of position. A fresh bot has neutral
    reads, so the edge is in-match adaptation, nothing hardcoded.
"""
import importlib.util
import os
import random

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOT_PATH = os.path.join(ROOT, "bots/gunslinger/bot.py")


@pytest.fixture
def bot():
    """Fresh module each test → OPP/SEEN/PROCESSED_HANDS reset (per-match restart)."""
    spec = importlib.util.spec_from_file_location("gunslinger_test", BOT_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def make_state(*, hole, street="preflop", pot=150, community_cards=None,
               current_bet=100, min_raise_to=200, amount_owed=50, can_check=False,
               your_stack=9950, your_bet_this_street=50, seat_to_act=1,
               action_log=None, n_players=6, match_action_log=None, players=None):
    community_cards = community_cards or []
    if action_log is None:
        action_log = [
            {"seat": 0, "action": "small_blind", "amount": 50},
            {"seat": 1, "action": "big_blind", "amount": 100},
        ]
    if players is None:
        players = []
        for i in range(n_players):
            bid = f"p{i}" if i != seat_to_act else "tw"
            players.append({"seat": i, "bot_id": bid, "state": "active",
                            "stack": 10000 if i != seat_to_act else your_stack,
                            "is_folded": False, "is_all_in": False})
    return {
        "type": "action_request", "hand_id": "test_match_h0", "street": street,
        "seat_to_act": seat_to_act, "pot": pot, "community_cards": community_cards,
        "current_bet": current_bet, "min_raise_to": min_raise_to,
        "amount_owed": amount_owed, "can_check": can_check, "your_cards": hole,
        "your_stack": your_stack, "your_bet_this_street": your_bet_this_street,
        "players": players, "action_log": action_log,
        "match_action_log": match_action_log or [],
    }


def facing_open_state(hole, in_position=True, opener_bid="opener"):
    """Hero faces a single 300 open. in_position → hero closes action (n_behind=0)."""
    if in_position:
        my_seat, opener_seat = 5, 2
        action_log = [{"seat": 0, "action": "small_blind", "amount": 50},
                      {"seat": 1, "action": "big_blind", "amount": 100},
                      {"seat": opener_seat, "action": "raise", "amount": 300},
                      {"seat": 3, "action": "fold", "amount": 0},
                      {"seat": 4, "action": "fold", "amount": 0}]
        folded = {0, 1, 3, 4}
    else:
        my_seat, opener_seat = 3, 2
        action_log = [{"seat": 0, "action": "small_blind", "amount": 50},
                      {"seat": 1, "action": "big_blind", "amount": 100},
                      {"seat": opener_seat, "action": "raise", "amount": 300}]
        folded = {0, 1}
    players = []
    for i in range(6):
        bid = "tw" if i == my_seat else (opener_bid if i == opener_seat else f"p{i}")
        players.append({"seat": i, "bot_id": bid,
                        "state": "folded" if i in folded else "active",
                        "stack": 10000 if i != my_seat else 9700,
                        "is_folded": i in folded, "is_all_in": False})
    return make_state(hole=hole, street="preflop", pot=450, current_bet=300,
                      min_raise_to=600, amount_owed=300, can_check=False,
                      your_stack=9700, your_bet_this_street=0, seat_to_act=my_seat,
                      action_log=action_log, players=players)


def facing_3bet_state(hole, in_position=True, owed=900, pot=1350):
    """Opener raises, villain 3-bets; hero faces the 3-bet. in_position → n_behind=0."""
    if in_position:
        my_seat, opener_seat, tb_seat = 5, 2, 4
        folded = {0, 1, 3}
    else:
        my_seat, opener_seat, tb_seat = 2, 3, 4
        folded = set()
    action_log = [{"seat": 0, "action": "small_blind", "amount": 50},
                  {"seat": 1, "action": "big_blind", "amount": 100},
                  {"seat": opener_seat, "action": "raise", "amount": 300},
                  {"seat": tb_seat, "action": "raise", "amount": 900}]
    players = []
    for i in range(6):
        bid = "tw" if i == my_seat else f"p{i}"
        players.append({"seat": i, "bot_id": bid,
                        "state": "folded" if i in folded else "active",
                        "stack": 10000 if i != my_seat else 9100,
                        "is_folded": i in folded, "is_all_in": False})
    return make_state(hole=hole, street="preflop", pot=pot, current_bet=900,
                      min_raise_to=1500, amount_owed=owed, can_check=False,
                      your_stack=9100, your_bet_this_street=0, seat_to_act=my_seat,
                      action_log=action_log, players=players)


def facing_4bet_state(hole, jam=False):
    """Hero (who 3-bet) now faces a 4-bet (n_raises==3). jam → 5-bet shove sizing."""
    amt = 9000 if jam else 2200
    action_log = [{"seat": 0, "action": "small_blind", "amount": 50},
                  {"seat": 1, "action": "big_blind", "amount": 100},
                  {"seat": 2, "action": "raise", "amount": 300},     # opener
                  {"seat": 5, "action": "raise", "amount": 900},     # hero 3-bet
                  {"seat": 2, "action": "raise", "amount": amt}]     # opener 4-bets
    players = []
    for i in range(6):
        bid = "tw" if i == 5 else f"p{i}"
        players.append({"seat": i, "bot_id": bid,
                        "state": "folded" if i in (1, 3, 4) else "active",
                        "stack": 10000 if i != 5 else 9100,
                        "is_folded": i in (1, 3, 4), "is_all_in": False})
    pot = 50 + 100 + 300 + 900 + amt
    return make_state(hole=hole, street="preflop", pot=pot, current_bet=amt,
                      min_raise_to=amt * 2, amount_owed=amt - 900, can_check=False,
                      your_stack=9100, your_bet_this_street=900, seat_to_act=5,
                      action_log=action_log, players=players)


# ---------------------------------------------------------------------------
# SAFETY INVARIANTS
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("hole", [["As", "Ad"], ["Ks", "Kd"], ["As", "Ks"],
                                  ["Qs", "Qh"], ["7s", "2c"], ["Tc", "7d"]])
def test_deep_stack_never_preflop_shoves(bot, hole):
    """The a4da672f anti-runaway guard: never auto-shove a deep stack preflop."""
    st = make_state(hole=hole, your_stack=30000, amount_owed=300, current_bet=300,
                    pot=450, min_raise_to=600, seat_to_act=5,
                    action_log=[{"seat": 0, "action": "small_blind", "amount": 50},
                                {"seat": 1, "action": "big_blind", "amount": 100},
                                {"seat": 2, "action": "raise", "amount": 300}])
    a = bot.decide(st)
    assert a["action"] != "all_in"
    if a["action"] == "raise":
        assert a["amount"] <= int(30000 * 0.85) + 1


def test_warmup_folds(bot):
    assert bot.decide({"type": "warmup"}) == {"action": "fold"}


def test_missing_cards_folds(bot):
    assert bot.decide({"type": "action_request"}) == {"action": "fold"}


def test_short_stack_premium_shoves(bot):
    st = make_state(hole=["As", "Ad"], your_stack=1200, current_bet=100,
                    amount_owed=100, pot=150, min_raise_to=200, seat_to_act=5)
    assert bot.decide(st)["action"] == "all_in"


def test_decide_never_raises_and_is_legal(bot):
    ranks, suits = "23456789TJQKA", "shdc"
    deck = [r + s for r in ranks for s in suits]
    rng = random.Random(99)
    for _ in range(400):
        hole = rng.sample(deck, 2)
        st = make_state(hole=hole,
                        street=rng.choice(["preflop", "flop", "turn", "river"]),
                        pot=rng.choice([150, 600, 1350, 4000]),
                        amount_owed=rng.choice([0, 100, 300, 900, 5000]),
                        current_bet=rng.choice([100, 300, 900]),
                        can_check=rng.choice([True, False]),
                        your_stack=rng.choice([800, 4000, 9100, 30000]),
                        community_cards=[c for c in rng.sample(deck, rng.choice([0, 3, 4, 5]))
                                         if c not in hole][:5])
        a = bot.decide(st)
        assert isinstance(a, dict) and "action" in a
        if a["action"] == "raise":
            assert "amount" in a and a["amount"] > 0
    assert bot.decide({"type": "warmup"}) == {"action": "fold"}


# ---------------------------------------------------------------------------
# 4-bet defense (value fires; never 5-bet-bluff; fold bluffs to a jam)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("hole", [["As", "Ad"], ["Ks", "Kd"], ["Qs", "Qd"]])
def test_value_4bet_premium_vs_3bet(bot, hole):
    """Premiums 4-bet (raise) a normal 3-bet (earlier versions just flat/folded)."""
    assert bot.decide(facing_3bet_state(hole, in_position=True))["action"] == "raise"


def test_value_4bet_AK_vs_3bet(bot):
    """AK (two blockers) 4-bets a normal 3-bet rather than folding (the leak)."""
    assert bot.decide(facing_3bet_state(["As", "Kd"], in_position=True))["action"] == "raise"


def test_trash_folds_to_3bet(bot):
    """No reads, no blockers → still fold trash to a 3-bet (no spew)."""
    assert bot.decide(facing_3bet_state(["7c", "2d"], in_position=True))["action"] == "fold"


def test_no_5bet_bluff_facing_4bet(bot):
    """Facing a 4-bet (n_raises>=3) with a non-premium: NEVER raise (no 5-bet bluff)."""
    for hole in (["As", "5s"], ["Kc", "Qd"], ["Ah", "Jd"], ["Ts", "Th"]):
        a = bot.decide(facing_4bet_state(hole, jam=False))
        assert a["action"] != "raise", f"5-bet-bluffed {hole}"


def test_bluff_folds_to_5bet_jam(bot):
    """A 4-bet-bluff-type hand folds to a 5-bet jam (premiums excepted)."""
    a = bot.decide(facing_4bet_state(["As", "5s"], jam=True))
    assert a["action"] == "fold"


def test_premium_calls_5bet_jam(bot):
    """The very top stacks off vs a 5-bet jam (we don't fold the nuts)."""
    a = bot.decide(facing_4bet_state(["As", "Ad"], jam=True))
    assert a["action"] in ("call", "all_in")


# ---------------------------------------------------------------------------
# 3-bet attack (value fires; bluff is position-gated)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("hole", [["As", "Ad"], ["Ks", "Kd"], ["As", "Qs"], ["Ah", "Ks"]])
def test_value_3bet_vs_open(bot, hole):
    """Strong hands 3-bet a single open (earlier versions near-pure flat-called)."""
    assert bot.decide(facing_open_state(hole, in_position=True))["action"] == "raise"


def test_3bet_bluff_fires_in_position(bot):
    """A blocker hand just below the value band 3-bet-bluffs *some* of the time IP."""
    raises = sum(1 for _ in range(200)
                 if bot.decide(facing_open_state(["As", "5d"], in_position=True))["action"] == "raise")
    assert 15 <= raises <= 130, f"IP 3-bet-bluff freq off: {raises}/200"


def test_no_3bet_bluff_out_of_position(bot):
    """The same hand never 3-bet-bluffs out of position (discipline)."""
    raises = sum(1 for _ in range(120)
                 if bot.decide(facing_open_state(["As", "5d"], in_position=False))["action"] == "raise")
    assert raises == 0, f"OOP 3-bet-bluffed {raises} times"
