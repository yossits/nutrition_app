# -*- coding: utf-8 -*-
"""
11_curation_sheet.py — the decision sheet for block 3d2.

READ-ONLY. Opens a READ ONLY transaction as its first statement and rolls back
at the end, exactly as 07_curation_candidates.py does. It writes no curation
row; block 3d3 does that, after Yossi has ruled.

Run.
The DSN is read from .env at the repository root — see db/_env.py.

  python db\\11_curation_sheet.py

Output: db/curation_sheet_report.txt. Gitignored via db/*_report.txt, like
every other run report. Regenerated from scratch on every run.


WHAT THIS FILE IS FOR

07 answers "which 119 items are worth a human's attention". This one answers
the next question — for each of them, what can the code already say, and what
is left for Yossi. The split down the middle of the sheet is the whole point:

  proposed   the code derived it, and the header says from what
  blank      the code has no source for it, and says so rather than guessing

A blank here is a finding, not an omission. spec/05-food-db.md §3 lists the
fields the source does not contain, and a default quietly filled in is how a
tagging effort ends up looking complete while being unreviewed.


THE CANDIDATES ARE NOT RE-DERIVED HERE

The 119 come from 07's select_candidates(), imported rather than restated. Two
statements of which rows are the candidates would not raise when they diverged;
they would hand this sheet a different list from the one the candidate report
shows. The module name starts with a digit, so it is loaded by path — the
pattern 09_export_menu_foods.py already uses for 04_transform.py.


KOSHER IS A PROPOSAL AND NOTHING MORE

spec/05-food-db.md §3 calls kashrut manual tagging, critical, and required to be
exact, and the CHECK on food_curation refuses menu_eligible without it. The ksh
column here is derived from class_code by way of the §5.5 family, and the sheet
carries a separate empty kok column for the human confirmation. The derivation
is deliberately silent where class_code cannot answer — margarine and
mayonnaise each hold parve and dairy rows under one code, and the source
misfiled pea protein 8547 into the milk group.
"""

import importlib.util
import io
import sys
from pathlib import Path

try:
    import psycopg
    from psycopg.rows import dict_row, tuple_row
except ImportError:
    sys.exit("psycopg is missing. Run:  pip install \"psycopg[binary]\"")

# sys.path[0] is db/ when this is run as `python db/11_curation_sheet.py`.
from _env import load_database_url, mask_dsn

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).parent
REPO = HERE.parent


def load_by_path(name, filename):
    """Import a sibling db/ module whose name starts with a digit.

    Same mechanism as 09_export_menu_foods.py._mida_codes(). Both files guard
    their entry point behind `if __name__ == "__main__"`, so this executes
    their module level — constants and definitions — and nothing else.
    """
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CAND = load_by_path("curation_candidates", "07_curation_candidates.py")
EXPORT = load_by_path("export_menu_foods", "09_export_menu_foods.py")

FAMILIES = CAND.FAMILIES
POOL_SQL = CAND.POOL_SQL

# §5.5 numbers the 25 families 1-25 across its two tables — fat 1-15, protein
# 16-25 — and FAMILIES is in that same order. The number is printed on every
# row so a line lifted out of the sheet still points back at the spec table.
FAMILY_NO = {label: i for i, (label, *_rest) in enumerate(FAMILIES, 1)}

# ---------------------------------------------------------------------------
#  The verification queue — PROGRESS.md, "ממתין להחלטה", group 1.
#
#  PROGRESS.md calls it "13 פריטים" and lists 13 ENTRIES, but 8623 is named
#  twice: once among the four beef rows at -12% to -16%, and again as one of
#  the two fat_g = 0 items. Thirteen mentions, twelve codes. The flag fires on
#  twelve, the report prints both numbers, and PROGRESS.md is left alone — the
#  count there is not wrong about anything except itself.
VERIFY_QUEUE = {
    "605", "8623", "755", "620",             # beef and veal, -12% to -16%
    "9688", "517", "8519", "9584", "4041",   # -14% to -25%
    "9469", "3543",                          # the two alcohol rows
    "1699",                                  # fat_g = 0 on an item that is not fat-free
}                                            # 8623 is the second fat_g = 0 row

