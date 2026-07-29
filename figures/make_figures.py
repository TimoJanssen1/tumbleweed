"""
Regenerate the figures in the README.

Two kinds of numbers appear here, and each block says which it is:

  * The range grids (Fig 3) are COMPUTED at figure-build time: each bot's own
    decide() is called on all 169 starting-hand classes in one fixed spot.
    Needs eval7 (the bots import it), no engine, no logs.
  * Figs 1, 2 and 4 are TRANSCRIBED measurements, so this script runs without
    the 16MB of competition logs or hours of engine time. Each block cites the
    tool in ../tools that produced it. Figs 1 and 2 were re-verified 2026-07 by
    re-running those tools against the real Q2 logs — every number matched.
    Fig 4's numbers come from competition-era engine benchmark runs and are
    not recomputed here.

    python tk.py make-figures
"""
import argparse
import importlib.util
import os
import random
from collections import Counter

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(OUT)
INK, GRID = "#1b2330", "#d9dee7"
GREEN, RED, BLUE, GOLD, GREY = "#2e9e6b", "#d2604f", "#3f7cc0", "#caa23b", "#9aa3b2"
plt.rcParams.update({
    "figure.dpi": 130, "savefig.dpi": 130, "font.size": 11,
    "axes.edgecolor": "#c4ccd6", "axes.linewidth": 0.9, "axes.titlesize": 13,
    "axes.titleweight": "bold", "axes.labelcolor": INK, "text.color": INK,
    "xtick.color": INK, "ytick.color": INK, "axes.grid": True,
    "grid.color": GRID, "grid.linewidth": 0.8, "figure.facecolor": "white",
})

def _save(fig, name):
    fig.tight_layout()
    p = os.path.join(OUT, name)
    fig.savefig(p, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("wrote", name)


# ── Fig 1 ── The edge, found in the data ───────────────────────────────────
# Source: tools/read_logs/field_profile.py over the 37 clean Q2 matches
# (opponents' OWN fold rates; n shown). Fold-to-3bet vs the game-theory
# defensibility bound (MDF = P/(P+R) ≈ 50% vs a pot-sized raise).
# Transcribed from the real Q2 logs (not shipped with this repo); verified
# 2026-07 by re-running the tool against them — all values matched exactly.
def fig_overfold():
    tiers = ["top-16", "ranks 17–64", "ranks 65+"]
    fold3 = [87, 88, 65]      # n = 390, 292, 439   (opener faces a 3-bet → folds?)
    fold4 = [26, 40, 41]      # n = 19, 25, 87       (3-bettor faces a 4-bet → folds?)
    x = range(len(tiers)); w = 0.38
    fig, ax = plt.subplots(figsize=(7.6, 4.4))
    b1 = ax.bar([i - w/2 for i in x], fold3, w, label="folds to a 3-bet", color=GREEN)
    b2 = ax.bar([i + w/2 for i in x], fold4, w, label="folds to a 4-bet", color=BLUE)
    ax.axhline(50, ls="--", lw=1.6, color=RED)
    ax.text(1.5, 50, "  defensibility bound · MDF ≈ 50%  ", color=RED, fontsize=9.5,
            ha="center", va="center", fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=RED, lw=1))
    for bars in (b1, b2):
        for b in bars:
            ax.text(b.get_x()+b.get_width()/2, b.get_height()+1.5, f"{int(b.get_height())}%",
                    ha="center", va="bottom", fontsize=9.5, fontweight="bold")
    ax.set_xticks(list(x)); ax.set_xticklabels(tiers)
    ax.set_ylabel("fold frequency"); ax.set_ylim(0, 100)
    ax.set_title("The whole field folds to 3-bets ~35 points past where it's allowed to")
    ax.legend(loc="upper right", framealpha=0.95)
    fig.text(0.5, -0.02, "measured from 37 real Q2 matches · tools/read_logs/field_profile.py · "
             "n(top-64 fold-to-3bet)=682 · transcribed, verified vs the logs 2026-07",
             ha="center", fontsize=8, color=GREY)
    _save(fig, "field_overfolds.png")


