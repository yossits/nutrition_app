-- Block 8ש-ז - migration 27: the six olives of the reopened family are reviewed for allergens
-- and become menu_eligible; the pool goes 267 -> 273 and fat goes 37 -> 43.
-- Decided in docs/decisions.md, 20.09.2026: 8ש-ב reopened the olive family on six codes,
-- 8ש-ד set one family default in grams with no exceptions, and 8ש-ה decided allergens '{}'
-- for all six - 4284 "זיתים ירוקים, ממולאים" included, by the generic filling and not by a
-- brand label. The review itself is the owner's, made in chat on 20.09.2026.
-- See docs/PROGRESS.md, row 8ש-ז, and docs/work/2026-09-20-block-8-fat.md.
--
-- The list is db/block8_fat_codes.txt (8ש-ג, sha256 61577710…). The names below are the ones
-- 26_tag_fat.sql carried in its own temp table; V0 stops the run if foods.name_he differs.
--
-- What this file writes, on the six rows only:
--   allergens             = '{}'    - the value they already carry, written because this is the
--                                     statement that records the decision. It does not move: the
--                                     five 26 inserted took the column default, and 4279 has held
--                                     '{}' since 3ד. V2 therefore does not list it either way.
--   allergens_reviewed_at = now()   - on all six, 4279 included. Its 30.08.2026 stamp is
--                                     overwritten on purpose: 8ש-ה reviewed the whole family
--                                     today, and the column records the review that applies, not
--                                     the oldest one. This is the one value 26 deliberately left
--                                     alone that 27 rewrites; 26's header says so.
--   menu_eligible         = true
-- Nothing else. curated_by and curated_at stay as 3ד wrote them and as 25 and 26 left them;
-- updated_at moves by itself, through the trigger food_curation_touch_updated_at.
--
-- The CHECK constraints this satisfies (db/01_food_db_schema.sql):
--   eligible_requires_safety_tagging - category, kosher and allergens_reviewed_at are all set
--   eligible_requires_menu_fields    - prep 0 and by_weight true are already on the rows
--   eligible_protein_requires_quality does not apply: the six are fat, and quality is NULL
--
-- Same pattern as 25_flip_labels.sql: one transaction, a _pre snapshot of every column - the 18
-- of 23 and the three of 24 - the UPDATE, assertions, COMMIT. V0 pins the state this file was
-- written against, so a second run fails before it touches anything.
-- The table-wide checks 25 carried are here too, decided at 8ש-ז S0: V4 is 25's V5 - the
-- snapshot, the safety views, the allergen vocabulary, and no eligible vegan row carrying Egg,
-- Milk or Fish - and V5 is 25's V6, the two recipe views. They run inside the transaction, so a
-- violation rolls the flip back instead of being found after an irreversible write. The same
-- numbers are read again outside the file, read-only, after the apply.
-- Expected canonical snapshot afterwards: 428 · 273 · 108 · 43 · 44 · 78 · 273 · 0 · 0.

BEGIN;

CREATE TEMP TABLE _pre ON COMMIT DROP AS
  SELECT source_code, category, kosher, allergens, allergens_reviewed_at, tags,
         quality, supp, prep, by_weight, whole_only, max_g, menu_eligible,
         curated_by, curated_at, created_at, updated_at, excluded_reason,
         label_source, label_date, fiber_g_label
    FROM food_curation;

-- The six codes of db/block8_fat_codes.txt, with the name each one carries in foods
CREATE TEMP TABLE _six (source_code text PRIMARY KEY, name_he text NOT NULL) ON COMMIT DROP;
INSERT INTO _six (source_code, name_he) VALUES
    ('4278', 'זיתים, לפנ'),
    ('4279', 'זיתים ירוקים'),
    ('4283', 'זיתים שחורים, בני דרום, בית השיטה'),
    ('4284', 'זיתים ירוקים, ממולאים'),
    ('4285', 'זיתים ללא גלעינים, קיבוץ יבנה, בית השיטה, אסם'),
    ('4288', 'זיתים מושחרים, קיבוץ יבנה, בית השיטה');

