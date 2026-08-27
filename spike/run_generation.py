# -*- coding: utf-8 -*-
"""
The real test of the product thesis.

    Mac/Linux:  ANTHROPIC_API_KEY=sk-ant-... python3 run_generation.py 30
    Windows:    set ANTHROPIC_API_KEY=sk-ant-...
                python run_generation.py 30

The number that matters is FIRST-ATTEMPT PASS RATE:
  >= 85%   thesis holds - build with confidence
  60-85%   workable - tighten the prompt and tolerances
  <  60%   rethink the generation approach before building any UI
"""
import os, sys, time, collections
from engine import targets, split_meals, SafetyBlock
from filters import eligible, validate, pool_health, sample_for_prompt, resolve
from portions import solve, feasible
from generator import generate
from profiles import PROFILES

KEY = os.environ.get("ANTHROPIC_API_KEY")
if not KEY:
    sys.exit("Missing ANTHROPIC_API_KEY environment variable.")

N = int(sys.argv[1]) if len(sys.argv) > 1 else 30
MEAL_NAMES = {3: ["ארוחת בוקר", "ארוחת צהריים", "ארוחת ערב"],
              4: ["ארוחת בוקר", "ארוחת צהריים", "ארוחת ביניים", "ארוחת ערב"],
              5: ["ארוחת בוקר", "ארוחת ביניים", "ארוחת צהריים",
                  "ארוחת ביניים אחה\"צ", "ארוחת ערב"]}

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

    def vf(menu, _p=p, _t=t, _pool=pool, _by=by):
        """Model picks foods -> solver sets portions -> validator checks."""
        picks = []
        for meal in menu:
            items = []
            for it in meal.get("items", []):
                f = resolve(it.get("food"), _pool)
                if f is None:
                    return False, [f"UNKNOWN_FOOD: {it.get('food')}"]
                it["food"] = f["name"]          # normalise back to the canonical name
                items.append((f, float(it.get("grams", 100))))
            if items:
                picks.append(items)
        if not picks:
            return False, ["EMPTY_MENU"]
        mt = split_meals(_t, len(picks))
        solved, _ok, _info = solve(picks, mt, _t)
        for meal, sm in zip(menu, solved):
            meal["items"] = [{"food": f["name"], "grams": g} for f, g in sm]
        return validate(menu, _p, _t, _pool)

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
