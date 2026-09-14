# -*- coding: utf-8 -*-
"""
_effective_ceilings.py - the ceiling a whole_only row is actually served at. Read-only, no database.

  python db\\_effective_ceilings.py [EXPORT.py]

Opened in block 8t-zayin for open-questions.md #53 and #55. Reads an export in
the format of spike/menu_foods.py - the file the portion solver reads, default
that file - and for every menu_eligible row with whole_only and a unit prints
the recorded max_g, the whole units it admits capped at three, and the
effective ceiling in grams.

The mechanism is spike/portions.py:53-57: a whole_only row's options are one,
two or three units, those above max_g are removed, and when none is left the
smallest one is served anyway. The arithmetic here is done in Decimal on the
exported values and checked against portions._options() on every row; a
disagreement exits 1. Nothing is written.
"""

import collections
import hashlib
import importlib.util
import sys
from decimal import Decimal, ROUND_FLOOR
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO = Path(__file__).resolve().parent.parent
SPIKE = REPO / "spike"
MAX_UNITS = 3            # the last step of both (1, 2, 3) and UNIT_STEPS in portions.py


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def dec(value):
    return Decimal(repr(float(value)))


def fmt(d):
    return format(d.normalize(), "f")


def main():
    export_path = Path(sys.argv[1]) if len(sys.argv) > 1 else SPIKE / "menu_foods.py"
    raw = export_path.read_bytes()
    print(f"export: {export_path.name} · {len(raw)} bytes · sha256 {hashlib.sha256(raw).hexdigest()}")
    foods = load("export_for_ceilings", export_path).FOODS
    sys.path.insert(0, str(SPIKE))
    portions = load("portions_for_ceilings", SPIKE / "portions.py")

    eligible = [f for f in foods if f.get("menu_eligible")]
    whole = [f for f in eligible if f.get("whole_only")]
    rows, mismatches, no_unit, no_max = [], [], [], []
    for f in whole:
        if not f.get("unit"):
            no_unit.append(f["source_code"])
            continue
        unit = dec(f["unit"]["grams"])
        if f.get("max_g") is None:
            no_max.append(f["source_code"])
            units, max_g = MAX_UNITS, None
        else:
            max_g = dec(f["max_g"])
            units = min(int((max_g / unit).to_integral_value(rounding=ROUND_FLOOR)), MAX_UNITS)
        if units == 0:
            effective, binds = unit, "unit above max_g"
        elif max_g is not None and unit * MAX_UNITS < max_g:
            effective, binds = unit * units, "three-unit cap"
        else:
            effective, binds = unit * units, "max_g" if max_g is not None else "no max_g"
        solver = max(portions._options(f))
        if abs(Decimal(repr(solver)) - effective) > Decimal("0.05"):
            mismatches.append((f["source_code"], fmt(effective), solver))
        rows.append(dict(code=f["source_code"], name=f["name"], cat=f["cat"], label=f["unit"]["he"],
                         unit=unit, max_g=max_g, units=units, effective=effective, binds=binds,
                         whole_multiple=max_g is not None and (max_g / unit) == (max_g / unit).to_integral_value(),
                         options=portions._options(f)))

    print(f"menu_eligible {len(eligible)} · whole_only {len(whole)} · with a unit {len(rows)} · "
          f"without a unit {len(no_unit)} {no_unit or ''} · max_g missing {len(no_max)} {no_max or ''}")
    print()
    print("code | name | category | unit | unit g | max_g | units (floor, cap 3) | effective g | binds | "
          "max_g whole multiple | solver options")
    for r in sorted(rows, key=lambda r: (r["cat"], -(r["max_g"] or 0), r["unit"], int(r["code"]))):
        print(f"{r['code']} | {r['name']} | {r['cat']} | {r['label']} | {fmt(r['unit'])} | "
              f"{fmt(r['max_g']) if r['max_g'] is not None else '-'} | {r['units']} | {fmt(r['effective'])} | "
              f"{r['binds']} | {r['whole_multiple']} | {' · '.join(f'{g:g}' for g in r['options'])}")

    def spread(label, group):
        values = collections.Counter(fmt(r["effective"]) for r in group)
        eff = [r["effective"] for r in group]
        print(f"{label}: rows {len(group)} · effective min {fmt(min(eff))} · max {fmt(max(eff))} · "
              f"distinct {len(values)} · " + " · ".join(f"{v} x{n}" for v, n in
                                                         sorted(values.items(), key=lambda kv: Decimal(kv[0]))))

    print()
    p175 = [r for r in rows if r["cat"] == "protein" and r["max_g"] == Decimal(175)]
    spread("(a) protein, recorded max_g 175", p175)
    by_max = collections.defaultdict(list)
    for r in rows:
        if r["max_g"] is not None and not (r["cat"] == "protein" and r["max_g"] == Decimal(175)):
            by_max[r["max_g"]].append(r)
    for max_g in sorted(by_max):
        if len(by_max[max_g]) > 1:
            cats = dict(collections.Counter(r["cat"] for r in by_max[max_g]))
            spread(f"(b) recorded max_g {fmt(max_g)} {cats}", by_max[max_g])
    cap = [r for r in rows if r["binds"] == "three-unit cap"]
    print(f"(c) three units below the recorded max_g: {len(cap)} · " + " ".join(r["code"] for r in cap))
    above = [r for r in rows if r["binds"] == "unit above max_g"]
    print(f"(d) unit above max_g, served one unit over the ceiling: {len(above)}"
          + ("" if not above else " · " + " ".join(f"{r['code']} (unit {fmt(r['unit'])} > {fmt(r['max_g'])})" for r in above)))
    # (e) the fallback of portions.py:57 is not a whole_only property: it fires on any row with a unit
    # whose smallest step is already above max_g - one unit for whole_only, half a unit otherwise.
    fallback, with_unit = [], 0
    for f in eligible:
        if f.get("by_weight") or not f.get("unit") or f.get("max_g") is None:
            continue
        with_unit += 1
        steps = (1, 2, 3) if f.get("whole_only") else portions.UNIT_STEPS
        smallest = min(round(f["unit"]["grams"] * s, 1) for s in steps)
        if smallest > f["max_g"]:
            fallback.append(f"{f['source_code']} (whole_only {f.get('whole_only')}, smallest step {smallest:g} > max_g {f['max_g']:g})")
    print(f"(e) all rows with a unit and max_g: {with_unit} · smallest step above max_g, served above the ceiling: "
          f"{len(fallback)}" + ("" if not fallback else " · " + " · ".join(fallback)))
    print(f"solver cross-check: {len(rows) - len(mismatches)} of {len(rows)} agree with max(portions._options())")
    if mismatches:
        for m in mismatches:
            print(f"  MISMATCH {m}")
        sys.exit(1)


if __name__ == "__main__":
    main()
