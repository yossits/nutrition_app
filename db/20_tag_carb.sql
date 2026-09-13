-- Block 8פ-ז — carbohydrate tagging: 40 new food_curation rows, tagged and NOT yet menu_eligible.
-- The list is db/block8_carb_codes.txt (the 8פ-ד "yes" list: 23 from the candidate
-- sheet db/block8_carb_candidates.tsv and 17 pulled by name). None of the 40 has a
-- curation row today — V0 proves it — so nothing existing is touched.
-- Values per docs/work/2026-09-12-block-8-carb.md (the owner's table of 8פ-ו,
-- 13.09.2026) and docs/decisions.md 13.09.2026: the convention is taken from the
-- four carbs curated in 3ד — cooked grain and potato prep 2, bread and breakfast
-- cereal prep 0; the unit by the 30.08 rule (slice, whole unit, cup), and where no
-- reasonable unit exists, by_weight. Ceilings: slices 3 × the slice; whole units
-- 1–8 by unit weight; cooked grains 240 as rice and pasta already carry; potatoes
-- 242; sweet potato 248; breakfast cereal 60, quaker oats 80; corn 240 in a cup.
-- kosher parve on all 40 — the family proposal of the 8פ-ה2 sheet
-- (_scratch/block-8p/tagging_carb40.tsv, sha256 8638141f…). tags {vegan} on 39;
-- 2849 granola carries honey and gets {}. quality is NULL: §5.3 is a protein
-- scale and the CHECK only binds an eligible protein row. supp false on all 40.
-- No spike MAX_G equivalent exists for any of them — the 12 MAX_G entries are fat,
-- protein and a date, and the 12 carb-shaped seed items carry max_g = None.
-- Allergens deliberately UNREVIEWED (column default '{}', allergens_reviewed_at
-- NULL) — 8פ-ח reviews them. curated_by 'yossi', curated_at now(), as 18 sets them.
-- Counts asserted below: prep 0 × 26 · prep 2 × 14; whole_only 19; by_weight 7;
-- tags {vegan} 39 and {} on 2849;
--   max_g 42.4: 1
--   max_g 46: 2
--   max_g 60: 5
--   max_g 66: 1
--   max_g 70: 1
--   max_g 78: 1
--   max_g 80: 2
--   max_g 85: 1
--   max_g 90: 4
--   max_g 96: 1
--   max_g 100: 2
--   max_g 102: 2
--   max_g 120: 1
--   max_g 130: 1
--   max_g 240: 12
--   max_g 242: 2
--   max_g 248: 1
-- Same pattern as 18_tag_protein.sql: one transaction, a _pre snapshot of every
-- column, one INSERT, assertions, COMMIT. V0 pins the snapshot this file was
-- written against, so a second run fails before it touches anything.
-- Expected canonical snapshot afterwards: 349 · 150 · 105 · 37 · 4 · 4 · 150 · 0 · 0.

BEGIN;

CREATE TEMP TABLE _pre ON COMMIT DROP AS
  SELECT source_code, category, kosher, allergens, allergens_reviewed_at, tags,
         quality, supp, prep, by_weight, whole_only, max_g, menu_eligible,
         curated_by, curated_at, created_at, updated_at, excluded_reason
    FROM food_curation;

-- V0 — precondition: the snapshot this file expects, and none of the 40 has a
-- curation row yet
DO $$
DECLARE tot int; el int; p int; f int; c int; v int; vm int; present int;
BEGIN
  SELECT count(*), count(*) FILTER (WHERE menu_eligible),
         count(*) FILTER (WHERE menu_eligible AND category = 'protein'),
         count(*) FILTER (WHERE menu_eligible AND category = 'fat'),
         count(*) FILTER (WHERE menu_eligible AND category = 'carb'),
         count(*) FILTER (WHERE menu_eligible AND category = 'veg')
    INTO tot, el, p, f, c, v FROM food_curation;
  SELECT count(*) INTO vm FROM v_menu_foods;
  SELECT count(*) INTO present FROM food_curation
   WHERE source_code IN ('1919', '1923', '1932', '1940', '1955', '1980', '2005', '2051', '2062', '2064', '2534', '2558', '2668', '2714', '2727', '2773', '2828', '2831', '2838', '2849', '3456', '3464', '3660', '3962', '3963', '8199', '8342', '8354', '8468', '8552', '8811', '8818', '8887', '9550', '9595', '9620', '9643', '9729', '9821', '10127');
  IF tot <> 309 OR el <> 150 OR p <> 105 OR f <> 37 OR c <> 4 OR v <> 4
     OR vm <> 150 OR present <> 0 THEN
    RAISE EXCEPTION 'V0 failed: tot=% el=% p=% f=% c=% v=% view=% of the 40 already present=%',
      tot, el, p, f, c, v, vm, present;
  END IF;
