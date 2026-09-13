# -*- coding: utf-8 -*-
"""
_audit_units.py - the menu unit against the curation flags. Read-only.

  python db\\_audit_units.py

Opened in block 8t-alef for open-questions.md #50 and #21. One READ ONLY
transaction, three sections to stdout, nothing written - no file, no row:

  A  whole_only rows whose max_g is not a whole multiple of the menu unit (#50)
  B  rows whose chosen unit is a counted one - MENU_UNIT rank in
     WHOLE_UNIT_RANKS - while whole_only is false (#21)
  C  totals

The unit is not re-derived here. choose_unit(), MENU_UNIT, UNIT_BY_JUDGEMENT and
SQL_SERVINGS come from 09_export_menu_foods.py, WHOLE_UNIT_RANKS from
11_curation_sheet.py, both loaded by path: a second copy of either would be a
second answer to the question they exist to settle.

choose_unit() sees the serving rows only, never by_weight - 09 nulls the unit of
a by_weight row after the call. The unit reported here is the call's result, and
by_weight is printed beside it, so a row the export sends to grams is visible as
such rather than silently dropped.

Every count is returned by SQL. The unit choice is Python, so the resolved unit
of each row goes back into the same transaction as arrays (unnest), and each
count is its own query over those arrays joined to v_menu_foods. The length of
the Python list is printed beside it; a disagreement exits 1.
"""

import importlib.util
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


def load_by_path(name, filename):
    """The module names start with a digit, so a plain import cannot reach them.
    Both keep their entry point behind `if __name__ == "__main__"`."""
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


EXPORT = load_by_path("export_menu_foods", "09_export_menu_foods.py")
SHEET = load_by_path("curation_sheet", "11_curation_sheet.py")

choose_unit = EXPORT.choose_unit
MENU_UNIT = EXPORT.MENU_UNIT
UNIT_BY_JUDGEMENT = EXPORT.UNIT_BY_JUDGEMENT
SQL_SERVINGS = EXPORT.SQL_SERVINGS
WHOLE_UNIT_RANKS = SHEET.WHOLE_UNIT_RANKS

# A ratio within this of an integer counts as a whole number of units.
WHOLE_TOL = 0.001

SQL_ROWS = """
    SELECT source_code, name_he, category::text, kcal, by_weight, whole_only, max_g
    FROM v_menu_foods
    ORDER BY source_code::int
"""

# The resolved unit of every examined row, as parallel arrays.
UNITS = """
    unnest(%(codes)s::text[], %(midas)s::text[], %(grams)s::float8[], %(ranks)s::int[])
        AS u(source_code, mida_code, grams, unit_rank)
    JOIN v_menu_foods m ON m.source_code = u.source_code
"""

NOT_WHOLE = "abs(m.max_g::float8 / u.grams - round(m.max_g::float8 / u.grams)) > %(tol)s"

SQL_A_EXAMINED = f"SELECT count(*) FROM {UNITS} WHERE m.whole_only"
SQL_A_NO_UNIT = f"SELECT count(*) FROM {UNITS} WHERE m.whole_only AND u.grams IS NULL"
SQL_A_NO_MAX = f"SELECT count(*) FROM {UNITS} WHERE m.whole_only AND m.max_g IS NULL"
SQL_A_VIOLATIONS = f"""
    SELECT count(*) FROM {UNITS}
    WHERE m.whole_only AND u.grams IS NOT NULL AND m.max_g IS NOT NULL AND {NOT_WHOLE}
"""

B_WHERE = "NOT m.whole_only AND u.unit_rank = ANY(%(whole_ranks)s::int[])"
SQL_B_COUNT = f"SELECT count(*) FROM {UNITS} WHERE {B_WHERE}"
SQL_B_BY_CATEGORY = f"""
    SELECT m.category::text,
           count(*),
           count(*) FILTER (WHERE m.by_weight),
           count(*) FILTER (WHERE NOT m.by_weight)
    FROM {UNITS} WHERE {B_WHERE}
    GROUP BY m.category ORDER BY m.category::text
"""

