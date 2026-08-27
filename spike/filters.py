import re
# -*- coding: utf-8 -*-
"""
Filter layer (spec 13.4.2) + validator (spec 10.1).
Both are pure code. The filter is the main cost lever AND the main
allergen safeguard: a food that never enters the prompt cannot appear
in the output.
"""
from foods import FOODS, macros_for

TOL_KCAL = 0.05      # +/- 5%
TOL_PROTEIN = 0.07   # +/- 7%
TOL_FAT = 0.35       # wide - fat is the remainder, not a lever
FAT_FLOOR_PER_KG = 0.6   # spec 8.5 - this one is a hard safety line


def eligible(profile):
    """Reduce the DB to the subset this profile may actually eat."""
    out = []
    allergies = set(profile.get("allergies", []))
    dislikes = set(profile.get("dislikes", []))
    kosher = profile.get("kosher", "none")   # none | kosher | separated
    diet = profile.get("diet", "omni")       # omni | vegetarian | vegan
    max_prep = {"minimal": 1, "medium": 2, "loves": 2}[profile.get("cooking", "medium")]
    max_price = {"cheap": 1, "normal": 2, "any": 3}[profile.get("budget", "normal")]

    for f in FOODS:
        if not f["menu_eligible"]:
            continue
        if f["allergens"] & allergies:
            continue
        if f["name"] in dislikes:
            continue
        if diet == "vegan" and "vegan" not in f["tags"]:
            continue
        if diet == "vegetarian" and f["kosher"] == "meat":
            continue
        if diet == "vegetarian" and "Fish" in f["allergens"]:
            continue
        if kosher in ("kosher", "separated") and f["kosher"] == "meat" and diet != "omni":
            continue
        if f["prep"] > max_prep:
            continue
        if f["price"] > max_price:
            continue
        out.append(f)
    return out


def kosher_conflict(items):
    """Meat and dairy in the same meal."""
    kinds = {i["kosher"] for i in items}
    return "meat" in kinds and "dairy" in kinds


def validate(menu, profile, day_targets, pool):
    """
    menu: [{'name':..,'items':[{'food':<name>,'grams':<n>}, ...]}, ...]
    Returns (ok, [errors]).
    """
    errs = []
    by_name = {f["name"]: f for f in FOODS}
    pool_names = {f["name"] for f in pool}
    allergies = set(profile.get("allergies", []))
    dislikes = set(profile.get("dislikes", []))

    tot = dict(kcal=0.0, protein=0.0, fat=0.0, carb=0.0)

    for meal in menu:
        objs = []
        for it in meal.get("items", []):
            f = by_name.get(it["food"])
            if f is None:
                errs.append(f"UNKNOWN_FOOD: {it['food']}")
                continue
            if f["name"] not in pool_names:
                errs.append(f"OUT_OF_POOL: {it['food']}")
            if f["allergens"] & allergies:
                errs.append(f"ALLERGEN: {it['food']} ({','.join(f['allergens'] & allergies)})")
            if f["name"] in dislikes:
                errs.append(f"DISLIKED: {it['food']}")
            objs.append(f)
            m = macros_for(f, it["grams"])
            for k in tot:
                tot[k] += m[k]
        if profile.get("kosher") == "separated" and kosher_conflict(objs):
            errs.append(f"KOSHER_MIX: {meal.get('name')}")

    if not menu:
        errs.append("EMPTY_MENU")
        return False, errs

    dk, dp = day_targets["kcal"], day_targets["protein"]
    if abs(tot["kcal"] - dk) / dk > TOL_KCAL:
        errs.append(f"KCAL_OFF: {tot['kcal']:.0f} vs {dk} ({(tot['kcal']-dk)/dk*100:+.1f}%)")
    if abs(tot["protein"] - dp) / dp > TOL_PROTEIN:
        errs.append(f"PROTEIN_OFF: {tot['protein']:.0f} vs {dp} ({(tot['protein']-dp)/dp*100:+.1f}%)")

    # fat: a hard safety floor, plus a wide sanity band above it
    floor = profile.get("weight", 0) * FAT_FLOOR_PER_KG
    if floor and tot["fat"] < floor:
        errs.append(f"FAT_BELOW_SAFETY_FLOOR: {tot['fat']:.0f}g vs {floor:.0f}g minimum")
    df = day_targets.get("fat")
    if df and abs(tot["fat"] - df) / df > TOL_FAT:
        errs.append(f"FAT_OFF: {tot['fat']:.0f} vs {df} ({(tot['fat']-df)/df*100:+.1f}%)")

    return len(errs) == 0, errs


