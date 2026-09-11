-- Block 5ה — fat tagging: 33 new food_curation rows, tagged and NOT yet menu_eligible.
-- The list is db/block5_fat_codes.txt: the block-4 "yes" list of 39 minus 1872
-- (roasting rule, decision of 11.09.2026). Five of the 38 were curated in 3ד
-- (1854 · 1873 · 1898 · 3223 · 4443) and are not touched; V3 proves it.
-- Values, per docs/work/2026-09-11-block-5-tagging.md and docs/decisions.md
-- (11.09.2026): category fat · kosher parve · tags {vegan} · prep 0 · supp false ·
-- quality NULL · menu_eligible false · excluded_reason NULL. max_g by family —
-- oils 40 · tahini & sesame 45 · seeds 45 · whole nuts 45 · nut butters 48 — with
-- the per-item exceptions 1825 = 15, 1826 = 15, 1900 = 15, 1899 = 30, 9440 = 30,
-- 1847 = 30, 1874 = 48.
-- by_weight and whole_only exactly as db/15_tagging_sheet.py printed them on
-- 11.09.2026 (_scratch/block-5e/tagging_sheet_fat38.txt, sha256 8ab8618f…):
-- by_weight true on ten — 1874 9440 1815 1819 1823 1826 1828 1834 1835 1848 —
-- whole_only true on 1825 1838 1845, and false on every by-weight row
-- (whole_only_requires_a_unit). Both are written explicitly on all 33.
-- Allergens are deliberately UNREVIEWED: allergens takes the column default
-- ('{}') and allergens_reviewed_at stays NULL — the "not reviewed" state of
-- CLAUDE.md §5, distinct from a reviewed '{}'. Block 6ש reviews them and only
-- then may flip menu_eligible. curated_by 'yossi' and curated_at now() mirror the
-- five 3ד rows.
-- Same pattern as 14_drop_three_fats.sql: one transaction, a _pre snapshot of
-- every column, one INSERT, assertions, COMMIT. V0 pins the snapshot this file
-- was written against, so a second run fails before it touches anything.
-- Expected canonical snapshot afterwards: 179 · 24 · 11 · 5 · 4 · 4 · 24 · 0 · 0.

BEGIN;

CREATE TEMP TABLE _pre ON COMMIT DROP AS
  SELECT source_code, category, kosher, allergens, allergens_reviewed_at, tags,
         quality, supp, prep, by_weight, whole_only, max_g, menu_eligible,
         curated_by, curated_at, created_at, updated_at, excluded_reason
    FROM food_curation;