END $$;

-- The one write. Column order:
--   source_code, category, kosher, tags, quality, supp, prep,
--   by_weight, whole_only, max_g, menu_eligible, excluded_reason, curated_by, curated_at
-- allergens and allergens_reviewed_at are omitted on purpose (default '{}', NULL).
INSERT INTO food_curation
  (source_code, category, kosher, tags, quality, supp, prep,
   by_weight, whole_only, max_g, menu_eligible, excluded_reason, curated_by, curated_at)
VALUES
  -- לחם (26)
  ('1919', 'carb', 'parve', '{vegan}', NULL, false, 0, false, true ,   102, false, NULL, 'yossi', now()),  -- לחם לבן, ברמן, אנג'ל, דוידוביץ, אילת
  ('1940', 'carb', 'parve', '{vegan}', NULL, false, 0, false, true ,   102, false, NULL, 'yossi', now()),  -- לחם קל, לבן
  ('2005', 'carb', 'parve', '{vegan}', NULL, false, 0, false, true ,    96, false, NULL, 'yossi', now()),  -- לחם דגנים, ברמן
  ('8342', 'carb', 'parve', '{vegan}', NULL, false, 0, false, true ,    78, false, NULL, 'yossi', now()),  -- לחם קל, חיטה מלאה, טרום נבוטה, ברמן לעניין קל
  ('8354', 'carb', 'parve', '{vegan}', NULL, false, 0, false, true ,    90, false, NULL, 'yossi', now()),  -- לחם שיפון 100%- לחם הארץ
  -- לחם אחיד, קובנה וטורטיות (27)
  ('2062', 'carb', 'parve', '{vegan}', NULL, false, 0, false, true ,    90, false, NULL, 'yossi', now()),  -- לחם אחיד, כהה, פרוס
  ('2064', 'carb', 'parve', '{vegan}', NULL, false, 0, false, true ,    90, false, NULL, 'yossi', now()),  -- לחם קל, אחיד, כהה, ברמן, דגנית עין בר, אנג'ל
  ('9595', 'carb', 'parve', '{vegan}', NULL, false, 0, false, true ,    90, false, NULL, 'yossi', now()),  -- לחם אחיד, מועשר בויטמינים, ודש
  -- לחם (26)
  ('1955', 'carb', 'parve', '{vegan}', NULL, false, 0, false, true ,   100, false, NULL, 'yossi', now()),  -- פיתה, דוידוביץ
  ('8887', 'carb', 'parve', '{vegan}', NULL, false, 0, false, true ,   100, false, NULL, 'yossi', now()),  -- פיתה, ג'פיתה, מקמח מלא, אנג'ל
  ('1980', 'carb', 'parve', '{vegan}', NULL, false, 0, false, true ,    85, false, NULL, 'yossi', now()),  -- בייגל, אנג'ל
  ('1923', 'carb', 'parve', '{vegan}', NULL, false, 0, false, true ,   130, false, NULL, 'yossi', now()),  -- לחם ג'בטה או פוקצ'ה, אנג'ל, דוידוביץ
  -- לחם אחיד, קובנה וטורטיות (27)
  ('2051', 'carb', 'parve', '{vegan}', NULL, false, 0, false, true ,    70, false, NULL, 'yossi', now()),  -- טורטיה, מתירס
  ('9729', 'carb', 'parve', '{vegan}', NULL, false, 0, false, true ,    80, false, NULL, 'yossi', now()),  -- טורטיה, קמח לבן
  -- מצות, פריכיות וקרקרים (28)
  ('2534', 'carb', 'parve', '{vegan}', NULL, false, 0, false, true ,    66, false, NULL, 'yossi', now()),  -- מצה, פת מצה, דננברג, מצות ראשון, מצות יהודה, כרמל
  ('2558', 'carb', 'parve', '{vegan}', NULL, false, 0, false, true ,    46, false, NULL, 'yossi', now()),  -- פריכיות אורז מלא עם תירס/כוסמת
  ('8468', 'carb', 'parve', '{vegan}', NULL, false, 0, false, true ,    46, false, NULL, 'yossi', now()),  -- פריכיות אורז מלא עם קינואה, B&D
  ('9821', 'carb', 'parve', '{vegan}', NULL, false, 0, false, true ,  42.4, false, NULL, 'yossi', now()),  -- פריכיות חיטה, קריספיות/קליליות
  -- לחם (26)
  ('1932', 'carb', 'parve', '{vegan}', NULL, false, 0, true , false,   120, false, NULL, 'yossi', now()),  -- לחם בגט, בונז'ור
  -- דגני בוקר וחיטה מבושלת (30)
  ('2849', 'carb', 'parve',      '{}', NULL, false, 0, true , false,    60, false, NULL, 'yossi', now()),  -- דגני בוקר, גרנולה
  ('9620', 'carb', 'parve', '{vegan}', NULL, false, 0, true , false,    60, false, NULL, 'yossi', now()),  -- דגני בוקר, ברנפלקס ללא גלוטן, תלמה
  -- דגנים, אורז ופסטה מבושלים (29)
  ('2668', 'carb', 'parve', '{vegan}', NULL, false, 2, false, false,   240, false, NULL, 'yossi', now()),  -- כוסמת, מבושלת, עם מלח, ללא תוספת שומן בבישול
  ('2714', 'carb', 'parve', '{vegan}', NULL, false, 2, false, false,   240, false, NULL, 'yossi', now()),  -- שיבולת שועל, מבושל, אינסטנט, ללא תוספת שומן בבישול
  ('2727', 'carb', 'parve', '{vegan}', NULL, false, 2, false, false,   240, false, NULL, 'yossi', now()),  -- אורז מלא, מבושל,רגיל/אינסטנט,ללא תוספת שומן בבישול
  ('2773', 'carb', 'parve', '{vegan}', NULL, false, 2, false, false,   240, false, NULL, 'yossi', now()),  -- קינואה מבושלת ללא תוספת שומן
  ('8811', 'carb', 'parve', '{vegan}', NULL, false, 2, false, false,   240, false, NULL, 'yossi', now()),  -- גריסי פנינה, מבושלים, ללא תוספת שומן בבישול
  ('8818', 'carb', 'parve', '{vegan}', NULL, false, 2, false, false,   240, false, NULL, 'yossi', now()),  -- אטריות אורז, מבושלות
  ('9550', 'carb', 'parve', '{vegan}', NULL, false, 2, false, false,   240, false, NULL, 'yossi', now()),  -- בורגול, מבושל עם מלח או משומר, ללא תוספת שומן בבישול
  ('10127', 'carb', 'parve', '{vegan}', NULL, false, 2, false, false,   240, false, NULL, 'yossi', now()),  -- קוסקוס מבושל ללא שמן עם מלח
  ('9643', 'carb', 'parve', '{vegan}', NULL, false, 2, true , false,   240, false, NULL, 'yossi', now()),  -- פתיתים אפוים, מבושלים, ללא גלוטן
  ('8552', 'carb', 'parve', '{vegan}', NULL, false, 2, true , false,   240, false, NULL, 'yossi', now()),  -- אטריות/פסטה, חיטה, מבושלות, עם מלח, ללא תוספת שמן בבישול
  -- תפוחי אדמה (31)
  ('3456', 'carb', 'parve', '{vegan}', NULL, false, 2, true , false,   242, false, NULL, 'yossi', now()),  -- תפוחי אדמה, אפויים, עם מלח, קליפה נאכלה, ללא תוספת שומן
  ('3464', 'carb', 'parve', '{vegan}', NULL, false, 2, true , false,   242, false, NULL, 'yossi', now()),  -- תפוחי אדמה, מבושלים, עם קליפה, עם מלח, ללא תוספת שומן
  -- דגני בוקר וחיטה מבושלת (30)
  ('2828', 'carb', 'parve', '{vegan}', NULL, false, 0, false, false,    60, false, NULL, 'yossi', now()),  -- דגני בוקר, קורנפלקס ללא סוכר ומלח, ללא גלוטן, דגש
  ('2831', 'carb', 'parve', '{vegan}', NULL, false, 0, false, false,    60, false, NULL, 'yossi', now()),  -- דגני בוקר, קורנפלקס UK ,KELLOGGS
  ('2838', 'carb', 'parve', '{vegan}', NULL, false, 0, false, false,    60, false, NULL, 'yossi', now()),  -- דגני בוקר, ברנפלקס ללא תוספת סוכר, תלמה
  ('8199', 'carb', 'parve', '{vegan}', NULL, false, 0, false, false,    80, false, NULL, 'yossi', now()),  -- שיבולת שועל, קוואקר, רגיל ואינסטנט, לא מבושל
  -- בטטה (32)
  ('3660', 'carb', 'parve', '{vegan}', NULL, false, 2, false, true ,   248, false, NULL, 'yossi', now()),  -- בטטה מבושלת, ללא קליפה, ללא תוספת שומן, עם מלח
  -- תירס (33)
  ('3962', 'carb', 'parve', '{vegan}', NULL, false, 2, false, false,   240, false, NULL, 'yossi', now()),  -- תירס, גרעינים, מבושל, קפוא, ללא תוספת שומן בבישול, עם מלח
  ('3963', 'carb', 'parve', '{vegan}', NULL, false, 0, false, false,   240, false, NULL, 'yossi', now());  -- תירס, מבושל, משומר, ללא תוספת שומן בבישול, עם מלח