MIN_PER_CAT = {"protein": 4, "carb": 3, "veg": 3, "fat": 2}
RELAX_HINT = {
    "protein": "allergies or diet type",
    "carb": "gluten sensitivity or cooking time",
    "fat": "tree-nut / sesame allergies",
    "veg": "the disliked-foods list",
}


def pool_health(pool, profile):
    """Is this pool rich enough to build a menu from? Returns (ok, missing, hint)."""
    cats = {c: sum(1 for x in pool if x["cat"] == c) for c in MIN_PER_CAT}
    missing = {c: (cats[c], MIN_PER_CAT[c]) for c in MIN_PER_CAT if cats[c] < MIN_PER_CAT[c]}
    if not missing:
        return True, {}, None
    worst = min(missing, key=lambda c: missing[c][0] - missing[c][1])
    return False, missing, RELAX_HINT[worst]


def sample_for_prompt(pool, profile, per_cat=None):
    """
    Third step the spec was missing: even after filtering, do not send the whole
    pool. Sample a diverse working set so the prompt stays small.

    Protein slots are ordered so COMPLETE proteins (all nine essential amino
    acids) come first. For non-vegan users the sample is therefore dominated by
    complete sources. Vegans keep the full plant list - excluding incomplete
    sources there would leave nothing to build from, and combining plant
    proteins across a day covers the amino acid profile anyway.
    """
    per_cat = per_cat or {"protein": 8, "carb": 6, "veg": 6, "fat": 4,
                          "fruit": 3, "drink": 2}
    vegan = profile.get("diet") == "vegan"
    out = []
    for c, n in per_cat.items():
        items = [x for x in pool if x["cat"] == c]
        if c == "protein":
            # Order by LEANNESS as well as completeness. Fat overshoot was
            # coming from fatty protein sources (eggs, mozzarella) needed to
            # hit a high protein target - not from the fat category at all.
            # Sorting lean-first lets the solver reach protein without
            # blowing the fat budget.
            # Supplements are excluded from the leanness advantage. Whey is
            # 78g protein to 5g fat - by ratio alone it beats every whole food
            # and ends up in every meal. A menu that is half protein shakes is
            # not a menu. Powders sort last and at most one enters the sample.
            # Order: whole foods before supplements, then by protein QUALITY,
            # then by leanness. Quality had to be added as its own dimension -
            # sorting on leanness alone put textured soy protein ahead of
            # chicken breast for omnivores, because its fat ratio is better.
            lean = lambda x: x["fat"] / max(x["protein"], 0.1)
            items.sort(key=lambda x: (x.get("supp", False),
                                      -x.get("quality", 0), lean(x)))
            whole = [x for x in items if not x.get("supp")]
            supps = sorted([x for x in items if x.get("supp")],
                           key=lambda x: -x.get("quality", 0))
            items = whole[:max(n - 1, 1)] + supps[:1]
        out.extend(items[:n])
    return out


def complete_ratio(sample):
    """Share of protein sources in the sample that are complete proteins."""
    prot = [f for f in sample if f["cat"] == "protein"]
    if not prot:
        return 0.0
    return sum(1 for f in prot if f.get("complete")) / len(prot)


def resolve(name, pool):
    """
    Tolerant food lookup. The model occasionally echoes the descriptor tags
    back with the name ("Almond milk, unsweetened [drink/parve]"). One run in
    40 failed on exactly that. Cheap to guard against.
    """
    if not name:
        return None
    exact = {f["name"]: f for f in pool}
    if name in exact:
        return exact[name]
    clean = re.sub(r"[\[(].*?[\])]", "", name).strip().strip('"').strip()
    if clean in exact:
        return exact[clean]
    low = {k.lower(): v for k, v in exact.items()}
    return low.get(clean.lower())
