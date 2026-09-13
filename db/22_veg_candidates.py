# -*- coding: utf-8 -*-
"""
22_veg_candidates.py — the vegetable candidate sheet for block 8י (8י-ד, 8י-ד2).

READ-ONLY. Opens a READ ONLY transaction as its first statement and rolls back
at the end, exactly as 20_carb_candidates.py does. Nothing is written to the
database; the only output is db/block8_veg_candidates.tsv.

Run.
The DSN is read from .env at the repository root — see db/_env.py.

  python db\\22_veg_candidates.py

Output: db/block8_veg_candidates.tsv — UTF-8, LF, tab-separated, one header
row, one row per sheet item, sorted by family then p6. Committed, like 20's
sheet: it is the sheet the owner reviews in 8י-ה.


WHAT THIS FILE IS

20 has no vegetable branch, and 20 is not modified — the same way 20 left 07
alone. This script COPIES 20's mechanisms (most of which 20 copied from 07) and
applies them to the vegetable families of spec/05-food-db.md §5.5 (families
40–55, decided in 8י-ב, quota column corrected in 8י-ד2). Nothing is imported
from 20 or 07. Each copied piece is marked "copied from 20" at the point of use:

  POOL_SQL                    the candidate pool, unchanged from 20 — kcal
                              present and > 0, no excluded_reason; moisture;
                              p2/p4/p6; servings; v_kcal_outliers; eligible.
  SOURCE_RANK                 ingredient 0 · industry 1 · recipe 2.
  EXCLUDED_P2/P4/P6           the kosher exclusions of §5.5, run before the
                              families (is_excluded, family_of).
  is_dry_form / is_raw_form   the dry? and raw? marks; raw? extended for veg.
  is_excluded / family_of     first match wins; exclusions before families.

What is NOT copied, and why:

  CORN_SQL                    every vegetable family is a p4 or p2 test, so
                              there is no name pattern to resolve and no SQL
                              for a caller to run. The 24 corn codes are only
                              an EXCLUSION here, and they are read from the
                              §5.5 row "| 33 |" at import time.
  quotas, caps and bands      replaced by coverage, below.

The families are not typed into this file. The tests, the quota column and the
"במאגר" counts are parsed from the §5.5 vegetable table at import time, so the
spec and the sheet cannot drift apart silently; only the English labels, which
11 and 15 use as dict keys, live here.


THE EXCLUSIONS AND THE ENTRANCE TEST

Before the families, the rows the existing §5.5 families already claim:
p2 71 (31 potatoes) · p4 7340 (32 sweet potato) · the 24 corn codes (33) ·
p6 755100/755101/755102 (4 olives) · p2 62/63 (38 fruit, #23).
Then the entrance test — a ceiling, not a floor (decisions.md, 13.09.2026):
carb_g < 15 AND kcal IS NOT NULL AND kcal <= 80 AND fat_g <= 2.


COVERAGE, NOT A QUOTA (8י-ד2)

The first sheet (111075f) ranked each family by kcal ascending and cut it at a
quota. It came out as a mechanism: kcal ascending measures water, not staples —
family 40 cut at 25.2 and 43 at 27.1, every pea form fell below the cut, and two
of the four eligible vegetables lost their p6 to near twins. There is no column
in the database that measures a household staple, so the quota is replaced by
coverage: in every family whose §5.5 quota reads "כל p6", each p6 present after
the exclusions and the entrance test contributes exactly one row. No ceiling, no
second band, no cut. Quota-0 families take nothing and are still counted.

The single row of a p6 is chosen by
(NOT eligible, recipe, outlier, NOT has_serving, kcal, src_rank, servings_gate, source_code).
An eligible item is the form already judged, so a near twin cannot displace it;
a row with no serving line cannot win its p6 on being the wateriest; and kcal
ranks the plain form before the seasoned one inside the p6, where that is what
it means. The order of the p6 winners in the sheet is by p6 code and selects
nothing.

raw? marks and does not sink: a fresh vegetable is a fully eaten form (§5.0.2).
In the veg families it fires on the whole word טרי and on חי/חיים as whole
words. It is in the TSV for the review and nowhere in the key or the selection.
"""

