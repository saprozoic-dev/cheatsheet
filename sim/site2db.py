"""Build db.py straight from a Holoscope (Knut's Gap Tracker) pull.

  python3 site2db.py pull.json            -> writes db.py next to it (cwd)

Pull format (made by pull.py):
  {"t": iso_time, "m": {code: [price, buyback, name,
        [[axis_lo, axis_hi, odds, items, min, max, median, total, counts(, bins)], ... x4  C/U/R/E]]}}
counts = cards per histogram bar; bins (v1 API) = each bar's [lo, hi] value range.
Older pulls without the name field ([price, buyback, all24, tiers]) are accepted too.
"""
import json, sys, datetime
from zoneinfo import ZoneInfo

CODES = {  # site code -> (sheet name, db variable); order = board order
 'pokemon_50':('Elite $50','ELITE'), 'dragonball_50':('Dragonball $50','DB50'),
 'pokemon_25':('Starter $25','STARTER'), 'pokemon_100':('Bronze $100','BRONZE'),
 'riftbound_100':('Riftbound 100','RIFT100'), 'dragonball_100':('Dragonball $100','DB100'),
 'basketball_100':('Basketball $100','BBALL'), 'sports_100':('Sports $100','SPORTS'),
 'baseball_100':('Baseball $100','BASEBALL'), 'football_100':('Football $100','FOOTBALL'),
 'soccer_100':('Soccer $100','SOCCER100'), 'riftbound_250':('Riftbound 250','RIFT250'),
 'pokemon_250':('Pokemon $250','PKMN250'), 'ewatch_250':('Watch $250','WATCH250'),
 'pokemon_500':('Hyper $500','HYPER'), 'pokemon_2500':('Pokemon $2500','PKMN2500'),
 'ewatch_500':('Watch $500','WATCH500'), 'pokemon_1000':('Grail $1000','GRAIL'),
 'pokemon_5000':('Pokemon $5000','PKMN5000'), 'basketball_250':('Basketball $250','BBALL250'),
 'baseball_250':('Baseball $250','BASE250'), 'football_250':('Football $250','FOOT250'),
 'sports_500':('Sports $500','SPORTS500'), 'soccer_250':('Soccer $250','SOCCER250'),
 'soccer_50':('Soccer $50','SOCCER50'), 'onepiece_50':('One Piece $50','OP50'),
 'onepiece_250':('One Piece $250','OP250'), 'onepiece_1000':('One Piece $1000','OP1000'),
 'e10_10':('PSA 10 $500','PSA500'), 'dragonball_250':('Dragonball $250','DB250'),
 'riftbound_50':('Riftbound 50','RIFT50'), 'lorcana_50':('Lorcana $50','LOR50'),
 'lorcana_100':('Lorcana $100','LOR100'), 'anime_75':('Anime $75','ANIME75'),
}
TIERS = ['common', 'uncommon', 'rare', 'epic']

def label(iso):
    t = datetime.datetime.fromisoformat(iso.replace('Z', '+00:00')).astimezone(ZoneInfo('America/Los_Angeles'))
    return t.strftime('%b ') + str(t.day)

def parse(pull):
    """-> list of (code, name, var, price, bb, tiers[4]) for usable machines, plus notes."""
    out, notes = [], []
    for code, rec in pull['m'].items():
        if isinstance(rec[2], str): price, bb, sname, tiers = rec
        else: price, bb, _, tiers = rec; sname = code
        if code in CODES: name, var = CODES[code]
        else:
            name, var = sname, 'M_' + ''.join(c if c.isalnum() else '_' for c in code).upper()
            notes.append('new machine on the tracker: %s (%s) - added under its tracker name' % (sname, code))
        if any(len(t) < 9 or t[3] == 0 for t in tiers):
            notes.append('skipped %s: a tier is empty' % name); continue
        bad = [k for k, t in zip(TIERS, tiers) if sum(t[8]) != t[3]]
        if bad: notes.append('skipped %s: histogram does not add up (%s)' % (name, bad)); continue
        out.append((code, name, var, float(price), float(bb), tiers))
    missing = [CODES[c][0] for c in CODES if c not in pull['m']]
    if missing: notes.append('no longer on the tracker: ' + ', '.join(missing))
    order = list(CODES)
    out.sort(key=lambda r: order.index(r[0]) if r[0] in order else 999)
    return out, notes

def main(src, dst='db.py'):
    pull = json.load(open(src)); lab = label(pull['t'])
    rows, notes = parse(pull)
    L = ['"""Machine database built by site2db.py from a tracker pull at %s."""' % pull['t'],
         'import machine as M', 'from machine import T', 'RECON = set()', '']
    for code, name, var, price, bb, tiers in rows:
        L.append("%s = M.Machine(%r, %.1f, %.2f, None, dict(" % (var, name, price, bb))
        for k, t in zip(TIERS, tiers):
            lo, hi, odds, items, mn, mx, med, total, counts = t[:9]
            ranges = t[9] if len(t) > 9 else None
            L.append(" %-8s=T(%r,(%r, %r),%r,%r,%d,%r,%d,%r,%r,%r)," % (k, odds, lo, hi, mn, mx, round(total / items), med, items, total, counts, ranges))
        L.append('))')
    L.append('\nBOARD = [')
    for code, name, var, *_ in rows: L.append("    (%r, %s, %r)," % (name, var, lab))
    L.append(']')
    open(dst, 'w').write('\n'.join(L) + '\n')
    print('db.py: %d machines, read %s' % (len(rows), lab))
    for n in notes: print('NOTE:', n)
    json.dump(notes, open('pull_notes.json', 'w'))

if __name__ == '__main__':
    main(*sys.argv[1:])