-- V0 - precondition and rerun guard: the snapshot this file expects; the six exist, carry the
-- name foods gives them, and stand in the state 26 left them in - fat, parve, {vegan}, not
-- eligible, allergens '{}', by_weight true, whole_only false, max_g 60, prep 0, quality NULL,
-- supp false, no excluded_reason, no label columns; five unreviewed and 4279 reviewed
DO $$
DECLARE tot int; el int; p int; f int; c int; v int; vm int; mt int; orph int;
        six int; present int; named int; ready int; unrev int; rev int;
BEGIN
  SELECT count(*), count(*) FILTER (WHERE menu_eligible),
         count(*) FILTER (WHERE menu_eligible AND category = 'protein'),
         count(*) FILTER (WHERE menu_eligible AND category = 'fat'),
         count(*) FILTER (WHERE menu_eligible AND category = 'carb'),
         count(*) FILTER (WHERE menu_eligible AND category = 'veg')
    INTO tot, el, p, f, c, v FROM food_curation;
  SELECT count(*) INTO vm   FROM v_menu_foods;
  SELECT count(*) INTO mt   FROM v_eligible_missing_tags;
  SELECT count(*) INTO orph FROM v_curation_orphans;
  SELECT count(*) INTO six  FROM _six;
  SELECT count(*),
         count(*) FILTER (WHERE fd.name_he = s.name_he),
         count(*) FILTER (WHERE cu.category = 'fat' AND cu.menu_eligible = false
                            AND cu.allergens = '{}'::text[] AND cu.kosher = 'parve'
                            AND cu.tags = '{vegan}'::text[]
                            AND cu.by_weight = true AND cu.whole_only = false
                            AND cu.max_g = 60 AND cu.prep = 0
                            AND cu.quality IS NULL AND cu.supp = false
                            AND cu.excluded_reason IS NULL
                            AND cu.label_source IS NULL AND cu.label_date IS NULL
                            AND cu.fiber_g_label IS NULL),
         count(*) FILTER (WHERE cu.allergens_reviewed_at IS NULL),
         count(*) FILTER (WHERE cu.allergens_reviewed_at IS NOT NULL AND cu.source_code = '4279')
    INTO present, named, ready, unrev, rev
    FROM _six s
    JOIN food_curation cu ON cu.source_code = s.source_code
    JOIN foods fd ON fd.source_code = s.source_code;
  IF tot<>428 OR el<>267 OR p<>108 OR f<>37 OR c<>44 OR v<>78 OR vm<>267 OR mt<>0 OR orph<>0
     OR six<>6 OR present<>6 OR named<>6 OR ready<>6 OR unrev<>5 OR rev<>1 THEN
    RAISE EXCEPTION 'V0 failed: tot=% el=% p=% f=% c=% v=% view=% missing_tags=% orphans=% · six=% present=% named=% ready=% unreviewed=% reviewed4279=%',
      tot, el, p, f, c, v, vm, mt, orph, six, present, named, ready, unrev, rev;
  END IF;
END $$;

-- The write. allergens_reviewed_at is now(), as 17, 19, 21, 23 and 25 set it - one transaction,
-- so the six carry the same stamp. allergens is written at its present value, '{}'.
UPDATE food_curation c
   SET allergens             = '{}'::text[],
       allergens_reviewed_at = now(),
       menu_eligible         = true
  FROM _six s
 WHERE c.source_code = s.source_code;

-- Raw output for the record, before the assertions
SELECT c.source_code, f.name_he, c.category, c.kosher, c.tags, c.allergens,
       c.allergens_reviewed_at, c.menu_eligible, c.by_weight, c.whole_only, c.max_g, c.prep,
       c.curated_by, c.curated_at, p.updated_at AS updated_before, c.updated_at AS updated_after
  FROM food_curation c JOIN _pre p USING (source_code)
  JOIN foods f ON f.source_code = c.source_code
 WHERE c.source_code IN ('4278', '4279', '4283', '4284', '4285', '4288')
 ORDER BY c.source_code::int;

