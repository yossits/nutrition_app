# -*- coding: utf-8 -*-
"""
15_tagging_sheet.py — the tagging sheet for a GIVEN list of codes (block 5c).

READ-ONLY. Opens a READ ONLY transaction as its first statement and rolls back
at the end, exactly as 07_curation_candidates.py and 11_curation_sheet.py do.
It writes no curation row; the tagging migration (block 5e) does that, after
the owner has ruled.

Run.
The DSN is read from .env at the repository root — see db/_env.py.

  python db\\15_tagging_sheet.py --codes db\\block5_fat_codes.txt [--out PATH] [--compact]

Output: --out, default db/tagging_sheet_report.txt (gitignored via
db/*_report.txt). Regenerated from scratch on every run. --compact writes one
tab-separated line per item instead of the wide sheet (default .tsv) — the same
values from the same functions, in a shape a chat window can hold (block 5f).


WHAT THIS FILE IS FOR

11 builds the decision sheet for the candidates 07 selects. Block 4 has already
ruled on those candidates, and what block 5 tags is the block-4 "yes" list — a
file of codes, not a selection. This script takes that file and builds the same
kind of sheet for exactly those codes: what the code can propose, what the
database already holds for the rows curated in 3d, and what is left for the
owner (max_g, prep — spec/05-food-db.md §3).


NOTHING IS RE-DERIVED HERE

Every proposal comes from the module that owns it, loaded by path the way 11
loads 07 and 09 (the module names start with a digit):

  07  POOL_SQL · family_of() · describe_floors()
  09  choose_unit() · SQL_SERVINGS — through 11's build_items()
  11  build_items() — kosher, supp, by_weight, the unit, whole_only, the flag
      mask; SQL_COMPONENTS; the row helpers and the @WIDTH@ mechanism

A column that no existing function computes stays blank and is named at the
end of the sheet. tags is one of them: nothing in db/ proposes tags today.

A code that is not in 07's pool (POOL_SQL) stops the run before anything is
written — that is block 5c's stop point 4, and a sheet that silently dropped a
code would hide exactly the row that needs a human.
"""

import argparse
import hashlib
import importlib.util
import io
import sys
from pathlib import Path

try:
    import psycopg
    from psycopg.rows import dict_row, tuple_row
except ImportError:
    sys.exit("psycopg is missing. Run:  pip install \"psycopg[binary]\"")

# sys.path[0] is db/ when this is run as `python db/15_tagging_sheet.py`.
from _env import load_database_url, mask_dsn

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).parent


def load_by_path(name, filename):
    """Import a sibling db/ module whose name starts with a digit. Same
    mechanism as 11_curation_sheet.py; the entry points are guarded, so only
    module level — constants and definitions — executes."""
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CAND = load_by_path("curation_candidates", "07_curation_candidates.py")
EXPORT = load_by_path("export_menu_foods", "09_export_menu_foods.py")
SHEET = load_by_path("curation_sheet", "11_curation_sheet.py")

FAMILIES = CAND.FAMILIES
POOL_SQL = CAND.POOL_SQL
FAMILY_NO = SHEET.FAMILY_NO
BLANK = SHEET.BLANK          # the code has no source for this cell
FILL = SHEET.FILL            # the owner fills this one
NAME_W = SHEET.NAME_W
RULE = SHEET.RULE
pad_name = SHEET.pad_name
num = SHEET.num

# Of 11's six flag letters (DRKFVC) the four block 5c asks for, in 11's order:
# K kcal_outlier? · F fiber? · V verify_queue? · C container_21?
FLAGS_SHOWN = "KFVC"

# What the database already holds for a code that has a curation row. Read as
# it is — this block proposes nothing.
SQL_CURATION = """
    SELECT source_code, menu_eligible,
           category::text AS category, kosher::text AS kosher,
           max_g, by_weight, whole_only, prep, quality, tags, allergens,
           allergens_reviewed_at
    FROM food_curation
    WHERE source_code = ANY(%s)
"""

HEAD = ("fam  code  " + "name_he".ljust(NAME_W) + "  class_cd"
        " |  kcal  prot   fat"
        " | ksh    sup  bw  unit          gram  wh  tags"
        " | " + FLAGS_SHOWN +
        " | in db: cat      ksh    max_g  bw  wh  prep  tags          allergens"
        " | max_g  prep")


