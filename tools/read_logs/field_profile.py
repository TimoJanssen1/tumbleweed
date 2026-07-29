"""What the field actually does, measured from the real Q2 logs, by leaderboard tier:
how often opponents FOLD to a 3-bet and to a 4-bet. This is the chart that found the edge
(they fold ~88%; game theory says ~50%). Run: Q2_MATCH_DIR=... python tk.py profile"""
import argparse, sys, os
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from leaderboard import rank_of


def tier(n):
    r = rank_of(n)
    return "top-16" if r <= 16 else ("17-64" if r <= 64 else "65+")


def measure():
    """Return (f3, f4): tier -> [folds, spots] for fold-to-3bet / fold-to-4bet."""
    from parse import segment_hand, attribute_match, clean_matches
    f3 = defaultdict(lambda: [0, 0])  # tier -> [folds, spots]  (opener faces 3-bet)
    f4 = defaultdict(lambda: [0, 0])  # tier -> [folds, spots]  (3-bettor faces 4-bet)

    for fn, d in clean_matches():
        per, ok, stack, name, id_orig = attribute_match(d)
        for rec in per:
            h = rec["h"]; amap = rec["amap"]
            streets, chips, _ = segment_hand(h); pre = dict(streets).get("preflop", [])
            # walk raises; record opener / 3bettor; then the NEXT voluntary action of each
            nr = 0; opener = None; threebettor = None
            opener_resolved = False; tb_resolved = False
            for a in pre:
                s = a["seat"]; act = a["action"]; bid = amap.get(s)
                if bid is None or act in ("small_blind", "big_blind"):
                    continue
                # opener facing the 3-bet: opener's first action after nr reached 2
                if opener is not None and not opener_resolved and bid == opener and nr >= 2:
                    f3[tier(name[opener])][1] += 1
                    if act == "fold":
                        f3[tier(name[opener])][0] += 1
                    opener_resolved = True
                # 3-bettor facing the 4-bet: their first action after nr reached 3
                if threebettor is not None and not tb_resolved and bid == threebettor and nr >= 3:
                    f4[tier(name[threebettor])][1] += 1
                    if act == "fold":
                        f4[tier(name[threebettor])][0] += 1
                    tb_resolved = True
                if act in ("raise", "all_in"):
                    if nr == 0: opener = bid
                    elif nr == 1: threebettor = bid
                    nr += 1
    return f3, f4


def show(label, d):
    print(f"\n=== {label} ===")
    tot = [0, 0]
    for t in ("top-16", "17-64", "65+"):
        fo, n = d[t]; tot[0] += fo; tot[1] += n
        if n: print(f"  {t:7}: fold {100*fo/n:4.0f}%   (n={n})")
    t16_64 = [d["top-16"][i] + d["17-64"][i] for i in range(2)]
    if t16_64[1]: print(f"  TOP-64 : fold {100*t16_64[0]/t16_64[1]:4.0f}%   (n={t16_64[1]})")
    if tot[1]:    print(f"  ALL    : fold {100*tot[0]/tot[1]:4.0f}%   (n={tot[1]})")


def main():
    argparse.ArgumentParser(
        description="Fold-to-3bet / fold-to-4bet by leaderboard tier, measured "
                    "from the real Q2 logs. Reads $Q2_MATCH_DIR/*.json."
    ).parse_args()
    f3, f4 = measure()
    show("FOLD-TO-3BET (opener faces a 3-bet)", f3)
    show("FOLD-TO-4BET (3-bettor faces a 4-bet)", f4)


if __name__ == "__main__":
    main()
