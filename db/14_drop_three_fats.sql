-- Block 4ג — three fat items leave menu_eligible.
--   4279 זיתים ירוקים · 4387 חמאה, ללא מלח, חפיסה · 4446 שמן ליפתית - קנולה
-- All three were curated in 3ד (30.08.2026) and withdrawn by the owner in the
-- block 4 review of 05.09.2026 — decision of 05.09.2026 in docs/decisions.md;
-- the owner's words are in docs/work/2026-09-05-block-4-curation.md.
-- Same pattern as 12_cottage_swap.sql: one transaction, a _pre snapshot, one
-- UPDATE, assertions, COMMIT. Nothing is inserted. The rows stay in
-- food_curation with excluded_reason NULL on purpose, like 493: the enum has
-- only 'ffq' and 'non_protein_nitrogen' — open question #35, decided before
-- block 8. Every other field on the three rows is asserted unchanged.
-- Expected canonical snapshot afterwards: 146 · 24 · 11 · 5 · 4 · 4 · 24 · 0 · 0.
-- V0 pins the snapshot this file was written against, so a second run fails
-- before it touches anything.

BEGIN;

CREATE TEMP TABLE _pre ON COMMIT DROP AS
  SELECT source_code, updated_at, menu_eligible, excluded_reason,
         category, kosher, allergens, allergens_reviewed_at, tags,
         quality, supp, prep, by_weight, whole_only, max_g,
         curated_by, curated_at
    FROM food_curation;

-- V0 — precondition: the three are menu_eligible fat rows, and the database is
-- at the snapshot this file expects
DO $$
DECLARE n int; tot int; el int; f int; vm int;
BEGIN
  SELECT count(*) INTO n FROM food_curation
   WHERE source_code IN ('4279','4387','4446')
     AND menu_eligible = true AND category = 'fat';
  SELECT count(*), count(*) FILTER (WHERE menu_eligible),
         count(*) FILTER (WHERE menu_eligible AND category = 'fat')
    INTO tot, el, f FROM food_curation;
  SELECT count(*) INTO vm FROM v_menu_foods;
  IF n <> 3 OR tot <> 146 OR el <> 27 OR f <> 8 OR vm <> 27 THEN
    RAISE EXCEPTION 'V0 failed: eligible fat among the three=% tot=% el=% f=% view=%',
      n, tot, el, f, vm;
  END IF;
END $$;

UPDATE food_curation
   SET menu_eligible = false
 WHERE source_code IN ('4279','4387','4446');

-- Raw output for the record, before the assertions
SELECT source_code, menu_eligible, excluded_reason, category, kosher,
       max_g, by_weight, whole_only, curated_by, updated_at
  FROM food_curation
 WHERE source_code IN ('4279','4387','4446')
 ORDER BY source_code;

-- V1 — the three are out, excluded_reason stays NULL, and no other field moved
DO $$
DECLARE n int;
BEGIN
  SELECT count(*) INTO n
    FROM food_curation c JOIN _pre p USING (source_code)
   WHERE c.source_code IN ('4279','4387','4446')
     AND c.menu_eligible = false
     AND c.excluded_reason IS NULL
     AND c.category = 'fat'
     AND (c.category, c.kosher, c.allergens, c.allergens_reviewed_at, c.tags,
          c.quality, c.supp, c.prep, c.by_weight, c.whole_only, c.max_g,
          c.curated_by, c.curated_at)
         IS NOT DISTINCT FROM
         (p.category, p.kosher, p.allergens, p.allergens_reviewed_at, p.tags,
          p.quality, p.supp, p.prep, p.by_weight, p.whole_only, p.max_g,
          p.curated_by, p.curated_at);
  IF n <> 3 THEN RAISE EXCEPTION 'V1 failed: % of 3 rows match', n; END IF;
END $$;

-- V2 — counts and category floors
DO $$
DECLARE tot int; el int; p int; f int; c int; v int;
BEGIN
  SELECT count(*), count(*) FILTER (WHERE menu_eligible),
         count(*) FILTER (WHERE menu_eligible AND category='protein'),
         count(*) FILTER (WHERE menu_eligible AND category='fat'),
         count(*) FILTER (WHERE menu_eligible AND category='carb'),
         count(*) FILTER (WHERE menu_eligible AND category='veg')
    INTO tot, el, p, f, c, v FROM food_curation;
  IF tot<>146 OR el<>24 OR p<>11 OR f<>5 OR c<>4 OR v<>4 THEN
    RAISE EXCEPTION 'V2 failed: tot=% el=% p=% f=% c=% v=%', tot, el, p, f, c, v;
  END IF;
END $$;

-- V3 — the view agrees: 24 rows, none of the three, and the fat pool is exactly
-- the five curated in 3ד and confirmed in block 4
DO $$
DECLARE n int; gone int; fats text;
BEGIN
  SELECT count(*) INTO n FROM v_menu_foods;
  IF n <> 24 THEN RAISE EXCEPTION 'V3 failed: v_menu_foods = %', n; END IF;
  SELECT count(*) INTO gone FROM v_menu_foods
   WHERE source_code IN ('4279','4387','4446');
  IF gone <> 0 THEN
    RAISE EXCEPTION 'V3 failed: % of the three still in the view', gone;
  END IF;
  SELECT string_agg(source_code, ',' ORDER BY source_code) INTO fats
    FROM v_menu_foods WHERE category = 'fat';
  IF fats IS DISTINCT FROM '1854,1873,1898,3223,4443' THEN
    RAISE EXCEPTION 'V3 failed: fat pool in view = %', fats;
  END IF;
END $$;

-- V4 — blast radius: exactly three pre-existing rows touched, and they are the
-- three; nothing added, nothing removed
DO $$
DECLARE touched int; who text; added int; removed int;
BEGIN
  SELECT count(*), string_agg(c.source_code, ',' ORDER BY c.source_code)
    INTO touched, who
    FROM food_curation c JOIN _pre p USING (source_code)
   WHERE c.updated_at IS DISTINCT FROM p.updated_at
      OR c.menu_eligible IS DISTINCT FROM p.menu_eligible;
  IF touched <> 3 OR who IS DISTINCT FROM '4279,4387,4446' THEN
    RAISE EXCEPTION 'V4 failed: % rows touched (%)', touched, who;
  END IF;
  SELECT count(*) INTO added FROM food_curation c
    LEFT JOIN _pre p USING (source_code) WHERE p.source_code IS NULL;
  SELECT count(*) INTO removed FROM _pre p
    LEFT JOIN food_curation c USING (source_code) WHERE c.source_code IS NULL;
  IF added <> 0 OR removed <> 0 THEN
    RAISE EXCEPTION 'V4 failed: % rows added, % rows removed', added, removed;
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
