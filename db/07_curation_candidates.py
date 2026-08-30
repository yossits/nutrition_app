# -*- coding: utf-8 -*-
"""
07_curation_candidates.py — the ranked candidate list for human curation.

READ-ONLY. This script never writes to the database. It opens a READ ONLY
transaction as its first statement and rolls back at the end, so an INSERT or
UPDATE added here later fails with a Postgres error instead of running quietly.
Curation itself starts in block 3; this is the raw material for the decision.

Run.
The DSN is read from .env at the repository root — see db/_env.py.

  python db\\07_curation_candidates.py

Output: db/curation_candidates_report.txt. Gitignored via db/*_report.txt, like
every other run report. Regenerated from scratch on every run.

What it produces: ~120 candidates, fat and protein only. Yossi approves 60 of
them in block 4, and ~25 of those go into the production canary in block 3.


THE DISCRIMINANT — class_code

food_curation.category is a curation field and curation has not started, so
there is no "fat source" or "protein source" marker in the database today. The
only structural discriminant available is class_code: an 8-digit hierarchical
food-group code inherited from the USDA classification, present on all 4,624
rows, where the first two digits are the food group.

  full class_code   4,624 distinct (one per item)
  first 4 digits      363 distinct
  first 2 digits       50 distinct

Its validity was measured, not assumed: the 116 FFQ rows excluded in block 1
occupy class_code group 90 exactly, with no remainder in either direction. That
is the same discriminant db/07_exclusion_reason.sql already relies on.

Two traps the measurement exposed, and how FAMILIES answers them:

  * The group alone is not enough. Olives sit under pickled vegetables (7551)
    and avocado under fruit (631050) — the two allergen-free fat sources that
    spec/05-food-db.md §5 demands depth in are exactly the two that a p2-only
    mapping would miss. Hence the p4 and p6 exceptions below.
  * A macro test alone is worse. "fat > 60% of energy and fat_g >= 10" returns
    577 items, including 72 cheeses, 25 chocolate confections and 13 ice
    creams. It also contradicts the seed convention: in spike/foods.py yellow
    cheese 28% is `protein`, not `fat`.

The mapping here is a PROPOSAL for review. It is not written to food_curation
and not written to docs/. Block 3 writes curation rows, after block 4.


THE RANKING — quotas per source family, ranked within the family

quality is the primary sort key under §5.3, and it is a curation field decided
in block 5. It does not exist yet and NOTHING here substitutes for it. What is
available is `complete`, derived from the nine essential amino acids in
04_transform.py and defined as the secondary sort in §5.1 — it is used as the
secondary key and named as such in the report header.

Quotas rather than one global score, because a global score over 209 fat items
returns a list that is all oils and nuts — which widens the bottleneck the list
exists to open.
"""

import io
import re
import sys
from pathlib import Path

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:
    sys.exit("psycopg is missing. Run:  pip install \"psycopg[binary]\"")

# sys.path[0] is db/ when this is run as `python db/07_curation_candidates.py`.
from _env import load_database_url, mask_dsn

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).parent

# The dry-form flag. spec/05-food-db.md §5.0.2 holds the menu pool to edible
# forms and says enforcement is by MARKING and human judgement at curation, not
# by exclusion — but nothing here did the marking, which is a spec describing an
# enforcement that does not exist. Two signals have to agree, because each one
# alone was measured against production on 29.08.2026 and each one alone is
# wrong:
#
#   moisture alone — the column is there (99.2% of the candidates carry it) and
#     it splits dry from cooked legumes perfectly: dry lentils 11.8 against
#     cooked 69.6, dry lupin 10.4 against cooked 69.6. It is still useless on
#     its own, because low water does not mean "not eaten as it stands": olive
#     oil is 0.0, raw tahini 0.0, ghee 0.2, nuts and seeds 1–5. At moisture < 10
#     the flag fires on 40 of the 119 candidates, 32 of them in the fat section
#     — a mark that lights up most of a table trains the reader to skip it.
#   the name alone — flags 11 and gets 4 of them wrong. The source names the raw
#     material and then the preparation, so "עדשים יבשים, מבושלים" is a COOKED
#     lentil, and "קלייה יבשה" is a roasting method rather than a form.
#
# Together they are clean: 7 flagged, none of them wrong, none in fat. Moisture
# vetoes the three cooked legumes for free. The roasting phrase is excluded by
# name and the exclusion is bounded — it matches exactly 3 rows in the whole
# database (1821, 8247, 8248). `(?<!מ)קמח` is flour and not the seven baked
# goods named "מקמח", made FROM flour.
#
# §5.0.2 admits name matching is weak in both directions and asks for it to be
# visible rather than trusted, which is why the flag carries a question mark and
# excludes nothing.
DRY_MOISTURE_MAX = 20                                    # g water per 100 g
DRY_NAME = re.compile(r"יבש|מיובש|אבק|(?<!מ)קמח")
DRY_NAME_VETO = re.compile(r"(קליה|קלייה|צליה|צלייה|אפיה|אפייה|בישול)\s+יבש")