# open-questions.md #21. The source calls one physical object קופסה on canned
# tuna and שקית or אריזה on white cheese. 906 and 905 were admitted as menu
# units in 3c; these three were not.
CONTAINER_MIDA = {"900", "903", "908"}

# MENU_UNIT rank 1 = יחידה and rank 6 = צורה טבעית. Both are whole objects — an
# egg, a fillet, a floret — and neither halves. Every other rank is a measure
# (slice, tub, cup, spoon) and says nothing about wholeness.
WHOLE_UNIT_RANKS = (1, 6)

# ---------------------------------------------------------------------------
#  Kosher, per §5.5 family. The family is itself a class_code derivation, so
#  this stays inside "from class_code alone" while being sharper than a p2
#  lookup: p2 = 81 holds butter and vegetable shortening together.
#
#  None means class_code cannot answer and the cell stays blank:
#    margarine & spreads  8110 carries both dairy margarine and 4423, a purely
#                         vegetable shortening
#    mayo & dressings     egg and dairy are both ordinary here and neither is
#                         visible in the code
#  Quota-0 families never reach the sheet and are absent on purpose.
KOSHER_BY_FAMILY = {
    "olive & avocado oil":   "parve",
    "nut & sesame oil":      "parve",
    "other neutral oil":     "parve",
    "olives":                "parve",
    "avocado":               "parve",
    "tahini & sesame":       "parve",
    "other seeds":           "parve",
    "nuts & nut butters":    "parve",
    "butter & ghee":         "dairy",
    "margarine & spreads":   None,
    "mayo & dressings":      None,
    "protein powders":       "_by_class",
    "poultry":               "meat",
    "fish & seafood":        "parve",
    "beef, veal & lamb":     "meat",
    "dairy & cheese":        "dairy",
    "legumes & soy":         "parve",
    "eggs":                  "parve",
    "seitan & wheat gluten": "parve",
}


def kosher_by_class(row):
    """The one family that mixes, resolved one level deeper than the family.

    8712 is whey and dairy; 1724 and 8274 are soy and parve. 8547 is pea
    protein filed under 1122, inside the milk group — a family answer would
    call it dairy, so it falls through to blank instead. That is the
    class_code limit showing itself, and it belongs in the sheet as a blank.
    """
    if row["p4"] == "1183":
        return "dairy"
    if row["p2"] == "41":
        return "parve"
    return None


def kosher_of(row, family):
    proposal = KOSHER_BY_FAMILY.get(family)
    if proposal == "_by_class":
        return kosher_by_class(row)
    return proposal


# ---------------------------------------------------------------------------
#  vegan, per §5.5 family. spec/05-food-db.md §3 lists vegetarian/vegan as
#  "נגזר בחלקו מהקטגוריה · חצי אוטומטי", which is exactly a family-level
#  proposal. Three states, and they are three different statements:
#    vegan   the family is plant — propose the tag
#    -       the family is animal — propose no vegan tag
#    blank   the family holds both, and class_code does not separate them
VEGAN_BY_FAMILY = {
    "olive & avocado oil":   True,
    "nut & sesame oil":      True,
    "other neutral oil":     True,
    "olives":                True,
    "avocado":               True,
    "tahini & sesame":       True,
    "other seeds":           True,
    "nuts & nut butters":    True,
    "butter & ghee":         False,
    "margarine & spreads":   None,
    "mayo & dressings":      None,
    "protein powders":       "_by_class",
    "poultry":               False,
    "fish & seafood":        False,
    "beef, veal & lamb":     False,
    "dairy & cheese":        False,
    "legumes & soy":         True,
    "eggs":                  False,
    "seitan & wheat gluten": True,
}


def vegan_of(row, family):
    proposal = VEGAN_BY_FAMILY.get(family)
    if proposal == "_by_class":
        if row["p2"] == "41":
            return True
        if row["p4"] == "1183":
            return False
        return None
    return proposal


SQL_COMPONENTS = """
    SELECT f.source_code, count(*) AS n
    FROM food_recipe_components rc
    JOIN foods f ON f.id = rc.recipe_id
    WHERE f.source_code = ANY(%s)
    GROUP BY 1
"""


