-- Block 6ש-ג — fat allergens: 32 tagged fat rows are reviewed for allergens and
-- become menu_eligible. The pool goes 24 → 56, fat 5 → 37.
-- The list is db/block6_fat_flip_codes.txt, derived by query on 11.09.2026: the
-- codes of db/block5_fat_codes.txt whose row is menu_eligible = false, minus
-- 1826 (Brazil nut butter waits for a label, #13, and is not touched — V3 says so).
-- The allergen per code follows docs/work/2026-09-11-block-6-allergens.md, the
-- owner's table of 11.09.2026, under the rule of the same day (decisions.md):
-- tagging by ingredient identity only, "may contain" is not tagged.
--   {}            4444 9808 1869 1870 1899 9440 1900 1874              (8)
--   {Tree nuts}   4437 4457 1815 1819 1823 1825 1828 1834 1835 1838
--                 1845 1847 1848 1849 8246 9068                        (16)
--   {Sesame}      4448 1890 1883 8242                                  (4)
--   {Peanuts}     4445 8263 1859 1860                                  (4)
-- 'Peanuts' enters the database vocabulary here for the first time (from the
-- spike's list). Fat eligible with allergens = {} afterwards: 11 — the 8 above
-- plus 4443, 3223 and 1873 from 3ד.
-- Same pattern as 16_tag_fat.sql: one transaction, a _pre snapshot of every
-- column, the writes, assertions, COMMIT. V0 pins the snapshot this file was
-- written against, so a second run fails before it touches anything.
-- Expected canonical snapshot afterwards: 179 · 56 · 11 · 37 · 4 · 4 · 56 · 0 · 0.

BEGIN;

CREATE TEMP TABLE _pre ON COMMIT DROP AS
  SELECT source_code, category, kosher, allergens, allergens_reviewed_at, tags,
         quality, supp, prep, by_weight, whole_only, max_g, menu_eligible,
         curated_by, curated_at, created_at, updated_at, excluded_reason
    FROM food_curation;

-- V0 — precondition: the snapshot this file expects; all 32 present, fat, not
-- eligible, unreviewed, allergens {}; 1826 present and unreviewed
DO $$
DECLARE tot int; el int; f int; vm int; ready int; brazil int;
BEGIN
  SELECT count(*), count(*) FILTER (WHERE menu_eligible),
         count(*) FILTER (WHERE menu_eligible AND category = 'fat')
    INTO tot, el, f FROM food_curation;
  SELECT count(*) INTO vm FROM v_menu_foods;
  SELECT count(*) INTO ready FROM food_curation
   WHERE source_code IN ('4444','9808','1869','1870','1899','9440','1900','1874',
                         '4437','4457','1815','1819','1823','1825','1828','1834',
                         '1835','1838','1845','1847','1848','1849','8246','9068',
                         '4448','1890','1883','8242','4445','8263','1859','1860')
     AND category = 'fat' AND menu_eligible = false
     AND allergens_reviewed_at IS NULL AND allergens = '{}'::text[];
  SELECT count(*) INTO brazil FROM food_curation
   WHERE source_code = '1826' AND allergens_reviewed_at IS NULL AND menu_eligible = false;
  IF tot <> 179 OR el <> 24 OR f <> 5 OR vm <> 24 OR ready <> 32 OR brazil <> 1 THEN
    RAISE EXCEPTION 'V0 failed: tot=% el=% f=% view=% ready-of-32=% 1826-unreviewed=%',
      tot, el, f, vm, ready, brazil;
  END IF;
END $$;

-- The writes: one UPDATE per allergen group, per the owner's table
UPDATE food_curation
   SET allergens = '{}'::text[], allergens_reviewed_at = now(), menu_eligible = true
 WHERE source_code IN ('4444','9808','1869','1870','1899','9440','1900','1874');

UPDATE food_curation
   SET allergens = '{"Tree nuts"}'::text[], allergens_reviewed_at = now(), menu_eligible = true
 WHERE source_code IN ('4437','4457','1815','1819','1823','1825','1828','1834',
                       '1835','1838','1845','1847','1848','1849','8246','9068');

UPDATE food_curation
   SET allergens = '{Sesame}'::text[], allergens_reviewed_at = now(), menu_eligible = true
 WHERE source_code IN ('4448','1890','1883','8242');

UPDATE food_curation
   SET allergens = '{Peanuts}'::text[], allergens_reviewed_at = now(), menu_eligible = true
 WHERE source_code IN ('4445','8263','1859','1860');

-- Raw output for the record, before the assertions
SELECT source_code, menu_eligible, allergens, allergens_reviewed_at, category,
       kosher, max_g, by_weight, whole_only, updated_at
  FROM food_curation
 WHERE source_code IN ('4444','9808','1869','1870','1899','9440','1900','1874',
                       '4437','4457','1815','1819','1823','1825','1828','1834',
                       '1835','1838','1845','1847','1848','1849','8246','9068',
                       '4448','1890','1883','8242','4445','8263','1859','1860')
 ORDER BY source_code::int;

-- V1 — 179 rows, nothing added, nothing removed; the rows that differ from _pre
-- in any column are exactly the 32
DO $$
DECLARE tot int; added int; removed int; touched int; who text;
BEGIN
  SELECT count(*) INTO tot FROM food_curation;
  SELECT count(*) INTO added FROM food_curation c
    LEFT JOIN _pre p USING (source_code) WHERE p.source_code IS NULL;
  SELECT count(*) INTO removed FROM _pre p
    LEFT JOIN food_curation c USING (source_code) WHERE c.source_code IS NULL;
  SELECT count(*), string_agg(c.source_code, ',' ORDER BY c.source_code::int)
    INTO touched, who
    FROM food_curation c JOIN _pre p USING (source_code)
   WHERE (c.category, c.kosher, c.allergens, c.allergens_reviewed_at, c.tags,
          c.quality, c.supp, c.prep, c.by_weight, c.whole_only, c.max_g,
          c.menu_eligible, c.curated_by, c.curated_at, c.created_at, c.updated_at,
          c.excluded_reason)
         IS DISTINCT FROM
         (p.category, p.kosher, p.allergens, p.allergens_reviewed_at, p.tags,
          p.quality, p.supp, p.prep, p.by_weight, p.whole_only, p.max_g,
          p.menu_eligible, p.curated_by, p.curated_at, p.created_at, p.updated_at,
          p.excluded_reason);
  IF tot <> 179 OR added <> 0 OR removed <> 0 OR touched <> 32 OR who IS DISTINCT FROM
     '1815,1819,1823,1825,1828,1834,1835,1838,1845,1847,1848,1849,1859,1860,1869,'
     '1870,1874,1883,1890,1899,1900,4437,4444,4445,4448,4457,8242,8246,8263,9068,'
     '9440,9808' THEN
    RAISE EXCEPTION 'V1 failed: tot=% added=% removed=% touched=% (%)',
      tot, added, removed, touched, who;
  END IF;
END $$;

-- V2 — the 32: eligible and reviewed, allergens exactly per group by name, every
-- other column identical to _pre; fat eligible with {} is 11; 'Peanuts' is in
-- the vocabulary
DO $$
DECLARE n int; flipped int; g_empty text; g_nuts text; g_sesame text; g_peanuts text;
        other_moved int; clean_fat int; has_peanuts bool;
BEGIN
  SELECT count(*),
         count(*) FILTER (WHERE c.menu_eligible AND c.allergens_reviewed_at IS NOT NULL),
         string_agg(c.source_code, ',' ORDER BY c.source_code::int)
           FILTER (WHERE c.allergens = '{}'::text[]),
         string_agg(c.source_code, ',' ORDER BY c.source_code::int)
           FILTER (WHERE c.allergens = '{"Tree nuts"}'::text[]),
         string_agg(c.source_code, ',' ORDER BY c.source_code::int)
           FILTER (WHERE c.allergens = '{Sesame}'::text[]),
         string_agg(c.source_code, ',' ORDER BY c.source_code::int)
           FILTER (WHERE c.allergens = '{Peanuts}'::text[]),
         count(*) FILTER (WHERE
           (c.category, c.kosher, c.tags, c.quality, c.supp, c.prep, c.by_weight,
            c.whole_only, c.max_g, c.curated_by, c.curated_at, c.created_at,
            c.excluded_reason)
           IS DISTINCT FROM
           (p.category, p.kosher, p.tags, p.quality, p.supp, p.prep, p.by_weight,
            p.whole_only, p.max_g, p.curated_by, p.curated_at, p.created_at,
            p.excluded_reason))
    INTO n, flipped, g_empty, g_nuts, g_sesame, g_peanuts, other_moved
    FROM food_curation c JOIN _pre p USING (source_code)
   WHERE c.source_code IN ('4444','9808','1869','1870','1899','9440','1900','1874',
                           '4437','4457','1815','1819','1823','1825','1828','1834',
                           '1835','1838','1845','1847','1848','1849','8246','9068',
                           '4448','1890','1883','8242','4445','8263','1859','1860');
  SELECT count(*) INTO clean_fat FROM food_curation
   WHERE menu_eligible AND category = 'fat' AND allergens = '{}'::text[];
  SELECT EXISTS (SELECT 1 FROM food_curation, unnest(allergens) AS a WHERE a = 'Peanuts')
    INTO has_peanuts;
  IF n <> 32 OR flipped <> 32 OR other_moved <> 0
     OR g_empty   IS DISTINCT FROM '1869,1870,1874,1899,1900,4444,9440,9808'
     OR g_nuts    IS DISTINCT FROM '1815,1819,1823,1825,1828,1834,1835,1838,1845,1847,1848,1849,4437,4457,8246,9068'
     OR g_sesame  IS DISTINCT FROM '1883,1890,4448,8242'
     OR g_peanuts IS DISTINCT FROM '1859,1860,4445,8263'
     OR clean_fat <> 11 OR NOT has_peanuts THEN
    RAISE EXCEPTION 'V2 failed: n=% flipped=% other-moved=% empty=(%) nuts=(%) sesame=(%) peanuts=(%) clean-fat=% has-peanuts=%',
      n, flipped, other_moved, g_empty, g_nuts, g_sesame, g_peanuts, clean_fat, has_peanuts;
  END IF;
END $$;

-- V3 — the other 147 rows are identical, every column, updated_at included;
-- and 1826 by name: still not eligible, still unreviewed
DO $$
DECLARE others int; moved int; brazil int;
BEGIN
  SELECT count(*), count(*) FILTER (WHERE
           (c.category, c.kosher, c.allergens, c.allergens_reviewed_at, c.tags,
            c.quality, c.supp, c.prep, c.by_weight, c.whole_only, c.max_g,
            c.menu_eligible, c.curated_by, c.curated_at, c.created_at, c.updated_at,
            c.excluded_reason)
           IS DISTINCT FROM
           (p.category, p.kosher, p.allergens, p.allergens_reviewed_at, p.tags,
            p.quality, p.supp, p.prep, p.by_weight, p.whole_only, p.max_g,
            p.menu_eligible, p.curated_by, p.curated_at, p.created_at, p.updated_at,
            p.excluded_reason))
    INTO others, moved
    FROM _pre p JOIN food_curation c USING (source_code)
   WHERE p.source_code NOT IN ('4444','9808','1869','1870','1899','9440','1900','1874',
                               '4437','4457','1815','1819','1823','1825','1828','1834',
                               '1835','1838','1845','1847','1848','1849','8246','9068',
                               '4448','1890','1883','8242','4445','8263','1859','1860');
  SELECT count(*) INTO brazil FROM food_curation
   WHERE source_code = '1826' AND menu_eligible = false AND allergens_reviewed_at IS NULL;
  IF others <> 147 OR moved <> 0 OR brazil <> 1 THEN
    RAISE EXCEPTION 'V3 failed: others=% moved=% 1826-untouched=%', others, moved, brazil;
  END IF;
END $$;

-- V4 — counts: 32 more eligible, all of them fat, the view follows
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
  IF tot<>179 OR el<>56 OR p<>11 OR f<>37 OR c<>4 OR v<>4 OR vm<>56 THEN
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
