# -*- coding: utf-8 -*-
"""
04_transform.py — transform: src_* → the core tables.

Run after 03_load_source.py. Re-runnable: drops and rebuilds
nutrients · foods · food_servings · food_nutrients · food_recipe_components.
The src_* tables are left untouched.

Run.
The DSN is read from .env at the repository root — see db/_env.py, which also
explains why .env overrides the ambient DATABASE_URL rather than filling in for
it. .env is gitignored; the value is never printed, only masked.

  # .env, UTF-8, one line
  DATABASE_URL=postgresql://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres

  python db\\04_transform.py

That is the Supabase session pooler string; the direct host,
db.<ref>.supabase.co, resolves to IPv6 only. The user is postgres.<ref>,
not plain postgres, and the port is 5432 — not the 6543 transaction pooler,
which does not hold psycopg's prepared statements.

What goes where:
  foods            — identifiers, macros, makor, class_code, derived source
  food_nutrients   — ~60 further nutrients (EAV), Hebrew names from the
                     official dictionary
  food_servings    — serving units, excluding 700 (gram) and 2000 (kilogram)
  food_recipe_components — recipe composition, in grams
  foods.kcal_source — the file's declared food_energy, kept as-is
  foods.kcal       — derived from the macros, once foods is populated. The file
                     value and the macro sum disagree by up to 24%; the solver
                     needs one consistent number. See db/05_derive_kcal.sql
  foods.complete   — derived from the nine essential amino acids, once
                     food_nutrients is populated

What this script must never touch:
  food_curation    — every hand-made tagging field. It is not in the TRUNCATE
                     list and has no foreign key to foods, so CASCADE cannot
                     reach it. Two of the three stop conditions at the end prove
                     that on every run and roll the run back if either fails.
                     See db/06_split_curation.sql for why the FK is absent.
                     The third condition guards the opposite direction — a
                     source row that never reached foods — and is unrelated.

makor decoding (from "מבנה קובץ מצרכים.xlsx", Ministry of Health):
  1 USA (NDB, FNDDS)              → ingredient
  2 industry, label only          → industry
  3 industry, label with calcs    → industry
  4 recipe                        → recipe
  5 other                         → ingredient
  6 USA with calculation          → ingredient
  7 combined values               → ingredient
  Structural detection (a Code appearing as a recipe in the composition file)
  overrides makor.

Excluded from foods: any entry missing protein, fat or energy. A blank
carbohydrate excludes too, except for the four items in CARB_ZERO_BY_JUDGEMENT —
see the comment there. Such an entry is no longer merely reported: since
29.08.2026 it is the third stop condition and rolls the whole run back. carb_g
is NOT NULL on foods, so without it a new meat item in a source update would be
dropped in silence.
"""

import io
import os
import sys
from pathlib import Path

try:
    import psycopg
except ImportError:
    sys.exit("psycopg is missing. Run:  pip install \"psycopg[binary]\"")

# sys.path[0] is db/ when this is run as `python db/04_transform.py`.
from _env import load_database_url, mask_dsn

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).parent
NUM = r"^-?[0-9]+(\.[0-9]+)?([eE][-+]?[0-9]+)?$"   # a valid numeric value in jsonb

