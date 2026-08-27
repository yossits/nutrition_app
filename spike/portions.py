# -*- coding: utf-8 -*-
"""
Portion solver - fixes the calorie/protein drift the first API run exposed.

The model chooses WHICH foods go in a meal. This module decides HOW MUCH,
deterministically. Spec principle 13.4 applied properly: composition is a
judgement call, arithmetic is not.

v2 change: protein and calories are solved JOINTLY across the whole day.
Solving them sequentially per-meal made protein undershoot ~15% on
high-protein profiles because carbs had already eaten the calorie budget.
"""
from foods import macros_for

MIN_G = 10.0
CAP = {"protein": 500.0, "carb": 600.0, "fat": 150.0, "veg": 400.0,
       "fruit": 300.0, "drink": 500.0}


def _sum(pairs):
    tot = dict(kcal=0.0, protein=0.0, fat=0.0, carb=0.0)
    for f, g in pairs:
        m = macros_for(f, g)
        for k in tot:
            tot[k] += m[k]
    return tot


def _cap(food, g):
    return max(MIN_G, min(CAP.get(food["cat"], 400.0), g))


# Only clean fractions a person can actually measure: half, whole, one and a
# half, and so on. Quarters (0.75, 1.25) were removed - "1.25 tubs of cottage
# cheese" is not an instruction anyone can follow. Capped at 3x because above
# that the amount stops being realistic even as a whole number of servings.
# Discrete items move in halves and wholes only. A tub is a tub; "0.8 of a
# tub" is not something anyone measures. Weighed items (chicken, mince, fish)
# are free to land on any sensible gram amount.
UNIT_STEPS = (0.5, 1, 1.5, 2, 2.5, 3)
WEIGHT_STEP = 5.0
WEIGHT_MIN, WEIGHT_MAX = 30.0, 400.0


def _options(food):
    """Every amount of this food a person would actually serve, in grams."""
    if food.get("by_weight"):
        hi = int(food.get("max_g") or WEIGHT_MAX)
        return [float(g) for g in range(int(WEIGHT_MIN), hi + 1, int(WEIGHT_STEP))]
    u = food.get("unit")
    if not u:
        return [float(g) for g in range(10, 401, 10)]
    steps = (1, 2, 3) if food.get("whole_only") else UNIT_STEPS
    opts = [round(u["grams"] * s, 1) for s in steps]
    cap = food.get("max_g")
    if cap:
        opts = [g for g in opts if g <= cap] or [min(opts)]
    return opts


def _snap(grams, food):
    opts = _options(food)
    return min(opts, key=lambda g: abs(g - grams)) if opts else round(grams, 1)


def describe(food, grams):
    """Human-readable amount, Hebrew. Weighed items get grams, others units."""
    if food.get("by_weight") or not food.get("unit"):
        return f'{int(round(grams / 5.0) * 5)} ג\''
    u = food["unit"]
    n = grams / u["grams"]
    n = round(n * 2) / 2
    if n <= 0.5:
        return f'חצי {u["he"]}'
    if n == 1:
        return u["he"]
    if n == 1.5:
        return f'{u["he"]} וחצי'
    if n == int(n):
        return f'{int(n)} {u["he_plural"]}'
    return f'{int(n)} {u["he_plural"]} וחצי'


def feasible(pool, day_target):
    """
    Can this pool even reach the protein target within the calorie budget?
    Uses the most protein-efficient food available (highest protein per kcal).
    """
    prots = [f for f in pool if f["cat"] == "protein" and f["protein"] > 0]
    if not prots:
        return False, "no protein sources in pool"
    best = max(prots, key=lambda f: f["protein"] / max(f["kcal"], 1))
    kcal_needed = day_target["protein"] / best["protein"] * best["kcal"]
    if kcal_needed > day_target["kcal"] * 0.92:
        return False, (f"protein target needs ~{kcal_needed:.0f} kcal from the leanest "
                       f"source available ({best['name']}), budget is {day_target['kcal']}")
    return True, None