def quote_source(relpath, first_marker, last_marker):
    """Print real lines from a real file, with their real line numbers.

    The gate measurement is worth nothing as a paraphrase that drifted from the
    code. Read at run time and located by marker, so the quote cannot go stale
    and cannot silently quote the wrong thing: if either marker is missing the
    script stops rather than print a guess.
    """
    path = REPO / relpath
    lines = path.read_text(encoding="utf-8").splitlines()
    start = end = None
    for i, line in enumerate(lines):
        if start is None and first_marker in line:
            start = i
        elif start is not None and last_marker in line:
            end = i
            break
    if start is None or end is None:
        sys.exit(f"Cannot locate {first_marker!r}..{last_marker!r} in {relpath}. "
                 "The gate quote would be a guess; refusing to print one.")
    width = len(str(end + 1))
    return "\n".join(f"  {str(i + 1).rjust(width)}  {lines[i]}"
                     for i in range(start, end + 1))


# ---------------------------------------------------------------------------
#  Row rendering.
#
#  One line per item, as asked. The cost is width, and the two things that keep
#  it near 190 rather than past 240 are the flag mask — one character per flag,
#  len(FLAG_LETTERS) of them — and the family number standing in for the family
#  name, which is already the group heading directly above.
NAME_W = 40
BLANK = "·"          # the code has no source for this cell
FILL = "_"           # Yossi fills this one in 3d2


def pad_name(name):
    """Fixed-width name column. Newlines exist in the source data (8743)."""
    name = " ".join(str(name).split())
    if len(name) > NAME_W:
        name = name[:NAME_W - 1] + "…"
    return name.ljust(NAME_W)


def num(value, width, decimals=1):
    if value is None:
        return "∅".rjust(width)
    return f"{float(value):.{decimals}f}".rjust(width)


# The flag columns, in column order. R sits beside D because raw? is dry?'s
# sibling — open-questions.md #28 — and the two are read together. flag_mask()
# renders positionally, so this string, HEAD_1 and the counts loop all read it
# rather than repeating it.
FLAG_LETTERS = "DRKFVC"


def flag_mask(flags):
    """Six flags in six columns. A dot is 'not set', a letter is 'set'.

    Spelled-out flag names cost about 30 characters a row and are read exactly
    once; the mask is read down the column, which is how a reader actually uses
    it — 'show me every dry row in this family'.
    """
    return "".join(letter if letter in flags else "·" for letter in FLAG_LETTERS)


HEAD_1 = ("fam  code  " + "name_he".ljust(NAME_W) + "  class_cd"
          " |  kcal  prot   fat  carb  fibr  mois"
          " | cat      ksh    q  sup  bw  unit          gram  wh  vgn"
          " | cmp | " + FLAG_LETTERS +
          " | max_g  prep  prc  kok  allergens")


def render_row(item):
    return "  ".join([
        str(item["family_no"]).rjust(3),
        str(item["source_code"]).ljust(5),
        pad_name(item["name_he"]),
        str(item["class_code"]).ljust(8),
        "|",
        num(item["kcal"], 5, 0),
        num(item["protein_g"], 5),
        num(item["fat_g"], 5),
        num(item["carb_g"], 5),
        num(item["fiber_g"], 5),
        num(item["moisture"], 5),
        "|",
        item["category"].ljust(7),
        (item["kosher"] or BLANK).ljust(5),
        FILL,                                   # quality — see the header note
        ("yes" if item["supp"] else "no").ljust(3),
        ("g" if item["by_weight"] else "u").ljust(2),
        (item["unit_label"] or BLANK).ljust(12),
        (num(item["unit_grams"], 4, 0) if item["unit_grams"] is not None
         else BLANK.rjust(4)),
        item["whole_only"].ljust(2),
        item["vegan"].ljust(3),
        "|",
        str(item["components"]).rjust(3),
        "|",
        flag_mask(item["flags"]),
        "|",
        FILL * 5,
        FILL * 4,
        FILL * 3,
        FILL * 3,
        FILL * 9,
    ])


RULE = "=" * 200


