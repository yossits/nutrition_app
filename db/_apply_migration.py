# db/_apply_migration.py - the migration runner CLAUDE.md section 5 requires.
#
#   python db/_apply_migration.py db/NN_name.sql           rehearsal: run everything, then rollback()
#   python db/_apply_migration.py db/NN_name.sql --apply   run everything, then commit() - one way, no undo
#
# Provenance. This is the runner that applied db/13_drop_price.sql in block 3z4g
# (03.09.2026, _scratch/block-3zayin4c/apply_13.py) and, re-pointed by two path
# lines, db/14_drop_three_fats.sql in block 4g (_scratch/block-4c/apply_14.py).
# Until block 4e it was copied per migration with the SQL path hard-coded; now
# the path is the first argument and the file lives next to _env.py. The run
# itself - the BEGIN;/COMMIT; check and strip, the transaction, the walk over
# result sets, the ROLLBACK/COMMIT branches - is that runner's, untouched.
#
# A migration wraps itself in BEGIN; ... COMMIT; the way db/12_cottage_swap.sql
# does, so it can be applied by any psql-like tool. This runner needs a
# rehearsal mode, and a COMMIT; executed inside a psycopg transaction would
# commit for real - so both statements are verified, stripped, and the body is
# run inside a transaction this process controls.
#
# Rehearsal is the default. --apply, spelled exactly so, is the only flag. A
# mistyped, wrong-case, doubled or unknown flag, a missing path, a path that is
# not a file, or a second positional stops the script before anything is read
# or connected, instead of silently choosing a branch.
#
# S4: the file must open with BEGIN; and close with COMMIT;, and after those two
# lines are cut nothing in the body may open, commit or roll back a transaction.
# Leading -- comments are skipped before looking for BEGIN;, because the file
# carries a header the way 12 does. Dollar-quoted blocks are removed before the
# body is scanned, since PL/pgSQL uses BEGIN as block syntax.
#
# Rehearsal safety. psycopg.Connection.__exit__ calls self.commit() when the
# block exits without an exception - verified from the installed source, 3.3.5.
# After rollback() there is no open transaction, so that commit() is a no-op,
# but this runner does not rely on that reasoning: in rehearse mode it closes
# the connection itself, and __exit__ returns early on a closed connection.
import os
import re
import sys

import psycopg

from _env import load_database_url, mask_dsn

USAGE = "usage: python db/_apply_migration.py <migration.sql> [--apply]"

# One positional SQL path, plus optionally --apply. Nothing else is accepted,
# and the checks run before the file is opened and before any connection.
_args = sys.argv[1:]
_flags = [a for a in _args if a.startswith("-")]
_paths = [a for a in _args if not a.startswith("-")]
_unknown = [a for a in _flags if a != "--apply"]
if _unknown:
    raise SystemExit(f"STOP: unknown argument {_unknown} - {USAGE}")
if len(_flags) > 1:
    raise SystemExit(f"STOP: --apply given {len(_flags)} times - {USAGE}")
if len(_paths) != 1:
    raise SystemExit(f"STOP: pass exactly one SQL path, got {_paths} - {USAGE}")
SQL_PATH = _paths[0]
if not os.path.isfile(SQL_PATH):
    raise SystemExit(f"STOP: not a file: {SQL_PATH!r} - {USAGE}")
REHEARSE = not _flags

raw = open(SQL_PATH, encoding="utf-8").read()
lines = raw.split("\n")

# ---- locate BEGIN; : first line that is neither blank nor a -- comment -------
first_idx = None
for i, l in enumerate(lines):
    s = l.strip()
    if not s or s.startswith("--"):
        continue
    first_idx = i
    break
if first_idx is None or lines[first_idx].strip() != "BEGIN;":
    raise SystemExit(f"STOP S4: first statement line is "
                     f"{None if first_idx is None else lines[first_idx]!r}, expected 'BEGIN;'")

# ---- locate COMMIT; : last non-blank line ------------------------------------
last_idx = None
for i in range(len(lines) - 1, -1, -1):
    if lines[i].strip():
        last_idx = i
        break