# EAV nutrients: source column → (Hebrew name, unit). From the official column
# dictionary. The Hebrew is data, not code — it is seeded into nutrients.name_he
# and nutrients.unit, so changing it changes the database.
NUTRIENTS = {
    "alcohol": ("אלכוהול", "גרם"), "moisture": ("לחות", "גרם"),
    "calcium": ("סידן", 'מ"ג'), "iron": ("ברזל", 'מ"ג'),
    "magnesium": ("מגנזיום", 'מ"ג'), "phosphorus": ("זרחן", 'מ"ג'),
    "potassium": ("אשלגן", 'מ"ג'), "zinc": ("אבץ", 'מ"ג'),
    "copper": ("נחושת", 'מ"ג'), "vitamin_a_iu": ("ויטמין A-IU", 'יב"ל'),
    "carotene": ("קרוטן", 'מק"ג'), "vitamin_e": ("ויטמין E", 'מ"ג'),
    "vitamin_c": ("ויטמין C", 'מ"ג'), "thiamin": ("תיאמין", 'מ"ג'),
    "riboflavin": ("ריבופלאבין", 'מ"ג'), "niacin": ("ניאצין", 'מ"ג'),
    "vitamin_b6": ("ויטמין B6", 'מ"ג'), "folate": ("פולאט", 'מק"ג'),
    "vitamin_b12": ("ויטמין B12", 'מק"ג'), "cholesterol": ("כולסטרול", 'מ"ג'),
    "butyric": ("ח. בוטירית 4:0", "גרם"), "caproic": ("ח. קפרואית 6:0", "גרם"),
    "caprylic": ("ח. קפרילית 8:0", "גרם"), "capric": ("ח. קפרית 10:0", "גרם"),
    "lauric": ("ח. לאורית 12:0", "גרם"), "myristic": ("ח. מיריסטית 14:0", "גרם"),
    "palmitic": ("ח. פלמיטית 16:0", "גרם"), "stearic": ("ח. סטיארית 18:0", "גרם"),
    "oleic": ("ח. אוליאית 18:1", "גרם"), "linoleic": ("ח. לינוליאית 18:2", "גרם"),
    "linolenic": ("ח. לינולנית 18:3", "גרם"), "arachidonic": ("ח. ארכידונית 20:4", "גרם"),
    "docosahexanoic": ("ח. DHA 22:6", "גרם"), "palmitoleic": ("ח. פלמיטולאית 16:1", "גרם"),
    "parinaric": ("ח. פרינרית 18:4", "גרם"), "gadoleic": ("ח. גדולאית 20:1", "גרם"),
    "eicosapentaenoic": ("ח. EPA 20:5", "גרם"), "erucic": ("ח. ארוסית 22:1", "גרם"),
    "docosapentaenoic": ("ח. DPA 22:5", "גרם"),
    "mono_unsaturated_fat": ("שומן חד בלתי רווי", "גרם"),
    "poly_unsaturated_fat": ("שומן רב בלתי רווי", "גרם"),
    "vitamin_d": ("ויטמין D", 'מק"ג'), "trans_fatty_acids": ("שומן טרנס", "גרם"),
    "vitamin_a_re": ("ויטמין A-RAE", 'מק"ג'),
    "isoleucine": ("איזוליאוצין", "גרם"), "leucine": ("לאוצין", "גרם"),
    "valine": ("ואלין", "גרם"), "lysine": ("ליזין", "גרם"),
    "threonine": ("תריאונין", "גרם"), "methionine": ("מתיונין", "גרם"),
    "phenylalanine": ("פנילאלנין", "גרם"), "tryptophan": ("טריפטופן", "גרם"),
    "histidine": ("היסטידין", "גרם"), "tyrosine": ("טירוזין", "גרם"),
    "arginine": ("ארגינין", "גרם"), "cystine": ("ציסטאין", "גרם"),
    "serine": ("סרין", "גרם"), "vitamin_k": ("ויטמין K", 'מק"ג'),
    "pantothenic_acid": ("ח. פנטותנית", 'מ"ג'), "iodine": ("יוד", 'מק"ג'),
    "selenium": ("סלניום", 'מק"ג'), "sugar_alcohols": ("רב-כוהלים", "גרם"),
    "choline": ("כולין", 'מ"ג'), "biotin": ("ביוטין", 'מק"ג'),
    "manganese": ("מנגן", 'מ"ג'), "fructose": ("פרוקטוז", "גרם"),
}

