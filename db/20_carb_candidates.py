# -*- coding: utf-8 -*-
"""
20_carb_candidates.py — the carbohydrate candidate sheet for block 8פ (8פ-ג).

READ-ONLY. Opens a READ ONLY transaction as its first statement and rolls back
at the end, exactly as 07_curation_candidates.py does. Nothing is written to
the database; the only output is db/block8_carb_candidates.tsv.

Run.
The DSN is read from .env at the repository root — see db/_env.py.

  python db\\20_carb_candidates.py

Output: db/block8_carb_candidates.tsv — UTF-8, LF, tab-separated, one header
row, one row per sheet item, sorted by family then rank. Committed, unlike the
*_report.txt files: it is the sheet the owner reviews in 8פ-ד.


WHAT THIS FILE IS

07 has no carbohydrate branch (its FAMILIES table is fat and protein only), and
the 12.09.2026 decision keeps it that way — 07 is not modified. This script
COPIES 07's mechanisms and applies them to the carbohydrate families of
spec/05-food-db.md §5.5 (families 26–39, decided in 8פ-ב). Each copied piece is
marked "copied from 07" at the point of use:

  POOL_SQL                    the candidate pool — kcal present and > 0, no
                              excluded_reason; the moisture subquery; p2/p4/p6
                              from class_code; the servings count; membership
                              in v_kcal_outliers. One column is ADDED here:
                              coalesce(c.menu_eligible, false) AS eligible.
  SOURCE_RANK                 ingredient 0 · industry 1 · recipe 2.
  EXCLUDED_P2/P4/P6           the kosher exclusions of §5.5, run before the
                              families (is_excluded, family_of).
  sort_key                    07's key shape — a recipe sinks below every raw
                              material, then outliers sink, then the nutrition
                              term (here -carb_share), then src_rank, then the
                              servings gate, then source_code.
  take_with_cap               the p4 cap: P4_CAP = 4 per p4 on the capped pass
                              for a quota of P4_CAP_MIN_QUOTA = 10 or more, then
                              a refill in rank order. Extended here to return
                              the band (1 capped pass, 2 refill) beside the row.
  is_dry_form / is_raw_form   the dry? and raw? marks. 11_curation_sheet.py
                              takes both from 07 through CAND.flags_of(); the
                              rules live in 07 and are copied from there.
  is_excluded / family_of     first match wins; exclusions before families.

Family membership is decided in Python, as 07 does it. The one Hebrew pattern —
"תירס" for the corn family — runs ONCE as a parameterised LIKE against foods
(never inline in the SQL string) and yields an explicit source_code set, the
same shape 07 uses for OLIVE_AVOCADO_OIL.


THE FLOOR

Default: carb_g >= 15 AND carb_g * 4 / kcal >= 0.5. Family 30 (breakfast
cereals & cooked wheat) overrides carb_g to 10 for cooked porridge. A row with
carb_g NULL fails the floor — 8פ-א's SQL probes counted it that way too.

The share is the working half of the floor: chips (~0.47) and pizza (~0.48)
fall under 0.5, whole-wheat bread 8348 passes at 0.54; 0.6 was rejected for
that reason (decisions.md, 12.09.2026).
"""

import csv
import re
import sys
from pathlib import Path

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:
    sys.exit("psycopg is missing. Run:  pip install \"psycopg[binary]\"")

# sys.path[0] is db/ when this is run as `python db/20_carb_candidates.py`.
from _env import load_database_url, mask_dsn

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).parent
OUT_PATH = HERE / "block8_carb_candidates.tsv"

# ---------------------------------------------------------------------------
# copied from 07 — the dry-form flag (DRY_MOISTURE_MAX, DRY_NAME, DRY_NAME_VETO)
DRY_MOISTURE_MAX = 20                                    # g water per 100 g
DRY_NAME = re.compile(r"יבש|מיובש|אבק|(?<!מ)קמח")
DRY_NAME_VETO = re.compile(r"(קליה|קלייה|צליה|צלייה|אפיה|אפייה|בישול)\s+יבש")

# copied from 07 — the raw-form flag (#28, 3ו2ד)
RAW_NAME = re.compile(r"(?<!\w)לא מבושל")
RAW_FRESH = re.compile(r"(?<!\w)טרי(?!\w)")
RAW_FROZEN = re.compile(r"קפוא")
RAW_FROZEN_VETO = re.compile(r"מבושל")
RAW_ANIMAL_FAMILIES = {"poultry", "fish & seafood", "beef, veal & lamb"}