-- The new rows, for the assertions below
CREATE TEMP TABLE _new ON COMMIT DROP AS
  SELECT c.* FROM food_curation c
   WHERE NOT EXISTS (SELECT 1 FROM _pre p WHERE p.source_code = c.source_code);

-- Raw output for the record, before the assertions
SELECT source_code, category, kosher, tags, quality, supp, prep, by_weight,
       whole_only, max_g, menu_eligible, allergens, allergens_reviewed_at, curated_by
  FROM _new ORDER BY source_code::int;

-- V1 — exactly 40 rows added, nothing removed, and the new set is exactly the 40 codes
DO $$
DECLARE added int; removed int; who text;
BEGIN
  SELECT count(*), string_agg(source_code, ',' ORDER BY source_code::int)
    INTO added, who FROM _new;
  SELECT count(*) INTO removed
    FROM _pre p LEFT JOIN food_curation c USING (source_code)
   WHERE c.source_code IS NULL;
  IF added <> 40 OR removed <> 0 OR who IS DISTINCT FROM
     '1919,1923,1932,1940,1955,1980,2005,2051,2062,2064,2534,2558,2668,2714,2727,2773,2828,2831,2838,2849,3456,3464,3660,3962,3963,8199,8342,8354,8468,8552,8811,8818,8887,9550,9595,9620,9643,9729,9821,10127' THEN
    RAISE EXCEPTION 'V1 failed: % added, % removed, new set = %', added, removed, who;
  END IF;
