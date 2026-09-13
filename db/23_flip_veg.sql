-- Block 8י-י — vegetable allergens: the 74 tagged veg rows of migration 22 are reviewed
-- for allergens and become menu_eligible; the pool goes 190 → 264, veg 4 → 78.
-- The list is db/block8_veg_codes.txt (8י-ה, less 3794 and 3766 in 8י-ח).
-- There is nothing to tag. No vegetable in the list carries an allergen of the eight
-- (Egg · Fish · Gluten · Milk · Peanuts · Sesame · Soy · Tree nuts) by the identity of
-- the ingredient, the rule of 11.09 — so allergens stays '{}' on all 74 and what changes
-- is the STATE: allergens_reviewed_at goes from NULL (nobody looked) to a stamp (looked,
-- clean). The schema keeps the two apart on purpose (spec §5).
-- The recipes among the 74, by their component lists (decisions.md 12.09), measured in
-- this sub-block before the write: 4040 roasted peppers = green pepper · 4086 steamed
-- vegetables = white cabbage, onion, green pepper, celery, tomato paste, salt · 9694 baked
-- zucchini = zucchini, salt. No component names an allergen of the eight.
-- No label-condition rows exist for veg: every one of the 80 was tagged by identity and
-- nothing went to block 7, so there is no assertion about them here (the V4 of 21 that
-- stopped 8פ-ט).
-- Not touched: the 349 rows outside the 74, including the four veg already eligible,
-- 3663 3793 3807 3837.
-- Same pattern as 21_flip_carb.sql: one transaction, a _pre snapshot of every column,
-- the UPDATE, assertions, COMMIT. V0 pins the snapshot this file was written against,
-- so a second run fails before it touches anything.
-- Expected canonical snapshot afterwards: 423 · 264 · 105 · 37 · 44 · 78 · 264 · 0 · 0.

BEGIN;

CREATE TEMP TABLE _pre ON COMMIT DROP AS
  SELECT source_code, category, kosher, allergens, allergens_reviewed_at, tags,
         quality, supp, prep, by_weight, whole_only, max_g, menu_eligible,
         curated_by, curated_at, created_at, updated_at, excluded_reason
    FROM food_curation;

CREATE TEMP TABLE _unrev_pre ON COMMIT DROP AS
  SELECT recipe_id, component_id FROM v_recipe_unreviewed_components;

-- V0 — precondition: the snapshot this file expects, and all 74 present as veg, not
-- eligible, unreviewed, with the fields the CHECK constraints read in place
DO $$
DECLARE tot int; el int; p int; f int; c int; v int; vm int; mt int; orph int;
        present int; ready int;
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
  SELECT count(*),
         count(*) FILTER (WHERE category = 'veg' AND menu_eligible = false
                            AND allergens_reviewed_at IS NULL
                            AND allergens = '{}'::text[]
                            AND kosher IS NOT NULL
                            AND prep IS NOT NULL AND by_weight IS NOT NULL)
    INTO present, ready
    FROM food_curation
   WHERE source_code IN ('3566', '3570', '3588', '3590', '3594', '3595', '3612', '3617',
                         '3626', '3638', '3647', '3665', '3667', '3672', '3673', '3735',
                         '3748', '3752', '3754', '3756', '3762', '3767', '3772', '3774',
                         '3776', '3778', '3801', '3804', '3812', '3819', '3833', '3839',
                         '3843', '3847', '3849', '3852', '3901', '3912', '3920', '3924',
                         '3929', '3930', '3932', '3933', '3948', '3949', '3954', '3956',
                         '3981', '3985', '3988', '4023', '4024', '4032', '4040', '4063',
                         '4067', '4068', '4077', '4082', '4086', '4091', '4092', '4096',
                         '4124', '4148', '4159', '8219', '8240', '8292', '8308', '8567',
                         '8838', '9694');
  IF tot<>423 OR el<>190 OR p<>105 OR f<>37 OR c<>44 OR v<>4 OR vm<>190 OR mt<>0 OR orph<>0
     OR present <> 74 OR ready <> 74 THEN
    RAISE EXCEPTION 'V0 failed: tot=% el=% p=% f=% c=% v=% view=% missing_tags=% orphans=% · of the 74 present=% ready=%',
      tot, el, p, f, c, v, vm, mt, orph, present, ready;
  END IF;
END $$;

