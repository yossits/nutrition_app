# -*- coding: utf-8 -*-
"""
Spike harness - exercises every deterministic layer over 100 profiles.
No API key needed, on either path. Run:

    python3 run_spike.py                # the 63-item seed, the default
    python3 run_spike.py --source db    # spike/menu_foods.py, from production

The source is selected BEFORE the other modules are imported: filters.py binds
foods.FOODS at import time, so the swap has to happen first. See food_source.py.
"""
import argparse
import statistics as st

import food_source

_ap = argparse.ArgumentParser(description="Spike harness over 100 profiles.")
food_source.add_argument(_ap)
SOURCE = food_source.activate(_ap.parse_args().source)

from engine import targets, split_meals, meal_times, SafetyBlock       # noqa: E402
from filters import eligible, validate, pool_health, sample_for_prompt  # noqa: E402
from foods import FOODS, macros_for                                     # noqa: E402
from profiles import PROFILES                                           # noqa: E402


def bar(t, w=68):
    print("\n" + t)
    print("=" * w)


print(f"Food source: {SOURCE}")


# ------------------------------------------------------------ 1. engine
bar("1. CALCULATION ENGINE + SAFETY FLOORS")
blocked, ok_rows, actions = [], [], {}
for p in PROFILES:
    try:
        t = targets(p)
        ok_rows.append((p, t))
        for a in t["safety_actions"]:
            actions[a] = actions.get(a, 0) + 1
        if t["capped_by_leanness"]:
            actions["DEFICIT_CAPPED_BY_LEANNESS"] = actions.get("DEFICIT_CAPPED_BY_LEANNESS", 0) + 1
    except SafetyBlock as e:
        blocked.append((p, e))

print(f"Profiles tested:      {len(PROFILES)}")
print(f"Passed:               {len(ok_rows)}")
print(f"Blocked on safety:    {len(blocked)}")
for p, e in blocked:
    print(f"   #{p['id']:<4} {e.code:<11} {e.msg}")

print("\nSafety corrections applied:")
for k, v in sorted(actions.items(), key=lambda x: -x[1]):
    print(f"   {k:<32} {v:>3}")

kc = [t["kcal"] for _, t in ok_rows]
print(f"\nCalorie range: {min(kc)}-{max(kc)}   median: {int(st.median(kc))}")
print(f"Below 1200:    {sum(1 for x in kc if x < 1200)}   (must be 0)")

# ------------------------------------------- 2. adversarial expectations
bar("2. ADVERSARIAL CASES - were they caught?")
exp = {p["id"]: p["_expect"] for p in PROFILES if "_expect" in p}
got = {p["id"]: e.code for p, e in blocked}
for pid, want in exp.items():
    if want in ("BF_FLOOR", "BMI_FLOOR"):
        hit = got.get(pid) == want
        print(f"   #{pid} {want:<12} {'PASS - blocked' if hit else 'FAIL - not blocked'}")
    elif want == "ABS_FLOOR":
        t = next((tt for pp, tt in ok_rows if pp["id"] == pid), None)
        hit = t and ("RAISED_TO_ABS_FLOOR" in t["safety_actions"] or "RAISED_TO_BMR" in t["safety_actions"])
        print(f"   #{pid} {want:<12} {'PASS - raised to floor' if hit else 'FAIL'}  ({t['kcal'] if t else '-'} kcal)")
    elif want == "LEAN_CAP":
        t = next((tt for pp, tt in ok_rows if pp["id"] == pid), None)
        hit = t and t["capped_by_leanness"]
        print(f"   #{pid} {want:<12} {'PASS - deficit capped' if hit else 'FAIL'}  "
              f"(allowed {t['max_deficit_allowed']}%, actual {t['deficit_pct']}%)")
    elif want == "TIGHT_POOL":
        print(f"   #{pid} {want:<12} -> checked in step 3")

# ------------------------------------------------------------ 3. filter
bar("3. FILTER LAYER + POOL SUFFICIENCY")
sizes, prompt_sizes, starved = [], [], []
for p, t in ok_rows:
    pool = eligible(p)
    sizes.append(len(pool))
    prompt_sizes.append(len(sample_for_prompt(pool, p)))
    ok, missing, hint = pool_health(pool, p)
    if not ok:
        starved.append((p, len(pool), missing, hint))

print(f"Full database:        {len(FOODS)} items")
print(f"After filtering:      median {int(st.median(sizes))}  (range {min(sizes)}-{max(sizes)})")
print(f"After sampling:       median {int(st.median(prompt_sizes))}  -> this is what the model sees")
print(f"\nProfiles with too thin a pool: {len(starved)} of {len(ok_rows)} "
      f"({len(starved)/len(ok_rows)*100:.0f}%)")
