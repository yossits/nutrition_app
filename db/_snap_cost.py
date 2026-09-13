# -*- coding: utf-8 -*-
"""
_snap_cost.py - what snapping a whole_only ceiling down to a whole multiple costs. Read-only.

  python db\\_snap_cost.py

Opened in block 8t-alef for open-questions.md #50 and #53. Runs _audit_units.py
fresh, reads its Section A rows - whole_only rows whose max_g is not a whole
multiple of the menu unit - and for each computes

    snapped = floor(max_g / unit_grams) * unit_grams,   difference = max_g - snapped

in Decimal on the values the audit printed, so 4.4 * 3 is 13.2 and not
13.200000000000001. Nothing is written.

FIVE is the set #50 works in 8t-vav (decision of block 8t-bet); every other
Section A row is "the rest". Every summary line is counted here, not read off the
table.
"""

import subprocess
import sys
from decimal import Decimal, ROUND_FLOOR
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).parent
FIVE = ("8348", "3459", "3663", "3793", "3837")
LARGE = Decimal(20)

HEADER = "code | name | category | unit label | mida | unit g | max_g | max_g/unit | whole"
COUNT_LINE = "  violations (max_g not a whole multiple): "


def section_a_rows():
    proc = subprocess.run([sys.executable, str(HERE / "_audit_units.py")], capture_output=True)
    out = proc.stdout.decode("utf-8")
    if proc.returncode != 0:
        sys.exit(f"STOP: _audit_units.py exited {proc.returncode}\n{proc.stderr.decode('utf-8', 'replace')}")
    lines = out.replace("\r", "").split("\n")
    start = lines.index(HEADER)
    rows, expected = [], None
    for line in lines[start + 1:]:
        if line.startswith("SECTION B"):
            break
        if line.startswith(COUNT_LINE):
            expected = int(line[len(COUNT_LINE):].split()[0])
            continue
        parts = line.split(" | ")
        if len(parts) >= 9 and parts[8] == "no":
            rows.append(dict(code=parts[0], category=parts[2],
                             unit=Decimal(parts[5]), max_g=Decimal(parts[6])))
    if expected is None or expected != len(rows):
        sys.exit(f"STOP: parsed {len(rows)} Section A rows, the audit counted {expected}")
    return rows


def fmt(d):
    s = format(d.normalize(), "f")
    return s


def summary(label, rows):
    diffs = [r["diff"] for r in rows]
    print(f"{label}: rows {len(rows)} · min {fmt(min(diffs))} · max {fmt(max(diffs))} · "
          f"sum {fmt(sum(diffs, Decimal(0)))}")


def main():
    rows = section_a_rows()
    for r in rows:
        units = (r["max_g"] / r["unit"]).to_integral_value(rounding=ROUND_FLOOR)
        r["snapped"] = units * r["unit"]
        r["diff"] = r["max_g"] - r["snapped"]

    five = [r for r in rows if r["code"] in FIVE]
    rest = [r for r in rows if r["code"] not in FIVE]
    if len(five) != len(FIVE):
        sys.exit(f"STOP: {len(five)} of the five #50 codes are in Section A")

    print(f"Section A rows from a fresh run of _audit_units.py: {len(rows)}")
    print("code | category | max_g | unit g | snapped | difference g | set")
    for r in rows:
        print(f"{r['code']} | {r['category']} | {fmt(r['max_g'])} | {fmt(r['unit'])} | "
              f"{fmt(r['snapped'])} | {fmt(r['diff'])} | {'#50' if r['code'] in FIVE else 'rest'}")
    print()
    summary("the five #50 rows", five)
    summary("the other rows", rest)
    large = [r["code"] for r in rest if r["diff"] > LARGE]
    print(f"other rows with difference > {LARGE} g: {len(large)} · {' '.join(large)}")
    ceiling = max(r["diff"] for r in five)
    small = [r["code"] for r in rest if r["diff"] <= ceiling]
    print(f"other rows with difference <= the five's max ({fmt(ceiling)} g): {len(small)} · {' '.join(small)}")


if __name__ == "__main__":
    main()
