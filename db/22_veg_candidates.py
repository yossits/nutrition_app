# -*- coding: utf-8 -*-
"""
22_veg_candidates.py — the vegetable candidate sheet for block 8י (8י-ד).

READ-ONLY. Opens a READ ONLY transaction as its first statement and rolls back
at the end, exactly as 20_carb_candidates.py does. Nothing is written to the
database; the only output is db/block8_veg_candidates.tsv.

Run.
The DSN is read from .env at the repository root — see db/_env.py.

  python db\\22_veg_candidates.py

Output: db/block8_veg_candidates.tsv — UTF-8, LF, tab-separated, one header
row, one row per sheet item, sorted by family then rank. Committed, like 20's
sheet: it is the sheet the owner reviews in 8י-ה.


WHAT THIS FILE IS

20 has no vegetable branch, and 20 is not modified — the same way 20 left 07
alone. This script COPIES 20's mechanisms (most of which 20 copied from 07) and
applies them to the vegetable families of spec/05-food-db.md §5.5 (families
40–55, decided in 8י-ב). Nothing is imported from 20 or 07. Each copied piece
is marked "copied from 20" at the point of use:

  POOL_SQL                    the candidate pool, unchanged from 20 — kcal
                              present and > 0, no excluded_reason; moisture;
                              p2/p4/p6; servings; v_kcal_outliers; eligible.
  SOURCE_RANK                 ingredient 0 · industry 1 · recipe 2.
  EXCLUDED_P2/P4/P6           the kosher exclusions of §5.5, run before the
                              families (is_excluded, family_of).
  is_dry_form / is_raw_form   the dry? and raw? marks, as 07 defines them.
  is_excluded / family_of     first match wins; exclusions before families.

What is NOT copied, and why:

  CORN_SQL                    every vegetable family is a p4 or p2 test, so
                              there is no name pattern to resolve and no SQL
                              for a caller to run. The 24 corn codes are only
                              an EXCLUSION here, and they are read from the
                              §5.5 row "| 33 |" at import time.
  take_with_cap / the dry band  replaced by the three bands below. There is no
                              dry band: a dry form falls out on carb_g < 15.

The families are not typed into this file. The tests, the quotas and the
"במאגר" counts are parsed from the §5.5 vegetable table at import time, so the
spec and the sheet cannot drift apart silently; only the English labels, which
11 and 15 use as dict keys, live here.


THE EXCLUSIONS AND THE ENTRANCE TEST

Before the families, the rows the existing §5.5 families already claim:
p2 71 (31 potatoes) · p4 7340 (32 sweet potato) · the 24 corn codes (33) ·
p6 755100/755101/755102 (4 olives) · p2 62/63 (38 fruit, #23).
Then the entrance test — a ceiling, not a floor (decisions.md, 13.09.2026):
carb_g < 15 AND kcal IS NOT NULL AND kcal <= 80 AND fat_g <= 2.


THE BANDS

Per family with a non-zero quota, in this order:
  band 1  non-recipe rows, at most 1 per p6, by the ranking
  band 2  non-recipe rows, no cap, by the ranking, until the quota fills
  band 3  recipes, by the ranking, only if the quota is still unfilled
The p6 cap lives inside band 1 only. In 8פ-ג2 the p4 cap crossed the dry band
and pulled three uncooked pastas above 77 wet rows; recipe is a hard band here
for the same reason. The ranking inside a band:
(outlier, kcal, src_rank, servings_gate, source_code).

raw? marks and does not sink: a fresh vegetable is a fully eaten form (§5.0.2).
It is in the TSV for the review and nowhere in sort_key or the bands.
"""

import csv
import hashlib
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
        out.append((int(number), t.group(1), codes, int(quota.strip("* ")), int(in_db)))
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
               "fiber?", "outlier?", "eligible", "has_serving", "band", "rank"]


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


def sort_key(row):
    """Rank inside a band. raw? is deliberately absent — it marks, it does not sink."""
    return (
        1 if row["is_outlier"] else 0,          # Atwater outliers sink, they do not drop
        float(row["kcal"]),                     # the plain form before the dressed one
        SOURCE_RANK.get(row["source"], 3),      # ingredient before industry
        0 if row["servings"] > 0 else 1,        # a human serving unit first
        int(row["source_code"]),
    )


def take_bands(rows, quota):
    """rows in any order -> [(row, band), ...], at most `quota` long.

    band 1  non-recipe, first row of each p6, by rank
    band 2  non-recipe rows band 1 did not take, by rank
    band 3  recipes, by rank
    The p6 cap is local to band 1; bands 2 and 3 never read it.
    """
    ranked = sorted(rows, key=sort_key)
    plain = [r for r in ranked if not is_recipe(r)]
    recipes = [r for r in ranked if is_recipe(r)]

    taken, seen_p6, taken_codes = [], set(), set()
    for row in plain:
        if len(taken) >= quota:
            break
        if row["p6"] not in seen_p6:
            seen_p6.add(row["p6"])
            taken.append((row, 1))
            taken_codes.add(row["source_code"])
    for row in plain:
        if len(taken) >= quota:
            break
        if row["source_code"] not in taken_codes:
            taken.append((row, 2))
            taken_codes.add(row["source_code"])
    for row in recipes:
        if len(taken) >= quota:
            break
        taken.append((row, 3))
    return taken


