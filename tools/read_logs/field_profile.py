"""What the field actually does, measured from the real Q2 logs, by leaderboard tier:
how often opponents FOLD to a 3-bet and to a 4-bet. This is the chart that found the edge
(they fold ~88%; game theory says ~50%). Run: Q2_MATCH_DIR=... python field_profile.py"""
import sys, os
from collections import Counter, defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from parse import segment_hand, OURS, attribute_match, clean_matches

LB = ["jew","CallMeMaybe","SevenDeuces","NecessarySkew","Looper257","Oxvard","BussBot-v3","Taleto13","winning","CrimsonBot","FerdaBot","Khan’t Fold","make_no_mistakes","Tumble-Weed-Dutch-v2","Lekemog","ant-bot","twader","Hyperion","durak","jotaroZAWARUDO","TheQuantBot","talan","Overfitted","Inefficiency","+ev","Pantheon","sam_bot_lfg_2","50CentRaise","IveyBot","𝐛𝐚𝐯","poker? I barely know her","pavan kumar","I hate arsenal","Pascal","RODBOTv2","BATNEEC","GrandSlam","Javis","Freelo","Super2Trooper","goku","72o","alan","elprofesoriqo","not_so_simple_bot","Lyra","SaviourBot","TheHouse","I'mDeffoCappin","VolatileNeuron","never played poker","gems_VC2","PhoonTooMuchForPoker","Thorp","SummerSun","SuperExtraDeluxeMegaBot","NEMESIS","G-Forge","TheCrystalline","Bot2","BeginnersLuck V3","Foldilocks","BOTv2","Worm"]
RANK = {n: i + 1 for i, n in enumerate(LB)}
def tier(n):
    r = RANK.get(n, 999)
    return "top-16" if r <= 16 else ("17-64" if r <= 64 else "65+")

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

def show(label, d):
    print(f"\n=== {label} ===")
    tot = [0, 0]
    for t in ("top-16", "17-64", "65+"):
        fo, n = d[t]; tot[0] += fo; tot[1] += n
        if n: print(f"  {t:7}: fold {100*fo/n:4.0f}%   (n={n})")
    t16_64 = [d["top-16"][i] + d["17-64"][i] for i in range(2)]
    if t16_64[1]: print(f"  TOP-64 : fold {100*t16_64[0]/t16_64[1]:4.0f}%   (n={t16_64[1]})")
    if tot[1]:    print(f"  ALL    : fold {100*tot[0]/tot[1]:4.0f}%   (n={tot[1]})")

show("FOLD-TO-3BET (opener faces a 3-bet)", f3)
show("FOLD-TO-4BET (3-bettor faces a 4-bet)", f4)