-- The write. allergens is set to '{}' explicitly, as 21 does for its clean group, so the
-- statement says what the state is rather than leaning on the column default.
UPDATE food_curation
   SET allergens = '{}'::text[], allergens_reviewed_at = now(), menu_eligible = true
 WHERE source_code IN ('3566', '3570', '3588', '3590', '3594', '3595', '3612', '3617',
                      '3626', '3638', '3647', '3665', '3667', '3672', '3673', '3735',
                      '3748', '3752', '3754', '3756', '3762', '3767', '3772', '3774',
                      '3776', '3778', '3801', '3804', '3812', '3819', '3833', '3839',
                      '3843', '3847', '3849', '3852', '3901', '3912', '3920', '3924',
                      '3929', '3930', '3932', '3933', '3948', '3949', '3954', '3956',
                      '3981', '3985', '3988', '4023', '4024', '4032', '4040', '4063',
                      '4067', '4068', '4077', '4082', '4086', '4091', '4092', '4096',
                      '4124', '4148', '4159', '8219', '8240', '8292', '8308', '8567',
                      '8838', '9694');

-- Raw output for the record, before the assertions
SELECT c.source_code, c.category, c.allergens, c.allergens_reviewed_at IS NOT NULL AS reviewed,
       c.menu_eligible, c.max_g, c.prep, c.by_weight, c.whole_only
  FROM food_curation c
 WHERE c.source_code IN ('3566', '3570', '3588', '3590', '3594', '3595', '3612', '3617',
                       '3626', '3638', '3647', '3665', '3667', '3672', '3673', '3735',
                       '3748', '3752', '3754', '3756', '3762', '3767', '3772', '3774',
                       '3776', '3778', '3801', '3804', '3812', '3819', '3833', '3839',
                       '3843', '3847', '3849', '3852', '3901', '3912', '3920', '3924',
                       '3929', '3930', '3932', '3933', '3948', '3949', '3954', '3956',
                       '3981', '3985', '3988', '4023', '4024', '4032', '4040', '4063',
                       '4067', '4068', '4077', '4082', '4086', '4091', '4092', '4096',
                       '4124', '4148', '4159', '8219', '8240', '8292', '8308', '8567',
                       '8838', '9694')
 ORDER BY c.source_code::int;

SELECT (SELECT count(*) FROM _unrev_pre) AS unreviewed_components_before,
       (SELECT count(*) FROM v_recipe_unreviewed_components) AS unreviewed_components_after,
       (SELECT string_agg(DISTINCT r.source_code, ' ')
          FROM v_recipe_unreviewed_components u JOIN foods r ON r.id = u.recipe_id) AS recipes_after;

-- V1 — exactly 74 rows differ from _pre, and the set that differs is the codes file
DO $$
DECLARE touched int; who text; tot int; added int; removed int;
BEGIN
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
  SELECT count(*) INTO tot FROM food_curation;
  SELECT count(*) INTO added FROM food_curation c
    LEFT JOIN _pre p USING (source_code) WHERE p.source_code IS NULL;
  SELECT count(*) INTO removed FROM _pre p
    LEFT JOIN food_curation c USING (source_code) WHERE c.source_code IS NULL;
  IF touched <> 74 OR tot <> 423 OR added <> 0 OR removed <> 0 OR who IS DISTINCT FROM
     '3566,3570,3588,3590,3594,3595,3612,3617,3626,3638,3647,3665,3667,3672,3673,3735,3748,3752,3754,3756,3762,3767,3772,3774,3776,3778,3801,3804,3812,3819,3833,3839,3843,3847,3849,3852,3901,3912,3920,3924,3929,3930,3932,3933,3948,3949,3954,3956,3981,3985,3988,4023,4024,4032,4040,4063,4067,4068,4077,4082,4086,4091,4092,4096,4124,4148,4159,8219,8240,8292,8308,8567,8838,9694' THEN
    RAISE EXCEPTION 'V1 failed: touched=% tot=% added=% removed=% set=%', touched, tot, added, removed, who;
  END IF;
END $$;

-- V2 — the 74 now: eligible, allergens '{}', reviewed
DO $$
DECLARE n int; ok int;
BEGIN
  SELECT count(*),
         count(*) FILTER (WHERE menu_eligible AND allergens = '{}'::text[]
                            AND allergens_reviewed_at IS NOT NULL)
    INTO n, ok
    FROM food_curation
   WHERE source_code IN ('3566', '3570', '3588', '3590', '3594', '3595', '3612', '3617',
                         '3626', '3638', '3647', '3665', '3667', '3672', '3673', '3735',
                         '3748', '3752', '3754', '3756', '3762', '3767', '3772', '3774',
                         '3776', '3778', '3801', '3804', '3812', '3819', '3833', '3839',
                         '3843', '3847', '3849', '3852', '3901', '3912', '3920', '3924',
                         '3929', '3930', '3932', '3933', '3948', '3949', '3954', '3956',
                         '3981', '3985', '3988', '4023', '4024', '4032', '4040', '4063',
                         '4067', '4068', '4077', '4082', '4086', '4091', '4092', '4096',
                         '4124', '4148', '4159', '8219', '8240', '8292', '8308', '8567',
                         '8838', '9694');
  IF n <> 74 OR ok <> 74 THEN
    RAISE EXCEPTION 'V2 failed: n=% eligible-clean-reviewed=%', n, ok;
  END IF;