# copied from 20 (is_dry_form) — the powder exemption is kept as written; no
# vegetable family is "protein powders", so it never fires here
def is_dry_form(row, family):
    if family == "protein powders":
        return False
    if row["moisture"] is None or float(row["moisture"]) >= DRY_MOISTURE_MAX:
        return False
    name = " ".join(str(row["name_he"]).split())
    return bool(DRY_NAME.search(name)) and not DRY_NAME_VETO.search(name)


# copied from 20 (is_raw_form) — only the "לא מבושל" marker can fire here; the
# fresh/frozen markers are limited to the animal families, as in 07
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
    """Pool rows -> (sheet, passing, n_excluded_total, n_excluded_veg).

    sheet    {family_number: [(row, band), ...]} in take order
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
        sheet[number] = take_bands(by_family.get(number, []), quota)
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
                "fat_g": num(r["fat_g"], 1),
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
    print("VEG CANDIDATES — block 8י, families 40–55 of §5.5. READ-ONLY: nothing was written to the database.")
    print(f"candidate pool {len(pool)} · kosher exclusions {n_excl_total} pool-wide, "
          f"{n_excl_veg} in veg families · food_curation {curation_before} before, {curation_after} after")
    print(f"corn (33) exclusion set read from §5.5 row 33: n={len(CORN_CODES)} · "
          f"entrance test: {describe_veg_floors(40)}")
    print()
    print("family | label | quota | passing | spec במאגר | band1 | band2 | band3 | in sheet | dry? | raw? | fiber? | outlier? | eligible today")
    total, stops, shortfalls, moved = 0, [], [], []
    for number, label, quota, _match, _floors in FAMILIES:
        taken = sheet.get(number, [])
        n_pass = passing.get(number, 0)
        b = [sum(1 for _r, band in taken if band == k) for k in (1, 2, 3)]
        n_sheet = len(taken)
        n_dry = sum(1 for r, _b in taken if is_dry_form(r, label))
        n_raw = sum(1 for r, _b in taken if is_raw_form(r, label))
        n_fib = sum(1 for r, _b in taken if r["fiber_g"] is None)
        n_out = sum(1 for r, _b in taken if r["is_outlier"])
        n_eli = sum(1 for r, _b in taken if r["eligible"])
        total += n_sheet
        note = ""
        if n_pass != IN_DB_SPEC[number]:
            moved.append((number, IN_DB_SPEC[number], n_pass))
            note += f"   MOVED from spec {IN_DB_SPEC[number]}"
        if quota and n_sheet < quota:
            shortfalls.append((number, quota, n_sheet))
            note += f"   SHORTFALL {quota - n_sheet}"
        print(f"{number} | {label} | {quota} | {n_pass} | {IN_DB_SPEC[number]} | {b[0]} | {b[1]} | {b[2]} | "
              f"{n_sheet} | {n_dry} | {n_raw} | {n_fib} | {n_out} | {n_eli}{note}")
        # S4: a recipe in the sheet means every non-recipe row was taken first
        if b[2]:
            plain = [r for r in by_family.get(number, []) if not is_recipe(r)]
            taken_codes = {r["source_code"] for r, _b in taken}
            left = [r for r in plain if r["source_code"] not in taken_codes]
            if left:
                stops.append((number, left))
        # the quota fills exactly when there is enough
        assert n_sheet == min(quota, n_pass), f"family {number}: {n_sheet} in sheet, quota {quota}, passing {n_pass}"

    print(f"\ntotal in sheet: {total} (TSV rows written: {len(rows_out)})")
    assert total == len(rows_out)
    print("moved from the spec's במאגר column: " + (", ".join(f"{n}: {a} -> {b}" for n, a, b in moved) or "none"))
    print("S3 quota shortfalls: " + (", ".join(f"{n}: quota {q}, in sheet {s}, short {q - s}" for n, q, s in shortfalls) or "none"))
    if stops:
        for number, left in stops:
            print(f"STOP (S4): family {number} took a recipe while {len(left)} non-recipe rows were left: "
                  + ", ".join(f"{r['source_code']} {sort_key(r)}" for r in left))
        sys.exit(4)
    print("S4 OK: no family took a recipe while a non-recipe row was left")
    if curation_before != curation_after:
        print(f"STOP (S5): food_curation moved {curation_before} -> {curation_after}")
        sys.exit(5)
    print(f"S5 OK: food_curation {curation_before} before, {curation_after} after")
    raw = OUT_PATH.read_bytes()
    n_lines = raw.count(b"\n")
    print(f"TSV: {OUT_PATH} · {len(raw)} bytes · {n_lines} lines · sha256 {hashlib.sha256(raw).hexdigest()}")


if __name__ == "__main__":
    main()
