"""Chunked sweep.  python3 run_sel.py <tag> 'A|B'  (low rows)  /  python3 run_hi.py <tag> 'A|B'  (high rows)
Each writes part_*.pkl.  Then:  python3 sweep2.py merge
"""
import numpy as np, warnings, json, time, sys, pickle, os
warnings.filterwarnings('ignore')
from db import BOARD, RECON

BOTNET = 0.90 * 0.98      # bot pays 90% of insured value, less the 2% seller fee
FILL   = 0.75             # fills about three times in four
BOTT   = {'common', 'uncommon'}
BOT_MACHINES = set()   # bot routing removed from the public sheet

BANKS_LO = [25] + list(range(50, 501, 50)) + list(range(600, 3001, 100))
BANKS_HI = [3500, 4000, 4500, 5000, 6000, 7000, 8000, 9000, 10000,
            12000, 14000, 16000, 18000, 20000]
BANKS = BANKS_LO + BANKS_HI
HI_MULT = 100      # above $3,000 a machine is only simulated if bank <= 100 x pack price
T = 30000

def hit(x):
    return (.04*x.tiers['rare']['avg'] + .01*x.tiers['epic']['avg'])/.05 * x.buyback

def build(x, fill):
    rng = np.random.default_rng(17); r2 = np.random.default_rng(3)
    vs, ps = [], []
    for t in x.tiers:
        n = max(1, int(round(x.tiers[t]['odds'] * 1_200_000)))
        s = x.sample(t, n, rng).astype(np.float32)
        if fill and t in BOTT:
            p = np.where(r2.random(s.size) < fill, s*BOTNET, s*x.buyback)
        else:
            p = s * x.buyback
        vs.append(s); ps.append(p.astype(np.float32))
    v = np.concatenate(vs); p = np.concatenate(ps)
    return (p - x.cost).astype(np.float32), float(p.mean()/v.mean())

MACH = []
for nm, x, fr in BOARD:
    MACH.append((nm, x, fr, 0.0))
    if nm in BOT_MACHINES:
        MACH.append((nm + ' + bot', x, fr, FILL))

def fam(s): return s.replace(' + bot', '')

BANKS_SEL = BANKS_LO

def simulate(sel):
    res, eff = {}, {}
    t0 = time.time()
    for nm, x, fr, f in sel:
        net, e = build(x, f); eff[nm] = e
        for B in BANKS_SEL:
            if B < x.cost: continue
            hi = B in BANKS_HI
            if hi and B > HI_MULT * x.cost: continue
            b = np.full(T, float(B)); done = np.zeros(T, bool)
            n = np.zeros(T, int);     pk = np.full(T, float(B))
            r = np.random.default_rng(11)
            # high rows stop a session once it doubles (median packs = packs to double-or-bust)
            for _ in range(60000 if hi else 9000):
                live = ~done
                if not live.any(): break
                b[live] += net[r.integers(0, net.size, live.sum())]; n[live] += 1
                pk = np.maximum(pk, b); done = b < x.cost
                if hi: done |= pk >= 2*B
            res[(nm, B)] = dict(d2=float((pk >= 2*B).mean()), md=int(np.median(n)),
                                k1=float((pk >= 5000).mean()))
        print(f"  {nm:<24} t={time.time()-t0:6.1f}s", file=sys.stderr, flush=True)
    return res, eff


def merge():
    res, eff = {}, {}
    for fn in sorted(os.listdir('.')):
        if fn.startswith('part_') and fn.endswith('.pkl'):
            r, e = pickle.load(open(fn, 'rb')); res.update(r); eff.update(e)
    names = [nm for nm, _, _, _ in MACH]
    missing = [nm for nm in names if nm not in eff]
    if missing:
        print('MISSING:', missing, file=sys.stderr); sys.exit(1)

    def rank(ns):
        out = []
        for B in BANKS:
            av = [(nm, res[(nm, B)]) for nm in ns if (nm, B) in res]
            if not av: continue
            by = sorted(av, key=lambda z: -z[1]['d2']); top = by[0][0]
            rest = [z for z in by[1:] if fam(z[0]) != fam(top)]
            bymd = sorted(av, key=lambda z: -z[1]['md'])
            p_ = by[0][1]['d2']
            q_ = rest[0][1]['d2'] if rest else 0.0
            se = ((p_*(1-p_)/T) + (q_*(1-q_)/T)) ** 0.5
            out.append(dict(bank=B, best=top, p2=round(p_*100, 2), md=by[0][1]['md'],
                            second=(rest[0][0] if rest else '—'),
                            p2b=round(q_*100, 2),
                            tie=bool(rest) and abs(p_-q_) < 2*se,
                            lng=bymd[0][0], lngmd=bymd[0][1]['md'],
                            k1=round(by[0][1]['k1']*100, 2), z='b'))
        return out

    rows_bot   = rank(names)
    rows_nobot = rank([n for n in names if '+ bot' not in n])

    ms = []
    for nm, x, fr, f in MACH:
        c = x.tiers['common']; u = x.tiers['uncommon']
        mul = (BOTNET*f + x.buyback*(1-f)) if f else x.buyback
        ms.append(dict(n=nm, cost=int(x.cost), bb=round(eff[nm]*100, 1),
                       sus=round(x.ev()*eff[nm]/x.cost*100, 2), hit=round(hit(x)),
                       floor=round(x.cost - c['avg']*mul, 2),
                       step=round(u['avg']*mul - x.cost, 2),
                       fresh=fr, bot=bool(f), recon=fam(nm) in RECON))
    ms.sort(key=lambda z: -z['sus'])
    json.dump(dict(rows=rows_bot, rows_nobot=rows_nobot, mach=ms, T=T),
              open('sheetdata.json', 'w'))

    for lab, rr in [("WITH BOT", rows_bot), ("NO BOT", rows_nobot)]:
        print("\n== " + lab + " ==")
        for r in rr:
            print(f"  ${r['bank']:<6,} {r['best']:<22} {r['p2']:5.2f}%   2nd {r['second']:<22} "
                  f"{r['p2b']:5.2f}%{'   TIE' if r['tie'] else ''}")
    print(f"\nOK {len(rows_bot)} rows, {len(ms)} machines, T={T}")


if __name__ == '__main__':
    if sys.argv[1] == 'merge':
        merge()
