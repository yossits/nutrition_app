# db/_compare_export.py - the delta gate of the database-dependent regression suite.
#
#   python db/_compare_export.py BEFORE.py AFTER.py [--expect-added CODES.txt]
#
# BEFORE and AFTER are two exports in the format of spike/menu_foods.py, the file
# db/09_export_menu_foods.py writes: a module holding FOODS, a list of dicts,
# one per menu_eligible item. Each is loaded as a module by path and its records
# are keyed by source_code. Nothing here touches the database.
#
# What it answers (decisions.md 11.09.2026, measurements.md "block 5"): after a
# migration that touches food_curation, the export must hold exactly the rows it
# held before plus the codes the migration made eligible - every pre-existing
# record identical field by field, none gone, and the new set equal to the
# expected list. The positional `id` (open-questions.md #36) is ignored: 09
# numbers records by position, so every insertion renumbers the tail of the
# file, and a comparison that read `id` would report the whole tail as changed.
#
# Output is ASCII only, the way _apply_migration.py prints, so the report survives
# a cp1252 console with stdout redirected (block 5b prime).
#
# Exit 0 only if: nothing disappeared, every common record is identical, and -
# when --expect-added is given - the added set equals the codes in that file
# (one code per line, # starts a comment). Otherwise STOP: lines and exit 1.
import importlib.util
import sys
from pathlib import Path

USAGE = "usage: python db/_compare_export.py BEFORE.py AFTER.py [--expect-added CODES.txt]"
IGNORED = ("id",)


def parse_args(argv):
    paths, expect = [], None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--expect-added":
            if expect is not None or i + 1 >= len(argv):
                raise SystemExit(f"STOP: --expect-added takes one path - {USAGE}")
            expect = argv[i + 1]
            i += 2
        elif a.startswith("-"):
            raise SystemExit(f"STOP: unknown argument {a!r} - {USAGE}")
        else:
            paths.append(a)
            i += 1
    if len(paths) != 2:
        raise SystemExit(f"STOP: pass exactly two export paths, got {paths} - {USAGE}")
    for p in paths + ([expect] if expect else []):
        if not Path(p).is_file():
            raise SystemExit(f"STOP: not a file: {p!r} - {USAGE}")
    return paths[0], paths[1], expect


def load_export(path):
    """Load an export module by path and key its FOODS by source_code."""
    spec = importlib.util.spec_from_file_location(f"export_{abs(hash(path))}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    records = getattr(module, "FOODS", None)
    if not isinstance(records, list):
        raise SystemExit(f"STOP: {path} has no FOODS list")
    by_code = {}
    for n, r in enumerate(records, 1):
        code = r.get("source_code")
        if code is None:
            raise SystemExit(f"STOP: {path} record {n} carries no source_code")
        if code in by_code:
            raise SystemExit(f"STOP: {path} holds source_code {code} twice")
        by_code[str(code)] = r
    return by_code


def read_codes(path):
    codes = []
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        s = raw.strip()
        if s and not s.startswith("#"):
            codes.append(s)
    return set(codes)


def by_int(code):
    return (0, int(code)) if code.isdigit() else (1, code)


def field_differences(a, b):
    """Field names whose values differ, id excluded. A field present on one
    side only counts as a difference under its own name."""
    diffs = []
    for key in sorted(set(a) | set(b)):
        if key in IGNORED:
            continue
        if key not in a or key not in b or a[key] != b[key]:
            diffs.append(key)
    return diffs


def main():
    before_path, after_path, expect_path = parse_args(sys.argv[1:])
    before = load_export(before_path)
    after = load_export(after_path)

    common = sorted(set(before) & set(after), key=by_int)
    added = sorted(set(after) - set(before), key=by_int)
    gone = sorted(set(before) - set(after), key=by_int)

    changed = []
    for code in common:
        diffs = field_differences(before[code], after[code])
        if diffs:
            changed.append((code, diffs))

    print(f"records: before {len(before)} - after {len(after)}")
    print(f"common: {len(common)} - identical {len(common) - len(changed)}, "
          f"changed {len(changed)} (id ignored)")
    print(f"added: {len(added)}" + (f" - {', '.join(added)}" if added else ""))
    print(f"gone: {len(gone)}" + (f" - {', '.join(gone)}" if gone else ""))

    failures = []
    for code, diffs in changed:
        for field in diffs:
            print(f"  changed {code} {field}: {before[code].get(field)!r} -> {after[code].get(field)!r}")
        failures.append(f"STOP: {code} changed in {', '.join(diffs)}")
    for code in gone:
        failures.append(f"STOP: {code} disappeared from the export")
    if expect_path is not None:
        expected = read_codes(expect_path)
        unexpected = sorted(set(added) - expected, key=by_int)
        missing = sorted(expected - set(added), key=by_int)
        if unexpected:
            failures.append(f"STOP: added but not expected: {', '.join(unexpected)}")
        if missing:
            failures.append(f"STOP: expected but not added: {', '.join(missing)}")
        if not unexpected and not missing:
            print(f"expected additions: {len(expected)} - the added set matches exactly")

    if failures:
        for line in failures:
            print(line)
        print(f"FAIL: {len(failures)} problem(s)")
        sys.exit(1)
    print("OK: nothing disappeared, every common record identical, "
          + ("added set as expected" if expect_path else f"{len(added)} added"))


if __name__ == "__main__":
    main()
