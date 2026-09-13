-- Block 8פ-ט — carbohydrate allergens: the 40 tagged carb rows of migration 20 are
-- reviewed for allergens and become menu_eligible; the pool goes 150 → 190, carb 4 → 44.
-- The list is db/block8_carb_codes.txt (8פ-ד). Allergen per code:
-- docs/work/2026-09-12-block-8-carb.md, the owner's table of 8פ-ח (13.09.2026),
-- under the rule of 11.09 — identity only, "may contain" is not tagged — with
-- oats read as gluten per the standard, and a named brand tagged by that
-- product's composition (decisions.md 13.09).
--   {Gluten}             24 — bread and pita 1919 1940 2005 8342 8354 2062 2064
--                         9595 1955 8887 1980 1923 1932 9729 · matza and wheat
--                         crispbread 2534 9821 · grains 2714 8811 9550 10127 8552
--                         · breakfast cereal 8199 2838 2831
--   {Gluten,Tree nuts}   1 — 2849 granola, the conservative reading
--   {}                   15 — 2051 2558 8468 2668 2727 2773 8818 9643 2828 9620
--                         3456 3464 3660 3962 3963
-- The two recipes by their component list (decisions.md 12.09), measured in this
-- sub-block: 2773 quinoa + water + salt → {}; 10127 dry couscous + water + salt → {Gluten}.
-- Three of the 40 sit in v_kcal_outliers — 2064, 2838, 8342 — and are flipped with
-- the rest by the ruling of 13.09 (decisions.md): all three are high-fibre "light"
-- products whose declared kcal follows Atwater 4/9/4 while db/05_derive_kcal.sql
-- adds fibre at 2 kcal/g, so the whole gap is 2 × fiber_g (23.0 · 47.6 · 22.0 per
-- 100 g). The flag sinks a row in the ranking; it does not exclude it (02.09).
-- V1b pins that membership, so a fourth outlier appearing here stops the run.
-- Not touched: the 4 carbs curated in 3ד (2659 2721 3459 8348) and the three
-- label-condition codes of 8פ-ד (2807 8966 8969, block 7).
-- Same pattern as 19_flip_protein.sql: one transaction, a _pre snapshot of every
-- column, one UPDATE per allergen group — each followed by W1–W3, a row-count
-- check against _pre — then V2–V6, COMMIT. V0 pins the snapshot this file was
-- written against, so a second run fails before it touches anything.
-- Expected canonical snapshot afterwards: 349 · 190 · 105 · 37 · 44 · 4 · 190 · 0 · 0.

BEGIN;

CREATE TEMP TABLE _pre ON COMMIT DROP AS
  SELECT source_code, category, kosher, allergens, allergens_reviewed_at, tags,
         quality, supp, prep, by_weight, whole_only, max_g, menu_eligible,
         curated_by, curated_at, created_at, updated_at, excluded_reason
    FROM food_curation;

-- V0 — precondition: the snapshot this file expects, so a second run fails
-- before it touches anything
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
  IF tot<>349 OR el<>150 OR p<>105 OR f<>37 OR c<>4 OR v<>4 OR vm<>150 OR mt<>0 OR orph<>0 THEN
    RAISE EXCEPTION 'V0 failed: tot=% el=% p=% f=% c=% v=% view=% missing_tags=% orphans=%',
      tot, el, p, f, c, v, vm, mt, orph;
  END IF;
END $$;