SQL_C_EXAMINED = "SELECT count(*) FROM v_menu_foods"
SQL_C_ELIGIBLE = "SELECT count(*) FROM food_curation WHERE menu_eligible"
SQL_C_WHOLE = "SELECT count(*) FROM v_menu_foods WHERE whole_only"
SQL_C_NOT_WHOLE = "SELECT count(*) FROM v_menu_foods WHERE NOT whole_only"
SQL_C_BY_WEIGHT = "SELECT count(*) FROM v_menu_foods WHERE by_weight"
SQL_C_NO_UNIT = f"SELECT count(*) FROM {UNITS} WHERE u.mida_code IS NULL"
SQL_C_EXPORT_NO_UNIT = f"SELECT count(*) FROM {UNITS} WHERE u.mida_code IS NULL OR m.by_weight"


def rank_of(mida_code):
    return MENU_UNIT.get(mida_code, (None, None))[0]


def fmt(value):
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def fmt_g(value):
    return "-" if value is None else f"{float(value):g}"


class Counts:
    """Each count from its own query, checked against the Python list."""

    def __init__(self, cur, params):
        self.cur, self.params, self.mismatches = cur, params, []

    def one(self, sql, label, python_len=None):
        self.cur.execute(sql, self.params)
        n = self.cur.fetchone()[0]
        if python_len is None:
            print(f"  {label}: {n}")
        else:
            agree = "agrees" if n == python_len else "DISAGREES"
            print(f"  {label}: {n}  (python list: {python_len}, {agree})")
            if n != python_len:
                self.mismatches.append(f"{label}: sql {n} vs python {python_len}")
        return n


