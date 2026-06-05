"""Parse the real Fullhouse match logs into something analysable.
Two jobs: (1) segment each hand into streets from the flat action log; (2) attribute
chips to the right bot despite the export reindexing seats on bust and logging
"intended" all-in amounts (stack-capped forward sim, validated 100% on an invariant).
Set Q2_MATCH_DIR to the match-history folder. Imported by the other read_logs scripts."""

import json, glob, os, sys
from collections import defaultdict, Counter

DIR = os.environ.get("Q2_MATCH_DIR",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "matchhistoryq2"))
OURS = "Tumble-Weed-Dutch-v2"
STREETS = ["preflop", "flop", "turn", "river"]

def load_matches():
    out = []
    for fn in sorted(glob.glob(os.path.join(DIR, "*.json"))):
        out.append((fn, json.load(open(fn))))
    return out

def segment_hand(hand):
    """Return (streets, chips_added, ok) where:
       streets = list of (street_name, [action dicts]) for streets that had actions
       chips_added = dict seat-> total chips put in hand (for pot reconciliation)
       ok = (pot_reconciles, street_matches)
    Also annotates each action dict with 'street'."""
    al = hand["action_log"]
    dealt = sorted(set(a["seat"] for a in al))
    folded = set(); allin = set()
    active = set(dealt)
    chips = defaultdict(int)         # total chips in hand per seat
    contrib = defaultdict(int)       # this-street commitment
    high = 0
    need = set()                     # active non-allin seats still to act this street
    street_idx = 0
    streets = [(STREETS[0], [])]
    # find blind entries (always first two for a normal hand)
    i = 0
    # process blinds
    while i < len(al) and al[i]["action"] in ("small_blind", "big_blind"):
        a = al[i]; s = a["seat"]
        contrib[s] = a["amount"]; chips[s] += a["amount"]
        high = max(high, a["amount"])
        a["street"] = "preflop"; streets[0][1].append(a)
        i += 1
    need = set(s for s in active if s not in allin)   # all act preflop (blinds get option)
    def close_and_advance():
        nonlocal street_idx, high, contrib, need
        street_idx += 1
        if street_idx < len(STREETS):
            streets.append((STREETS[street_idx], []))
        high = 0
        contrib = defaultdict(int)
        need = set(s for s in active if s not in allin)
    for a in al[i:]:
        s = a["seat"]; act = a["action"]
        # if current street's need already empty, advance to next street first
        if not need:
            close_and_advance()
        a["street"] = streets[street_idx][0]
        streets[street_idx][1].append(a)
        before = contrib[s]
        if act == "fold":
            folded.add(s); active.discard(s); need.discard(s)
        elif act == "check":
            need.discard(s)
        elif act == "call":
            contrib[s] += a["amount"]; chips[s] += a["amount"]; need.discard(s)
        elif act == "raise":
            chips[s] += a["amount"] - before; contrib[s] = a["amount"]; high = a["amount"]
            need = set(x for x in active if x not in allin and x != s)
        elif act == "all_in":
            chips[s] += a["amount"] - before; contrib[s] = a["amount"]
            if a["amount"] > high:
                high = a["amount"]; need = set(x for x in active if x not in allin and x != s)
            else:
                need.discard(s)
            allin.add(s); need.discard(s)
        # closure
        if not need:
            pass  # will advance on next action or end
    # validation
    pot_calc = sum(chips.values())
    pot_ok = (pot_calc == hand["pot"])
    # last street with actions OR with community cards
    ncards = len(hand["community_cards"])
    implied_last = "preflop" if ncards == 0 else ("flop" if ncards == 3 else ("turn" if ncards == 4 else "river"))
    street_ok = (streets[-1][0] == hand["street_ended"]) or (hand["street_ended"] == implied_last)
    return streets, chips, (pot_ok, street_ok)