-- V1 — the 40 all exist: carb, not eligible, unreviewed, and the menu fields the
-- CHECK constraints read are in place (kosher, prep, by_weight; quality is NULL
-- on purpose — eligible_protein_requires_quality binds protein only)
DO $$
DECLARE present int; ready int;
BEGIN
  SELECT count(*),
         count(*) FILTER (WHERE category = 'carb' AND menu_eligible = false
                            AND allergens_reviewed_at IS NULL
                            AND allergens = '{}'::text[]
                            AND kosher IS NOT NULL
                            AND prep IS NOT NULL AND by_weight IS NOT NULL)
    INTO present, ready
    FROM food_curation
   WHERE source_code IN ('1919', '1923', '1932', '1940', '1955', '1980',
                         '2005', '2051', '2062', '2064', '2534', '2558',
                         '2668', '2714', '2727', '2773', '2828', '2831',
                         '2838', '2849', '3456', '3464', '3660', '3962',
                         '3963', '8199', '8342', '8354', '8468', '8552',
                         '8811', '8818', '8887', '9550', '9595', '9620',
                         '9643', '9729', '9821', '10127');
  IF present <> 40 OR ready <> 40 THEN
    RAISE EXCEPTION 'V1 failed: present=% ready=% of 40', present, ready;
  END IF;
END $$;

-- V1b — the kcal outliers among the 40 are exactly 2064, 2838 and 8342, the three
-- ruled eligible on 13.09 (decisions.md): high-fibre "light" products whose gap is
-- 2 × fiber_g, the fibre term of db/05_derive_kcal.sql. A fourth one appearing
-- here is a row nobody has ruled on, and it stops the run.
DO $$
DECLARE who text;
BEGIN
  SELECT string_agg(source_code, ',' ORDER BY source_code::int) INTO who
    FROM v_kcal_outliers
   WHERE source_code IN ('1919', '1923', '1932', '1940', '1955', '1980',
                         '2005', '2051', '2062', '2064', '2534', '2558',
                         '2668', '2714', '2727', '2773', '2828', '2831',
                         '2838', '2849', '3456', '3464', '3660', '3962',
                         '3963', '8199', '8342', '8354', '8468', '8552',
                         '8811', '8818', '8887', '9550', '9595', '9620',
                         '9643', '9729', '9821', '10127');
  IF who IS DISTINCT FROM '2064,2838,8342' THEN
    RAISE EXCEPTION 'V1b failed: kcal outliers among the 40 = (%), expected 2064,2838,8342', who;
  END IF;
END $$;

-- The writes: one UPDATE per allergen group, per the owner's table. Each is
-- followed by W<n>: against _pre, exactly the group's rows changed, and each of
-- them now carries the group's literal, is reviewed and eligible.
UPDATE food_curation
   SET allergens = '{Gluten}'::text[], allergens_reviewed_at = now(), menu_eligible = true
 WHERE source_code IN ('1919', '1923', '1932', '1940', '1955', '1980', '2005',
                       '2062', '2064', '2534', '2714', '2831', '2838', '8199',
                       '8342', '8354', '8552', '8811', '8887', '9550', '9595',
                       '9729', '9821', '10127');

DO $$
DECLARE n int; changed int;
BEGIN
  SELECT count(*),
         count(*) FILTER (WHERE c.menu_eligible AND c.allergens_reviewed_at IS NOT NULL
                            AND c.allergens = '{Gluten}'::text[]
                            AND (c.allergens, c.allergens_reviewed_at, c.menu_eligible)
                                IS DISTINCT FROM (p.allergens, p.allergens_reviewed_at, p.menu_eligible))
    INTO n, changed
    FROM food_curation c JOIN _pre p USING (source_code)
   WHERE c.source_code IN ('1919', '1923', '1932', '1940', '1955', '1980',
                           '2005', '2062', '2064', '2534', '2714', '2831',
                           '2838', '8199', '8342', '8354', '8552', '8811',
                           '8887', '9550', '9595', '9729', '9821', '10127');
  IF n <> 24 OR changed <> 24 THEN
    RAISE EXCEPTION 'W1 failed: {Gluten} group: in-list=% changed=% expected 24', n, changed;
  END IF;
END $$;

UPDATE food_curation
   SET allergens = '{Gluten,"Tree nuts"}'::text[], allergens_reviewed_at = now(), menu_eligible = true
 WHERE source_code IN ('2849');