# copied from 07 — the p4 cap
P4_CAP = 4                # rows per p4 in the capped pass
P4_CAP_MIN_QUOTA = 10     # below this a quota is too small to spread

# copied from 07 — kosher exclusions of §5.5
EXCLUDED_P2 = {"22"}                                   # pork
EXCLUDED_P4 = {"2620", "2621", "2630", "2631",         # octopus · squid · crab · shellfish
               "2331"}                                 # rabbit
EXCLUDED_P6 = {"812020"}                               # rendered pork fat

# copied from 07 — POOL_SQL, plus ONE added column: eligible (menu_eligible today)
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
               WHERE o.source_code = f.source_code)                   AS is_outlier,
       coalesce(c.menu_eligible, false)                               AS eligible
FROM foods f
LEFT JOIN food_curation c ON c.source_code = f.source_code
WHERE f.kcal IS NOT NULL
  AND f.kcal > 0
  AND c.excluded_reason IS NULL
"""

# copied from 07
SOURCE_RANK = {"ingredient": 0, "industry": 1, "recipe": 2}

# The corn family (33) is "תירס" inside p4 7510 · 7521. The pattern goes to the
# server as a query parameter — never inline in the SQL string — and the result
# is an explicit source_code set, the shape 07 uses for OLIVE_AVOCADO_OIL.
CORN_P4 = ("7510", "7521")
CORN_SQL = """
SELECT f.source_code
FROM foods f
WHERE left(f.class_code, 4) = ANY(%s)
  AND f.name_he LIKE %s
