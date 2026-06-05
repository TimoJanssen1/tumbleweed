"""How I actually did, from the real Q2 logs: chip-Δ by how many top-64 bots
were at the table (the "I farmed weak tables" chart), plus per-opponent detail."""
import sys, os, statistics
from collections import Counter, defaultdict
import eval7
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from parse import attribute_match, clean_matches, our_id, segment_hand

LB = ["jew","CallMeMaybe","SevenDeuces","NecessarySkew","Looper257","Oxvard","BussBot-v3","Taleto13","winning",
 "CrimsonBot","FerdaBot","Khan’t Fold","make_no_mistakes","Tumble-Weed-Dutch-v2","Lekemog","ant-bot","twader",
 "Hyperion","durak","jotaroZAWARUDO","TheQuantBot","talan","Overfitted","Inefficiency","+ev","Pantheon",
 "sam_bot_lfg_2","50CentRaise","IveyBot","𝐛𝐚𝐯","poker? I barely know her","pavan kumar","I hate arsenal","Pascal",
 "RODBOTv2","BATNEEC","GrandSlam","Javis","Freelo","Super2Trooper","goku","72o","alan","elprofesoriqo",
 "not_so_simple_bot","Lyra","SaviourBot","TheHouse","I'mDeffoCappin","VolatileNeuron","never played poker",
 "gems_VC2","PhoonTooMuchForPoker","Thorp","SummerSun","SuperExtraDeluxeMegaBot","NEMESIS","G-Forge",
 "TheCrystalline","Bot2","BeginnersLuck V3","Foldilocks","BOTv2","Worm"]
RANK={n:i+1 for i,n in enumerate(LB)}
def rank_of(n): return RANK.get(n,200)
def tier(n):
    r=rank_of(n)
    return "T16" if r<=16 else ("T17-64" if r<=64 else "65+")

def preflop_actions(h):
    return [a for a in h["action_log"] if a.get("street")=="preflop"]

