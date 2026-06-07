"""Tests for bots/tumbleweeddutch_v21/bot.py, the Q2 calibration bot.

Two groups:
  - Safety invariants: the anti-runaway guard, exception boundary, warmup,
    short-stack push/fold, pot-bet defense, nut value sizing. These must never
    regress.
  - Aggression: the read-driven exploit lines fire. 4-bet a modeled
    over-3-bettor, don't light-4-bet a tight 3-bettor, never bluff a modeled
    station, and light-3-bet a proven over-folder at a controlled frequency. A
    fresh bot with no reads plays like the plain baseline, so the edge is purely
    in-match adaptation, not hardcoded.
"""
import importlib.util
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOT_PATH = os.path.join(ROOT, "bots/tumbleweeddutch_v21/bot.py")


@pytest.fixture
def bot():
    """Fresh module each test → OPP / SEEN / PROCESSED_HANDS reset (mirrors the
    per-match process restart)."""
    spec = importlib.util.spec_from_file_location("dutch_test", BOT_PATH)
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
            {"seat": 1, "action": "small_blind", "amount": 50, "bot_id": "tw"},
            {"seat": 2, "action": "big_blind", "amount": 100, "bot_id": "bb"},
        ]
    if players is None:
        players = []
        for i in range(n_players):
            bid = f"p{i}" if i != seat_to_act else "tw"
            players.append({
                "seat": i, "bot_id": bid, "state": "active",
                "stack": 10000 if i != seat_to_act else your_stack,
                "is_folded": False, "is_all_in": False,
            })
    return {
        "type": "action_request", "hand_id": "test_match_h0", "street": street,
        "seat_to_act": seat_to_act, "pot": pot, "community_cards": community_cards,
        "current_bet": current_bet, "min_raise_to": min_raise_to,
        "amount_owed": amount_owed, "can_check": can_check, "your_cards": hole,
        "your_stack": your_stack, "your_bet_this_street": your_bet_this_street,
        "players": players, "action_log": action_log,
        "match_action_log": match_action_log or [],
    }


def facing_3bet_state(hole, *, villain_bid="villain", villain_seat=4, my_seat=2,
                      your_stack=9100):
    """Preflop spot: an opener raises, `villain` 3-bets to 900, hero is to act
    facing the 3-bet (owed 900 into a 1350 pot → ratio 0.67)."""
    action_log = [
        {"seat": 0, "action": "small_blind", "amount": 50},
        {"seat": 1, "action": "big_blind", "amount": 100},
        {"seat": 3, "action": "raise", "amount": 300},
        {"seat": villain_seat, "action": "raise", "amount": 900},
    ]
    players = []
    for i in range(6):
        bid = "tw" if i == my_seat else (villain_bid if i == villain_seat else f"p{i}")
        players.append({"seat": i, "bot_id": bid, "state": "active",
                        "stack": 10000 if i != my_seat else your_stack,
                        "is_folded": False, "is_all_in": False})
    return make_state(hole=hole, street="preflop", pot=1350, current_bet=900,
                      min_raise_to=1500, amount_owed=900, can_check=False,
                      your_stack=your_stack, your_bet_this_street=0,
                      seat_to_act=my_seat, action_log=action_log, players=players)


# ---------------------------------------------------------------------------
# SAFETY INVARIANTS (must never regress)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("hole,stack", [
    (["As", "Ks"], 30000), (["Qs", "Qh"], 30000), (["7s", "2c"], 30000),
    (["Tc", "7d"], 30000), (["As", "Ad"], 30000), (["Js", "8s"], 25000),
    (["Kc", "Qd"], 15000),
])
def test_deep_stack_never_preflop_shoves(bot, hole, stack):
    """Anti-runaway guard: never auto-shove deep; raises capped at 0.85x stack."""
    st = make_state(hole=hole, your_stack=stack, your_bet_this_street=0,
                    amount_owed=100, current_bet=100, can_check=False, pot=150)
    a = bot.decide(st)
    assert a["action"] != "all_in"
    if a["action"] == "raise":
        assert a["amount"] <= int(stack * 0.85) + 1


def test_exception_safety(bot):
    for bad in [{"type": "garbage"}, {"type": "action_request"},
                {"type": "action_request", "your_cards": ["As"]}]:
        a = bot.decide(bad)
        assert isinstance(a, dict) and "action" in a
        if a["action"] == "raise":
            assert "amount" in a


