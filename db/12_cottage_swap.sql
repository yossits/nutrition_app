-- Block 3ח — cottage swap. 493 (0.5%) leaves menu_eligible;
-- 500 (3%) and 494 (5%) are curated in its place.
-- Decision of 31.08.2026, see docs/decisions.md.
-- 493 keeps excluded_reason NULL on purpose: the enum has only 'ffq' and
-- 'non_protein_nitrogen', and neither describes "not a shelf product".
-- That gap is an open question not yet opened in docs/open-questions.md, and it
-- is to be decided before block 8. No number is cited here on purpose: the
-- number is assigned when the question is written, in a separate documentation
-- block.

BEGIN;

CREATE TEMP TABLE _pre ON COMMIT DROP AS
  SELECT source_code, updated_at, menu_eligible FROM food_curation;

UPDATE food_curation
SET menu_eligible = false
WHERE source_code = '493';

INSERT INTO food_curation
  (source_code, category, kosher, allergens, allergens_reviewed_at, tags,
   quality, supp, prep, price, by_weight, whole_only, max_g,
   menu_eligible, curated_by, curated_at)
VALUES
  ('500', 'protein', 'dairy', ARRAY['Milk'], now(), '{}',
   3, false, 0, 1, false, false, 250, true, 'yossi', now()),
  ('494', 'protein', 'dairy', ARRAY['Milk'], now(), '{}',
   3, false, 0, 1, false, false, 250, true, 'yossi', now());

-- Raw output for the record, before the assertions
SELECT source_code, menu_eligible, excluded_reason, category, kosher,
       allergens, tags, quality, supp, prep, price, by_weight, whole_only,
       max_g, curated_by, allergens_reviewed_at IS NOT NULL AS ar
FROM food_curation WHERE source_code IN ('493','500','494') ORDER BY source_code;

-- V1 — 493 is out, and nothing else about it changed
DO $$
DECLARE r record;
BEGIN
  SELECT menu_eligible, excluded_reason, category::text, kosher::text
    INTO r FROM food_curation WHERE source_code='493';
  IF r.menu_eligible IS NOT false OR r.excluded_reason IS NOT NULL
     OR r.category <> 'protein' OR r.kosher <> 'dairy' THEN
    RAISE EXCEPTION 'V1 failed: 493 = %', r;
  END IF;
END $$;

-- V2 — the two new rows carry exactly the approved values
DO $$
DECLARE n int;
BEGIN
  SELECT count(*) INTO n FROM food_curation
  WHERE source_code IN ('500','494')
    AND category='protein' AND kosher='dairy'
    AND allergens = ARRAY['Milk'] AND tags = '{}'
    AND quality=3 AND supp=false AND prep=0 AND price=1
    AND by_weight=false AND whole_only=false AND max_g=250
    AND menu_eligible=true AND curated_by='yossi'
    AND allergens_reviewed_at IS NOT NULL;
  IF n <> 2 THEN RAISE EXCEPTION 'V2 failed: % of 2 rows match', n; END IF;
END $$;

-- V3 — counts and category floors
DO $$
DECLARE tot int; el int; p int; f int; c int; v int;
BEGIN
  SELECT count(*), count(*) FILTER (WHERE menu_eligible),
         count(*) FILTER (WHERE menu_eligible AND category='protein'),
         count(*) FILTER (WHERE menu_eligible AND category='fat'),
         count(*) FILTER (WHERE menu_eligible AND category='carb'),
         count(*) FILTER (WHERE menu_eligible AND category='veg')
    INTO tot, el, p, f, c, v FROM food_curation;
  IF tot<>146 OR el<>27 OR p<>11 OR f<>8 OR c<>4 OR v<>4 THEN
    RAISE EXCEPTION 'V3 failed: tot=% el=% p=% f=% c=% v=%', tot, el, p, f, c, v;
  END IF;
END $$;

-- V4 — the view agrees: 493 gone, 500 and 494 present, total 27
DO $$
DECLARE n int; swapped text;
BEGIN
  SELECT count(*) INTO n FROM v_menu_foods;
  IF n <> 27 THEN RAISE EXCEPTION 'V4 failed: v_menu_foods = %', n; END IF;
  SELECT string_agg(source_code, ',' ORDER BY source_code) INTO swapped
    FROM v_menu_foods WHERE source_code IN ('493','500','494');
  IF swapped IS DISTINCT FROM '494,500' THEN
    RAISE EXCEPTION 'V4 failed: view holds %', swapped;
  END IF;
END $$;

-- V5 — blast radius: exactly one pre-existing row touched, and it is 493
DO $$
DECLARE touched int; who text; added int;
BEGIN
  SELECT count(*), string_agg(c.source_code, ',')
    INTO touched, who
    FROM food_curation c JOIN _pre p USING (source_code)
   WHERE c.updated_at IS DISTINCT FROM p.updated_at
      OR c.menu_eligible IS DISTINCT FROM p.menu_eligible;
  IF touched <> 1 OR who <> '493' THEN
    RAISE EXCEPTION 'V5 failed: % rows touched (%)', touched, who;
  END IF;
  SELECT count(*) INTO added FROM food_curation c
    LEFT JOIN _pre p USING (source_code) WHERE p.source_code IS NULL;
  IF added <> 2 THEN RAISE EXCEPTION 'V5 failed: % rows added', added; END IF;
END $$;

-- V6 — the safety views stay clean
DO $$
DECLARE mt int; orph int;
BEGIN
  SELECT count(*) INTO mt   FROM v_eligible_missing_tags;
  SELECT count(*) INTO orph FROM v_curation_orphans;
  IF mt <> 0 OR orph <> 0 THEN
    RAISE EXCEPTION 'V6 failed: missing_tags=% orphans=%', mt, orph;
  END IF;
END $$;

COMMIT;
