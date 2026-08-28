# -*- coding: utf-8 -*-
"""
03_load_source.py — loads the Tzameret source files into the src_* tables in
Postgres.

What it does:
  1. Connects using DATABASE_URL (environment variable)
  2. If the schema is missing — runs 01_food_db_schema.sql
  3. TRUNCATEs src_* and reloads the 4 data files from db/source
     (identified by their headers, not by file name)
  4. Validates the links, runs probe queries, and writes a report to
     db/load_report.txt

What it does not do:
  Does not touch the core tables (foods and friends). That is the transform —
  step 04, separate.

Run (from the repo root):
  cmd:         set DATABASE_URL=postgresql://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres
  PowerShell:  $env:DATABASE_URL = "postgresql://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres"
  python db\\03_load_source.py

Files are identified by their headers:
  shmmitzrach + protein            → src_foods                (ingredients, 85 columns)
  mitzbsisi                        → src_recipe_components    (recipe composition)
  smlmida + shmmida only           → src_mida                 (unit key)
  mmitzrach + mida + mishkal only  → src_servings             (grams per unit, per ingredient)
"""

import csv
import io
import json
import os
import sys
from pathlib import Path

try:
    import psycopg
except ImportError:
    sys.exit("psycopg is missing. Run:  pip install \"psycopg[binary]\"")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).parent
SCHEMA = HERE / "01_food_db_schema.sql"
BATCH = 1000
CSV_ENCODINGS = ("utf-8-sig", "utf-8", "cp1255")


# ------------------------------------------------------------- CSV reading --

def read_rows(path):
    raw = path.read_bytes()
    for enc in CSV_ENCODINGS:
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError(f"No encoding detected for {path.name}")
    rows = list(csv.reader(io.StringIO(text)))
    headers = [h.strip() for h in rows[0]]
    out = []
    for r in rows[1:]:
        if not any(c.strip() for c in r):
            continue
        d = {}
        for j, h in enumerate(headers):
            v = r[j].strip() if j < len(r) else ""
            d[h] = v if v != "" else None
        out.append(d)
    return headers, out


def classify(headers):
    h = set(headers)
    if "shmmitzrach" in h and "protein" in h:
        return "foods"
    if "mitzbsisi" in h:
        return "recipes"
    if h == {"smlmida", "shmmida"}:
        return "mida"
    if h == {"mmitzrach", "mida", "mishkal"}:
        return "servings"
    return None


# ----------------------------------------------------------------- Loading --

def load_foods(cur, rows):
    cur.execute("TRUNCATE src_foods")
    data = [(i + 1, r.get("Code"), json.dumps(r, ensure_ascii=False))
            for i, r in enumerate(rows)]
    cur.executemany(
        "INSERT INTO src_foods (row_num, code, raw) VALUES (%s, %s, %s)", data)
    return len(data)


def load_recipes(cur, rows):
    cur.execute("TRUNCATE src_recipe_components")
    data = [(i + 1, r.get("mmitzrach"), r.get("mitzbsisi"), r.get("mida"),
             r.get("mishkal"), json.dumps(r, ensure_ascii=False))
            for i, r in enumerate(rows)]
    cur.executemany(
        """INSERT INTO src_recipe_components
           (row_num, recipe_code, component_code, mida_code, amount, raw)
           VALUES (%s, %s, %s, %s, %s::numeric, %s)""", data)
    return len(data)


def load_mida(cur, rows):
    cur.execute("TRUNCATE src_mida")
    data = [(r.get("smlmida"), r.get("shmmida"),
             json.dumps(r, ensure_ascii=False)) for r in rows]
    cur.executemany(
        "INSERT INTO src_mida (mida_code, label_he, raw) VALUES (%s, %s, %s)", data)
    return len(data)


def load_servings(cur, rows):
    cur.execute("TRUNCATE src_servings")
    data = [(i + 1, r.get("mmitzrach"), r.get("mida"), r.get("mishkal"),
             json.dumps(r, ensure_ascii=False)) for i, r in enumerate(rows)]
    cur.executemany(
        """INSERT INTO src_servings (row_num, code, mida_code, grams, raw)
           VALUES (%s, %s, %s, %s::numeric, %s)""", data)
    return len(data)


LOADERS = {"foods": load_foods, "recipes": load_recipes,
           "mida": load_mida, "servings": load_servings}


# ------------------------------------------- Validation and probe queries --