import csv
import hashlib
import math
import re
import sys
from pathlib import Path

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:
    sys.exit("psycopg is missing. Run:  pip install \"psycopg[binary]\"")

# sys.path[0] is db/ when this is run as `python db/22_veg_candidates.py`.
from _env import load_database_url, mask_dsn

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).parent
OUT_PATH = HERE / "block8_veg_candidates.tsv"
SPEC_PATH = HERE.parent / "docs" / "spec" / "05-food-db.md"

# ---------------------------------------------------------------------------
# copied from 20 — the dry-form flag (DRY_MOISTURE_MAX, DRY_NAME, DRY_NAME_VETO)
DRY_MOISTURE_MAX = 20                                    # g water per 100 g
DRY_NAME = re.compile(r"יבש|מיובש|אבק|(?<!מ)קמח")
DRY_NAME_VETO = re.compile(r"(קליה|קלייה|צליה|צלייה|אפיה|אפייה|בישול)\s+יבש")

# copied from 20 — the raw-form flag (#28, 3ו2ד)
RAW_NAME = re.compile(r"(?<!\w)לא מבושל")
RAW_FRESH = re.compile(r"(?<!\w)טרי(?!\w)")
RAW_FROZEN = re.compile(r"קפוא")
RAW_FROZEN_VETO = re.compile(r"מבושל")
RAW_ANIMAL_FAMILIES = {"poultry", "fish & seafood", "beef, veal & lamb"}

# 8י-ד2: in the veg families raw? also fires on טרי (RAW_FRESH above, as 07
# writes it) and on חי / חיים as whole words. It marks only.
RAW_ALIVE = re.compile(r"(?<!\w)(?:חי|חיים)(?!\w)")
# Printed beside the count, never used for the flag: the same word with only
# the left-hand guard, which also catches טריה · טריים · טריות.
RAW_FRESH_LEFT_ONLY = re.compile(r"(?<!\w)טרי")

# copied from 20 — kosher exclusions of §5.5
EXCLUDED_P2 = {"22"}                                   # pork
EXCLUDED_P4 = {"2620", "2621", "2630", "2631",         # octopus · squid · crab · shellfish
               "2331"}                                 # rabbit
EXCLUDED_P6 = {"812020"}                               # rendered pork fat

# copied from 20 (itself copied from 07, plus the eligible column), unchanged
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

# copied from 20
SOURCE_RANK = {"ingredient": 0, "industry": 1, "recipe": 2}


# ---------------------------------------------------------------------------
#  The spec is the source. Parsed once, at import, so a caller loading this
#  module by path (15 in 8י-ו) gets the same families the sheet uses.
# ---------------------------------------------------------------------------
def _spec_lines():
    return SPEC_PATH.read_bytes().decode("utf-8").replace("\r", "").split("\n")


def _corn_codes(lines):
    """The 24 source_codes of carb family 33, from the §5.5 row '| 33 |'."""
    rows = [l for l in lines if l.startswith("| 33 |")]
    if len(rows) != 1:
        raise SystemExit(f"§5.5: {len(rows)} rows start with '| 33 |', expected 1")
    m = re.search(r"`source_code` ∈ \{([0-9, ]+)\}", rows[0])
    codes = {c.strip() for c in m.group(1).split(",")} if m else set()
    if len(codes) != 24:
        raise SystemExit(f"§5.5 row 33: {len(codes)} corn codes parsed, expected 24")
    return codes


VEG_HEADING = "#### ירק"
TEST_RE = re.compile(r"^(p2|p4|p6) (?:=|∈) (?:\{(?P<set>[^}]*)\}|`(?P<one>\d+)`)(?: - .*)?$")

# A family whose §5.5 quota reads "כל p6" takes one row per p6, with no ceiling.
# inf rather than a string, so `quota > 0` and `quota == 0` read the way they do
# for 20's numeric quotas wherever a caller filters on them.
ALL_P6 = math.inf
QUOTA_ALL_P6 = "כל p6"


def _quota(cell, number):
    cell = cell.strip()
    if cell == QUOTA_ALL_P6:
        return ALL_P6
    if cell.strip("*") == "0":
        return 0
    raise SystemExit(f"§5.5 family {number}: quota {cell!r} is neither {QUOTA_ALL_P6!r} nor 0")