def test_warmup_returns_fold(bot):
    assert bot.decide({"type": "warmup"}) == {"action": "fold"}


def test_short_stack_premium_shoves(bot):
    st = make_state(hole=["As", "Ad"], your_stack=1150, your_bet_this_street=0,
                    amount_owed=100, current_bet=100, pot=150)
    assert bot.decide(st)["action"] in ("all_in", "raise")


def test_short_stack_trash_folds(bot):
    st = make_state(hole=["7s", "2c"], your_stack=950, your_bet_this_street=0,
                    amount_owed=100, current_bet=100, pot=150)
    assert bot.decide(st)["action"] == "fold"


def test_pot_bet_defense_top_pair(bot):
    """Heads-up, don't over-fold to pot-sized bets with top pair."""
    players = [
        {"seat": 0, "bot_id": "villain", "state": "active", "stack": 9400,
         "is_folded": False, "is_all_in": False},
        {"seat": 1, "bot_id": "tw", "state": "active", "stack": 9400,
         "is_folded": False, "is_all_in": False},
    ] + [{"seat": i, "bot_id": f"p{i}", "state": "folded", "stack": 9000,
          "is_folded": True, "is_all_in": False} for i in range(2, 6)]
    st = make_state(hole=["Kh", "Qd"], street="flop",
                    community_cards=["Ks", "7d", "2c"], pot=600, current_bet=600,
                    min_raise_to=1200, amount_owed=600, can_check=False,
                    your_stack=9400, your_bet_this_street=0, seat_to_act=1,
                    players=players)
    assert bot.decide(st)["action"] in ("call", "raise")


def test_nut_value_bet(bot):
    """Still extract value with the nuts when checked to."""
    st = make_state(hole=["Kc", "7h"], street="river",
                    community_cards=["Ks", "Kd", "7d", "7c", "2h"], pot=2000,
                    current_bet=0, min_raise_to=100, amount_owed=0, can_check=True,
                    your_stack=8000, your_bet_this_street=0)
    a = bot.decide(st)
    assert a["action"] == "raise" and a["amount"] >= 1000


# ---------------------------------------------------------------------------
# AGGRESSION TESTS (the read-driven exploit lines must actually fire)
# ---------------------------------------------------------------------------

def test_fresh_bot_folds_AJ_to_3bet(bot):
    """Cold start (no reads) plays like the plain baseline: AJo folds to a
    3-bet. The read-driven 4-bet defense is what changes that once there is data."""
    st = facing_3bet_state(["Ah", "Jd"])
    assert bot.decide(st)["action"] == "fold"


def test_fourbet_defense_vs_modeled_over_threebettor(bot):
    """THE #1 lever: vs an opponent we've observed 3-betting a lot (wide/weak
    range), stop folding AJo to their 3-bet; 4-bet or call instead."""
    bot.OPP["villain"]["tb_opp"] = 12
    bot.OPP["villain"]["tb_made"] = 6          # 50% 3-bet freq → very wide
    assert bot.opp_threebet_freq("villain") == pytest.approx(0.5)
    a = bot.decide(facing_3bet_state(["Ah", "Jd"]))
    assert a["action"] in ("raise", "call")    # punishing, not folding


def test_no_light_fourbet_vs_tight_threebettor(bot):
    """Conditioning holds: vs a rare (=strong) 3-bettor, AJo still folds, we
    don't blindly fight everyone, only proven over-3-bettors."""
    bot.OPP["villain"]["tb_opp"] = 14
    bot.OPP["villain"]["tb_made"] = 1          # ~7% 3-bet freq → tight/strong
    assert bot.opp_threebet_freq("villain") < 0.16
    assert bot.decide(facing_3bet_state(["Ah", "Jd"]))["action"] == "fold"


def test_value_fourbet_always(bot):
    """Premiums 4-bet for value vs anyone (even a tight 3-bettor)."""
    bot.OPP["villain"]["tb_opp"] = 14
    bot.OPP["villain"]["tb_made"] = 1
    assert bot.decide(facing_3bet_state(["As", "Ad"]))["action"] == "raise"