# ── Fig 2 ── How I knew Dutch needed more: it lost showdowns to the elite ─────
# Source: tools/read_logs/my_results.py — Dutch's cards-shown win-rate against
# each opponent tier over the real Q2 matches (n shown).
# Transcribed; verified 2026-07 by re-running the tool against the Q2 logs —
# all values matched exactly (14W/16L, 174W/110L, 365W/246L).
def fig_showdown_by_tier():
    tiers = ["top-16", "ranks 17-64", "ranks 65+"]
    win   = [47, 61, 60]
    ns    = [30, 284, 611]
    fig, ax = plt.subplots(figsize=(7.4, 4.2))
    cols = [RED if w < 50 else GREEN for w in win]
    bars = ax.bar(tiers, win, color=cols, width=0.6)
    ax.axhline(50, ls="--", lw=1.6, color=INK)
    ax.text(-0.42, 51, "break-even", color=INK, fontsize=9, ha="left", va="bottom")
    for b, w, n in zip(bars, win, ns):
        ax.text(b.get_x()+b.get_width()/2, w-3, f"{w}%\n(n={n})",
                ha="center", va="top", color="white", fontsize=9.5, fontweight="bold")
    ax.set_ylim(0, 72); ax.set_ylabel("showdown win-rate")
    ax.set_title("At showdown, Dutch beat the field but lost to the top-16")
    fig.text(0.5, -0.02, "tools/read_logs/my_results.py · cards-shown win-rate over the real Q2 matches · "
             "transcribed, verified vs the logs 2026-07",
             ha="center", fontsize=8, color=GREY)
    _save(fig, "showdown_by_tier.png")


# ── Fig 3 ── Range grids: what each version plays back facing a single open ──
# COMPUTED, not transcribed: each bot's own decide() is called on all 169
# starting-hand classes in one fixed spot (button facing a single 300 open —
# the same spot the unit tests use). Mixed strategies are read off decide()'s
# own randomness: 200 trials per hand; a 3-bet that fires on (almost) every
# trial is a value 3-bet, a sometimes-3-bet is the mixed blocker bluff.
BOTS_FOR_GRIDS = [
    ("Q1 · Tumble-Weed",      "bots/tumbleweed_q1/bot.py"),
    ("Q2 · Dutch",            "bots/tumbleweeddutch_v21/bot.py"),
    ("Final · Gunslinger",    "bots/gunslinger/bot.py"),
]
R = "AKQJT98765432"
GRID_TRIALS = 200


def _load_bot(rel_path):
    """Fresh module load (same mechanism as the unit tests) so per-match
    opponent state starts clean."""
    path = os.path.join(REPO, rel_path)
    name = "grids_" + rel_path.replace("/", "_").replace(".py", "")
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _facing_open_state(hole):
    """Button facing a single 300 open, everyone else out — the fixed spot.
    Mirrors tests/test_gunslinger.py::facing_open_state (hero seat 5 closes
    the action, so the position-aware bots read this as in position)."""
    my_seat, opener_seat = 5, 2
    folded = {0, 1, 3, 4}
    action_log = [{"seat": 0, "action": "small_blind", "amount": 50},
                  {"seat": 1, "action": "big_blind", "amount": 100},
                  {"seat": opener_seat, "action": "raise", "amount": 300},
                  {"seat": 3, "action": "fold", "amount": 0},
                  {"seat": 4, "action": "fold", "amount": 0}]
    players = []
    for i in range(6):
        bid = "hero" if i == my_seat else f"opp{i}"
        players.append({"seat": i, "bot_id": bid,
                        "state": "folded" if i in folded else "active",
                        "stack": 10000 if i != my_seat else 9700,
                        "is_folded": i in folded, "is_all_in": False})
    return {
        "type": "action_request", "hand_id": "grid_h0", "street": "preflop",
        "seat_to_act": my_seat, "pot": 450, "community_cards": [],
        "current_bet": 300, "min_raise_to": 600, "amount_owed": 300,
        "can_check": False, "your_cards": list(hole), "your_stack": 9700,
        "your_bet_this_street": 0, "players": players,
        "action_log": action_log, "match_action_log": [],
    }


def _cell_cards(i, j):
    """Concrete hole cards for grid cell (i, j): diagonal = pair,
    upper triangle = suited, lower = offsuit. Suits are arbitrary (no board)."""
    if i == j:
        return (R[i] + "s", R[i] + "h")
    hi, lo = R[min(i, j)], R[max(i, j)]
    if i < j:                      # suited
        return (hi + "s", lo + "s")
    return (hi + "s", lo + "h")    # offsuit


def _classify_cell(mod, cards):
    """Call decide() GRID_TRIALS times (seeded, reproducible) and map the
    observed mix to: 0 fold · 1 call · 2 bluff-3-bet (mixed) · 3 value-3-bet
    (near-deterministic)."""
    counts = Counter()
    for t in range(GRID_TRIALS):
        random.seed(f"{cards[0]}{cards[1]}#{t}")
        act = mod.decide(_facing_open_state(cards))["action"]
        counts[act] += 1
    n = sum(counts.values())
    n_raise = counts["raise"] + counts["all_in"]
    if n_raise >= 0.9 * n:
        return 3                                # always 3-bets: value
    if n_raise > 0:
        return 2                                # sometimes 3-bets: mixed bluff
    return 1 if counts["call"] >= counts["fold"] else 0


def compute_grid(rel_path):
    mod = _load_bot(rel_path)
    return [[_classify_cell(mod, _cell_cards(i, j)) for j in range(13)]
            for i in range(13)]