# Animal food groups, by class_code prefix. Used for one thing only: the
# vegetable-fibre flag. The 29.08.2026 decision requires a PLANT item with a
# blank fiber_g to be verified against a label before it can be menu_eligible;
# a blank on butter or beef is not that case.
ANIMAL_P2 = {"11", "12", "13", "14",
             "21", "22", "23", "24", "25", "26", "27", "28",
             "31", "32", "33", "34", "81"}

# Group 82 is "oils", and it is NOT uniformly allergen-free. Splitting it is
# the whole point of the coverage section at the end of the report: counting
# all 28 oils as allergen-free would report the bottleneck as solved while
# sesame, peanut, walnut and almond oil sit inside the number. No structural
# split exists below group 82, so these two sets are explicit source_codes —
# auditable, and every selected row prints its own name for checking.
OLIVE_AVOCADO_OIL = {"4443",   # שמן זית
                     "4444",   # שמן זית כתית, מעודן
                     "4435",   # שמן קנולה וזית, זיתולה
                     "9808"}   # שמן אבוקדו
NUT_SESAME_OIL    = {"4448",   # שמן שומשום
                     "4445",   # שמן בוטנים
                     "4457",   # שמן אגוזי מלך
                     "4437"}   # שמן שקדים

# Category entry thresholds. A family may override any key; see FAMILIES.
DEFAULT_FLOORS = {
    "fat":     {"fat_g": 10},
    # The protein energy share is what keeps out dishes whose protein is
    # incidental to their carbohydrate — a pasta bake clears 10 g per 100 g and
    # is still a carbohydrate.
    "protein": {"protein_g": 10, "share": 0.25},
}

