-- Block 7ת-ג1 — migration 24: three label columns on food_curation, and no row touched.
-- Decided 16.09.2026 (docs/decisions.md, the 16.09.2026 row on migration 24 and its three
-- columns; docs/PROGRESS.md, row 7ת-ג1):
--   label_source   text     the address of the page the label was read from; several, separated
--                           by " | ", when one row covers several versions; for a label read from
--                           a packaging image on the maker's page, the address of the image file,
--                           on the maker's domain (decisions.md, 16.09.2026 and 19.09.2026)
--   label_date     date     the day the page, or the image, was read. date, not timestamptz: the
--                           name says a date, and every _at column in this schema is timestamptz
--   fiber_g_label  numeric  fibre per 100 g as the label states it (#59), typed as foods.fiber_g.
--                           After 25 it is NULL on every row - no labelled row needs it - and it
--                           stays, ready for 7מ (decisions.md, 19.09.2026)
-- The CHECK: label_source and label_date are both NULL or both set. A row curated by identity
-- carries all three NULL.
-- No row is written: the three columns are nullable with no default, so ADD COLUMN fills
-- nothing and the BEFORE UPDATE trigger touch_updated_at does not fire. The canonical snapshot
-- is the same before and after, 423 · 264 · 105 · 37 · 44 · 78 · 264 · 0 · 0, and the export
-- delta gate is N = 0.
-- 01_food_db_schema.sql carries the same three columns and the CHECK for a database built from
-- scratch - the two files must never disagree (07_exclusion_reason.sql:17-18).
-- Same shape as 23_flip_veg.sql: one transaction, a _pre snapshot of every existing column,
-- the change, assertions, COMMIT. V0 pins the state this file was written against, so a
-- second run fails before it touches anything.

BEGIN;

CREATE TEMP TABLE _pre ON COMMIT DROP AS
  SELECT source_code, category, kosher, allergens, allergens_reviewed_at, tags,
         quality, supp, prep, by_weight, whole_only, max_g, menu_eligible,
         curated_by, curated_at, created_at, updated_at, excluded_reason
    FROM food_curation;

-- V0 — precondition and rerun guard: none of the three columns and no constraint of that name
-- exists yet, and the table holds the 423 rows this file was written against
DO $$
DECLARE cols int; cons int; tot int;
BEGIN
  SELECT count(*) INTO cols FROM information_schema.columns
   WHERE table_schema = 'public' AND table_name = 'food_curation'
     AND column_name IN ('label_source', 'label_date', 'fiber_g_label');
  SELECT count(*) INTO cons FROM pg_constraint
   WHERE conrelid = 'public.food_curation'::regclass AND conname = 'label_source_and_date_together';
  SELECT count(*) INTO tot FROM food_curation;
  IF cols <> 0 OR cons <> 0 OR tot <> 423 THEN
    RAISE EXCEPTION 'V0 failed: label columns present=% constraint present=% rows=%', cols, cons, tot;
  END IF;
END $$;

-- The change. No DEFAULT and no NOT NULL on any of the three: NULL is the state of every row
-- until 25 writes the labelled ones.
ALTER TABLE food_curation
    ADD COLUMN label_source  text,
    ADD COLUMN label_date    date,
    ADD COLUMN fiber_g_label numeric;

-- Two-way on purpose, unlike excluded_reason_requires_ineligible: a source without the day it
-- was read cannot be checked again, and a date without a source dates nothing.
ALTER TABLE food_curation
    ADD CONSTRAINT label_source_and_date_together CHECK (
        (label_source IS NULL AND label_date IS NULL)
     OR (label_source IS NOT NULL AND label_date IS NOT NULL)
    );

-- Raw output for the record, before the assertions
SELECT ordinal_position, column_name, data_type, numeric_precision, numeric_scale,
       is_nullable, column_default
  FROM information_schema.columns
 WHERE table_schema = 'public' AND table_name = 'food_curation'
   AND column_name IN ('label_source', 'label_date', 'fiber_g_label')
 ORDER BY ordinal_position;

SELECT conname, contype, pg_get_constraintdef(oid) AS definition
  FROM pg_constraint
 WHERE conrelid = 'public.food_curation'::regclass AND conname = 'label_source_and_date_together';

-- V1 — the three columns: text · date · numeric (no precision, as foods.fiber_g), nullable,
-- no default
DO $$
DECLARE n int; ok int;
BEGIN
  SELECT count(*),
         count(*) FILTER (WHERE is_nullable = 'YES' AND column_default IS NULL
                            AND ((column_name = 'label_source'  AND data_type = 'text')
                              OR (column_name = 'label_date'    AND data_type = 'date')
                              OR (column_name = 'fiber_g_label' AND data_type = 'numeric'
                                  AND numeric_precision IS NULL AND numeric_scale IS NULL)))
    INTO n, ok
    FROM information_schema.columns
   WHERE table_schema = 'public' AND table_name = 'food_curation'
     AND column_name IN ('label_source', 'label_date', 'fiber_g_label');
  IF n <> 3 OR ok <> 3 THEN
    RAISE EXCEPTION 'V1 failed: columns=% with the expected type, nullable, no default=%', n, ok;
  END IF;
END $$;

-- V2 — the constraint is a CHECK on food_curation, and Postgres reads it back as written
DO $$
DECLARE def text;
BEGIN
  SELECT pg_get_constraintdef(oid) INTO def FROM pg_constraint
   WHERE conrelid = 'public.food_curation'::regclass AND contype = 'c'
     AND conname = 'label_source_and_date_together';
  IF def IS DISTINCT FROM
     'CHECK ((((label_source IS NULL) AND (label_date IS NULL)) OR ((label_source IS NOT NULL) AND (label_date IS NOT NULL))))' THEN
    RAISE EXCEPTION 'V2 failed: constraint definition %', def;
  END IF;
END $$;

-- V3 — no row carries a value in any of the three, and the table still holds 423 rows
DO $$
DECLARE tot int; filled int;
BEGIN
  SELECT count(*),
         count(*) FILTER (WHERE label_source IS NOT NULL OR label_date IS NOT NULL
                            OR fiber_g_label IS NOT NULL)
    INTO tot, filled
    FROM food_curation;
  IF tot <> 423 OR filled <> 0 THEN
    RAISE EXCEPTION 'V3 failed: rows=% with a label value=%', tot, filled;
  END IF;
END $$;

-- V4 — the 18 existing columns are unchanged on every row, updated_at included: EXCEPT both
-- ways against _pre, equal counts, and field by field joined on source_code, as 23's V4
DO $$
DECLARE only_now int; only_pre int; n_now int; n_pre int; moved int;
BEGIN
  SELECT count(*) INTO only_now FROM (
    SELECT source_code, category, kosher, allergens, allergens_reviewed_at, tags,
           quality, supp, prep, by_weight, whole_only, max_g, menu_eligible,
           curated_by, curated_at, created_at, updated_at, excluded_reason
      FROM food_curation
    EXCEPT
    SELECT * FROM _pre) x;
  SELECT count(*) INTO only_pre FROM (
    SELECT * FROM _pre
    EXCEPT
    SELECT source_code, category, kosher, allergens, allergens_reviewed_at, tags,
           quality, supp, prep, by_weight, whole_only, max_g, menu_eligible,
           curated_by, curated_at, created_at, updated_at, excluded_reason
      FROM food_curation) x;
  SELECT count(*) INTO n_now FROM food_curation;
  SELECT count(*) INTO n_pre FROM _pre;
  SELECT count(*) FILTER (WHERE
           (c.category, c.kosher, c.allergens, c.allergens_reviewed_at, c.tags,
            c.quality, c.supp, c.prep, c.by_weight, c.whole_only, c.max_g,
            c.menu_eligible, c.curated_by, c.curated_at, c.created_at, c.updated_at,
            c.excluded_reason)
           IS DISTINCT FROM
           (p.category, p.kosher, p.allergens, p.allergens_reviewed_at, p.tags,
            p.quality, p.supp, p.prep, p.by_weight, p.whole_only, p.max_g,
            p.menu_eligible, p.curated_by, p.curated_at, p.created_at, p.updated_at,
            p.excluded_reason))
    INTO moved
    FROM _pre p JOIN food_curation c USING (source_code);
  IF only_now <> 0 OR only_pre <> 0 OR n_now <> n_pre OR n_now <> 423 OR moved <> 0 THEN
    RAISE EXCEPTION 'V4 failed: only-now=% only-pre=% rows now=% pre=% moved=%',
      only_now, only_pre, n_now, n_pre, moved;
  END IF;
END $$;

-- V5 — the canonical snapshot afterwards and the safety views, unchanged
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
  IF tot<>423 OR el<>264 OR p<>105 OR f<>37 OR c<>44 OR v<>78 OR vm<>264 OR mt<>0 OR orph<>0 THEN
    RAISE EXCEPTION 'V5 failed: tot=% el=% p=% f=% c=% v=% view=% missing_tags=% orphans=%',
      tot, el, p, f, c, v, vm, mt, orph;
  END IF;
END $$;

COMMIT;