def build_items(selected, servings_by_code, components_by_code):
    """One dict per candidate, in FAMILIES order inside each category.

    Every proposal the sheet makes is decided here and nowhere else, so the
    provenance table in the header can be checked against one function.
    """
    items = {"fat": [], "protein": []}

    for category in ("fat", "protein"):
        for family, row in selected[category]:
            code = str(row["source_code"])
            all_rows = servings_by_code.get(code, [])

            kcal = float(row["kcal"]) if row["kcal"] is not None else None
            unit_row = EXPORT.choose_unit(all_rows, kcal, code)

            by_weight = unit_row is None
            unit_label = None if by_weight else unit_row[1]
            unit_grams = None if by_weight else float(unit_row[3])
            unit_mida = None if by_weight else unit_row[0]

            # whole_only follows the unit family, and is blank without a unit:
            # whole_only_requires_a_unit reads both fields together, and
            # open-questions #22 records that it stops catching the pair once
            # by_weight is NULL. A row measured in grams has nothing to be whole.
            if by_weight:
                whole = BLANK
            else:
                rank = EXPORT.MENU_UNIT.get(unit_mida, (None, None))[0]
                whole = "y" if rank in WHOLE_UNIT_RANKS else "n"

            vegan = vegan_of(row, family)
            vegan_cell = BLANK if vegan is None else ("veg" if vegan else "-")

            # container_21 — open-questions #21, both clauses.
            #   (a) the chosen unit is one of the three
            #   (b) no eligible unit at all, and a row in one of the three
            # (a) cannot fire while MENU_UNIT ranks all three None and
            # UNIT_BY_JUDGEMENT is empty. It is implemented anyway, because the
            # override is the documented path by which that changes, and the
            # report says how many times each clause actually fired.
            has_container = any(r[0] in CONTAINER_MIDA for r in all_rows)
            container_a = bool(unit_mida) and unit_mida in CONTAINER_MIDA
            container_b = by_weight and has_container

            flags = set(CAND.flags_of(row, family))
            mask = set()
            if "dry?" in flags:
                mask.add("D")
            if "raw?" in flags:
                mask.add("R")
            if row["is_outlier"]:
                mask.add("K")
            if "fiber?" in flags:
                mask.add("F")
            if code in VERIFY_QUEUE:
                mask.add("V")
            if container_a or container_b:
                mask.add("C")

            items[category].append({
                "family": family,
                "family_no": FAMILY_NO[family],
                "source_code": code,
                "name_he": row["name_he"],
                "class_code": row["class_code"],
                "kcal": row["kcal"],
                "protein_g": row["protein_g"],
                "fat_g": row["fat_g"],
                "carb_g": row["carb_g"],
                "fiber_g": row["fiber_g"],
                "moisture": row["moisture"],
                "category": category,
                "kosher": kosher_of(row, family),
                "supp": family == "protein powders",
                "by_weight": by_weight,
                "unit_label": unit_label,
                "unit_grams": unit_grams,
                "whole_only": whole,
                "vegan": vegan_cell,
                "components": components_by_code.get(code, 0),
                "flags": mask,
                "container_a": container_a,
                "container_b": container_b,
            })
    return items


def write_header(out, gate_filters, gate_portions):
    out.write("CURATION DECISION SHEET — the 119 candidates, with what the code "
              "can say and what it cannot\n")
    out.write("Generated by db/11_curation_sheet.py. READ-ONLY: nothing was "
              "written to the database.\n")
    out.write("Block 3d1. Yossi picks ~25 and fills the blanks in 3d2; block 3d3 "
              "writes food_curation.\n")

    out.write("\n\n" + RULE + "\n")
    out.write("▸ THE GATE, MEASURED — quoted from the files at run time, not "
              "described\n")
    out.write(RULE + "\n\n")
    out.write("spike/filters.py\n")
    out.write(gate_filters + "\n\n")
    out.write("  The floor in force: protein 4 · carb 3 · veg 3 · fat 2 — twelve "
              "items across four categories.\n"
              "  fruit and drink are not in MIN_PER_CAT and are never gated at "
              "all.\n\n")
    out.write("  An entirely empty category gets no special branch. cats[c] is 0, "
              "0 < MIN is true, so it lands\n"
              "  in `missing` as (0, MIN) and the return is (False, missing, "
              "RELAX_HINT[worst]). `worst` is\n"
              "  min() over have-want, i.e. the largest absolute shortfall, so an "
              "empty protein (0-4) outranks\n"
              "  an empty fat (0-2). Zero is just the extreme case of the same "
              "comparison.\n\n")
    out.write("spike/portions.py\n")
    out.write(gate_portions + "\n\n")
    out.write("  feasible() touches one category only — protein. An empty protein "
              "pool returns\n"
              "  (False, 'no protein sources in pool'); otherwise the test is "
              "kcal_needed > kcal * 0.92.\n")
    out.write("\n  What this measures for open-questions #23: a pool of fat and "
              "protein alone fails on carb\n"
              "  and veg, at 0 against 3 each — not on protein or fat. The number "
              "that binds pool_health()\n"
              "  is 12, not 60. §5's 60 is a diversity floor for the product, not "
              "this function's gate.\n")


