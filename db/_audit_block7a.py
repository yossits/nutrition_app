# -*- coding: utf-8 -*-
"""
_audit_block7a.py - opening measurement for block 7 (commercial products vs labels). Read-only.

  python db\\_audit_block7a.py

Opened in block 7a. Every query runs in its own transaction that opens with
SET TRANSACTION READ ONLY and is rolled back on exit. Nothing is written to the
database or to disk; the report goes to stdout.

Sections:
  A0  the nine canonical metrics, before
  A1  the label queue: db/block6_protein_label_codes.txt, db/block8_carb_label_codes.txt
      and the three codes the docs name individually (1826, 1698, 9589)
  A2  the reverse check: curated, not eligible, allergens_reviewed_at IS NULL
  A3  source / makor / name for the A1 union
  A4  the fat landscape: allergen-free eligible fats, allergen histogram, p4 families
  A5  constraints, triggers and the shape of source_code
  A6  every column of foods and food_curation
  A7  the nine canonical metrics, after
"""

import collections
import re
import sys
from pathlib import Path

try:
    import psycopg
except ImportError:
    sys.exit("psycopg is missing. Run:  pip install \"psycopg[binary]\"")

# sys.path[0] is db/ when this is run as `python db/_audit_block7a.py`.
from _env import load_database_url, mask_dsn

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
LABEL_FILES = {
    "protein_file": HERE / "block6_protein_label_codes.txt",
    "carb_file": HERE / "block8_carb_label_codes.txt",
}
NAMED_CODES = ("1826", "1698", "9589")
EXPECTED_SNAPSHOT = (423, 264, 105, 37, 44, 78, 264, 0, 0)
EXPECTED_QUEUE = 38
LUPIN, BLOCK4_EXCLUDED = "1630", "680"

SNAPSHOT_SQL = """
    SELECT (SELECT count(*) FROM food_curation),
           (SELECT count(*) FROM food_curation WHERE menu_eligible),
           (SELECT count(*) FROM food_curation WHERE menu_eligible AND category='protein'),
           (SELECT count(*) FROM food_curation WHERE menu_eligible AND category='fat'),
           (SELECT count(*) FROM food_curation WHERE menu_eligible AND category='carb'),
           (SELECT count(*) FROM food_curation WHERE menu_eligible AND category='veg'),
           (SELECT count(*) FROM v_menu_foods),
           (SELECT count(*) FROM v_eligible_missing_tags),
           (SELECT count(*) FROM v_curation_orphans)"""
SNAPSHOT_NAMES = ("food_curation_rows", "menu_eligible", "elig_protein", "elig_fat",
                  "elig_carb", "elig_veg", "v_menu_foods", "v_eligible_missing_tags",
                  "v_curation_orphans")

stops = []


def query(conn, sql, params=None):
    """One read-only transaction per query, always rolled back."""
    with conn.transaction(force_rollback=True):
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY;")
            cur.execute(sql, params)
            cols = [d.name for d in cur.description]
            return cols, cur.fetchall()


def cell(v):
    if v is None:
        return "∅"
    if isinstance(v, list):
        return "{" + ",".join(str(x) for x in v) + "}"
    if isinstance(v, bool):
        return "y" if v else "n"
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return str(v)


def table(cols, rows):
    print("| " + " | ".join(cols) + " |")
    print("|" + "---|" * len(cols))
    for r in rows:
        print("| " + " | ".join(cell(v) for v in r) + " |")
    print(f"({len(rows)} rows)")


def heading(title):
    print(f"\n## {title}\n")


def snapshot(conn, label):
    _, rows = query(conn, SNAPSHOT_SQL)
    values = tuple(int(v) for v in rows[0])
    heading(f"Snapshot {label}")
    print(" · ".join(str(v) for v in values))
    table(list(SNAPSHOT_NAMES), [values])
    return values


def read_code_file(path):
    """Returns (physical_lines, comment_lines, codes, malformed)."""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    comments, codes, malformed = [], [], []
    for n, line in enumerate(lines, 1):
        s = line.strip()
        if not s:
            continue
        if s.startswith("#"):
            comments.append((n, s))
        elif re.fullmatch(r"[0-9]+", s):
            codes.append(s)
        else:
            malformed.append((n, s))
    return len(lines), comments, codes, malformed


