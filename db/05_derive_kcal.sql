-- ============================================================================
--  05_derive_kcal.sql — kcal becomes a derived column
--
--  Why: the database carries two calorie sources that do not agree — the
--  file's declared food_energy, and P*4 + F*9 + C*4 from the macros. The gap
--  reaches 24% on legumes. The portion solver chases a calorie target AND
--  macro targets at once; when the items themselves are inconsistent the two
--  cannot both hold, and the validator penalises the solver for a
--  contradiction that is in the data, not in the solve.
--
--  From here on kcal is derived as P*4 + F*9 + C*4 + fibre*2 + ethanol*7, and
--  the file's value is kept in kcal_source. Nothing is deleted.
--
--  Re-runnable, and meant to be edited in place rather than superseded by a
--  06: ADD COLUMN IF NOT EXISTS is safe, the kcal_source UPDATE is a no-op once
--  the column is populated, and the kcal UPDATE simply recomputes. Re-running
--  this file after a formula change brings production to the correct state
--  without a separate delta.
--
--  The same derivation also lives as a step in 04_transform.py, so a future
--  re-import does not silently undo it. That copy is the source of truth.
-- ============================================================================

BEGIN;

-- ---------------------------------------------------------------- 1. Columns

ALTER TABLE foods ADD COLUMN IF NOT EXISTS kcal_source numeric;

-- Keep the source once, and once only. A re-run must not overwrite it with an
-- already-derived kcal.
UPDATE foods SET kcal_source = kcal WHERE kcal_source IS NULL;

-- kcal was NOT NULL, which was right while it held the file's value. As a
-- derived column it must be nullable: if the derivation step is ever dropped,
-- kcal should come out NULL on every row rather than quietly keeping a stale
-- value that looks fine. Same failure mode as the `complete` bug.
ALTER TABLE foods ALTER COLUMN kcal DROP NOT NULL;

-- --------------------------------------------------------------- 2. Derivation

-- P*4 + F*9 + available carbohydrate*4 + fibre*2 + ethanol*7.
-- These are the coefficients Israeli food labelling is regulated by, so a user
-- checking a tub in the fridge sees the same number.
--
-- Ethanol sits in no macro field. Without its term a bottle of gin derives to
-- 0 kcal against a declared 263; with it, 37.9 g * 7 = 265. It lives in
-- food_nutrients and is looked up by nutrients.code — never by a hardcoded id,
-- which moves if nutrients is reseeded.
--
-- Polyols were measured and left out: 45 of the 325 gate rows, all sweets and
-- chewing gum that will never be curated, and the median barely moved.
-- nutrients.code = 'sugar_alcohols' is there if it is ever reopened.
--
-- COALESCE(fiber_g, 0) touches 384 items whose fibre is NULL rather than 0.
-- Decided provisionally in favour of zero on 28.08.2026 so the migration is
-- not blocked; it contradicts the principle that NULL is not 0, it is logged
-- in open-questions.md, and it may be reversed.
--
-- The NULL rule. An item that declares calories but carries no macro base at
-- all — no protein, fat, carbohydrate, fibre or ethanol — has nothing to
-- derive from. Writing 0 there would be a silent failure: sucralose tablets
-- declaring 390 kcal would read as free. NULL fails loudly instead. This is
-- the NOT NULL argument applied to the data rather than to the column.
-- Catches exactly two rows, 8703 and 9740. The genuinely zero items (water,
-- salt, 0-kcal sweeteners) are not caught — their kcal_source is 0.
UPDATE foods f
SET kcal = src.kcal
FROM (
    SELECT f2.id,
           CASE
             WHEN f2.kcal_source > 0
              AND f2.protein_g = 0
              AND f2.fat_g     = 0
              AND f2.carb_g    = 0
              AND COALESCE(f2.fiber_g,0)  = 0
              AND COALESCE(al.value,0)    = 0
             THEN NULL
             ELSE ROUND(f2.protein_g*4 + f2.fat_g*9 + f2.carb_g*4
                      + COALESCE(f2.fiber_g,0)*2
                      + COALESCE(al.value,0)*7, 1)
           END AS kcal
    FROM foods f2
    LEFT JOIN food_nutrients al
           ON al.food_id = f2.id
          AND al.nutrient_id = (SELECT id FROM nutrients WHERE code = 'alcohol')
) src
WHERE f.id = src.id;

-- ------------------------------------------------------- 3. The third validator