def write_provenance(out):
    out.write("\n\n" + RULE + "\n")
    out.write("▸ WHERE EVERY COLUMN COMES FROM — proposed, or deliberately blank\n")
    out.write(RULE + "\n\n")
    out.write("  PROPOSED BY THE CODE\n"
              "    cat     the §5.5 family category. fat and protein map 1:1 onto "
              "the food_category enum\n"
              "    ksh     class_code by way of the family. A PROPOSAL — §3 makes "
              "kashrut manual and critical,\n"
              "            and the sheet carries `kok` separately for the "
              "confirmation. Blank where class_code\n"
              "            cannot answer: margarine, mayo & dressings, and pea "
              "protein 8547\n"
              "    sup     family = protein powders (§5.4)\n"
              "    bw      by_weight. u = a serving unit was found · g = measured "
              "in grams.\n"
              "            choose_unit() imported from 09, unchanged\n"
              "    unit    the winning serving row, and its grams\n"
              "    wh      whole_only, from the unit family: rank 1 יחידה or 6 "
              "צורה טבעית -> y, else n.\n"
              "            Blank when by_weight — a row measured in grams has "
              "nothing to be whole\n"
              "    vgn     vegan at family level (§3: נגזר בחלקו מהקטגוריה · חצי "
              "אוטומטי).\n"
              "            veg = propose the tag · - = animal family, propose none "
              "· · = the family holds both\n"
              "    cmp     rows in food_recipe_components. 0 = a base ingredient · "
              ">0 = a recipe that inherits.\n"
              "            This is the distinction the allergen pass will stand "
              "on\n\n")
    out.write("  LEFT BLANK, WITH A REASON\n"
              "    q       quality. NOT proposed on any of the 119. §3 and §5.3 make it "
              "manual, and 07 refuses to let\n"
              "            `complete` stand in for it — nothing in the data ranks "
              "biological value. Note the\n"
              "            CHECK: a protein item cannot become menu_eligible "
              "without it\n"
              "    max_g   §5.0 makes it mandatory at curation, and it has no "
              "source in the data\n"
              "    prep    not something a nutritional database carries\n"
              "    prc     varies; a coarse 3-level judgement\n"
              "    kok     the human confirmation of the ksh proposal\n"
              "    allerg  §3 — manual where missing, critical to safety. '{}' "
              "(reviewed and clean) and\n"
              "            allergens_reviewed_at IS NULL (not reviewed) are two "
              "different states\n\n")
    out.write("  FLAGS — they mark, they never exclude. Every flagged row stays on "
              "the sheet.\n"
              "    D  dry?           §5.0.2 — moisture under "
              f"{CAND.DRY_MOISTURE_MAX} g AND a name that says so\n"
              "    R  raw?           #28 — the name says the uncooked form: "
              "\"לא מבושל\" anywhere but the\n"
              "                      powders; or, in poultry, fish, and beef, "
              "veal & lamb, \"טרי\" as a\n"
              "                      whole word, or \"קפוא\" with no \"מבושל\" "
              "beside it (frozen-uncooked)\n"
              "    K  kcal_outlier?  the derived kcal and the file's disagree "
              "beyond the Atwater gate\n"
              "    F  fiber?         a plant item with no fibre value; verify "
              "against a label first\n"
              "    V  verify_queue?  on the PROGRESS.md list of items to check "
              "against labels\n"
              "    C  container_21?  open-questions #21 — the 900/903/908 "
              "container class\n\n")
    out.write("  · = the code has no source for this cell.   _ = Yossi fills it "
              "in 3d2.\n")
    out.write(f"  Line width is {len(HEAD_1)} characters — paste into a monospace "
              "block, or take one family at a time.\n")


