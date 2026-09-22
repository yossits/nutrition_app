# -*- coding: utf-8 -*-
"""
_bound_landscape.py - what binds the portion solver on the real pool: per profile, the upper
bounds the effective ceilings allow against the day targets. Read-only: no API call, no database.

Opened in block 9-alef for open-questions.md #64. The fix block reruns it before and after.

  cd <scratch directory holding the export as menu_foods.py>
  PYTHONUTF8=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/d/<repo>/spike:/d/<repo>/db \\
      python -m _bound_landscape --run /d/<repo>/db/block9_db_40.txt --expect-export 2966e65c \\
      --expect-fingerprint 9ac85deaaa5fcccd --out /d/<repo>/db/block9_landscape_db_40.txt
  ... python -m _bound_landscape --source seed --expect-fingerprint 9b27d71a08ce227b

Lessons 53 and 54: under -m, sys.path[0] is the cwd, so `import menu_foods` resolves to the export
in the scratch directory and never to a stale gitignored spike/menu_foods.py; the imported path and
sha256 are printed and gated (--expect-export). PYTHONUTF8 keeps the printed bytes stable. The
PYTHONPATH above is Git Bash form: MSYS turns the ':'-list into a ';'-list for the Windows interpreter.

The replay is spike/run_generation.py --source db up to the API call, in its order:
food_source.activate (:53), targets / SafetyBlock (:87-89), eligible (:90), pool_health (:91),
feasible(sample_for_prompt(pool, p), t) (:93), n = min(40, len(runnable)) (:97), then per profile
split_meals (:107) and sample_for_prompt (:108). Gates: the fingerprint of predict.py (block 9), and
every target the run output prints equals the recomputed one.

Definitions (decided at S0 of 9-alef, 22.09.2026):
  C_f      the effective ceiling, max(portions._options(f)) (portions.py:45-58) - the largest amount
           the solver can serve a row. It can sit below max_g (the 5 g grid of by_weight) or above
           it (the half-unit fallback of portions.py:57).
  slots    every non-supp item of a pool gives min(2, meals) slots of C_f * x / 100 (SYSTEM rule 8),
           the best supp one slot (rule 9). Rules 1, 8 and 9 are prompt rules only; code enforces
           none of them, and the run output carries no menus, so obedience is not observed.
  U_inf    per macro x, the sum of all slots - no per-meal limit, which is what the prompt says.
  U_2      the same with at most 2 * meals slots per family - a conditional bound, not a bound on
           what the prompt permits.
  joint    most kcal with protein <= (1 + TOL_PROTEIN) * P and fat >= the fat floor, grams anywhere
           in [0, C_f] per slot (a continuous relaxation: the solver snaps to options). Solved as an
           LP by a dense two-phase simplex; its value is checked against the Lagrangian bound at the
           LP's own multipliers. U_2: the LP with the cardinality relaxed to sum(x) <= 2 * meals per
           family is an upper bound; the LP restricted to the top 2 * meals slots per family of that
           solution is a feasible point.
  tiers    T1: 0.95 * K above joint on U_inf (or infeasible) - unreachable on the 24 in principle.
           T2: inside joint U_inf, above the U_2 bound - needs more than two items per family per meal
               (or one item in every meal; rule 8 is not enforced).
           T3: the U_2 feasible point reaches 0.95 * K - reachable in the continuous relaxation only:
               grams anywhere in [0, C_f], no snapping to options, no KOSHER_MIX. "T2/T3?": between
               the U_2 point and bound. A "no" is robust (an infeasible relaxation is infeasible); a
               T3 or a window "yes" is not a proof on the options grid. The joint line tests the kcal
               floor under the protein cap only; the window line tests every band.
  mirror   for the fat-floor set: most fat with kcal <= (1 + TOL_KCAL) * K and protein >=
           (1 - TOL_PROTEIN) * P, same slots.
  window   is any menu inside every band validate() checks - kcal +/-5%, protein +/-7%, fat >= the
           floor and fat +/-35% - on the 24, same slots and relaxation (U_inf exact; U_2 relaxed, then
           a feasible point (continuous) on the top 2 * meals slots per family).
  fat/meal the fat of the 24's fat-family items at ceiling in one meal: all of them (U_inf), the top
           two (U_2). Neither solve() nor validate() reads per-meal targets.
  binding  for a profile outside a joint bound: the family whose share of the single-macro kcal bound,
           divided by its macro's share of the kcal target (protein 4P/K, carb 4C/K, fat 9F/K), is
           smallest. Veg carries no macro share and is not a solver lever.
"""

import argparse
import collections
import difflib
import hashlib
import re
import statistics
import sys
from pathlib import Path

sys.dont_write_bytecode = True

AP = argparse.ArgumentParser(description="Upper bounds under the effective ceilings, per profile (#64).")
AP.add_argument("--source", choices=("db", "seed"), default="db")
AP.add_argument("--run", type=Path, help="the run output, db/block9_db_40.txt")
AP.add_argument("--expect-export", help="sha256 prefix the imported menu_foods must carry (db source)")
AP.add_argument("--expect-fingerprint", help="predict.py fingerprint of the first 40 runnable profiles")
AP.add_argument("--out", type=Path, help="write the landscape table here (LF, UTF-8)")
ARGS = AP.parse_args()
if ARGS.source == "db" and not (ARGS.run and ARGS.expect_export and ARGS.expect_fingerprint):
    AP.error("--source db needs --run, --expect-export and --expect-fingerprint (lesson 53: a stale "
             "spike/menu_foods.py imports silently when the cwd or the invocation is wrong)")

import food_source  # noqa: E402

SOURCE = food_source.activate(ARGS.source)

import foods  # noqa: E402
from engine import targets, split_meals, SafetyBlock  # noqa: E402
from filters import (eligible, pool_health, sample_for_prompt, FAT_FLOOR_PER_KG,  # noqa: E402
                     TOL_KCAL, TOL_PROTEIN, TOL_FAT)
