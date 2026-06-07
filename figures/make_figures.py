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


# ── Fig 2 ── How I knew Dutch needed more: it lost showdowns to the elite ─────
# Source: tools/read_logs/my_results.py. Dutch's cards-shown win-rate against
# each opponent tier over the real Q2 matches (n shown).
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
    fig.text(0.5, -0.02, "tools/read_logs/my_results.py · cards-shown win-rate over the real Q2 matches",
             ha="center", fontsize=8, color=GREY)
    _save(fig, "showdown_by_tier.png")


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


# ── Range grids ── what each version plays back facing a single open ─────────
# Source: each bot's own decide() run on all 169 starting hands in one fixed spot
# (button facing a single open). 0 fold · 1 call · 2 bluff-3-bet · 3 value-3-bet.
def fig_range_grids():
    from matplotlib.colors import ListedColormap
    import matplotlib.patches as mpatches
    R = "AKQJT98765432"
    Q1 = [
        [3,0,0,3,0,0,0,0,0,0,0,0,0],[0,3,0,0,0,0,0,0,0,0,0,0,0],
        [0,0,3,0,0,0,0,0,0,0,0,0,0],[3,0,0,3,0,0,0,0,0,0,0,0,0],
        [0,0,0,0,3,0,0,0,0,0,0,0,0],[0,0,0,0,0,3,0,0,0,0,0,0,0],
        [0,0,0,0,0,0,3,0,0,0,0,0,0],[0,0,0,0,0,0,0,0,0,0,0,0,0],
        [0,0,0,0,0,0,0,0,0,0,0,0,0],[0,0,0,0,0,0,0,0,0,0,0,0,0],
        [0,0,0,0,0,0,0,0,0,0,0,0,0],[0,0,0,0,0,0,0,0,0,0,0,0,0],
        [0,0,0,0,0,0,0,0,0,0,0,0,0]]
    DUTCH = [
        [3,0,0,3,0,0,0,0,0,0,0,0,0],[0,3,0,0,0,0,0,0,0,0,0,0,0],
        [0,0,3,0,0,0,0,0,0,0,0,0,0],[3,0,0,3,0,0,0,0,0,0,0,0,0],
        [0,0,0,0,3,0,0,0,0,0,0,0,0],[0,0,0,0,0,3,0,0,0,0,0,0,0],
        [0,0,0,0,0,0,3,0,0,0,0,0,0],[0,0,0,0,0,0,0,1,0,0,0,0,0],
        [0,0,0,0,0,0,0,0,1,0,0,0,0],[0,0,0,0,0,0,0,0,0,1,0,0,0],
        [0,0,0,0,0,0,0,0,0,0,1,0,0],[0,0,0,0,0,0,0,0,0,0,0,1,0],
        [0,0,0,0,0,0,0,0,0,0,0,0,1]]
    GUNS = [
        [3,3,3,3,3,3,2,3,2,2,2,2,2],[3,3,3,3,3,3,2,2,2,2,2,2,2],
        [2,3,3,0,0,0,0,0,0,0,0,0,0],[3,2,0,3,0,0,0,0,0,0,0,0,0],
        [3,2,0,0,3,0,0,0,0,0,0,0,0],[3,2,0,0,0,3,0,0,0,0,0,0,0],
        [2,2,0,0,0,0,3,0,0,0,0,0,0],[2,2,0,0,0,0,0,3,0,0,0,0,0],
        [2,2,0,0,0,0,0,0,3,0,0,0,0],[2,2,0,0,0,0,0,0,0,3,0,0,0],
        [2,2,0,0,0,0,0,0,0,0,1,0,0],[2,2,0,0,0,0,0,0,0,0,0,1,0],
        [2,2,0,0,0,0,0,0,0,0,0,0,1]]
    cmap = ListedColormap(["#e9edf2", BLUE, GOLD, GREEN])  # 0 fold,1 call,2 bluff,3 value
    panels = [("Q1 · Tumble-Weed", Q1), ("Q2 · Dutch", DUTCH), ("Final · Gunslinger", GUNS)]
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
    fig.text(0.5, -0.05, "each bot's own decide() on all 169 starting hands, one fixed spot (button vs an open)",
             ha="center", fontsize=8, color=GREY)
    _save(fig, "range_grids.png")


if __name__ == "__main__":
    fig_overfold()
    fig_showdown_by_tier()
    fig_range_grids()
    fig_benchmark_noise()
    print("done →", OUT)
