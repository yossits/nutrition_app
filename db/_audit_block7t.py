# -*- coding: utf-8 -*-
"""
_audit_block7t.py - opening measurement for sub-block 7ת (the label queue). Read-only in the database.

  python db\\_audit_block7t.py

Opened in 7ת-א (15.09.2026). Every query runs in its own transaction that opens
with SET TRANSACTION READ ONLY and is rolled back on exit - query() and
SNAPSHOT_SQL are imported from _audit_block7a.py, unchanged. Nothing is written
to the database. Two files are written to db/, and only when no stop fired:

  block7_label_codes.txt   the 34 codes of the queue, one per line, numeric order,
                           a header comment in the style of block8_carb_label_codes.txt
  block7_label_sheet.tsv   the owner's sheet for 7ת-ב - UTF-8, LF, tab-separated, one
                           header row, written the way db/20_carb_candidates.py writes
                           its TSV: an empty cell is NULL or not applicable, flags are 1/0

Sections:
  B0  the nine canonical metrics, before
  B1  the queue derived in code: db/block6_protein_label_codes.txt less 625 649 683
      (D4, docs/work/2026-09-14-block-7-labels.md), plus 1698 and 1826, plus
      db/block8_carb_label_codes.txt
  B2  the queue against the database: foods, food_curation, the category split
  B3  the tag vocabulary the plant marker rests on
  B4  fiber_g IS NULL among the 34 - plant items and the rest
  B5  the columns of food_curation, and every public column whose name could meet D2
  B6  the nine canonical metrics, after
  B7  the codes file and the sheet

The plant marker (7ת-א, owner's ruling of 15.09.2026): a row of the 31 is a plant
item when food_curation.tags holds 'vegan'; the 3 carbs count as plant by category.
It rests on the tag vocabulary of the rows 16_tag_fat.sql and 18_tag_protein.sql
wrote - {vegan} or {} and nothing else (V2 in 16, V2e in 18) - which B3 re-measures
on the 31 and stops on if it no longer holds.

Exit 1 when a stop fires.
"""

import collections
import csv
import hashlib
import io
import sys
from pathlib import Path

try:
    import psycopg
except ImportError:
    sys.exit("psycopg is missing. Run:  pip install \"psycopg[binary]\"")

# sys.path[0] is db/ when this is run as `python db/_audit_block7t.py`.
from _env import load_database_url, mask_dsn
from _audit_block7a import SNAPSHOT_SQL, query, read_code_file, table, heading, snapshot

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
PROTEIN_LABEL_FILE = HERE / "block6_protein_label_codes.txt"
CARB_LABEL_FILE = HERE / "block8_carb_label_codes.txt"
CODES_OUT = HERE / "block7_label_codes.txt"
SHEET_OUT = HERE / "block7_label_sheet.tsv"

EXPECTED_SNAPSHOT = (423, 264, 105, 37, 44, 78, 264, 0, 0)
D4_OUT = ("625", "649", "683")                  # generic descriptions, no product on a shelf
ADDED = ("1698", "1826")                        # the two named codes that stay in the queue
NOT_IN_QUEUE = ("625", "649", "683", "9589", "1630", "680", "493")
EXPECTED_WITH_ROW, EXPECTED_WITHOUT_ROW, EXPECTED_TOTAL = 31, 3, 34
EXPECTED_CATEGORY_31 = {"protein": 30, "fat": 1}
PLANT_TAG = "vegan"
TAG_VOCABULARY = ({PLANT_TAG}, set())
CHAT_FIVE = ("1698", "1826", "2807", "8966", "8969")   # the five the chat looked at
CATEGORY_ORDER = {"protein": 0, "fat": 1, "carb": 2}

SHEET_COLUMNS = ["source_code", "name_he", "name_en", "makor", "category", "tags",
                 "has_curation_row", "fiber_g", "allergens_now", "needs_tagging",
                 "ingredients_label", "allergens_label", "fiber_g_label",
                 "label_source", "label_date", "notes"]
OWNER_COLUMNS = SHEET_COLUMNS[10:]

QUEUE_SQL = """
    SELECT u.code AS source_code,
           (f.source_code IS NOT NULL) AS in_foods,
           f.name_he, f.name_en, f.makor, f.fiber_g,
           (c.source_code IS NOT NULL) AS has_curation_row,
           c.category::text AS category, c.tags, c.allergens, c.allergens_reviewed_at,
           c.excluded_reason::text AS excluded_reason, c.menu_eligible
    FROM unnest(%s::text[]) WITH ORDINALITY AS u(code, ord)
    LEFT JOIN foods f         ON f.source_code = u.code
    LEFT JOIN food_curation c ON c.source_code = u.code
    ORDER BY u.ord"""

