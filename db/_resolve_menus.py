"""_resolve_menus.py - no network. Re-solve the 40 menus printed in a --show-menu run, without and with fat_floor,
holding the model's picks fixed.

Check first: without the floor, the re-solve must reproduce the totals the run printed for that menu (the passing
attempt, or the last attempt that reached the validator). Then: with fat_floor = weight * FAT_FLOOR_PER_KG, the new
totals and the validator's verdict.

Session 13 wrote it in its scratch as resolve_menus.py (D:/workspace/_scratch/block-9g-s13/), in 9g1's opening,
23.09.2026 16:09, before that step's S0 and its API run. It measured step (a) offline on the 9g0 menus: 40/40
reproduced without the floor, and FAT_BELOW_SAFETY_FLOOR on 7 of them -> 3 with it. At 9g1's S1, 16:50, the guard
for a profile with no printed menu (#38 in 9g1, stopped before the solver) was added. The scratch helper s1_g1.py
read its globals (runs, byid) then and re-solved the 9g1 menus with the floor itself: 38 of the 39 printed menus
reproduce, #26 off by 3 kcal and 1 g fat. This script does not print that count; its globals runs and rows hold
it. It entered db/ in session 14's opening, 24.09.2026, as it stood after 16:50, unchanged apart from this docstring.

Recipe (lessons 53 and 54), as db/_bound_landscape.py:
  cd <scratch directory holding the fresh export as menu_foods.py>
  PYTHONUTF8=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/d/<repo>/spike:/d/<repo>/db \\
      python -m _resolve_menus /d/<repo>/db/block9g0_db_40.txt
Under -m, sys.path[0] is the cwd, so food_source.activate('db') imports the scratch export. Run as a script from
db/, sys.path[0] would be db/, and a stale gitignored spike/menu_foods.py would import silently instead.

The replay needs the pool the run had. Since 24.09.2026 food_source.activate('db') maps the profile label Eggs to
Egg (#67), and the printed menus of the runs before it (9g0, 9g1) hold an egg item for #23 and #31 that the mapped
pool no longer has: KeyError. Those files replay with a copy of spike/food_source.py as it was at 27c43ec
(`git show 27c43ec:spike/food_source.py`), in a directory put first on PYTHONPATH.
"""
import ast, re, sys, collections
sys.dont_write_bytecode = True
import food_source
food_source.activate('db')
from engine import targets, split_meals
from filters import eligible, validate, FAT_FLOOR_PER_KG
from portions import solve, _options
from profiles import PROFILES

PROFILE_RE = re.compile(r"^\s+(\d+)/(\d+)\s+#(\d+)\s+(\d+)kcal (\d)meals\s+(\d+)items\s+(.*)$")
ATT_RE = re.compile(r"^\s+attempt (\d+): kcal_err=(\S+)\s+protein_err=(\S+)\s+totals=(\{.*\})$")
ITEM_RE = re.compile(r"^ {10}(\S.*?)  \|  (.*)  \|  ([\d.]+) g$")
L = open(sys.argv[1], encoding='utf-8').read().replace('\r', '').split('\n')
runs, cur, zone = [], None, None
for l in L:
    m = PROFILE_RE.match(l)
    if m:
        cur = dict(id=int(m.group(3)), status=m.group(7), meals=[], atts=[]); runs.append(cur); zone = 'menu'; continue
    if cur is None: continue
    if l.startswith('=' * 20): cur = None; continue
    if 'attempts that reached the validator' in l: zone = 'trace'; continue
    m = ATT_RE.match(l)
    if m: cur['atts'].append(ast.literal_eval(m.group(4))); continue
    if zone == 'menu':
        if l.startswith('        [REJECTED'): continue
        m = ITEM_RE.match(l)
        if m: cur['meals'][-1].append((m.group(1), float(m.group(3)))); continue
        if l.startswith(' ' * 8) and not l.startswith(' ' * 9) and l.strip(): cur['meals'].append([]); continue

byid = {p['id']: p for p in PROFILES}
out = collections.Counter(); rows = []
for r in runs:
    p = byid[r['id']]; t = targets(p); pool = eligible(p); by = {f['he']: f for f in pool}
    picks = [[(by[he], g) for he, g in meal] for meal in r['meals'] if meal]
    if not picks:
        continue   # no menu printed (stopped before the solver)
    printed = r['atts'][-1] if r['atts'] else None
    floor = p.get('weight', 0) * FAT_FLOOR_PER_KG
    res = {}
    for key, ff in (('no', None), ('floor', floor)):
        solved, ok, info = solve(picks, split_meals(t, len(picks)), t, fat_floor=ff)
        menu = [{'name': f'm{i}', 'items': [{'food': f['name'], 'grams': g} for f, g in sm]} for i, sm in enumerate(solved)]
        verdict, errs = validate(menu, p, t, pool)
        res[key] = (info['totals'], verdict, [e.split(':')[0] for e in errs])
    repro = printed == res['no'][0]
    raisable = sum(1 for meal in picks for f, _ in meal if f['cat'] == 'fat' or f['fat'] > 8)
    rows.append((r['id'], r['status'][:4], floor, repro, raisable, res['no'], res['floor']))
    out['reproduced' if repro else 'NOT reproduced'] += 1

print(f"menus {len(runs)} · re-solve without floor reproduces the printed totals: {out['reproduced']}/{len(runs)}")
chg = [x for x in rows if x[5][0] != x[6][0]]
print(f"totals changed by the floor: {len(chg)}")
for pid, st, floor, repro, rais, no, fl in rows:
    if no[0] != fl[0] or 'FAT_BELOW_SAFETY_FLOOR' in no[2]:
        print(f"  #{pid} {st} floor {floor:.1f} · raisable rows {rais} · no floor: fat {no[0]['fat']} kcal {no[0]['kcal']} P {no[0]['protein']} "
              f"{'PASS' if no[1] else 'FAIL ' + ','.join(no[2])} -> floor: fat {fl[0]['fat']} kcal {fl[0]['kcal']} P {fl[0]['protein']} "
              f"{'PASS' if fl[1] else 'FAIL ' + ','.join(fl[2])}")
pv = collections.Counter((('PASS' if x[5][1] else 'FAIL'), ('PASS' if x[6][1] else 'FAIL')) for x in rows)
print('verdict no floor -> floor, same picks:', dict(pv))
nf = [x[0] for x in rows if 'FAT_BELOW_SAFETY_FLOOR' in x[5][2]]; ff = [x[0] for x in rows if 'FAT_BELOW_SAFETY_FLOOR' in x[6][2]]
print(f"FAT_BELOW_SAFETY_FLOOR on these menus: without floor {len(nf)} {nf} · with floor {len(ff)} {ff}")