-- The Atwater curation gate, alongside v_eligible_missing_tags and
-- v_pool_depth. Three known reasons the two figures disagree: dietary fibre
-- (carb_g is available carbohydrate, the label counts fibre too), polyols and
-- sucralose-bulked sweeteners, and ethanol at 7 kcal/g which sits in no macro
-- field at all.
--
-- Two thresholds, both required. 12% relative catches the real disagreements;
-- the absolute 5 kcal floor keeps every 6-kcal diet drink out of the list.
--
-- NOT a CHECK constraint. Items land here and are still correct (sugar-free
-- products). An item listed here does not get menu_eligible until a human has
-- ruled on it — a curation decision, not an automatic block.
--
-- category and menu_eligible come from food_curation since 06_split_curation.sql
-- — this file defines the view a second time, alongside 01_food_db_schema.sql,
-- so both definitions have to move together. A re-run of this file with the
-- old body would silently restore a view reading columns that no longer exist
-- on foods, and fail on the next re-run of the schema instead of here.
--
-- LEFT JOIN, and here it is load-bearing. The gate has to work on an UNCURATED
-- database — that is its whole job, since an item is ruled on here before it
-- gets menu_eligible. An INNER join would empty the view exactly when it
-- matters most. COALESCE keeps the ordering column non-NULL.
CREATE OR REPLACE VIEW v_kcal_outliers AS
SELECT f.id, f.source_code, f.name_he, f.makor,
       c.category,
       COALESCE(c.menu_eligible, false) AS menu_eligible,
       f.kcal_source, f.kcal,
       ROUND(((f.kcal - f.kcal_source) / NULLIF(f.kcal_source,0) * 100)::numeric, 1) AS dev_pct,
       CASE
         WHEN f.kcal > f.kcal_source THEN 'עודף — חשד לפוליאולים או כוהל'
         WHEN f.fiber_g IS NULL      THEN 'חוסר — סיבים לא ידועים'
         ELSE                             'חוסר — לא מוסבר'
       END AS suspected
FROM foods f
LEFT JOIN food_curation c ON c.source_code = f.source_code
WHERE f.kcal_source > 0
  AND f.kcal IS NOT NULL
  AND abs(f.kcal - f.kcal_source) / f.kcal_source > 0.12
  AND abs(f.kcal - f.kcal_source) >= 5
ORDER BY COALESCE(c.menu_eligible, false) DESC,
         abs(f.kcal - f.kcal_source) / f.kcal_source DESC;

-- --------------------------------------------------------------- 4. Grants

-- A view carries no RLS of its own and runs as its owner, so a view granted to
-- anon reads and writes straight past the policies on foods. Supabase grants
-- anon full DML on new objects by default, and a single-table view like
-- v_pool_depth is auto-updatable — which made DELETE through the view a live
-- path into the base table with the public anon key.
--
-- security_invoker makes the view honour the caller's own RLS; the REVOKE/GRANT
-- pair leaves nothing but SELECT. Applied to every view, not just this one:
-- they all had the same hole. Seven since 06_split_curation.sql.
DO $$
DECLARE v text;
BEGIN
  FOREACH v IN ARRAY ARRAY[
      'v_kcal_outliers',
      'v_eligible_missing_tags',
      'v_pool_depth',
      'v_recipe_inherited_allergens',
      'v_recipe_unreviewed_components',
      'v_menu_foods',
      'v_curation_orphans'
  ] LOOP
      EXECUTE format('ALTER VIEW %I SET (security_invoker = on)', v);
      EXECUTE format('REVOKE ALL ON %I FROM anon, authenticated', v);
      EXECUTE format('GRANT SELECT ON %I TO anon, authenticated', v);
  END LOOP;
END $$;

COMMIT;

-- ============================================================================
--  Verification — run after COMMIT.
--
--  `kcal <= 0` on its own is the wrong test: it flags water and salt, where 0
--  is the correct answer. zero_but_caloric is the real one — an item that
--  declares calories and still derived to 0 means energy the formula cannot
--  see.
--
--  Stop conditions: negative > 0, zero_but_caloric > 0, or derived_null <> 2.
--
--  The two expected NULLs are 8703 (sucralose tablets, declared 390, bulked
--  with a carbohydrate the macro row omits) and 9740 (wheatgrass juice,
--  declared 21, all four macros at zero).
-- ============================================================================

-- SELECT count(*) AS total,
--        count(kcal_source)                                    AS with_source,
--        count(kcal)                                           AS with_derived,
--        count(*) FILTER (WHERE kcal IS NULL)                  AS derived_null,
--        count(*) FILTER (WHERE kcal < 0)                      AS negative,
--        count(*) FILTER (WHERE kcal <= 0 AND kcal_source > 0) AS zero_but_caloric,
--        ROUND((percentile_cont(0.5) WITHIN GROUP (
--          ORDER BY abs(kcal-kcal_source)/NULLIF(kcal_source,0))*100)::numeric,2)
--                                                              AS median_dev_pct
-- FROM foods;