ORDER BY f.source_code::int
"""
CORN_PATTERN = "%תירס%"

DEFAULT_FLOOR = {"carb_g": 15, "share": 0.5}

# The carbohydrate families of §5.5 (decided 12.09.2026, 8פ-ב). Ordered — the
# FIRST match wins, as in 07. 32 and 33 are p4-level and sit inside p2 groups
# 73 and 75, which are not families, so no p2 rule shadows them.
#   (number, label, quota, match, floor overrides)
FAMILIES = [
    (26, "bread",                             15, lambda r: r["p2"] == "51",              {}),
    (27, "flatbreads & tortillas",             3, lambda r: r["p2"] == "52",              {}),
    (28, "matza, crispbread, crackers",        6, lambda r: r["p2"] == "54",              {}),
    (29, "cooked grains, rice & pasta",       18, lambda r: r["p2"] == "56",              {}),
    (30, "breakfast cereals & cooked wheat",   6, lambda r: r["p2"] == "57",              {"carb_g": 10}),
    (31, "potatoes",                           8, lambda r: r["p2"] == "71",              {}),
    (32, "sweet potato",                       3, lambda r: r["p4"] == "7340",            {}),
    (33, "corn",                               3, lambda r: r["source_code"] in CORN_CODES, {}),
    (34, "cakes & cookies",                    0, lambda r: r["p2"] == "53",              {}),
    (35, "pastries & composite dishes",        0, lambda r: r["p2"] == "58",              {}),
    (36, "sugars & sweets",                    0, lambda r: r["p2"] == "91",              {}),
    (37, "dairy desserts & ice cream",         0, lambda r: r["p2"] == "13",              {}),
    (38, "fruit & dried fruit",                0, lambda r: r["p2"] in ("62", "63"),      {}),
    (39, "doughs & waffles",                   0, lambda r: r["p2"] == "55",              {}),
]

CORN_CODES = set()      # filled from CORN_SQL before the families are applied

TSV_COLUMNS = ["family", "p2", "p4", "source_code", "name_he", "source", "kcal",
               "carb_g", "carb_share", "fiber_g", "moisture", "dry?", "raw?",
               "fiber?", "outlier?", "eligible", "has_serving", "band", "rank"]


# copied from 07
def is_excluded(row):
    """Kosher exclusions. See EXCLUDED_P2 for why these come before anything."""
    return (row["p2"] in EXCLUDED_P2
            or row["p4"] in EXCLUDED_P4
            or row["p6"] in EXCLUDED_P6)


def match_family(row):
    """First matching family regardless of kosher — used to count what the
    exclusions removed from the carb families. Order in FAMILIES is load-bearing."""
    for number, label, _quota, match, _floors in FAMILIES:
        if match(row):
            return number
    return None


# copied from 07 (family_of) — exclusions first, then first match wins
def family_of(row):
    if is_excluded(row):
        return None
    return match_family(row)


def floors_for(number):
    for num, _label, _quota, _match, overrides in FAMILIES:
        if num == number:
            return {**DEFAULT_FLOOR, **overrides}
    raise KeyError(number)


def carb_share(row):
    """Carbohydrate energy share: carb_g * 4 / kcal. kcal > 0 by POOL_SQL."""
    if row["carb_g"] is None:
        return None
    return (float(row["carb_g"]) * 4) / float(row["kcal"])


def passes_floor(row, number):
    floors = floors_for(number)
    if row["carb_g"] is None:
        return False
    if float(row["carb_g"]) < floors["carb_g"]:
        return False
    return carb_share(row) >= floors["share"]


# copied from 07 (sort_key) — the nutrition term is -carb_share here
def sort_key(row):
    """Rank within a family: raw material first, then the food, then the record."""
    return (
        1 if row["source"] == "recipe" else 0,  # a dish sinks below every raw material
        1 if row["is_outlier"] else 0,          # Atwater outliers sink, they do not drop
        -carb_share(row),                       # the carbohydrate energy share
        SOURCE_RANK.get(row["source"], 3),      # tie-break: ingredient before industry; recipe is already below
        0 if row["servings"] > 0 else 1,        # tie-break: a human serving unit first
        int(row["source_code"]),
    )


# copied from 07 (take_with_cap) — returns (row, band) instead of row
def take_with_cap(rows, quota):
    """The first `quota` rows, at most P4_CAP per p4 on the capped pass.

    `rows` arrive in rank order. The capped pass walks them and takes a row
    while its p4 has fewer than P4_CAP taken. The refill pass runs only if the
    first came up short, and walks the same order again taking what the first
    skipped. Band 1 is the capped pass, band 2 the refill; a family under
    P4_CAP_MIN_QUOTA is returned untouched, all band 1.
    """
    if quota < P4_CAP_MIN_QUOTA:
        return [(row, 1) for row in rows[:quota]]

    taken, skipped, per_p4 = [], [], {}
    for row in rows:
        if len(taken) >= quota:
            break
        p4 = row["p4"]
        if per_p4.get(p4, 0) < P4_CAP:
            per_p4[p4] = per_p4.get(p4, 0) + 1
            taken.append((row, 1))
        else:
            skipped.append(row)

    for row in skipped:
        if len(taken) >= quota:
            break
        taken.append((row, 2))

    return taken


# copied from 07 (is_dry_form) — the powder exemption is kept as written; no
# carbohydrate family is "protein powders", so it never fires here
def is_dry_form(row, family):
    if family == "protein powders":
        return False
    if row["moisture"] is None or float(row["moisture"]) >= DRY_MOISTURE_MAX:
        return False
    name = " ".join(str(row["name_he"]).split())
    return bool(DRY_NAME.search(name)) and not DRY_NAME_VETO.search(name)


# copied from 07 (is_raw_form) — only the "לא מבושל" marker can fire here; the
# fresh/frozen markers are limited to the animal families
def is_raw_form(row, family):
    name = " ".join(str(row["name_he"]).split())
    if family != "protein powders" and RAW_NAME.search(name):
        return True
    if family not in RAW_ANIMAL_FAMILIES:
        return False
    if RAW_FRESH.search(name):
        return True
    return bool(RAW_FROZEN.search(name)) and not RAW_FROZEN_VETO.search(name)


def select_candidates(pool):
    """Pool rows -> (sheet, passing, n_excluded_total, n_excluded_carb).

    sheet     {family_number: [(row, band), ...]} in take order
    passing   {family_number: n rows past the floor (kosher exclusions applied)}
    """
    by_family, passing = {}, {}
    n_excluded_total = n_excluded_carb = 0
    for row in pool:
        if is_excluded(row):
            n_excluded_total += 1
            if match_family(row) is not None:
                n_excluded_carb += 1
            continue
        number = family_of(row)
        if number is None:
            continue
        if not passes_floor(row, number):
            continue
        passing[number] = passing.get(number, 0) + 1
        by_family.setdefault(number, []).append(row)

    sheet = {}
    for number, _label, quota, _match, _floors in FAMILIES:
        if quota == 0:
            continue
        rows = sorted(by_family.get(number, []), key=sort_key)
        sheet[number] = take_with_cap(rows, quota)
    return sheet, passing, n_excluded_total, n_excluded_carb


def num(value, digits):
    if value is None:
        return ""
    return f"{float(value):.{digits}f}"


def main():
    global CORN_CODES
    url = load_database_url()

    try:
        conn_ctx = psycopg.connect(url, row_factory=dict_row)
    except psycopg.OperationalError as exc:
        sys.exit(f"Cannot connect to {mask_dsn(url)}\n{exc}")

    with conn_ctx as conn:
        with conn.cursor() as cur:
            # First statement in the transaction: any write added here later
            # fails loudly instead of running quietly.
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("SELECT count(*) AS n FROM food_curation")
            curation_before = cur.fetchone()["n"]
            cur.execute(CORN_SQL, (list(CORN_P4), CORN_PATTERN))
            CORN_CODES = {r["source_code"] for r in cur.fetchall()}
            cur.execute(POOL_SQL)
            pool = cur.fetchall()
            cur.execute("SELECT count(*) AS n FROM food_curation")
            curation_after = cur.fetchone()["n"]
        conn.rollback()

    sheet, passing, n_excl_total, n_excl_carb = select_candidates(pool)

    # ---- the TSV -----------------------------------------------------------
    rows_out = []
    for number, label, quota, _match, _floors in FAMILIES:
        for rank, (r, band) in enumerate(sheet.get(number, []), 1):
            rows_out.append({
                "family": number,
                "p2": r["p2"],
                "p4": r["p4"],
                "source_code": r["source_code"],
                "name_he": " ".join(str(r["name_he"]).split()),
                "source": r["source"],
                "kcal": num(r["kcal"], 1),
                "carb_g": num(r["carb_g"], 1),
                "carb_share": f"{carb_share(r):.3f}",
                "fiber_g": num(r["fiber_g"], 1),
                "moisture": num(r["moisture"], 1),
                "dry?": 1 if is_dry_form(r, label) else 0,
                "raw?": 1 if is_raw_form(r, label) else 0,
                "fiber?": 1 if r["fiber_g"] is None else 0,
                "outlier?": 1 if r["is_outlier"] else 0,
                "eligible": 1 if r["eligible"] else 0,
                "has_serving": 1 if r["servings"] > 0 else 0,
                "band": band,
                "rank": rank,
            })
    with open(OUT_PATH, "w", encoding="utf-8", newline="\n") as fh:
        writer = csv.DictWriter(fh, fieldnames=TSV_COLUMNS, delimiter="\t",
                                lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows_out)

    # ---- the summary -------------------------------------------------------
    print("CARB CANDIDATES — block 8פ, families 26–39 of §5.5. READ-ONLY: nothing was written to the database.")
    print(f"candidate pool {len(pool)} · kosher exclusions {n_excl_total} pool-wide, "
          f"{n_excl_carb} in carb families · food_curation {curation_before} before, {curation_after} after")
    print(f"corn (33) source_code set from LIKE {CORN_PATTERN!r} in p4 {CORN_P4}: "
          + ", ".join(sorted(CORN_CODES, key=int)) + f"  (n={len(CORN_CODES)})")
    print()
    print("family | label | quota | floor-passing | band1 | band2 | in sheet | recipes | dry? | fiber? | outlier? | eligible today")
    total = 0
    per_family = {}
    for number, label, quota, _match, _floors in FAMILIES:
        taken = sheet.get(number, [])
        n_pass = passing.get(number, 0)
        b1 = sum(1 for _r, b in taken if b == 1)
        b2 = sum(1 for _r, b in taken if b == 2)
        n_sheet = len(taken)
        n_rec = sum(1 for r, _b in taken if r["source"] == "recipe")
        n_dry = sum(1 for r, _b in taken if is_dry_form(r, label))
        n_fib = sum(1 for r, _b in taken if r["fiber_g"] is None)
        n_out = sum(1 for r, _b in taken if r["is_outlier"])
        n_eli = sum(1 for r, _b in taken if r["eligible"])
        per_family[number] = n_sheet
        total += n_sheet
        short = "   POOL EXHAUSTED" if (quota and n_pass < quota) else ""
        print(f"{number} | {label} | {quota} | {n_pass} | {b1} | {b2} | {n_sheet} | {n_rec} | {n_dry} | {n_fib} | {n_out} | {n_eli}{short}")
        # S5: a family with more passing rows than its quota fills it exactly
        if quota and n_pass > quota:
            assert n_sheet == quota, f"family {number}: {n_sheet} in sheet, quota {quota}, passing {n_pass}"
        if quota and n_pass <= quota:
            assert n_sheet == n_pass, f"family {number}: {n_sheet} in sheet, passing {n_pass}"
    print(f"\ntotal in sheet: {total} (sum of per-family counts: {sum(per_family.values())}; TSV rows written: {len(rows_out)})")
    assert total == sum(per_family.values()) == len(rows_out)
    assert CORN_CODES, "corn set is empty"          # S5
    print(f"TSV: {OUT_PATH}")


if __name__ == "__main__":
    main()