DO $$
DECLARE n int; changed int;
BEGIN
  SELECT count(*),
         count(*) FILTER (WHERE c.menu_eligible AND c.allergens_reviewed_at IS NOT NULL
                            AND c.allergens = '{Gluten,"Tree nuts"}'::text[]
                            AND (c.allergens, c.allergens_reviewed_at, c.menu_eligible)
                                IS DISTINCT FROM (p.allergens, p.allergens_reviewed_at, p.menu_eligible))
    INTO n, changed
    FROM food_curation c JOIN _pre p USING (source_code)
   WHERE c.source_code IN ('2849');
  IF n <> 1 OR changed <> 1 THEN
    RAISE EXCEPTION 'W2 failed: {Gluten,Tree nuts} group: in-list=% changed=% expected 1', n, changed;
  END IF;
END $$;

-- The 15 clean rows: allergens stays '{}', and what changes is the STATE —
-- allergens_reviewed_at goes from NULL (nobody looked) to a stamp (looked, clean).
-- The two are different states and the schema keeps them apart on purpose.
UPDATE food_curation
   SET allergens = '{}'::text[], allergens_reviewed_at = now(), menu_eligible = true
 WHERE source_code IN ('2051', '2558', '2668', '2727', '2773', '2828', '3456',
                       '3464', '3660', '3962', '3963', '8468', '8818', '9620',
                       '9643');

DO $$
DECLARE n int; changed int;
BEGIN
  SELECT count(*),
         count(*) FILTER (WHERE c.menu_eligible AND c.allergens_reviewed_at IS NOT NULL
                            AND c.allergens = '{}'::text[]
                            AND (c.allergens_reviewed_at, c.menu_eligible)
                                IS DISTINCT FROM (p.allergens_reviewed_at, p.menu_eligible))
    INTO n, changed
    FROM food_curation c JOIN _pre p USING (source_code)
   WHERE c.source_code IN ('2051', '2558', '2668', '2727', '2773', '2828',
                           '3456', '3464', '3660', '3962', '3963', '8468',
                           '8818', '9620', '9643');
  IF n <> 15 OR changed <> 15 THEN
    RAISE EXCEPTION 'W3 failed: {} group: in-list=% changed=% expected 15', n, changed;
  END IF;
END $$;

-- Raw output for the record, before the assertions
SELECT c.source_code, c.category, c.allergens, c.allergens_reviewed_at IS NOT NULL AS reviewed,
       c.menu_eligible, c.max_g, c.prep, c.by_weight, c.whole_only
  FROM food_curation c
 WHERE c.source_code IN ('1919', '1923', '1932', '1940', '1955', '1980',
                        '2005', '2051', '2062', '2064', '2534', '2558',
                        '2668', '2714', '2727', '2773', '2828', '2831',
                        '2838', '2849', '3456', '3464', '3660', '3962',
                        '3963', '8199', '8342', '8354', '8468', '8552',
                        '8811', '8818', '8887', '9550', '9595', '9620',
                        '9643', '9729', '9821', '10127')
 ORDER BY c.source_code::int;

-- V2 — 349 rows, nothing added or removed; the rows that differ from _pre in any
-- column are exactly the 40, and within them only allergens,
-- allergens_reviewed_at, menu_eligible and updated_at (the trigger) moved; the
-- other 309 rows are identical in every column, updated_at included
DO $$
DECLARE tot int; added int; removed int; touched int; touched_outside int;
        other_moved int; others int; others_moved int;