def main():
    cm=clean_matches()
    oid_name="Tumble-Weed-Dutch-v2"
    # per-opponent encounter + showdown
    enc=defaultdict(lambda: {"hands":0,"sd":0,"sd_w":0,"hu_net":0,"hu_n":0,"open_vs_us":0,
                             "they3bet_us":0,"we_folded_to_their_3bet":0})
    # behavioral splits by opponent tier
    vs_open=defaultdict(Counter)       # tier -> our response to their open
    we_open_3bet=defaultdict(Counter)  # tier of 3bettor -> our response
    cbet_vs=defaultdict(Counter)       # tier of caller -> cbet/check
    table_results=[]                   # (n_top64_opps, our_chip_delta)
    sd_by_tier=defaultdict(lambda:[0,0])  # tier -> [W,L]
    for fn,d in cm:
        per,_,_,name,id_orig=attribute_match(d)
        oid=our_id(d)
        cd=[b for b in d["bots"] if b["bot_name"]==oid_name][0]["chip_delta"] or 0
        opps=[b["bot_name"] for b in d["bots"] if b["bot_name"]!=oid_name]
        table_results.append((sum(1 for o in opps if rank_of(o)<=64), cd, opps))
        for rec in per:
            h=rec["h"]; amap=rec["amap"]
            if oid not in amap.values():  # we're busted/out
                continue
            myseat=[s for s,b in amap.items() if b==oid][0]
            seat2id=amap
            # opponents present this hand
            for s,bid in amap.items():
                if bid!=oid: enc[name[bid]]["hands"]+=1
            pre=preflop_actions(h)
            # identify raisers in order
            raisers=[(a["seat"]) for a in pre if a["action"] in("raise","all_in")]
            # our first voluntary preflop action + context
            nr=0; resp=None; faced=None
            opener=None; three_bettor=None
            for a in pre:
                s=a["seat"]
                if a["action"] in("raise","all_in"):
                    if nr==0: opener=s
                    elif nr==1: three_bettor=s
                    nr_after=nr+1
                if s==myseat and a["action"] not in("small_blind","big_blind") and resp is None:
                    resp=a["action"]; faced=nr
                if a["action"] in("raise","all_in"): nr+=1
            # (a) facing an open (someone opened before our first action, we are not opener)
            if faced==1 and resp is not None and opener is not None and amap.get(opener)!=oid:
                opp=name[amap[opener]]; vs_open[tier(opp)][resp if resp in("fold","call") else "3bet"]+=1
                enc[opp]["open_vs_us"]+=1
            # (b) we opened, someone 3bet
            we_opened = (opener is not None and amap.get(opener)==oid)
            if we_opened and three_bettor is not None and amap.get(three_bettor)!=oid:
                tb=name[amap[three_bettor]]
                we_open_3bet[tier(tb)]["spots"]+=1
                enc[tb]["they3bet_us"]+=1
                our_pre=[a for a in pre if a["seat"]==myseat and a["action"] not in("small_blind","big_blind")]
                last=our_pre[-1]["action"] if our_pre else "fold"
                key="fold" if last=="fold" else ("4bet" if last in("raise","all_in") else "call")
                we_open_3bet[tier(tb)][key]+=1
                if key=="fold": enc[tb]["we_folded_to_their_3bet"]+=1
            # (c) c-bet: we are last preflop raiser, single caller, what do we do on flop
            if raisers and amap.get(raisers[-1])==oid:
                flop=[a for a in h["action_log"] if a.get("street")=="flop"]
                callers=[amap.get(s) for s in set(a["seat"] for a in pre if a["action"]=="call")]
                callers=[c for c in callers if c and c!=oid]
                if flop and len(callers)==1:
                    ct=tier(name[callers[0]])
                    of=[a for a in flop if a["seat"]==myseat]
                    if of and of[0]["action"] in("raise","all_in"): cbet_vs[ct]["cbet"]+=1
                    elif of and of[0]["action"]=="check": cbet_vs[ct]["check"]+=1
            # (d) showdowns & HU pots via stable ids
            rc=h.get("revealed_cards",{})
            if oid in rc and len(rc)>=2:
                board=h["community_cards"]
                we_won = oid in [w["bot_id"] for w in h["winners"]]
                # opponents in showdown
                for xb in rc:
                    if xb==oid: continue
                    t=tier(name[xb]);
                    if we_won: sd_by_tier[t][0]+=1; enc[name[xb]]["sd_w"]+=1
                    else: sd_by_tier[t][1]+=1
                    enc[name[xb]]["sd"]+=1
            # HU pot net (only us + one opp contributed beyond blinds) via authoritative winnings
            contribs=[s for s in amap if rec["h"]]  # placeholder
    # ---- OUTPUT ----
    print("=== SHOWDOWN RECORD BY OPPONENT TIER (all-in & non-all-in showdowns, stable ids) ===")
    for t in ["T16","T17-64","65+"]:
        w,l=sd_by_tier[t]; tot=w+l
        if tot: print(f"  {t:7}: {w}W/{l}L  ({100*w/tot:.0f}% win)  n={tot}")
    print("\n=== FACING AN OPEN, by opener tier (our response) ===")
    for t in ["T16","T17-64","65+"]:
        c=vs_open[t]; n=sum(c.values())
        if n: print(f"  vs {t:7} open ({n}): fold {100*c['fold']/n:.0f}%  call {100*c['call']/n:.0f}%  3bet {100*c['3bet']/n:.0f}%")
    print("\n=== WE OPEN, THEY 3-BET, by 3-bettor tier (our response) — THE EXPLOIT ===")
    for t in ["T16","T17-64","65+"]:
        c=we_open_3bet[t]; n=c["spots"]
        if n: print(f"  3-bet by {t:7} ({n}): FOLD {100*c['fold']/n:.0f}%  call {100*c['call']/n:.0f}%  4bet {100*c['4bet']/n:.0f}%")
    print("\n=== C-BET when single caller is of tier ===")
    for t in ["T16","T17-64","65+"]:
        c=cbet_vs[t]; n=c["cbet"]+c["check"]
        if n: print(f"  caller {t:7} ({n} flops): c-bet {100*c['cbet']/n:.0f}%  check {100*c['check']/n:.0f}%")
    print("\n=== RESULT vs # TOP-64 OPPONENTS AT TABLE ===")
    byn=defaultdict(list)
    for ntop,cd,opps in table_results: byn[ntop].append(cd)
    for ntop in sorted(byn):
        v=byn[ntop]; print(f"  {ntop} top-64 opps: n={len(v)} mean {statistics.mean(v):+,.0f} scoop {sum(1 for x in v if x==50000)} bust {sum(1 for x in v if x==-10000)}")
    print("\n=== TOP-64 OPPONENTS WE FACED (encounter detail, sorted by rank) ===")
    rows=[(rank_of(n),n,e) for n,e in enc.items() if rank_of(n)<=64]
    for r,n,e in sorted(rows):
        f3=f"{e['we_folded_to_their_3bet']}/{e['they3bet_us']}" if e['they3bet_us'] else "-"
        print(f"  #{r:<3}{n:<26} hands={e['hands']:<5} SD {e['sd_w']}W/{e['sd']-e['sd_w']}L  3bet-us {e['they3bet_us']:<3} (we-fold {f3})")
    print("\n=== who 3-bets us most (any tier) ===")
    top3=sorted(enc.items(), key=lambda kv:-kv[1]["they3bet_us"])[:12]
    for n,e in top3:
        if e["they3bet_us"]: print(f"  {n} (#{rank_of(n)}): 3bet us {e['they3bet_us']}x, we folded {e['we_folded_to_their_3bet']}")

if __name__=="__main__":
    main()