# The gate numbers come from this query, not from counting the rows above.
COUNT_SQL = """
    SELECT count(*)                                          AS codes,
           count(f.source_code)                              AS in_foods,
           count(c.source_code)                              AS with_curation_row,
           count(*) FILTER (WHERE c.source_code IS NOT NULL
                              AND c.menu_eligible = false
                              AND c.allergens_reviewed_at IS NULL
                              AND c.excluded_reason IS NULL
                              AND c.allergens = '{}'::text[]) AS waiting_state,
           count(*) FILTER (WHERE c.category = 'protein')    AS protein,
           count(*) FILTER (WHERE c.category = 'fat')        AS fat,
           count(*) FILTER (WHERE c.category = 'carb')       AS carb,
           count(*) FILTER (WHERE c.category = 'veg')        AS veg,
           count(*) FILTER (WHERE c.source_code IS NOT NULL
                              AND c.category IS NULL)         AS no_category
    FROM unnest(%s::text[]) AS u(code)
    LEFT JOIN foods f         ON f.source_code = u.code
    LEFT JOIN food_curation c ON c.source_code = u.code"""

FIBER_SQL = """
    SELECT count(*) FILTER (WHERE f.fiber_g IS NULL) AS fiber_null,
           count(*) FILTER (WHERE f.fiber_g IS NULL
                              AND (u.code = ANY(%(carb)s::text[])
                                   OR COALESCE('vegan' = ANY(c.tags), false))) AS fiber_null_plant,
           count(*) FILTER (WHERE f.fiber_g IS NULL
                              AND NOT (u.code = ANY(%(carb)s::text[])
                                       OR COALESCE('vegan' = ANY(c.tags), false))) AS fiber_null_not_plant
    FROM unnest(%(queue)s::text[]) AS u(code)
    JOIN foods f              ON f.source_code = u.code
    LEFT JOIN food_curation c ON c.source_code = u.code"""

stops = []


def fmt(v):
    """A TSV cell: NULL is empty, a bool is 1/0, an array is {a,b}."""
    if v is None:
        return ""
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, list):
        return "{" + ",".join(str(x) for x in v) + "}"
    return str(v)


def codes_of(path):
    n_lines, comments, codes, malformed = read_code_file(path)
    dup = sorted({c for c, k in collections.Counter(codes).items() if k > 1})
    print(f"{path.name}: physical lines {n_lines} · comment lines {len(comments)} · "
          f"codes {len(codes)} · distinct {len(set(codes))} · duplicates {dup or 'none'} · "
          f"malformed {malformed or 'none'}")
    if malformed or dup:
        stops.append(f"S4: {path.name} malformed {malformed} duplicates {dup}")
    return codes


