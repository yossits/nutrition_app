-- Block 7ת-ג3 — migration 25: the labelled rows of block 7ת are reviewed for allergens from their
-- labels and become menu_eligible; the pool goes 264 → 267, protein 105 → 108.
-- Decided in docs/decisions.md: 16.09.2026 (the label record - source, tastes, name matching and the
-- composition check; label_source is the page, label_date the day it was read), 19.09.2026 (for a
-- label read from a packaging image, label_source is the image file) and 17.09.2026 (7ת has
-- two migrations, 24 the columns and 25 the flip; a labelled row is one whose label_source in
-- db/block7_label_sheet.tsv is not empty, and only those are flipped; the tag vegan comes off a row
-- whose allergens_label names Egg, Milk or Fish); docs/PROGRESS.md, row 7ת-ג3.
-- The rows and their values come from the sheet as it is in git (sha256 9d48346f…), built by a
-- script and checked by name: each row below carries the sheet's name_he, and V0 stops the run if
-- foods.name_he differs. Allergens are the sheet's allergens_label, by the identity of the ingredient
-- on the label ("contains" is tagged, "may contain" is not); fiber_g_label is empty in every row of
-- the sheet and stays NULL (decisions.md, 19.09.2026).
--   code   allergens            label
--   661    '{}'                 read 2026-09-18
--   1791   '{Egg,Gluten,Soy}'   read 2026-09-16   - loses vegan
--   10126  '{Egg,Gluten,Soy}'   read 2026-09-16   - loses vegan
-- A row without a label is not written. Not touched: the 420 other rows, among them the
-- 28 rows of the queue that went out in 7ת-ב; the other 3 that went out have no
-- curation row (2807 · 8966 · 8969).
-- Same pattern as 23_flip_veg.sql: one transaction, a _pre snapshot of every column - the 18 of 23
-- and the three of 24 - the UPDATE, assertions, COMMIT. V0 pins the state this file was written
-- against, so a second run fails before it touches anything.
-- Expected canonical snapshot afterwards: 423 · 267 · 108 · 37 · 44 · 78 · 267 · 0 · 0.

BEGIN;

CREATE TEMP TABLE _pre ON COMMIT DROP AS
  SELECT source_code, category, kosher, allergens, allergens_reviewed_at, tags,
         quality, supp, prep, by_weight, whole_only, max_g, menu_eligible,
         curated_by, curated_at, created_at, updated_at, excluded_reason,
         label_source, label_date, fiber_g_label
    FROM food_curation;

-- The labelled rows of the sheet, one per code
CREATE TEMP TABLE _labels (source_code text PRIMARY KEY, name_he text NOT NULL, allergens text[] NOT NULL,
                           label_source text NOT NULL, label_date date NOT NULL) ON COMMIT DROP;
INSERT INTO _labels (source_code, name_he, allergens, label_source, label_date) VALUES
    ('661', 'קבב בקר אמיתי, טיבון ויל',
     '{}'::text[], 'https://neto.org.il/wp-content/uploads/2025/03/7290002109488.jpg', DATE '2026-09-18'),
    ('1791', 'נקניקיות מן הצומח, טבעול',
     '{Egg,Gluten,Soy}'::text[], 'https://www.tivall.co.il/product/vegetarian-sausages', DATE '2026-09-16'),
    ('10126', 'המבורגר מן הצומח, מופחת שומן/99, טבעול',
     '{Egg,Gluten,Soy}'::text[], 'https://www.tivall.co.il/product/99-cal-vegeterian-burger', DATE '2026-09-16');

-- V0 — precondition and rerun guard: the snapshot this file expects; the 3 rows exist, carry the
-- sheet's name in foods, and are protein, not eligible, unreviewed, allergens '{}', label columns
-- NULL, with the fields the CHECK constraints read in place
DO $$
DECLARE tot int; el int; p int; f int; c int; v int; vm int; mt int; orph int;
        labels int; present int; named int; ready int;
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
  SELECT count(*) INTO labels FROM _labels;
  SELECT count(*),
         count(*) FILTER (WHERE fd.name_he = l.name_he),
         count(*) FILTER (WHERE cu.category = 'protein' AND cu.menu_eligible = false
                            AND cu.allergens_reviewed_at IS NULL AND cu.allergens = '{}'::text[]
                            AND cu.label_source IS NULL AND cu.label_date IS NULL
                            AND cu.fiber_g_label IS NULL AND cu.excluded_reason IS NULL
                            AND cu.kosher IS NOT NULL AND cu.quality IS NOT NULL
                            AND cu.prep IS NOT NULL AND cu.by_weight IS NOT NULL)
    INTO present, named, ready
    FROM _labels l
    JOIN food_curation cu ON cu.source_code = l.source_code
    JOIN foods fd ON fd.source_code = l.source_code;
  IF tot<>423 OR el<>264 OR p<>105 OR f<>37 OR c<>44 OR v<>78 OR vm<>264 OR mt<>0 OR orph<>0
     OR labels <> 3 OR present <> 3 OR named <> 3 OR ready <> 3 THEN
    RAISE EXCEPTION 'V0 failed: tot=% el=% p=% f=% c=% v=% view=% missing_tags=% orphans=% · labels=% present=% named=% ready=%',
      tot, el, p, f, c, v, vm, mt, orph, labels, present, named, ready;
  END IF;