from portions import feasible, _options  # noqa: E402
from profiles import PROFILES  # noqa: E402

FAMILIES = ("protein", "carb", "veg", "fat")
MACROS = ("kcal", "protein", "fat")
N_PROFILES = 40
EPS = 1e-9
ALLERGEN_ALIAS = {"Eggs": "Egg"}   # the one name the seed vocabulary and the export spell differently


# ---------------------------------------------------------------- replay

def replay(n_wanted=N_PROFILES):
    """run_generation.py:86-97 and :107-108, in the same order."""
    runnable = []
    for p in PROFILES:
        try:
            t = targets(p)
        except SafetyBlock:
            continue
        pool = eligible(p)
        if not pool_health(pool, p)[0]:
            continue
        if not feasible(sample_for_prompt(pool, p), t)[0]:
            continue
        runnable.append((p, t, pool))
    n = min(n_wanted, len(runnable))
    rows, fp = [], hashlib.sha256()
    for p, t, pool in runnable[:n]:
        parts = split_meals(t, p["meals"])
        sub = sample_for_prompt(pool, p)
        fp.update(repr((p["id"], t["kcal"], p["meals"], [f["name"] for f in sub])).encode("utf-8"))
        rows.append(dict(p=p, t=t, pool=pool, parts=parts, sub=sub))
    return len(runnable), rows, fp.hexdigest()[:16]


# ---------------------------------------------------------------- run output

PROFILE_RE = re.compile(r"^\s+(\d+)/(\d+)\s+#(\d+)\s+(\d+)kcal (\d)meals\s+(\d+)items\s+(.*)$")
REACHED_RE = re.compile(r"^\s+attempts that reached the validator: (\d+)$")
ATT_RE = re.compile(r"^\s+attempt (\d+): kcal_err=(\S+)\s+protein_err=(\S+)\s+totals=(\{.*\})$")
NOSOLVER_RE = re.compile(r"^\s+attempt (\d+): solver did not run$")
ERR_RE = re.compile(r"^\s{11}([A-Z_]+): (.*)$")
TOTALS_RE = re.compile(r"'(kcal|protein|fat|carb)': (-?\d+)")


def parse_run(path):
    lines = path.read_bytes().replace(b"\r\n", b"\n").decode("utf-8").split("\n")
    out, cur, att = [], None, None
    for line in lines:
        m = PROFILE_RE.match(line)
        if m:
            ok = re.match(r"OK on attempt (\d)", m.group(7))
            cur = dict(i=int(m.group(1)), n=int(m.group(2)), id=int(m.group(3)), kcal=int(m.group(4)),
                       meals=int(m.group(5)), items=int(m.group(6)), status=m.group(7),
                       outcome=("first" if ok and ok.group(1) == "1" else "retry" if ok else "fail"),
                       reached=None, attempts=[])
            out.append(cur)
            att = None
            continue
        if cur is None:
            continue
        m = REACHED_RE.match(line)
        if m:
            cur["reached"] = int(m.group(1))
            continue
        m = ATT_RE.match(line)
        if m:
            att = dict(k=int(m.group(1)), totals={k: int(v) for k, v in TOTALS_RE.findall(m.group(4))}, errs=[])
            cur["attempts"].append(att)
            continue
        m = NOSOLVER_RE.match(line)
        if m:
            att = dict(k=int(m.group(1)), totals=None, errs=[])
            cur["attempts"].append(att)
            continue
        m = ERR_RE.match(line)
        if m and att is not None:
            att["errs"].append((m.group(1), m.group(2)))
    return out


def target_mismatches(rows, run):
    checked, bad = 0, []
    by_id = {o["id"]: o for o in run}
    for r in rows:
        p, t = r["p"], r["t"]
        o = by_id.get(p["id"])
        if o is None:
            bad.append((p["id"], "missing"))
            continue
        floor = p.get("weight", 0) * FAT_FLOOR_PER_KG
        for label, got, want in (("kcal", o["kcal"], t["kcal"]), ("meals", o["meals"], p["meals"]),
                                 ("items", o["items"], len(r["sub"]))):
            checked += 1
            if got != want:
                bad.append((p["id"], label, got, want))
        for a in o["attempts"]:
            for code, text in a["errs"]:
                pat = {"KCAL_OFF": (r" vs (\d+) \(", t["kcal"]),
                       "PROTEIN_OFF": (r" vs (\d+) \(", t["protein"]),
                       "FAT_OFF": (r" vs (\d+) \(", t["fat"]),
                       "FAT_BELOW_SAFETY_FLOOR": (r" vs (\d+)g minimum", f"{floor:.0f}")}.get(code)
                if not pat:
                    continue
                m = re.search(pat[0], text)
                checked += 1
                if not m or m.group(1) != str(pat[1]):
                    bad.append((p["id"], code, m.group(1) if m else None, pat[1]))
    return checked, bad


# ---------------------------------------------------------------- ceilings, slots, single-macro bounds

def ceiling(f):
    return max(_options(f))


def at_ceiling(f, macro):
    return ceiling(f) * f[macro] / 100.0


def slots_of(items, meals):
    """[(family, kcal, protein, fat, code, supp)] - min(2, meals) per non-supp item, one per supp item.
    At most one supp slot may be used in a day (rule 9): single_bounds keeps the best supp slot per
    macro, joint() and mirror() add the row sum(supp x) <= 1 when the pool holds more than one."""
    out, reps = [], min(2, meals)
    for f in items:
        n = 1 if f.get("supp") else reps
        out += [(f["cat"], at_ceiling(f, "kcal"), at_ceiling(f, "protein"), at_ceiling(f, "fat"),
                 f.get("source_code", f["name"]), bool(f.get("supp")))] * n
    return out


