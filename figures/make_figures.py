"""
Regenerate the figures in the README.

Every number here is *measured*, not asserted — each block cites the tool in
../tools that produced it (run against the real Fullhouse match logs / the sim
field). The values are embedded so this script runs standalone (no engine, no
16MB of logs needed to redraw the charts); re-run the cited tool to verify.

    python figures/make_figures.py
"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = os.path.dirname(os.path.abspath(__file__))
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
# Source: tools/read_logs/field_profile.py (measure of opponents' OWN fold rates over 37 clean
# Q2 matches; n shown). Fold-to-3bet vs the game-theory defensibility bound (MDF).
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
    fig.text(0.5, -0.02, "measured from 37 real Q2 matches · tools/read_logs/field_profile.py · n(top-64 fold-to-3bet)=682",
             ha="center", fontsize=8, color=GREY)
    _save(fig, "field_overfolds.png")


# ── Fig 2 ── Where the chips actually came from ─────────────────────────────
# Source: tools/read_logs/my_results.py — Dutch's mean chip-Δ by how many top-64
# opponents sat at the table (the bot that finished #14).
def fig_chips_by_strength():
    ntop = [0, 1, 2, 3, 5]
    mean = [16892, -10000, 11176, 30000, -10000]
    ns   = [8, 8, 17, 3, 1]
    fig, ax = plt.subplots(figsize=(7.6, 4.4))
    cols = [GREEN if m > 0 else RED for m in mean]
    bars = ax.bar([str(n) for n in ntop], mean, color=cols, width=0.62)
    ax.axhline(0, color=INK, lw=1)
    for b, m, n in zip(bars, mean, ns):
        off = 900 if m > 0 else -1900
        ax.text(b.get_x()+b.get_width()/2, m+off, f"{m:+,}\n(n={n})",
                ha="center", va="bottom" if m > 0 else "top", fontsize=9)
    ax.axvspan(3.5, 4.5, color=GOLD, alpha=0.12)
    ax.text(4, 22000, "← the FINAL\n(all top-64)", ha="center", color="#8a6d12", fontsize=9, fontweight="bold")
    ax.set_xlabel("number of top-64 opponents at the table")
    ax.set_ylabel("Dutch's mean chip-Δ / match"); ax.set_ylim(-16000, 34000)
    ax.set_title("Dutch (#14) crushed soft tables and broke even against strong ones")
    fig.text(0.5, -0.02, "tools/read_logs/my_results.py · the #14 bot, over its real Q2 matches · n small for 3 & 5",
             ha="center", fontsize=8, color=GREY)
    _save(fig, "chips_by_field_strength.png")


# ── Fig 3 ── Three iterations: too hot → too cold → just right ──────────────
# Source: tools/audit_bot.py on the survivor field (60–80 seeds each).
def fig_three_iterations():
    names = ["Tumble-Weed\n(Q1)", "Dutch\n(Q2)", "Gunslinger\n(final)"]
    threebet = [3.4, 3.4, 11.9]
    cbet     = [20.9, 23.6, 40.5]
    af       = [7.0, 2.8, 4.1]
    fig, (axL, axR) = plt.subplots(1, 2, figsize=(10.6, 4.4))
    x = range(3); w = 0.38
    b1 = axL.bar([i-w/2 for i in x], threebet, w, label="3-bet %", color=BLUE)
    b2 = axL.bar([i+w/2 for i in x], cbet, w, label="c-bet %", color=GREEN)
    for bars in (b1, b2):
        for b in bars:
            axL.text(b.get_x()+b.get_width()/2, b.get_height()+0.6, f"{b.get_height():.1f}",
                     ha="center", va="bottom", fontsize=9)
    axL.set_xticks(list(x)); axL.set_xticklabels(names); axL.set_ylabel("frequency (%)")
    axL.set_ylim(0, 46); axL.legend(loc="upper left", framealpha=0.95)
    axL.set_title("Applying pressure: from flat-caller to 3-bettor")

    cols = [RED, GOLD, GREEN]
    bars = axR.bar(range(3), af, color=cols, width=0.6)
    axR.axhline(3.6, ls="--", lw=1.5, color=GREY)
    axR.text(1.35, 3.74, "field ≈ 3.6", color="#6b7480", ha="left", fontsize=9)
    tags = ["reckless", "timid", "disciplined"]
    for b, v, t in zip(bars, af, tags):
        axR.text(b.get_x()+b.get_width()/2, v+0.12, f"{v:.1f}", ha="center", va="bottom", fontsize=10, fontweight="bold")
        axR.text(b.get_x()+b.get_width()/2, 0.25, t, ha="center", va="bottom", fontsize=9, color="white", fontweight="bold")
    axR.set_xticks(range(3)); axR.set_xticklabels(names); axR.set_ylabel("aggression factor (bets+raises)/calls")
    axR.set_ylim(0, 7.8); axR.set_title("Aggression: too hot → too cold → just right")
    fig.text(0.5, -0.02, "tools/audit_bot.py · survivor (elite-heavy) field", ha="center", fontsize=8, color=GREY)
    _save(fig, "three_iterations.png")


# ── Fig 4 ── How we tested it (and why we trust the field data, not the sim) ─
# Source: tools/compare_bots.py & q2_overfolder_bench.py — CRN paired diffs ± 95% CI.
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
    fig.text(0.5, -0.04, "tools/compare_bots.py · the gap leans bigger on the calibrated field, but ±50k swings keep both CIs across zero",
             ha="center", fontsize=8, color=GREY)
    _save(fig, "benchmark_noise.png")


if __name__ == "__main__":
    fig_overfold()
    fig_chips_by_strength()
    fig_three_iterations()
    fig_benchmark_noise()
    print("done →", OUT)