def main():
    EXPORT.check_tables_agree()

    url = load_database_url()
    try:
        conn_ctx = psycopg.connect(url)
    except psycopg.OperationalError as exc:
        sys.exit(f"Cannot connect to {mask_dsn(url)}\n{exc}")

    with conn_ctx as conn:
        conn.read_only = True
        with conn.cursor() as cur:
            cur.execute("SHOW transaction_read_only")
            read_only = cur.fetchone()[0]
            print(f"transaction_read_only = {read_only}")
            if read_only != "on":
                sys.exit("STOP: the transaction is not read-only")

            cur.execute(SQL_ROWS)
            rows = cur.fetchall()
            codes = [r[0] for r in rows]
            servings_by_code = {}
            if codes:
                cur.execute(SQL_SERVINGS, (codes,))
                for source_code, mida_code, label, plural, grams in cur.fetchall():
                    servings_by_code.setdefault(source_code, []).append(
                        (mida_code, label, plural, grams))

            resolved = []
            for source_code, name_he, category, kcal, by_weight, whole_only, max_g in rows:
                servings = servings_by_code.get(source_code, [])
                kcal_f = None if kcal is None else float(kcal)
                unit = choose_unit(servings, kcal_f, source_code)
                resolved.append(dict(
                    code=source_code, name=name_he, category=category,
                    by_weight=by_weight, whole_only=whole_only,
                    max_g=None if max_g is None else float(max_g),
                    unit=unit, rank=None if unit is None else rank_of(unit[0]),
                    servings=servings,
                    override=source_code in UNIT_BY_JUDGEMENT))

            params = dict(
                codes=[r["code"] for r in resolved],
                midas=[None if r["unit"] is None else r["unit"][0] for r in resolved],
                grams=[None if r["unit"] is None else float(r["unit"][3]) for r in resolved],
                ranks=[r["rank"] for r in resolved],
                whole_ranks=list(WHOLE_UNIT_RANKS),
                tol=WHOLE_TOL)
            counts = Counts(cur, params)

            # ---- A ----------------------------------------------------------
            print()
            print("=" * 100)
            print("SECTION A - whole_only rows whose max_g is not a whole multiple of the unit (#50)")
            print(f"  unit via choose_unit(); ratio = max_g / unit grams; whole = within {WHOLE_TOL} of an integer")
            print("=" * 100)
            whole_rows = [r for r in resolved if r["whole_only"]]
            a_no_unit = [r for r in whole_rows if r["unit"] is None]
            a_no_max = [r for r in whole_rows if r["max_g"] is None]
            print("code | name | category | unit label | mida | unit g | max_g | max_g/unit | whole")
            violations = []
            for r in whole_rows:
                if r["unit"] is None or r["max_g"] is None:
                    continue
                grams = float(r["unit"][3])
                ratio = r["max_g"] / grams
                whole = abs(ratio - round(ratio)) <= WHOLE_TOL
                if not whole:
                    violations.append(r)
                    print(f"{r['code']} | {r['name']} | {r['category']} | {r['unit'][1]} | "
                          f"{r['unit'][0]} | {fmt_g(grams)} | {fmt_g(r['max_g'])} | "
                          f"{ratio:.3f} | no" + (" | UNIT_BY_JUDGEMENT" if r["override"] else ""))
            if not violations:
                print("(none)")
            for r in a_no_unit:
                print(f"NO UNIT: {r['code']} | {r['name']} | {r['category']} | by_weight {r['by_weight']}")
            for r in a_no_max:
                print(f"NO MAX_G: {r['code']} | {r['name']} | {r['category']}")
            print("counts:")
            counts.one(SQL_A_EXAMINED, "whole_only = true rows examined", len(whole_rows))
            counts.one(SQL_A_VIOLATIONS, "violations (max_g not a whole multiple)", len(violations))
            counts.one(SQL_A_NO_UNIT, "whole_only rows with no unit from choose_unit()", len(a_no_unit))
            counts.one(SQL_A_NO_MAX, "whole_only rows with max_g NULL", len(a_no_max))

            # ---- B ----------------------------------------------------------
            print()
            print("=" * 100)
            print("SECTION B - counted unit chosen while whole_only is false (#21)")
            print(f"  counted = MENU_UNIT rank in WHOLE_UNIT_RANKS {tuple(WHOLE_UNIT_RANKS)} "
                  f"(read from 11_curation_sheet.py)")
            print("=" * 100)
            b_rows = [r for r in resolved
                      if not r["whole_only"] and r["rank"] in WHOLE_UNIT_RANKS]
            for category in sorted({r["category"] for r in b_rows}):
                in_cat = [r for r in b_rows if r["category"] == category]
                print(f"-- category {category}: {len(in_cat)} rows")
                print("code | name | category | unit label | mida | unit g | rank | max_g | by_weight"
                      " | food_servings (mida, label, grams)")
                for r in in_cat:
                    serv = " · ".join(f"({s[0]}, {s[1]}, {fmt_g(s[3])})" for s in r["servings"])
                    print(f"{r['code']} | {r['name']} | {r['category']} | {r['unit'][1]} | "
                          f"{r['unit'][0]} | {fmt_g(r['unit'][3])} | {r['rank']} | "
                          f"{fmt_g(r['max_g'])} | {r['by_weight']} | {serv}"
                          + (" | UNIT_BY_JUDGEMENT" if r["override"] else ""))
            if not b_rows:
                print("(none)")
            print("counts:")
            counts.one(SQL_B_COUNT, "rows, all categories", len(b_rows))
            cur.execute(SQL_B_BY_CATEGORY, params)
            print("  by category (sql): category | rows | by_weight true | by_weight false")
            for category, n, n_bw, n_not_bw in cur.fetchall():
                py = [r for r in b_rows if r["category"] == category]
                py_bw = sum(1 for r in py if r["by_weight"])
                agree = (n, n_bw, n_not_bw) == (len(py), py_bw, len(py) - py_bw)
                print(f"    {category} | {n} | {n_bw} | {n_not_bw}"
                      f"  (python: {len(py)} | {py_bw} | {len(py) - py_bw}, "
                      f"{'agrees' if agree else 'DISAGREES'})")
                if not agree:
                    counts.mismatches.append(f"B category {category}")

            # ---- C ----------------------------------------------------------
            print()
            print("=" * 100)
            print("SECTION C - totals")
            print("=" * 100)
            counts.one(SQL_C_EXAMINED, "menu_eligible rows examined (v_menu_foods)", len(resolved))
            counts.one(SQL_C_ELIGIBLE, "menu_eligible rows in food_curation")
            counts.one(SQL_C_WHOLE, "whole_only = true",
                       sum(1 for r in resolved if r["whole_only"]))
            counts.one(SQL_C_NOT_WHOLE, "whole_only = false",
                       sum(1 for r in resolved if not r["whole_only"]))
            counts.one(SQL_C_BY_WEIGHT, "by_weight = true",
                       sum(1 for r in resolved if r["by_weight"]))
            counts.one(SQL_C_NO_UNIT, "no acceptable unit at all (choose_unit() is None)",
                       sum(1 for r in resolved if r["unit"] is None))
            counts.one(SQL_C_EXPORT_NO_UNIT, "export carries no unit (None or by_weight)",
                       sum(1 for r in resolved if r["unit"] is None or r["by_weight"]))

    if counts.mismatches:
        print()
        for m in counts.mismatches:
            print(f"STOP: sql and python disagree - {m}")
        sys.exit(1)


if __name__ == "__main__":
    main()