END $$;

-- The write. allergens_reviewed_at is now(), as 17, 19, 21 and 23 set it. fiber_g_label is not
-- written. The tag vegan comes off only where the label names Egg, Milk or Fish.
UPDATE food_curation c
   SET allergens             = l.allergens,
       allergens_reviewed_at = now(),
       label_source          = l.label_source,
       label_date            = l.label_date,
       tags                  = CASE WHEN l.allergens && '{Egg,Milk,Fish}'::text[]
                                    THEN array_remove(c.tags, 'vegan') ELSE c.tags END,
       menu_eligible         = true
  FROM _labels l
 WHERE c.source_code = l.source_code;

-- Raw output for the record, before the assertions
SELECT c.source_code, c.category, p.tags AS tags_before, c.tags AS tags_after, c.allergens,
       c.allergens_reviewed_at IS NOT NULL AS reviewed, c.menu_eligible,
       c.label_source, c.label_date, c.fiber_g_label
  FROM food_curation c JOIN _pre p USING (source_code)
 WHERE c.source_code IN ('661', '1791', '10126')
 ORDER BY c.source_code::int;

SELECT (SELECT count(*) FROM v_recipe_unreviewed_components) AS unreviewed_components,
       (SELECT count(*) FROM v_recipe_inherited_allergens) AS inherited_allergens,
       (SELECT count(*) FROM food_curation WHERE menu_eligible AND 'vegan' = ANY(tags)) AS eligible_vegan;

-- V1 — exactly 3 rows differ from _pre in any of the 21 columns, and the set that differs is the
-- 3 codes; nothing added, nothing removed
DO $$
DECLARE touched int; who text; tot int; added int; removed int;
BEGIN
  SELECT count(*), string_agg(c.source_code, ',' ORDER BY c.source_code::int)
    INTO touched, who
    FROM food_curation c JOIN _pre p USING (source_code)
   WHERE (c.category, c.kosher, c.allergens, c.allergens_reviewed_at, c.tags,
          c.quality, c.supp, c.prep, c.by_weight, c.whole_only, c.max_g,
          c.menu_eligible, c.curated_by, c.curated_at, c.created_at, c.updated_at,
          c.excluded_reason, c.label_source, c.label_date, c.fiber_g_label)
         IS DISTINCT FROM
         (p.category, p.kosher, p.allergens, p.allergens_reviewed_at, p.tags,
          p.quality, p.supp, p.prep, p.by_weight, p.whole_only, p.max_g,
          p.menu_eligible, p.curated_by, p.curated_at, p.created_at, p.updated_at,
          p.excluded_reason, p.label_source, p.label_date, p.fiber_g_label);
  SELECT count(*) INTO tot FROM food_curation;
  SELECT count(*) INTO added FROM food_curation c
    LEFT JOIN _pre p USING (source_code) WHERE p.source_code IS NULL;
  SELECT count(*) INTO removed FROM _pre p
    LEFT JOIN food_curation c USING (source_code) WHERE c.source_code IS NULL;
  IF touched <> 3 OR tot <> 423 OR added <> 0 OR removed <> 0
     OR who IS DISTINCT FROM '661,1791,10126' THEN
    RAISE EXCEPTION 'V1 failed: touched=% tot=% added=% removed=% set=%', touched, tot, added, removed, who;
  END IF;
END $$;

-- V2 — the 3 now: eligible, reviewed, fiber_g_label NULL, and allergens and the two label
-- columns equal to _labels row by row. _labels is this file's copy of the sheet: V2 proves the
-- UPDATE wrote it, not that it matches the sheet - that check runs outside the file, in the script
-- that built _labels and in a read-back of the rows against the sheet after the apply
DO $$
DECLARE n int; ok int;
BEGIN
  SELECT count(*),
         count(*) FILTER (WHERE c.menu_eligible AND c.allergens = l.allergens
                            AND c.allergens_reviewed_at IS NOT NULL
                            AND c.label_source = l.label_source AND c.label_date = l.label_date
                            AND c.fiber_g_label IS NULL)
    INTO n, ok
    FROM food_curation c JOIN _labels l USING (source_code);
  IF n <> 3 OR ok <> 3 THEN
    RAISE EXCEPTION 'V2 failed: n=% as-_labels=%', n, ok;
  END IF;
END $$;

