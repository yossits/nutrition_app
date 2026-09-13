# -*- coding: utf-8 -*-
"""
_trace_ceilings.py - where a curation max_g came from. Read-only.

  python db\\_trace_ceilings.py CODE [CODE ...]

Opened in block 8t-alef for open-questions.md #50 and #53. For each code it prints:

  * every row for that code that a migration in db/*.sql writes into
    food_curation - an INSERT ... VALUES tuple, read against the INSERT's own
    column list, or an UPDATE that sets max_g - with the file, the file's first
    line (the block it names) and the max_g written there;
  * max_g in the database today, and the unit choose_unit() picks today;
  * the entries of the spike's MAX_G table (spike/foods.py) equal to that max_g.

A code with no writing row in db/*.sql was curated before migrations were kept in
the repository (blocks 3d and 3h). The SQL is scanned, not executed: quotes,
dollar-quoted bodies and -- comments are honoured, nothing else of SQL is.

The unit comes from _audit_units.py, which takes choose_unit() and SQL_SERVINGS
from 09_export_menu_foods.py; nothing about units is re-derived here.
"""

import glob
import importlib.util
import re
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
SPIKE_FOODS = HERE.parent / "spike" / "foods.py"


def load_by_path(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


AUDIT = load_by_path("audit_units", HERE / "_audit_units.py")


# ---------------------------------------------------------------------------
#  A scanner that knows just enough SQL: '...' with '' escapes, $$...$$, -- to EOL.

def strip_comments(sql):
    out, i, n = [], 0, len(sql)
    while i < n:
        if sql.startswith("--", i):
            j = sql.find("\n", i)
            i = n if j < 0 else j
        elif sql[i] == "'":
            j = i + 1
            while j < n:
                if sql[j] == "'" and sql.startswith("''", j):
                    j += 2
                elif sql[j] == "'":
                    break
                else:
                    j += 1
            out.append(sql[i:j + 1])
            i = j + 1
        elif sql.startswith("$$", i):
            j = sql.find("$$", i + 2)
            j = n if j < 0 else j + 2
            out.append(sql[i:j])
            i = j
        else:
            out.append(sql[i])
            i += 1
    return "".join(out)


def split_top(text, sep):
    """Split on sep at parenthesis depth 0, outside quotes and $$ bodies."""
    parts, depth, start, i, n = [], 0, 0, 0, len(text)
    while i < n:
        c = text[i]
        if c == "'":
            i += 1
            while i < n and not (text[i] == "'" and not text.startswith("''", i)):
                i += 2 if text.startswith("''", i) else 1
        elif text.startswith("$$", i):
            j = text.find("$$", i + 2)
            i = n if j < 0 else j + 1
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
        elif c == sep and depth == 0:
            parts.append(text[start:i])
            start = i + 1
        i += 1
    parts.append(text[start:])
    return parts


def tuples_of(values_body):
    """The top-level (...) groups of a VALUES body."""
    groups = []
    for chunk in split_top(values_body, ","):
        s = chunk.strip()
        if s.startswith("(") and s.endswith(")"):
            groups.append(s[1:-1])
    return groups


def unquote(value):
    v = value.strip()
    return v[1:-1].replace("''", "'") if len(v) >= 2 and v[0] == v[-1] == "'" else v


INSERT_RE = re.compile(r"^\s*INSERT\s+INTO\s+food_curation\s*\(([^)]*)\)\s*VALUES\s*(.*)$",
                       re.IGNORECASE | re.DOTALL)
UPDATE_RE = re.compile(r"^\s*UPDATE\s+food_curation\b(.*)$", re.IGNORECASE | re.DOTALL)
SET_MAX_RE = re.compile(r"\bmax_g\s*=\s*([^,\s]+)", re.IGNORECASE)


def scan_migrations(codes):
    found = {c: [] for c in codes}
    for path in sorted(glob.glob(str(HERE / "*.sql"))):
        raw = Path(path).read_text(encoding="utf-8")
        first_line = raw.splitlines()[0] if raw else ""
        sql = strip_comments(raw)
        for stmt in split_top(sql, ";"):
            m = INSERT_RE.match(stmt)
            if m:
                cols = [c.strip() for c in m.group(1).split(",")]
                for tup in tuples_of(m.group(2)):
                    vals = [v.strip() for v in split_top(tup, ",")]
                    if len(vals) != len(cols):
                        continue
                    row = dict(zip(cols, vals))
                    code = unquote(row.get("source_code", ""))
                    if code in found:
                        found[code].append((Path(path).name, first_line, "INSERT",
                                            row.get("max_g", "(no max_g column)")))
                continue
            m = UPDATE_RE.match(stmt)
            if m and SET_MAX_RE.search(stmt):
                for code in codes:
                    if re.search(r"'" + re.escape(code) + r"'", stmt):
                        found[code].append((Path(path).name, first_line, "UPDATE",
                                            SET_MAX_RE.search(stmt).group(1)))
    return found


SQL_ROW = """
    SELECT f.source_code, f.name_he, c.category::text, f.kcal, c.max_g,
           c.whole_only, c.by_weight, c.menu_eligible
    FROM foods f JOIN food_curation c ON c.source_code = f.source_code
    WHERE f.source_code = ANY(%s)
"""


def main():
    codes = sys.argv[1:]
    if not codes:
        sys.exit("usage: python db\\_trace_ceilings.py CODE [CODE ...]")

    spike = load_by_path("spike_foods", SPIKE_FOODS)
    max_g_table = spike.MAX_G
    print(f"spike/foods.py MAX_G: {len(max_g_table)} entries - "
          + " · ".join(f"{k} {v}" for k, v in max_g_table.items()))

    found = scan_migrations(codes)

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
            cur.execute(SQL_ROW, (codes,))
            rows = {r[0]: r for r in cur.fetchall()}
            cur.execute(AUDIT.SQL_SERVINGS, (codes,))
            servings = {}
            for source_code, mida, label, plural, grams in cur.fetchall():
                servings.setdefault(source_code, []).append((mida, label, plural, grams))

    missing = [c for c in codes if c not in rows]
    print()
    print("code | name | category | max_g today | whole_only | by_weight | unit today (mida, label, g)"
          " | max_g / unit | spike MAX_G entries equal to max_g | writing rows in db/*.sql")
    for code in codes:
        if code not in rows:
            continue
        _, name, category, kcal, max_g, whole_only, by_weight, eligible = rows[code]
        unit = AUDIT.choose_unit(servings.get(code, []), None if kcal is None else float(kcal), code)
        unit_s = "-" if unit is None else f"({unit[0]}, {unit[1]}, {float(unit[3]):g})"
        ratio = ("-" if unit is None or max_g is None
                 else f"{float(max_g) / float(unit[3]):.3f}")
        equal = [k for k, v in max_g_table.items() if max_g is not None and float(v) == float(max_g)]
        writes = found[code]
        writes_s = ("none - curated before migrations were kept in the repo" if not writes else
                    " · ".join(f"{f} {kind} max_g={g} [{first}]" for f, first, kind, g in writes))
        print(f"{code} | {name} | {category} | {AUDIT.fmt_g(max_g)} | {whole_only} | {by_weight} | "
              f"{unit_s} | {ratio} | {', '.join(equal) or 'none'} | {writes_s}")
    print()
    print(f"codes asked: {len(codes)} · found in food_curation: {len(codes) - len(missing)}"
          + (f" · missing: {', '.join(missing)}" if missing else ""))
    print(f"codes with a writing row in db/*.sql: {sum(1 for c in codes if found[c])} · "
          f"without: {sum(1 for c in codes if not found[c])}")
    print(f"codes whose max_g equals a spike MAX_G value: "
          f"{sum(1 for c in codes if c in rows and rows[c][4] is not None and any(float(v) == float(rows[c][4]) for v in max_g_table.values()))}")
    if missing:
        sys.exit(1)


if __name__ == "__main__":
    main()
