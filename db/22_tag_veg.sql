-- Block 8י-ט — vegetable tagging: 74 new food_curation rows, tagged and NOT yet menu_eligible.
-- The list is db/block8_veg_codes.txt (8י-ה "yes", 76, less 3794 and 3766 removed in
-- 8י-ח: raw forms nobody eats, whose cooked twins 3981 and 3930 are on the list). None
-- of the 74 has a curation row today — V0 proves it — so nothing existing is touched.
-- Values per the 8י-ח decisions (docs/work/2026-09-13-block-8-veg.md, docs/decisions.md
-- 13.09.2026): the unit by the 30.08 rule on three paths — a whole unit when one item is
-- a serving (whole_only, 17), a cup or a serving for chopped and cooked vegetables (50),
-- and by_weight where the only unit is a leaf, a stalk, a thin slice or a spoon (7).
-- max_g for a whole_only item is an integer multiple of its unit (#50). prep 0 for raw and
-- for canned that is opened and eaten (33); prep 2 for anything cooked, frozen-cooked
-- included (41). kosher parve and tags {vegan} on all 74 — every meat and dairy recipe
-- was rejected in 8י-ה, and veg has no label-condition rows: nothing goes to block 7.
-- quality NULL, supp false. No spike MAX_G entry exists for any of them — the 12 MAX_G
-- keys are fat, protein, a date and a cheese, and the 9 vegetable seed items carry none.
-- Allergens deliberately UNREVIEWED (column default '{}', allergens_reviewed_at NULL) —
-- 8י-י sets them together with menu_eligible. curated_by 'yossi', curated_at now().
-- Counts asserted below: prep 0 × 33 · prep 2 × 41; whole_only 17; by_weight 7;
--   max_g 60: 1
--   max_g 100: 2
--   max_g 114: 1
--   max_g 144: 1
--   max_g 150: 5
--   max_g 155: 1
--   max_g 160: 3
--   max_g 161: 1
--   max_g 164: 1
--   max_g 165: 1
--   max_g 170: 1
--   max_g 171: 1
--   max_g 175: 1
--   max_g 176: 1
--   max_g 178: 3
--   max_g 180: 1
--   max_g 186: 1
--   max_g 189: 1
--   max_g 192: 1
--   max_g 198: 1
--   max_g 200: 10
--   max_g 208: 2
--   max_g 210: 2
--   max_g 214: 3
--   max_g 218: 1
--   max_g 220: 1
--   max_g 226: 2
--   max_g 230: 4
--   max_g 232: 1
--   max_g 240: 1
--   max_g 245: 2
--   max_g 250: 1
--   max_g 255: 2
--   max_g 266: 1
--   max_g 270: 3
--   max_g 272: 1
--   max_g 280: 1
--   max_g 290: 1
--   max_g 300: 5
--   max_g 304: 1
-- Same pattern as 20_tag_carb.sql: one transaction, a _pre snapshot of every column,
-- one INSERT, assertions, COMMIT. V0 pins the snapshot this file was written against,
-- so a second run fails before it touches anything.
-- Expected canonical snapshot afterwards: 423 · 190 · 105 · 37 · 44 · 4 · 190 · 0 · 0.

BEGIN;

CREATE TEMP TABLE _pre ON COMMIT DROP AS
  SELECT source_code, category, kosher, allergens, allergens_reviewed_at, tags,
         quality, supp, prep, by_weight, whole_only, max_g, menu_eligible,
         curated_by, curated_at, created_at, updated_at, excluded_reason
    FROM food_curation;

-- V0 — precondition: the snapshot this file expects, and none of the 74 has a
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
   WHERE source_code IN ('3566', '3570', '3588', '3590', '3594', '3595', '3612', '3617', '3626', '3638', '3647', '3665', '3667', '3672', '3673', '3735', '3748', '3752', '3754', '3756', '3762', '3767', '3772', '3774', '3776', '3778', '3801', '3804', '3812', '3819', '3833', '3839', '3843', '3847', '3849', '3852', '3901', '3912', '3920', '3924', '3929', '3930', '3932', '3933', '3948', '3949', '3954', '3956', '3981', '3985', '3988', '4023', '4024', '4032', '4040', '4063', '4067', '4068', '4077', '4082', '4086', '4091', '4092', '4096', '4124', '4148', '4159', '8219', '8240', '8292', '8308', '8567', '8838', '9694');
  IF tot <> 349 OR el <> 190 OR p <> 105 OR f <> 37 OR c <> 44 OR v <> 4
     OR vm <> 190 OR present <> 0 THEN
    RAISE EXCEPTION 'V0 failed: tot=% el=% p=% f=% c=% v=% view=% of the 74 already present=%',
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
  -- fresh vegetables (40)
  ('3748', 'veg', 'parve', '{vegan}', NULL, false, 0, false, false,    60, false, NULL, 'yossi', now()),  -- נבטים, אלפלפה, טריים
  ('3752', 'veg', 'parve', '{vegan}', NULL, false, 0, false, true ,   150, false, NULL, 'yossi', now()),  -- אספרגוס, טרי
  ('3754', 'veg', 'parve', '{vegan}', NULL, false, 0, false, false,   208, false, NULL, 'yossi', now()),  -- נבטי מש, נבטים סיניים, טרי
  ('3756', 'veg', 'parve', '{vegan}', NULL, false, 0, false, false,   220, false, NULL, 'yossi', now()),  -- שעועית ירוקה, טריה
  ('3762', 'veg', 'parve', '{vegan}', NULL, false, 0, false, true ,   164, false, NULL, 'yossi', now()),  -- סלק, טרי
  ('3767', 'veg', 'parve', '{vegan}', NULL, false, 0, false, false,   300, false, NULL, 'yossi', now()),  -- כרוב לבן, טרי
  ('3772', 'veg', 'parve', '{vegan}', NULL, false, 0, false, false,   210, false, NULL, 'yossi', now()),  -- כרוב סיני, טרי
  ('3774', 'veg', 'parve', '{vegan}', NULL, false, 0, true , false,   150, false, NULL, 'yossi', now()),  -- כרוב אדום, טרי
  ('3776', 'veg', 'parve', '{vegan}', NULL, false, 0, false, false,   200, false, NULL, 'yossi', now()),  -- כרובית, טריה
  ('3778', 'veg', 'parve', '{vegan}', NULL, false, 0, false, true ,   160, false, NULL, 'yossi', now()),  -- סלרי, כרפס, טרי
  ('3801', 'veg', 'parve', '{vegan}', NULL, false, 0, false, true ,   214, false, NULL, 'yossi', now()),  -- קולרבי, טרי
  ('3804', 'veg', 'parve', '{vegan}', NULL, false, 2, false, false,   208, false, NULL, 'yossi', now()),  -- כרישה, מבושלת ללא מלח
  ('3812', 'veg', 'parve', '{vegan}', NULL, false, 0, false, false,   210, false, NULL, 'yossi', now()),  -- פטריות, טריות
  ('3819', 'veg', 'parve', '{vegan}', NULL, false, 0, false, false,   100, false, NULL, 'yossi', now()),  -- בצל ירוק, טרי
  ('3833', 'veg', 'parve', '{vegan}', NULL, false, 0, false, false,   178, false, NULL, 'yossi', now()),  -- אפונה ירוקה, טריה
  ('3839', 'veg', 'parve', '{vegan}', NULL, false, 0, false, true ,   218, false, NULL, 'yossi', now()),  -- פלפל אדום, טרי
  ('3843', 'veg', 'parve', '{vegan}', NULL, false, 0, false, true ,   226, false, NULL, 'yossi', now()),  -- צנון, טרי
  ('3847', 'veg', 'parve', '{vegan}', NULL, false, 0, false, false,   189, false, NULL, 'yossi', now()),  -- אפונה סינית, טריה
  ('3849', 'veg', 'parve', '{vegan}', NULL, false, 0, false, true ,   290, false, NULL, 'yossi', now()),  -- קישואים, כהים, חיים, עם קליפה
  ('3852', 'veg', 'parve', '{vegan}', NULL, false, 0, false, true ,   240, false, NULL, 'yossi', now()),  -- לפת, טריה
  -- leafy greens (41)
  ('3566', 'veg', 'parve', '{vegan}', NULL, false, 0, false, false,   114, false, NULL, 'yossi', now()),  -- עלי סלק, מנגולד, טרי
  ('3570', 'veg', 'parve', '{vegan}', NULL, false, 2, true , false,   150, false, NULL, 'yossi', now()),  -- עלי סלק, מבושל עם מלח, ללא תוספת שומן
  ('3588', 'veg', 'parve', '{vegan}', NULL, false, 0, false, false,   165, false, NULL, 'yossi', now()),  -- חסה ערבית, חסה מסולסלת ESCAROLE Romaine
  ('3590', 'veg', 'parve', '{vegan}', NULL, false, 0, false, false,   100, false, NULL, 'yossi', now()),  -- תרד, טרי
  ('3594', 'veg', 'parve', '{vegan}', NULL, false, 2, true , false,   200, false, NULL, 'yossi', now()),  -- תרד, טרי, מבושל, ללא תוספת שומן, עם מלח
  ('3595', 'veg', 'parve', '{vegan}', NULL, false, 2, true , false,   200, false, NULL, 'yossi', now()),  -- תרד, קפוא, מבושל, ללא תוספת שומן, עם מלח
  ('8219', 'veg', 'parve', '{vegan}', NULL, false, 2, false, false,   175, false, NULL, 'yossi', now()),  -- מנגולד, מבושל, מסונן, ללא מלח, ללא תוספת שומן בבישול
  ('8567', 'veg', 'parve', '{vegan}', NULL, false, 2, false, false,   200, false, NULL, 'yossi', now()),  -- כרוב עלים, קייל ,KALE, מבושל, ללא תוספת שומן, עם מלח
  -- broccoli (42)
  ('3612', 'veg', 'parve', '{vegan}', NULL, false, 0, false, false,   176, false, NULL, 'yossi', now()),  -- ברוקולי, טרי
  ('3617', 'veg', 'parve', '{vegan}', NULL, false, 2, false, false,   200, false, NULL, 'yossi', now()),  -- ברוקולי, מבושל, קפוא, ללא תוספת שומן בבישול, עם מלח
  -- cooked vegetables (43)
  ('3901', 'veg', 'parve', '{vegan}', NULL, false, 2, false, false,   200, false, NULL, 'yossi', now()),  -- ירקות לקט מעורב, אפונה, גזר, שעועית ירוקה, תירס, תפוחי אדמה, קפוא, סנפרוסט
  ('3912', 'veg', 'parve', '{vegan}', NULL, false, 2, false, true ,   150, false, NULL, 'yossi', now()),  -- אספרגוס, מבושל, קפוא, ללא תוספת שומן בבישול
  ('3920', 'veg', 'parve', '{vegan}', NULL, false, 0, false, false,   270, false, NULL, 'yossi', now()),  -- שעועית ירוקה, מבושלת, משומרת, ללא תוספת שומן
  ('3924', 'veg', 'parve', '{vegan}', NULL, false, 2, false, false,   270, false, NULL, 'yossi', now()),  -- שעועית צהובה, קפואה, מבושלת, ללא תוספת שומן, עם מלח
  ('3929', 'veg', 'parve', '{vegan}', NULL, false, 0, false, false,   300, false, NULL, 'yossi', now()),  -- סלק, מבושל, משומר, ללא תוספת שומן
  ('3930', 'veg', 'parve', '{vegan}', NULL, false, 2, false, false,   155, false, NULL, 'yossi', now()),  -- כרוב ניצנים, מבושל, טרי, ללא תוספת שומן, עם מלח
  ('3932', 'veg', 'parve', '{vegan}', NULL, false, 2, false, false,   280, false, NULL, 'yossi', now()),  -- כרוב סיני, מבושל, ללא תוספת שומן
  ('3933', 'veg', 'parve', '{vegan}', NULL, false, 2, false, false,   214, false, NULL, 'yossi', now()),  -- כרוב לבן, מבושל עם מלח, ללא תוספת שומן בבישול
  ('3948', 'veg', 'parve', '{vegan}', NULL, false, 2, false, false,   300, false, NULL, 'yossi', now()),  -- כרוב אדום, מבושל, ללא תוספת שומן בבישול, עם מלח
  ('3949', 'veg', 'parve', '{vegan}', NULL, false, 2, false, false,   300, false, NULL, 'yossi', now()),  -- כרוב מסולסל, מבושל, ללא תוספת שומן בבישול, עם מלח
  ('3954', 'veg', 'parve', '{vegan}', NULL, false, 2, false, false,   250, false, NULL, 'yossi', now()),  -- כרובית, מבושלת, קפואה, ללא תוספת שומן בבישול, עם מלח
  ('3956', 'veg', 'parve', '{vegan}', NULL, false, 2, false, false,   150, false, NULL, 'yossi', now()),  -- סלרי, כרפס, מבושל, ללא תוספת שומן בבישול, עם מלח
  ('3981', 'veg', 'parve', '{vegan}', NULL, false, 2, false, false,   198, false, NULL, 'yossi', now()),  -- חצילים מבושלים עם מלח, ללא תוספת שומן בבישול
  ('3985', 'veg', 'parve', '{vegan}', NULL, false, 2, false, true ,   214, false, NULL, 'yossi', now()),  -- קולרבי, מבושל, עם מלח, ללא תוספת שומן בבישול
  ('3988', 'veg', 'parve', '{vegan}', NULL, false, 0, false, false,   161, false, NULL, 'yossi', now()),  -- פטריות, משומרות, מבושלות, ללא תוספת שומן בבישול
  ('4023', 'veg', 'parve', '{vegan}', NULL, false, 2, false, false,   178, false, NULL, 'yossi', now()),  -- אפונה ירוקה, מבושלת, קפואה, ללא תוספת שומן בבישול, עם מלח
  ('4024', 'veg', 'parve', '{vegan}', NULL, false, 0, false, false,   178, false, NULL, 'yossi', now()),  -- אפונה ירוקה, מבושלת, משומרת, ללא תוספת שומן בבישול
  ('4032', 'veg', 'parve', '{vegan}', NULL, false, 2, false, true ,   266, false, NULL, 'yossi', now()),  -- פלפל ירוק, מבושל, ללא תוספת שומן בבישול, עם מלח
  ('4040', 'veg', 'parve', '{vegan}', NULL, false, 2, false, false,   272, false, NULL, 'yossi', now()),  -- פלפלים קלויים
  ('4063', 'veg', 'parve', '{vegan}', NULL, false, 2, false, false,   160, false, NULL, 'yossi', now()),  -- אפונה סינית, מבושלת, לפנ לסוג, ללא תוספת שומן בבישול
  ('4067', 'veg', 'parve', '{vegan}', NULL, false, 2, false, true ,   226, false, NULL, 'yossi', now()),  -- קישואים מבושלים עם מלח, ללא תוספת שומן בבישול
  ('4068', 'veg', 'parve', '{vegan}', NULL, false, 2, false, true ,   232, false, NULL, 'yossi', now()),  -- לפת מבושלת, ללא תוספת שומן בבישול, עם מלח
  ('8308', 'veg', 'parve', '{vegan}', NULL, false, 2, false, true ,   171, false, NULL, 'yossi', now()),  -- ארטישוק, תחתיות, קפואות, סנפרוסט
  ('8838', 'veg', 'parve', '{vegan}', NULL, false, 2, true , false,   170, false, NULL, 'yossi', now()),  -- שומר, מבושל, ללא תוספת שומן בבישול, עם מלח
  -- cooked & frozen vegetable mixes (44)
  ('4077', 'veg', 'parve', '{vegan}', NULL, false, 2, false, false,   270, false, NULL, 'yossi', now()),  -- שעועית ירוקה, עם בצל, מבושלת, ללא תוספת שומן, עם מלח
  ('4082', 'veg', 'parve', '{vegan}', NULL, false, 2, false, false,   192, false, NULL, 'yossi', now()),  -- חצילים מבושלים ברוטב עגבניות, ללא תוספת שומן
  ('4086', 'veg', 'parve', '{vegan}', NULL, false, 2, false, false,   304, false, NULL, 'yossi', now()),  -- ירקות מאודים, בצל, כרוב, סלרי ופלפל עם רסק עגבניות, ללא שמן
  ('4091', 'veg', 'parve', '{vegan}', NULL, false, 2, false, false,   230, false, NULL, 'yossi', now()),  -- אפונה ובצל, מבושלים, ללא תוספת שומן בבישול, עם מלח
  ('4092', 'veg', 'parve', '{vegan}', NULL, false, 2, false, false,   230, false, NULL, 'yossi', now()),  -- אפונה ופטריות, מבושלים, ללא לתוספת שומן בבישול
  ('4096', 'veg', 'parve', '{vegan}', NULL, false, 2, false, false,   180, false, NULL, 'yossi', now()),  -- קישואים מבושלים ברוטב עגבניות, ללא תוספת שומן , עם מלח
  ('4124', 'veg', 'parve', '{vegan}', NULL, false, 2, false, false,   160, false, NULL, 'yossi', now()),  -- ירקות מבושלים, בצל, גזר, סלרי ותפו"א ללא תוספת שמן
  ('4148', 'veg', 'parve', '{vegan}', NULL, false, 2, false, false,   230, false, NULL, 'yossi', now()),  -- ירקות, לקט תאילנדי,ברוקלי,פלפלים ואפונה, סנפרוסט
  ('4159', 'veg', 'parve', '{vegan}', NULL, false, 2, false, false,   200, false, NULL, 'yossi', now()),  -- ירקות, לקט מבושל עם מלח, בצל, ברוקולי, פטריות
  ('9694', 'veg', 'parve', '{vegan}', NULL, false, 2, true , false,   200, false, NULL, 'yossi', now()),  -- קישואים אפויים ללא שמן
  -- carrot (45)
  ('3626', 'veg', 'parve', '{vegan}', NULL, false, 0, false, true ,   186, false, NULL, 'yossi', now()),  -- גזר, טרי, בלי קליפה וקצוות
  ('3638', 'veg', 'parve', '{vegan}', NULL, false, 0, false, false,   144, false, NULL, 'yossi', now()),  -- גזר, מבושל, משומר, ללא תוספת שומן בבישול
  -- pumpkin & squash (46)
  ('8240', 'veg', 'parve', '{vegan}', NULL, false, 2, false, false,   245, false, NULL, 'yossi', now()),  -- דלעת, מבושלת, עם מלח, ללא תוספת שומן בבישול
  ('8292', 'veg', 'parve', '{vegan}', NULL, false, 0, false, false,   245, false, NULL, 'yossi', now()),  -- דלעת, משומרת, מבושלת ללא תוספת שומן בבישול
  -- tomatoes, fresh & cooked (47)
  ('3665', 'veg', 'parve', '{vegan}', NULL, false, 2, false, true ,   300, false, NULL, 'yossi', now()),  -- עגבניות, מבושלות, לפנ לסוג, לפנ לשיטת הבישול, עם מלח
  ('3667', 'veg', 'parve', '{vegan}', NULL, false, 2, false, true ,   200, false, NULL, 'yossi', now()),  -- עגבניות, טריות, בגריל
  ('3672', 'veg', 'parve', '{vegan}', NULL, false, 0, false, false,   255, false, NULL, 'yossi', now()),  -- עגבניות, משומרות, מבושלות
  ('3673', 'veg', 'parve', '{vegan}', NULL, false, 0, false, false,   255, false, NULL, 'yossi', now()),  -- עגבניות מקולפות קוביות/חתוכות/שלמות, טל
  ('3735', 'veg', 'parve', '{vegan}', NULL, false, 2, true , false,   200, false, NULL, 'yossi', now()),  -- עגבניות ובצל, מבושלים, ללא תוספת שומן, עם מלח
  -- peas & carrots (48)
  ('3647', 'veg', 'parve', '{vegan}', NULL, false, 0, false, false,   230, false, NULL, 'yossi', now());  -- אפונה וגזר, מבושלים, משומרים,ללא תוספת שומן בבישול

-- The new rows, for the assertions below
CREATE TEMP TABLE _new ON COMMIT DROP AS
  SELECT c.* FROM food_curation c
   WHERE NOT EXISTS (SELECT 1 FROM _pre p WHERE p.source_code = c.source_code);

-- Raw output for the record, before the assertions
SELECT source_code, category, kosher, tags, quality, supp, prep, by_weight,
       whole_only, max_g, menu_eligible, allergens, allergens_reviewed_at, curated_by
  FROM _new ORDER BY source_code::int;

-- V1 — exactly 74 rows added, nothing removed, and the new set is exactly the codes file
DO $$
DECLARE added int; removed int; who text;
BEGIN
  SELECT count(*), string_agg(source_code, ',' ORDER BY source_code::int)
    INTO added, who FROM _new;
  SELECT count(*) INTO removed
    FROM _pre p LEFT JOIN food_curation c USING (source_code)
   WHERE c.source_code IS NULL;
  IF added <> 74 OR removed <> 0 OR who IS DISTINCT FROM
     '3566,3570,3588,3590,3594,3595,3612,3617,3626,3638,3647,3665,3667,3672,3673,3735,3748,3752,3754,3756,3762,3767,3772,3774,3776,3778,3801,3804,3812,3819,3833,3839,3843,3847,3849,3852,3901,3912,3920,3924,3929,3930,3932,3933,3948,3949,3954,3956,3981,3985,3988,4023,4024,4032,4040,4063,4067,4068,4077,4082,4086,4091,4092,4096,4124,4148,4159,8219,8240,8292,8308,8567,8838,9694' THEN
    RAISE EXCEPTION 'V1 failed: % added, % removed, new set = %', added, removed, who;
  END IF;
END $$;

-- V2 — the constants on every row: veg, parve, supp false, quality NULL, allergens
-- '{}' and unreviewed, tags {vegan}, no exclusion, curated by yossi, menu fields present
DO $$
DECLARE n int; off int;
BEGIN
  SELECT count(*),
         count(*) FILTER (WHERE NOT (
             category = 'veg' AND kosher = 'parve' AND supp = false AND quality IS NULL
             AND allergens = '{}'::text[] AND allergens_reviewed_at IS NULL
             AND tags = '{vegan}'::text[] AND excluded_reason IS NULL
             AND curated_by = 'yossi' AND curated_at IS NOT NULL
             AND by_weight IS NOT NULL AND prep IS NOT NULL AND max_g IS NOT NULL))
    INTO n, off FROM _new;
  IF n <> 74 OR off <> 0 THEN
    RAISE EXCEPTION 'V2 failed: n=% off-spec=%', n, off;
  END IF;
END $$;

-- V3 — none of the 74 is menu_eligible
DO $$
DECLARE el int;
BEGIN
  SELECT count(*) FILTER (WHERE menu_eligible IS DISTINCT FROM false) INTO el FROM _new;
  IF el <> 0 THEN
    RAISE EXCEPTION 'V3 failed: % of the 74 are not menu_eligible = false', el;
  END IF;
END $$;

-- V4 — by_weight on exactly 7 and whole_only on exactly 17, both by name, never both
-- (whole_only_requires_a_unit). wo_bad, not `both`: BOTH is reserved in PL/pgSQL.
DO $$
DECLARE wo text; bw text; n_wo int; n_bw int; wo_bad int;
BEGIN
  SELECT string_agg(source_code, ',' ORDER BY source_code::int) FILTER (WHERE whole_only),
         string_agg(source_code, ',' ORDER BY source_code::int) FILTER (WHERE by_weight),
         count(*) FILTER (WHERE whole_only), count(*) FILTER (WHERE by_weight),
         count(*) FILTER (WHERE whole_only AND by_weight)
    INTO wo, bw, n_wo, n_bw, wo_bad FROM _new;
  IF n_wo <> 17 OR n_bw <> 7 OR wo_bad <> 0
     OR wo IS DISTINCT FROM '3626,3665,3667,3752,3762,3778,3801,3839,3843,3849,3852,3912,3985,4032,4067,4068,8308'
     OR bw IS DISTINCT FROM '3570,3594,3595,3735,3774,8838,9694' THEN
    RAISE EXCEPTION 'V4 failed: whole_only % (%) by_weight % (%) both=%', n_wo, wo, n_bw, bw, wo_bad;
  END IF;
END $$;

-- V5 — prep 0 on exactly 33 and prep 2 on exactly 41, both by name; no other value
DO $$
DECLARE p0 int; p2 int; other int; p0_who text; p2_who text;
BEGIN
  SELECT count(*) FILTER (WHERE prep = 0), count(*) FILTER (WHERE prep = 2),
         count(*) FILTER (WHERE prep IS NULL OR prep NOT IN (0, 2)),
         string_agg(source_code, ',' ORDER BY source_code::int) FILTER (WHERE prep = 0),
         string_agg(source_code, ',' ORDER BY source_code::int) FILTER (WHERE prep = 2)
    INTO p0, p2, other, p0_who, p2_who FROM _new;
  IF p0 <> 33 OR p2 <> 41 OR other <> 0
     OR p0_who IS DISTINCT FROM '3566,3588,3590,3612,3626,3638,3647,3672,3673,3748,3752,3754,3756,3762,3767,3772,3774,3776,3778,3801,3812,3819,3833,3839,3843,3847,3849,3852,3920,3929,3988,4024,8292'
     OR p2_who IS DISTINCT FROM '3570,3594,3595,3617,3665,3667,3735,3804,3901,3912,3924,3930,3932,3933,3948,3949,3954,3956,3981,3985,4023,4032,4040,4063,4067,4068,4077,4082,4086,4091,4092,4096,4124,4148,4159,8219,8240,8308,8567,8838,9694' THEN
    RAISE EXCEPTION 'V5 failed: p0=% (%) p2=% (%) other=%', p0, p0_who, p2, p2_who, other;
  END IF;
END $$;

-- V6 — the 349 pre-existing rows are identical, every column, updated_at included
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
  IF n <> 349 OR moved <> 0 THEN
    RAISE EXCEPTION 'V6 failed: _pre holds % rows, % of them changed', n, moved;
  END IF;
END $$;

-- V7 — the four vegetables already eligible are untouched and still eligible veg
DO $$
DECLARE still int; moved int;
BEGIN
  SELECT count(*) INTO still FROM food_curation
   WHERE source_code IN ('3663', '3793', '3807', '3837')
     AND menu_eligible AND category = 'veg';
  SELECT count(*) INTO moved
    FROM _pre p JOIN food_curation c USING (source_code)
   WHERE p.source_code IN ('3663', '3793', '3807', '3837')
     AND (c.updated_at, c.menu_eligible, c.max_g, c.prep, c.by_weight, c.whole_only, c.allergens_reviewed_at)
         IS DISTINCT FROM
         (p.updated_at, p.menu_eligible, p.max_g, p.prep, p.by_weight, p.whole_only, p.allergens_reviewed_at);
  IF still <> 4 OR moved <> 0 THEN
    RAISE EXCEPTION 'V7 failed: % of the four still eligible veg, % changed', still, moved;
  END IF;
END $$;

-- V8 — max_g, every group by name
DO $$
DECLARE bad text;
BEGIN
  SELECT string_agg(g, ' | ') INTO bad FROM (
    SELECT 'max_g 60' AS g WHERE (SELECT string_agg(source_code, ',' ORDER BY source_code::int) FROM _new WHERE max_g = 60) IS DISTINCT FROM '3748'
    UNION ALL
    SELECT 'max_g 100' AS g WHERE (SELECT string_agg(source_code, ',' ORDER BY source_code::int) FROM _new WHERE max_g = 100) IS DISTINCT FROM '3590,3819'
    UNION ALL
    SELECT 'max_g 114' AS g WHERE (SELECT string_agg(source_code, ',' ORDER BY source_code::int) FROM _new WHERE max_g = 114) IS DISTINCT FROM '3566'
    UNION ALL
    SELECT 'max_g 144' AS g WHERE (SELECT string_agg(source_code, ',' ORDER BY source_code::int) FROM _new WHERE max_g = 144) IS DISTINCT FROM '3638'
    UNION ALL
    SELECT 'max_g 150' AS g WHERE (SELECT string_agg(source_code, ',' ORDER BY source_code::int) FROM _new WHERE max_g = 150) IS DISTINCT FROM '3570,3752,3774,3912,3956'
    UNION ALL
    SELECT 'max_g 155' AS g WHERE (SELECT string_agg(source_code, ',' ORDER BY source_code::int) FROM _new WHERE max_g = 155) IS DISTINCT FROM '3930'
    UNION ALL
    SELECT 'max_g 160' AS g WHERE (SELECT string_agg(source_code, ',' ORDER BY source_code::int) FROM _new WHERE max_g = 160) IS DISTINCT FROM '3778,4063,4124'
    UNION ALL
    SELECT 'max_g 161' AS g WHERE (SELECT string_agg(source_code, ',' ORDER BY source_code::int) FROM _new WHERE max_g = 161) IS DISTINCT FROM '3988'
    UNION ALL
    SELECT 'max_g 164' AS g WHERE (SELECT string_agg(source_code, ',' ORDER BY source_code::int) FROM _new WHERE max_g = 164) IS DISTINCT FROM '3762'
    UNION ALL
    SELECT 'max_g 165' AS g WHERE (SELECT string_agg(source_code, ',' ORDER BY source_code::int) FROM _new WHERE max_g = 165) IS DISTINCT FROM '3588'
    UNION ALL
    SELECT 'max_g 170' AS g WHERE (SELECT string_agg(source_code, ',' ORDER BY source_code::int) FROM _new WHERE max_g = 170) IS DISTINCT FROM '8838'
    UNION ALL
    SELECT 'max_g 171' AS g WHERE (SELECT string_agg(source_code, ',' ORDER BY source_code::int) FROM _new WHERE max_g = 171) IS DISTINCT FROM '8308'
    UNION ALL
    SELECT 'max_g 175' AS g WHERE (SELECT string_agg(source_code, ',' ORDER BY source_code::int) FROM _new WHERE max_g = 175) IS DISTINCT FROM '8219'
    UNION ALL
    SELECT 'max_g 176' AS g WHERE (SELECT string_agg(source_code, ',' ORDER BY source_code::int) FROM _new WHERE max_g = 176) IS DISTINCT FROM '3612'
    UNION ALL
    SELECT 'max_g 178' AS g WHERE (SELECT string_agg(source_code, ',' ORDER BY source_code::int) FROM _new WHERE max_g = 178) IS DISTINCT FROM '3833,4023,4024'
    UNION ALL
    SELECT 'max_g 180' AS g WHERE (SELECT string_agg(source_code, ',' ORDER BY source_code::int) FROM _new WHERE max_g = 180) IS DISTINCT FROM '4096'
    UNION ALL
    SELECT 'max_g 186' AS g WHERE (SELECT string_agg(source_code, ',' ORDER BY source_code::int) FROM _new WHERE max_g = 186) IS DISTINCT FROM '3626'
    UNION ALL
    SELECT 'max_g 189' AS g WHERE (SELECT string_agg(source_code, ',' ORDER BY source_code::int) FROM _new WHERE max_g = 189) IS DISTINCT FROM '3847'
    UNION ALL
    SELECT 'max_g 192' AS g WHERE (SELECT string_agg(source_code, ',' ORDER BY source_code::int) FROM _new WHERE max_g = 192) IS DISTINCT FROM '4082'
    UNION ALL
    SELECT 'max_g 198' AS g WHERE (SELECT string_agg(source_code, ',' ORDER BY source_code::int) FROM _new WHERE max_g = 198) IS DISTINCT FROM '3981'
    UNION ALL
    SELECT 'max_g 200' AS g WHERE (SELECT string_agg(source_code, ',' ORDER BY source_code::int) FROM _new WHERE max_g = 200) IS DISTINCT FROM '3594,3595,3617,3667,3735,3776,3901,4159,8567,9694'
    UNION ALL
    SELECT 'max_g 208' AS g WHERE (SELECT string_agg(source_code, ',' ORDER BY source_code::int) FROM _new WHERE max_g = 208) IS DISTINCT FROM '3754,3804'
    UNION ALL
    SELECT 'max_g 210' AS g WHERE (SELECT string_agg(source_code, ',' ORDER BY source_code::int) FROM _new WHERE max_g = 210) IS DISTINCT FROM '3772,3812'
    UNION ALL
    SELECT 'max_g 214' AS g WHERE (SELECT string_agg(source_code, ',' ORDER BY source_code::int) FROM _new WHERE max_g = 214) IS DISTINCT FROM '3801,3933,3985'
    UNION ALL
    SELECT 'max_g 218' AS g WHERE (SELECT string_agg(source_code, ',' ORDER BY source_code::int) FROM _new WHERE max_g = 218) IS DISTINCT FROM '3839'
    UNION ALL
    SELECT 'max_g 220' AS g WHERE (SELECT string_agg(source_code, ',' ORDER BY source_code::int) FROM _new WHERE max_g = 220) IS DISTINCT FROM '3756'
    UNION ALL
    SELECT 'max_g 226' AS g WHERE (SELECT string_agg(source_code, ',' ORDER BY source_code::int) FROM _new WHERE max_g = 226) IS DISTINCT FROM '3843,4067'
    UNION ALL
    SELECT 'max_g 230' AS g WHERE (SELECT string_agg(source_code, ',' ORDER BY source_code::int) FROM _new WHERE max_g = 230) IS DISTINCT FROM '3647,4091,4092,4148'
    UNION ALL
    SELECT 'max_g 232' AS g WHERE (SELECT string_agg(source_code, ',' ORDER BY source_code::int) FROM _new WHERE max_g = 232) IS DISTINCT FROM '4068'
    UNION ALL
    SELECT 'max_g 240' AS g WHERE (SELECT string_agg(source_code, ',' ORDER BY source_code::int) FROM _new WHERE max_g = 240) IS DISTINCT FROM '3852'
    UNION ALL
    SELECT 'max_g 245' AS g WHERE (SELECT string_agg(source_code, ',' ORDER BY source_code::int) FROM _new WHERE max_g = 245) IS DISTINCT FROM '8240,8292'
    UNION ALL
    SELECT 'max_g 250' AS g WHERE (SELECT string_agg(source_code, ',' ORDER BY source_code::int) FROM _new WHERE max_g = 250) IS DISTINCT FROM '3954'
    UNION ALL
    SELECT 'max_g 255' AS g WHERE (SELECT string_agg(source_code, ',' ORDER BY source_code::int) FROM _new WHERE max_g = 255) IS DISTINCT FROM '3672,3673'
    UNION ALL
    SELECT 'max_g 266' AS g WHERE (SELECT string_agg(source_code, ',' ORDER BY source_code::int) FROM _new WHERE max_g = 266) IS DISTINCT FROM '4032'
    UNION ALL
    SELECT 'max_g 270' AS g WHERE (SELECT string_agg(source_code, ',' ORDER BY source_code::int) FROM _new WHERE max_g = 270) IS DISTINCT FROM '3920,3924,4077'
    UNION ALL
    SELECT 'max_g 272' AS g WHERE (SELECT string_agg(source_code, ',' ORDER BY source_code::int) FROM _new WHERE max_g = 272) IS DISTINCT FROM '4040'
    UNION ALL
    SELECT 'max_g 280' AS g WHERE (SELECT string_agg(source_code, ',' ORDER BY source_code::int) FROM _new WHERE max_g = 280) IS DISTINCT FROM '3932'
    UNION ALL
    SELECT 'max_g 290' AS g WHERE (SELECT string_agg(source_code, ',' ORDER BY source_code::int) FROM _new WHERE max_g = 290) IS DISTINCT FROM '3849'
    UNION ALL
    SELECT 'max_g 300' AS g WHERE (SELECT string_agg(source_code, ',' ORDER BY source_code::int) FROM _new WHERE max_g = 300) IS DISTINCT FROM '3665,3767,3929,3948,3949'
    UNION ALL
    SELECT 'max_g 304' AS g WHERE (SELECT string_agg(source_code, ',' ORDER BY source_code::int) FROM _new WHERE max_g = 304) IS DISTINCT FROM '4086'
  ) x;
  IF bad IS NOT NULL THEN
    RAISE EXCEPTION 'V8 failed: %', bad;
  END IF;
END $$;

-- V9 — counts afterwards: 74 more rows, eligibility untouched, the view unchanged, and
-- the safety views clean
DO $$
DECLARE tot int; el int; p int; f int; c int; v int; vm int; mt int; orph int;
BEGIN
  SELECT count(*), count(*) FILTER (WHERE menu_eligible),
         count(*) FILTER (WHERE menu_eligible AND category='protein'),
         count(*) FILTER (WHERE menu_eligible AND category='fat'),
         count(*) FILTER (WHERE menu_eligible AND category='carb'),
         count(*) FILTER (WHERE menu_eligible AND category='veg')
    INTO tot, el, p, f, c, v FROM food_curation;
  SELECT count(*) INTO vm   FROM v_menu_foods;
  SELECT count(*) INTO mt   FROM v_eligible_missing_tags;
  SELECT count(*) INTO orph FROM v_curation_orphans;
  IF tot<>423 OR el<>190 OR p<>105 OR f<>37 OR c<>44 OR v<>4 OR vm<>190 OR mt<>0 OR orph<>0 THEN
    RAISE EXCEPTION 'V9 failed: tot=% el=% p=% f=% c=% v=% view=% missing_tags=% orphans=%',
      tot, el, p, f, c, v, vm, mt, orph;
  END IF;
END $$;

COMMIT;