if lines[last_idx].strip() != "COMMIT;":
    raise SystemExit(f"STOP S4: last non-empty line is {lines[last_idx]!r}, expected 'COMMIT;'")

print(f"BEGIN;  at line {first_idx + 1}")
print(f"COMMIT; at line {last_idx + 1}")

body_lines = lines[:first_idx] + lines[first_idx + 1:last_idx] + lines[last_idx + 1:]
body = "\n".join(body_lines)

# ---- the body must not manage a transaction ---------------------------------
# Dollar quoting is checked first: an odd count, or a tagged $tag$ quote the
# simple $$ pair regex would miss, means the scan below cannot be trusted.
if body.count("$$") % 2 != 0:
    raise SystemExit(f"STOP S4: odd number of $$ markers ({body.count('$$')})")
tagged = re.findall(r"\$[A-Za-z_][A-Za-z0-9_]*\$", body)
if tagged:
    raise SystemExit(f"STOP S4: tagged dollar quotes present, the scan cannot be trusted: {set(tagged)}")
print(f"dollar quotes: {body.count('$$')} markers, {body.count('$$') // 2} balanced pairs, no tagged quotes")

probe = re.sub(r"\$\$.*?\$\$", " ", body, flags=re.S)
probe = re.sub(r"--[^\n]*", " ", probe)
# ON COMMIT DROP / DELETE ROWS / PRESERVE ROWS is a CREATE TEMP TABLE clause, not
# transaction control. db/12_cottage_swap.sql uses it too. Remove it before the
# scan the way $$ blocks are removed for PL/pgSQL's BEGIN, and count what was
# removed so it is visible rather than silently tolerated.
on_commit = re.findall(r"\bON\s+COMMIT\s+(?:DROP|DELETE\s+ROWS|PRESERVE\s+ROWS)\b", probe, flags=re.I)
probe = re.sub(r"\bON\s+COMMIT\s+(?:DROP|DELETE\s+ROWS|PRESERVE\s+ROWS)\b", " ", probe, flags=re.I)
print(f"ON COMMIT temp-table clauses ignored: {len(on_commit)} {on_commit}")

offenders = []
for kw in ("BEGIN", "COMMIT", "ROLLBACK", "SAVEPOINT", "START TRANSACTION", "END TRANSACTION"):
    hits = re.findall(r"\b" + kw.replace(" ", r"\s+") + r"\b", probe, flags=re.I)
    if hits:
        offenders.append((kw, len(hits)))
if offenders:
    raise SystemExit(f"STOP S4: transaction control left in the body: {offenders}")

# Belt and braces: no statement in the body may consist solely of a transaction
# control word, whatever the keyword scan above concluded.
for stmt in probe.split(";"):
    s = " ".join(stmt.split()).upper()
    if s in ("BEGIN", "COMMIT", "ROLLBACK", "END", "START TRANSACTION", "ABORT"):
        raise SystemExit(f"STOP S4: bare transaction statement in the body: {s!r}")
print("body carries no BEGIN / COMMIT / ROLLBACK / SAVEPOINT outside $$ blocks, comments and ON COMMIT clauses")
print(f"body: {len(body)} chars, {body.count(chr(10)) + 1} lines")

# ---- run --------------------------------------------------------------------
dsn = load_database_url()
print(f"\nmode: {'REHEARSE (rollback)' if REHEARSE else 'APPLY (commit)'}")

with psycopg.connect(dsn) as conn:
    print("autocommit:", conn.autocommit, " (False = this process owns the transaction)")
    with conn.cursor() as cur:
        cur.execute(body)
        n = 0
        while True:
            if cur.description is not None:
                cols = [d.name for d in cur.description]
                print(f"  result {n}: {cols} -> {cur.fetchall()}")
            n += 1
            if not cur.nextset():
                break
        print(f"  result sets walked: {n}")
    if conn.info.transaction_status is not None:
        print("  transaction status before the decision:", conn.info.transaction_status)
    if REHEARSE:
        conn.rollback()
        print("\nROLLBACK issued - nothing was written")
        conn.close()
        print("connection closed by the runner, so the context manager cannot commit")
    else:
        conn.commit()
        print("\nCOMMIT issued - the migration is applied")
print("connection closed:", "yes")
