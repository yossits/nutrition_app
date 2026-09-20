-- Block 8ש-ו — olive tagging: five new food_curation rows and one UPDATE, none menu_eligible.
-- The list is db/block8_fat_codes.txt (8ש-ב, 20.09.2026): the olive family reopened, six codes.
-- Five of them have no curation row today — V0 proves it. 4279 does: it was curated in 3ד and
-- left menu_eligible false in 4ג (migration 14), and it is the one row this file updates.
-- This is why 26 combines the two forms — 22_tag_veg.sql's INSERT and 25_flip_labels.sql's
-- UPDATE against a temp table whose names are checked against foods.
--
-- Values per the 8ש-ד decisions (docs/work/2026-09-20-block-8-fat.md, docs/decisions.md
-- 20.09.2026): one default for the whole family, no exceptions — category fat · kosher parve ·
-- tags {vegan} · quality NULL · supp false · prep 0 · by_weight true · whole_only false ·
-- max_g 60 · menu_eligible false. by_weight and whole_only are not free of each other: the
-- CHECK whole_only_requires_a_unit (db/01_food_db_schema.sql) forbids both, and all 154
-- by_weight rows in the table today carry whole_only false. A by_weight row carries no unit at
-- all — 09 zeroes it in the export (spec/05-food-db.md §5, decisions.md 31.08.2026).
-- The grams decision: the sheet proposed a single olive, 2.9–4 g, with whole_only; the solver
-- serves a whole_only row in one, two or three units (#53), so the effective ceiling would be
-- ~9–12 g of olives, under 2 g of fat. 60 g is about 15 olives, ~9 g of fat, and it is the
-- ceiling 4279 already carries from 3ד.
--
-- Allergens deliberately UNREVIEWED on the five (column default '{}', allergens_reviewed_at
-- NULL): 8ש-ה decided '{}' for all six, and 27 writes it together with menu_eligible. 4279's
-- allergens_reviewed_at is NOT touched here — it carries 30.08.2026 and 27 rewrites it.
-- The UPDATE writes only what the tagging decision changes, by_weight and whole_only; the four
-- values 4279 already carries — category, kosher, tags, prep, max_g — are asserted in V0 and
-- again in V2 rather than rewritten, so a row that drifted fails loudly instead of being fixed
-- silently. curated_by and curated_at are left as 3ד wrote them, the way 25 left them.
--
-- No row becomes eligible here. Expected canonical snapshot afterwards:
--   428 · 267 · 108 · 37 · 44 · 78 · 267 · 0 · 0
-- V0 pins the snapshot this file was written against, so a second run fails before it writes.

BEGIN;

CREATE TEMP TABLE _pre ON COMMIT DROP AS
  SELECT source_code, category, kosher, allergens, allergens_reviewed_at, tags,
         quality, supp, prep, by_weight, whole_only, max_g, menu_eligible,
         curated_by, curated_at, created_at, updated_at, excluded_reason,
         label_source, label_date, fiber_g_label
    FROM food_curation;

-- The six codes of db/block8_fat_codes.txt, with the name each one carries in foods
CREATE TEMP TABLE _six (source_code text PRIMARY KEY, name_he text NOT NULL,
                        is_update boolean NOT NULL) ON COMMIT DROP;
INSERT INTO _six (source_code, name_he, is_update) VALUES
    ('4278', 'זיתים, לפנ',                                     false),
    ('4279', 'זיתים ירוקים',                                    true ),
    ('4283', 'זיתים שחורים, בני דרום, בית השיטה',                false),
    ('4284', 'זיתים ירוקים, ממולאים',                            false),
    ('4285', 'זיתים ללא גלעינים, קיבוץ יבנה, בית השיטה, אסם',    false),
    ('4288', 'זיתים מושחרים, קיבוץ יבנה, בית השיטה',             false);

-- V0 — precondition and rerun guard: the snapshot this file expects; all six exist in foods
-- under the sheet's name; five have no curation row; 4279 has one, not eligible, fat, parve,
-- {vegan}, prep 0, max_g 60, quality NULL, supp false, no excluded_reason
DO $$
DECLARE tot int; el int; p int; f int; c int; v int; vm int; mt int; orph int;
        six int; named int; present int; ready int;
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
  SELECT count(*) FILTER (WHERE fd.name_he = s.name_he)
    INTO named FROM _six s JOIN foods fd ON fd.source_code = s.source_code;
  SELECT count(*) INTO present
    FROM _six s JOIN food_curation cu ON cu.source_code = s.source_code;
  SELECT count(*) INTO ready
    FROM _six s JOIN food_curation cu ON cu.source_code = s.source_code
   WHERE s.is_update
     AND cu.menu_eligible = false AND cu.category = 'fat' AND cu.kosher = 'parve'
     AND cu.tags = '{vegan}'::text[] AND cu.prep = 0 AND cu.max_g = 60
     AND cu.quality IS NULL AND cu.supp = false AND cu.excluded_reason IS NULL;
  IF tot<>423 OR el<>267 OR p<>108 OR f<>37 OR c<>44 OR v<>78 OR vm<>267 OR mt<>0 OR orph<>0
     OR six<>6 OR named<>6 OR present<>1 OR ready<>1 THEN
    RAISE EXCEPTION 'V0 failed: tot=% el=% p=% f=% c=% v=% view=% missing_tags=% orphans=% · six=% named=% present=% ready=%',
      tot, el, p, f, c, v, vm, mt, orph, six, named, present, ready;
  END IF;
END $$;

-- Write 1 of 2 — the five that have no row. Column order:
--   source_code, category, kosher, tags, quality, supp, prep,
--   by_weight, whole_only, max_g, menu_eligible, excluded_reason, curated_by, curated_at
-- allergens and allergens_reviewed_at are omitted on purpose (default '{}', NULL).
INSERT INTO food_curation
  (source_code, category, kosher, tags, quality, supp, prep,
   by_weight, whole_only, max_g, menu_eligible, excluded_reason, curated_by, curated_at)
VALUES
  ('4278', 'fat', 'parve', '{vegan}', NULL, false, 0, true, false, 60, false, NULL, 'yossi', now()),  -- זיתים, לפנ
  ('4283', 'fat', 'parve', '{vegan}', NULL, false, 0, true, false, 60, false, NULL, 'yossi', now()),  -- זיתים שחורים, בני דרום, בית השיטה
  ('4284', 'fat', 'parve', '{vegan}', NULL, false, 0, true, false, 60, false, NULL, 'yossi', now()),  -- זיתים ירוקים, ממולאים
  ('4285', 'fat', 'parve', '{vegan}', NULL, false, 0, true, false, 60, false, NULL, 'yossi', now()),  -- זיתים ללא גלעינים, קיבוץ יבנה, בית השיטה, אסם
  ('4288', 'fat', 'parve', '{vegan}', NULL, false, 0, true, false, 60, false, NULL, 'yossi', now());  -- זיתים מושחרים, קיבוץ יבנה, בית השיטה

-- Write 2 of 2 — 4279, the row 3ד curated: by_weight false → true and whole_only true → false,
-- the two fields the family default changes. Nothing else on the row is rewritten.
UPDATE food_curation c
   SET by_weight  = true,
       whole_only = false
  FROM _six s
 WHERE c.source_code = s.source_code AND s.is_update;

-- Raw output for the record, before the assertions
SELECT c.source_code, f.name_he, c.category, c.kosher, c.tags, c.allergens,
       c.allergens_reviewed_at IS NOT NULL AS reviewed, c.prep, c.by_weight, c.whole_only,
       c.max_g, c.menu_eligible, c.curated_at
  FROM food_curation c JOIN foods f ON f.source_code = c.source_code
 WHERE c.source_code IN ('4278', '4279', '4283', '4284', '4285', '4288')
 ORDER BY c.source_code::int;

-- V1 — exactly 5 rows added, none removed, and the added set is the five non-update codes
DO $$
DECLARE tot int; added int; removed int; who text;
BEGIN
  SELECT count(*) INTO tot FROM food_curation;
  SELECT count(*) INTO added
    FROM food_curation c WHERE NOT EXISTS (SELECT 1 FROM _pre p WHERE p.source_code = c.source_code);
  SELECT count(*) INTO removed
    FROM _pre p WHERE NOT EXISTS (SELECT 1 FROM food_curation c WHERE c.source_code = p.source_code);
  SELECT string_agg(c.source_code, ',' ORDER BY c.source_code::int) INTO who
    FROM food_curation c WHERE NOT EXISTS (SELECT 1 FROM _pre p WHERE p.source_code = c.source_code);
  IF tot <> 428 OR added <> 5 OR removed <> 0 OR who <> '4278,4283,4284,4285,4288' THEN
    RAISE EXCEPTION 'V1 failed: tot=% added=% removed=% who=%', tot, added, removed, who;
  END IF;
END $$;

-- V2 — the decision values on all six, and the allergen state each one should be in:
-- the five unreviewed with '{}', 4279 still carrying the review 3ד wrote
DO $$
DECLARE n int; off_spec int; five_unreviewed int; kept int;
BEGIN
  SELECT count(*),
         count(*) FILTER (WHERE NOT (c.category = 'fat' AND c.kosher = 'parve'
                              AND c.tags = '{vegan}'::text[] AND c.quality IS NULL
                              AND c.supp = false AND c.prep = 0
                              AND c.by_weight = true AND c.whole_only = false
                              AND c.max_g = 60 AND c.menu_eligible = false
                              AND c.excluded_reason IS NULL
                              AND c.allergens = '{}'::text[]
                              AND c.label_source IS NULL AND c.label_date IS NULL
                              AND c.fiber_g_label IS NULL))
    INTO n, off_spec
    FROM food_curation c JOIN _six s ON s.source_code = c.source_code;
  SELECT count(*) INTO five_unreviewed
    FROM food_curation c JOIN _six s ON s.source_code = c.source_code
   WHERE NOT s.is_update AND c.allergens_reviewed_at IS NULL AND c.curated_by = 'yossi';
  SELECT count(*) INTO kept
    FROM food_curation c JOIN _pre p USING (source_code) JOIN _six s ON s.source_code = c.source_code
   WHERE s.is_update
     AND c.allergens_reviewed_at = p.allergens_reviewed_at
     AND c.curated_by = p.curated_by AND c.curated_at = p.curated_at
     AND c.created_at = p.created_at;
  IF n <> 6 OR off_spec <> 0 OR five_unreviewed <> 5 OR kept <> 1 THEN
    RAISE EXCEPTION 'V2 failed: n=% off-spec=% five_unreviewed=% kept=%', n, off_spec, five_unreviewed, kept;
  END IF;
END $$;

-- V3 — 4279 changed in exactly by_weight and whole_only, and in updated_at
DO $$
DECLARE moved int; other int;
BEGIN
  SELECT count(*) INTO moved
    FROM food_curation c JOIN _pre p USING (source_code)
   WHERE c.source_code = '4279'
     AND p.by_weight = false AND c.by_weight = true
     AND p.whole_only = true AND c.whole_only = false
     AND c.updated_at > p.updated_at;
  SELECT count(*) INTO other
    FROM food_curation c JOIN _pre p USING (source_code)
   WHERE c.source_code = '4279'
     AND (c.category IS DISTINCT FROM p.category OR c.kosher IS DISTINCT FROM p.kosher
       OR c.allergens IS DISTINCT FROM p.allergens
       OR c.allergens_reviewed_at IS DISTINCT FROM p.allergens_reviewed_at
       OR c.tags IS DISTINCT FROM p.tags OR c.quality IS DISTINCT FROM p.quality
       OR c.supp IS DISTINCT FROM p.supp OR c.prep IS DISTINCT FROM p.prep
       OR c.max_g IS DISTINCT FROM p.max_g OR c.menu_eligible IS DISTINCT FROM p.menu_eligible
       OR c.curated_by IS DISTINCT FROM p.curated_by OR c.curated_at IS DISTINCT FROM p.curated_at
       OR c.created_at IS DISTINCT FROM p.created_at
       OR c.excluded_reason IS DISTINCT FROM p.excluded_reason
       OR c.label_source IS DISTINCT FROM p.label_source
       OR c.label_date IS DISTINCT FROM p.label_date
       OR c.fiber_g_label IS DISTINCT FROM p.fiber_g_label);
  IF moved <> 1 OR other <> 0 THEN
    RAISE EXCEPTION 'V3 failed: moved=% other-fields-changed=%', moved, other;
  END IF;
END $$;

-- V4 — the 422 rows that are neither new nor 4279 are identical, every column, updated_at included
DO $$
DECLARE n int; moved int;
BEGIN
  SELECT count(*) INTO n FROM _pre WHERE source_code <> '4279';
  SELECT count(*) INTO moved
    FROM _pre p JOIN food_curation c USING (source_code)
   WHERE p.source_code <> '4279'
     AND (c.category IS DISTINCT FROM p.category OR c.kosher IS DISTINCT FROM p.kosher
       OR c.allergens IS DISTINCT FROM p.allergens
       OR c.allergens_reviewed_at IS DISTINCT FROM p.allergens_reviewed_at
       OR c.tags IS DISTINCT FROM p.tags OR c.quality IS DISTINCT FROM p.quality
       OR c.supp IS DISTINCT FROM p.supp OR c.prep IS DISTINCT FROM p.prep
       OR c.by_weight IS DISTINCT FROM p.by_weight OR c.whole_only IS DISTINCT FROM p.whole_only
       OR c.max_g IS DISTINCT FROM p.max_g OR c.menu_eligible IS DISTINCT FROM p.menu_eligible
       OR c.curated_by IS DISTINCT FROM p.curated_by OR c.curated_at IS DISTINCT FROM p.curated_at
       OR c.created_at IS DISTINCT FROM p.created_at OR c.updated_at IS DISTINCT FROM p.updated_at
       OR c.excluded_reason IS DISTINCT FROM p.excluded_reason
       OR c.label_source IS DISTINCT FROM p.label_source
       OR c.label_date IS DISTINCT FROM p.label_date
       OR c.fiber_g_label IS DISTINCT FROM p.fiber_g_label);
  IF n <> 422 OR moved <> 0 THEN
    RAISE EXCEPTION 'V4 failed: _pre holds % rows besides 4279, % of them changed', n, moved;
  END IF;
END $$;

-- V5 — counts afterwards: 5 more rows, eligibility untouched, the views unchanged
DO $$
DECLARE tot int; el int; p int; f int; c int; v int; vm int; mt int; orph int;
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
  IF tot<>428 OR el<>267 OR p<>108 OR f<>37 OR c<>44 OR v<>78 OR vm<>267 OR mt<>0 OR orph<>0 THEN
    RAISE EXCEPTION 'V5 failed: tot=% el=% p=% f=% c=% v=% view=% missing_tags=% orphans=%',
      tot, el, p, f, c, v, vm, mt, orph;
  END IF;
END $$;

COMMIT;