# Source families. Ordered — the FIRST match wins, so every narrow rule must
# precede the broad one it sits inside: the p6 olive rule before p4 7551, the
# p6 tahini rule before p2 43, the supplement rule before group 11.
#
# quota 0 means "mapped, deliberately not sampled for the canary". Those
# families stay in the table rather than being dropped from it — a family with
# no rule at all would vanish silently, and the pool count printed beside the
# quota is what makes the omission visible. Block 4 opens one by changing a
# single number.
FAMILIES = [
    # ---- fat -------------------------------------------------------------
    # Group 7551 is pickled vegetables, not olives: 15 of its 21 rows are
    # olives (p6 755100/755101/755102) and the rest are peppers and pickles.
    # Splitting at p6 rather than leaning on the fat_g floor keeps a fried
    # pepper at 10.6 g of fat out of the olive count.
    ("olive & avocado oil",   "fat",  4, lambda r: r["source_code"] in OLIVE_AVOCADO_OIL, {}),
    ("nut & sesame oil",      "fat",  3, lambda r: r["source_code"] in NUT_SESAME_OIL,    {}),
    ("other neutral oil",     "fat",  7, lambda r: r["p2"] == "82",                       {}),
    ("olives",                "fat", 10, lambda r: r["p6"] in ("755100", "755101", "755102"), {}),
    ("avocado",               "fat",  2, lambda r: r["p6"] == "631050",                   {}),
    # 431030 sesame seed and sesame butter · 431031 tahini salads ·
    # 431033 raw tahini. The rest of group 43 is pumpkin, sunflower, flax,
    # poppy, chia and watermelon seed — allergen-free, and a separate family.
    ("tahini & sesame",       "fat",  4, lambda r: r["p6"] in ("431030", "431031", "431033"), {}),
    ("other seeds",           "fat",  6, lambda r: r["p2"] == "43",                       {}),
    ("nuts & nut butters",    "fat",  7, lambda r: r["p2"] == "42",                       {}),
    ("butter & ghee",         "fat",  4, lambda r: r["p6"] in ("811010", "811011",
                                                               "811015", "812040"),       {}),
    ("margarine & spreads",   "fat",  2, lambda r: r["p4"] == "8110" or r["p6"] == "812031", {}),
    # 8132 is lecithin — an emulsifier at 100 g of fat per 100 g. It clears
    # every macro floor and is not a food. Mapped to its own quota-0 family
    # rather than left unmatched: an unmatched row disappears without a trace.
    ("food additives",        "fat",  0, lambda r: r["p4"] == "8132",                     {}),
    ("mayo & dressings",      "fat",  6, lambda r: r["p2"] == "83" or r["p4"] == "8130",  {}),
    ("rendered animal fat",   "fat",  0, lambda r: r["p6"] == "812010",                   {}),
    ("pickled vegetables",    "fat",  0, lambda r: r["p4"] == "7551",                     {}),
    ("carob",                 "fat",  0, lambda r: r["p2"] == "44",                       {}),

    # ---- protein ---------------------------------------------------------
    # The supplement rule comes first because group 1183 sits inside group 11.
    # Its floor of 50 g protein is what separates a protein powder from the
    # enteral formulas and cocoa powders that share the group.
    #
    # 414400 AND 414401 — the split is arbitrary and reading only the first half
    # was a real defect. 414400 holds 1720 (soy protein, 47 g, below the floor)
    # and 1723 (Ensure Plus, 5.2 g); the three soy powders that actually matter
    # sit in 414401: 1724 isolate 80.7 g, 8274 concentrate 63.6 g, and 1726, an
    # industrial full-fat soy powder at 41 g. Without 414401 all three fall
    # through to legumes, where 1724 and 8274 took 2 of the 10 slots — the
    # inverse of spec/05-food-db.md §5.0.2, since legumes are the depth the
    # narrow track exists to build. The floor still does its work inside the
    # family: 1726 is caught here and dropped at 50 g, which is the right
    # outcome — an industrial powder is not an edible form.
    ("protein powders",       "protein",  4, lambda r: (r["p4"] == "1183"
                                                        or r["p6"] in ("414400", "414401")
                                                        or r["source_code"] == "8547"),
     {"protein_g": 50}),
    ("poultry",               "protein", 12, lambda r: r["p2"] == "24",                   {}),
    ("fish & seafood",        "protein", 12, lambda r: r["p2"] == "26",                   {}),
    ("beef, veal & lamb",     "protein", 10, lambda r: r["p2"] in ("21", "23"),           {}),
    ("dairy & cheese",        "protein", 10, lambda r: r["p2"] in ("11", "14"),           {}),
    # Legumes get their own floor, and it is the one deliberate exception in
    # this table. Cooked lentils are 9 g of protein per 100 g and cooked
    # chickpeas 8.9 — the 10 g floor removes the entire category, which is
    # exactly what spec/05-food-db.md §5 forbids ("legumes and eggs alongside
    # meat and fish"). The 80 kcal floor replaces what the protein floor was
    # doing here: it keeps soy sauce, 8 g of protein in 59 kcal, out of a list
    # of protein sources. A condiment is not a protein source.
    ("legumes & soy",         "protein", 10, lambda r: r["p2"] == "41",
     {"protein_g": 7, "share": 0.20, "kcal": 80}),
    ("eggs",                  "protein",  5, lambda r: r["p2"] in ("31", "32", "34"),     {}),
    ("seitan & wheat gluten", "protein",  2, lambda r: r["p4"] == "5003",                 {}),
    ("organ meat",            "protein",  0, lambda r: r["p2"] == "25",                   {}),
    ("cooked dishes & soups", "protein",  0, lambda r: r["p2"] in ("27", "28"),           {}),
]

# Kosher exclusions. Not nutrition, and not negotiable for this market: an item
# here cannot become menu_eligible whatever its macros look like, so it has no
# business consuming a review slot.
#
# Fineness is limited by the taxonomy, and the limit is worth stating: eel
# (דג צלופח) is non-kosher and sits inside 2611 among sole and halibut, with no
# structural split to catch it. The coarse groups below are what class_code can
# express; the rest is a curation judgement in block 4.
EXCLUDED_P2 = {"22"}                                   # pork
EXCLUDED_P4 = {"2620", "2621", "2630", "2631",         # octopus · squid · crab · shellfish
               "2331"}                                 # rabbit
