"""_run_summary.py - the S1 summary of a run_generation.py output (with or without --show-menu). Read-only: no
API, no database, no network; prints summaries only.

Session 13 wrote it in its scratch as s1_summary.py (D:/workspace/_scratch/block-9g-s13/) and read the run files
of block 9g with it: the S1 lines of 9g0 and 9g1 - first attempt, validation, full failures, derived calls and
the last-attempt error Counter - are its output. It entered db/ in session 14's opening, 24.09.2026, unchanged
apart from this docstring: a run file without the script that reads it is not a measurement.

  python db/_run_summary.py db/block9g1_db_40.txt
  python db/_run_summary.py <run.out> [<run.err>] [--export <scratch>/menu_foods.py] [--predict <predict.txt>]

Nothing is imported from spike/; --export is loaded by its path. Gate at entry, on db/block9g1_db_40.txt: first
attempt 6/40 · validation 20/40 · full failures 20 · calls 95 · last-attempt Counter KCAL_OFF 15 · PROTEIN_OFF 14
· FAT_BELOW_SAFETY_FLOOR 3 · FAT_OFF 1 · UNKNOWN_FOOD 1. The profile ids it prints by name (1 · 27 · 28 · 34, and
23 · 31 with --export) are block 9g's questions, kept as they ran. The size it prints is the file on disk.

Definitions (decisions.md 21.09.2026, 4a-4e):
  full failure  status FAIL and the last error is not API_ERROR (validation or BAD_JSON)
  API_ERROR     counted separately
  calls         derived: OK on attempt k -> k; FAIL (not API_ERROR) -> MAX_ATTEMPTS = 3;
                FAIL with API_ERROR -> attempts that reached the validator + BAD_JSON attempts + 1, flagged
"""
import collections, hashlib, importlib.util, re, sys
from pathlib import Path

args = [a for a in sys.argv[1:]]
def opt(name):
    if name in args:
        i = args.index(name); v = args[i + 1]; del args[i:i + 2]; return v
exp_path, pred_path = opt('--export'), opt('--predict')
run_path = Path(args[0]); err_path = Path(args[1]) if len(args) > 1 else None

raw = run_path.read_bytes()
text = raw.replace(b'\r\n', b'\n').decode('utf-8')
L = text.split('\n')
PROFILE_RE = re.compile(r"^\s+(\d+)/(\d+)\s+#(\d+)\s+(\d+)kcal (\d)meals\s+(\d+)items\s+(.*)$")
REACHED_RE = re.compile(r"^\s+attempts that reached the validator: (\d+)$")
ATT_RE = re.compile(r"^\s+attempt (\d+): kcal_err=(\S+)\s+protein_err=(\S+)\s+totals=(\{.*\})$")
NOSOLVER_RE = re.compile(r"^\s+attempt (\d+): solver did not run$")
ERR_RE = re.compile(r"^\s{11}([A-Z_]+): (.*)$")
ACC_RE = re.compile(r"^\s{11}\(accepted - no errors\)$")
MENU_ITEM_RE = re.compile(r"^ {10}(\S.*?)  \|  (.*)  \|  ([\d.]+) g$")
REJ = "        [REJECTED - last attempt, failed validation]"
REJ_STOP = "        [REJECTED - stopped before the solver: "