def read_codes(path):
    """One source_code per line; blank lines and # comments are skipped.
    Order is kept — it is the order of the block-4 table."""
    codes = []
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if not line.isdigit():
            sys.exit(f"STOP: not a code: {raw!r} in {path}")
        codes.append(line)
    dupes = sorted({c for c in codes if codes.count(c) > 1})
    if dupes:
        sys.exit(f"STOP: duplicate codes in {path}: {dupes}")
    if not codes:
        sys.exit(f"STOP: no codes in {path}")
    return codes


def yn(value):
    return BLANK if value is None else ("y" if value else "n")


def as_set(value):
    """A Postgres array as psycopg hands it back, or a scalar, printed short."""
    if value is None:
        return BLANK
    if isinstance(value, (list, tuple)):
        return "{" + ",".join(str(v) for v in value) + "}"
    return str(value)


def render_row(item, db):
    """One line per code. The proposals are 11's; the db block is the row as
    stored; the last two cells are the owner's."""
    if db is None:
        in_db = [BLANK.ljust(7), BLANK.ljust(5), BLANK.rjust(5), BLANK.ljust(2),
                 BLANK.ljust(2), BLANK.rjust(4), BLANK.ljust(12), BLANK]
    else:
        allergens = as_set(db["allergens"])
        if db["allergens_reviewed_at"] is None:
            allergens += "?"          # not reviewed — a different state from {}
        in_db = [(db["category"] or BLANK).ljust(7),
                 (db["kosher"] or BLANK).ljust(5),
                 (num(db["max_g"], 5, 0) if db["max_g"] is not None else BLANK.rjust(5)),
                 yn(db["by_weight"]).ljust(2),
                 yn(db["whole_only"]).ljust(2),
                 (str(db["prep"]).rjust(4) if db["prep"] is not None else BLANK.rjust(4)),
                 as_set(db["tags"]).ljust(12),
                 allergens]
    return "  ".join([
        str(item["family_no"]).rjust(3),
        str(item["source_code"]).ljust(5),
        pad_name(item["name_he"]),
        str(item["class_code"]).ljust(8),
        "|",
        num(item["kcal"], 5, 0),
        num(item["protein_g"], 5),
        num(item["fat_g"], 5),
        "|",
        (item["kosher"] or BLANK).ljust(5),
        ("yes" if item["supp"] else "no").ljust(3),
        ("g" if item["by_weight"] else "u").ljust(2),
        (item["unit_label"] or BLANK).ljust(12),
        (num(item["unit_grams"], 4, 0) if item["unit_grams"] is not None
         else BLANK.rjust(4)),
        item["whole_only"].ljust(2),
        BLANK.ljust(4),                         # tags — no function proposes it
        "|",
        "".join(letter if letter in item["flags"] else "·" for letter in FLAGS_SHOWN),
        "|",
        *in_db,
        "|",
        FILL * 5,
        FILL * 4,
    ])


def render_servings(rows):
    """Every food_servings row of the item, smallest first (SQL_SERVINGS order)."""
    if not rows:
        return "servings: none"
    return "servings: " + " · ".join(
        f"{label} {float(grams):g}g [{mida}]" for mida, label, _plural, grams in rows)


COMPACT_HEAD = ["code", "name_he", "family", "p2", "kcal", "protein_g", "fat_g",
                "fiber_g", "source", "kosher", "unit", "by_weight", "whole_only", "supp",
                "flags", "curated", "quality", "max_g", "prep"]