EXCLUDED_P6 = {"812020"}                               # rendered pork fat

# Allergen bucket per fat family, for the coverage section. This classifies the
# SOURCE, not the item: it is the question spec/05-food-db.md §5 asks — is the
# fat pool deep in sources that a sesame or nut allergy does not erase?
FAT_ALLERGEN_BUCKET = {
    "olive & avocado oil":  "core",
    "olives":               "core",
    "avocado":              "core",
    "other neutral oil":    "other allergen-free",
    "other seeds":          "other allergen-free",
    "carob":                "other allergen-free",
    "pickled vegetables":   "other allergen-free",
    "food additives":       "other allergen-free",
    "nuts & nut butters":   "nut & sesame",
    "tahini & sesame":      "nut & sesame",
    "nut & sesame oil":     "nut & sesame",
    "butter & ghee":        "dairy / egg",
    "margarine & spreads":  "dairy / egg",
    "mayo & dressings":     "dairy / egg",
    "rendered animal fat":  "dairy / egg",
}

# The candidate pool. Two mechanical exclusions and nothing else:
#   kcal IS NULL          — 8703 and 9740, which declare calories with no macro
#                           base to derive from
#   excluded_reason       — 116 ffq + 2 non_protein_nitrogen
#
# The filter is on excluded_reason and NOT on "has no curation row", so the
# script keeps working once block 3 starts adding ordinary curation rows.
POOL_SQL = """
SELECT f.source_code,
       f.class_code,
       left(f.class_code, 2) AS p2,
       left(f.class_code, 4) AS p4,
       left(f.class_code, 6) AS p6,
       f.name_he,
       f.source::text        AS source,
       f.kcal, f.protein_g, f.fat_g, f.carb_g, f.fiber_g,
       f.complete,
       (SELECT fn.value FROM food_nutrients fn
          JOIN nutrients n ON n.id = fn.nutrient_id
         WHERE fn.food_id = f.id AND n.code = 'moisture')            AS moisture,
       (SELECT count(*) FROM food_servings s WHERE s.food_id = f.id) AS servings,
       EXISTS (SELECT 1 FROM v_kcal_outliers o
               WHERE o.source_code = f.source_code)                   AS is_outlier
FROM foods f
LEFT JOIN food_curation c ON c.source_code = f.source_code
WHERE f.kcal IS NOT NULL
  AND f.kcal > 0
  AND c.excluded_reason IS NULL
"""

SOURCE_RANK = {"ingredient": 0, "industry": 1, "recipe": 2}

NAME_W = 46          # name_he column width
SEP = " | "


def is_excluded(row):
    """Kosher exclusions. See EXCLUDED_P2 for why these come before anything."""
    return (row["p2"] in EXCLUDED_P2
            or row["p4"] in EXCLUDED_P4
            or row["p6"] in EXCLUDED_P6)


def family_of(row):
    """First matching family, or None. Order in FAMILIES is load-bearing."""
    if is_excluded(row):
        return None
    for label, category, _quota, match, _floors in FAMILIES:
        if match(row):
            return (label, category)
    return None


def floors_for(label):
    """Category defaults, overridden per family."""
    for lbl, category, _quota, _match, overrides in FAMILIES:
        if lbl == label:
            return {**DEFAULT_FLOORS[category], **overrides}
    raise KeyError(label)


def passes_floor(row, label):
    floors = floors_for(label)
    for key in ("fat_g", "protein_g", "kcal"):
        if key in floors and float(row[key]) < floors[key]:
            return False
    if "share" in floors:
        if (float(row["protein_g"]) * 4) / float(row["kcal"]) < floors["share"]:
            return False
    return True


def describe_floors(label):
    """The family's entry threshold, printed beside it. A floor nobody can see
    is a filter nobody can argue with."""
    floors = floors_for(label)
    parts = []
    if "fat_g" in floors:
        parts.append(f"fat>={floors['fat_g']}")
    if "protein_g" in floors:
        parts.append(f"prot>={floors['protein_g']}")
    if "share" in floors:
        parts.append(f"share>={floors['share']:.2f}")
    if "kcal" in floors:
        parts.append(f"kcal>={floors['kcal']}")
    return ", ".join(parts)


