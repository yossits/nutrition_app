# -*- coding: utf-8 -*-
"""The canonical snapshot - nine counts over food_curation and its views. Read-only.

  python db\\_snapshot_ro.py
  python db\\_snapshot_ro.py --expect "423 · 264 · 105 · 37 · 44 · 78 · 264 · 0 · 0"

Prints the resolved path of the imported _audit_block7a, the masked DSN (from
load_database_url, as main() there does), transaction_read_only from inside query(),
the nine values as `a · b · c · d · e · f · g · h · i`, and each next to its name.

Every statement runs through query() from db/_audit_block7a.py: its own transaction,
SET TRANSACTION READ ONLY, always rolled back. SNAPSHOT_SQL, SNAPSHOT_NAMES and
query() are imported from there, not copied, so the snapshot has one definition.
EXPECTED_SNAPSHOT there is not used; what is expected comes from --expect.

Why it exists: open-questions.md #62, closed 19.09.2026. Until then every state
report ran a hand-made scratch copy whose db/ path pointed at one worktree's db/.
Here db/ is resolved from __file__, so each worktree runs its own db/.

--expect takes nine integers separated by "·", commas or whitespace. Exit codes:
  0  snapshot taken; with --expect, it matches
  2  it does not match --expect - expected and measured are printed
  1  bad arguments, DATABASE_URL missing, or no connection

Writes nothing - not to the database, not to disk. sys.dont_write_bytecode is set
before the import, so no __pycache__ appears under db/.
"""

import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

import _audit_block7a  # noqa: E402  exits with an install hint if psycopg is missing
import psycopg  # noqa: E402
from _audit_block7a import SNAPSHOT_NAMES, SNAPSHOT_SQL, query  # noqa: E402
from _env import load_database_url, mask_dsn  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

USAGE = 'usage: _snapshot_ro.py [--expect "a · b · c · d · e · f · g · h · i"]'


def parse_args(argv):
    """The expected tuple, or None without --expect. Anything else exits 1."""
    if not argv:
        return None
    if len(argv) == 2 and argv[0] == "--expect":
        raw = argv[1]
    elif len(argv) == 1 and argv[0].startswith("--expect="):
        raw = argv[0][len("--expect="):]
    else:
        sys.exit(USAGE)
    parts = [p for p in re.split(r"[\s,·]+", raw) if p]
    if len(parts) != len(SNAPSHOT_NAMES) or not all(re.fullmatch(r"[0-9]+", p) for p in parts):
        sys.exit(f"--expect needs {len(SNAPSHOT_NAMES)} integers, got {raw!r}\n{USAGE}")
    return tuple(int(p) for p in parts)


def main():
    expected = parse_args(sys.argv[1:])
    print(f"_audit_block7a: {Path(_audit_block7a.__file__).resolve()}")
    url = load_database_url()
    try:
        conn = psycopg.connect(url, autocommit=True)
    except psycopg.OperationalError as exc:
        sys.exit(f"Cannot connect to {mask_dsn(url)}\n{exc}")

    with conn:
        _, ro = query(conn, "SHOW transaction_read_only")
        _, rows = query(conn, SNAPSHOT_SQL)
    values = tuple(int(v) for v in rows[0])

    print(f"transaction_read_only inside query(): {ro[0][0]}")
    print(" · ".join(str(v) for v in values))
    for name, v in zip(SNAPSHOT_NAMES, values):
        print(f"  {name} = {v}")

    if expected is not None:
        if values != expected:
            print(f"MISMATCH\n  expected {' · '.join(map(str, expected))}\n  measured {' · '.join(map(str, values))}")
            sys.exit(2)
        print("matches --expect")


if __name__ == "__main__":
    main()