def test_never_bluff_a_modeled_station(bot):
    """vs an opponent modeled as a passive station (AF<1), a hopeless hand on a
    blank-ish board checks; we never fire bluffs at someone who won't fold."""
    bot.OPP["villain"]["agg"] = 2
    bot.OPP["villain"]["cal"] = 24             # AF ≈ 0.08 → station
    assert bot.opp_af("villain") < 1.0
    # hero is the most-recent caller's opponent; villain is the primary read
    action_log = [
        {"seat": 0, "action": "small_blind", "amount": 50},
        {"seat": 1, "action": "big_blind", "amount": 100},
        {"seat": 4, "action": "call", "amount": 100},
    ]
    players = [{"seat": i, "bot_id": ("tw" if i == 2 else "villain" if i == 4 else f"p{i}"),
                "state": "active", "stack": 9000, "is_folded": False, "is_all_in": False}
               for i in range(6)]
    st = make_state(hole=["7h", "2c"], street="river",
                    community_cards=["As", "Kd", "Qh", "9c", "4s"], pot=800,
                    current_bet=0, min_raise_to=100, amount_owed=0, can_check=True,
                    your_stack=9000, your_bet_this_street=0, seat_to_act=2,
                    action_log=action_log, players=players)
    seen = set()
    for s in range(40):
        bot.random.seed(s)
        seen.add(bot.decide(st)["action"])
    assert seen == {"check"}                   # never bluffs across 40 seeds


def test_no_light_3bet_spew_vs_overfolder(bot):
    """'Redistribute, don't amplify' regression guard: even vs a proven
    over-folder, a marginal hand (KJo) is NOT spewed as a light 3-bet; it
    calls/folds. (An earlier over-eager light-3bet spiked AF to 7.4 and bust to
    43% on the survivor field with no chip gain, so it was cut. The fold-to-3bet
    READ is still tracked for value decisions / future fold-to-4bet work.)"""
    bot.OPP["villain"]["f3_opp"] = 12
    bot.OPP["villain"]["f3_fold"] = 10          # folds 83% to 3-bets → over-folder
    assert bot.opp_fold_to_threebet("villain") > 0.65
    action_log = [
        {"seat": 0, "action": "small_blind", "amount": 50},
        {"seat": 1, "action": "big_blind", "amount": 100},
        {"seat": 4, "action": "raise", "amount": 300},
    ]
    players = [{"seat": i, "bot_id": ("tw" if i == 2 else "villain" if i == 4 else f"p{i}"),
                "state": "active", "stack": 9700, "is_folded": False, "is_all_in": False}
               for i in range(6)]
    st = make_state(hole=["Kh", "Jd"], street="preflop", pot=450, current_bet=300,
                    min_raise_to=500, amount_owed=300, can_check=False,
                    your_stack=9700, your_bet_this_street=0, seat_to_act=2,
                    action_log=action_log, players=players)
    seen = set()
    for s in range(30):
        bot.random.seed(s)
        seen.add(bot.decide(st)["action"])
    assert "raise" not in seen                  # no light-3bet spew; call/fold only


def _open_state(hole, *, open_to, your_stack, my_seat=2, opener_seat=4):
    pot = 50 + 100 + open_to
    action_log = [
        {"seat": 0, "action": "small_blind", "amount": 50},
        {"seat": 1, "action": "big_blind", "amount": 100},
        {"seat": opener_seat, "action": "raise", "amount": open_to},
    ]
    players = [{"seat": i, "bot_id": ("tw" if i == my_seat else f"p{i}"),
                "state": "active", "stack": your_stack, "is_folded": False, "is_all_in": False}
               for i in range(6)]
    return make_state(hole=hole, street="preflop", pot=pot, current_bet=open_to,
                      min_raise_to=open_to * 2, amount_owed=open_to, can_check=False,
                      your_stack=your_stack, your_bet_this_street=0, seat_to_act=my_seat,
                      action_log=action_log, players=players)


def test_set_mine_pair_vs_large_open_when_deep(bot):
    """W2: deep + cheap, flat a small pair vs a larger open to set-mine (a CALL,
    not a raise, lowers AF). The baseline folds this (bet_ratio > call_max_ratio);
    we call for the implied odds of flopping a set and stacking them."""
    st = _open_state(["4h", "4d"], open_to=700, your_stack=14000)  # 140bb, owed 5% of stack
    assert bot.decide(st)["action"] == "call"


def test_no_set_mine_when_shallow(bot):
    """Set-mine needs implied odds (deep stacks). Shallow → fold the small pair to
    a big open rather than spew chips chasing a set we can't get paid on."""
    st = _open_state(["4h", "4d"], open_to=700, your_stack=1500)   # 15bb → no implied odds
    assert bot.decide(st)["action"] == "fold"