# The nine essential amino acids. Each one is a key in NUTRIENTS above, so it
# gets a food_nutrients row wherever the source file supplies a value.
#
# A food is a complete protein when all nine rows are PRESENT — presence, not a
# positive value. That is the rule the production database was fixed to, and it
# yields 2,758 of 4,620. Adding `value > 0` would give 2,586 instead: 172 items
# carry all nine, with at least one of them recorded as zero.
ESSENTIAL_AMINO_ACIDS = (
    "histidine", "isoleucine", "leucine", "lysine", "methionine",
    "phenylalanine", "threonine", "tryptophan", "valine",
)
AMINO_CODES_SQL = ", ".join(f"'{code}'" for code in ESSENTIAL_AMINO_ACIDS)

# Four items the source leaves the carbohydrate field blank on. In muscle meat
# and pure fish an empty carbohydrate reads as zero, not as missing data — a
# signed nutritional judgement, decided 28.08.2026, closing open question #14.
# See docs/decisions.md and docs/spec/05-food-db.md §5.0.1.
#
#   638   בשר בקר, פילה שריר, מבושל      P 35.5  F 19   → derives 313 vs file 315
#   1134  דג דניס-צ'יפורה, לא מבושל      P 21    F 4.9  → derives 128 vs file 128
#   9691  דג דניס-צ'יפורה, מבושל עם מלח  P 27.3  F 6.4  → derives 167 vs file 166
#   9784  דג דניס בגריל, ללא ציפוי       P 27.3  F 6.4  → derives 167 vs file 166
#
# All four land within 1% of the file's declared energy once carbohydrate is
# read as zero. That agreement is the check on the judgement: had the blank
# actually hidden a real carbohydrate value, the derived energy would fall short
# of the declared one by exactly the missing 4 kcal per gram.
#
# Deliberately an explicit list and NOT the general rule. open-questions.md #15
# was decided on 29.08.2026 and the decision KEEPS the list: the rule's wording
# lost its "no recipe components" clause once three of these four turned out to
# carry one, and a clause that loose has no business admitting rows on its own.
# What the decision added instead is the third stop condition in
# check_stop_conditions() — a source row with a blank macro that is not named
# here aborts the run rather than vanishing from foods.
#
# Measured against production on 29.08.2026: these four are the ONLY rows the
# file drops for a missing macro (src_foods 4,624 and foods 4,624 with them
# restored). Adding a fifth code here is a signed nutritional judgement; the
# stop condition is what forces that judgement to be made rather than skipped.
CARB_ZERO_BY_JUDGEMENT = ("638", "1134", "9691", "9784")
CARB_ZERO_SQL = ", ".join(f"'{code}'" for code in CARB_ZERO_BY_JUDGEMENT)