prof, cur, zone = [], None, None
runnable_line = next((l for l in L if l.startswith('Runnable profiles:')), None)
for l in L:
    m = PROFILE_RE.match(l)
    if m:
        st = m.group(7)
        ok = re.match(r"OK on attempt (\d)", st)
        cur = dict(id=int(m.group(3)), kcal=int(m.group(4)), meals=int(m.group(5)), items=int(m.group(6)), status=st,
                   ok=bool(ok), att=int(ok.group(1)) if ok else None, reached=None, attempts=[], menu=[], rejected=False, rejected_stop=None,
                   menu_meals=0)
        prof.append(cur); zone = 'menu'; continue
    if cur is None: continue
    if l.startswith('=' * 20): cur = None; continue
    if l == REJ: cur['rejected'] = True; continue
    if l.startswith(REJ_STOP): cur['rejected_stop'] = l[len(REJ_STOP):].rstrip(']'); continue
    m = REACHED_RE.match(l)
    if m: cur['reached'] = int(m.group(1)); zone = 'trace'; continue
    m = ATT_RE.match(l)
    if m:
        cur['attempts'].append(dict(k=int(m.group(1)), totals=m.group(4), errs=[])); continue
    m = NOSOLVER_RE.match(l)
    if m:
        cur['attempts'].append(dict(k=int(m.group(1)), totals=None, errs=[])); continue
    m = ERR_RE.match(l)
    if m and cur['attempts']:
        cur['attempts'][-1]['errs'].append((m.group(1), m.group(2))); continue
    if ACC_RE.match(l): continue
    if zone == 'menu':
        m = MENU_ITEM_RE.match(l)
        if m: cur['menu'].append((m.group(1), float(m.group(3)))); continue
        if l.startswith(' ' * 8) and not l.startswith(' ' * 9) and l.strip(): cur['menu_meals'] += 1; continue

def last_code(p):
    s = p['status']
    if s.startswith('FAIL - '):
        return s[7:].split(':')[0]
    return None

n = len(prof)
first = sum(1 for p in prof if p['att'] == 1)
passed = sum(1 for p in prof if p['ok'])
api = [p['id'] for p in prof if last_code(p) == 'API_ERROR']
full = [p['id'] for p in prof if not p['ok'] and last_code(p) != 'API_ERROR']
calls, flagged = 0, []
for p in prof:
    if p['ok']: calls += p['att']
    elif last_code(p) == 'API_ERROR':
        calls += (p['reached'] or 0) + 1; flagged.append(p['id'])
    else: calls += 3
print(f"file: {run_path.name} {len(raw):,} bytes · {raw.count(b'\n'):,} lines · CRLF {raw.count(b'\r\n')}")
if err_path: print(f"err:  {err_path.name} {err_path.stat().st_size:,} bytes")
print(f"runnable line: {runnable_line}")
print(f"status lines {n} · ids {' '.join(str(p['id']) for p in prof)}")
if pred_path:
    pl = Path(pred_path).read_text(encoding='utf-8').replace('\r', '')
    pids = re.search(r"first \d+ ids: (.*)", pl).group(1).split()
    print(f"ids == prediction: {[str(p['id']) for p in prof] == pids}")
print(f"first attempt {first}/{n} ({first / n * 100:.1f}%) · validation {passed}/{n} · full failures (4a) {len(full)}: {' '.join(map(str, full))}")
print(f"API_ERROR {len(api)}: {api} · calls, derived, {calls}" + (f" (API_ERROR profiles counted as reached+1: {flagged})" if flagged else ''))
summ = {k: re.search(pat, text) for k, pat in dict(
    passed=r"Passed validation:\s+(\d+)/(\d+)", first=r"Passed FIRST attempt:\s+(\d+)/(\d+)", fail=r"Failed entirely:\s+(\d+)/(\d+)",
    tokens=r"Tokens:\s+input ([\d,]+)\s+output ([\d,]+)", avg=r"Avg time: ([\d.]+)s per menu").items()}
if all(summ.values()):
    print(f"summary block: passed {summ['passed'].group(1)} · first {summ['first'].group(1)} · failed {summ['fail'].group(1)} · "
          f"tokens {summ['tokens'].group(1)} / {summ['tokens'].group(2)} · avg {summ['avg'].group(1)} s/menu · "
          f"consistent with status lines: {int(summ['passed'].group(1)) == passed and int(summ['first'].group(1)) == first and int(summ['fail'].group(1)) == n - passed}")
else:
    print('summary block: MISSING', {k: bool(v) for k, v in summ.items()})
fr = re.search(r"Failure reasons:\n((?:   .*\n?)*)", text)
if fr: print('failure reasons block:', ' · '.join(' '.join(x.split()) for x in fr.group(1).strip().split('\n')))