def solve(meals, meal_targets, day_target, rounds=12, fat_floor=None):
    """
    meals:     [[(food, proposed_grams), ...], ...]
    fat_floor: absolute minimum grams of fat for the day (spec 8.5, 0.6 g/kg).
               Enforced as a HARD constraint here, not just checked later -
               lean-first protein selection can otherwise push fat under it.
    Returns (solved_meals, ok, info)
    """
    cur = [[[f, float(g)] for f, g in m] for m in meals]
    flat = lambda: [(f, g) for m in cur for f, g in m]

    def group(cat):
        return [r for m in cur for r in m if r[0]["cat"] == cat]

    prot, carb, fat = group("protein"), group("carb"), group("fat")

    # ---- seed sensible starting sizes so ratios are not wild ----
    for r in prot: r[1] = 120.0
    for r in carb: r[1] = 100.0
    for r in fat:  r[1] = 15.0

    for _ in range(rounds):
        # 1) protein sources -> hit the day protein target
        if prot:
            other = sum(macros_for(f, g)["protein"] for f, g in flat()
                        if f["cat"] != "protein")
            need = max(day_target["protein"] - other, 0)
            have = sum(macros_for(r[0], r[1])["protein"] for r in prot)
            if have > 0:
                s = need / have
                for r in prot:
                    r[1] = _cap(r[0], r[1] * s)

        # 2) fat sources -> hit the day fat target
        if fat:
            other = sum(macros_for(f, g)["fat"] for f, g in flat() if f["cat"] != "fat")
            need = max(day_target["fat"] - other, 0)
            have = sum(macros_for(r[0], r[1])["fat"] for r in fat)
            if have > 0:
                s = need / have
                for r in fat:
                    r[1] = _cap(r[0], r[1] * s)

        # 3) carbs -> close the remaining calorie gap
        if carb:
            other = sum(macros_for(f, g)["kcal"] for f, g in flat() if f["cat"] != "carb")
            need = max(day_target["kcal"] - other, 0)
            have = sum(macros_for(r[0], r[1])["kcal"] for r in carb)
            if have > 0:
                s = need / have
                for r in carb:
                    r[1] = _cap(r[0], r[1] * s)

        # 4a) carbs pinned at the CEILING and calories still short -> add fat.
        #     High-calorie profiles (3000+) run out of carb headroom first.
        t = _sum(flat())
        if t["kcal"] < day_target["kcal"] * 0.98 and fat:
            capped = all(r[1] >= CAP["carb"] - 1 for r in carb) if carb else True
            if capped:
                short = day_target["kcal"] - t["kcal"]
                per_g = sum(r[0]["kcal"] for r in fat) / 100.0
                if per_g > 0:
                    add = short / per_g / len(fat)
                    for r in fat:
                        r[1] = _cap(r[0], r[1] + add)

        # 4b) if carbs are pinned at the floor and calories still overshoot,
        #     the excess must come out of fat, not protein
        t = _sum(flat())
        if t["kcal"] > day_target["kcal"] * 1.02 and fat:
            over = t["kcal"] - day_target["kcal"]
            per_g = sum(r[0]["kcal"] for r in fat) / 100.0
            if per_g > 0:
                cut = over / per_g / len(fat)
                for r in fat:
                    r[1] = _cap(r[0], r[1] - cut)

    # ---- snap to human portions, then micro-correct the drift snapping caused ----
    for m in cur:
        for r in m:
            r[1] = _snap(r[1], r[0])

    # Post-snap correction. Critically, this moves items between *human*
    # amounts only - it never re-scales by an arbitrary factor. The earlier
    # version re-scaled here and un-did the snapping, producing things like
    # "11 slices of bread" and "10g of avocado".
    rows = [r for m in cur for r in m]

    def err():
        """
        Normalised by each tolerance so no axis dominates the search.
        Fat carries a lower weight - calories and protein are the levers that
        drive the result, fat is mostly preference. But leaving it out entirely
        let fat swing from -44% to +112% of target, which a user would feel.
        """
        s = _sum(flat())
        ek = (s["kcal"] - day_target["kcal"]) / day_target["kcal"] / 0.05
        ep = (s["protein"] - day_target["protein"]) / day_target["protein"] / 0.07
        ef = (s["fat"] - day_target["fat"]) / max(day_target["fat"], 1) / 0.25
        return ek * ek + ep * ep + 0.4 * ef * ef

    for _ in range(140):
        best, cur_err = None, err()
        for r in rows:
            if r[0]["cat"] in ("veg", "fruit", "drink"):
                continue
            opts = _options(r[0])
            if not opts:
                continue
            i = opts.index(min(opts, key=lambda g: abs(g - r[1])))
            for j in (i - 3, i - 2, i - 1, i + 1, i + 2, i + 3):
                if not (0 <= j < len(opts)):
                    continue
                keep = r[1]
                r[1] = opts[j]
                e = err()
                r[1] = keep
                if e < cur_err - 1e-9:
                    best, cur_err = (r, opts[j]), e
        if best is None:
            break
        best[0][1] = best[1]

    # ---- hard fat floor: raise fat sources until the day clears it ----
    if fat_floor:
        for _ in range(30):
            s = _sum(flat())
            if s["fat"] >= fat_floor:
                break
            fats = [r for r in rows if r[0]["cat"] == "fat"] or \
                   [r for r in rows if r[0]["fat"] > 8]
            if not fats:
                break
            moved = False
            for r in fats:
                opts = _options(r[0])
                i = opts.index(min(opts, key=lambda g: abs(g - r[1])))
                if i + 1 < len(opts):
                    r[1] = opts[i + 1]
                    moved = True
                    break
            if not moved:
                break
        # calories drifted up - claw them back from carbs, floor stays intact
        for _ in range(30):
            s = _sum(flat())
            if s["kcal"] <= day_target["kcal"] * 1.05:
                break
            cbs = [r for r in rows if r[0]["cat"] == "carb"]
            if not cbs:
                break
            moved = False
            for r in cbs:
                opts = _options(r[0])
                i = opts.index(min(opts, key=lambda g: abs(g - r[1])))
                if i - 1 >= 0:
                    r[1] = opts[i - 1]
                    moved = True
                    break
            if not moved:
                break

    final = _sum(flat())
    ek = abs(final["kcal"] - day_target["kcal"]) / day_target["kcal"]
    ep = abs(final["protein"] - day_target["protein"]) / day_target["protein"]
    ok = ek <= 0.05 and ep <= 0.07
    info = dict(kcal_err=round(ek * 100, 1), protein_err=round(ep * 100, 1),
                totals={k: round(v) for k, v in final.items()})
    return [[(f, g) for f, g in m] for m in cur], ok, info