def write_section(out, items, category, title):
    rows = items[category]
    quota = sum(q for _l, c, q, _m, _f in FAMILIES if c == category)

    out.write("\n\n" + RULE + "\n")
    out.write(f"▸ {title} — {len(rows)} rows of the {quota} the §5.5 quotas "
              f"allow\n")
    out.write(RULE + "\n")

    for label, cat, q, _m, _f in FAMILIES:
        if cat != category or q == 0:
            continue
        picked = [it for it in rows if it["family"] == label]
        if not picked:
            continue
        out.write(f"\n  §5.5 #{FAMILY_NO[label]} · {label} — {len(picked)}/{q}"
                  f"  [{CAND.describe_floors(label)}]\n")
        out.write("  " + HEAD_1 + "\n")
        out.write("  " + "-" * len(HEAD_1) + "\n")
        for it in picked:
            out.write("  " + render_row(it).rstrip() + "\n")


def verify_queue_status(pool, chosen_codes):
    """Where each verification-queue item stands relative to the 119.

    The flag firing zero times is a result, not an absence, and a bare 0 in a
    report is the kind of thing a later session re-derives from scratch. This
    says which gate each of the twelve stopped at.
    """
    by_code = {str(r["source_code"]): r for r in pool}
    rows = []
    for code in sorted(VERIFY_QUEUE, key=int):
        row = by_code.get(code)
        if row is None:
            rows.append((code, "not in the candidate pool at all", ""))
            continue
        name = " ".join(str(row["name_he"]).split())[:34]
        hit = CAND.family_of(row)
        if hit is None:
            rows.append((code, "no §5.5 family matches it", name))
        elif not CAND.passes_floor(row, hit[0]):
            rows.append((code, f"{hit[0]} — below the family floor", name))
        elif code in chosen_codes:
            rows.append((code, f"{hit[0]} — SELECTED", name))
        else:
            rows.append((code, f"{hit[0]} — passed the floor, lost the quota",
                         name))
    return rows