STEPS = [
    # food_curation is NOT on this list, and it has no foreign key to foods, so
    # TRUNCATE ... CASCADE cannot reach it. Both halves of that are load-bearing.
    #
    # CASCADE empties every table that references one on the list. A FK from
    # food_curation to foods — the thing that looks like the careful, correct
    # addition — would CONDUCT the deletion here, not prevent it, and one
    # re-import would erase the entire tagging effort. That is exactly the bug
    # db/06_split_curation.sql was written to close. Do not add the FK.
    #
    # What replaces it: v_curation_orphans, checked as a stop condition below.
    ("Truncate the core tables", """
        TRUNCATE food_recipe_components, food_nutrients, food_servings,
                 foods, nutrients RESTART IDENTITY CASCADE"""),

    ("foods — entries with protein, fat and energy present", f"""
        INSERT INTO foods (source_code, class_code, makor, source,
                           name_he, name_en,
                           kcal_source, protein_g, fat_g, carb_g,
                           fiber_g, sugar_g, sat_fat_g, sodium_mg)
        SELECT
            sf.code,
            sf.raw->>'smlmitzrach',
            NULLIF(sf.raw->>'makor','')::smallint,
            CASE
              WHEN EXISTS (SELECT 1 FROM src_recipe_components rc
                           WHERE rc.recipe_code = sf.code)       THEN 'recipe'
              WHEN sf.raw->>'makor' IN ('2','3')                 THEN 'industry'
              WHEN sf.raw->>'makor' IN ('1','4','5','6','7')     THEN
                   CASE WHEN sf.raw->>'makor' = '4' THEN 'recipe'
                        ELSE 'ingredient' END
              ELSE NULL
            END::source_kind,
            sf.raw->>'shmmitzrach',
            sf.raw->>'english_name',
            (sf.raw->>'food_energy')::numeric,
            (sf.raw->>'protein')::numeric,
            (sf.raw->>'total_fat')::numeric,
            CASE WHEN sf.raw->>'carbohydrates' ~ '{NUM}'
                 THEN (sf.raw->>'carbohydrates')::numeric
                 ELSE 0 END,          -- CARB_ZERO_BY_JUDGEMENT only; see above
            CASE WHEN sf.raw->>'total_dietary_fiber' ~ '{NUM}'
                 THEN (sf.raw->>'total_dietary_fiber')::numeric END,
            CASE WHEN sf.raw->>'total_sugars' ~ '{NUM}'
                 THEN (sf.raw->>'total_sugars')::numeric END,
            CASE WHEN sf.raw->>'saturated_fat' ~ '{NUM}'
                 THEN (sf.raw->>'saturated_fat')::numeric END,
            CASE WHEN sf.raw->>'sodium' ~ '{NUM}'
                 THEN (sf.raw->>'sodium')::numeric END
        FROM src_foods sf
        WHERE sf.raw->>'protein'       ~ '{NUM}'
          AND sf.raw->>'total_fat'     ~ '{NUM}'
          AND sf.raw->>'food_energy'   ~ '{NUM}'
          AND (sf.raw->>'carbohydrates' ~ '{NUM}'
               OR sf.code IN ({CARB_ZERO_SQL}))"""),

    ("food_servings — excluding 700 (gram) and 2000 (kilogram)", """
        INSERT INTO food_servings (food_id, mida_code, label_he, grams)
        SELECT f.id, s.mida_code, m.label_he, s.grams
        FROM src_servings s
        JOIN foods f    ON f.source_code = s.code
        JOIN src_mida m ON m.mida_code   = s.mida_code
        WHERE s.mida_code NOT IN ('700','2000')
          AND s.grams > 0
        ON CONFLICT (food_id, label_he) DO NOTHING"""),

    ("food_nutrients — the remaining nutrients, EAV", f"""
        INSERT INTO food_nutrients (food_id, nutrient_id, value)
        SELECT f.id, n.id, (sf.raw->>n.code)::numeric
        FROM src_foods sf
        JOIN foods f ON f.source_code = sf.code
        JOIN nutrients n ON sf.raw->>n.code ~ '{NUM}'"""),

    ("food_recipe_components — recipe composition in grams", """
        INSERT INTO food_recipe_components (recipe_id, component_id, grams)
        SELECT r.id, c.id, sum(rc.amount)
        FROM src_recipe_components rc
        JOIN foods r ON r.source_code = rc.recipe_code
        JOIN foods c ON c.source_code = rc.component_code
        GROUP BY r.id, c.id"""),

    # Must run after food_nutrients — ethanol is read from there. Like
    # `complete`, and for the same reason. It must also be a step and not a
    # one-off fix in production: the omission on `complete` left a hand-patched
    # column that the next run would have silently reverted.
    #
    # P*4 + F*9 + available carbohydrate*4 + fibre*2 + ethanol*7 — the
    # coefficients Israeli food labelling is regulated by. Ethanol sits in no
    # macro field; without its term a bottle of gin derives to 0 kcal against a
    # declared 263. It is looked up by nutrients.code, never by a hardcoded id,
    # because the id moves if nutrients is reseeded.
    #
    # COALESCE(fiber_g, 0) touches 384 items whose fibre is NULL rather than 0;
    # decided provisionally in favour of zero, see docs/open-questions.md.
    #
    # The NULL rule: an item that declares calories but carries no macro base at
    # all has nothing to derive from. Writing 0 there would be a silent failure —
    # sucralose tablets declaring 390 kcal would read as free. NULL fails loudly
    # instead. Catches exactly two rows, 8703 and 9740; the genuinely zero items
    # (water, salt, 0-kcal sweeteners) are not caught, their kcal_source is 0.
    #
    # kcal_source is never touched.
    ("foods.kcal — derived from the macros, ethanol included", """
        UPDATE foods f
        SET kcal = src.kcal
        FROM (
            SELECT f2.id,
                   CASE
                     WHEN f2.kcal_source > 0
                      AND f2.protein_g = 0
                      AND f2.fat_g     = 0
                      AND f2.carb_g    = 0
                      AND COALESCE(f2.fiber_g,0)  = 0
                      AND COALESCE(al.value,0)    = 0
                     THEN NULL
                     ELSE ROUND(f2.protein_g*4 + f2.fat_g*9 + f2.carb_g*4
                              + COALESCE(f2.fiber_g,0)*2
                              + COALESCE(al.value,0)*7, 1)
                   END AS kcal
            FROM foods f2
            LEFT JOIN food_nutrients al
                   ON al.food_id = f2.id
                  AND al.nutrient_id = (SELECT id FROM nutrients WHERE code = 'alcohol')
        ) src
        WHERE f.id = src.id"""),

    # Must stay last: it reads food_nutrients, which the step above populates.
    # TRUNCATE already reset the column to its DEFAULT false, so setting only
    # the true rows is enough.
    ("foods.complete — all nine essential amino acids present", f"""
        UPDATE foods f SET complete = true
        WHERE (SELECT count(*)
               FROM food_nutrients fn
               JOIN nutrients n ON n.id = fn.nutrient_id
               WHERE fn.food_id = f.id
                 AND n.code IN ({AMINO_CODES_SQL}))
              = {len(ESSENTIAL_AMINO_ACIDS)}"""),
]