END $$;

-- V2a — the constants on every row: carb, parve, not eligible, allergens unreviewed,
-- supp false, quality NULL, and the menu fields present
DO $$
DECLARE n int; off int;
BEGIN
  SELECT count(*),
         count(*) FILTER (WHERE NOT (
             category = 'carb' AND kosher = 'parve' AND menu_eligible = false
             AND allergens = '{}'::text[] AND allergens_reviewed_at IS NULL
             AND excluded_reason IS NULL AND curated_by = 'yossi'
             AND curated_at IS NOT NULL AND supp = false AND quality IS NULL
             AND by_weight IS NOT NULL AND prep IS NOT NULL AND max_g IS NOT NULL))
    INTO n, off FROM _new;
  IF n <> 40 OR off <> 0 THEN
    RAISE EXCEPTION 'V2a failed: n=% off-spec=%', n, off;
  END IF;
END $$;

-- V2b — prep 26 / 14, both groups by name
DO $$
DECLARE p0 int; p2 int; p0_who text; p2_who text;
BEGIN
  SELECT count(*) FILTER (WHERE prep = 0), count(*) FILTER (WHERE prep = 2),
         string_agg(source_code, ',' ORDER BY source_code::int) FILTER (WHERE prep = 0),
         string_agg(source_code, ',' ORDER BY source_code::int) FILTER (WHERE prep = 2)
    INTO p0, p2, p0_who, p2_who FROM _new;
  IF p0 <> 26 OR p2 <> 14
     OR p0_who IS DISTINCT FROM '1919,1923,1932,1940,1955,1980,2005,2051,2062,2064,2534,2558,2828,2831,2838,2849,3963,8199,8342,8354,8468,8887,9595,9620,9729,9821'
     OR p2_who IS DISTINCT FROM '2668,2714,2727,2773,3456,3464,3660,3962,8552,8811,8818,9550,9643,10127' THEN
    RAISE EXCEPTION 'V2b failed: p0=% (%) p2=% (%)', p0, p0_who, p2, p2_who;
  END IF;