SELECT (SELECT count(*) FROM v_recipe_unreviewed_components) AS unreviewed_components,
       (SELECT count(*) FROM v_recipe_inherited_allergens) AS inherited_allergens,
       (SELECT count(*) FROM food_curation WHERE menu_eligible AND 'vegan' = ANY(tags)) AS eligible_vegan;

-- V1 - the six now: eligible, allergens '{}', reviewed, and the six stamps are one value,
-- because one transaction wrote them
DO $$
DECLARE n int; ok int; stamps int;
BEGIN
  SELECT count(*),
         count(*) FILTER (WHERE c.menu_eligible
                            AND c.allergens = '{}'::text[]
                            AND c.allergens_reviewed_at IS NOT NULL)
    INTO n, ok
    FROM food_curation c JOIN _six s USING (source_code);
  SELECT count(DISTINCT c.allergens_reviewed_at) INTO stamps
    FROM food_curation c JOIN _six s USING (source_code);
  IF n <> 6 OR ok <> 6 OR stamps <> 1 THEN
    RAISE EXCEPTION 'V1 failed: n=% eligible-reviewed-clean=% distinct-stamps=%', n, ok, stamps;
  END IF;
END $$;

-- V2 - on the six: every field the flip does not write is unchanged against _pre, and the two
-- fields it does write moved on all six. updated_at moved too, through the trigger
DO $$
DECLARE n int; moved int; el_changed int; rev_changed int; touched int;
BEGIN
  SELECT count(*),
         count(*) FILTER (WHERE
           (c.category, c.kosher, c.tags, c.quality, c.supp, c.prep, c.by_weight,
            c.whole_only, c.max_g, c.curated_by, c.curated_at, c.created_at,
            c.excluded_reason, c.label_source, c.label_date, c.fiber_g_label)
           IS DISTINCT FROM
           (p.category, p.kosher, p.tags, p.quality, p.supp, p.prep, p.by_weight,
            p.whole_only, p.max_g, p.curated_by, p.curated_at, p.created_at,
            p.excluded_reason, p.label_source, p.label_date, p.fiber_g_label)),
         count(*) FILTER (WHERE p.menu_eligible = false AND c.menu_eligible = true),
         count(*) FILTER (WHERE c.allergens_reviewed_at IS DISTINCT FROM p.allergens_reviewed_at),
         count(*) FILTER (WHERE c.updated_at > p.updated_at)
    INTO n, moved, el_changed, rev_changed, touched
    FROM food_curation c JOIN _pre p USING (source_code) JOIN _six s USING (source_code);
  IF n <> 6 OR moved <> 0 OR el_changed <> 6 OR rev_changed <> 6 OR touched <> 6 THEN
    RAISE EXCEPTION 'V2 failed: n=% untouched-fields-moved=% eligible-changed=% reviewed-changed=% updated_at-moved=%',
      n, moved, el_changed, rev_changed, touched;
  END IF;
END $$;

-- V3 - the 422 rows outside the six are identical in all 21 columns, updated_at included,
-- and nothing was added or removed
DO $$
DECLARE others int; others_moved int; tot int; added int; removed int;
BEGIN
  SELECT count(*), count(*) FILTER (WHERE
           (c.category, c.kosher, c.allergens, c.allergens_reviewed_at, c.tags,
            c.quality, c.supp, c.prep, c.by_weight, c.whole_only, c.max_g,
            c.menu_eligible, c.curated_by, c.curated_at, c.created_at, c.updated_at,
            c.excluded_reason, c.label_source, c.label_date, c.fiber_g_label)
           IS DISTINCT FROM
           (p.category, p.kosher, p.allergens, p.allergens_reviewed_at, p.tags,
            p.quality, p.supp, p.prep, p.by_weight, p.whole_only, p.max_g,
            p.menu_eligible, p.curated_by, p.curated_at, p.created_at, p.updated_at,
            p.excluded_reason, p.label_source, p.label_date, p.fiber_g_label))
    INTO others, others_moved
    FROM _pre p JOIN food_curation c USING (source_code)
   WHERE p.source_code NOT IN ('4278', '4279', '4283', '4284', '4285', '4288');
  SELECT count(*) INTO tot FROM food_curation;
  SELECT count(*) INTO added FROM food_curation c
    WHERE NOT EXISTS (SELECT 1 FROM _pre p WHERE p.source_code = c.source_code);
  SELECT count(*) INTO removed FROM _pre p
    WHERE NOT EXISTS (SELECT 1 FROM food_curation c WHERE c.source_code = p.source_code);
  IF others <> 422 OR others_moved <> 0 OR tot <> 428 OR added <> 0 OR removed <> 0 THEN
    RAISE EXCEPTION 'V3 failed: others=% moved=% tot=% added=% removed=%',
      others, others_moved, tot, added, removed;
  END IF;
