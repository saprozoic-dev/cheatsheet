"""Pull every open machine's odds + pool stats from Knut's Gap Tracker API (v1).

  python3 pull.py pull.json

Uses the public v1 API (https://holoscope.app/developers):
  GET /machines?listed=true        once: every machine on CollectorCrypt's own site
  GET /machines/{code}/inventory   once per open machine: per-tier pool stats + value histogram
That is ~35 requests a run. With a key (env GAP_API_KEY, kept in GitHub's secrets,
never in this public file) the limit is 30/minute, so requests are spaced 2.2 s apart;
without a key it is 2/minute, so they are spaced 31 s apart. A 429 waits Retry-After.

Writes the same pull.json shape site2db.py has always read:
  {t, m: {code: [price, buyback, name, [tier x4: common, uncommon, rare, epic]]}}
  tier = [range_lo, range_hi, odds, cards, min, max, median, total, counts, bins]
where counts[i] cards sit in the value range bins[i] = [lo, hi]. (v1 gives one
histogram for the whole pool with per-tier counts; bins are those buckets, trimmed
to the tier's own min..max.) Money is converted from cents to dollars.
"""
import json, math, os, sys, time, urllib.request, urllib.error, datetime

BASE = os.environ.get("GAP_API_BASE", "https://api.holoscope.app/v1").rstrip("/")
KEY = os.environ.get("GAP_API_KEY", "").strip()
UA = "Epicenter cheatsheet (epicenter.saprozoic.dev) - hourly read via the v1 API"
ORDER = ["common", "uncommon", "rare", "epic"]
SPACING = 2.2 if KEY else 31.0


def get(path, tries=4):
    global KEY, SPACING
    for attempt in range(1, tries + 1):
        headers = {"User-Agent": UA, "Accept": "application/json"}
        if KEY:
            headers["X-API-Key"] = KEY
        try:
            req = urllib.request.Request(BASE + path, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < tries:
                wait = int(e.headers.get("Retry-After") or 30) + 1
                print(f"  rate limited, waiting {wait}s", flush=True)
                time.sleep(wait)
                continue
            body = e.read().decode("utf-8", "replace")[:200]
            if e.code == 403 and KEY and "key_pending" in body:
                # New keys are approved by hand (usually within a day); until then
                # the key is refused, so carry on without it at the keyless pace.
                print("  key not approved yet - continuing without it (slower)", flush=True)
                KEY, SPACING = "", 31.0
                time.sleep(SPACING)
                continue
            if e.code in (401, 402, 410) or attempt == tries:
                raise RuntimeError(f"{path}: HTTP {e.code} {body}")
            time.sleep(5 * attempt)
        except Exception as e:
            if attempt == tries:
                raise RuntimeError(f"{path}: {e}")
            time.sleep(5 * attempt)


def r2(x):  # same rounding as JS Math.round(x*100)/100
    return math.floor(x * 100 + 0.5) / 100


def dollars(c):
    return None if c is None else c / 100


def tier_entry(code, mach_tier, inv_tier, buckets):
    """One tier in the pull.json shape (see the header)."""
    if not inv_tier or not inv_tier.get("cards"):
        lo = dollars((mach_tier or {}).get("minCents")); hi = dollars((mach_tier or {}).get("maxCents"))
        return [lo, hi, (mach_tier or {}).get("odds"), 0]
    n = str(inv_tier["tier"])
    mn, mx = dollars(inv_tier["minCents"]), dollars(inv_tier["maxCents"])
    counts, bins = [], []
    for b in buckets:
        c = (b.get("byTier") or {}).get(n, 0)
        if not c:
            continue
        lo, hi = max(dollars(b["fromCents"]), mn), min(dollars(b["toCents"]), mx)
        if hi < lo:
            hi = lo
        counts.append(c); bins.append([lo, hi])
    lo = dollars(inv_tier.get("rangeMinCents")); hi = dollars(inv_tier.get("rangeMaxCents"))
    if hi is None:  # the top tier has no ceiling
        hi = mx
    return [lo, hi, inv_tier.get("odds"), inv_tier["cards"], mn, mx, r2(inv_tier["medianCents"] / 100),
            inv_tier["valueCents"] / 100, counts, bins]


def main(dst):
    print(f"Gap Tracker v1 at {BASE} ({'with' if KEY else 'without'} a key)", flush=True)
    machines = [m for m in get("/machines?listed=true")["machines"] if m.get("open") and m.get("listed")]
    out = {"t": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"), "m": {}}
    for m in machines:
        time.sleep(SPACING)
        code = m["code"]
        v = get(f"/machines/{code}/inventory")
        sync = v.get("sync") or {}
        if sync.get("state") not in (None, "ok") or sync.get("partial"):
            print(f"  note: {code} pool sync is {sync.get('state')} ({sync.get('message')})", flush=True)
        by_key_m = {t["key"]: t for t in m.get("tiers") or []}
        by_key_v = {t["key"]: t for t in v.get("tiers") or []}
        buckets = (v.get("histogram") or {}).get("buckets") or []
        tiers = [tier_entry(code, by_key_m.get(k), by_key_v.get(k), buckets) for k in ORDER]
        out["m"][code] = [m["priceCents"] / 100, m.get("buybackRate"), m.get("name") or code, tiers]
        print(f"  {code}", flush=True)
    if len(out["m"]) < 30:
        raise SystemExit(f"only {len(out['m'])} machines - tracker looks wrong, not publishing")
    json.dump(out, open(dst, "w"))
    print(f"pulled {len(out['m'])} machines at {out['t']}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "pull.json")