END $$;

-- V3 — the tagging fields of the 74 are untouched, field by field against _pre;
-- only allergens_reviewed_at, menu_eligible and updated_at (the trigger) moved
DO $$
DECLARE n int; moved int;
BEGIN
  SELECT count(*), count(*) FILTER (WHERE
           (c.prep, c.by_weight, c.whole_only, c.max_g, c.kosher, c.tags, c.quality, c.supp,
            c.category, c.allergens, c.curated_by, c.curated_at, c.created_at, c.excluded_reason)
           IS DISTINCT FROM
           (p.prep, p.by_weight, p.whole_only, p.max_g, p.kosher, p.tags, p.quality, p.supp,
            p.category, p.allergens, p.curated_by, p.curated_at, p.created_at, p.excluded_reason))
    INTO n, moved
    FROM food_curation c JOIN _pre p USING (source_code)
   WHERE c.source_code IN ('3566', '3570', '3588', '3590', '3594', '3595', '3612', '3617',
                         '3626', '3638', '3647', '3665', '3667', '3672', '3673', '3735',
                         '3748', '3752', '3754', '3756', '3762', '3767', '3772', '3774',
                         '3776', '3778', '3801', '3804', '3812', '3819', '3833', '3839',
                         '3843', '3847', '3849', '3852', '3901', '3912', '3920', '3924',
                         '3929', '3930', '3932', '3933', '3948', '3949', '3954', '3956',
                         '3981', '3985', '3988', '4023', '4024', '4032', '4040', '4063',
                         '4067', '4068', '4077', '4082', '4086', '4091', '4092', '4096',
                         '4124', '4148', '4159', '8219', '8240', '8292', '8308', '8567',
                         '8838', '9694');
  IF n <> 74 OR moved <> 0 THEN
    RAISE EXCEPTION 'V3 failed: n=% tagging-fields-moved=%', n, moved;
  END IF;
END $$;

-- V4 — the 349 rows outside the 74 are identical in every column, updated_at included,
-- and 190 of them are still eligible; the four veg already eligible are among them
DO $$
DECLARE others int; others_moved int; others_el int; elig4 int;
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
            p.excluded_reason)),
         count(*) FILTER (WHERE c.menu_eligible)
    INTO others, others_moved, others_el
    FROM _pre p JOIN food_curation c USING (source_code)
   WHERE p.source_code NOT IN ('3566', '3570', '3588', '3590', '3594', '3595', '3612', '3617',
                               '3626', '3638', '3647', '3665', '3667', '3672', '3673', '3735',
                               '3748', '3752', '3754', '3756', '3762', '3767', '3772', '3774',
                               '3776', '3778', '3801', '3804', '3812', '3819', '3833', '3839',
                               '3843', '3847', '3849', '3852', '3901', '3912', '3920', '3924',
                               '3929', '3930', '3932', '3933', '3948', '3949', '3954', '3956',
                               '3981', '3985', '3988', '4023', '4024', '4032', '4040', '4063',
                               '4067', '4068', '4077', '4082', '4086', '4091', '4092', '4096',
                               '4124', '4148', '4159', '8219', '8240', '8292', '8308', '8567',
                               '8838', '9694');
  SELECT count(*) INTO elig4 FROM food_curation
   WHERE source_code IN ('3663', '3793', '3807', '3837') AND menu_eligible AND category = 'veg';
  IF others <> 349 OR others_moved <> 0 OR others_el <> 190 OR elig4 <> 4 THEN
    RAISE EXCEPTION 'V4 failed: others=% moved=% eligible-among-them=% four-veg=%', others, others_moved, others_el, elig4;
  END IF;
END $$;

-- V5 — the canonical snapshot afterwards, the safety views, and the vocabulary
DO $$
DECLARE tot int; el int; p int; f int; c int; v int; vm int; mt int; orph int; off_vocab int;
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
  IF tot<>423 OR el<>264 OR p<>105 OR f<>37 OR c<>44 OR v<>78 OR vm<>264 OR mt<>0 OR orph<>0 OR off_vocab<>0 THEN
    RAISE EXCEPTION 'V5 failed: tot=% el=% p=% f=% c=% v=% view=% missing_tags=% orphans=% off-vocabulary=%',
      tot, el, p, f, c, v, vm, mt, orph, off_vocab;
  END IF;
END $$;

-- V6 — v_recipe_unreviewed_components: after 19 it was 21 by design (the components of
-- the eight protein recipes, #49). The veg recipes may add to it; it may not drop below 21.
DO $$
DECLARE n int;
BEGIN
  SELECT count(*) INTO n FROM v_recipe_unreviewed_components;
  IF n < 21 THEN
    RAISE EXCEPTION 'V6 failed: v_recipe_unreviewed_components=% dropped below 21', n;
  END IF;
END $$;

COMMIT;
