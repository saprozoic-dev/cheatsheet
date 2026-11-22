"""Machine model. Rebuilt Oct 31 after a workspace reset (same method as before)."""
import numpy as np

def T(odds, axis, mn, mx, avg, med, items, total, counts):
    """One tier as read off the Value Distribution panel. avg is recomputed as total/items."""
    return dict(odds=odds, axis=tuple(axis), mn=mn, mx=mx, shown_avg=avg, med=med,
                items=items, total=total, avg=total / items, counts=list(counts))

class Machine:
    def __init__(self, name, cost, buyback, recon, tiers):
        self.name, self.cost, self.buyback, self.recon, self.tiers = name, float(cost), buyback, recon, tiers

    def ev(self):
        return sum(t['odds'] * t['avg'] for t in self.tiers.values())

    def sustain(self):
        return self.ev() * self.buyback / self.cost

    def sample(self, tier, size, rng):
        """Empirical draw from the 20-bar histogram: pick a bar by count, uniform inside it,
        then rescale about the tier minimum so the mean is exactly total/items, clipped to [min,max]."""
        d = self.tiers[tier]
        mn, mx, avg = float(d['mn']), float(d['mx']), float(d['avg'])
        c = np.asarray(d['counts'], dtype=float)
        lo, hi = d['axis']; w = (hi - lo) / len(c)
        b = rng.choice(len(c), size=size, p=c / c.sum())
        v = lo + (b + rng.random(size)) * w
        v = np.clip(v, mn, mx)
        for _ in range(4):   # rescale + clip, repeated so clipping does not shift the mean
            m = v.mean()
            if abs(m - avg) < 1e-6 or m == mn: break
            v = np.clip(mn + (v - mn) * (avg - mn) / (m - mn), mn, mx)
        return v
