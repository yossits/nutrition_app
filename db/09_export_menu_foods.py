# -*- coding: utf-8 -*-
"""
09_export_menu_foods.py — the bridge from the production database to the spike.

Reads v_menu_foods (foods JOIN food_curation WHERE menu_eligible) together with
food_servings, and writes a Python module in the record shape spike/filters.py
and spike/portions.py already consume. Read-only against the database: it opens
a read-only transaction and writes nothing but the output file.

  python db\\09_export_menu_foods.py                 # → spike/menu_foods.py
  python db\\09_export_menu_foods.py --out other.py
  python db\\09_export_menu_foods.py --dry-run       # print, write nothing

The DSN comes from .env at the repository root — see db/_env.py.

This is NOT spike/foods.py. That file is the 63-item seed written by hand during
stage A; it is not generated and must not be regenerated. Its docstring says so.
The seed remains the default path through run_spike.py; this export is the
second path, selected with --source db.

What the export decides, and what it must not
---------------------------------------------
Curation fields — by_weight, whole_only, max_g, prep, price, quality, category,
kosher, allergens, tags, supp — are read from food_curation as they are. They
are human judgements and deriving them here would be inventing tagging.

Exactly one thing is computed: WHICH serving unit becomes the menu unit. The
source gives 2.35 serving units per item on average and does not mark any of
them as the portion, while the spike's UNIT is one unit per item. That choice is
computed on every run and stored nowhere — food_servings is rebuilt by
TRUNCATE ... CASCADE on every import, so a flag written into it by hand would be
erased, which is the bug db/06_split_curation.sql closed. Decided 29.08.2026;
see docs/decisions.md and docs/spec/05-food-db.md §5.0.3.

The name written into the record is the full name_he. No display-name column, no
truncation at the first comma: 3,677 of 4,624 names contain one, and cutting
there turns "עדשים יבשים, מבושלים ללא מלח" into "עדשים יבשים" — the opposite
meaning, on exactly the item block 3b caught.
"""

import argparse
import importlib.util
import io
import sys
from pathlib import Path

try:
    import psycopg
except ImportError:
    sys.exit("psycopg is missing. Run:  pip install \"psycopg[binary]\"")

from _env import load_database_url, mask_dsn

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).parent
DEFAULT_OUT = HERE.parent / "spike" / "menu_foods.py"

