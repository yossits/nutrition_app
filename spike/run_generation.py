# -*- coding: utf-8 -*-
"""
The real test of the product thesis.

    Mac/Linux:  ANTHROPIC_API_KEY=sk-ant-... python3 run_generation.py 30
    Windows:    set ANTHROPIC_API_KEY=sk-ant-...
                python run_generation.py 30

Three optional flags, all off by default. With none of them passed, this file
behaves exactly as it did before they existed:

    --source db      run against spike/menu_foods.py instead of the 63-item
                     seed - the same switch run_spike.py carries, through the
                     same food_source contract.
    --profile <id>   run the single profile with this id, instead of the first
                     N that survive the runnable gates.
    --show-menu      print the Hebrew menu text and the grams the solver set,
                     phrased by portions.describe() - the function show_menus.py
                     already renders with. No second API call: vf() writes the
                     solved grams back into the menu that passed validation.
                     A REJECTED menu prints too, marked as such: generate()
                     returns None on failure, so the last attempt is read back
                     out of the trace vf keeps.
    --trace          per attempt: the solver's own kcal_err and protein_err,
                     and every validator error IN FULL. The status line above
                     shows one error truncated to 44 characters; three attempts
                     that each failed differently look identical there.

The number that matters is FIRST-ATTEMPT PASS RATE:
  >= 85%   thesis holds - build with confidence
  60-85%   workable - tighten the prompt and tolerances
  <  60%   rethink the generation approach before building any UI
"""
import argparse
import os, sys, time, collections

import food_source

# The source is selected BEFORE the other modules are imported: filters.py binds
# foods.FOODS at import time, so the swap has to happen first. Same ordering as
# run_spike.py, and for the same reason. See food_source.py.
_ap = argparse.ArgumentParser(description="Generation run over N runnable profiles.")
_ap.add_argument("n", nargs="?", type=int, default=30,
                 help="how many runnable profiles to generate (default: 30)")
_ap.add_argument("--profile", type=int, default=None, metavar="ID",
                 help="run the single profile with this id instead of the first N")
_ap.add_argument("--show-menu", action="store_true",
                 help="print the Hebrew menu text and the grams the solver set")
_ap.add_argument("--trace", action="store_true",
                 help="per attempt: solver kcal_err/protein_err and all validator errors")
food_source.add_argument(_ap)
_args = _ap.parse_args()
SOURCE = food_source.activate(_args.source)

from engine import targets, split_meals, SafetyBlock                             # noqa: E402
from filters import eligible, validate, pool_health, sample_for_prompt, resolve  # noqa: E402
from portions import solve, feasible, describe                                   # noqa: E402
from generator import generate                                                   # noqa: E402
from profiles import PROFILES                                                    # noqa: E402

# Always announced, as run_spike.py does: a run says which food database it
# used. Unconditional since 03.09.2026; until then the default run stayed
# silent so its output matched the gate recorded before the flag existed.
print(f"Food source: {SOURCE}")

KEY = os.environ.get("ANTHROPIC_API_KEY")
if not KEY:
    sys.exit("Missing ANTHROPIC_API_KEY environment variable.")

N = _args.n
MEAL_NAMES = {3: ["ארוחת בוקר", "ארוחת צהריים", "ארוחת ערב"],
              4: ["ארוחת בוקר", "ארוחת צהריים", "ארוחת ביניים", "ארוחת ערב"],
              5: ["ארוחת בוקר", "ארוחת ביניים", "ארוחת צהריים",
                  "ארוחת ביניים אחה\"צ", "ארוחת ערב"]}

# --profile isolates one id. Without the flag, candidates IS PROFILES and the
# loop below is unchanged.
candidates = PROFILES
if _args.profile is not None:
    candidates = [x for x in PROFILES if x["id"] == _args.profile]
    if not candidates:
        sys.exit(f"No profile with id {_args.profile} in this profile set.")

runnable = []
for p in candidates:
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

n = min(N, len(runnable))
print(f"Runnable profiles: {len(runnable)}   |   running {n}\n")

stats = collections.Counter()
tokens = {"in": 0, "out": 0}
failures = collections.Counter()
t0 = time.time()