-- V0 — precondition: the database is at the snapshot this file expects, and
-- none of the 33 has a curation row yet
DO $$
DECLARE tot int; el int; f int; vm int; present int;
BEGIN
  SELECT count(*), count(*) FILTER (WHERE menu_eligible),
         count(*) FILTER (WHERE menu_eligible AND category = 'fat')
    INTO tot, el, f FROM food_curation;
  SELECT count(*) INTO vm FROM v_menu_foods;
  SELECT count(*) INTO present FROM food_curation
   WHERE source_code IN ('1815','1819','1823','1825','1826','1828','1834','1835',
                         '1838','1845','1847','1848','1849','1859','1860','1869',
                         '1870','1874','1883','1890','1899','1900','4437','4444',
                         '4445','4448','4457','8242','8246','8263','9068','9440',
                         '9808');
  IF tot <> 146 OR el <> 24 OR f <> 5 OR vm <> 24 OR present <> 0 THEN
    RAISE EXCEPTION 'V0 failed: tot=% el=% f=% view=% of the 33 already present=%',
      tot, el, f, vm, present;
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
  -- §5.5 #1 olive & avocado oil — 40
  ('4444', 'fat', 'parve', '{vegan}', NULL, false, 0, false, false,  40, false, NULL, 'yossi', now()),  -- שמן זית כתית, מעודן
  ('9808', 'fat', 'parve', '{vegan}', NULL, false, 0, false, false,  40, false, NULL, 'yossi', now()),  -- שמן אבוקדו
  -- §5.5 #2 nut & sesame oil — 40
  ('4437', 'fat', 'parve', '{vegan}', NULL, false, 0, false, false,  40, false, NULL, 'yossi', now()),  -- שמן שקדים
  ('4457', 'fat', 'parve', '{vegan}', NULL, false, 0, false, false,  40, false, NULL, 'yossi', now()),  -- שמן אגוזי מלך
  ('4448', 'fat', 'parve', '{vegan}', NULL, false, 0, false, false,  40, false, NULL, 'yossi', now()),  -- שמן שומשום
  ('4445', 'fat', 'parve', '{vegan}', NULL, false, 0, false, false,  40, false, NULL, 'yossi', now()),  -- שמן בוטנים
  -- §5.5 #6 tahini & sesame — 45
  ('1890', 'fat', 'parve', '{vegan}', NULL, false, 0, false, false,  45, false, NULL, 'yossi', now()),  -- טחינה גולמית, שומשום מלא
  ('1883', 'fat', 'parve', '{vegan}', NULL, false, 0, false, false,  45, false, NULL, 'yossi', now()),  -- גרעיני שומשום קלופים
  ('8242', 'fat', 'parve', '{vegan}', NULL, false, 0, false, false,  45, false, NULL, 'yossi', now()),  -- שומשום, גרעינים מלאים
  -- §5.5 #7 other seeds — 45; 1874 goes with the butters (48); 1899, 9440 = 30; 1900 = 15
  ('1874', 'fat', 'parve', '{vegan}', NULL, false, 0, true,  false,  48, false, NULL, 'yossi', now()),  -- חמאת גרעיני חמניות — by weight
  ('1869', 'fat', 'parve', '{vegan}', NULL, false, 0, false, false,  45, false, NULL, 'yossi', now()),  -- גרעיני דלעת בלי קליפה
  ('1870', 'fat', 'parve', '{vegan}', NULL, false, 0, false, false,  45, false, NULL, 'yossi', now()),  -- גרעיני דלעת עם קליפה, לא קלויים
  ('1899', 'fat', 'parve', '{vegan}', NULL, false, 0, false, false,  30, false, NULL, 'yossi', now()),  -- זרעי פשתן
  ('9440', 'fat', 'parve', '{vegan}', NULL, false, 0, true,  false,  30, false, NULL, 'yossi', now()),  -- צ'יה — by weight
  ('1900', 'fat', 'parve', '{vegan}', NULL, false, 0, false, false,  15, false, NULL, 'yossi', now()),  -- פרג
  -- §5.5 #8 nuts & nut butters — whole nuts 45, butters 48; 1825, 1826 = 15; 1847 = 30
  ('1815', 'fat', 'parve', '{vegan}', NULL, false, 0, true,  false,  45, false, NULL, 'yossi', now()),  -- שקדים לא קלויים — by weight
  ('1819', 'fat', 'parve', '{vegan}', NULL, false, 0, true,  false,  48, false, NULL, 'yossi', now()),  -- חמאת שקדים, ירושלים — by weight
  ('1823', 'fat', 'parve', '{vegan}', NULL, false, 0, true,  false,  45, false, NULL, 'yossi', now()),  -- שקדים מולבנים — by weight
  ('1825', 'fat', 'parve', '{vegan}', NULL, false, 0, false, true,   15, false, NULL, 'yossi', now()),  -- אגוזי ברזיל — whole
  ('1826', 'fat', 'parve', '{vegan}', NULL, false, 0, true,  false,  15, false, NULL, 'yossi', now()),  -- חמאת אגוזי ברזיל — by weight
  ('1828', 'fat', 'parve', '{vegan}', NULL, false, 0, true,  false,  45, false, NULL, 'yossi', now()),  -- אגוזי קשיו — by weight
  ('1834', 'fat', 'parve', '{vegan}', NULL, false, 0, true,  false,  45, false, NULL, 'yossi', now()),  -- אגוזי לוז — by weight
  ('1835', 'fat', 'parve', '{vegan}', NULL, false, 0, true,  false,  48, false, NULL, 'yossi', now()),  -- חמאת אגוזי לוז — by weight
  ('1838', 'fat', 'parve', '{vegan}', NULL, false, 0, false, true,   45, false, NULL, 'yossi', now()),  -- אגוזי מקדמיה — whole
  ('8263', 'fat', 'parve', '{vegan}', NULL, false, 0, false, false,  45, false, NULL, 'yossi', now()),  -- בוטנים, טריים
  ('1845', 'fat', 'parve', '{vegan}', NULL, false, 0, false, true,   45, false, NULL, 'yossi', now()),  -- אגוזי פקאן — whole
  ('1847', 'fat', 'parve', '{vegan}', NULL, false, 0, false, false,  30, false, NULL, 'yossi', now()),  -- צנוברים
  ('1848', 'fat', 'parve', '{vegan}', NULL, false, 0, true,  false,  45, false, NULL, 'yossi', now()),  -- פיסטוק — by weight
  ('1849', 'fat', 'parve', '{vegan}', NULL, false, 0, false, false,  48, false, NULL, 'yossi', now()),  -- חמאת פיסטוק
  ('8246', 'fat', 'parve', '{vegan}', NULL, false, 0, false, false,  48, false, NULL, 'yossi', now()),  -- חמאת שקדים, ללא מלח
  ('9068', 'fat', 'parve', '{vegan}', NULL, false, 0, false, false,  48, false, NULL, 'yossi', now()),  -- חמאת שקדים, B&D
  ('1859', 'fat', 'parve', '{vegan}', NULL, false, 0, false, false,  48, false, NULL, 'yossi', now()),  -- חמאת בוטנים טבעית, B&D
  ('1860', 'fat', 'parve', '{vegan}', NULL, false, 0, false, false,  48, false, NULL, 'yossi', now());  -- חמאת בוטנים, דל נתרן