CHECKS = [
    ("Row counts", """
        SELECT 'foods' t, count(*) n FROM foods
        UNION ALL SELECT 'food_servings', count(*) FROM food_servings
        UNION ALL SELECT 'food_nutrients', count(*) FROM food_nutrients
        UNION ALL SELECT 'food_recipe_components', count(*) FROM food_recipe_components
        UNION ALL SELECT 'nutrients', count(*) FROM nutrients"""),

    ("Distribution of derived source against makor", """
        SELECT source, makor, count(*) n
        FROM foods GROUP BY 1, 2 ORDER BY 1 NULLS LAST, 2"""),

    # zero_but_caloric is the one to read: an item declaring calories that
    # derived to 0 means energy the formula cannot see. It must be 0 — the two
    # such items are caught by the NULL rule instead. A plain `kcal <= 0` count
    # is the wrong test; it flags water and salt, where 0 is the right answer.
    #
    # Stop conditions: negative > 0, zero_but_caloric > 0, or derived_null <> 2.
    ("kcal derivation — expected: derived_null 2 · negative 0 · zero_but_caloric 0", """
        SELECT count(*) AS total,
               count(kcal_source)                                    AS with_source,
               count(kcal)                                           AS with_derived,
               count(*) FILTER (WHERE kcal IS NULL)                  AS derived_null,
               count(*) FILTER (WHERE kcal < 0)                      AS negative,
               count(*) FILTER (WHERE kcal <= 0 AND kcal_source > 0) AS zero_but_caloric,
               ROUND((percentile_cont(0.5) WITHIN GROUP (
                 ORDER BY abs(kcal-kcal_source)/NULLIF(kcal_source,0))*100)::numeric,2)
                                                                     AS median_dev_pct
        FROM foods"""),

    # Which rows the NULL rule caught, and why. The macros are NOT NULL on
    # foods, so a NULL kcal can only come from the rule or from the step never
    # having run at all — the check the `complete` bug lacked.
    ("kcal IS NULL — declared calories with no macro base to derive from", """
        SELECT source_code, name_he, kcal_source
        FROM foods WHERE kcal IS NULL ORDER BY kcal_source DESC"""),

    # If this is 0, the ethanol term silently did nothing — most likely because
    # nutrients has no row with code 'alcohol' and the lookup matched nothing.
    ("Ethanol term — rows where alcohol contributes. 0 here means the lookup failed", """
        SELECT count(*) AS rows_with_alcohol,
               ROUND(max(fn.value),1) AS max_g_per_100g
        FROM food_nutrients fn
        JOIN nutrients n ON n.id = fn.nutrient_id
        WHERE n.code = 'alcohol' AND fn.value > 0"""),

    ("Atwater outliers — the curation gate. eligible must stay 0 until each is ruled on", """
        SELECT count(*) AS outliers,
               count(*) FILTER (WHERE menu_eligible) AS eligible
        FROM v_kcal_outliers"""),

    # 2,758 of 4,620 until 29.08.2026; the four restored meat and fish items
    # all carry the nine essential amino acids, so both totals moved by four.
    ("Complete proteins — 2,762 of 4,624 expected", """
        SELECT count(*) FILTER (WHERE complete)     AS complete,
               count(*) FILTER (WHERE NOT complete) AS incomplete
        FROM foods"""),

    # The judgement, shown rather than asserted. carb_g must read 0 and the
    # derived kcal must land within ~1% of the file's declared energy — if a
    # real carbohydrate value were hiding behind the blank, kcal would fall
    # short of kcal_source by 4 kcal per missing gram.
    (f"Carbohydrate read as zero by judgement — expected {len(CARB_ZERO_BY_JUDGEMENT)} rows", f"""
        SELECT source_code, name_he, protein_g, fat_g, carb_g, kcal, kcal_source,
               ROUND(100 * (kcal - kcal_source) / NULLIF(kcal_source,0), 1) AS pct_gap
        FROM foods
        WHERE source_code IN ({CARB_ZERO_SQL})
        ORDER BY source_code"""),

    ("Recipe components dropped (the component never reached foods)", """
        SELECT count(*) FROM src_recipe_components rc
        WHERE NOT EXISTS (SELECT 1 FROM foods c WHERE c.source_code = rc.component_code)
           OR NOT EXISTS (SELECT 1 FROM foods r WHERE r.source_code = rc.recipe_code)"""),

    # A count over foods, not a tagging state — by_weight lives on
    # food_curation and is set during curation, not derived here. This is the
    # shortlist that curation should default to by_weight = true.
    ("Entries with no human serving unit — the by_weight shortlist for curation", """
        SELECT count(*) FROM foods f
        WHERE NOT EXISTS (SELECT 1 FROM food_servings s WHERE s.food_id = f.id)"""),

    ("Cross-check: structural recipe against makor=4. The critical figure: makor4 with no composition", """
        SELECT
          count(*) FILTER (WHERE EXISTS (SELECT 1 FROM food_recipe_components rc
                                         WHERE rc.recipe_id = f.id))  AS with_composition,
          count(*) FILTER (WHERE makor = 4)                           AS makor_4,
          count(*) FILTER (WHERE makor = 4 AND NOT EXISTS
                             (SELECT 1 FROM food_recipe_components rc
                              WHERE rc.recipe_id = f.id))             AS makor4_no_composition,
          count(*) FILTER (WHERE makor <> 4 AND EXISTS
                             (SELECT 1 FROM food_recipe_components rc
                              WHERE rc.recipe_id = f.id))             AS composition_not_makor4
        FROM foods f"""),

    ("Sample: 5 entries with their serving units", """
        SELECT f.name_he, string_agg(s.label_he || '=' || s.grams || 'ג',
                                     ' · ' ORDER BY s.grams) units
        FROM foods f JOIN food_servings s ON s.food_id = f.id
        GROUP BY f.id, f.name_he ORDER BY f.id LIMIT 5"""),
]