def sort_key(row, category):
    """Rank within a family. See the module docstring on why quality is absent."""
    base = (
        SOURCE_RANK.get(row["source"], 3),      # ingredient before industry before recipe
        0 if row["servings"] > 0 else 1,        # a human serving unit first
        1 if row["is_outlier"] else 0,          # Atwater outliers sink, they do not drop
    )
    if category == "fat":
        density = -float(row["fat_g"])
        return base + (density, int(row["source_code"]))
    return base + (
        0 if row["complete"] else 1,            # §5.1 — the available secondary key
        -(float(row["protein_g"]) * 4) / float(row["kcal"]),
        int(row["source_code"]),
    )


def select_candidates(pool):
    """Pool rows -> (selected, pool_sizes, n_excluded).

    selected    {"fat": [(family_label, row), ...], "protein": [...]}
    pool_sizes  how many rows reached each family, counted BEFORE its floor
    n_excluded  the non-kosher drop count

    Lifted out of main() unchanged so db/11_curation_sheet.py can reuse the
    selection instead of restating it. Two statements of which rows are the
    candidates would not raise when they diverged — they would quietly hand
    the curation sheet a different list from the one this report shows, which
    is the failure mode the whole read-only discipline here exists to avoid.
    """
    by_family = {}
    pool_sizes = {}
    n_excluded = 0

    for row in pool:
        if is_excluded(row):
            n_excluded += 1
            continue
        hit = family_of(row)
        if hit is None:
            continue
        label, _category = hit
        pool_sizes[label] = pool_sizes.get(label, 0) + 1
        if not passes_floor(row, label):
            continue
        by_family.setdefault(label, []).append(row)

    selected = {"fat": [], "protein": []}
    for label, category, quota, _m, _f in FAMILIES:
        if quota == 0:
            continue
        rows = sorted(by_family.get(label, []), key=lambda r: sort_key(r, category))
        for row in rows[:quota]:
            selected[category].append((label, row))

    return selected, pool_sizes, n_excluded


def is_dry_form(row, family):
    """Does this look like a form nobody eats as it stands? See DRY_NAME above.

    `family` is needed for one exemption and one only: a protein powder IS eaten
    as powder, and §5.0.2 names it as its own exception, governed by supp and
    the 12% ceiling of §5.4 instead. Marking all four of them dry? would be
    noise, and noise is what teaches a reader to skip a flag.
    """
    if family == "protein powders":
        return False
    if row["moisture"] is None or float(row["moisture"]) >= DRY_MOISTURE_MAX:
        return False
    name = " ".join(str(row["name_he"]).split())
    return bool(DRY_NAME.search(name)) and not DRY_NAME_VETO.search(name)


def flags_of(row, family):
    """The four marks. Marks, not exclusions — every flagged item stays."""
    flags = []
    if row["is_outlier"]:
        flags.append("outlier")
    if row["fiber_g"] is None and row["p2"] not in ANIMAL_P2:
        flags.append("fiber?")
    if row["servings"] == 0:
        flags.append("by_weight?")
    if is_dry_form(row, family):
        flags.append("dry?")
    return flags


def fmt(value, width, decimals=1):
    if value is None:
        return "∅".rjust(width)
    return f"{float(value):.{decimals}f}".rjust(width)


def pad_name(name):
    """Fixed-width name column. Newlines exist in the source data (8743)."""
    name = " ".join(str(name).split())
    if len(name) > NAME_W:
        name = name[:NAME_W - 1] + "…"
    return name.ljust(NAME_W)


HEADER = (SEP.join(["code ", pad_name("name_he"), "kcal ", "prot", " fat",
                    "carb", "fibr", "cmpl", "un", "flags"]))


