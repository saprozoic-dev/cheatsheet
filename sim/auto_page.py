"""Fill page_template.html automatically after a scheduled run.

  python3 auto_page.py pull.json [prev_state.json]
reads sheetdata.json, epicdata.json, db.py, pull_notes.json; writes bankroll-table.html and new_state.json.
"""
import json, sys, os, datetime
from zoneinfo import ZoneInfo
import db

PT = ZoneInfo('America/Los_Angeles')
TIERS = ['common', 'uncommon', 'rare', 'epic']
BANDS = [('d', 25, 100), ('a', 150, 900), ('b', 1000, 4000), ('c', 4500, 10**9)]

def when(iso):
    t = datetime.datetime.fromisoformat(iso.replace('Z', '+00:00')).astimezone(PT)
    return t.strftime('%b ') + str(t.day) + ', ' + t.strftime('%I:%M %p').lstrip('0').lower() + ' PT'

def money(n): return '$' + format(int(round(n)), ',')
def pc(x, d=1): return ('%.' + str(d) + 'f&#37;') % x
def nb(n):
    s = n.replace('Pokemon', 'Pok&eacute;mon').replace(' + bot', '&nbsp;+&nbsp;bot')
    return s.replace(' $', '&nbsp;$').replace('Piece ', 'Piece&nbsp;').replace('Riftbound ', 'Riftbound&nbsp;').replace('PSA 10', 'PSA&nbsp;10')
def rng(a, b): return money(a) if a == b else '%s&ndash;%s' % (money(a), money(b))
def prange(lo, hi): return pc(lo, 0) if round(lo) == round(hi) else '%d&ndash;%s' % (round(lo), pc(hi, 0))

def segments(rows):
    """consecutive rows with the same best machine -> [(name, rows)]"""
    out = []
    for r in rows:
        if out and out[-1][0] == r['best']: out[-1][1].append(r)
        else: out.append((r['best'], [r]))
    return out

def seg_text(name, rs):
    ties = sum(r['tie'] for r in rs)
    tie = '' if ties == 0 else (', tie' if ties == len(rs) else ', some ties')
    return '<b>%s</b> %s (%s%s)' % (nb(name), rng(rs[0]['bank'], rs[-1]['bank']),
                                              prange(min(r['p2'] for r in rs), max(r['p2'] for r in rs)), tie)

def merge_ties(segs):
    """adjacent segments whose rows are all ties become one group: (names, rows)"""
    out = []
    for n, rs in segs:
        allt = all(r['tie'] for r in rs)
        if out and allt and out[-1][2]:
            if n not in out[-1][0]: out[-1][0].append(n)
            out[-1][1].extend(rs)
        else:
            out.append(([n], list(rs), allt))
    return out

def group_text(names, rs, allt):
    if len(names) == 1: return seg_text(names[0], rs)
    return '%s %s (%s, all ties)' % (' / '.join('<b>%s</b>' % nb(n) for n in names),
        rng(rs[0]['bank'], rs[-1]['bank']), prange(min(r['p2'] for r in rs), max(r['p2'] for r in rs)))

def zones(rows):
    Z = []
    for z, lo, hi in BANDS:
        rs = [r for r in rows if lo <= r['bank'] <= hi]
        if not rs: continue
        segs = segments(rs)
        names = []
        for n, _ in segs:
            if n not in names: names.append(n)
        pick = ' &rarr; '.join(nb(n) for n in names) if len(names) <= 3 else 'Mixed: %s &rarr; %s' % (nb(names[0]), nb(names[-1]))
        body = '<br>'.join(group_text(*g) for g in merge_ties(segs))
        top = rs[-1]['bank'] if hi < 10**9 else None
        label = ('%s &ndash; %s' % (money(rs[0]['bank']), money(rs[-1]['bank']))) if top else '%s and up' % money(rs[0]['bank'])
        Z.append(dict(z=z, rng=label, pick=pick, body=body))
    return Z

def tier_stats(x):
    return {k: [x.tiers[k]['items'], x.tiers[k]['avg']] for k in TIERS}