-- Raw output for the record, before the assertions: the rows that were not in _pre
SELECT source_code, category, kosher, allergens, allergens_reviewed_at, tags,
       quality, supp, prep, by_weight, whole_only, max_g, menu_eligible,
       excluded_reason, curated_by
  FROM food_curation
 WHERE source_code NOT IN (SELECT source_code FROM _pre)
 ORDER BY source_code::int;

-- V1 — exactly 33 rows added, nothing removed, and the new set is exactly the 33 codes
DO $$
DECLARE added int; removed int; who text;
BEGIN
  SELECT count(*), string_agg(c.source_code, ',' ORDER BY c.source_code::int)
    INTO added, who
    FROM food_curation c LEFT JOIN _pre p USING (source_code)
   WHERE p.source_code IS NULL;
  SELECT count(*) INTO removed
    FROM _pre p LEFT JOIN food_curation c USING (source_code)
   WHERE c.source_code IS NULL;
  IF added <> 33 OR removed <> 0 OR who IS DISTINCT FROM
     '1815,1819,1823,1825,1826,1828,1834,1835,1838,1845,1847,1848,1849,1859,1860,'
     '1869,1870,1874,1883,1890,1899,1900,4437,4444,4445,4448,4457,8242,8246,8263,'
     '9068,9440,9808' THEN
    RAISE EXCEPTION 'V1 failed: % added, % removed, new set = %', added, removed, who;
  END IF;
END $$;

-- V2 — the 33 carry the decided values: the constants on every row, by_weight on
-- exactly the ten, whole_only on exactly the three, and the max_g distribution
-- 40×6 · 45×13 · 48×8 · 15×3 · 30×3 with the seven named exceptions
DO $$
DECLARE n int; off int; bw int; bw_who text; wo_who text;
        g40 int; g45 int; g48 int; g15 int; g30 int; named int;
BEGIN
  SELECT count(*),
         count(*) FILTER (WHERE NOT (
             c.category = 'fat' AND c.kosher = 'parve'
             AND c.tags = '{vegan}'::text[] AND c.prep = 0 AND c.supp = false
             AND c.quality IS NULL AND c.menu_eligible = false
             AND c.excluded_reason IS NULL
             AND c.allergens = '{}'::text[] AND c.allergens_reviewed_at IS NULL
             AND c.curated_by = 'yossi' AND c.curated_at IS NOT NULL
             AND c.by_weight IS NOT NULL)),
         count(*) FILTER (WHERE c.by_weight),
         string_agg(c.source_code, ',' ORDER BY c.source_code::int) FILTER (WHERE c.by_weight),
         string_agg(c.source_code, ',' ORDER BY c.source_code::int) FILTER (WHERE c.whole_only),
         count(*) FILTER (WHERE c.max_g = 40), count(*) FILTER (WHERE c.max_g = 45),
         count(*) FILTER (WHERE c.max_g = 48), count(*) FILTER (WHERE c.max_g = 15),
         count(*) FILTER (WHERE c.max_g = 30)
    INTO n, off, bw, bw_who, wo_who, g40, g45, g48, g15, g30
    FROM food_curation c
   WHERE NOT EXISTS (SELECT 1 FROM _pre p WHERE p.source_code = c.source_code);
  SELECT count(*) INTO named FROM food_curation
   WHERE (source_code, max_g) IN (('1825',15), ('1826',15), ('1900',15),
                                  ('1899',30), ('9440',30), ('1847',30), ('1874',48));
  IF n <> 33 OR off <> 0 OR bw <> 10
     OR bw_who IS DISTINCT FROM '1815,1819,1823,1826,1828,1834,1835,1848,1874,9440'
     OR wo_who IS DISTINCT FROM '1825,1838,1845'
     OR g40 <> 6 OR g45 <> 13 OR g48 <> 8 OR g15 <> 3 OR g30 <> 3 OR named <> 7 THEN
    RAISE EXCEPTION 'V2 failed: n=% off-spec=% by_weight=% (%) whole_only=(%) max_g 40=% 45=% 48=% 15=% 30=% named=%',
      n, off, bw, bw_who, wo_who, g40, g45, g48, g15, g30, named;
  END IF;
END $$;

-- V3 — the 146 pre-existing rows are identical, every column, updated_at included
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
  IF n <> 146 OR moved <> 0 THEN
    RAISE EXCEPTION 'V3 failed: _pre holds % rows, % of them changed', n, moved;
  END IF;
END $$;

-- V4 — counts: 33 more rows, eligibility untouched, the view unchanged
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
  IF tot<>179 OR el<>24 OR p<>11 OR f<>5 OR c<>4 OR v<>4 OR vm<>24 THEN
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