END $$;

-- V4 - the canonical snapshot afterwards, the safety views, the allergen vocabulary, and over
-- the whole table: no eligible row tagged vegan carries Egg, Milk or Fish (decisions.md,
-- 17.09.2026). This is 25's V5, the block the snapshot check corresponds to. The six are vegan
-- and their allergens are '{}', so the eligible vegan rows go 176 -> 182; 176 was measured
-- read-only at 8ש-ז S0, through query(), before this file was written
DO $$
DECLARE tot int; el int; p int; f int; c int; v int; vm int; mt int; orph int; off_vocab int;
        vegan_bad int; vegan_el int;
BEGIN
  SELECT count(*), count(*) FILTER (WHERE menu_eligible),
         count(*) FILTER (WHERE menu_eligible AND category = 'protein'),
         count(*) FILTER (WHERE menu_eligible AND category = 'fat'),
         count(*) FILTER (WHERE menu_eligible AND category = 'carb'),
         count(*) FILTER (WHERE menu_eligible AND category = 'veg')
    INTO tot, el, p, f, c, v FROM food_curation;
  SELECT count(*) INTO vm   FROM v_menu_foods;
  SELECT count(*) INTO mt   FROM v_eligible_missing_tags;
  SELECT count(*) INTO orph FROM v_curation_orphans;
  SELECT count(*) INTO off_vocab FROM food_curation, unnest(allergens) AS a
   WHERE a NOT IN ('Egg','Fish','Gluten','Milk','Peanuts','Sesame','Soy','Tree nuts');
  SELECT count(*) FILTER (WHERE allergens && '{Egg,Milk,Fish}'::text[]), count(*)
    INTO vegan_bad, vegan_el
    FROM food_curation WHERE menu_eligible AND 'vegan' = ANY(tags);
  IF tot<>428 OR el<>273 OR p<>108 OR f<>43 OR c<>44 OR v<>78 OR vm<>273 OR mt<>0 OR orph<>0
     OR off_vocab<>0 OR vegan_bad<>0 OR vegan_el<>182 THEN
    RAISE EXCEPTION 'V4 failed: tot=% el=% p=% f=% c=% v=% view=% missing_tags=% orphans=% off-vocabulary=% eligible-vegan-with-Egg/Milk/Fish=% eligible-vegan=%',
      tot, el, p, f, c, v, vm, mt, orph, off_vocab, vegan_bad, vegan_el;
  END IF;
END $$;

-- V5 - the recipe views, as measured read-only at 8ש-ז S0, before this file was written: none
-- of the six is a recipe or a recipe component, so both stay where they are - 31 and 487.
-- This is 25's V6
DO $$
DECLARE unrev int; inh int;
BEGIN
  SELECT count(*) INTO unrev FROM v_recipe_unreviewed_components;
  SELECT count(*) INTO inh   FROM v_recipe_inherited_allergens;
  IF unrev <> 31 OR inh <> 487 THEN
    RAISE EXCEPTION 'V5 failed: v_recipe_unreviewed_components=% v_recipe_inherited_allergens=%', unrev, inh;
  END IF;
END $$;

COMMIT;