def open_data(pull, stamp, rows, mach, X, cc):
    """epicenter.json: the page's results as an open data file, published next to the page
    (https://epicenter.saprozoic.dev/data/epicenter.json) for anyone to build on."""
    code = lambda n: cc.get(n, n)
    def r1(v): return None if v is None else round(v, 2)
    machines = []
    for m in mach:
        machines.append(dict(
            code=code(m['n']), name=m['n'], packPriceUsd=m['cost'], buybackPct=m['bb'],
            sustainPct=r1(m['sus']), floorLossUsd=r1(m['floor']), stepUpUsd=r1(m['step']), hitSizeUsd=r1(m['hit'])))
        # Raw pool numbers (cards left, values) are Holoscope's data, so they stay out of this file.
    machines.sort(key=lambda m: -(m['sustainPct'] or 0))
    best = []
    for r in rows:
        e = dict(bankrollUsd=r['bank'],
                 best=dict(code=code(r['best']), name=r['best'], chanceToDoublePct=r['p2'], medianPacks=r['md']),
                 runnerUp=(dict(code=code(r['second']), name=r['second'], chanceToDoublePct=r['p2b']) if r['second'] != '\u2014' else None),
                 tie=r['tie'])
        if r['bank'] < 5000: e['chanceToReach5000Pct'] = r['k1']
        if r['bank'] <= 3000: e['longestSession'] = dict(code=code(r['lng']), name=r['lng'], medianPacks=r['lngmd'])
        best.append(e)
    return dict(
        schema='epicenter/1',
        generatedAt=pull['t'], generatedAtPT=stamp,
        about='Which Collector Crypt gacha machine gives a bankroll the best chance to double before it runs out, '
              'from 30,000 simulated sessions per bankroll, selling every card back instantly. Every machine loses '
              'money on average; this only ranks them against each other. Not financial advice.',
        site='https://epicenter.saprozoic.dev',
        source=dict(name='Holoscope', url='https://holoscope.app', note='Pool inventories, odds and buybacks via the Holoscope API (Knut\u2019s Gap Tracker).'),
        license='Free to use with a link to https://epicenter.saprozoic.dev and to Holoscope (https://holoscope.app) as the data source.',
        updates='Every hour at about :13 UTC. Fetch at most a few times an hour.',
        fields=dict(
            sustainPct='% of the pack price returned on average per pull, all tiers, after buyback',
            floorLossUsd='what a plain common pull costs you (pack price minus its buyback)',
            stepUpUsd='what an average uncommon gains over the pack price (negative = loses)',
            hitSizeUsd='average rare/epic payout after buyback',
            chanceToDoublePct='% of simulated sessions that reach 2x the bankroll before it can no longer buy a pack',
            medianPacks='packs a typical session lasts',
            tie='best and runner-up are within simulation noise (2 standard errors)',
            chanceToReach5000Pct='% of sessions that ever reach $5,000 (bankrolls under $5,000)',
            longestSession='the machine a bankroll lasts longest on (bankrolls up to $3,000)'),
        machines=machines, bestByBankroll=best)