last = collections.Counter()
for p in prof:
    if p['ok']: continue
    c = last_code(p)
    if c in ('API_ERROR', 'BAD_JSON'): last[c] += 1; continue
    if p['attempts']:
        for code, _ in p['attempts'][-1]['errs']: last[code] += 1
print('last-attempt error codes (full failures, per line):', dict(last.most_common()))
for fid in (1, 27, 28, 34):
    p = next((x for x in prof if x['id'] == fid), None)
    if p is None: print(f"  #{fid}: not in run"); continue
    lastc = [c for c, _ in p['attempts'][-1]['errs']] if p['attempts'] else []
    print(f"  #{fid}: {'OK att ' + str(p['att']) if p['ok'] else 'FAIL'} · FAT_BELOW_SAFETY_FLOOR in last attempt: {'FAT_BELOW_SAFETY_FLOOR' in lastc}")
fb = [(p['id'], sum(c == 'FAT_BELOW_SAFETY_FLOOR' for a in p['attempts'] for c, _ in a['errs'])) for p in prof]
fb = [x for x in fb if x[1]]
print(f"FAT_BELOW_SAFETY_FLOOR occurrences {sum(c for _, c in fb)} in {len(fb)} profiles: {fb}")
uk = [(p['id'], a['k']) for p in prof for a in p['attempts'] for c, _ in a['errs'] if c == 'UNKNOWN_FOOD']
print(f"UNKNOWN_FOOD {len(uk)} in {len({i for i, _ in uk})} profiles: {uk} · on a last attempt: "
      f"{[p['id'] for p in prof if p['attempts'] and any(c == 'UNKNOWN_FOOD' for c, _ in p['attempts'][-1]['errs'])]}")
same = []
for p in prof:
    a = p['attempts']
    for i in range(1, len(a)):
        if a[i]['totals'] and a[i]['totals'] == a[i - 1]['totals']: same.append((p['id'], a[i - 1]['k'], a[i]['k']))
print(f"identical totals in consecutive attempts: {len({i for i, _, _ in same})} profiles {same}")
withmenu = [p for p in prof if p['menu']]
bad = [(p['id'], p['reached'], len(p['attempts'])) for p in prof if p['reached'] is not None and p['reached'] != len(p['attempts'])]
print(f"trace check: reached == attempts parsed for every profile: {not bad} {bad if bad else ''}")
stop = [(p['id'], p['rejected_stop']) for p in prof if p['rejected_stop'] is not None]
print(f"REJECTED lines: 'last attempt, failed validation' {sum(p['rejected'] for p in prof)} · 'stopped before the solver' {len(stop)} {stop}")
print(f"menus printed: {len(withmenu)} profiles · REJECTED marked {sum(p['rejected'] for p in prof)} · "
      f"items {sum(len(p['menu']) for p in prof)} · meal-name lines {sum(p['menu_meals'] for p in prof)}")
if exp_path:
    spec = importlib.util.spec_from_file_location('export_for_s1', exp_path)
    mod = importlib.util.module_from_spec(spec); sys.dont_write_bytecode = True; spec.loader.exec_module(mod)
    by_he = {f['he']: f for f in mod.FOODS}
    unk = [(p['id'], he) for p in prof for he, _ in p['menu'] if he not in by_he]
    print(f"menu items not in the export by he-name: {len(unk)}")
    for pid in (23, 31):
        p = next((x for x in prof if x['id'] == pid), None)
        if p is None: print(f"  #{pid}: not in run"); continue
        codes = [by_he[he]['source_code'] for he, _ in p['menu'] if he in by_he]
        egg = [(c, by_he[he]['he']) for he, _ in p['menu'] if he in by_he and 'Egg' in by_he[he]['allergens'] for c in [by_he[he]['source_code']]]
        kind = 'no menu printed' if not p['menu'] else ('OK menu' if p['ok'] else 'REJECTED menu')
        print(f"  #{pid}: {kind}, {len(codes)} items · 1575 in it: {'1575' in codes} · Egg-tagged items: {egg}")