def _veg_table(lines):
    """[(number, level, codes, quota, in_db), ...] from the §5.5 vegetable table."""
    heads = [i for i, l in enumerate(lines) if l.startswith(VEG_HEADING)]
    if len(heads) != 1:
        raise SystemExit(f"§5.5: {len(heads)} headings start with {VEG_HEADING!r}, expected 1")
    out = []
    for line in lines[heads[0] + 1:]:
        if line.startswith("#### "):
            break
        m = re.match(r"^\| (\d+) \| (.+?) \| (.+?) \| (.+?) \| (.+?) \|$", line)
        if not m:
            continue
        number, test, _name, quota, in_db = m.groups()
        t = TEST_RE.match(test.strip())
        if not t:
            raise SystemExit(f"§5.5 family {number}: cannot read the test {test!r}")
        codes = (set(re.findall(r"`(\d+)`", t.group("set"))) if t.group("set") is not None
                 else {t.group("one")})
        out.append((int(number), t.group(1), codes, _quota(quota, number), int(in_db)))
    return out


# English labels — 11 and 15 key their per-family dicts on the label, so these
# must not collide with 07's fat/protein labels or 20's carb labels. 07 already
# owns "pickled vegetables" (fat family 14), hence the veg-prefixed 52.
VEG_LABEL_EN = {
    40: "fresh vegetables",
    41: "leafy greens",
    42: "broccoli",
    43: "cooked vegetables",
    44: "cooked & frozen vegetable mixes",
    45: "carrot",
    46: "pumpkin & squash",
    47: "tomatoes, fresh & cooked",
    48: "peas & carrots",
    49: "packaged salads",
    50: "tomato juice & puree",
    51: "fried & roasted vegetables",
    52: "veg: pickled vegetables",
    53: "vegetable soups",
    54: "baby purees",
    55: "vegetable remainder",
}

_LINES = _spec_lines()
CORN_CODES = _corn_codes(_LINES)
VEG_TABLE = _veg_table(_LINES)
if [n for n, *_ in VEG_TABLE] != list(range(40, 56)):
    raise SystemExit(f"§5.5 veg families read: {[n for n, *_ in VEG_TABLE]}, expected 40–55 in order")
if set(VEG_LABEL_EN) != {n for n, *_ in VEG_TABLE}:
    raise SystemExit("VEG_LABEL_EN does not cover exactly the §5.5 veg families")

ENTRANCE = {"carb_g_lt": 15, "kcal_le": 80, "fat_g_le": 2}


def _match(level, codes):
    return lambda r: r[level] in codes


# (number, label, quota, match, floors) — 20's row shape. floors is empty: the
# entrance test is one for every vegetable family. Ordered; the FIRST match wins.
FAMILIES = [(n, VEG_LABEL_EN[n], quota, _match(level, codes), {})
            for n, level, codes, quota, _in_db in VEG_TABLE]
IN_DB_SPEC = {n: in_db for n, _l, _c, _q, in_db in VEG_TABLE}
VEG_LABELS = set(VEG_LABEL_EN.values())

# ---- the names 15 imports in 8י-ו, in the shape 15 builds for 20 ------------
VEG_FAMILIES = [(no, label, quota) for no, label, quota, _m, _f in FAMILIES]
VEG_LABEL = {no: label for no, label, _q in VEG_FAMILIES}
# kosher parve for all nine families with a quota; vegan yes for the plain
# vegetables, blank (None) for 43 cooked vegetables and 44 cooked mixes, where
# a dairy or egg component is decided item by item.
VEG_KOSHER = {label: "parve" for no, label, quota in VEG_FAMILIES if quota > 0}
VEG_VEGAN = {label: (None if no in (43, 44) else True)
             for no, label, quota in VEG_FAMILIES if quota > 0}
assert sorted(no for no, _l, q in VEG_FAMILIES if q > 0) == list(range(40, 49))


def floors_for(number):
    """The entrance test, the same for every vegetable family (20's name)."""
    if number not in VEG_LABEL:
        raise KeyError(number)
    return dict(ENTRANCE)