-- V3 — on the 3, every field the flip does not write is unchanged; tags equal _pre except that
-- vegan is gone where the label names Egg, Milk or Fish, and the rows whose tags changed are exactly
-- 1791,10126; the CHECK label_source_and_date_together holds on every row
DO $$
DECLARE n int; moved int; tags_off int; tag_changed int; tag_who text; pair_broken int;
BEGIN
  SELECT count(*),
         count(*) FILTER (WHERE
           (c.category, c.kosher, c.quality, c.supp, c.prep, c.by_weight, c.whole_only, c.max_g,
            c.curated_by, c.curated_at, c.created_at, c.excluded_reason, c.fiber_g_label)
           IS DISTINCT FROM
           (p.category, p.kosher, p.quality, p.supp, p.prep, p.by_weight, p.whole_only, p.max_g,
            p.curated_by, p.curated_at, p.created_at, p.excluded_reason, p.fiber_g_label)),
         count(*) FILTER (WHERE c.tags IS DISTINCT FROM
                            CASE WHEN l.allergens && '{Egg,Milk,Fish}'::text[]
                                 THEN array_remove(p.tags, 'vegan') ELSE p.tags END),
         count(*) FILTER (WHERE c.tags IS DISTINCT FROM p.tags),
         string_agg(c.source_code, ',' ORDER BY c.source_code::int)
           FILTER (WHERE c.tags IS DISTINCT FROM p.tags)
    INTO n, moved, tags_off, tag_changed, tag_who
    FROM food_curation c JOIN _pre p USING (source_code) JOIN _labels l USING (source_code);
  SELECT count(*) INTO pair_broken FROM food_curation
   WHERE (label_source IS NULL) <> (label_date IS NULL);
  IF n <> 3 OR moved <> 0 OR tags_off <> 0 OR tag_changed <> 2
     OR tag_who IS DISTINCT FROM '1791,10126' OR pair_broken <> 0 THEN
    RAISE EXCEPTION 'V3 failed: n=% untouched-fields-moved=% tags-off-rule=% tags-changed=% (%) label-pair-broken=%',
      n, moved, tags_off, tag_changed, tag_who, pair_broken;
  END IF;
END $$;

-- V4 — the 420 rows outside the 3 are identical in all 21 columns, updated_at included,
-- and 264 of them are still eligible
DO $$
DECLARE others int; others_moved int; others_el int;
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
            p.excluded_reason, p.label_source, p.label_date, p.fiber_g_label)),
         count(*) FILTER (WHERE c.menu_eligible)
    INTO others, others_moved, others_el
    FROM _pre p JOIN food_curation c USING (source_code)
   WHERE p.source_code NOT IN ('661', '1791', '10126');
  IF others <> 420 OR others_moved <> 0 OR others_el <> 264 THEN
    RAISE EXCEPTION 'V4 failed: others=% moved=% eligible-among-them=%', others, others_moved, others_el;
  END IF;
END $$;

-- V5 — the canonical snapshot afterwards, the safety views, the vocabulary, and over the whole
-- table: no eligible row tagged vegan carries Egg, Milk or Fish (decisions.md, 17.09.2026); the
-- eligible vegan rows stay 176, since the two that lose the tag were not eligible before
DO $$
DECLARE tot int; el int; p int; f int; c int; v int; vm int; mt int; orph int; off_vocab int;
        vegan_bad int; vegan_el int;
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
  SELECT count(*) INTO off_vocab FROM food_curation, unnest(allergens) AS a
   WHERE a NOT IN ('Egg','Fish','Gluten','Milk','Peanuts','Sesame','Soy','Tree nuts');
  SELECT count(*) FILTER (WHERE allergens && '{Egg,Milk,Fish}'::text[]), count(*)
    INTO vegan_bad, vegan_el
    FROM food_curation WHERE menu_eligible AND 'vegan' = ANY(tags);
  IF tot<>423 OR el<>267 OR p<>108 OR f<>37 OR c<>44 OR v<>78
     OR vm<>267 OR mt<>0 OR orph<>0 OR off_vocab<>0 OR vegan_bad<>0 OR vegan_el<>176 THEN
    RAISE EXCEPTION 'V5 failed: tot=% el=% p=% f=% c=% v=% view=% missing_tags=% orphans=% off-vocabulary=% eligible-vegan-with-Egg/Milk/Fish=% eligible-vegan=%',
      tot, el, p, f, c, v, vm, mt, orph, off_vocab, vegan_bad, vegan_el;
  END IF;
END $$;

-- V6 — the recipe views, as measured before this file was written (7ת-ג3, S0): none of the 3 is a
-- recipe or a recipe component, so both stay where they are - 31 and 487
DO $$
DECLARE unrev int; inh int;
BEGIN
  SELECT count(*) INTO unrev FROM v_recipe_unreviewed_components;
  SELECT count(*) INTO inh   FROM v_recipe_inherited_allergens;
  IF unrev <> 31 OR inh <> 487 THEN
    RAISE EXCEPTION 'V6 failed: v_recipe_unreviewed_components=% v_recipe_inherited_allergens=%', unrev, inh;
  END IF;
END $$;

COMMIT;