def main():
    url = load_database_url()
    try:
        conn = psycopg.connect(url, autocommit=True)
    except psycopg.OperationalError as exc:
        sys.exit(f"Cannot connect to {mask_dsn(url)}\n{exc}")

    with conn:
        _, ro = query(conn, "SHOW transaction_read_only")
        print(f"transaction_read_only inside the helper: {ro[0][0]}")

        # ---------------------------------------------------------------- A0 --
        before = snapshot(conn, "before (A0)")
        if before != EXPECTED_SNAPSHOT:
            stops.append(f"S1: snapshot before {before} != expected {EXPECTED_SNAPSHOT}")

        # ---------------------------------------------------------------- A1 --
        heading("A1 - label files")
        origins = collections.OrderedDict()
        for key, path in LABEL_FILES.items():
            if not path.is_file():
                stops.append(f"S6: {path} does not exist")
                continue
            n_lines, comments, codes, malformed = read_code_file(path)
            dup = [c for c, k in collections.Counter(codes).items() if k > 1]
            print(f"{path.name}: physical lines {n_lines} · comment lines {len(comments)} · "
                  f"code lines {len(codes)} · distinct codes {len(set(codes))} · "
                  f"duplicates {dup or 'none'} · malformed {malformed or 'none'}")
            for n, c in comments:
                print(f"    comment line {n}: {c}")
            print(f"    codes: {' '.join(codes)}")
            if malformed:
                stops.append(f"S6: {path.name} has malformed lines {malformed}")
            for c in codes:
                origins.setdefault(c, []).append(key)
        for c in NAMED_CODES:
            origins.setdefault(c, []).append("named_in_docs")

        union = list(origins)
        overlaps = {c: o for c, o in origins.items() if len(o) > 1}
        print(f"\nnamed codes: {' '.join(NAMED_CODES)}")
        print(f"codes appearing in more than one source: {overlaps or 'none'}")

        a1_sql = """
            SELECT u.code AS source_code,
                   c.category, f.name_he,
                   (f.source_code IS NOT NULL) AS in_foods,
                   (c.source_code IS NOT NULL) AS has_curation,
                   c.menu_eligible, c.allergens, c.allergens_reviewed_at,
                   c.excluded_reason,
                   EXISTS (SELECT 1 FROM v_menu_foods v WHERE v.source_code = u.code) AS in_v_menu_foods,
                   f.source, f.makor, f.class_code
            FROM unnest(%s::text[]) WITH ORDINALITY AS u(code, ord)
            LEFT JOIN foods f         ON f.source_code = u.code
            LEFT JOIN food_curation c ON c.source_code = u.code
            ORDER BY u.ord"""
        cols, rows = query(conn, a1_sql, (union,))
        heading("A1 - one row per code in the union")
        a1_cols = cols[:10] + ["origin"]
        table(a1_cols, [r[:10] + ("+".join(origins[r[0]]),) for r in rows])
        by_code = {r[0]: dict(zip(cols, r)) for r in rows}

        total = len(union)
        print(f"\nA1 total (distinct codes in the union): {total}")
        missing_foods = [c for c in union if not by_code[c]["in_foods"]]
        print(f"codes not in foods: {missing_foods or 'none'}")
        print(f"codes with no food_curation row: "
              f"{[c for c in union if not by_code[c]['has_curation']] or 'none'}")
        if missing_foods:
            stops.append(f"S3: codes not in foods {missing_foods}")
        if total != EXPECTED_QUEUE:
            stops.append(f"S3: A1 total {total} != {EXPECTED_QUEUE}")

        heading("A1 - split by category")
        cnt = collections.Counter(cell(by_code[c]["category"]) for c in union)
        table(["category", "n"], sorted(cnt.items()))
        heading("A1 - split by origin")
        cnt = collections.Counter("+".join(origins[c]) for c in union)
        table(["origin", "n"], sorted(cnt.items()))
        heading("A1 - split by origin x category")
        cnt = collections.Counter(("+".join(origins[c]), cell(by_code[c]["category"])) for c in union)
        table(["origin", "category", "n"], [k + (v,) for k, v in sorted(cnt.items())])
        heading("A1 - state counts")
        state = collections.Counter(
            (cell(by_code[c]["menu_eligible"]),
             "reviewed_at NULL" if by_code[c]["allergens_reviewed_at"] is None else "reviewed_at set",
             cell(by_code[c]["excluded_reason"]),
             cell(by_code[c]["in_v_menu_foods"]))
            for c in union)
        table(["menu_eligible", "allergens_reviewed_at", "excluded_reason", "in_v_menu_foods", "n"],
              [k + (v,) for k, v in sorted(state.items())])

        # ---------------------------------------------------------------- A2 --
        heading("A2 - curated, not eligible, allergens_reviewed_at IS NULL")
        _, n = query(conn, """SELECT count(*) FROM food_curation
                               WHERE menu_eligible = false AND allergens_reviewed_at IS NULL""")
        print(f"population count (SQL): {n[0][0]}")
        cols, rows = query(conn, """
            SELECT c.source_code, f.name_he, c.category, c.excluded_reason, c.allergens
            FROM food_curation c
            LEFT JOIN foods f ON f.source_code = c.source_code
            WHERE c.menu_eligible = false AND c.allergens_reviewed_at IS NULL
            ORDER BY c.source_code::int""")
        union_set = set(union)

        def klass(code):
            if code in union_set:
                return "a"
            if code == LUPIN:
                return "b"
            if code == BLOCK4_EXCLUDED:
                return "c"
            return "d"

        a2 = [r + (klass(r[0]),) for r in rows]
        table(cols + ["group"], a2)
        cnt = collections.Counter(r[-1] for r in a2)
        heading("A2 - groups")
        table(["group", "n"], [(g, cnt.get(g, 0)) for g in "abcd"])
        group_d = [r for r in a2 if r[-1] == "d"]
        heading("A2 - group (d) in full")
        table(cols + ["group"], group_d)
        if group_d:
            stops.append(f"S4: A2 group (d) has {len(group_d)} rows")
        pop_codes = {r[0] for r in rows}
        not_in_pop = [c for c in union if c not in pop_codes]
        heading("A2 - A1 union codes that are NOT in the A2 population")
        table(["source_code", "menu_eligible", "allergens_reviewed_at", "has_curation"],
              [(c, by_code[c]["menu_eligible"], by_code[c]["allergens_reviewed_at"],
                by_code[c]["has_curation"]) for c in not_in_pop])

        # ---------------------------------------------------------------- A3 --
        heading("A3 - source, makor, name for the A1 union")
        table(["source_code", "source", "makor", "name_he", "origin"],
              [(c, by_code[c]["source"], by_code[c]["makor"], by_code[c]["name_he"],
                "+".join(origins[c])) for c in union])
        heading("A3 - split by source")
        cnt = collections.Counter(cell(by_code[c]["source"]) for c in union)
        table(["source", "n"], sorted(cnt.items()))
        heading("A3 - split by source x makor")
        cnt = collections.Counter((cell(by_code[c]["source"]), cell(by_code[c]["makor"])) for c in union)
        table(["source", "makor", "n"], [k + (v,) for k, v in sorted(cnt.items())])

        # ---------------------------------------------------------------- A4 --
        heading("A4 - eligible fat counts (SQL)")
        cols, rows = query(conn, """
            SELECT count(*) AS eligible_fat,
                   count(*) FILTER (WHERE allergens = '{}')  AS allergen_free,
                   count(*) FILTER (WHERE allergens <> '{}') AS with_allergens
            FROM food_curation WHERE menu_eligible AND category = 'fat'""")
        table(cols, rows)

        heading("A4.1 - the allergen-free eligible fats")
        cols, rows = query(conn, """
            SELECT c.source_code, f.name_he, f.class_code,
                   left(f.class_code, 2) AS p2, left(f.class_code, 4) AS p4,
                   left(f.class_code, 6) AS p6, c.max_g
            FROM food_curation c JOIN foods f ON f.source_code = c.source_code
            WHERE c.menu_eligible AND c.category = 'fat' AND c.allergens = '{}'
            ORDER BY f.class_code, c.source_code::int""")
        table(cols, rows)
        free_p4 = sorted({r[4] for r in rows})

        heading("A4.2 - allergen histogram over eligible fats with allergens (one row may count under several)")
        cols, rows = query(conn, """
            SELECT a AS allergen, count(*) AS rows
            FROM food_curation c CROSS JOIN LATERAL unnest(c.allergens) AS a
            WHERE c.menu_eligible AND c.category = 'fat' AND c.allergens <> '{}'
            GROUP BY a ORDER BY count(*) DESC, a""")
        table(cols, rows)
        heading("A4.2 - by exact allergen set")
        cols, rows = query(conn, """
            SELECT (SELECT array_agg(x ORDER BY x) FROM unnest(c.allergens) x) AS allergen_set,
                   count(*) AS rows
            FROM food_curation c
            WHERE c.menu_eligible AND c.category = 'fat' AND c.allergens <> '{}'
            GROUP BY 1 ORDER BY count(*) DESC, 1""")
        table(cols, rows)
        heading("A4.2 - the eligible fats with allergens, row by row")
        cols, rows = query(conn, """
            SELECT c.source_code, f.name_he, left(f.class_code, 4) AS p4, c.allergens
            FROM food_curation c JOIN foods f ON f.source_code = c.source_code
            WHERE c.menu_eligible AND c.category = 'fat' AND c.allergens <> '{}'
            ORDER BY f.class_code, c.source_code::int""")
        table(cols, rows)

        heading("A4.3 - the p4 families of the allergen-free eligible fats")
        cols, rows = query(conn, """
            SELECT left(f.class_code, 4) AS p4,
                   count(*) AS foods_rows,
                   count(c.source_code) AS with_curation_row,
                   count(*) FILTER (WHERE c.menu_eligible) AS menu_eligible,
                   count(*) FILTER (WHERE c.menu_eligible AND c.category = 'fat'
                                      AND c.allergens = '{}') AS eligible_fat_allergen_free,
                   count(*) FILTER (WHERE c.source_code IS NULL) AS no_curation_row
            FROM foods f
            LEFT JOIN food_curation c ON c.source_code = f.source_code
            WHERE left(f.class_code, 4) = ANY(%s::text[])
            GROUP BY 1 ORDER BY 1""", (free_p4,))
        table(cols, rows)
        print(f"total rows with no food_curation row across these p4: {sum(r[-1] for r in rows)}")
        print("Allergen status of a row with no food_curation row is unknown until reviewed.")
        heading("A4.3 - the uncurated rows in those p4 families")
        cols, rows = query(conn, """
            SELECT f.source_code, f.name_he, f.class_code, left(f.class_code, 4) AS p4,
                   f.source, f.makor, f.fat_g
            FROM foods f
            WHERE left(f.class_code, 4) = ANY(%s::text[])
              AND NOT EXISTS (SELECT 1 FROM food_curation c WHERE c.source_code = f.source_code)
            ORDER BY f.class_code, f.source_code::int""", (free_p4,))
        table(cols, rows)

        # ---------------------------------------------------------------- A5 --
        heading("A5.2 - constraints on foods and food_curation (pg_constraint)")
        cols, rows = query(conn, """
            SELECT conrelid::regclass::text AS table_name, conname, contype,
                   pg_get_constraintdef(oid) AS definition
            FROM pg_constraint
            WHERE conrelid IN ('public.foods'::regclass, 'public.food_curation'::regclass)
            ORDER BY 1, contype, conname""")
        table(cols, rows)
        heading("A5.2 - foreign keys that reference foods or food_curation")
        cols, rows = query(conn, """
            SELECT conrelid::regclass::text AS from_table, conname,
                   confrelid::regclass::text AS to_table, pg_get_constraintdef(oid) AS definition
            FROM pg_constraint
            WHERE contype = 'f'
              AND (confrelid IN ('public.foods'::regclass, 'public.food_curation'::regclass)
                   OR conrelid = 'public.food_curation'::regclass)
            ORDER BY 1, 2""")
        table(cols, rows)
        heading("A5.2 - non-internal triggers on foods and food_curation")
        cols, rows = query(conn, """
            SELECT tgrelid::regclass::text AS table_name, tgname,
                   pg_get_triggerdef(oid) AS definition
            FROM pg_trigger
            WHERE NOT tgisinternal
              AND tgrelid IN ('public.foods'::regclass, 'public.food_curation'::regclass)
            ORDER BY 1, 2""")
        table(cols, rows)
        heading("A5.2 - RLS policies on foods and food_curation")
        cols, rows = query(conn, """
            SELECT tablename, policyname, cmd, roles::text, qual, with_check
            FROM pg_policies
            WHERE schemaname = 'public' AND tablename IN ('foods', 'food_curation')
            ORDER BY 1, 2""")
        table(cols, rows)
        heading("A5.2 - v_curation_orphans definition")
        cols, rows = query(conn, "SELECT pg_get_viewdef('public.v_curation_orphans'::regclass, true)")
        print(rows[0][0])

        heading("A5.3 - source_code shape")
        cols, rows = query(conn, """
            SELECT 'foods' AS table_name, count(*) AS n,
                   count(*) FILTER (WHERE source_code ~ '^[0-9]+$') AS numeric_rows,
                   count(*) FILTER (WHERE source_code !~ '^[0-9]+$') AS non_numeric_rows,
                   min(source_code::bigint) FILTER (WHERE source_code ~ '^[0-9]+$') AS min_num,
                   max(source_code::bigint) FILTER (WHERE source_code ~ '^[0-9]+$') AS max_num,
                   min(length(source_code)) AS min_len, max(length(source_code)) AS max_len,
                   min(source_code) AS min_text, max(source_code) AS max_text
            FROM foods
            UNION ALL
            SELECT 'food_curation', count(*),
                   count(*) FILTER (WHERE source_code ~ '^[0-9]+$'),
                   count(*) FILTER (WHERE source_code !~ '^[0-9]+$'),
                   min(source_code::bigint) FILTER (WHERE source_code ~ '^[0-9]+$'),
                   max(source_code::bigint) FILTER (WHERE source_code ~ '^[0-9]+$'),
                   min(length(source_code)), max(length(source_code)),
                   min(source_code), max(source_code)
            FROM food_curation
            UNION ALL
            SELECT 'src_foods.code', count(*),
                   count(*) FILTER (WHERE code ~ '^[0-9]+$'),
                   count(*) FILTER (WHERE code !~ '^[0-9]+$' OR code IS NULL),
                   min(code::bigint) FILTER (WHERE code ~ '^[0-9]+$'),
                   max(code::bigint) FILTER (WHERE code ~ '^[0-9]+$'),
                   min(length(code)), max(length(code)),
                   min(code), max(code)
            FROM src_foods""")
        table(cols, rows)
        heading("A5.3 - source_code column types")
        cols, rows = query(conn, """
            SELECT table_name, column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND ((table_name IN ('foods', 'food_curation') AND column_name = 'source_code')
                   OR (table_name = 'src_foods' AND column_name = 'code'))
            ORDER BY 1""")
        table(cols, rows)
        heading("A5.3 - constraints whose definition mentions source_code")
        cols, rows = query(conn, """
            SELECT conrelid::regclass::text AS table_name, conname, contype,
                   pg_get_constraintdef(oid) AS definition
            FROM pg_constraint
            WHERE conrelid IN ('public.foods'::regclass, 'public.food_curation'::regclass)
              AND pg_get_constraintdef(oid) ILIKE '%%source_code%%'
            ORDER BY 1, 2""")
        table(cols, rows)
        heading("A5.3 - indexes on foods and food_curation")
        cols, rows = query(conn, """
            SELECT tablename, indexname, indexdef FROM pg_indexes
            WHERE schemaname = 'public' AND tablename IN ('foods', 'food_curation')
            ORDER BY 1, 2""")
        table(cols, rows)

        # ---------------------------------------------------------------- A6 --
        for t in ("food_curation", "foods"):
            heading(f"A6 - columns of {t}")
            cols, rows = query(conn, """
                SELECT ordinal_position, column_name, data_type, udt_name, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = %s
                ORDER BY ordinal_position""", (t,))
            table(cols, rows)

        # ---------------------------------------------------------------- A7 --
        after = snapshot(conn, "after (A7)")
        if after != before:
            stops.append(f"S7: snapshot after {after} != before {before}")

    heading("Stop points")
    if stops:
        for s in stops:
            print(f"FIRED  {s}")
    else:
        print("none fired in this script (S2 and S5 are checked outside it)")


if __name__ == "__main__":
    main()