for i, (p, t, pool) in enumerate(runnable[:n], 1):
    names = MEAL_NAMES[p["meals"]]
    parts = split_meals(t, p["meals"])
    sub = sample_for_prompt(pool, p)

    by = {f["name"]: f for f in pool}

    # Every attempt's menu, solver info and verdict, captured as vf sees them.
    # generate() returns None on failure and the menu would otherwise be lost -
    # but vf is handed each attempt's object and already mutates it in place.
    # This is the capture show_menus.py does with its `store` dict, one entry
    # per attempt instead of one. Reporting only: nothing below changes what is
    # composed, solved or validated, and no threshold moves.
    trace = []

    def vf(menu, _p=p, _t=t, _pool=pool, _by=by, _tr=trace):
        """Model picks foods -> solver sets portions -> validator checks."""
        picks = []
        for meal in menu:
            items = []
            for it in meal.get("items", []):
                f = resolve(it.get("food"), _pool)
                if f is None:
                    _e = [f"UNKNOWN_FOOD: {it.get('food')}"]
                    _tr.append({"menu": menu, "info": None, "errs": _e})
                    return False, _e
                it["food"] = f["name"]          # normalise back to the canonical name
                items.append((f, float(it.get("grams", 100))))
            if items:
                picks.append(items)
        if not picks:
            _tr.append({"menu": menu, "info": None, "errs": ["EMPTY_MENU"]})
            return False, ["EMPTY_MENU"]
        mt = split_meals(_t, len(picks))
        solved, _ok, _info = solve(picks, mt, _t)
        for meal, sm in zip(menu, solved):
            meal["items"] = [{"food": f["name"], "grams": g} for f, g in sm]
        _verdict, _errs = validate(menu, _p, _t, _pool)
        _tr.append({"menu": menu, "info": _info, "errs": _errs})
        return _verdict, _errs

    menu, att, usage, errs = generate(p, t, parts, names, sub, KEY, vf)
    tokens["in"] += usage["input_tokens"]
    tokens["out"] += usage["output_tokens"]

    if menu:
        stats["pass"] += 1
        if att == 1:
            stats["first_try"] += 1
    else:
        stats["fail"] += 1
        for e in errs:
            failures[e.split(":")[0]] += 1

    status = f"OK on attempt {att}" if menu else f"FAIL - {errs[0][:44] if errs else ''}"
    print(f"  {i:>3}/{n}  #{p['id']:<4} {t['kcal']:>4}kcal {p['meals']}meals "
          f"{len(sub):>2}items   {status}")

    # vf() wrote the solver's grams back into `menu`, so the object that passed
    # validation is the object printed here. One API call, not two. On failure
    # generate() hands back None, so the last attempt comes out of the trace:
    # a menu that was rejected is the one worth reading, and it used to print
    # nothing at all.
    shown = menu if menu else (trace[-1]["menu"] if trace else None)
    if _args.show_menu and shown:
        if menu is None:
            print("        [REJECTED - last attempt, failed validation]")
        for meal in shown:
            print(f"        {meal.get('name', '')}")
            for it in meal.get("items", []):
                _f = by[it["food"]]
                print(f"          {_f['he']}  |  {describe(_f, it['grams'])}"
                      f"  |  {it['grams']:.1f} g")

    if _args.trace:
        print(f"        attempts that reached the validator: {len(trace)}")
        for _k, _tr in enumerate(trace, 1):
            _inf = _tr["info"]
            if _inf is None:
                print(f"        attempt {_k}: solver did not run")
            else:
                print(f"        attempt {_k}: kcal_err={_inf['kcal_err']}  "
                      f"protein_err={_inf['protein_err']}  totals={_inf['totals']}")
            for _e in (_tr["errs"] or ["(accepted - no errors)"]):
                print(f"           {_e}")

el = time.time() - t0
print(f"""
{'=' * 62}
Passed validation:     {stats['pass']}/{n}  ({stats['pass']/n*100:.0f}%)
Passed FIRST attempt:  {stats['first_try']}/{n}  ({stats['first_try']/n*100:.0f}%)   <-- THE NUMBER
Failed entirely:       {stats['fail']}/{n}

Tokens:   input {tokens['in']:,}   output {tokens['out']:,}
Per menu: {tokens['in']//n:,} in / {tokens['out']//n:,} out
Avg time: {el/n:.1f}s per menu""")

if failures:
    print("\nFailure reasons:")
    for k, v in failures.most_common():
        print(f"   {k:<22} {v}")
