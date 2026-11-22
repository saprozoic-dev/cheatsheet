"""Epic view: per machine, what waiting for an epic costs, what the epic pays, and for each bankroll
how many pulls it buys with no epic and the chance at least one epic lands before the money runs out.

  python3 epicsim.py            -> epicdata.json   (fill_page.py reads it)

wait   = money lost over 100 pulls when the epic's payout is left out
         = 100*pack - 100*(common, uncommon, rare returns at their normal odds)
eavg   = average epic payout after buyback;  emed = median epic payout after buyback
pulls  = median pulls before the balance drops below one pack if no epic lands
ch     = chance of at least one epic before that happens = 1 - E[0.99^N]   (exact given the walk:
         the first epic arrives at a geometric time that is independent of the non-epic outcomes)
"""
import numpy as np, json, sys, time, warnings
warnings.filterwarnings('ignore')
import sweep2
from sweep2 import MACH, BOTNET, BOTT, BANKS

GRID = sorted(set(BANKS + [75]))
TP, CH, BLK = 4000, 500, 1000
PE = 0.01

def pools(x, fill):
    rng = np.random.default_rng(17); r2 = np.random.default_rng(3)
    ps = []
    for t in ('common', 'uncommon', 'rare'):
        n = max(1, int(round(x.tiers[t]['odds'] * 1_200_000)))
        s = x.sample(t, n, rng).astype(np.float64)
        if fill and t in BOTT:
            p = np.where(r2.random(s.size) < fill, s*BOTNET, s*x.buyback)
        else:
            p = s * x.buyback
        ps.append(p)
    nonepic = np.concatenate(ps)                       # payouts of non-epic pulls, in odds proportion
    ep = x.sample('epic', 200000, rng) * x.buyback
    return nonepic, ep

def one(nm, x, f):
    assert abs(x.tiers['epic']['odds'] - PE) < 1e-9
    nonepic, ep = pools(x, f)
    net = (nonepic - x.cost).astype(np.float32)
    wait = 100*x.cost - 99*float(nonepic.mean())      # 100 packs bought, 99 non-epic pulls pay back
    banks = [B for B in GRID if B >= x.cost]
    th = np.array([x.cost - B for B in banks], dtype=np.float64)       # bust when cumulative net < th
    N = np.zeros((TP, len(banks)), dtype=np.int64)
    r = np.random.default_rng(11)
    for c0 in range(0, TP, CH):
        cum = np.zeros(CH); rmin = np.full(CH, np.inf)
        first = np.zeros((CH, len(banks)), dtype=np.int64)             # 0 = not yet bust
        k = 0
        while (first == 0).any():
            cs = cum[:, None] + np.cumsum(net[r.integers(0, net.size, (CH, BLK))], axis=1, dtype=np.float64)
            rm = np.minimum(np.minimum.accumulate(cs, axis=1), rmin[:, None])
            for j in range(len(banks)):
                todo = first[:, j] == 0
                if not todo.any(): continue
                alive = (rm[todo] >= th[j]).sum(axis=1)                 # rm is non-increasing along a row
                hit = alive < BLK
                idx = np.where(todo)[0][hit]
                first[idx, j] = k + alive[hit] + 1
            cum = cs[:, -1]; rmin = rm[:, -1]; k += BLK
            if k > 400000: raise RuntimeError('no bust: ' + nm)
        N[c0:c0+CH] = first
    pulls = np.median(N, axis=0)
    ch = 1 - np.power(1 - PE, N).mean(axis=0)
    out = dict(cost=int(x.cost), wait=round(wait, 2), eavg=round(float(x.tiers['epic']['avg']*x.buyback), 2),
               emed=round(float(np.median(ep)), 2), ne=int(x.tiers['epic']['items']),
               nc=int(x.tiers['common']['items']),
               pulls=[None]*len(GRID), ch=[None]*len(GRID))
    for B, p, c in zip(banks, pulls, ch):
        i = GRID.index(B); out['pulls'][i] = int(round(float(p))); out['ch'][i] = round(float(c)*100, 2)
    return out

if __name__ == '__main__':
    res = {}; t0 = time.time()
    for nm, x, fr, f in MACH:
        res[nm] = one(nm, x, f)
        print(f"  {nm:<22} wait {res[nm]['wait']:>9.0f}  epic {res[nm]['eavg']:>8.0f}  t={time.time()-t0:5.1f}s",
              file=sys.stderr, flush=True)
    json.dump(dict(grid=GRID, m=res), open('epicdata.json', 'w'), separators=(',', ':'))
    print('OK', len(res), 'machines')