BEGIN
  SELECT count(*) INTO tot FROM food_curation;
  SELECT count(*) INTO added FROM food_curation c
    LEFT JOIN _pre p USING (source_code) WHERE p.source_code IS NULL;
  SELECT count(*) INTO removed FROM _pre p
    LEFT JOIN food_curation c USING (source_code) WHERE c.source_code IS NULL;
  SELECT count(*) INTO touched
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
  SELECT count(*) INTO touched_outside
    FROM food_curation c JOIN _pre p USING (source_code)
   WHERE c.source_code NOT IN ('1919', '1923', '1932', '1940', '1955',
                                '1980', '2005', '2051', '2062', '2064',
                                '2534', '2558', '2668', '2714', '2727',
                                '2773', '2828', '2831', '2838', '2849',
                                '3456', '3464', '3660', '3962', '3963',
                                '8199', '8342', '8354', '8468', '8552',
                                '8811', '8818', '8887', '9550', '9595',
                                '9620', '9643', '9729', '9821', '10127')
     AND (c.category, c.kosher, c.allergens, c.allergens_reviewed_at, c.tags,
            c.quality, c.supp, c.prep, c.by_weight, c.whole_only, c.max_g,
            c.menu_eligible, c.curated_by, c.curated_at, c.created_at, c.updated_at,
            c.excluded_reason)
         IS DISTINCT FROM
         (p.category, p.kosher, p.allergens, p.allergens_reviewed_at, p.tags,
            p.quality, p.supp, p.prep, p.by_weight, p.whole_only, p.max_g,
            p.menu_eligible, p.curated_by, p.curated_at, p.created_at, p.updated_at,
            p.excluded_reason);
  SELECT count(*) FILTER (WHERE
           (c.category, c.kosher, c.tags, c.quality, c.supp, c.prep, c.by_weight,
            c.whole_only, c.max_g, c.curated_by, c.curated_at, c.created_at,
            c.excluded_reason)
           IS DISTINCT FROM
           (p.category, p.kosher, p.tags, p.quality, p.supp, p.prep, p.by_weight,
            p.whole_only, p.max_g, p.curated_by, p.curated_at, p.created_at,
            p.excluded_reason))
    INTO other_moved
    FROM food_curation c JOIN _pre p USING (source_code)
   WHERE c.source_code IN ('1919', '1923', '1932', '1940', '1955', '1980',
                           '2005', '2051', '2062', '2064', '2534', '2558',
                           '2668', '2714', '2727', '2773', '2828', '2831',
                           '2838', '2849', '3456', '3464', '3660', '3962',
                           '3963', '8199', '8342', '8354', '8468', '8552',
                           '8811', '8818', '8887', '9550', '9595', '9620',
                           '9643', '9729', '9821', '10127');
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
    INTO others, others_moved
    FROM _pre p JOIN food_curation c USING (source_code)
   WHERE p.source_code NOT IN ('1919', '1923', '1932', '1940', '1955',
                                '1980', '2005', '2051', '2062', '2064',
                                '2534', '2558', '2668', '2714', '2727',
                                '2773', '2828', '2831', '2838', '2849',
                                '3456', '3464', '3660', '3962', '3963',
                                '8199', '8342', '8354', '8468', '8552',
                                '8811', '8818', '8887', '9550', '9595',
                                '9620', '9643', '9729', '9821', '10127');
  IF tot <> 349 OR added <> 0 OR removed <> 0 OR touched <> 40 OR touched_outside <> 0
     OR other_moved <> 0 OR others <> 309 OR others_moved <> 0 THEN
    RAISE EXCEPTION 'V2 failed: tot=% added=% removed=% touched=% touched-outside-40=% other-columns-moved=% others=% others-moved=%',
      tot, added, removed, touched, touched_outside, other_moved, others, others_moved;
  END IF;
END $$;