def single_bounds(items, meals, keep=None):
    """{macro: (total, {family: part})}; keep = slots per family (None = U_inf)."""
    sl = slots_of(items, meals)
    out = {}
    for mi, macro in enumerate(MACROS, 1):
        parts = {}
        for c in FAMILIES:
            whole = [s[mi] for s in sl if s[0] == c and not s[5]]
            supp = sorted((s[mi] for s in sl if s[0] == c and s[5]), reverse=True)[:1]
            v = sorted(whole + supp, reverse=True)
            parts[c] = sum(v if keep is None else v[:keep])
        out[macro] = (sum(parts.values()), parts)
    return out


def supp_row(sl):
    """The rule-9 row, needed only when the pool holds more than one supp slot."""
    idx = [i for i, s in enumerate(sl) if s[5]]
    return [([1.0 if s[5] else 0.0 for s in sl], 1.0)] if len(idx) > 1 else []


# ---------------------------------------------------------------- a small LP

def lp_max(c, le, ge, n):
    """
    max c.x  s.t.  a.x <= b (le, b >= 0),  a.x >= b (ge, b >= 0),  0 <= x <= 1.
    Dense two-phase tableau simplex, Bland's rule. Returns None when infeasible, else
    (x, objective, duals) with one dual per le row then per ge row (ge duals are <= 0).
    """
    rows = [(a, b, "le") for a, b in le] + \
           [([1.0 if k == j else 0.0 for k in range(n)], 1.0, "le") for j in range(n)] + \
           [(a, b, "ge") for a, b in ge]
    m = len(rows)
    n_le = sum(1 for r in rows if r[2] == "le")
    n_ge = m - n_le
    ncol = n + n_le + 2 * n_ge
    T = [[0.0] * (ncol + 1) for _ in range(m)]
    basis, unit_col, art = [0] * m, [0] * m, set()
    si, gi, ai = n, n + n_le, n + n_le + n_ge
    for i, (a, b, kind) in enumerate(rows):
        T[i][:n] = [float(v) for v in a]
        T[i][ncol] = float(b)
        if kind == "le":
            T[i][si] = 1.0
            basis[i] = unit_col[i] = si
            si += 1
        else:
            T[i][gi] = -1.0
            gi += 1
            T[i][ai] = 1.0
            basis[i] = unit_col[i] = ai
            art.add(ai)
            ai += 1

    def pivot(r, col):
        pv = T[r][col]
        T[r] = [v / pv for v in T[r]]
        for i in range(m):
            if i != r and abs(T[i][col]) > EPS:
                f = T[i][col]
                Ti, Tr = T[i], T[r]
                T[i] = [Ti[j] - f * Tr[j] for j in range(ncol + 1)]
        basis[r] = col

    def run(cost, allowed):
        for _ in range(5000):
            cb = [cost[basis[i]] for i in range(m)]
            inb = set(basis)
            enter = None
            for j in range(ncol):
                if j in inb or not allowed(j):
                    continue
                if cost[j] - sum(cb[i] * T[i][j] for i in range(m)) > EPS:
                    enter = j
                    break
            if enter is None:
                return
            best = None
            for i in range(m):
                if T[i][enter] > EPS:
                    ratio = T[i][ncol] / T[i][enter]
                    if best is None or ratio < best[0] - EPS or (abs(ratio - best[0]) <= EPS and basis[i] < basis[best[1]]):
                        best = (ratio, i)
            if best is None:
                raise RuntimeError("unbounded LP - cannot happen with 0 <= x <= 1")
            pivot(best[1], enter)
        raise RuntimeError("simplex did not converge")

    if art:
        cost1 = [-1.0 if j in art else 0.0 for j in range(ncol)]
        run(cost1, lambda j: True)
        if sum(T[i][ncol] for i in range(m) if basis[i] in art) > 1e-7:
            return None
        for i in range(m):
            if basis[i] in art:
                for j in range(ncol):
                    if j not in art and abs(T[i][j]) > 1e-7:
                        pivot(i, j)
                        break
    cost2 = [float(c[j]) if j < n else 0.0 for j in range(ncol)]
    run(cost2, lambda j: j not in art)
    x = [0.0] * n
    for i in range(m):
        if basis[i] < n:
            x[basis[i]] = T[i][ncol]
    cb = [cost2[basis[i]] for i in range(m)]
    duals = [sum(cb[k] * T[k][unit_col[i]] for k in range(m)) for i in range(m)]
    keep = list(range(len(le))) + list(range(m - n_ge, m))
    return x, sum(c[j] * x[j] for j in range(n)), [duals[i] for i in keep]