def write_table(out, category, title, note, selected, quotas):
    """One category table: totals, then a block per family."""
    rows = [r for _, r in selected]
    n_out = sum(1 for r in rows if r["is_outlier"])
    n_fib = sum(1 for r in rows if r["fiber_g"] is None and r["p2"] not in ANIMAL_P2)
    n_wgt = sum(1 for r in rows if r["servings"] == 0)
    n_dry = sum(1 for fam, r in selected if is_dry_form(r, fam))

    out.write(f"\n\n{'=' * 118}\n")
    out.write(f"▸ {title} — {len(rows)} candidates · "
              f"{n_out} kcal outliers · {n_fib} unknown fibre · {n_wgt} by_weight · "
              f"{n_dry} dry\n")
    out.write(f"  {note}\n")
    out.write(f"{'=' * 118}\n")

    for label, cat, quota, _match, _floors in FAMILIES:
        if cat != category or quota == 0:
            continue
        picked = [r for fam, r in selected if fam == label]
        out.write(f"\n  {label} — {len(picked)}/{quota} "
                  f"of {quotas.get(label, 0)} in group  [{describe_floors(label)}]"
                  f"{'   POOL EXHAUSTED' if len(picked) < quota else ''}\n")
        out.write("  " + HEADER + "\n")
        out.write("  " + "-" * 116 + "\n")
        for r in picked:
            out.write("  " + SEP.join([
                str(r["source_code"]).ljust(5),
                pad_name(r["name_he"]),
                fmt(r["kcal"], 5, 0),
                fmt(r["protein_g"], 4),
                fmt(r["fat_g"], 4),
                fmt(r["carb_g"], 4),
                fmt(r["fiber_g"], 4),
                ("yes" if r["complete"] else "no").ljust(4),
                str(r["servings"]).rjust(2),
                " · ".join(flags_of(r, label)),
            ]).rstrip() + "\n")

    zero = [f"{lbl} ({quotas.get(lbl, 0)} in group)"
            for lbl, cat, quota, _m, _f in FAMILIES
            if cat == category and quota == 0]
    if zero:
        out.write("\n  Mapped, quota 0 — staples before dishes, and open in "
                  "block 4 by changing one number:\n    " + " · ".join(zero) + "\n")


def write_coverage(out, selected_fat):
    """The number that decides whether the list opens the bottleneck.

    The question spec/05-food-db.md §5 asks is about SOURCES, not about tagged
    allergens: is there enough fat left standing once a sesame or nut allergy
    removes tahini and nuts? Counted from the selection, not from the quotas.
    """
    per_family = {}
    for fam, _row in selected_fat:
        per_family[fam] = per_family.get(fam, 0) + 1

    def bucket_total(name):
        return sum(n for fam, n in per_family.items()
                   if FAT_ALLERGEN_BUCKET.get(fam) == name)

    def breakdown(name):
        parts = [f"{fam} {n}" for fam, n in sorted(per_family.items())
                 if FAT_ALLERGEN_BUCKET.get(fam) == name]
        return " · ".join(parts) if parts else "none"

    named_three = (per_family.get("olive & avocado oil", 0)
                   + per_family.get("olives", 0)
                   + per_family.get("avocado", 0))
    nut_sesame = bucket_total("nut & sesame")

    out.write(f"\n\n{'=' * 118}\n")
    out.write("▸ ALLERGEN-FREE FAT COVERAGE — the number that decides whether this\n"
              "  list opens the bottleneck or only widens it\n")
    out.write(f"{'=' * 118}\n\n")
    out.write(f"  olive oil · avocado · olives   {named_three:>3}   "
              f"{breakdown('core')}\n")
    out.write(f"  tahini · nuts · their oils     {nut_sesame:>3}   "
              f"{breakdown('nut & sesame')}\n")
    out.write(f"  {'-' * 74}\n")
    out.write(f"  ratio, the headline            {named_three} : {nut_sesame}"
              f"   {'core holds' if named_three >= nut_sesame else 'NUT AND SESAME DOMINATE'}\n\n")
    out.write(f"  other allergen-free            "
              f"{bucket_total('other allergen-free'):>3}   "
              f"{breakdown('other allergen-free')}\n")
    out.write(f"  dairy / egg bearing            "
              f"{bucket_total('dairy / egg'):>3}   "
              f"{breakdown('dairy / egg')}\n")
    out.write(f"\n  allergen-free in total         "
              f"{named_three + bucket_total('other allergen-free'):>3}"
              f"   of {sum(per_family.values())} fat candidates\n")


