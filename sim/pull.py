"""Pull every open machine's odds + inventory stats from Knut's Gap Tracker.

  python3 pull.py pull.json

Same requests as the old browser pull (pull.js): one list call, then two
small calls per open machine, spaced 0.4 s apart to go easy on the tracker.
Writes {t, m: {code: [price, buyback, name, [tier x4]]}} for site2db.py.
"""
import json, math, sys, time, urllib.request, datetime

BASE = "https://gap.knutegil.dev"
UA = "Epicenter cheatsheet (epicenter.saprozoic.dev) - twice-daily read of public stats"
ORDER = ["Common", "Uncommon", "Rare", "Epic"]
SPACING = 0.4

def get(path, tries=3):
    for attempt in range(1, tries + 1):
        try:
            req = urllib.request.Request(BASE + path, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception as e:
            if attempt == tries:
                raise RuntimeError(f"{path}: {e}")
            time.sleep(5 * attempt)

def r2(x):  # same rounding as JS Math.round(x*100)/100
    return math.floor(x * 100 + 0.5) / 100

def main(dst):
    machines = get("/api/stats/machines")["data"]
    out = {"t": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"), "m": {}}
    for m in machines:
        if m.get("status") and m["status"] != "open":
            continue
        code = m["code"]
        s = get(f"/api/stats/machines/{code}"); time.sleep(SPACING)
        v = get(f"/api/inventory/machines/{code}/stats"); time.sleep(SPACING)
        ax = {t["name"]: [t.get("minValue"), t.get("maxValue"), t.get("probability")] for t in s["tiers"]}
        vt = {t["tierName"]: t for t in v["tiers"]}
        tiers = []
        for n in ORDER:
            a = ax.get(n, [0, 0, 0]); t = vt.get(n)
            if t:
                # The tracker now leaves the top tier open-ended (maxValue null, Nov 24 2026).
                # The 20 histogram bars carry their own edges, so use those for the range
                # whenever the tier itself gives none.
                h = t.get("histogram") or []
                lo = a[0] if a[0] is not None else (h[0].get("min") if h else t["minValue"])
                hi = a[1] if a[1] is not None else (h[-1].get("max") if h and h[-1].get("max") is not None else t["maxValue"])
                tiers.append([lo, hi, a[2], t["count"], t["minValue"], t["maxValue"], r2(t["medianValue"]),
                              t["totalValue"], [h["count"] for h in t["histogram"]]])
            else:
                tiers.append([a[0], a[1], a[2], 0])
        out["m"][code] = [m["priceUsd"], m["buybackPercentage"], m["name"], tiers]
        print(f"  {code}", flush=True)
    if len(out["m"]) < 30:
        raise SystemExit(f"only {len(out['m'])} machines - tracker looks wrong, not publishing")
    json.dump(out, open(dst, "w"))
    print(f"pulled {len(out['m'])} machines at {out['t']}")

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "pull.json")
