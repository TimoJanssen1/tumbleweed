"""
Field generator — materializes 30+ bot.py files from parameterized templates.

Each generated bot is fully self-contained (preflop equity table inlined,
no external imports beyond eval7/random/collections/itertools/math/time).

Run:  python3 analysis/generate_field.py

Output:
  bots/field/strong/*/bot.py    (8 bots — strong, mid-elite quality)
  bots/field/mid/*/bot.py       (10 bots — typical heuristic / LLM-style)
  bots/field/weak/*/bot.py      (5 bots — template tilts / single-rule)
  bots/field/broken/*/bot.py    (3 bots — error-mode for engine testing)

Plus tests/test_field_bots.py that validates every generated bot.
"""

import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from analysis.preflop_table import render_eq_table_source
from analysis.templates import (
    COMMON_HEADER, MC_EQUITY_HELPERS, SAFE_DECIDE_WRAPPER,
    MC_EQUITY_BOT, ABSTRACTION_BOT, MIXED_SIZING_BOT,
    HAND_CHART_BOT, POT_ODDS_BOT, LLM_BOILERPLATE_BOT,
    WEAK_VARIANT_BOT,
    BROKEN_CRASHER_BOT, BROKEN_ILLEGAL_BOT, BROKEN_SLOW_BOT,
)