def main(pull_path, prev_path=None):
    D = json.load(open('sheetdata.json')); pull = json.load(open(pull_path))
    notes = json.load(open('pull_notes.json')) if os.path.exists('pull_notes.json') else []
    prev = json.load(open(prev_path)) if prev_path and os.path.exists(prev_path) else None
    stamp = when(pull['t']); lab = db.BOARD[0][2]
    X = {n: x for n, x, _ in db.BOARD}
    M = {m['n']: m for m in D['mach']}
    rows, rowsn = D['rows'], D['rows_nobot']
    R = {}
    sus = {n: round(x.sustain() * 100, 2) for n, x in X.items()}

    # ---------- callout 1: what changed ----------
    parts = ['<div class="panel callout">',
             '  <h3>Sustain &amp; picks<small>Auto-update, %s</small></h3>' % stamp]
    nmov = nreal = nflip = 0
    if prev:
        movers = []
        for n, x in X.items():
            if n not in prev['sus']: continue
            d = sus[n] - prev['sus'][n]
            if abs(d) < 0.25: continue
            # which tier moved the most (per-pack contribution)
            best_k, best_v = None, 0
            for k in TIERS:
                pi, pa = prev['tiers'][n][k]; ni, na = x.tiers[k]['items'], x.tiers[k]['avg']
                v = abs(x.tiers[k]['odds'] * (na - pa))
                if v > best_v: best_k, best_v = k, v
            pi, pa = prev['tiers'][n][best_k]; t = x.tiers[best_k]
            movers.append((abs(d), '<li><b>%s</b> %s &rarr; %s <span>%ss %d &rarr; %d, avg %s &rarr; %s</span></li>' % (
                nb(n), pc(prev['sus'][n], 2), pc(sus[n], 2), best_k, pi, t['items'], money(pa), money(t['avg']))))
        movers.sort(reverse=True); nmov = len(movers)
        if movers:
            parts.append('  <p><b>Sustain moves</b> since %s:</p>' % prev['stamp'])
            parts.append('  <ul class="moves">' + ''.join(m[1] for m in movers[:8]) + '</ul>')
            if len(movers) > 8: parts.append('  <p>+ %d smaller moves.</p>' % (len(movers) - 8))
        else:
            parts.append('  <p><b>No sustain moves</b> over 0.25 pts since %s.</p>' % prev['stamp'])
        pb = {r[0]: r[1] for r in prev.get('rows_nobot', prev['rows'])}
        ch = [(r['bank'], pb.get(r['bank']), r['best'], r['tie']) for r in rows if pb.get(r['bank']) and pb[r['bank']] != r['best']]
        if ch:
            groups = []
            for b, o, n, t in ch:
                if groups and groups[-1][1] == o and groups[-1][2] == n: groups[-1][0].append(b); groups[-1][3].append(t)
                else: groups.append(([b], o, n, [t]))
            real = [g for g in groups if not all(g[3])]
            flips = len(groups) - len(real); nreal, nflip = len(real), flips
            if real:
                parts.append('  <p><b>Pick changes:</b></p>')
                parts.append('  <ul class="moves">' + ''.join('<li>%s: %s &rarr; <b>%s</b></li>' % (rng(g[0][0], g[0][-1]), nb(g[1]), nb(g[2])) for g in real) + '</ul>')
            else:
                parts.append('  <p><b>No real pick changes.</b></p>')
            if flips:
                parts.append('  <p>+ %d tie flip%s (top name swapped inside the noise &mdash; not a real change).</p>' % (flips, '' if flips == 1 else 's'))
        else:
            parts.append('  <p><b>No pick changes.</b></p>')
    else:
        parts.append('  <p><b>First auto-update.</b> All machines now share one read time.</p>')
    for n in notes: parts.append('  <p><b>Tracker:</b> %s.</p>' % n)
    parts.append('</div>')

    # ---------- callout 2: thin tiers behind a pick ----------
    leaders = []
    for name, rs in segments(rows):
        x = X.get(name)
        if not x: continue
        e, c = x.tiers['epic'], x.tiers['common']
        if e['items'] < 60 or c['items'] < 100:
            seconds = [r['second'] for r in rs if r['second'] != '—']
            alt = max(set(seconds), key=seconds.count) if seconds else None
            thin = ('%d epics, avg %s' % (e['items'], money(e['avg']))) if e['items'] < 60 else ('only %d commons' % c['items'])
            leaders.append('<li><b>%s</b> leads %s <span>%s.%s</span></li>' % (
                nb(name), rng(rs[0]['bank'], rs[-1]['bank']), thin, (' Sells out &rarr; next pick: %s.' % nb(alt)) if alt else ''))
    if leaders:
        parts += ['', '<div class="panel callout">',
                  '  <h3>Picks on a thin tier<small>Can shift fast &mdash; sim assumes the cards stay</small></h3>',
                  '  <ul class="moves">' + ''.join(leaders) + '</ul>', '</div>']
    R['__CALLOUTS__'] = '\n'.join(parts)
    if prev:
        bits = []
        if nmov: bits.append('%d sustain move%s' % (nmov, '' if nmov == 1 else 's'))
        if nreal: bits.append('%d pick change%s' % (nreal, '' if nreal == 1 else 's'))
        if nflip and not nreal: bits.append('tie flips only')
        R['__CHANGESUM__'] = ('%s since %s' % (', '.join(bits), prev['stamp'])) if bits else 'No real changes since %s' % prev['stamp']
        R['__CHANGESUM__'] = R['__CHANGESUM__'][0].upper() + R['__CHANGESUM__'][1:]
    else:
        R['__CHANGESUM__'] = 'First auto-update'

    # ---------- zones ----------
    zb = zones(rows)
    cuts = [b[2] for b in BANDS[:3]]
    ZN = {z['z']: z['rng'].replace('&ndash;', '-').replace(' and up', '+') for z in zb}
    R['__ZONES__'] = '\n'.join(['const ZN_LIST=%s;' % json.dumps(ZN), 'const ZCUT=%s;' % cuts,
                                'const ZONES=%s;' % json.dumps(zb)])

    # ---------- small generated lines ----------
    st = X.get('Starter $25')
    if st:
        R['__STARTERNOTE__'] = ('<p class="note"><b>Starter&nbsp;$25: leads low, then fades.</b> Commons cost just &minus;$%.2f, '
            'but hits are small (rares ~%s, epics ~%s, top %s) &mdash; can&rsquo;t move a few-hundred bankroll.</p>'
            % (M['Starter $25']['floor'], money(st.tiers['rare']['avg']), money(st.tiers['epic']['avg']), money(st.tiers['epic']['mx'])))
    else:
        R['__STARTERNOTE__'] = ''
    thin = sorted(X.items(), key=lambda kv: kv[1].tiers['epic']['items'])[:4]
    R['__THINLINE__'] = ', '.join(('%s: %d epics' if i == 0 else '%s: %d') % (nb(n), x.tiers['epic']['items'])
                                  for i, (n, x) in enumerate(thin)) + '.'
    best_names = {r['best'] for r in rows}
    bp = [n for n in ('Pokemon $2500', 'Pokemon $5000') if n in M]
    if bp:
        if not any(n in best_names for n in bp):
            R['__BIGPKMN__'] = 'Big Pok&eacute;mon packs win no row, even at $20k &mdash; commons cost ~%s per pull.' % ' / ~'.join(
                '%s (%s)' % (money(M[n]['floor']), n.split()[-1].replace('$2500', '$2,500').replace('$5000', '$5,000')) for n in bp)
        else:
            R['__BIGPKMN__'] = 'A big Pok&eacute;mon pack now wins a row &mdash; see Full table.'
    else:
        R['__BIGPKMN__'] = ''
    groups = {}
    for n, x in X.items():
        groups.setdefault('/'.join(str(round(x.tiers[k]['odds'] * 100)) for k in TIERS), []).append(n)
    main_split = max(groups, key=lambda k: len(groups[k]))
    others = '; '.join('%s on %s' % (k, ', '.join(nb(n) for n in v)) for k, v in groups.items() if k != main_split)
    bbs = {}
    for n, x in X.items(): bbs.setdefault(round(x.buyback * 100), []).append(n)
    R['__ODDSLINE__'] = '<b>Odds</b> %s%s.<br>' % (main_split, (', except ' + others) if others else '') + '<br>'.join(
        '<b>%d&#37; buyback:</b> %s' % (k, ', '.join(nb(n) for n in sorted(bbs[k]))) for k in sorted(bbs))
    R['__NMACH__'] = str(len(X))
    R['__UPDATED__'] = stamp
    R['__PULLISO__'] = pull['t']
    R['__READSLINE__'] = '<b>Source:</b> Holoscope, Knut&rsquo;s tracker (holoscope.app). Last pull %s.' % stamp
    R['__FRESH__'] = json.dumps([lab])
    E = json.load(open('epicdata.json'))
    E['m'] = {k: v for k, v in E['m'].items() if not k.endswith(' + bot')}
    mach = [{k: v for k, v in m.items() if k != 'bot'} for m in D['mach'] if not m['bot']]
    import site2db
    cc = {name: code for code, name, *_ in site2db.parse(pull)[0]}   # sheet name -> Collector Crypt machine code
    R['__D__'] = json.dumps(dict(rows=rows, mach=mach, T=D['T'], epic=E, cc=cc), separators=(',', ':'))

    h = open('page_template.html').read()
    for k, v in R.items():
        assert h.count(k) == 1, k
        h = h.replace(k, v)
    assert '__' not in h.replace('__proto__', '').replace('__gap', ''), [l for l in h.splitlines() if '__' in l][:3]
    open('bankroll-table.html', 'w').write(h)
    json.dump(open_data(pull, stamp, rows, mach, X, cc), open('epicenter.json', 'w'), indent=1, ensure_ascii=False)
    json.dump(dict(t=pull['t'], stamp=stamp, sus=sus, tiers={n: tier_stats(x) for n, x in X.items()},
                   rows=[[r['bank'], r['best'], r['p2'], r['tie']] for r in rows],
                   rows_nobot=[[r['bank'], r['best'], r['p2'], r['tie']] for r in rowsn]),
              open('new_state.json', 'w'))
    print('page ok', len(h), 'bytes;', stamp)

if __name__ == '__main__':
    main(*sys.argv[1:])