# Which source rows never reached foods, and which macro is to blame. Read by
# stop condition 3 and by nothing else — it deliberately does NOT sit in CHECKS,
# because printing this was the bug: carb_g is NOT NULL, so a source row with a
# blank macro cannot fail the INSERT, it simply never arrives, and a report
# nobody reads in time is not a guard. See open-questions.md #15.
#
# Each CASE mirrors the INSERT's own predicate — the regex, not IS NULL. The
# source stores a blank as an empty string at least as often as a JSON null, and
# an IS NULL test would name no field at all on those rows: a failure message
# reading "a macro is missing" and nothing else sends the reader back to
# searching by hand. COALESCE because `!~` yields NULL, not true, on a NULL.
# The carbohydrate arm carries the CARB_ZERO_BY_JUDGEMENT exemption, so a listed
# code is never reported as missing a carbohydrate it was ruled to have as zero.
MISSING_MACRO_SQL = f"""
    SELECT sf.code, sf.raw->>'shmmitzrach' AS name,
           trim(
             CASE WHEN COALESCE(sf.raw->>'protein','')       !~ '{NUM}'
                  THEN 'protein ' ELSE '' END ||
             CASE WHEN COALESCE(sf.raw->>'total_fat','')     !~ '{NUM}'
                  THEN 'fat ' ELSE '' END ||
             CASE WHEN COALESCE(sf.raw->>'carbohydrates','') !~ '{NUM}'
                   AND sf.code NOT IN ({CARB_ZERO_SQL})
                  THEN 'carbs ' ELSE '' END ||
             CASE WHEN COALESCE(sf.raw->>'food_energy','')   !~ '{NUM}'
                  THEN 'energy' ELSE '' END
           ) AS missing
    FROM src_foods sf
    WHERE NOT EXISTS (SELECT 1 FROM foods f WHERE f.source_code = sf.code)
    ORDER BY sf.code::int"""

