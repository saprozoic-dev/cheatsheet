"""Per-machine 'what to expect as you roll' stats, merged into sheetdata.json."""
import numpy as np, warnings, json
warnings.filterwarnings('ignore')
from sweep2 import MACH, BANKS, BOTNET, FILL, fam
rng = np.random.default_rng(23)
out = {}
for nm, x, fr, f in MACH:
    r = x.sample('rare', 400000, rng) * x.buyback - x.cost
    e = x.sample('epic', 100000, rng) * x.buyback - x.cost
    big = np.concatenate([r, e])
    mul = (BOTNET*f + x.buyback*(1-f)) if f else x.buyback
    floor = x.cost - x.tiers['common']['avg'] * mul
    out[nm] = dict(
        hitmed=round(float(np.median(big))),
        hitodds=round((x.tiers['rare']['odds'] + x.tiers['epic']['odds']) * 100),
        clr={str(B): round(float((big >= B).mean()) * 100, 1) for B in BANKS},
        dry={str(B): int(max(0, (B - x.cost)) // max(floor, 0.01)) + (1 if B >= x.cost else 0) for B in BANKS},
    )
D = json.load(open('sheetdata.json'))
for m in D['mach']: m.update(out[m['n']])
json.dump(D, open('sheetdata.json', 'w'))
print('hitstats ok')