def write_counts(out, items, curation_before, curation_after, null_reason,
                 exclusions, vq_status):
    every = items["fat"] + items["protein"]

    out.write("\n\n" + RULE + "\n")
    out.write("▸ THE COUNTS — what this run actually produced\n")
    out.write(RULE + "\n\n")

    out.write("  food_curation\n")
    out.write(f"    rows before                  {curation_before}\n")
    out.write(f"    rows after                   {curation_after}"
              f"   {'unchanged' if curation_before == curation_after else 'CHANGED — THIS IS A BUG'}\n")
    out.write(f"    excluded_reason IS NULL      {null_reason}"
              f"   {'as expected' if null_reason == 0 else 'UNEXPECTED'}\n")
    for e in exclusions:
        out.write(f"      {e['reason']:<24} {e['n']}\n")

    fat_quota = sum(q for _l, c, q, _m, _f in FAMILIES if c == "fat")
    pro_quota = sum(q for _l, c, q, _m, _f in FAMILIES if c == "protein")
    out.write("\n  Sheet rows by section\n")
    out.write(f"    fat                          {len(items['fat']):>3}"
              f"   of {fat_quota} allowed by the §5.5 quotas\n")
    out.write(f"    protein                      {len(items['protein']):>3}"
              f"   of {pro_quota}\n")
    out.write(f"    total                        {len(every):>3}"
              f"   of {fat_quota + pro_quota}\n")

    out.write("\n  Flags — how many rows each one lights up\n")
    names = {"D": "dry?", "R": "raw?", "K": "kcal_outlier?", "F": "fiber?",
             "V": "verify_queue?", "C": "container_21?"}
    for letter in FLAG_LETTERS:
        n = sum(1 for it in every if letter in it["flags"])
        n_fat = sum(1 for it in items["fat"] if letter in it["flags"])
        n_pro = sum(1 for it in items["protein"] if letter in it["flags"])
        out.write(f"    {letter}  {names[letter]:<16} {n:>3}"
                  f"   fat {n_fat} · protein {n_pro}\n")
    out.write(f"    at least one flag            "
              f"{sum(1 for it in every if it['flags']):>3}\n")

    out.write("\n  container_21? by clause — open-questions #21\n")
    n_a = sum(1 for it in every if it["container_a"])
    n_b = sum(1 for it in every if it["container_b"])
    out.write(f"    (a) chosen unit is 900/903/908           {n_a:>3}\n")
    out.write(f"    (b) no eligible unit, has such a row     {n_b:>3}\n")
    if n_a == 0:
        out.write("    Clause (a) returned 0, and it cannot return anything "
                  "else today: MENU_UNIT ranks\n"
                  "    900, 903 and 908 as (None, \"אריזה\"), so they are never "
                  "eligible, and\n"
                  "    UNIT_BY_JUDGEMENT — the one documented way past the "
                  "ranking — is empty.\n"
                  "    Only clause (b) can fire until one of those two "
                  "changes.\n")

    out.write("\n  verify_queue? — the count PROGRESS.md gives, and the count "
              "of codes\n")
    hit = sorted((it["source_code"] for it in every if "V" in it["flags"]),
                 key=int)
    out.write(f"    entries listed in PROGRESS.md            13\n")
    out.write(f"    distinct source_codes in that list       {len(VERIFY_QUEUE)}"
              "   8623 is named twice — beef, and fat_g = 0\n")
    out.write(f"    of those, present among the 119          {len(hit)}"
              f"   {' · '.join(hit) if hit else 'none'}\n")
    if not hit:
        out.write("\n    The queue and the candidate list are disjoint, and "
                  "that is worth having in writing:\n"
                  "    nothing on the sheet is waiting on a label check, so "
                  "the queue does not constrain\n"
                  "    the 3d2 selection. Where each of the twelve stopped:\n")
        for code, where, name in vq_status:
            out.write(f"      {code:>5}  {where:<48} {name}\n")

    out.write("\n  Proposals filled, and blanks\n")
    for column, key, note in (
        ("category", "category", "the family category; every row has one"),
        ("kosher",   "kosher",   "blank where class_code cannot answer"),
        ("quality",  "_quality", "never proposed — §3/§5.3 manual, no data source"),
    ):
        if key == "_quality":
            filled = 0
        else:
            filled = sum(1 for it in every if it[key])
        out.write(f"    {column:<10} filled {filled:>3}   blank "
                  f"{len(every) - filled:>3}   {note}\n")

    blank_k = [it for it in every if not it["kosher"]]
    if blank_k:
        out.write("\n    kosher blanks, by family\n")
        per = {}
        for it in blank_k:
            per.setdefault(it["family"], []).append(it["source_code"])
        for fam, codes in sorted(per.items()):
            out.write(f"      {fam:<22} {len(codes):>2}   "
                      f"{' · '.join(sorted(codes, key=int))}\n")

    out.write("\n  Other proposals\n")
    n_bw = sum(1 for it in every if it["by_weight"])
    out.write(f"    by_weight (g)                {n_bw:>3}"
              f"   unit found for the other {len(every) - n_bw}\n")
    out.write(f"    supp                         "
              f"{sum(1 for it in every if it['supp']):>3}\n")
    out.write(f"    whole_only y                 "
              f"{sum(1 for it in every if it['whole_only'] == 'y'):>3}"
              f"   n {sum(1 for it in every if it['whole_only'] == 'n')}"
              f" · blank {sum(1 for it in every if it['whole_only'] == BLANK)}\n")
    out.write(f"    vegan proposed               "
              f"{sum(1 for it in every if it['vegan'] == 'veg'):>3}"
              f"   animal {sum(1 for it in every if it['vegan'] == '-')}"
              f" · blank {sum(1 for it in every if it['vegan'] == BLANK)}\n")
    n_recipe = sum(1 for it in every if it["components"])
    out.write(f"    recipes (cmp > 0)            {n_recipe:>3}"
              f"   base ingredients "
              f"{len(every) - n_recipe}\n")
    if n_recipe == 0:
        out.write("\n    Every one of the 119 is a base ingredient, so nothing "
                  "on this sheet inherits\n"
                  "    allergens from components — the allergen pass reviews "
                  "each row on its own.\n"
                  "    The mechanism is the first key of sort_key() in 07: a "
                  "recipe sinks below every\n"
                  "    raw material in its family (02.09.2026), so a quota "
                  "reaches one only where the\n"
                  "    raw materials ran out — either the family holds fewer "
                  "than its quota, or the p4\n"
                  "    cap skipped enough of them. Neither happened here. The "
                  "count above is\n"
                  "    food_recipe_components, a different field from `source`, "
                  "and it agrees.\n")