def joint(items, meals, pmax, fmin, keep=None):
    """
    Most kcal with protein <= pmax and fat >= fmin. keep=None: exact LP on all slots (U_inf).
    keep=k: (bound, point) - the LP with sum(x) <= k per family (a relaxation of 'at most k slots'),
    and the LP on the top k slots per family of that solution (a feasible point of the true U_2).
    Returns dict(bound, point, lagrange, protein, fat, feasible).
    """
    sl = slots_of(items, meals)
    n = len(sl)
    kc = [s[1] for s in sl]
    pr = [s[2] for s in sl]
    ft = [s[3] for s in sl]
    le = [(pr, pmax)] + supp_row(sl)
    if keep is not None:
        le += [([1.0 if s[0] == c else 0.0 for s in sl], float(keep)) for c in FAMILIES]
    res = lp_max(kc, le, [(ft, fmin)], n)
    if res is None:
        return dict(bound=None, point=None, lagrange=None, feasible=False, protein=None, fat=None)
    x, obj, duals = res
    if supp_row(sl):
        raise RuntimeError("more than one supp in a joint pool - the Lagrangian check does not model rule 9")
    assert all(-1e-7 <= v <= 1 + 1e-7 for v in x), "x outside [0, 1]"
    assert sum(pr[i] * x[i] for i in range(n)) <= pmax + 1e-6, "protein cap violated"
    assert sum(ft[i] * x[i] for i in range(n)) >= fmin - 1e-6, "fat floor violated"
    lam, mu = max(duals[0], 0.0), max(-duals[-1], 0.0)
    # Lagrangian bound at the LP's own multipliers, over the integral polytope 0<=x<=1, sum per family <= keep
    lag = lam * pmax - mu * fmin
    for c in FAMILIES:
        v = sorted((kc[i] - lam * pr[i] + mu * ft[i] for i in range(n) if sl[i][0] == c), reverse=True)
        v = v if keep is None else v[:keep]
        lag += sum(u for u in v if u > 0)
    if keep is None:
        return dict(bound=obj, point=obj, lagrange=lag, feasible=True, lam=lam, mu=mu,
                    protein=sum(pr[i] * x[i] for i in range(n)), fat=sum(ft[i] * x[i] for i in range(n)))
    chosen = []
    for c in FAMILIES:
        idx = [i for i in range(n) if sl[i][0] == c]
        idx.sort(key=lambda i: (-x[i], -(kc[i] - lam * pr[i] + mu * ft[i])))
        chosen += idx[:keep]
    if sum(1 for i in chosen if sl[i][5]) > 1:
        raise RuntimeError("restricted U_2 set holds more than one supp slot")
    sub = lp_max([kc[i] for i in chosen], [([pr[i] for i in chosen], pmax)],
                 [([ft[i] for i in chosen], fmin)], len(chosen))
    if sub is not None:
        xs = sub[0]
        assert sum(pr[chosen[j]] * xs[j] for j in range(len(chosen))) <= pmax + 1e-6
        assert sum(ft[chosen[j]] * xs[j] for j in range(len(chosen))) >= fmin - 1e-6
    point = None if sub is None else sub[1]
    return dict(bound=obj, point=point, lagrange=lag, feasible=True, lam=lam, mu=mu,
                protein=None if sub is None else sum(pr[chosen[j]] * sub[0][j] for j in range(len(chosen))),
                fat=None if sub is None else sum(ft[chosen[j]] * sub[0][j] for j in range(len(chosen))))


def mirror(items, meals, kmax, pmin, keep=None):
    """Most fat with kcal <= kmax and protein >= pmin; same structure as joint()."""
    sl = slots_of(items, meals)
    n = len(sl)
    kc = [s[1] for s in sl]
    pr = [s[2] for s in sl]
    ft = [s[3] for s in sl]
    le = [(kc, kmax)] + supp_row(sl)
    if keep is not None:
        le += [([1.0 if s[0] == c else 0.0 for s in sl], float(keep)) for c in FAMILIES]
    res = lp_max(ft, le, [(pr, pmin)], n)
    if res is None:
        return dict(bound=None, point=None)
    x, obj, _ = res
    assert sum(kc[i] * x[i] for i in range(n)) <= kmax + 1e-6 and sum(pr[i] * x[i] for i in range(n)) >= pmin - 1e-6
    if keep is None:
        return dict(bound=obj, point=obj)
    chosen = []
    for c in FAMILIES:
        idx = sorted((i for i in range(n) if sl[i][0] == c), key=lambda i: -x[i])
        chosen += idx[:keep]
    if sum(1 for i in chosen if sl[i][5]) > 1:
        raise RuntimeError("restricted U_2 set holds more than one supp slot")
    sub = lp_max([ft[i] for i in chosen], [([kc[i] for i in chosen], kmax)], [([pr[i] for i in chosen], pmin)], len(chosen))
    return dict(bound=obj, point=None if sub is None else sub[1])


def window(items, meals, t, floor, keep=None):
    """Is there a menu inside every band validate() checks? None = infeasible, else the kcal it carries."""
    sl = slots_of(items, meals)
    n = len(sl)
    kc = [s[1] for s in sl]
    pr = [s[2] for s in sl]
    ft = [s[3] for s in sl]
    le = [(kc, (1 + TOL_KCAL) * t["kcal"]), (pr, (1 + TOL_PROTEIN) * t["protein"]),
          (ft, (1 + TOL_FAT) * t["fat"])] + supp_row(sl)
    ge = [(kc, (1 - TOL_KCAL) * t["kcal"]), (pr, (1 - TOL_PROTEIN) * t["protein"]),
          (ft, max(floor, (1 - TOL_FAT) * t["fat"]))]
    if keep is not None:
        le += [([1.0 if s[0] == c else 0.0 for s in sl], float(keep)) for c in FAMILIES]
    res = lp_max(kc, le, ge, n)
    if res is None or keep is None:
        return dict(relaxed=None if res is None else res[1], proven=None if res is None else res[1])
    x = res[0]
    chosen = []
    for c in FAMILIES:
        chosen += sorted((i for i in range(n) if sl[i][0] == c), key=lambda i: -x[i])[:keep]
    if sum(1 for i in chosen if sl[i][5]) > 1:
        raise RuntimeError("restricted U_2 set holds more than one supp slot")
    sub = lp_max([kc[i] for i in chosen], [([row[0][i] for i in chosen], row[1]) for row in le[:3]],
                 [([row[0][i] for i in chosen], row[1]) for row in ge], len(chosen))
    return dict(relaxed=res[1], proven=None if sub is None else sub[1])


# ---------------------------------------------------------------- per profile

def fat_per_meal(items):
    v = sorted((at_ceiling(f, "fat") for f in items if f["cat"] == "fat"), reverse=True)
    return sum(v), sum(v[:2])


def tier(t, j_inf, j_2):
    low = (1 - TOL_KCAL) * t["kcal"]
    if not j_inf["feasible"] or j_inf["bound"] < low - 1e-6:
        return "T1"
    if j_2["bound"] is None or j_2["bound"] < low - 1e-6:
        return "T2"
    if j_2["point"] is not None and j_2["point"] >= low - 1e-6:
        return "T3"
    return "T2/T3?"