# ---------------------------------------------------------------------------
#  The menu-unit table — mida_code → (family rank, reason it is not a menu unit)
#
#  One row per code, 88 of them, the same 88 as MIDA in 04_transform.py. That
#  file owns what a unit is CALLED; this one owns whether it may be a MENU unit
#  and where it sits in the ranking. A reason of None means eligible.
#
#  This table replaces the code-range test that stood here first. The ranges got
#  the answer wrong in a way a range always will: 906 (קופסה) and 905 (אריזה
#  אישית) fall inside the 900s, which the range read as packaging, but a tin of
#  tuna IS the portion. Without them item 1360 (דג טונה, משומר במים) keeps only
#  כפית=7 and כף=21, the ranking drops to the spoon families, and a 130 g
#  serving gets phrased "6 כפות טונה" — spike bug #5, rebuilt. There is no
#  second range test anywhere in this file: two answers to one question is what
#  the table exists to prevent.
#
#  The four 1200s codes marked "תואר" are adjectives with no noun — 1232
#  (קטן ללא עצם), 1235, 1236, 1237. They sit on cooked pond fish, and for trout
#  10137 the rows are 1229=113 · 1230=170 · 1231=255 · 1232=82: the within-family
#  tie-break takes the smallest, so "קטן ללא עצם" would win and the menu would
#  read "2 קטנים ללא עצם".
#
#  Ranking, first family with a surviving row wins:
#     1 יחידה · 2 פרוסה · 3 גביע · 4 קופסה · 5 אריזה אישית · 6 צורה טבעית
#     7 כוס · 8 מנה · 9 צלחת/קערית · 10 כף · 11 כפית
#
#  קופסה sits at 4 and אריזה אישית at 5, immediately after גביע, because a tin
#  is the same kind of object as a tub: a single-serve retail container that is
#  itself the portion. קופסה ranks ABOVE אריזה אישית because when an item has
#  both, the tin is the ordinary portion and the personal pack is the snack
#  version — 130 g against 80 g on tuna 1360. Ranking them together would send
#  them through the within-family tie-break, which prefers the smaller grams and
#  would return 80 g.
MENU_UNIT = {
    # 1 · יחידה — a whole item
    "100":  (1, None),  "101":  (1, None),  "102":  (1, None),
    "103":  (1, None),  "104":  (1, None),  "105":  (1, None),
    # 2 · פרוסה
    "500":  (2, None),  "501":  (2, None),  "502":  (2, None),  "503":  (2, None),
    # 3 · גביע
    "600":  (3, None),  "601":  (3, None),  "602":  (3, None),
    "603":  (3, None),  "604":  (3, None),  "605":  (3, None),
    # 4 · קופסה — a tin is the portion
    "906":  (4, None),
    # 5 · אריזה אישית — the single-serve pack
    "905":  (5, None),
    # 6 · צורה טבעית — a leaf, a floret, a stalk, a fillet
    "1201": (6, None),  "1202": (6, None),  "1203": (6, None),  "1204": (6, None),
    "1205": (6, None),  "1206": (6, None),  "1207": (6, None),  "1208": (6, None),
    "1209": (6, None),  "1212": (6, None),  "1213": (6, None),  "1214": (6, None),
    "1215": (6, None),  "1217": (6, None),  "1229": (6, None),  "1230": (6, None),
    "1231": (6, None),
    # 7 · כוס
    "200":  (7, None),  "201":  (7, None),  "202":  (7, None),  "203":  (7, None),
    "204":  (7, None),  "205":  (7, None),  "206":  (7, None),  "207":  (7, None),
    "208":  (7, None),  "209":  (7, None),
    # 8 · מנה
    "800":  (8, None),  "801":  (8, None),  "802":  (8, None),  "803":  (8, None),
    # 9 · צלחת / קערית
    "1001": (9, None),  "1002": (9, None),  "1003": (9, None),  "1004": (9, None),
    "1005": (9, None),  "1006": (9, None),  "1007": (9, None),
    # 10 · כף
    "300":  (10, None), "301":  (10, None), "302":  (10, None),
    "307":  (10, None), "308":  (10, None),
    # 11 · כפית
    "400":  (11, None), "401":  (11, None), "402":  (11, None),

    # ---- not menu units -------------------------------------------------
    "900":  (None, "אריזה"),   "901":  (None, "אריזה"),   "902":  (None, "אריזה"),
    "903":  (None, "אריזה"),   "904":  (None, "אריזה"),   "907":  (None, "אריזה"),
    "908":  (None, "אריזה"),   "909":  (None, "אריזה"),   "910":  (None, "אריזה"),
    "911":  (None, "אריזה"),   "912":  (None, "אריזה"),
    "1100": (None, "מכל"),     "1101": (None, "מכל"),     "1102": (None, "מכל"),
    "1103": (None, "מכל"),     "1104": (None, "מכל"),     "1106": (None, "מכל"),
    "1210": (None, "תוסף"),    "1211": (None, "מעורפל"),  "1216": (None, "תיבול"),
    "1232": (None, "תואר"),    "1235": (None, "תואר"),
    "1236": (None, "תואר"),    "1237": (None, "תואר"),
}

SPOON_RANKS = (10, 11)          # כף and כפית — measuring spoons, not portions

# The unmarked size inside a family, preferred first: the source reached for it
# when it had no reason to distinguish. Then the medium, then the smallest in
# grams — smaller is the safer error while max_g is still unset.
MEDIUM_CODES = ("103", "502", "603", "802", "1002")

# Plausibility band on a serving, in grams.
#   floor 2  — below it are only טיפה (0.03 g) and טבליה (0.08 g) and a handful
#              of spice spoons; 114 rows of 9,864.
#   ceiling 400 — measured, not chosen: the largest plain כוס in the whole file
#              is 384 g. The band therefore admits every household measure that
#              exists and cuts only the tail of containers and whole produce.
GRAMS_MIN, GRAMS_MAX = 2.0, 400.0

# Energy ceiling on one serving. A single component of a single meal cannot
# carry 600 kcal. Without this, olive oil 4443 (כפית=3 · כף=10 · כוס=216) is
# given כוס — 1,944 kcal — because כוס outranks כף. With it the cup is dropped
# and כף=10 wins. Measured over the whole database: it moves 139 choices.
KCAL_MAX_PER_SERVING = 600.0

# Explicit overrides, source_code → mida_code, in the CARB_ZERO_BY_JUDGEMENT
# pattern: each entry is a signed judgement about one item and it bypasses the
# rule entirely, band and ranking included.
#
# Deliberately empty. Every entry would be a decision about a particular food,
# and that is curation — block 3d, not this bridge. The place to add one is the
# moment the rule is seen to fail on a curated item.
UNIT_BY_JUDGEMENT = {}