def describe_veg_floors(number):
    """The vegetable family's entrance test, in the shape 15's
    describe_carb_floors prints beside a family."""
    e = floors_for(number)
    return f"carb<{e['carb_g_lt']}, kcal<={e['kcal_le']}, fat<={e['fat_g_le']}"


TSV_COLUMNS = ["family", "p2", "p4", "source_code", "name_he", "source", "kcal",
               "carb_g", "fat_g", "fiber_g", "moisture", "dry?", "raw?",
               "fiber?", "outlier?", "eligible", "has_serving", "p6", "rank"]


# copied from 20
def is_excluded(row):
    """Kosher exclusions. They run before anything else."""
    return (row["p2"] in EXCLUDED_P2
            or row["p4"] in EXCLUDED_P4
            or row["p6"] in EXCLUDED_P6)


def is_claimed(row):
    """Rows an existing §5.5 family already claims: 31 · 32 · 33 · 4 · 38."""
    return (row["p2"] == "71"
            or row["p4"] == "7340"
            or str(row["source_code"]) in CORN_CODES
            or row["p6"] in ("755100", "755101", "755102")
            or row["p2"] in ("62", "63"))


def match_family(row):
    """First matching family regardless of kosher and claims. Order is load-bearing."""
    for number, _label, _quota, match, _floors in FAMILIES:
        if match(row):
            return number
    return None


# copied from 20 (family_of) — exclusions first, then first match wins
def family_of(row):
    if is_excluded(row) or is_claimed(row):
        return None
    return match_family(row)


def passes_entrance(row):
    if row["carb_g"] is None or row["kcal"] is None or row["fat_g"] is None:
        return False
    return (float(row["carb_g"]) < ENTRANCE["carb_g_lt"]
            and float(row["kcal"]) <= ENTRANCE["kcal_le"]
            and float(row["fat_g"]) <= ENTRANCE["fat_g_le"])


def is_recipe(row):
    return row["source"] == "recipe"


def p6_key(row):
    """Choose the one row of a p6. raw? is deliberately absent — it marks, it does not sink."""
    return (
        0 if row["eligible"] else 1,            # the form already judged
        1 if is_recipe(row) else 0,             # a dish below every raw material
        1 if row["is_outlier"] else 0,          # Atwater outliers sink, they do not drop
        0 if row["servings"] > 0 else 1,        # no serving line cannot win on water
        float(row["kcal"]),                     # the plain form before the seasoned one
        SOURCE_RANK.get(row["source"], 3),      # ingredient before industry
        0 if row["servings"] > 0 else 1,        # servings gate, as in 20
        int(row["source_code"]),
    )


def take_p6(rows):
    """rows of one family -> one row per p6, the winner by p6_key, in p6 order."""
    by_p6 = {}
    for row in rows:
        by_p6.setdefault(row["p6"], []).append(row)
    return [min(group, key=p6_key) for _p6, group in sorted(by_p6.items())]


# copied from 20 (is_dry_form) — the powder exemption is kept as written; no
# vegetable family is "protein powders", so it never fires here
def is_dry_form(row, family):
    if family == "protein powders":
        return False
    if row["moisture"] is None or float(row["moisture"]) >= DRY_MOISTURE_MAX:
        return False
    name = " ".join(str(row["name_he"]).split())
    return bool(DRY_NAME.search(name)) and not DRY_NAME_VETO.search(name)


# copied from 20 (is_raw_form), with the veg branch of 8י-ד2
def is_raw_form(row, family):
    name = " ".join(str(row["name_he"]).split())
    if family != "protein powders" and RAW_NAME.search(name):
        return True
    if family in VEG_LABELS:
        return bool(RAW_FRESH.search(name) or RAW_ALIVE.search(name))
    if family not in RAW_ANIMAL_FAMILIES:
        return False
    if RAW_FRESH.search(name):
        return True
    return bool(RAW_FROZEN.search(name)) and not RAW_FROZEN_VETO.search(name)


