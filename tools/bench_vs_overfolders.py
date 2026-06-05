"""CRN upside test: v23 / v22 / v21 each vs 5 calibrated over-folders, same seeds.
Proves whether v23's 3-bet/4-bet pressure converts the field's measured 90% fold
into chips (what the realistic sim field cannot show)."""
import json, statistics, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from math import sqrt, erf

REPO = "/Users/timo/claudettesting/blackswan/fullhouse-engine"
OPPS = [f"bots/field/finalist/of{i}" for i in range(1, 6)]
HEROES = {"v23": "bots/tumbleweeddutch_v23", "v22": "bots/tumbleweeddutch_v22",
          "v21": "bots/tumbleweeddutch_v21"}
SEEDS = int(sys.argv[1]) if len(sys.argv) > 1 else 80
HANDS = int(sys.argv[2]) if len(sys.argv) > 2 else 300
BASE = int(sys.argv[3]) if len(sys.argv) > 3 else 91000

def run(job):
    hero_key, hero_path, seed = job
    cmd = [sys.executable, "sandbox/match.py", hero_path, *OPPS,
           "--hands", str(HANDS), "--seed", str(seed), "--json"]
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO)
    try:
        d = json.loads(p.stdout)
        key = [k for k in d["chip_delta"] if k.startswith("tumbleweeddutch")][0]
        return hero_key, seed, d["chip_delta"][key]
    except Exception:
        return hero_key, seed, None

jobs = [(hk, hp, BASE + s) for s in range(SEEDS) for hk, hp in HEROES.items()]
with ThreadPoolExecutor(max_workers=6) as ex:
    res = list(ex.map(run, jobs))

by = {k: {} for k in HEROES}
for hk, seed, cd in res:
    if cd is not None:
        by[hk][seed] = cd

def stats(xs):
    m = statistics.mean(xs); sd = statistics.pstdev(xs)
    return m, sd, sum(1 for x in xs if x == 50000), sum(1 for x in xs if x == -10000)

print(f"=== vs 5 calibrated over-folders ({SEEDS} seeds x {HANDS}h, CRN) ===")
for hk in ("v21", "v22", "v23"):
    xs = list(by[hk].values())
    m, sd, sc, bu = stats(xs)
    print(f"  {hk}: mean {m:+8.0f}  scoop {sc:>2}/{len(xs)} ({100*sc/len(xs):.0f}%)  bust {bu:>2} ({100*bu/len(xs):.0f}%)  sd {sd:.0f}")

def paired(a, b):
    common = sorted(set(by[a]) & set(by[b]))
    diffs = [by[a][s] - by[b][s] for s in common]
    m = statistics.mean(diffs); sd = statistics.pstdev(diffs)
    se = sd / sqrt(len(diffs)) if diffs else 0
    z = m / se if se else 0
    p = 2 * (1 - 0.5 * (1 + erf(abs(z) / sqrt(2))))
    return m, 1.96 * se, z, p, len(diffs)

for a, b in [("v23", "v22"), ("v23", "v21"), ("v22", "v21")]:
    m, ci, z, p, n = paired(a, b)
    flag = "  <-- SIGNIFICANT" if p < 0.05 else ""
    print(f"  paired {a}-{b}: {m:+8.0f} ± {ci:.0f}  z={z:+.2f} p={p:.3f} (n={n}){flag}")