def materialize(template, output_path, **kwargs):
    """Render template with kwargs (plus equity table + helpers) and write."""
    eq_table = render_eq_table_source()
    common = COMMON_HEADER.format(
        display_name=kwargs.get("display_name", "Generated Bot"),
        equity_table=eq_table,
    )
    mc_helpers = MC_EQUITY_HELPERS
    safe_decide = SAFE_DECIDE_WRAPPER

    rendered = template.format(
        common_header=common,
        mc_helpers=mc_helpers,
        safe_decide=safe_decide,
        **kwargs,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(rendered)


# ============================================================================
# Strong tier — 8 bots
# Real-time MC equity variants with different parameter choices
# ============================================================================

STRONG_BOTS = [
    # MC equity — tight TAG
    dict(name="mc_tight_tag", template=MC_EQUITY_BOT, params=dict(
        display_name="MC Tight TAG", tier="strong",
        open_thresh=0.60, three_bet_thresh=0.72, call_thresh=0.60,
        cbet_freq=0.65, n_trials=180, value_bet_eq=0.62,
        sizing_menu=[0.5, 0.66, 0.75, 1.0],
    )),
    # MC equity — looser LAG
    dict(name="mc_loose_lag", template=MC_EQUITY_BOT, params=dict(
        display_name="MC Loose LAG", tier="strong",
        open_thresh=0.50, three_bet_thresh=0.66, call_thresh=0.52,
        cbet_freq=0.78, n_trials=180, value_bet_eq=0.55,
        sizing_menu=[0.33, 0.5, 0.66, 0.85],
    )),
    # MC equity — small-ball
    dict(name="mc_small_ball", template=MC_EQUITY_BOT, params=dict(
        display_name="MC Small Ball", tier="strong",
        open_thresh=0.55, three_bet_thresh=0.70, call_thresh=0.55,
        cbet_freq=0.70, n_trials=180, value_bet_eq=0.58,
        sizing_menu=[0.25, 0.33, 0.45, 0.66],
    )),
    # MC equity — big sizings
    dict(name="mc_big_sizing", template=MC_EQUITY_BOT, params=dict(
        display_name="MC Big Sizing", tier="strong",
        open_thresh=0.58, three_bet_thresh=0.72, call_thresh=0.58,
        cbet_freq=0.65, n_trials=180, value_bet_eq=0.60,
        sizing_menu=[0.75, 1.0, 1.25, 1.5],
    )),
    # Mixed-sizing solver imitator
    dict(name="solver_mixed", template=MIXED_SIZING_BOT, params=dict(
        display_name="Solver Mixed", tier="strong",
    )),
    # Abstraction bot — MCCFR-style with fixed bet tree
    dict(name="abstraction_tight", template=ABSTRACTION_BOT, params=dict(
        display_name="Abstraction Tight", tier="strong",
    )),
    # Mixed-sizing variant (slight different from solver_mixed)
    dict(name="solver_mixed_b", template=MIXED_SIZING_BOT, params=dict(
        display_name="Solver Mixed B", tier="strong",
    )),
    # MC equity — balanced (mid-of-range tunings)
    dict(name="mc_balanced", template=MC_EQUITY_BOT, params=dict(
        display_name="MC Balanced", tier="strong",
        open_thresh=0.56, three_bet_thresh=0.70, call_thresh=0.56,
        cbet_freq=0.68, n_trials=180, value_bet_eq=0.58,
        sizing_menu=[0.4, 0.66, 0.85, 1.1],
    )),
]


# ============================================================================
# Mid tier — 10 bots
# Typical hackathon submissions: hand-chart bots, pot-odds bots, LLM boilerplate
# ============================================================================

MID_BOTS = [
    # Hand-chart variants
    dict(name="chart_tight", template=HAND_CHART_BOT, params=dict(
        display_name="Chart Tight", tier="mid",
        chart_tightness=0.62, cbet_freq=0.65,
    )),
    dict(name="chart_standard", template=HAND_CHART_BOT, params=dict(
        display_name="Chart Standard", tier="mid",
        chart_tightness=0.55, cbet_freq=0.55,
    )),
    dict(name="chart_loose", template=HAND_CHART_BOT, params=dict(
        display_name="Chart Loose", tier="mid",
        chart_tightness=0.48, cbet_freq=0.70,
    )),
    # Pot-odds bots
    dict(name="pot_odds_tight", template=POT_ODDS_BOT, params=dict(
        display_name="Pot Odds Tight", tier="mid",
        call_threshold=0.20,
    )),
    dict(name="pot_odds_loose", template=POT_ODDS_BOT, params=dict(
        display_name="Pot Odds Loose", tier="mid",
        call_threshold=0.40,
    )),
    # LLM-boilerplate variants — many qualifier entries will look like this
    dict(name="llm_boilerplate_a", template=LLM_BOILERPLATE_BOT, params=dict(
        display_name="LLM Boilerplate A", tier="mid",
    )),
    dict(name="llm_boilerplate_b", template=LLM_BOILERPLATE_BOT, params=dict(
        display_name="LLM Boilerplate B", tier="mid",
    )),
    dict(name="llm_boilerplate_c", template=LLM_BOILERPLATE_BOT, params=dict(
        display_name="LLM Boilerplate C", tier="mid",
    )),
    # Chart bot with very tight cbets
    dict(name="chart_passive", template=HAND_CHART_BOT, params=dict(
        display_name="Chart Passive", tier="mid",
        chart_tightness=0.58, cbet_freq=0.40,
    )),
    # Chart bot with aggressive cbets
    dict(name="chart_aggressive", template=HAND_CHART_BOT, params=dict(
        display_name="Chart Aggressive", tier="mid",
        chart_tightness=0.52, cbet_freq=0.85,
    )),
]


# ============================================================================
# Weak tier — 5 bots
# ============================================================================

WEAK_BOTS = [
    dict(name="calling_station", template=WEAK_VARIANT_BOT, params=dict(
        display_name="Calling Station", tier="weak", mode="calling_station",
    )),
    dict(name="naive_aggressor", template=WEAK_VARIANT_BOT, params=dict(
        display_name="Naive Aggressor", tier="weak", mode="naive_aggressor",
    )),
    dict(name="ultra_nit", template=WEAK_VARIANT_BOT, params=dict(
        display_name="Ultra Nit", tier="weak", mode="ultra_nit",
    )),
    dict(name="minraise_bot", template=WEAK_VARIANT_BOT, params=dict(
        display_name="Minraise Bot", tier="weak", mode="minraise_bot",
    )),
    dict(name="random_action", template=WEAK_VARIANT_BOT, params=dict(
        display_name="Random Action", tier="weak", mode="random_action",
    )),
]


# ============================================================================
# Broken tier — 3 bots
# Tests engine's auto-fold-on-exception / auto-fold-on-timeout handling.
# ============================================================================

BROKEN_BOTS = [
    dict(name="broken_crasher", template=BROKEN_CRASHER_BOT, params=dict(
        display_name="Broken Crasher", tier="broken",
    )),
    dict(name="broken_illegal", template=BROKEN_ILLEGAL_BOT, params=dict(
        display_name="Broken Illegal", tier="broken",
    )),
    dict(name="broken_slow", template=BROKEN_SLOW_BOT, params=dict(
        display_name="Broken Slow", tier="broken",
    )),
]


def all_bots():
    bots = []
    for tier_name, group in [
        ("strong", STRONG_BOTS),
        ("mid", MID_BOTS),
        ("weak", WEAK_BOTS),
        ("broken", BROKEN_BOTS),
    ]:
        for bot in group:
            bots.append((tier_name, bot))
    return bots


def main():
    written = []
    for tier_name, bot in all_bots():
        out = REPO / "bots" / "field" / tier_name / bot["name"] / "bot.py"
        materialize(bot["template"], out, **bot["params"])
        written.append(str(out.relative_to(REPO)))

    print(f"Wrote {len(written)} bots:")
    for w in written:
        print(f"  {w}")


if __name__ == "__main__":
    main()