def select_candidates(pool):
    """Pool rows -> (sheet, passing, by_family, n_excluded_total, n_excluded_veg).

    sheet    {family_number: [row, ...]} one per p6, in p6 order
    passing  {family_number: n rows past the entrance test (exclusions applied)}
    """
    by_family, passing = {}, {}
    n_excluded_total = n_excluded_veg = 0
    for row in pool:
        if is_excluded(row):
            n_excluded_total += 1
            if not is_claimed(row) and match_family(row) is not None:
                n_excluded_veg += 1
            continue
        number = family_of(row)
        if number is None or not passes_entrance(row):
            continue
        passing[number] = passing.get(number, 0) + 1
        by_family.setdefault(number, []).append(row)

    sheet = {}
    for number, _label, quota, _match, _floors in FAMILIES:
        if quota == 0:
            continue
        sheet[number] = take_p6(by_family.get(number, []))
    return sheet, passing, by_family, n_excluded_total, n_excluded_veg


def num(value, digits):
    if value is None:
        return ""
    return f"{float(value):.{digits}f}"


def main():
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
            cur.execute(POOL_SQL)
            pool = cur.fetchall()
            cur.execute("SELECT count(*) AS n FROM food_curation")
            curation_after = cur.fetchone()["n"]
        conn.rollback()

    sheet, passing, by_family, n_excl_total, n_excl_veg = select_candidates(pool)

    # ---- the TSV -----------------------------------------------------------
    rows_out = []
    for number, label, quota, _match, _floors in FAMILIES:
        for rank, r in enumerate(sheet.get(number, []), 1):
            rows_out.append({
                "family": number,
                "p2": r["p2"],
                "p4": r["p4"],
                "source_code": r["source_code"],
                "name_he": " ".join(str(r["name_he"]).split()),
                "source": r["source"],
                "kcal": num(r["kcal"], 1),
                "carb_g": num(r["carb_g"], 1),
                "fat_g": num(r["fat_g"], 1),
                "fiber_g": num(r["fiber_g"], 1),
                "moisture": num(r["moisture"], 1),
                "dry?": 1 if is_dry_form(r, label) else 0,
                "raw?": 1 if is_raw_form(r, label) else 0,
                "fiber?": 1 if r["fiber_g"] is None else 0,
                "outlier?": 1 if r["is_outlier"] else 0,
                "eligible": 1 if r["eligible"] else 0,
                "has_serving": 1 if r["servings"] > 0 else 0,
                "p6": r["p6"],
                "rank": rank,
            })
    with open(OUT_PATH, "w", encoding="utf-8", newline="\n") as fh:
        writer = csv.DictWriter(fh, fieldnames=TSV_COLUMNS, delimiter="\t",
                                lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows_out)

    # ---- the summary -------------------------------------------------------
    print("VEG CANDIDATES — block 8י, families 40–55 of §5.5, one row per p6. READ-ONLY: nothing was written to the database.")
    print(f"candidate pool {len(pool)} · kosher exclusions {n_excl_total} pool-wide, "
          f"{n_excl_veg} in veg families · food_curation {curation_before} before, {curation_after} after")
    print(f"corn (33) exclusion set read from §5.5 row 33: n={len(CORN_CODES)} · "
          f"entrance test: {describe_veg_floors(40)}")
    print()
    print("family | label | quota | passing | spec במאגר | distinct p6 | in sheet | dry? | raw? | fiber? | outlier? | eligible today | kcal > 50 | raw? left-guard-only")
    total, stops = 0, []
    for number, label, quota, _match, _floors in FAMILIES:
        taken = sheet.get(number, [])
        fam_rows = by_family.get(number, [])
        n_p6 = len({r["p6"] for r in fam_rows})
        n_pass = passing.get(number, 0)
        n_sheet = len(taken)
        total += n_sheet
        cells = [
            sum(1 for r in taken if is_dry_form(r, label)),
            sum(1 for r in taken if is_raw_form(r, label)),
            sum(1 for r in taken if r["fiber_g"] is None),
            sum(1 for r in taken if r["is_outlier"]),
            sum(1 for r in taken if r["eligible"]),
            sum(1 for r in taken if float(r["kcal"]) > 50),
            sum(1 for r in taken if RAW_FRESH_LEFT_ONLY.search(" ".join(str(r["name_he"]).split()))
                or RAW_ALIVE.search(" ".join(str(r["name_he"]).split()))
                or RAW_NAME.search(" ".join(str(r["name_he"]).split()))),
        ]
        note = f"   MOVED from spec {IN_DB_SPEC[number]}" if n_pass != IN_DB_SPEC[number] else ""
        q_txt = "all p6" if quota == ALL_P6 else str(quota)
        print(f"{number} | {label} | {q_txt} | {n_pass} | {IN_DB_SPEC[number]} | {n_p6} | {n_sheet} | "
              + " | ".join(str(c) for c in cells) + note)
        # S4: coverage — one row per p6, every p6, no p6 twice
        if quota > 0:
            sheet_p6 = [r["p6"] for r in taken]
            if n_sheet != n_p6 or len(set(sheet_p6)) != len(sheet_p6):
                stops.append(f"S4 family {number}: {n_sheet} rows, {n_p6} distinct p6, "
                             f"{len(sheet_p6) - len(set(sheet_p6))} p6 repeated")
        elif n_sheet:
            stops.append(f"quota-0 family {number} took {n_sheet} rows")

    print(f"\ntotal in sheet: {total} (TSV rows written: {len(rows_out)})")
    assert total == len(rows_out)

    selected = [r for number in sheet for r in sheet[number]]
    selected_codes = {r["source_code"] for r in selected}
    print("\nELIGIBLE TODAY in the veg families (after exclusions and the entrance test):")
    for number in sorted(by_family):
        for r in sorted(by_family[number], key=lambda r: int(r["source_code"])):
            if r["eligible"]:
                print(f"  {r['source_code']} | {' '.join(str(r['name_he']).split())} | family {number} | p6 {r['p6']} | "
                      f"kcal {num(r['kcal'], 1)} | {'WON its p6' if r['source_code'] in selected_codes else 'NOT selected'}")

    print("\nPEA ROWS in the veg families (name carries אפונה), after the entrance test:")
    pea_p6 = {}
    for number in sorted(by_family):
        for r in by_family[number]:
            if "אפונה" in str(r["name_he"]):
                pea_p6.setdefault((number, r["p6"]), []).append(r)
    for (number, p6), rows in sorted(pea_p6.items()):
        winner = next((w for w in sheet.get(number, []) if w["p6"] == p6), None)
        for r in sorted(rows, key=lambda r: int(r["source_code"])):
            print(f"  family {number} | p6 {p6} | {r['source_code']} | {' '.join(str(r['name_he']).split())} | "
                  f"kcal {num(r['kcal'], 1)} | {'WON its p6' if winner is r else 'lost to ' + (winner['source_code'] if winner else 'none')}")

    # S5: the claim of 8י-ב that the first sheet falsified
    over_50 = sum(1 for r in selected if float(r["kcal"]) > 50)
    peas_in = [r for r in selected if "אפונה" in str(r["name_he"])]
    print(f"\nS5: rows with kcal > 50 in the sheet: {over_50} · pea rows in the sheet: {len(peas_in)} "
          f"({', '.join(r['source_code'] for r in peas_in)})")
    if not over_50 or not peas_in:
        for (number, p6), rows in sorted(pea_p6.items()):
            winner = next((w for w in sheet.get(number, []) if w["p6"] == p6), None)
            stops.append(f"S5 pea p6 {p6} (family {number}) won by "
                         f"{winner['source_code'] if winner else 'none'}")
        stops.append("S5 failed: no row above 50 kcal or no pea row selected")

    if stops:
        for s in stops:
            print("STOP:", s)
        sys.exit(4)
    print("S4 OK: every family with a quota has one row per p6, no p6 twice")
    print("S5 OK: a row above 50 kcal and a pea row are in the sheet")
    if curation_before != curation_after:
        print(f"STOP (S6): food_curation moved {curation_before} -> {curation_after}")
        sys.exit(6)
    print(f"S6 OK: food_curation {curation_before} before, {curation_after} after")
    raw = OUT_PATH.read_bytes()
    n_lines = raw.count(b"\n")
    print(f"TSV: {OUT_PATH} · {len(raw)} bytes · {n_lines} lines · sha256 {hashlib.sha256(raw).hexdigest()}")


if __name__ == "__main__":
    main()
