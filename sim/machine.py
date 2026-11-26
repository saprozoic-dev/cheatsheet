"""Machine model. Rebuilt Oct 31 after a workspace reset (same method as before)."""
import numpy as np

def T(odds, axis, mn, mx, avg, med, items, total, counts, bins=None):
    """One tier as read off the tracker. avg is recomputed as total/items.
    counts: cards per histogram bar. bins (optional): each bar's own [lo, hi] value range;
    without it the bars split axis into equal widths (the old tracker's 20-bar panel)."""
    return dict(odds=odds, axis=tuple(axis), mn=mn, mx=mx, shown_avg=avg, med=med,
                items=items, total=total, avg=total / items, counts=list(counts),
                bins=[tuple(b) for b in bins] if bins else None)

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
        b = rng.choice(len(c), size=size, p=c / c.sum())
        if d.get('bins'):   # bars with their own ranges (v1 API)
            edges = np.asarray(d['bins'], dtype=float)
            v = edges[b, 0] + rng.random(size) * (edges[b, 1] - edges[b, 0])
        else:               # equal-width bars across the tier's axis (old tracker)
            lo, hi = d['axis']; w = (hi - lo) / len(c)
            v = lo + (b + rng.random(size)) * w
        v = np.clip(v, mn, mx)
        for _ in range(4):   # rescale + clip, repeated so clipping does not shift the mean
            m = v.mean()
            if abs(m - avg) < 1e-6 or m == mn: break
            v = np.clip(mn + (v - mn) * (avg - mn) / (m - mn), mn, mx)
        return v