-- V3 — the 40 now: eligible and reviewed; count by allergens array
DO $$
DECLARE flipped int; g_gluten int; g_gluten_nuts int; g_empty int;
BEGIN
  SELECT count(*) FILTER (WHERE menu_eligible AND allergens_reviewed_at IS NOT NULL),
         count(*) FILTER (WHERE allergens = '{Gluten}'::text[]),
         count(*) FILTER (WHERE allergens = '{Gluten,"Tree nuts"}'::text[]),
         count(*) FILTER (WHERE allergens = '{}'::text[])
    INTO flipped, g_gluten, g_gluten_nuts, g_empty
    FROM food_curation
   WHERE source_code IN ('1919', '1923', '1932', '1940', '1955', '1980',
                         '2005', '2051', '2062', '2064', '2534', '2558',
                         '2668', '2714', '2727', '2773', '2828', '2831',
                         '2838', '2849', '3456', '3464', '3660', '3962',
                         '3963', '8199', '8342', '8354', '8468', '8552',
                         '8811', '8818', '8887', '9550', '9595', '9620',
                         '9643', '9729', '9821', '10127');
  IF flipped <> 40 OR g_gluten <> 24 OR g_gluten_nuts <> 1 OR g_empty <> 15 THEN
    RAISE EXCEPTION 'V3 failed: flipped=% gluten=% gluten+nuts=% clean=%',
      flipped, g_gluten, g_gluten_nuts, g_empty;
  END IF;
END $$;

-- V4 — untouched by name: the 4 carbs curated in 3ד stay exactly as they were,
-- and the three label-condition codes of 8פ-ד have NO curation row at all. That
-- is the carbohydrate difference from the protein blocks, where 5ז tagged the 32
-- label codes as non-eligible rows: here 8פ-ד sent 2807, 8966 and 8969 to
-- db/block8_carb_label_codes.txt for block 7, and migration 20 inserted the 40
-- "yes" codes only (8פ-ה measured 0 of 43 in food_curation).
DO $$
DECLARE old4 int; old4_same int; label3 int;
BEGIN
  SELECT count(*), count(*) FILTER (WHERE
           (c.allergens, c.allergens_reviewed_at, c.menu_eligible, c.updated_at)
           IS NOT DISTINCT FROM
           (p.allergens, p.allergens_reviewed_at, p.menu_eligible, p.updated_at))
    INTO old4, old4_same
    FROM food_curation c JOIN _pre p USING (source_code)
   WHERE c.source_code IN ('2659', '2721', '3459', '8348');
  SELECT count(*) INTO label3
    FROM food_curation WHERE source_code IN ('2807', '8966', '8969');
  IF old4 <> 4 OR old4_same <> 4 OR label3 <> 0 THEN
    RAISE EXCEPTION 'V4 failed: the 4 curated carbs=% unchanged=% · label-code curation rows=% expected 0',
      old4, old4_same, label3;
  END IF;
END $$;

-- V5 — the canonical snapshot afterwards, and the safety views
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
  IF tot<>349 OR el<>190 OR p<>105 OR f<>37 OR c<>44 OR v<>4 OR vm<>190 OR mt<>0 OR orph<>0 THEN
    RAISE EXCEPTION 'V5 failed: tot=% el=% p=% f=% c=% v=% view=% missing_tags=% orphans=%',
      tot, el, p, f, c, v, vm, mt, orph;
  END IF;
END $$;

-- V6 — the depth the block exists to open: v_pool_depth carb = 44 eligible and
-- 17 allergen-free (#47 asked for 30 and 10). Every label anywhere in
-- food_curation.allergens is still one of the eight words.
DO $$
DECLARE carb_el int; carb_free int; off_vocab int; off_list text;
BEGIN
  SELECT eligible, allergen_free INTO carb_el, carb_free
    FROM v_pool_depth WHERE category = 'carb';
  SELECT count(*), string_agg(DISTINCT a, ',') INTO off_vocab, off_list
    FROM food_curation, unnest(allergens) AS a
   WHERE a NOT IN ('Egg','Fish','Gluten','Milk','Peanuts','Sesame','Soy','Tree nuts');
  IF carb_el <> 44 OR carb_free <> 17 OR off_vocab <> 0 THEN
    RAISE EXCEPTION 'V6 failed: carb eligible=% allergen-free=% off-vocabulary=% (%)',
      carb_el, carb_free, off_vocab, coalesce(off_list, '');
  END IF;
END $$;

COMMIT;