def main():
    url = load_database_url()
    out = io.StringIO()

    try:
        conn_ctx = psycopg.connect(url, row_factory=dict_row)
    except psycopg.OperationalError as exc:
        sys.exit(f"Cannot connect to {mask_dsn(url)}\n{exc}")

    with conn_ctx as conn:
        with conn.cursor() as cur:
            # First statement in the transaction, and the reason this script is
            # safe to run against production during curation: any write added
            # here later fails loudly instead of running quietly.
            cur.execute("SET TRANSACTION READ ONLY")

            cur.execute("SELECT count(*) AS n FROM food_curation")
            curation_before = cur.fetchone()["n"]

            cur.execute(POOL_SQL)
            pool = cur.fetchall()

            # Proof, in the report, that the two mechanical exclusions bit.
            cur.execute("""SELECT excluded_reason::text AS reason, count(*) AS n
                           FROM food_curation WHERE excluded_reason IS NOT NULL
                           GROUP BY 1 ORDER BY 1""")
            exclusions = cur.fetchall()
            cur.execute("SELECT count(*) AS n FROM foods WHERE kcal IS NULL")
            kcal_null = cur.fetchone()["n"]
            cur.execute("SELECT count(*) AS n FROM foods")
            foods_total = cur.fetchone()["n"]

        # ---- family assignment, thresholds, quotas ---------------------
        selected, pool_sizes, n_excluded = select_candidates(pool)

        # ---- report ----------------------------------------------------
        out.write("CURATION CANDIDATES — fat and protein, ranked for human review\n")
        out.write("Generated by db/07_curation_candidates.py. READ-ONLY: nothing was written.\n")
        out.write(f"\nfoods {foods_total} · candidate pool {len(pool)} after "
                  f"{kcal_null} kcal IS NULL and "
                  + " + ".join(f"{e['n']} {e['reason']}" for e in exclusions)
                  + " were removed\n")
        out.write(f"{n_excluded} further rows dropped as non-kosher — pork, pork fat, "
                  "rabbit, shellfish, squid, octopus, crab.\n"
                  "  Eel is non-kosher too and has no class_code of its own; it sits "
                  "inside 2611 with sole and halibut, so it survives here.\n")
        out.write("Category comes from class_code, not from food_curation.category, "
                  "which does not exist yet.\n"
                  "This mapping is a proposal for review. It is not written anywhere.\n")
        out.write("\nFlags mark, they never exclude — every flagged row stays in the "
                  "list.\n"
                  "  outlier     the derived kcal and the file's disagree beyond the "
                  "Atwater gate\n"
                  "  fiber?      a plant item with no fibre value; verify against a "
                  "label before menu_eligible\n"
                  "  by_weight?  the source gives no human serving unit\n"
                  "  dry?        a form that is not eaten as it stands (§5.0.2): "
                  f"moisture under {DRY_MOISTURE_MAX} g AND a name that says so.\n"
                  "              Both are required — oil and nuts are dry and edible, "
                  "and \"עדשים יבשים, מבושלים\" is cooked.\n"
                  "              Protein powders are exempt; a powder eaten as powder "
                  "is §5.0.2's own exception, held by §5.4.\n")

        write_table(
            out, "fat", "FAT",
            "Ranked by source kind, then serving unit, then Atwater outlier, "
            "then fat_g. Entry floor per family in brackets.",
            selected["fat"], pool_sizes)

        write_table(
            out, "protein", "PROTEIN",
            "Ranked by source kind, then serving unit, then Atwater outlier, then "
            "`complete`, then protein energy share.\n  quality is a block-5 "
            "curation field and is NOT available. `complete` is the secondary key "
            "under §5.1; nothing stands in for quality.",
            selected["protein"], pool_sizes)

        write_coverage(out, selected["fat"])

        # ---- read-only proof -------------------------------------------
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) AS n FROM food_curation")
            curation_after = cur.fetchone()["n"]
        out.write(f"\n\n▸ Read-only proof — food_curation {curation_before} rows before, "
                  f"{curation_after} after\n")

        # Never commit. The transaction is READ ONLY, so this is belt and
        # braces — and belt and braces is the point.
        conn.rollback()

    report = out.getvalue()
    (HERE / "curation_candidates_report.txt").write_text(report, encoding="utf-8")
    print(report)
    print(f"\n✔ Saved: {HERE / 'curation_candidates_report.txt'} — hand this over.")


if __name__ == "__main__":
    main()