def binding_family(t, items, meals, keep):
    total, parts = single_bounds(items, meals, keep)["kcal"]
    share = {"protein": 4 * t["protein"] / t["kcal"], "carb": 4 * t["carb"] / t["kcal"], "fat": 9 * t["fat"] / t["kcal"]}
    ratio = {c: (parts[c] / total) / share[c] for c in share if share[c] > 0}
    return min(ratio, key=ratio.get), ratio


def analyse(r, o, vocab_missing):
    p, t, sub, pool = r["p"], r["t"], r["sub"], r["pool"]
    m = p["meals"]
    k2 = 2 * m
    floor = p.get("weight", 0) * FAT_FLOOR_PER_KG
    pmax = (1 + TOL_PROTEIN) * t["protein"]
    a = dict(id=p["id"], meals=m, t=t, floor=floor, n_pool=len(pool), n_sub=len(sub),
             share=4 * t["protein"] / t["kcal"], outcome=o["outcome"], reached=o["reached"])
    a["ub"] = {(w, lab): single_bounds(items, m, keep)
               for w, items in (("24", sub), ("elig", pool)) for lab, keep in (("inf", None), ("2", k2))}
    a["j_inf"] = joint(sub, m, pmax, floor)
    a["j_2"] = joint(sub, m, pmax, floor, keep=k2)
    a["tier"] = tier(t, a["j_inf"], a["j_2"])
    a["win_inf"] = window(sub, m, t, floor)
    a["win_2"] = window(sub, m, t, floor, keep=k2)
    a["fatmeal"] = fat_per_meal(sub)
    solved = [x for x in o["attempts"] if x["totals"]]
    a["last"] = solved[-1]["totals"] if solved else None
    a["last_errs"] = [c for c, _ in o["attempts"][-1]["errs"]] if o["attempts"] else []
    a["all_errs"] = [[c for c, _ in x["errs"]] for x in o["attempts"]]
    a["attempts"] = o["attempts"]
    unmatched = sorted(set(p.get("allergies", [])) & vocab_missing)
    a["flag"] = ""
    if unmatched:
        hit = [f for f in sub if any(ALLERGEN_ALIAS.get(al, al) in f["allergens"] for al in unmatched)]
        a["flag"] = f"allergy {'/'.join(unmatched)} unmatched in the export; in the 24: " + \
                    (" ".join(str(f["source_code"]) for f in hit) or "none")
        a["sub_clean"] = [f for f in sub if f not in hit]
    return a


# ---------------------------------------------------------------- output helpers

def f0(v):
    return "-" if v is None else f"{v:.0f}"


def f1(v):
    return "-" if v is None else f"{v:.1f}"


def kpf(b):
    return " · ".join(f0(b[mac][0]) for mac in MACROS)


def landscape(rows):
    head = ["id", "meals", "kcal", "protein", "fat", "carb", "fat floor", "protein share", "eligible", "sampled",
            "U_inf eligible kcal · P · F", "U_inf 24", "U_2 eligible", "U_2 24",
            "joint U_inf 24", "joint U_2 24 bound · point", "tier", "window (continuous) U_inf · U_2",
            "fat/meal U_inf · U_2",
            "last solved attempt kcal · P · F · C", "outcome", "reached validator", "errors per attempt", "flag"]
    out = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for a in rows:
        t = a["t"]
        errs = " / ".join(",".join(e) or "ok" for e in a["all_errs"]) or "-"
        last = a["last"]
        cells = [a["id"], a["meals"], t["kcal"], t["protein"], t["fat"], t["carb"], f1(a["floor"]),
                 f"{a['share'] * 100:.1f}%", a["n_pool"], a["n_sub"],
                 kpf(a["ub"][("elig", "inf")]), kpf(a["ub"][("24", "inf")]),
                 kpf(a["ub"][("elig", "2")]), kpf(a["ub"][("24", "2")]),
                 f1(a["j_inf"]["bound"]) if a["j_inf"]["feasible"] else "infeasible",
                 (f"{f1(a['j_2']['bound'])} · {f1(a['j_2']['point'])}") if a["j_2"]["feasible"] else "infeasible",
                 a["tier"],
                 ("yes" if a["win_inf"]["proven"] is not None else "no") + " · " +
                 ("yes" if a["win_2"]["proven"] is not None else
                  "relaxed only" if a["win_2"]["relaxed"] is not None else "no"),
                 f"{a['fatmeal'][0]:.1f} · {a['fatmeal'][1]:.1f}",
                 " · ".join(str(last[k]) for k in ("kcal", "protein", "fat", "carb")) if last else "-",
                 a["outcome"], a["reached"], errs, a["flag"] or "-"]
        out.append("| " + " | ".join(str(c) for c in cells) + " |")
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- main

def family_sets(rows, cat):
    sets = collections.Counter(tuple(f["source_code"] if "source_code" in f else f["name"]
                                     for f in r["sub"] if f["cat"] == cat) for r in rows)
    return sets


def print_sets(rows, cat):
    by_code = {(f.get("source_code") or f["name"]): f for r in rows for f in r["sub"]}
    sets = family_sets(rows, cat)
    sizes = sorted({len(r["sub"]) for r in rows})
    print(f"{cat} sets in the sample ({'/'.join(map(str, sizes))} items) over the {len(rows)} profiles: "
          f"{len(sets)} distinct · {len({c for st in sets for c in st})} distinct items · profiles per set "
          f"{' / '.join(str(n) for _, n in sets.most_common())}")
    for n_set, (codes, count) in enumerate(sets.most_common(), 1):
        print(f"  {cat} set {n_set} - {count} profiles:")
        for code in codes:
            f = by_code[code]
            label = f"{code} · {f['name']}" if f.get("source_code") else f["name"]
            print(f"    {label} · C {ceiling(f):g} g · at ceiling kcal {at_ceiling(f, 'kcal'):.0f} · "
                  f"protein {at_ceiling(f, 'protein'):.1f} · fat {at_ceiling(f, 'fat'):.1f}")