CHECKS = [
    ("Row counts", """
        SELECT 'src_foods' t, count(*) n FROM src_foods
        UNION ALL SELECT 'src_recipe_components', count(*) FROM src_recipe_components
        UNION ALL SELECT 'src_mida', count(*) FROM src_mida
        UNION ALL SELECT 'src_servings', count(*) FROM src_servings"""),

    ("Link: recipe components (mitzbsisi) not in the ingredient file — must be 0", """
        SELECT count(DISTINCT rc.component_code)
        FROM src_recipe_components rc
        LEFT JOIN src_foods f ON f.code = rc.component_code
        WHERE f.code IS NULL"""),

    ("Link: recipes (mmitzrach) not in the ingredient file — must be 0", """
        SELECT count(DISTINCT rc.recipe_code)
        FROM src_recipe_components rc
        LEFT JOIN src_foods f ON f.code = rc.recipe_code
        WHERE f.code IS NULL"""),

    ("Link: unit weights for an ingredient that does not exist — must be 0", """
        SELECT count(DISTINCT s.code)
        FROM src_servings s LEFT JOIN src_foods f ON f.code = s.code
        WHERE f.code IS NULL"""),

    ("Link: mida codes in the weights file that are absent from the key — must be 0", """
        SELECT count(DISTINCT s.mida_code)
        FROM src_servings s LEFT JOIN src_mida m ON m.mida_code = s.mida_code
        WHERE m.mida_code IS NULL"""),

    ("How many entries are recipes (Code appearing as mmitzrach in the composition)", """
        SELECT count(*) FROM src_foods f
        WHERE EXISTS (SELECT 1 FROM src_recipe_components rc
                      WHERE rc.recipe_code = f.code)"""),

    ("Distinct base components across all recipes — the allergen tagging scope", """
        SELECT count(DISTINCT component_code) FROM src_recipe_components"""),

    ("Decoding: labels of the most common mida codes in the serving weights", """
        SELECT s.mida_code, m.label_he, count(*) n
        FROM src_servings s LEFT JOIN src_mida m ON m.mida_code = s.mida_code
        GROUP BY 1, 2 ORDER BY n DESC LIMIT 12"""),

    ("makor distribution + 2 sample names per value", """
        SELECT raw->>'makor' makor, count(*) n,
               string_agg(raw->>'shmmitzrach', ' · ')
                 FILTER (WHERE rn <= 2) samples
        FROM (SELECT raw, row_number() OVER
                (PARTITION BY raw->>'makor' ORDER BY row_num) rn
              FROM src_foods) t
        GROUP BY 1 ORDER BY n DESC"""),

    ("Ingredients with no carbohydrate value (excluded from foods, logged) — ~4 expected", """
        SELECT count(*) FROM src_foods WHERE raw->>'carbohydrates' IS NULL"""),

    ("Other empty macro fields — protein / total_fat / food_energy", """
        SELECT count(*) FILTER (WHERE raw->>'protein' IS NULL) p,
               count(*) FILTER (WHERE raw->>'total_fat' IS NULL) f,
               count(*) FILTER (WHERE raw->>'food_energy' IS NULL) k
        FROM src_foods"""),
]


def run_checks(cur, out):
    for title, sql in CHECKS:
        out.write(f"\n▸ {title}\n")
        cur.execute(sql)
        cols = [d.name for d in cur.description]
        for row in cur.fetchall():
            out.write("    " + " | ".join(
                "∅" if v is None else str(v) for v in row) + "\n")
        _ = cols


# -------------------------------------------------------------------- main --

def main():
    url = os.environ.get("DATABASE_URL")
    if not url:
        sys.exit("DATABASE_URL is missing. For example:\n"
                 "  cmd:         set DATABASE_URL=postgresql://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres\n"
                 "  PowerShell:  $env:DATABASE_URL = \"postgresql://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres\"")

    src = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "source"
    files = sorted(p for p in src.glob("*.csv"))
    if not files:
        sys.exit(f"No csv files inside {src}")

    out = io.StringIO()
    with psycopg.connect(url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass('public.src_foods')")
            if cur.fetchone()[0] is None:
                print("Schema is missing — running", SCHEMA.name)
                conn.execute(SCHEMA.read_text(encoding="utf-8"))

            seen = {}
            for p in files:
                headers, rows = read_rows(p)
                kind = classify(headers)
                if kind is None:
                    out.write(f"✗ {p.name}: headers not recognised — skipped. "
                              f"({', '.join(headers[:6])}…)\n")
                    continue
                if kind in seen:
                    out.write(f"✗ {p.name}: identified as {kind}, but {seen[kind]} "
                              f"was already loaded as that — skipped.\n")
                    continue
                with conn.cursor() as c2:
                    n = LOADERS[kind](c2, rows)
                seen[kind] = p.name
                out.write(f"✓ {p.name} → src_{kind if kind != 'recipes' else 'recipe_components'}: {n} rows\n")

            missing = set(LOADERS) - set(seen)
            if missing:
                out.write(f"\n⚠ No file found for: {', '.join(sorted(missing))} — "
                          f"validation will run only partially.\n")

            run_checks(cur, out)
        conn.commit()

    report = out.getvalue()
    (HERE / "load_report.txt").write_text(report, encoding="utf-8")
    print(report)
    print(f"\n✔ Saved: {HERE / 'load_report.txt'} — hand this over ahead of step 04 (transform).")


if __name__ == "__main__":
    main()