def main():
    url = load_database_url()
    try:
        conn = psycopg.connect(url, autocommit=True)
    except psycopg.OperationalError as exc:
        sys.exit(f"Cannot connect to {mask_dsn(url)}\n{exc}")

    with conn:
        _, ro = query(conn, "SHOW transaction_read_only")
        print(f"transaction_read_only inside the helper: {ro[0][0]}")

        # ---------------------------------------------------------------- B0 --
        before = snapshot(conn, "before (B0)")
        if before != EXPECTED_SNAPSHOT:
            stops.append(f"S4: snapshot before {before} != expected {EXPECTED_SNAPSHOT}")

        # ---------------------------------------------------------------- B1 --
        heading("B1 - the queue, derived in code")
        protein_codes = codes_of(PROTEIN_LABEL_FILE)
        carb_codes = codes_of(CARB_LABEL_FILE)
        missing_d4 = [c for c in D4_OUT if c not in protein_codes]
        already = [c for c in ADDED if c in protein_codes or c in carb_codes]
        if missing_d4:
            stops.append(f"S4: D4 codes not in {PROTEIN_LABEL_FILE.name}: {missing_d4}")
        if already:
            stops.append(f"S4: codes to add are already in a label file: {already}")
        with_row = [c for c in protein_codes if c not in D4_OUT] + list(ADDED)
        without_row = list(carb_codes)
        queue = with_row + without_row
        overlap = sorted(set(with_row) & set(without_row))
        in_queue_forbidden = [c for c in NOT_IN_QUEUE if c in queue]
        print(f"{PROTEIN_LABEL_FILE.name} {len(protein_codes)} - D4 {len(D4_OUT)} "
              f"+ added {len(ADDED)} = {len(with_row)}")
        print(f"{CARB_LABEL_FILE.name} {len(without_row)}")
        print(f"queue {len(queue)} · distinct {len(set(queue))} · overlap {overlap or 'none'}")
        print(f"of {' '.join(NOT_IN_QUEUE)} in the queue: {in_queue_forbidden or 'none'}")
        if (len(with_row), len(without_row), len(queue), len(set(queue))) != (
                EXPECTED_WITH_ROW, EXPECTED_WITHOUT_ROW, EXPECTED_TOTAL, EXPECTED_TOTAL):
            stops.append(f"S4: queue {len(with_row)} + {len(without_row)} = {len(queue)} "
                         f"(distinct {len(set(queue))}), expected 31 + 3 = 34")
        if overlap or in_queue_forbidden:
            stops.append(f"S4: overlap {overlap} · forbidden codes in queue {in_queue_forbidden}")

        # ---------------------------------------------------------------- B2 --
        heading("B2 - counts in SQL, per group")
        count_rows = []
        for label, codes in (("with_row (31)", with_row), ("without_row (3)", without_row),
                             ("queue (34)", queue)):
            cols, rows = query(conn, COUNT_SQL, (codes,))
            count_rows.append((label,) + rows[0])
        table(["group"] + cols, count_rows)
        c31 = dict(zip(cols, count_rows[0][1:]))
        c3 = dict(zip(cols, count_rows[1][1:]))
        c34 = dict(zip(cols, count_rows[2][1:]))
        if c34["in_foods"] != EXPECTED_TOTAL:
            stops.append(f"S4: {c34['in_foods']} of the queue in foods, expected 34")
        if c31["with_curation_row"] != EXPECTED_WITH_ROW or c31["waiting_state"] != EXPECTED_WITH_ROW:
            stops.append(f"S4: of the 31, curation row {c31['with_curation_row']}, "
                         f"waiting state {c31['waiting_state']}; expected 31 and 31")
        if c3["with_curation_row"] != 0:
            stops.append(f"S4: {c3['with_curation_row']} of the 3 carbs have a curation row, expected 0")
        split = {k: c31[k] for k in ("protein", "fat", "carb", "veg", "no_category") if c31[k]}
        print(f"\ncategory split of the 31 (SQL): {split} · expected {EXPECTED_CATEGORY_31}")
        if split != EXPECTED_CATEGORY_31:
            stops.append(f"S4: category split of the 31 {split} != {EXPECTED_CATEGORY_31}")

        cols, rows = query(conn, QUEUE_SQL, (queue,))
        by_code = {r[0]: dict(zip(cols, r)) for r in rows}
        heading("B2 - one row per code")
        table(cols, rows)
        rows_have = sorted((c for c in queue if by_code[c]["has_curation_row"]), key=int)
        if rows_have != sorted(with_row, key=int):
            stops.append(f"S4: codes with a curation row {rows_have} != the 31 derived in B1")
        print("the 3 carbs are carb by the 8פ-ד decision (docs/work/2026-09-12-block-8-carb.md, "
              "\"### תווית - 3, לבלוק 7\"); there is no row to read the category from")

        # ---------------------------------------------------------------- B3 --
        heading("B3 - tag vocabulary")
        cols, rows = query(conn, """
            SELECT c.tags::text AS tags, c.category::text AS category, count(*) AS n
            FROM food_curation c
            WHERE c.source_code = ANY(%s::text[])
            GROUP BY 1, 2 ORDER BY 2, 1""", (with_row,))
        print("on the 31:")
        table(cols, rows)
        cols, rows_all = query(conn, """
            SELECT c.tags::text AS tags, count(*) AS n
            FROM food_curation c GROUP BY 1 ORDER BY 2 DESC, 1""")
        print("\nacross food_curation (context):")
        table(cols, rows_all)
        off_vocabulary = sorted((c for c in with_row if set(by_code[c]["tags"] or []) not in TAG_VOCABULARY),
                                key=int)
        if off_vocabulary:
            stops.append(f"S4: tags outside {{vegan}} / {{}} on {off_vocabulary} - the plant marker does not hold")

        # ---------------------------------------------------------------- B4 --
        heading("B4 - fiber_g IS NULL among the 34")

        def is_plant(code):
            if code in without_row:
                return True
            return PLANT_TAG in (by_code[code]["tags"] or [])

        null_codes = sorted((c for c in queue if by_code[c]["fiber_g"] is None), key=int)
        null_plant = [c for c in null_codes if is_plant(c)]
        null_not_plant = [c for c in null_codes if not is_plant(c)]
        cols, rows = query(conn, FIBER_SQL, {"queue": queue, "carb": without_row})
        sql_fiber = dict(zip(cols, rows[0]))
        table(cols, rows)
        print(f"fiber_g NULL among the 34: {len(null_codes)} - {' '.join(null_codes) or 'none'}")
        print(f"  of them plant:     {len(null_plant)} - {' '.join(null_plant) or 'none'}")
        print(f"  of them not plant: {len(null_not_plant)} - {' '.join(null_not_plant) or 'none'}")
        if (sql_fiber["fiber_null"], sql_fiber["fiber_null_plant"], sql_fiber["fiber_null_not_plant"]) != (
                len(null_codes), len(null_plant), len(null_not_plant)):
            stops.append(f"S4: fiber counts in SQL {sql_fiber} != in code "
                         f"{(len(null_codes), len(null_plant), len(null_not_plant))}")
        print("\nthe five the chat looked at:")
        table(["source_code", "fiber_g", "plant"],
              [(c, by_code[c]["fiber_g"], is_plant(c)) for c in CHAT_FIVE])
        plant_all = sum(1 for c in queue if is_plant(c))
        print(f"plant items among the 34 (context): {plant_all}")

        # ---------------------------------------------------------------- B5 --
        heading("B5 - columns of food_curation (D2)")
        cols, rows = query(conn, """
            SELECT ordinal_position, column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'food_curation'
            ORDER BY ordinal_position""")
        table(cols, rows)
        heading("B5 - public columns named like label / _source / _date / _at / _on")
        cols, rows = query(conn, """
            SELECT table_name, column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND (column_name ILIKE '%%label%%' OR column_name ILIKE '%%\\_source'
                   OR column_name ILIKE '%%\\_date' OR column_name ILIKE '%%\\_at'
                   OR column_name ILIKE '%%\\_on')
            ORDER BY 1, 2""")
        table(cols, rows)

        # ---------------------------------------------------------------- B6 --
        after = snapshot(conn, "after (B6)")
        if after != before:
            stops.append(f"S4: snapshot after {after} != before {before}")

    # -------------------------------------------------------------------- B7 --
    heading("B7 - the codes file and the sheet")
    if stops:
        print("not written: a stop fired")
    else:
        codes_text = ("# label queue - block 7ת (#45): 29 of block6_protein_label_codes.txt "
                      "less D4 + 1698 + 1826, and 3 carb mixes from 8פ-ד (15.09.2026)\n"
                      + "".join(f"{c}\n" for c in sorted(queue, key=int)))
        CODES_OUT.write_bytes(codes_text.encode("utf-8"))

        def category_of(code):
            return "carb" if code in without_row else by_code[code]["category"]

        ordered = sorted(queue, key=lambda c: (CATEGORY_ORDER[category_of(c)], int(c)))
        buf = io.StringIO(newline="")
        writer = csv.DictWriter(buf, fieldnames=SHEET_COLUMNS, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for c in ordered:
            r = by_code[c]
            row = {
                "source_code": c,
                "name_he": fmt(r["name_he"]),
                "name_en": fmt(r["name_en"]),
                "makor": fmt(r["makor"]),
                "category": category_of(c),
                "tags": fmt(r["tags"]),
                "has_curation_row": fmt(r["has_curation_row"]),
                "fiber_g": fmt(r["fiber_g"]),
                "allergens_now": fmt(r["allergens"]),
                "needs_tagging": fmt(c in without_row),
            }
            row.update({k: "" for k in OWNER_COLUMNS})
            writer.writerow(row)
        SHEET_OUT.write_bytes(buf.getvalue().encode("utf-8"))

        n_lines, comments, codes_back, malformed = read_code_file(CODES_OUT)
        if sorted(codes_back, key=int) != sorted(queue, key=int) or len(comments) != 1 or malformed:
            stops.append(f"S4: {CODES_OUT.name} read back {len(codes_back)} codes, "
                         f"{len(comments)} comments, malformed {malformed}")
        with open(SHEET_OUT, encoding="utf-8", newline="") as fh:
            back = list(csv.DictReader(fh, delimiter="\t"))
        if [b["source_code"] for b in back] != ordered or any(len(b) != len(SHEET_COLUMNS) for b in back):
            stops.append(f"S4: {SHEET_OUT.name} read back {len(back)} rows, not the 34 in order")

        print(buf.getvalue(), end="")
        split_sheet = collections.Counter(category_of(c) for c in ordered)
        print(f"\nsheet rows {len(back)} · by category {dict(split_sheet)} · "
              f"needs_tagging {sum(1 for c in ordered if c in without_row)}")
        for path in (CODES_OUT, SHEET_OUT):
            raw = path.read_bytes()
            n_lf, n_cr = raw.count(b"\n"), raw.count(b"\r")
            print(f"✔ {path.name} — {len(raw)} bytes · {n_lf} lines · "
                  f"CR bytes {n_cr} · sha256 {hashlib.sha256(raw).hexdigest()}")

    heading("Stop points")
    if stops:
        for s in stops:
            print(f"FIRED  {s}")
        sys.exit(1)
    print("none fired")


if __name__ == "__main__":
    main()