END $$;

-- V2c — whole_only and by_weight by name, and never both (whole_only_requires_a_unit).
-- wo_bad, not `both`: BOTH is a reserved word and PL/pgSQL refuses it as a name.
DO $$
DECLARE wo text; bw text; wo_bad int;
BEGIN
  SELECT string_agg(source_code, ',' ORDER BY source_code::int) FILTER (WHERE whole_only),
         string_agg(source_code, ',' ORDER BY source_code::int) FILTER (WHERE by_weight),
         count(*) FILTER (WHERE whole_only AND by_weight)
    INTO wo, bw, wo_bad FROM _new;
  IF wo IS DISTINCT FROM '1919,1923,1940,1955,1980,2005,2051,2062,2064,2534,2558,3660,8342,8354,8468,8887,9595,9729,9821'
     OR bw IS DISTINCT FROM '1932,2849,3456,3464,8552,9620,9643'
     OR wo_bad <> 0 THEN
    RAISE EXCEPTION 'V2c failed: whole_only=(%) by_weight=(%) whole-and-by-weight=%', wo, bw, wo_bad;
  END IF;
END $$;

-- V2d — max_g, every group by name
DO $$
DECLARE m1 text; m2 text; m3 text; m4 text; m5 text; m6 text; m7 text; m8 text; m9 text; m10 text; m11 text; m12 text; m13 text; m14 text; m15 text; m16 text; m17 text;
BEGIN
  SELECT
         string_agg(source_code, ',' ORDER BY source_code::int) FILTER (WHERE max_g = 42.4),
         string_agg(source_code, ',' ORDER BY source_code::int) FILTER (WHERE max_g = 46),
         string_agg(source_code, ',' ORDER BY source_code::int) FILTER (WHERE max_g = 60),
         string_agg(source_code, ',' ORDER BY source_code::int) FILTER (WHERE max_g = 66),
         string_agg(source_code, ',' ORDER BY source_code::int) FILTER (WHERE max_g = 70),
         string_agg(source_code, ',' ORDER BY source_code::int) FILTER (WHERE max_g = 78),
         string_agg(source_code, ',' ORDER BY source_code::int) FILTER (WHERE max_g = 80),
         string_agg(source_code, ',' ORDER BY source_code::int) FILTER (WHERE max_g = 85),
         string_agg(source_code, ',' ORDER BY source_code::int) FILTER (WHERE max_g = 90),
         string_agg(source_code, ',' ORDER BY source_code::int) FILTER (WHERE max_g = 96),
         string_agg(source_code, ',' ORDER BY source_code::int) FILTER (WHERE max_g = 100),
         string_agg(source_code, ',' ORDER BY source_code::int) FILTER (WHERE max_g = 102),
         string_agg(source_code, ',' ORDER BY source_code::int) FILTER (WHERE max_g = 120),
         string_agg(source_code, ',' ORDER BY source_code::int) FILTER (WHERE max_g = 130),
         string_agg(source_code, ',' ORDER BY source_code::int) FILTER (WHERE max_g = 240),
         string_agg(source_code, ',' ORDER BY source_code::int) FILTER (WHERE max_g = 242),
         string_agg(source_code, ',' ORDER BY source_code::int) FILTER (WHERE max_g = 248)
    INTO m1, m2, m3, m4, m5, m6, m7, m8, m9, m10, m11, m12, m13, m14, m15, m16, m17 FROM _new;
  IF false
     OR m1 IS DISTINCT FROM '9821'
     OR m2 IS DISTINCT FROM '2558,8468'
     OR m3 IS DISTINCT FROM '2828,2831,2838,2849,9620'
     OR m4 IS DISTINCT FROM '2534'
     OR m5 IS DISTINCT FROM '2051'
     OR m6 IS DISTINCT FROM '8342'
     OR m7 IS DISTINCT FROM '8199,9729'
     OR m8 IS DISTINCT FROM '1980'
     OR m9 IS DISTINCT FROM '2062,2064,8354,9595'
     OR m10 IS DISTINCT FROM '2005'
     OR m11 IS DISTINCT FROM '1955,8887'
     OR m12 IS DISTINCT FROM '1919,1940'
     OR m13 IS DISTINCT FROM '1932'
     OR m14 IS DISTINCT FROM '1923'
     OR m15 IS DISTINCT FROM '2668,2714,2727,2773,3962,3963,8552,8811,8818,9550,9643,10127'
     OR m16 IS DISTINCT FROM '3456,3464'
     OR m17 IS DISTINCT FROM '3660' THEN
    RAISE EXCEPTION 'V2d failed: % % % % % % % % % % % % % % % % %', m1, m2, m3, m4, m5, m6, m7, m8, m9, m10, m11, m12, m13, m14, m15, m16, m17;
  END IF;