def main():
    # Located by marker and read at run time — see quote_source(). Done before
    # the database is touched, so a moved function fails the run early rather
    # than after a connection is open.
    gate_filters = quote_source("spike/filters.py",
                                "MIN_PER_CAT = {", "return False, missing,")
    gate_portions = quote_source("spike/portions.py",
                                 "def feasible(", "return True, None")

    url = load_database_url()

    try:
        conn_ctx = psycopg.connect(url, row_factory=dict_row)
    except psycopg.OperationalError as exc:
        sys.exit(f"Cannot connect to {mask_dsn(url)}\n{exc}")

    out = io.StringIO()

    with conn_ctx as conn:
        with conn.cursor() as cur:
            # First statement in the transaction, and the reason this script is
            # safe to run against production during curation: any write added
            # here later fails loudly instead of running quietly.
            cur.execute("SET TRANSACTION READ ONLY")

            cur.execute("SELECT count(*) AS n FROM food_curation")
            curation_before = cur.fetchone()["n"]

            cur.execute("SELECT count(*) AS n FROM food_curation "
                        "WHERE excluded_reason IS NULL")
            null_reason = cur.fetchone()["n"]

            cur.execute("""SELECT excluded_reason::text AS reason, count(*) AS n
                           FROM food_curation WHERE excluded_reason IS NOT NULL
                           GROUP BY 1 ORDER BY 1""")
            exclusions = cur.fetchall()

            cur.execute(POOL_SQL)
            pool = cur.fetchall()

        selected, _pool_sizes, _n_excluded = CAND.select_candidates(pool)
        codes = [str(r["source_code"])
                 for cat in ("fat", "protein") for _f, r in selected[cat]]

        # Every serving row, not only the menu-eligible ones: choose_unit()
        # does its own filtering, and the container flag has to see the rows
        # that filtering removes.
        servings_by_code = {}
        components_by_code = {}
        with conn.cursor(row_factory=tuple_row) as cur:
            cur.execute(EXPORT.SQL_SERVINGS, (codes,))
            for source_code, mida_code, label, plural, grams in cur.fetchall():
                servings_by_code.setdefault(source_code, []).append(
                    (mida_code, label, plural, grams))

            cur.execute(SQL_COMPONENTS, (codes,))
            for source_code, n in cur.fetchall():
                components_by_code[source_code] = n

        items = build_items(selected, servings_by_code, components_by_code)

        write_header(out, gate_filters, gate_portions)
        write_provenance(out)
        write_section(out, items, "fat", "FAT")
        write_section(out, items, "protein", "PROTEIN")

        with conn.cursor() as cur:
            cur.execute("SELECT count(*) AS n FROM food_curation")
            curation_after = cur.fetchone()["n"]

        write_counts(out, items, curation_before, curation_after, null_reason,
                     exclusions, verify_queue_status(pool, set(codes)))

        # Never commit. The transaction is READ ONLY, so this is belt and
        # braces — and belt and braces is the point.
        conn.rollback()

    out.write("\n\n▸ Read-only proof — food_curation "
              f"{curation_before} rows before, {curation_after} after. "
              "No curation row was written.\n")

    report = out.getvalue()
    (HERE / "curation_sheet_report.txt").write_text(report, encoding="utf-8")
    print(report)
    print(f"\n✔ Saved: {HERE / 'curation_sheet_report.txt'} — hand this over.")


if __name__ == "__main__":
    main()
