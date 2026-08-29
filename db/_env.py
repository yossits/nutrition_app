# -*- coding: utf-8 -*-
"""Where the database secret comes from, for 03_load_source.py and 04_transform.py.

The rule: .env wins over the ambient environment.

That is the opposite of python-dotenv's default, and the inversion is
deliberate. DATABASE_URL is persisted on this machine at User scope (setx), so
it reappears in every new shell. Anything that merely fills in a *missing*
variable would therefore never fire, and .env would look loaded while the stale
value was being used — a failure that shows up as "password authentication
failed" against a DSN nobody edited.

Three things this handles that a two-line reader does not:

  * Encoding. A .env written by PowerShell 5.1 redirection (`... > .env`) lands
    as UTF-16 LE with a BOM. Read as UTF-8 it is gibberish, and the parse fails
    in a way that looks like a missing key rather than a wrong encoding. This
    cost a session already — see docs/work/2026-08-27-food-db-import.md. The
    BOM is sniffed, so both encodings work.
  * Location. The repository is worked on in git worktrees under
    .claude/worktrees/. .env is untracked, so it exists only in the main
    checkout — next to the script is the wrong place to look. The search walks
    up from this file until it finds one.
  * Masking. The DSN carries the password. mask_dsn() is what error messages
    print; the value itself is never logged.

No dependency on python-dotenv: it does not solve the encoding trap above, and
requirements.txt is deliberately near-empty.
"""

import os
import sys
from pathlib import Path

ENV_FILENAME = ".env"


def _read_text(path):
    """Decode .env by sniffing the BOM. UTF-16 is the PowerShell 5.1 default."""
    raw = path.read_bytes()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16")
    return raw.decode("utf-8-sig")


def find_env_file(start=None):
    """Walk up from `start` (default: this file) looking for a .env."""
    here = Path(start or __file__).resolve()
    for directory in [here] + list(here.parents):
        if directory.is_dir():
            candidate = directory / ENV_FILENAME
            if candidate.is_file():
                return candidate
    return None


def parse_env_file(path):
    """Minimal KEY=VALUE parser. No interpolation, no export, no multiline."""
    values = {}
    for line in _read_text(path).splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def mask_dsn(dsn):
    """postgresql://user:secret@host/db → postgresql://user:***@host/db.

    Anything unparseable is reduced to a placeholder rather than echoed: a DSN
    that failed to parse is exactly the one most likely to be malformed in a way
    that puts the password somewhere unexpected.
    """
    if not dsn:
        return "<unset>"
    try:
        scheme, _, rest = dsn.partition("://")
        if not rest:
            return "<unparseable DSN>"
        userinfo, at, hostpart = rest.rpartition("@")
        if not at:
            return f"{scheme}://{hostpart}"
        user, colon, _password = userinfo.partition(":")
        return f"{scheme}://{user}{':***' if colon else ''}@{hostpart}"
    except Exception:
        return "<unparseable DSN>"


def load_database_url(verbose=True):
    """Return the DSN, preferring .env. Exits with a masked message if absent.

    Prints which source was used and the masked DSN — never the value.
    """
    env_path = find_env_file()
    if env_path is not None:
        value = parse_env_file(env_path).get("DATABASE_URL")
        if value:
            # override: see the module docstring. The ambient value is stale on
            # this machine and would otherwise win silently.
            os.environ["DATABASE_URL"] = value
            if verbose:
                # ASCII only. This module gets imported before a caller has had
                # the chance to reconfigure stdout, and a cp1252 console kills
                # the process on an arrow rather than on anything that matters.
                print(f"DATABASE_URL <- {env_path}")
                print(f"  {mask_dsn(value)}")
            return value

    value = os.environ.get("DATABASE_URL")
    if value:
        if verbose:
            where = f"{env_path} has no DATABASE_URL" if env_path else "no .env found"
            print(f"DATABASE_URL <- process environment ({where})")
            print(f"  {mask_dsn(value)}")
        return value

    sys.exit(
        "DATABASE_URL is missing. Put it in .env at the repository root:\n"
        '  DATABASE_URL=postgresql://postgres.<ref>:<password>'
        "@aws-0-<region>.pooler.supabase.com:5432/postgres\n"
        "The session pooler on port 5432, not 6543: the direct host\n"
        "db.<ref>.supabase.co resolves to IPv6 only, and 6543 is the\n"
        "transaction pooler, which does not hold psycopg's prepared statements."
    )