if __name__ == "__main__":
    matches = load_matches()
    tot_delta = 0; per_match = []; busts = 0; errs = 0
    pot_ok = pot_bad = street_ok = street_bad = 0
    hands_total = 0
    for fn, d in matches:
        ours = [b for b in d["bots"] if b["bot_name"] == OURS][0]
        cd = ours["chip_delta"] if ours["chip_delta"] is not None else 0
        tot_delta += cd
        per_match.append((cd, d.get("round"), os.path.basename(fn), len(d["hands"]),
                          [b["bot_name"] for b in d["bots"]], d.get("status")))
        if cd == -10000: busts += 1
        errs += len(ours.get("bot_errors") or [])
        for h in d["hands"]:
            hands_total += 1
            _, _, (po, so) = segment_hand(h)
            pot_ok += po; pot_bad += (not po)
            street_ok += so; street_bad += (not so)
    print(f"=== OVERALL (40 matches, our bot = {OURS}) ===")
    print(f"  total cumulative chip-delta : {tot_delta:+,}")
    print(f"  mean per match              : {tot_delta/len(matches):+,.0f}")
    print(f"  matches                     : {len(matches)}   busts(-10k): {busts}   scoops(+50k): {sum(1 for x in per_match if x[0]==50000)}")
    print(f"  total hands                 : {hands_total}")
    print(f"  our bot_errors              : {errs}")
    print(f"\n=== PARSER VALIDATION ===")
    print(f"  pot reconciles    : {pot_ok}/{hands_total} ({100*pot_ok/hands_total:.2f}%)   bad={pot_bad}")
    print(f"  street_ended match: {street_ok}/{hands_total} ({100*street_ok/hands_total:.2f}%)  bad={street_bad}")
    print(f"\n=== PER-MATCH (sorted by our delta) ===")
    for delta, rnd, fn, nh, names, status in sorted(per_match):
        opps = [n for n in names if n != OURS]
        print(f"  {delta:+7,}  round {str(rnd):>3}  {nh:>4}h  [{status}]  vs {', '.join(opps)}")


# ---- chip attribution (stack-capped forward simulation) ----
def attribute_match(d):
    id_orig = {b["bot_id"]: b["seat"] for b in d["bots"]}     # id -> initial seat
    orig_id = {s: i for i, s in id_orig.items()}              # initial seat -> id
    name = {b["bot_id"]: b["bot_name"] for b in d["bots"]}
    stack = {i: 10000 for i in id_orig}
    # last hand index each id appears in winners/revealed (anchors bust timing)
    last_seen = {i: -1 for i in id_orig}
    for hi, h in enumerate(d["hands"]):
        for w in h["winners"]:
            if w["bot_id"] in last_seen: last_seen[w["bot_id"]] = hi
        for k in h.get("revealed_cards", {}):
            if k in last_seen: last_seen[k] = hi
    alive = sorted(id_orig.values())                          # initial seats alive (asc)
    per_hand = []
    for hi, h in enumerate(d["hands"]):
        aseats = sorted(set(a["seat"] for a in h["action_log"]))
        k = len(aseats)
        # drive alive-set by table size: if more 'alive' than seats, the surplus
        # ids (those whose last appearance is earliest, i.e. already done) busted.
        if len(alive) > k:
            surplus = len(alive) - k
            # candidates to drop: alive ids that won't appear again at/after this hand
            ranked = sorted(alive, key=lambda s: last_seen[orig_id[s]])
            drop = set(ranked[:surplus])
            alive = [s for s in alive if s not in drop]
        amap = {}                                             # action-seat -> id
        for i, asx in enumerate(aseats):
            if i < len(alive):
                amap[asx] = orig_id[alive[i]]
        _, chips, _ = segment_hand(h)
        won = {}
        for w in h["winners"]:
            won[w["bot_id"]] = won.get(w["bot_id"], 0) + w["amount"]
        contrib_id = {}
        for asx, bid in amap.items():
            c = min(chips.get(asx, 0), stack[bid])            # cap at available stack
            contrib_id[bid] = c
            stack[bid] -= c
        for bid, amt in won.items():
            stack[bid] = stack.get(bid, 0) + amt
        net = {bid: won.get(bid, 0) - contrib_id.get(bid, 0)
               for bid in set(list(contrib_id) + list(won))}
        per_hand.append({"h": h, "amap": amap, "won": won,
                         "contrib": contrib_id, "net": net, "stack": dict(stack)})
        # also drop anyone who actually busted to 0 (belt and suspenders)
        alive = [s for s in alive if stack[orig_id[s]] > 0]
    ok = True
    for b in d["bots"]:
        fs = b["final_stack"]
        if fs is not None and abs(stack[b["bot_id"]] - fs) > 1:
            ok = False
    return per_hand, ok, stack, name, id_orig

def our_id(d):
    return [b["bot_id"] for b in d["bots"] if b["bot_name"] == OURS][0]

def clean_matches():
    return [(fn, d) for fn, d in load_matches()
            if len(d["bots"]) == 6 and d.get("status") == "complete"]