def fig_range_grids():
    from matplotlib.colors import ListedColormap
    import matplotlib.patches as mpatches
    panels = [(title, compute_grid(rel)) for title, rel in BOTS_FOR_GRIDS]
    # sanity: premiums fight back, trash folds — fail loudly, never draw nonsense
    for title, M in panels:
        assert M[0][0] == 3, f"{title}: AA must 3-bet for value"
        assert M[12][6] == 0, f"{title}: 72o must fold"
    cmap = ListedColormap(["#e9edf2", BLUE, GOLD, GREEN])  # 0 fold,1 call,2 bluff,3 value
    fig, axes = plt.subplots(1, 3, figsize=(13.6, 5.0))
    for ax, (title, M) in zip(axes, panels):
        ax.imshow(M, cmap=cmap, vmin=0, vmax=3, aspect="equal")
        for i in range(13):
            for j in range(13):
                hr, lr = R[min(i, j)], R[max(i, j)]
                lab = f"{hr}{hr}" if i == j else (f"{hr}{lr}s" if i < j else f"{hr}{lr}o")
                ax.text(j, i, lab, ha="center", va="center", fontsize=4.6,
                        color=("#5b6675" if M[i][j] == 0 else "white"))
        ax.set_xticks(range(13)); ax.set_xticklabels(list(R), fontsize=7)
        ax.set_yticks(range(13)); ax.set_yticklabels(list(R), fontsize=7)
        ax.set_xticks([v-0.5 for v in range(14)], minor=True)
        ax.set_yticks([v-0.5 for v in range(14)], minor=True)
        ax.grid(which="minor", color="white", lw=1.1); ax.tick_params(length=0)
        agg = sum(1 for row in M for v in row if v >= 2)
        ax.set_title(f"{title}    ({100*agg/169:.0f}% 3-bet)", fontsize=11)
    handles = [mpatches.Patch(color="#e9edf2", label="fold"),
               mpatches.Patch(color=BLUE, label="call"),
               mpatches.Patch(color=GREEN, label="3-bet (value)"),
               mpatches.Patch(color=GOLD, label="3-bet (bluff)")]
    fig.legend(handles=handles, loc="lower center", ncol=4, framealpha=0.95, bbox_to_anchor=(0.5, -0.01))
    fig.suptitle("Facing a single open: the hands each version fights back with", fontsize=13, fontweight="bold")
    fig.text(0.5, -0.05, "computed at figure-build time: each bot's own decide() on all 169 starting hands, "
             f"one fixed spot (button vs an open), {GRID_TRIALS} seeded trials per hand",
             ha="center", fontsize=8, color=GREY)
    _save(fig, "range_grids.png")


# ── Fig 4 ── How we tested it (and why we trust the field data, not the sim) ─
# Source: tools/compare_bots.py --crn --survivor (generic field) and
# tools/bench_vs_overfolders.py (calibrated field) — CRN paired diffs ± 95% CI.
# Transcribed from competition-era engine benchmark runs; reproducing them
# needs the fullhouse-engine and hours of match simulation, so these two
# numbers are NOT recomputed at figure-build time.
def fig_benchmark_noise():
    labels = ["generic field\n(survivor mix)", "calibrated field\n(the over-folders)"]
    diff = [625, 2086]      # Gunslinger − Dutch, CRN paired
    ci   = [1858, 2488]     # 95% CI — both cross zero
    y = [1, 0]
    fig, ax = plt.subplots(figsize=(8.2, 3.5))
    for yi, d, c in zip(y, diff, ci):
        ax.errorbar(d, yi, xerr=c, fmt="o", color=GREY, ecolor=GREY,
                    elinewidth=2.6, capsize=6, markersize=10)
        ax.text(d, yi + 0.22, f"{d:+,}", ha="center", fontsize=10.5, fontweight="bold", color=INK)
    ax.axvline(0, color=INK, lw=1.5)
    ax.set_yticks(y); ax.set_yticklabels(labels, fontsize=11)
    ax.set_ylim(-0.7, 1.7); ax.set_xlim(-2300, 5000)
    ax.set_xlabel("Gunslinger − Dutch, chip-Δ / match   (CRN paired, ±95% CI)")
    ax.set_title("Even my cleanest A/B is lost in the noise on the sim — so the logs decided it")
    fig.text(0.5, -0.04, "tools/compare_bots.py + tools/bench_vs_overfolders.py · transcribed from competition-era "
             "benchmark runs · the gap leans bigger on the calibrated field, but both CIs cross zero",
             ha="center", fontsize=8, color=GREY)
    _save(fig, "benchmark_noise.png")


if __name__ == "__main__":
    argparse.ArgumentParser(
        description="Redraw the README charts into figures/. Needs matplotlib "
                    "+ eval7 (the range grids call the bots' own decide())."
    ).parse_args()
    fig_overfold()
    fig_showdown_by_tier()
    fig_range_grids()
    fig_benchmark_noise()
    print("done →", OUT)