# The stop conditions live in main(), not here, because they are not queries
# whose output gets printed — they decide whether the run is allowed to commit.
# See check_stop_conditions().


def check_stop_conditions(cur, out, curation_before):
    """The three conditions that abort the run. Returns a list of failures.

    These are not informative checks. Conditions 1 and 2 stand in for a foreign
    key: food_curation deliberately carries none to foods — a FK would conduct
    the TRUNCATE ... CASCADE rather than block it, which is the whole bug
    db/06_split_curation.sql closed. The integrity a FK would have given is
    enforced here instead, and it has to be enforced loudly: a stop condition
    that only prints is worth nothing, since the damage it reports has already
    been committed by the time anyone reads the report.

    Condition 3 guards the opposite direction and has nothing to do with
    food_curation: a source row that never reached foods at all. It was an
    ordinary printed check until 29.08.2026, and the same argument moved it
    here — see open-questions.md #15 and MISSING_MACRO_SQL.
    """
    failures = []
    out.write("\n▸ Stop conditions — the run is rolled back if any of the three fails\n")

    # 1. What replaces the foreign key. A curation row whose source_code is no
    #    longer in foods means this import dropped an item out from under
    #    tagging work that still exists.
    cur.execute("SELECT count(*) FROM v_curation_orphans")
    orphans = cur.fetchone()[0]
    if orphans:
        cur.execute("""SELECT source_code, category, menu_eligible, curated_by
                       FROM v_curation_orphans ORDER BY source_code LIMIT 50""")
        rows = "\n".join("        " + " | ".join(
            "∅" if v is None else str(v) for v in r) for r in cur.fetchall())
        failures.append(
            f"v_curation_orphans returned {orphans} rows. Curation work points "
            f"at source_codes that are no longer in foods — the source file "
            f"dropped them, or their code changed:\n{rows}")
    else:
        out.write("    ✓ v_curation_orphans — 0 rows\n")

    # 2. The direct test that TRUNCATE did not reach food_curation. Counted
    #    before the TRUNCATE step and again after everything, so a loss caused
    #    by this run cannot hide behind a curation session that ran in parallel.
    cur.execute("SELECT count(*) FROM food_curation")
    curation_after = cur.fetchone()[0]
    if curation_after < curation_before:
        failures.append(
            f"food_curation lost rows during this run: {curation_before} → "
            f"{curation_after}. Something reached it. Check for a foreign key "
            f"to foods — there must not be one.")
    else:
        out.write(f"    ✓ food_curation — {curation_before} rows before, "
                  f"{curation_after} after\n")

    # 3. Rule #15, enforced rather than reported. The four codes in
    #    CARB_ZERO_BY_JUDGEMENT are the only source rows a missing macro is
    #    allowed to touch; anything else here is a source update that introduced
    #    a new gap, and it must be ruled on before the database is rebuilt
    #    around its absence. Decided 29.08.2026 — see docs/decisions.md,
    #    "תיקון לנוסח כלל #15", and docs/spec/05-food-db.md §5.0.1.
    cur.execute(MISSING_MACRO_SQL)
    dropped = cur.fetchall()
    if dropped:
        rows = "\n".join(f"        {code} | {name} | missing: {missing}"
                         for code, name, missing in dropped[:50])
        failures.append(
            f"{len(dropped)} src_foods rows never reached foods — a macro is "
            f"blank and the code is not in CARB_ZERO_BY_JUDGEMENT. Either the "
            f"source file changed, or the item belongs on that list under rule "
            f"#15. Deciding that is a nutritional judgement, not a code "
            f"change:\n{rows}")
    else:
        out.write(f"    ✓ every src_foods row reached foods — no macro blank "
                  f"outside the {len(CARB_ZERO_BY_JUDGEMENT)} judged codes\n")

    return failures