def _mida_codes():
    """The unit codes 04_transform.py writes. Loaded by path — the module name
    starts with a digit, so a plain import cannot reach it."""
    spec = importlib.util.spec_from_file_location(
        "transform_mida", HERE / "04_transform.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return set(module.MIDA)


def check_tables_agree():
    """Both halves of the unit table must cover the same 88 codes.

    04_transform.py owns what a unit is called; this file owns whether it may be
    a menu unit. The split is deliberate, but it only holds while the two agree
    on which codes exist: a code added there and forgotten here would get no
    rank, read as not-a-menu-unit, and vanish from every menu without a word.
    """
    mida, menu = _mida_codes(), set(MENU_UNIT)
    if mida == menu:
        return
    missing = sorted(mida - menu, key=int)
    extra = sorted(menu - mida, key=int)
    sys.exit(
        "MIDA in 04_transform.py and MENU_UNIT here describe different code "
        "sets.\n"
        f"  in MIDA, no rank here: {missing or '—'}\n"
        f"  ranked here, not in MIDA: {extra or '—'}\n"
        "Every code needs both a label and a menu-eligibility ruling.")


def choose_unit(rows, kcal_per_100g, source_code):
    """Pick the menu unit for one item. Returns a serving row, or None.

    rows: [(mida_code, label_he, label_he_plural, grams), ...] — every serving
    the source gives this item, nothing filtered yet.

    None means the item is exported by weight, in grams. That is a legitimate
    outcome and not a failure: 428 items carry no serving unit at all, and a
    further 200 carry only containers.
    """
    override = UNIT_BY_JUDGEMENT.get(source_code)
    if override:
        for row in rows:
            if row[0] == override:
                return row
        raise SystemExit(
            f"UNIT_BY_JUDGEMENT names mida_code {override} for {source_code}, "
            f"which has no such serving row. Fix the override or drop it.")

    def rank(row):
        return MENU_UNIT.get(row[0], (None, None))[0]

    eligible = [r for r in rows if rank(r) is not None]

    def within_grams(row):
        return GRAMS_MIN <= float(row[3]) <= GRAMS_MAX

    def within_energy(row):
        if kcal_per_100g is None:
            return True
        return kcal_per_100g * float(row[3]) / 100.0 <= KCAL_MAX_PER_SERVING

    surviving = [r for r in eligible if within_grams(r) and within_energy(r)]
    if not surviving:
        return None

    def sort_key(row):
        code = row[0]
        return (rank(row),
                0 if code.endswith("00") else 1,
                0 if code in MEDIUM_CODES else 1,
                float(row[3]),
                code)

    winner = min(surviving, key=sort_key)

    # The measuring-spoon guard, and the one place where WHICH band rejected a
    # row matters.
    #
    # A spoon winning is right for items that have nothing else — oils, spreads,
    # powders. It is wrong when the item has a real portion that we rejected for
    # being too many grams: yogurt 45 offers גביע גדול=500, out of the band, and
    # would otherwise be served as כף=20, i.e. "12 כפות יוגורט".
    #
    # But rejection by the ENERGY ceiling means the opposite. Olive oil 4443
    # offers כפית=3 · כף=10 · כוס=216, and the cup is dropped at 1,944 kcal —
    # which says the food is concentrated, not that its spoon is a measuring
    # instrument. A tablespoon of oil IS the serving. Sending it to grams
    # instead hands the solver a 30–400 g range with no max_g on it, and 400 g
    # of olive oil is the same bug as 400 g of avocado.
    #
    # So the guard fires on the grams band only.
    if rank(winner) in SPOON_RANKS:
        lost_a_real_portion = any(rank(r) not in SPOON_RANKS and not within_grams(r)
                                  for r in eligible)
        if lost_a_real_portion:
            return None
    return winner


SQL_FOODS = """
    SELECT source_code, name_he, category::text, kcal, protein_g, fat_g, carb_g,
           kosher::text, allergens, tags, quality, supp, prep, price, complete,
           by_weight, whole_only, max_g
    FROM v_menu_foods
    ORDER BY source_code::int
"""

SQL_SERVINGS = """
    SELECT f.source_code, s.mida_code, s.label_he, s.label_he_plural, s.grams
    FROM food_servings s
    JOIN foods f ON f.id = s.food_id
    WHERE f.source_code = ANY(%s)
    ORDER BY f.source_code, s.grams
"""


def num(value, digits=1):
    """Decimal → float, rounded. The source stores float32 artefacts such as
    2.400000095367432; carrying them into a generated file is noise."""
    return None if value is None else round(float(value), digits)


def build_records(foods, servings_by_code):
    records, problems = [], []
    for i, row in enumerate(foods, 1):
        (source_code, name_he, category, kcal, protein, fat, carb, kosher,
         allergens, tags, quality, supp, prep, price, complete,
         by_weight, whole_only, max_g) = row

        # Refusing, not filling in. An exported record with a hole in it fails
        # somewhere downstream instead of here, and the message it fails with
        # names neither the item nor the field: prep = NULL surfaces as
        # "TypeError: '>' not supported between NoneType and int" inside
        # filters.eligible(), five frames from anything a reader can act on.
        #
        # Note that the schema permits both of these on a menu_eligible row.
        # eligible_requires_safety_tagging covers category, kosher and the
        # allergen review; prep and price are not in it. That is a gap in the
        # constraint, not in this file, and closing it is a schema decision.
        gaps = [field for field, value in
                (("kcal", kcal), ("prep", prep), ("price", price))
                if value is None]
        if gaps:
            problems.append(f"{source_code} | {name_he} | NULL: {', '.join(gaps)}")
            continue

        rows = servings_by_code.get(source_code, [])
        unit_row = choose_unit(rows, float(kcal), source_code)

        # Only the servings that may be menu units reach the prompt; a bottle
        # printed next to a tin invites the model to reason about the bottle.
        menu_rows = [r for r in rows if MENU_UNIT.get(r[0], (None, None))[0] is not None]

        records.append(dict(
            name=name_he,                    # full name_he — decided 29.08.2026
            he=name_he,
            cat=category,
            kcal=num(kcal), protein=num(protein), fat=num(fat), carb=num(carb),
            kosher=kosher,
            servings=[(r[2], num(r[3])) for r in menu_rows],
            allergens=set(allergens or ()),
            tags=set(tags or ()),
            prep=prep, price=price,
            complete=bool(complete), supp=bool(supp), quality=quality,
            unit=(None if unit_row is None else
                  {"he": unit_row[1], "he_plural": unit_row[2],
                   "grams": num(unit_row[3])}),
            by_weight=bool(by_weight),       # curation, read as-is
            whole_only=bool(whole_only),     # curation, read as-is
            max_g=num(max_g),                # curation, read as-is
            id=i,
            menu_eligible=True,              # v_menu_foods filters on it
            source_code=source_code,
        ))
    return records, problems


def render(records):
    def lit(value):
        if isinstance(value, set):
            return "set()" if not value else "{" + ", ".join(repr(v) for v in sorted(value)) + "}"
        return repr(value)

    out = io.StringIO()
    out.write('# -*- coding: utf-8 -*-\n')
    out.write('"""GENERATED by db/09_export_menu_foods.py from v_menu_foods.\n\n')
    out.write("Do not edit. Re-run the exporter; every hand edit is lost and,\n")
    out.write("worse, disagrees with the database while looking authoritative.\n")
    out.write("Values are per 100 g. kcal is foods.kcal, derived from the macros —\n")
    out.write('not kcal_source, the value declared in the source file.\n"""\n\n')
    out.write(f"FOODS = [\n")
    for r in records:
        out.write("    {\n")
        for key, value in r.items():
            out.write(f"        {key!r}: {lit(value)},\n")
        out.write("    },\n")
    out.write("]\n\n")
    allergens = sorted({a for r in records for a in r["allergens"]})
    out.write(f"ALL_ALLERGENS = {allergens!r}\n")
    return out.getvalue()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    check_tables_agree()

    url = load_database_url()
    try:
        conn_ctx = psycopg.connect(url)
    except psycopg.OperationalError as exc:
        sys.exit(f"Cannot connect to {mask_dsn(url)}\n{exc}")

    with conn_ctx as conn:
        conn.read_only = True
        with conn.cursor() as cur:
            cur.execute(SQL_FOODS)
            foods = cur.fetchall()
            codes = [r[0] for r in foods]
            servings_by_code = {}
            if codes:
                cur.execute(SQL_SERVINGS, (codes,))
                for source_code, mida_code, label, plural, grams in cur.fetchall():
                    servings_by_code.setdefault(source_code, []).append(
                        (mida_code, label, plural, grams))

    records, problems = build_records(foods, servings_by_code)

    print(f"v_menu_foods: {len(foods)} rows · exported: {len(records)}")
    with_unit = [r for r in records if r["unit"]]
    print(f"with a UNIT: {len(with_unit)} · by grams: {len(records) - len(with_unit)}")
    for r in records:
        unit = (f"{r['unit']['he']} / {r['unit']['he_plural']} = {r['unit']['grams']}g"
                if r["unit"] else "→ by grams")
        print(f"  {r['source_code']:>6}  {r['cat']:<8} {r['name'][:46]:<46} {unit}")
    for p in problems:
        print(f"  SKIPPED  {p}")

    if problems:
        sys.exit(f"\n✘ {len(problems)} menu_eligible items could not be exported: "
                 f"a field the spike reads is NULL. Filling it in here would be "
                 f"inventing curation; it has to be tagged.")

    if args.dry_run:
        print("\n--dry-run: nothing written.")
        return

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render(records), encoding="utf-8")
    print(f"\n✔ Wrote {args.out} — {len(records)} items.")


if __name__ == "__main__":
    main()