def render_compact(items, pool_by_code, db_by_code):
    """One tab-separated line per item, header first — the sheet for a chat
    window. Every value is the wide sheet's, from the same functions; the last
    three columns are the owner's and stay empty."""
    def dec(v, places=1):
        return "" if v is None else f"{float(v):.{places}f}"

    lines = ["\t".join(COMPACT_HEAD)]
    for it in items:
        code = it["source_code"]
        row = pool_by_code[code]
        db = db_by_code.get(code)
        if it["by_weight"]:
            unit = "grams"
        else:
            unit = f"{it['unit_label']} {float(it['unit_grams']):g}g"
        whole = {"y": "true", "n": "false"}.get(it["whole_only"], "")
        flags = "".join(letter for letter in SHEET.FLAG_LETTERS if letter in it["flags"])
        curated = ""
        if db is not None:
            curated = (f"E q={db['quality'] if db['quality'] is not None else ''}"
                       f" max_g={dec(db['max_g'], 0)} prep={db['prep'] if db['prep'] is not None else ''}"
                       f" kosher={db['kosher'] or ''}")
        lines.append("\t".join([
            code,
            " ".join(str(it["name_he"]).split()),
            it["family"],
            str(row["p2"]),
            dec(it["kcal"], 0), dec(it["protein_g"]), dec(it["fat_g"]), dec(it["fiber_g"]),
            str(row["source"]),
            it["kosher"] or "",
            unit,
            "true" if it["by_weight"] else "false",
            whole,
            "true" if it["supp"] else "false",
            flags,
            curated,
            "", "", "",
        ]))
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--codes", required=True, help="one source_code per line")
    parser.add_argument("--out", default=None,
                        help="default db/tagging_sheet_report.txt, .tsv with --compact")
    parser.add_argument("--compact", action="store_true",
                        help="one tab-separated line per item instead of the wide sheet")
    args = parser.parse_args()

    codes = read_codes(args.codes)
    url = load_database_url()

    try:
        conn_ctx = psycopg.connect(url, row_factory=dict_row)
    except psycopg.OperationalError as exc:
        sys.exit(f"Cannot connect to {mask_dsn(url)}\n{exc}")

    out = io.StringIO()

    with conn_ctx as conn:
        with conn.cursor() as cur:
            # First statement in the transaction: any write added here later
            # fails loudly instead of running quietly.
            cur.execute("SET TRANSACTION READ ONLY")

            cur.execute("SELECT count(*) AS n FROM food_curation")
            curation_before = cur.fetchone()["n"]

            cur.execute(POOL_SQL)
            pool_by_code = {str(r["source_code"]): r for r in cur.fetchall()}

            cur.execute(SQL_CURATION, (codes,))
            db_by_code = {str(r["source_code"]): r for r in cur.fetchall()}

        # ---- stop point 4: every code must be in 07's pool ----------------
        missing = [c for c in codes if c not in pool_by_code]
        if missing:
            sys.exit(f"STOP 4: {len(missing)} code(s) not in the POOL_SQL pool: {missing}")

        # ---- the same shape 11 hands to build_items --------------------------
        selected = {"fat": [], "protein": []}
        unmapped = []
        for code in codes:
            row = pool_by_code[code]
            family = CAND.family_of(row)
            if family is None:
                unmapped.append(row)
            else:
                selected[family[1]].append((family[0], row))

        servings_by_code = {}
        components_by_code = {}
        with conn.cursor(row_factory=tuple_row) as cur:
            cur.execute(EXPORT.SQL_SERVINGS, (codes,))
            for source_code, mida_code, label, plural, grams in cur.fetchall():
                servings_by_code.setdefault(source_code, []).append(
                    (mida_code, label, plural, grams))
            cur.execute(SHEET.SQL_COMPONENTS, (codes,))
            for source_code, n in cur.fetchall():
                components_by_code[source_code] = n

        items = SHEET.build_items(selected, servings_by_code, components_by_code)
        all_items = items["fat"] + items["protein"]

        if args.compact:
            out.write(render_compact(all_items, pool_by_code, db_by_code))
        else:
            title = "/".join(sorted({it["category"] for it in all_items})).upper() or "ITEMS"
            # ---- the sheet --------------------------------------------------------
            out.write("TAGGING SHEET — the given code list, with what the code can "
                      "propose and what the database already holds\n")
            out.write("Generated by db/15_tagging_sheet.py. READ-ONLY: nothing was "
                      "written to the database.\n")
            out.write(f"Codes: {args.codes} — {len(codes)} codes, in the order of the "
                      "block-4 table.\n")
            out.write("\n  PROPOSED BY THE CODE (11_curation_sheet.build_items, unchanged)\n"
                      "    fam     §5.5 family number, from class_code (07.family_of)\n"
                      "    ksh     kosher by family — a PROPOSAL; blank where class_code "
                      "cannot answer\n"
                      "    sup     family = protein powders (§5.4)\n"
                      "    bw      by_weight: u = a serving unit was found · g = grams "
                      "(09.choose_unit)\n"
                      "    unit    the winning serving row and its grams\n"
                      "    wh      whole_only from the unit family: y / n; blank when "
                      "by_weight\n"
                      "    tags    BLANK — no function in db/ proposes tags\n"
                      f"    {FLAGS_SHOWN}    K kcal_outlier? · F fiber? · V verify_queue? · "
                      "C container_21? (11's mask, four of its six letters)\n"
                      "  IN DB — the food_curation row as stored, for codes curated in 3d; "
                      "blank = no row\n"
                      "    cat ksh max_g bw wh prep tags allergens — allergens with a "
                      "trailing ? = allergens_reviewed_at IS NULL\n"
                      "  OWNER FILLS\n"
                      "    max_g   §5.0 makes it mandatory at curation; no source in the "
                      "data\n"
                      "    prep    not something a nutritional database carries\n"
                      "  · = the code has no source for this cell.   _ = the owner fills "
                      "it in 5d.\n")
            out.write("  Line width is @WIDTH@ characters — paste into a monospace block, "
                      "or take one family at a time.\n")

            out.write("\n\n" + RULE + "\n")
            out.write(f"▸ {title} — {len(all_items)} rows, grouped by §5.5 family\n")
            out.write(RULE + "\n")
            for label, _cat, quota, _m, _f in FAMILIES:
                picked = [it for it in all_items if it["family"] == label]
                if not picked:
                    continue
                out.write(f"\n  §5.5 #{FAMILY_NO[label]} · {label} — {len(picked)} "
                          f"(quota {quota})  [{CAND.describe_floors(label)}]\n")
                out.write("  " + HEAD + "\n")
                out.write("  " + "-" * len(HEAD) + "\n")
                for it in picked:
                    code = it["source_code"]
                    out.write("  " + render_row(it, db_by_code.get(code)).rstrip() + "\n")
                    out.write("        " + render_servings(servings_by_code.get(code, [])) + "\n")
            if unmapped:
                out.write(f"\n  NO §5.5 FAMILY — {len(unmapped)} rows family_of() returns "
                          "None for (kosher-excluded or unmatched class_code)\n")
                for row in unmapped:
                    out.write(f"    {row['source_code']}  {pad_name(row['name_he'])}  "
                              f"{row['class_code']}\n")

        with conn.cursor() as cur:
            cur.execute("SELECT count(*) AS n FROM food_curation")
            curation_after = cur.fetchone()["n"]

        # Never commit. The transaction is READ ONLY — belt and braces.
        conn.rollback()

    n_eligible = sum(1 for c in codes if c in db_by_code and db_by_code[c]["menu_eligible"])
    n_curated_not_eligible = sum(1 for c in codes
                                 if c in db_by_code and not db_by_code[c]["menu_eligible"])
    n_new = sum(1 for c in codes if c not in db_by_code)

    counts = (f"{len(codes)} codes · {len(codes) - len(missing)} in the 07 pool · "
              f"{n_eligible} menu_eligible · {n_new} with no curation row"
              + (f" · {n_curated_not_eligible} curated but not eligible"
                 if n_curated_not_eligible else "")
              + f" · {len(unmapped)} without a §5.5 family")

    if args.compact:
        tsv = out.getvalue()
        out_path = Path(args.out) if args.out else HERE / "tagging_sheet_report.tsv"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(tsv, encoding="utf-8")
        raw = out_path.read_bytes()
        print(tsv, end="")
        print(f"\n▸ COUNTS — {counts}")
        print("  Blank by design — no existing function computes: quality (§5.3, manual) · max_g · prep")
        print(f"▸ Read-only proof — food_curation {curation_before} rows before, "
              f"{curation_after} after. No curation row was written.")
        print(f"\n✔ Saved: {out_path} — {len(raw)} bytes · sha256 {hashlib.sha256(raw).hexdigest()}")
        return

    out.write("\n\n" + RULE + "\n")
    out.write("▸ COUNTS\n")
    out.write(RULE + "\n")
    out.write(f"  {counts}\n")
    out.write("  Blank by design — no existing function computes: tags\n")
    out.write("  Owner fills: max_g · prep\n")
    out.write(f"\n▸ Read-only proof — food_curation {curation_before} rows before, "
              f"{curation_after} after. No curation row was written.\n")

    # The width is a property of the finished sheet — the 11 mechanism.
    text = out.getvalue()
    assert text.count("@WIDTH@") == 1
    width = max(len(line) for line in text.splitlines())
    assert all(len(line) < width for line in text.splitlines() if "@WIDTH@" in line)
    text = text.replace("@WIDTH@", str(width))

    out_path = Path(args.out) if args.out else HERE / "tagging_sheet_report.txt"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    raw = out_path.read_bytes()
    print(text)
    print(f"\n✔ Saved: {out_path} — {len(raw)} bytes · sha256 {hashlib.sha256(raw).hexdigest()}")


if __name__ == "__main__":
    main()