def main():
    url = load_database_url()

    out = io.StringIO()
    failures = []
    try:
        conn_ctx = psycopg.connect(url)
    except psycopg.OperationalError as exc:
        # psycopg does not echo the password, but the DSN reaches this message
        # from several directions. Mask on the way out rather than trusting it.
        sys.exit(f"Cannot connect to {mask_dsn(url)}\n{exc}")

    with conn_ctx as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM src_foods")
            if cur.fetchone()[0] == 0:
                sys.exit("src_foods is empty — run 03_load_source.py first")

            # Taken before the TRUNCATE step, so stop condition 2 measures this
            # run and nothing else.
            cur.execute("SELECT count(*) FROM food_curation")
            curation_before = cur.fetchone()[0]

            for title, sql in STEPS:
                cur.execute(sql)
                out.write(f"✓ {title}"
                          f"{f' — {cur.rowcount} rows' if cur.rowcount >= 0 else ''}\n")
                if title.startswith("Truncate"):
                    cur.executemany(
                        "INSERT INTO nutrients (code, name_he, unit) VALUES (%s,%s,%s)",
                        [(c, n, u) for c, (n, u) in NUTRIENTS.items()])
                    out.write(f"✓ nutrients — {len(NUTRIENTS)} seeded from the official dictionary\n")

            for title, sql in CHECKS:
                out.write(f"\n▸ {title}\n")
                cur.execute(sql)
                for row in cur.fetchall():
                    out.write("    " + " | ".join(
                        "∅" if v is None else str(v) for v in row) + "\n")

            failures = check_stop_conditions(cur, out, curation_before)

        if failures:
            conn.rollback()
            out.write("\n✘ ABORTED — nothing was committed.\n")
            for f in failures:
                out.write(f"\n{f}\n")
        else:
            conn.commit()

    report = out.getvalue()
    (HERE / "transform_report.txt").write_text(report, encoding="utf-8")
    print(report)
    if failures:
        sys.exit(f"\n✘ Stop condition hit. The run was rolled back and the "
                 f"database is unchanged. Report: {HERE / 'transform_report.txt'}")
    print(f"\n✔ Saved: {HERE / 'transform_report.txt'} — hand this over.")


if __name__ == "__main__":
    main()