def main_seed():
    n_runnable, rows, fp = replay()
    print(f"source: {SOURCE}")
    print(f"runnable {n_runnable} · first {len(rows)} ids: {' '.join(str(r['p']['id']) for r in rows)}")
    print(f"fingerprint {fp}")
    if ARGS.expect_fingerprint and fp != ARGS.expect_fingerprint:
        sys.exit(f"fingerprint {fp} != expected {ARGS.expect_fingerprint}")
    for cat in ("fat", "carb"):
        print_sets(rows, cat)


def main_db():
    import menu_foods
    path = Path(menu_foods.__file__).resolve()
    raw = path.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    print(f"source: {SOURCE}")
    print(f"menu_foods imported from: {path} · {len(raw)} bytes · sha256 {sha}")
    if ARGS.expect_export and not sha.startswith(ARGS.expect_export):
        sys.exit(f"imported export sha256 {sha[:8]} != expected {ARGS.expect_export}")
    other = sorted({f["cat"] for f in foods.FOODS} - set(FAMILIES))
    if other:
        sys.exit(f"export categories the bounds do not sum over: {other}")

    n_runnable, rows, fp = replay()
    print(f"runnable {n_runnable} · first {len(rows)} ids: {' '.join(str(r['p']['id']) for r in rows)}")
    print(f"fingerprint {fp} · sampled sizes {sorted({len(r['sub']) for r in rows})}")
    if ARGS.expect_fingerprint and fp != ARGS.expect_fingerprint:
        sys.exit(f"fingerprint {fp} != expected {ARGS.expect_fingerprint}")
    raw_run = ARGS.run.read_bytes().replace(b"\r\n", b"\n")
    print(f"run file LF: {len(raw_run)} bytes · sha256 {hashlib.sha256(raw_run).hexdigest()[:8]}")
    run = parse_run(ARGS.run)
    if [o["id"] for o in run] != [r["p"]["id"] for r in rows]:
        sys.exit("run file ids differ from the replay")
    checked, bad = target_mismatches(rows, run)
    print(f"targets compared {checked} · mismatches {len(bad)}")
    if bad:
        sys.exit(f"target mismatches: {bad[:10]}")

    # allergen vocabulary: the names profiles draw from against the export's own
    seed_names = list(foods.ALL_ALLERGENS)
    exp_names = list(getattr(menu_foods, "ALL_ALLERGENS", []))
    exp_tags = collections.Counter(a for f in foods.FOODS for a in f["allergens"])
    missing = {a for a in seed_names if a not in exp_tags}
    print(f"allergen names profiles draw from (foods.ALL_ALLERGENS, {len(seed_names)}): {seed_names}")
    print(f"export ALL_ALLERGENS ({len(exp_names)}): {exp_names}")
    print(f"  in the profiles' list, no export row tagged with it: {sorted(missing) or 'none'}")
    print(f"  in the export's list, not in the profiles' list: {sorted(set(exp_names) - set(seed_names)) or 'none'}")
    print(f"  export tags outside the export's own list: {sorted(set(exp_tags) - set(exp_names)) or 'none'}")

    res = [analyse(r, o, missing) for r, o in zip(rows, run)]

    # the LP against its own Lagrangian bound
    worst = max(abs(a[j]["bound"] - a[j]["lagrange"]) for a in res for j in ("j_inf", "j_2") if a[j]["feasible"])
    print(f"joint LP vs its Lagrangian bound at the LP's multipliers: max |difference| {worst:.4f} kcal")

    groups = {}
    for label, sel in (("full failures", lambda a: a["outcome"] == "fail"),
                       ("passes", lambda a: a["outcome"] != "fail"),
                       ("first-attempt passes", lambda a: a["outcome"] == "first")):
        items = [a for a in res if sel(a)]
        groups[f"{len(items)} {label}"] = items
    lams = [a["j_inf"]["lam"] for a in res if a["j_inf"]["feasible"]]
    mus = [a["j_inf"]["mu"] for a in res if a["j_inf"]["feasible"]]
    pcap = [a["id"] for a in res if a["j_inf"]["feasible"] and a["j_inf"]["lam"] > 1e-9]
    fflo = [a["id"] for a in res if a["j_inf"]["feasible"] and a["j_inf"]["mu"] > 1e-9]
    print(f"joint U_inf multipliers: protein cap binding in {len(pcap)} of {len(res)} (lambda {min(lams):.1f}-"
          f"{max(lams):.1f} kcal/g) · fat floor binding in {len(fflo)}: {' '.join('#' + str(i) for i in fflo) or '-'} "
          f"(mu at most {max(mus):.2f}) · every returned x checked feasible")
    print()
    print("tiers (joint: most kcal with protein <= 1.07 P and fat >= floor, on the 24; T3 = reachable in the "
          "continuous relaxation):")
    for g, items in groups.items():
        c = collections.Counter(a["tier"] for a in items)
        print(f"  {g}: " + " · ".join(f"{k} {c.get(k, 0)}" for k in ("T1", "T2", "T2/T3?", "T3"))
              + " · T1 ids " + (" ".join(f"#{a['id']}" for a in items if a["tier"] == "T1") or "-")
              + " · T2 ids " + (" ".join(f"#{a['id']}" for a in items if a["tier"] == "T2") or "-"))
    print("single-macro: target above the bound on the 24 (U_inf | U_2), by macro:")
    for g, items in groups.items():
        parts = []
        for lab in ("inf", "2"):
            cnt = {mac: sum(1 for a in items if a["t"][mac] > a["ub"][("24", lab)][mac][0]) for mac in MACROS}
            parts.append(f"U_{lab}: " + " · ".join(f"{mac} {cnt[mac]}" for mac in MACROS))
        print(f"  {g}: " + " | ".join(parts))
    t3_nowin = [a["id"] for a in res if a["tier"] == "T3" and a["win_2"]["proven"] is None]
    feas = sum(1 for a in res if not a["j_inf"]["feasible"])
    print(f"joint infeasible (fat floor unreachable under the protein cap) on U_inf: {feas}")
    print("window - a menu inside every band validate() checks exists on the 24, continuous relaxation "
          "(U_inf | U_2 feasible point, U_2 relaxed only):")
    for g, items in groups.items():
        wi = sum(1 for a in items if a["win_inf"]["proven"] is not None)
        w2 = sum(1 for a in items if a["win_2"]["proven"] is not None)
        w2r = sum(1 for a in items if a["win_2"]["proven"] is None and a["win_2"]["relaxed"] is not None)
        no = [a["id"] for a in items if a["win_inf"]["proven"] is None]
        no2 = [a["id"] for a in items if a["win_2"]["proven"] is None]
        print(f"  {g}: U_inf {wi}/{len(items)} | U_2 {w2}/{len(items)} · relaxed only {w2r} · "
              f"no window U_inf: {' '.join('#' + str(i) for i in no) or '-'} · no U_2 point: "
              f"{' '.join('#' + str(i) for i in no2) or '-'}")

    print(f"T3 without a U_2 window (the joint line does not test that band pair): "
          f"{' '.join('#' + str(i) for i in t3_nowin) or '-'}")
    print("binding family (out-of-bound profiles):")
    out_b = [a for a in res if a["tier"] in ("T1", "T2")]
    for a in out_b:
        rr = next(r for r in rows if r["p"]["id"] == a["id"])
        fam, ratio = binding_family(a["t"], rr["sub"], a["meals"], None if a["tier"] == "T1" else 2 * a["meals"])
        a["binding"] = fam
        print(f"  #{a['id']} {a['tier']} {a['outcome']}: {fam} (ratios " +
              " · ".join(f"{c} {v:.2f}" for c, v in ratio.items()) + ")")
    print(f"  count: {dict(collections.Counter(a['binding'] for a in out_b))}")

    # the fat-floor set: full failures whose last attempt failed on the floor with kcal and protein inside
    ff = [a for a in res if a["outcome"] == "fail" and "FAT_BELOW_SAFETY_FLOOR" in a["last_errs"]
          and not {"KCAL_OFF", "PROTEIN_OFF"} & set(a["last_errs"])]
    ff_att = [(a["id"], x["k"]) for a in res for x in a["attempts"]
              if "FAT_BELOW_SAFETY_FLOOR" in [c for c, _ in x["errs"]]
              and not {"KCAL_OFF", "PROTEIN_OFF"} & {c for c, _ in x["errs"]}]
    print(f"fat-floor set (open-questions #20/#31): full failures whose last solved attempt failed on the floor with kcal and protein "
          f"inside tolerance: {len(ff)} · {' '.join('#' + str(a['id']) for a in ff) or '-'}")
    print(f"  attempts over all 40 with the floor and no KCAL/PROTEIN error: {len(ff_att)} in "
          f"{len({i for i, _ in ff_att})} profiles")
    for a in ff:
        rr = next(r for r in rows if r["p"]["id"] == a["id"])
        t = a["t"]
        kmax, pmin = (1 + TOL_KCAL) * t["kcal"], (1 - TOL_PROTEIN) * t["protein"]
        mi = mirror(rr["sub"], a["meals"], kmax, pmin)
        m2 = mirror(rr["sub"], a["meals"], kmax, pmin, keep=2 * a["meals"])
        print(f"  mirror #{a['id']}: floor {a['floor']:.1f} · last fat {a['last']['fat'] if a['last'] else '-'} · most fat with "
              f"kcal <= {kmax:.0f} and protein >= {pmin:.1f}: U_inf {f1(mi['bound'])} · U_2 bound {f1(m2['bound'])} "
              f"point {f1(m2['point'])} · floor reachable: U_inf {mi['bound'] is not None and mi['bound'] >= a['floor']} · "
              f"U_2 point {m2['point'] is not None and m2['point'] >= a['floor']} · run_generation.py:139 passes no "
              f"fat_floor to solve() (#20)")

    # consecutive identical totals
    same = []
    for a in res:
        tots = [x["totals"] for x in a["attempts"] if x["totals"]]
        pairs = [(i + 1, i + 2) for i in range(len(tots) - 1) if tots[i] == tots[i + 1]]
        if pairs:
            tt = tots[pairs[0][0] - 1]
            eq = {lab: any(abs(tt[mac] - a["ub"][("24", lab)][mac][0]) <= 1 for mac in MACROS) for lab in ("inf", "2")}
            eqj = abs(tt["kcal"] - (a["j_inf"]["bound"] or -1)) <= 1
            same.append((a["id"], a["outcome"], len(tots), tt, eq, eqj))
    print(f"consecutive attempts with identical totals: {len(same)} profiles")
    for pid, oc, n, tt, eq, eqj in same:
        print(f"  #{pid} ({oc}, {n} solved attempts): {tt['kcal']} · {tt['protein']} · {tt['fat']} · {tt['carb']} · "
              f"equals a single-macro bound on the 24: U_inf {eq['inf']} · U_2 {eq['2']} · equals joint U_inf kcal {eqj}")

    def band(a, mac, tol):
        v, t = a["last"][mac], a["t"][mac]
        return "over" if v > (1 + tol) * t else "under" if v < (1 - tol) * t else "in"
    over = [a for a in res if a["outcome"] == "fail" and a["last"]
            and "over" in (band(a, "kcal", TOL_KCAL), band(a, "protein", TOL_PROTEIN))
            and "under" not in (band(a, "kcal", TOL_KCAL), band(a, "protein", TOL_PROTEIN))]
    print(f"full failures whose last solved attempt overshot kcal or protein with neither below its band: "
          f"{' '.join('#' + str(a['id']) for a in over) or '-'}")
    for a in over:
        print(f"  #{a['id']}: target kcal {a['t']['kcal']} · protein {a['t']['protein']} · last {a['last']} · errors "
              f"{a['last_errs']} - not explained by an upper bound (U_inf on the 24: {kpf(a['ub'][('24', 'inf')])}); "
              f"no lower bound in this run")

    # UNKNOWN_FOOD
    names = [f["name"] for f in foods.FOODS]
    unk = [(a["id"], x["k"], text) for a in res for x in a["attempts"] for c, text in x["errs"] if c == "UNKNOWN_FOOD"]
    print(f"UNKNOWN_FOOD: {len(unk)} in {len({i for i, _, _ in unk})} profiles")
    for pid, k, text in unk:
        rr = next(r for r in rows if r["p"]["id"] == pid)
        best = max(names, key=lambda nm: difflib.SequenceMatcher(None, text, nm).ratio())
        ratio = difflib.SequenceMatcher(None, text, best).ratio()
        where = "in the 24" if best in {f["name"] for f in rr["sub"]} else \
            "eligible, not sampled" if best in {f["name"] for f in rr["pool"]} else "not eligible"
        in24 = max((f["name"] for f in rr["sub"]), key=lambda nm: difflib.SequenceMatcher(None, text, nm).ratio())
        r24 = difflib.SequenceMatcher(None, text, in24).ratio()
        print(f"  #{pid} attempt {k}: {text!r} -> nearest export name {best!r} (ratio {ratio:.2f}, {where}) · "
              f"nearest in its 24 {in24!r} (ratio {r24:.2f})")

    print(f"validator tolerances: kcal +/-{TOL_KCAL:.0%} (filters.py:11, checked :91) · protein +/-{TOL_PROTEIN:.0%} "
          f"(:12, checked :93) · fat +/-{TOL_FAT:.0%} (:13, checked :101) · fat floor {FAT_FLOOR_PER_KG} g/kg (:14, checked :97-98)")

    fm = [a["fatmeal"] for a in res]
    print(f"fat per meal from the fat items of the 24 (all at ceiling | top two): median {statistics.median(x for x, _ in fm):.1f} "
          f"| {statistics.median(y for _, y in fm):.1f} g · range {min(x for x, _ in fm):.1f}-{max(x for x, _ in fm):.1f} "
          f"| {min(y for _, y in fm):.1f}-{max(y for _, y in fm):.1f} · per-meal fat target median "
          f"{statistics.median(a['t']['fat'] / a['meals'] for a in res):.1f} g (not enforced per meal)")

    hi = [a for a in res if a["share"] >= 0.30]
    print(f"protein density, profiles with protein >= 30% of kcal: {len(hi)} · " + " ".join(f"#{a['id']}" for a in hi))
    for a in hi:
        rr = next(r for r in rows if r["p"]["id"] == a["id"])
        need = a["t"]["protein"] / a["t"]["kcal"] * 100
        dens = sorted(((f["protein"] / f["kcal"] * 100), f["source_code"]) for f in rr["sub"] if f["cat"] == "protein")
        a["dens"] = (need, dens)
    needs = [a["dens"][0] for a in hi]
    above = [sum(1 for d, _ in a["dens"][1] if d >= a["dens"][0]) for a in hi]
    print(f"  target density g/100 kcal: {min(needs):.1f}-{max(needs):.1f} (median {statistics.median(needs):.1f}) · "
          f"protein items in the 24 at or above the profile's target density: min {min(above)} · median "
          f"{statistics.median(above)} · max {max(above)} of "
          f"{'/'.join(str(x) for x in sorted({len(a['dens'][1]) for a in hi}))} protein items")
    dset = collections.Counter(tuple(round(d, 1) for d, _ in a["dens"][1]) for a in hi)
    for dens, cnt in dset.most_common():
        print(f"  {cnt} profiles carry protein densities {dens}")
    print("  per profile: " + " · ".join(f"#{a['id']} {a['share'] * 100:.0f}% need {a['dens'][0]:.1f} "
                                        f"{a['outcome']} {a['tier']}" for a in hi))

    # #23 and #31 without the unmatched-allergen items
    for a in res:
        if a.get("sub_clean") is not None and len(a["sub_clean"]) != a["n_sub"]:
            t, m = a["t"], a["meals"]
            pmax = (1 + TOL_PROTEIN) * t["protein"]
            ub_i = single_bounds(a["sub_clean"], m)
            ub_2 = single_bounds(a["sub_clean"], m, 2 * m)
            ji = joint(a["sub_clean"], m, pmax, a["floor"])
            j2 = joint(a["sub_clean"], m, pmax, a["floor"], keep=2 * m)
            print(f"#{a['id']} ({a['flag']}): the 24 without it, {len(a['sub_clean'])} items: U_inf {kpf(ub_i)} · U_2 {kpf(ub_2)} · "
                  f"joint U_inf {f1(ji['bound'])} · U_2 {f1(j2['bound'])} / {f1(j2['point'])} · tier {tier(t, ji, j2)} "
                  f"(with it: {a['tier']})")

    print()
    for cat in ("fat", "carb"):
        print_sets(rows, cat)
    print("code fact: sample_for_prompt sorts the protein family only; carb, veg and fat take items[:n] "
          "in export order (filters.py:149-159)")

    if ARGS.out:
        text = landscape(res)
        ARGS.out.write_bytes(text.encode("utf-8"))
        lines = text.count("\n")
        print(f"\nwrote {ARGS.out} · {len(text.encode('utf-8'))} bytes · sha256 "
              f"{hashlib.sha256(text.encode('utf-8')).hexdigest()[:8]} · {lines} lines · LF")


if __name__ == "__main__":
    main_seed() if ARGS.source == "seed" else main_db()