END $$;

-- V2e — tags {vegan} on 39, {} on 2849 alone, nothing else
DO $$
DECLARE vegan int; empty_who text; other int;
BEGIN
  SELECT count(*) FILTER (WHERE tags = '{vegan}'::text[]),
         string_agg(source_code, ',' ORDER BY source_code::int) FILTER (WHERE tags = '{}'::text[]),
         count(*) FILTER (WHERE tags <> '{vegan}'::text[] AND tags <> '{}'::text[])
    INTO vegan, empty_who, other FROM _new;
  IF vegan <> 39 OR empty_who IS DISTINCT FROM '2849' OR other <> 0 THEN
    RAISE EXCEPTION 'V2e failed: vegan=% empty=(%) other=%', vegan, empty_who, other;
  END IF;
END $$;

-- V3 — the 309 pre-existing rows are identical, every column, updated_at included
DO $$
DECLARE n int; moved int;
BEGIN
  SELECT count(*) INTO n FROM _pre;
  SELECT count(*) INTO moved
    FROM _pre p JOIN food_curation c USING (source_code)
   WHERE (c.category, c.kosher, c.allergens, c.allergens_reviewed_at, c.tags,
          c.quality, c.supp, c.prep, c.by_weight, c.whole_only, c.max_g,
          c.menu_eligible, c.curated_by, c.curated_at, c.created_at, c.updated_at,
          c.excluded_reason)
         IS DISTINCT FROM
         (p.category, p.kosher, p.allergens, p.allergens_reviewed_at, p.tags,
          p.quality, p.supp, p.prep, p.by_weight, p.whole_only, p.max_g,
          p.menu_eligible, p.curated_by, p.curated_at, p.created_at, p.updated_at,
          p.excluded_reason);
  IF n <> 309 OR moved <> 0 THEN
    RAISE EXCEPTION 'V3 failed: _pre holds % rows, % of them changed', n, moved;
  END IF;
END $$;

-- V4 — counts: 40 more rows, eligibility untouched, the view unchanged
DO $$
DECLARE tot int; el int; p int; f int; c int; v int; vm int;
BEGIN
  SELECT count(*), count(*) FILTER (WHERE menu_eligible),
         count(*) FILTER (WHERE menu_eligible AND category='protein'),
         count(*) FILTER (WHERE menu_eligible AND category='fat'),
         count(*) FILTER (WHERE menu_eligible AND category='carb'),
         count(*) FILTER (WHERE menu_eligible AND category='veg')
    INTO tot, el, p, f, c, v FROM food_curation;
  SELECT count(*) INTO vm FROM v_menu_foods;
  IF tot<>349 OR el<>150 OR p<>105 OR f<>37 OR c<>4 OR v<>4 OR vm<>150 THEN
    RAISE EXCEPTION 'V4 failed: tot=% el=% p=% f=% c=% v=% view=%', tot, el, p, f, c, v, vm;
  END IF;
END $$;

-- V5 — the safety views stay clean
DO $$
DECLARE mt int; orph int;
BEGIN
  SELECT count(*) INTO mt   FROM v_eligible_missing_tags;
  SELECT count(*) INTO orph FROM v_curation_orphans;
  IF mt <> 0 OR orph <> 0 THEN
    RAISE EXCEPTION 'V5 failed: missing_tags=% orphans=%', mt, orph;
  END IF;
END $$;

COMMIT;
