# db/_compare_export.py - the delta gate of the database-dependent regression suite.
#
#   python db/_compare_export.py BEFORE.py AFTER.py [--expect-added CODES.txt]
#                                                   [--expect-changed CHANGES.tsv]
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
# --expect-changed (open-questions.md #51, block 8t-dalet) gives the same answer
# for a change made on purpose to records that already exist - a unit judgement,
# a max_g correction. It names, per record, the fields the change touches. The
# file follows the codes file of --expect-added - UTF-8, one entry per line,
# blank lines and lines starting with # skipped - and an entry is a source_code,
# a TAB, and the field names separated by commas, the way
# db/block6_protein_allergens.tsv puts a code and a list on one line:
#
#     3962<TAB>unit
#     2828<TAB>servings,unit
#
# A listed record must change in exactly its listed fields. A change in a field
# that is not listed fails and names the field: #52 was a servings change nobody
# made. A listed field that did not change fails too, as a missing addition does
# under --expect-added, and so does a listed code that is not in both exports.
# Stopped before anything is compared: a malformed line, a code or a field named
# twice, a field no record in either export carries, the ignored `id`, and a code
# also listed under --expect-added.
#
# Output is ASCII only, the way _apply_migration.py prints, so the report survives
# a cp1252 console with stdout redirected (block 5b prime).
#
# Exit 0 only if: nothing disappeared, every common record is identical - or,
# when --expect-changed is given, changed in exactly its listed fields - and,
# when --expect-added is given, the added set equals the codes in that file
# (one code per line, # starts a comment). Otherwise STOP: lines and exit 1.
import importlib.util
import sys
from pathlib import Path

USAGE = ("usage: python db/_compare_export.py BEFORE.py AFTER.py [--expect-added CODES.txt]"
         " [--expect-changed CHANGES.tsv]")
IGNORED = ("id",)


def parse_args(argv):
    paths, expect, changes = [], None, None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--expect-added":
            if expect is not None or i + 1 >= len(argv):
                raise SystemExit(f"STOP: --expect-added takes one path - {USAGE}")
            expect = argv[i + 1]
            i += 2
        elif a == "--expect-changed":
            if changes is not None or i + 1 >= len(argv):
                raise SystemExit(f"STOP: --expect-changed takes one path - {USAGE}")
            changes = argv[i + 1]
            i += 2
        elif a.startswith("-"):
            raise SystemExit(f"STOP: unknown argument {a!r} - {USAGE}")
        else:
            paths.append(a)
            i += 1
    if len(paths) != 2:
        raise SystemExit(f"STOP: pass exactly two export paths, got {paths} - {USAGE}")
    for p in paths + ([expect] if expect else []) + ([changes] if changes else []):
        if not Path(p).is_file():
            raise SystemExit(f"STOP: not a file: {p!r} - {USAGE}")
    return paths[0], paths[1], expect, changes


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


def read_changes(path):
    """--expect-changed entries as {source_code: frozenset of field names}.

    A code named twice stops, where --expect-added swallows a repeat into a set.
    A repeated code there says nothing new; here two lines for one record are two
    expectations, and merging them would widen what passes. A field named twice
    in one entry stops for the same reason a gate should not guess: 'unit,unit'
    reads as a second field that was meant and not written.
    """
    changes, problems = {}, []
    for n, raw in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        code, tab, rest = s.partition("\t")
        code = code.strip()
        fields = [f.strip() for f in rest.split(",")] if tab else []
        if not tab or not code or not fields or not all(fields):
            problems.append(f"line {n} is not CODE<TAB>field[,field...]: {s!r}")
        elif code in changes:
            problems.append(f"line {n} names {code} a second time")
        elif len(set(fields)) != len(fields):
            problems.append(f"line {n} names a field of {code} twice")
        else:
            changes[code] = frozenset(fields)
    if problems:
        raise SystemExit(f"STOP: --expect-changed {path} - " + "; ".join(problems))
    return changes


def check_changes(changes, before, after, expected_added):
    """What stops before any comparison: field names no record carries, the
    ignored id, and a code expected both as an addition and as a change."""
    named = {f for fields in changes.values() for f in fields}
    carried = {key for side in (before, after) for record in side.values() for key in record}
    problems = []
    unknown = sorted(named - carried)
    if unknown:
        problems.append(f"no record in either export carries {', '.join(unknown)}")
    ignored = sorted(named & set(IGNORED))
    if ignored:
        problems.append(f"{', '.join(ignored)} is ignored by the comparison and cannot be expected to change")
    both = sorted(set(changes) & expected_added, key=by_int)
    if both:
        problems.append(f"listed under both --expect-added and --expect-changed: {', '.join(both)}")
    if problems:
        raise SystemExit("STOP: --expect-changed - " + "; ".join(problems))


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
    before_path, after_path, expect_path, changes_path = parse_args(sys.argv[1:])
    changes = read_changes(changes_path) if changes_path is not None else None
    before = load_export(before_path)
    after = load_export(after_path)
    if changes is not None:
        check_changes(changes, before, after,
                      read_codes(expect_path) if expect_path is not None else set())

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
        if changes is None or code not in changes:
            failures.append(f"STOP: {code} changed in {', '.join(diffs)}")
        else:
            unlisted = [f for f in diffs if f not in changes[code]]
            if unlisted:
                failures.append(f"STOP: {code} changed in {', '.join(unlisted)}, "
                                f"which --expect-changed does not list for it")
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
    if changes is not None:
        diffs_by_code = dict(changed)
        change_failures = []
        for code in sorted(changes, key=by_int):
            listed = changes[code]
            if code not in before and code not in after:
                change_failures.append(f"STOP: {code} is listed in --expect-changed but is in neither export")
            elif code not in before or code not in after:
                side = "added" if code in after else "gone"
                change_failures.append(f"STOP: {code} is listed in --expect-changed but was {side}, not changed")
            elif code not in diffs_by_code:
                change_failures.append(f"STOP: {code} expected to change in {', '.join(sorted(listed))}, "
                                       f"but the record is identical")
            else:
                did_not = sorted(listed - set(diffs_by_code[code]))
                if did_not:
                    change_failures.append(f"STOP: {code} expected to change in {', '.join(did_not)}, "
                                           f"which did not change")
        unlisted_any = any(code in changes and any(f not in changes[code] for f in diffs)
                           for code, diffs in changed)
        if not change_failures and not unlisted_any:
            print(f"expected changes: {len(changes)} - each listed record changed in exactly its listed fields")
        failures.extend(change_failures)

    if failures:
        for line in failures:
            print(line)
        print(f"FAIL: {len(failures)} problem(s)")
        sys.exit(1)
    if changes is None:
        print("OK: nothing disappeared, every common record identical, "
              + ("added set as expected" if expect_path else f"{len(added)} added"))
    else:
        print("OK: nothing disappeared, every common record identical or changed exactly as listed, "
              + ("added set as expected" if expect_path else f"{len(added)} added"))


if __name__ == "__main__":
    main()
