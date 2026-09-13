# -*- coding: utf-8 -*-
"""
_compare_export_suite.py - the suite for db/_compare_export.py. No database.

  python db\\_compare_export_suite.py [--tool PATH] [--capture]

Block 8t-dalet (open-questions.md #51). The shape of the block-6s-a suite - a base
export, one variant export per case, expectation files beside them, one run of
the tool per case checked for its exit code - but kept in the repository this
time: the 6s-a fixtures live in _scratch/block-6a and were never committed.
Fixtures here are written to a temporary directory from the records below, not
taken from the database. Exit 0 only if every case holds.

Two groups:

  R  regression - the invocations the tool had before --expect-changed, each
     pinned to the exact stdout and exit code of the tool at c668e42. The new tool
     must reproduce them byte for byte.
  E  --expect-changed - the semantics of #51, including the two changes that
     named it: 3962's unit judgement from 8p-tet2, and 2828's servings reordering
     from #52.

--tool runs the cases against another copy of the tool, and --capture prints the
R results instead of checking them; that is how GOLDEN below was taken from the
c668e42 version.
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).parent
TOOL = HERE / "_compare_export.py"

# The keys of an exported record, in the order 09_export_menu_foods.py writes them.
KEYS = ("name", "he", "cat", "kcal", "protein", "fat", "carb", "kosher", "servings",
        "allergens", "tags", "prep", "complete", "supp", "quality", "unit", "by_weight",
        "whole_only", "max_g", "id", "menu_eligible", "source_code")


def record(i, code, cat, **values):
    r = dict(name=f"food {code}", he=f"food {code}", cat=cat, kcal=100.0, protein=5.0,
             fat=1.0, carb=20.0, kosher="parve", servings=[], allergens=set(), tags=set(),
             prep=0, complete=False, supp=False, quality=None, unit=None, by_weight=False,
             whole_only=False, max_g=None, id=i, menu_eligible=True, source_code=code)
    r.update(values)
    assert tuple(r) == KEYS, tuple(r)
    return r


def base():
    # 3962 and 2828 carry the fields of the two cases that named #51; the values
    # are modelled on 8p-tet2 and #52, not read from the database.
    return [
        record(1, "2828", "carb", servings=[("כוסות", 30.0), ("מנות קטנות", 30.0)],
               unit={"he": "כוס", "he_plural": "כוסות", "grams": 30.0}),
        record(2, "3663", "veg", whole_only=True, max_g=322.0,
               unit={"he": "יחידה בינונית", "he_plural": "יחידות בינוניות", "grams": 160.0}),
        record(3, "3962", "carb", max_g=240.0,
               unit={"he": "יחידה בינונית", "he_plural": "יחידות בינוניות", "grams": 100.0}),
    ]


def variant(*edits, drop=(), add=(), shift_ids=0):
    records = [dict(r) for r in base() if r["source_code"] not in drop]
    by_code = {r["source_code"]: r for r in records}
    for code, field, value in edits:
        by_code[code][field] = value
    for code in add:
        records.append(record(len(records) + 1, code, "veg"))
    for r in records:
        r["id"] += shift_ids
    return records


UNIT_3962 = ("3962", "unit", {"he": "כוס", "he_plural": "כוסות", "grams": 165.0})
SERVINGS_2828 = ("2828", "servings", [("מנות קטנות", 30.0), ("כוסות", 30.0)])
MAX_G_3663 = ("3663", "max_g", 320.0)

ADDED_RIGHT = ("--expect-added", "added.txt", "# one\n9001\n")
ADDED_9001 = ("--expect-added", "added.txt", "9001\n")


def changed_file(text):
    return ("--expect-changed", "changed.tsv", text)


# name -> (before, after, [(flag, file name, file text), ...])
CASES = {
    # ---- R: the tool as it stood ------------------------------------------------
    "R1 no flags, identical": (base(), base(), []),
    "R2 no flags, max_g changed": (base(), variant(MAX_G_3663), []),
    "R3 no flags, record gone": (base(), variant(drop=("3663",)), []),
    "R4 expect-added, matches": (base(), variant(add=("9001",)), [ADDED_RIGHT]),
    "R5 expect-added, wrong": (base(), variant(add=("9001",)), [("--expect-added", "added.txt", "9002\n")]),
    "R6 no flags, every id shifted": (base(), variant(shift_ids=1), []),
    # ---- E: --expect-changed ------------------------------------------------------
    "E1 3962 unit, as listed": (base(), variant(UNIT_3962), [changed_file("# 8p-tet2\n3962\tunit\n")]),
    "E2 #52: 2828 listed for unit, servings changed": (base(), variant(SERVINGS_2828),
                                                        [changed_file("2828\tunit\n")]),
    "E3 listed change did not happen": (base(), base(), [changed_file("3962\tunit\n")]),
    "E4 listed code in neither export": (base(), variant(UNIT_3962), [changed_file("3962\tunit\n99999\tunit\n")]),
    "E5 field no record carries": (base(), variant(UNIT_3962), [changed_file("3962\tunitt\n")]),
    "E6 unlisted record changed": (base(), variant(UNIT_3962, MAX_G_3663), [changed_file("3962\tunit\n")]),
    "E7 one of two listed fields did not change": (base(), variant(UNIT_3962),
                                                    [changed_file("3962\tunit,servings\n")]),
    "E8 both flags, both as listed": (base(), variant(UNIT_3962, add=("9001",)),
                                      [ADDED_9001, changed_file("3962\tunit\n")]),
    "E9 id listed": (base(), variant(shift_ids=1), [changed_file("3962\tid\n")]),
    "E10 code named twice": (base(), variant(UNIT_3962), [changed_file("3962\tunit\n3962\tmax_g\n")]),
    "E11 line without a TAB": (base(), variant(UNIT_3962), [changed_file("3962 unit\n")]),
    "E12 field named twice": (base(), variant(UNIT_3962), [changed_file("3962\tunit,unit\n")]),
    "E13 code under both flags": (base(), variant(add=("9001",)), [ADDED_9001, changed_file("9001\tunit\n")]),
    "E14 --expect-changed twice": (base(), variant(UNIT_3962),
                                   [changed_file("3962\tunit\n"), changed_file("3962\tunit\n")]),
    "E15 listed code was added": (base(), variant(add=("9001",)), [changed_file("9001\tunit\n")]),
}

# E cases: exit code, lines stdout must contain, and - for a stop at argument
# time - the text stderr must carry, with stdout empty because nothing was compared.
CHECKS = {
    "E1 3962 unit, as listed": (0, [
        "expected changes: 1 - each listed record changed in exactly its listed fields",
        "OK: nothing disappeared, every common record identical or changed exactly as listed, 0 added"], None),
    "E2 #52: 2828 listed for unit, servings changed": (1, [
        "STOP: 2828 changed in servings, which --expect-changed does not list for it",
        "STOP: 2828 expected to change in unit, which did not change",
        "FAIL: 2 problem(s)"], None),
    "E3 listed change did not happen": (1, [
        "STOP: 3962 expected to change in unit, but the record is identical",
        "FAIL: 1 problem(s)"], None),
    "E4 listed code in neither export": (1, [
        "STOP: 99999 is listed in --expect-changed but is in neither export",
        "FAIL: 1 problem(s)"], None),
    "E5 field no record carries": (1, [], "STOP: --expect-changed - no record in either export carries unitt"),
    "E6 unlisted record changed": (1, ["STOP: 3663 changed in max_g", "FAIL: 1 problem(s)"], None),
    "E7 one of two listed fields did not change": (1, [
        "STOP: 3962 expected to change in servings, which did not change",
        "FAIL: 1 problem(s)"], None),
    "E8 both flags, both as listed": (0, [
        "expected additions: 1 - the added set matches exactly",
        "expected changes: 1 - each listed record changed in exactly its listed fields",
        "OK: nothing disappeared, every common record identical or changed exactly as listed, added set as expected"],
        None),
    "E9 id listed": (1, [], "id is ignored by the comparison and cannot be expected to change"),
    "E10 code named twice": (1, [], "line 2 names 3962 a second time"),
    "E11 line without a TAB": (1, [], "line 1 is not CODE<TAB>field[,field...]"),
    "E12 field named twice": (1, [], "line 1 names a field of 3962 twice"),
    "E13 code under both flags": (1, [], "listed under both --expect-added and --expect-changed: 9001"),
    "E14 --expect-changed twice": (1, [], "STOP: --expect-changed takes one path"),
    "E15 listed code was added": (1, [
        "added: 1 - 9001",
        "STOP: 9001 is listed in --expect-changed but was added, not changed",
        "FAIL: 1 problem(s)"], None),
}

# Exit code and stdout of the tool at c668e42 on the R fixtures.
GOLDEN = {'R1 no flags, identical': (0, 'records: before 3 - after 3\ncommon: 3 - identical 3, changed 0 (id ignored)\nadded: 0\ngone: 0\nOK: nothing disappeared, every common record identical, 0 added\n'), 'R2 no flags, max_g changed': (1, 'records: before 3 - after 3\ncommon: 3 - identical 2, changed 1 (id ignored)\nadded: 0\ngone: 0\n  changed 3663 max_g: 322.0 -> 320.0\nSTOP: 3663 changed in max_g\nFAIL: 1 problem(s)\n'), 'R3 no flags, record gone': (1, 'records: before 3 - after 2\ncommon: 2 - identical 2, changed 0 (id ignored)\nadded: 0\ngone: 1 - 3663\nSTOP: 3663 disappeared from the export\nFAIL: 1 problem(s)\n'), 'R4 expect-added, matches': (0, 'records: before 3 - after 4\ncommon: 3 - identical 3, changed 0 (id ignored)\nadded: 1 - 9001\ngone: 0\nexpected additions: 1 - the added set matches exactly\nOK: nothing disappeared, every common record identical, added set as expected\n'), 'R5 expect-added, wrong': (1, 'records: before 3 - after 4\ncommon: 3 - identical 3, changed 0 (id ignored)\nadded: 1 - 9001\ngone: 0\nSTOP: added but not expected: 9001\nSTOP: expected but not added: 9002\nFAIL: 2 problem(s)\n'), 'R6 no flags, every id shifted': (0, 'records: before 3 - after 3\ncommon: 3 - identical 3, changed 0 (id ignored)\nadded: 0\ngone: 0\nOK: nothing disappeared, every common record identical, 0 added\n')}


def write_export(path, records):
    path.write_text("# -*- coding: utf-8 -*-\nFOODS = " + repr(records) + "\n", encoding="utf-8")


def run_case(tool, workdir, name, before, after, extra):
    case_dir = workdir / name.split()[0]
    case_dir.mkdir()
    write_export(case_dir / "before.py", before)
    write_export(case_dir / "after.py", after)
    args = [str(case_dir / "before.py"), str(case_dir / "after.py")]
    for flag, file_name, text in extra:
        (case_dir / file_name).write_text(text, encoding="utf-8")
        args += [flag, str(case_dir / file_name)]
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
    p = subprocess.run([sys.executable, str(tool)] + args, capture_output=True, env=env)
    return (p.returncode, p.stdout.decode("utf-8").replace("\r\n", "\n"),
            p.stderr.decode("utf-8").replace("\r\n", "\n"))


def main():
    tool = TOOL
    if "--tool" in sys.argv:
        tool = Path(sys.argv[sys.argv.index("--tool") + 1])
    capture = "--capture" in sys.argv
    failed, captured = 0, {}
    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        for name, (before, after, extra) in CASES.items():
            if capture and not name.startswith("R"):
                continue
            code, out, err = run_case(tool, workdir, name, before, after, extra)
            problems = []
            if name.startswith("R"):
                captured[name] = (code, out)
                if not capture:
                    want = GOLDEN.get(name)
                    if want is None:
                        problems.append("no golden output recorded")
                    elif (code, out) != want:
                        problems.append(f"exit {code} vs golden {want[0]}; stdout identical: {out == want[1]}")
                if err:
                    problems.append("stderr not empty")
            else:
                want_code, lines, stderr_text = CHECKS[name]
                if code != want_code:
                    problems.append(f"exit {code}, expected {want_code}")
                for line in lines:
                    if line not in out.split("\n"):
                        problems.append(f"missing stdout line: {line!r}")
                if stderr_text is not None:
                    if out:
                        problems.append("stdout not empty - the comparison ran")
                    if stderr_text not in err:
                        problems.append(f"stderr lacks {stderr_text!r}")
                elif err:
                    problems.append("stderr not empty")
            failed += bool(problems)
            print(f"{'PASS' if not problems else 'FAIL'}  {name}  (exit {code})")
            for line in (out.rstrip("\n").split("\n") if out else []):
                print(f"      | {line}")
            for line in (err.rstrip("\n").split("\n") if err else []):
                print(f"      ! {line}")
            for problem in problems:
                print(f"      >> {problem}")
    if capture:
        print("GOLDEN = " + repr(captured))
        return
    print(f"\n{len(CASES) - failed} of {len(CASES)} cases pass")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