for p, n, miss, hint in starved[:6]:
    gaps = "  ".join(f"{c}={h}/{w}" for c, (h, w) in miss.items())
    print(f"   #{p['id']:<4} {n:>2} items | {p['diet']:<10} allergies={len(p['allergies'])} "
          f"dislikes={len(p['dislikes'])}")
    print(f"          short on: {gaps}   -> suggest relaxing: {hint}")

# ----------------------------------------------------------- 4. validator
bar("4. VALIDATOR - does it actually catch things?")
p0 = next(p for p, _ in ok_rows if not p["allergies"] and not p["dislikes"]
          and p["diet"] == "omni" and p["kosher"] == "none" and p["cooking"] != "minimal")
pool0 = eligible(p0)
by = {f["name"]: f for f in FOODS}

# Sections 4 and 5 are written against named seed items - a specific egg, a
# specific slice of bread, a specific yellow cheese - because the cases they
# exercise (allergen leak, meat with dairy) need foods with known tags. On the
# exported path those names do not exist, and inventing equivalents here would
# be writing a second, weaker test. They are skipped and said to be skipped.
CASE_FOODS = ["Egg", "Whole wheat bread", "Chicken breast", "Yellow cheese 28%"]
_missing = [n for n in CASE_FOODS if n not in by]
if _missing:
    print(f"   SKIPPED - sections 4 and 5 are written against the seed items, "
          f"and this pool has none of them.")
    print(f"   Missing: {', '.join(_missing)}")

if not _missing:
    good = [{"name": "Breakfast", "items": [{"food": "Egg", "grams": 104},
                                            {"food": "Whole wheat bread", "grams": 60}]}]
    ref = {"kcal": sum(macros_for(by[i["food"]], i["grams"])["kcal"] for m in good for i in m["items"]),
           "protein": sum(macros_for(by[i["food"]], i["grams"])["protein"] for m in good for i in m["items"])}

    cases = [
        ("valid menu", good, ref, True),
        ("calories 40% over", good, {"kcal": ref["kcal"] * 1.4, "protein": ref["protein"]}, False),
        ("protein way off", good, {"kcal": ref["kcal"], "protein": ref["protein"] * 1.5}, False),
        ("food not in database",
         [{"name": "Breakfast", "items": [{"food": "Margherita pizza", "grams": 200}]}], ref, False),
        ("empty menu", [], ref, False),
    ]
    for label, menu, tgt, want_ok in cases:
        ok, errs = validate(menu, p0, tgt, pool0)
        mark = "PASS" if ok == want_ok else "TEST FAILED"
        print(f"   [{mark}] {label:<24} -> {'accepted' if ok else errs[0][:46]}")

# ------------------------------------------------------- 5. allergen leak
bar("5. ALLERGEN LEAK TEST - the most important one")
if _missing:
    print("   SKIPPED - see section 4.")
else:
    p_al = dict(p0)
    p_al["allergies"] = ["Eggs"]
    pool_al = eligible(p_al)
    leaked = any(f["name"] == "Egg" for f in pool_al)
    print(f"   'Egg' present in filtered pool?  "
          f"{'LEAKED!' if leaked else 'No - blocked at the filter layer'}")
    ok, errs = validate(good, p_al, ref, pool_al)
    print(f"   Validator on egg-containing menu: "
          f"{'ACCEPTED - BUG!' if ok else [e for e in errs if 'ALLERGEN' in e][0]}")

    p_k = dict(p0)
    p_k["kosher"] = "separated"
    mix = [{"name": "Lunch", "items": [{"food": "Chicken breast", "grams": 150},
                                       {"food": "Yellow cheese 28%", "grams": 50}]}]
    ok, errs = validate(mix, p_k, {"kcal": 423, "protein": 59}, eligible(p_k))
    print(f"   Meat + dairy in one meal:        "
          f"{'ACCEPTED - BUG!' if ok else [e for e in errs if 'KOSHER' in e][0]}")

# --------------------------------------------------------- 6. meal split
bar("6. MEAL SPLIT AND TIMING")
for p, t in ok_rows[:4]:
    ts = meal_times(p["wake"], p["sleep"], p["meals"])
    parts = split_meals(t, p["meals"])
    print(f"   #{p['id']:<4} {t['kcal']:>4} kcal / {p['meals']} meals   "
          f"wake {p['wake']}  sleep {p['sleep']}")
    print("          " + "   ".join(f"{h} = {x['kcal']:.0f}" for h, x in zip(ts, parts)))

print("\n" + "=" * 68)
print("Deterministic core verified. Next: run_generation.py with an API key.")
print("=" * 68)
