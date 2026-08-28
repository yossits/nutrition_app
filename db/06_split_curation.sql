-- ============================================================================
--  06_split_curation.sql — the curation fields move off foods
--
--  Why: 04_transform.py opens with
--      TRUNCATE food_recipe_components, food_nutrients, food_servings,
--               foods, nutrients RESTART IDENTITY CASCADE
--  and rebuilds foods from src_*. Every hand-made tagging field sat on that
--  same table, so one re-import after curation begins would erase all of it —
--  567 allergen-tagged base ingredients, the kosher review, the quality tiers.
--
--  The src_* layer is genuinely re-runnable, and that was verified against
--  production. But it is re-runnable for DERIVED data. foods held derived and
--  hand-made data in one table, and only one of the two can be rebuilt.
--
--  Run once against production, after 05_derive_kcal.sql.
--  01_food_db_schema.sql carries the same split for a database built from
--  scratch — the two files must never disagree, or a rebuild silently
--  restores the old shape.
--
--  Safe only while no curation exists. Before running, this must return 0:
--
--      SELECT count(*) FROM foods
--      WHERE menu_eligible
--         OR category IS NOT NULL OR kosher IS NOT NULL
--         OR allergens <> '{}' OR allergens_reviewed_at IS NOT NULL
--         OR tags <> '{}' OR quality IS NOT NULL OR supp
--         OR prep IS NOT NULL OR price IS NOT NULL
--         OR whole_only OR NOT by_weight OR max_g IS NOT NULL
--         OR curated_by IS NOT NULL OR curated_at IS NOT NULL;
--
--  Verified 0 against production on 28.08.2026 — this is a migration with no
--  data to carry across, which is exactly why it had to happen before the
--  first menu_eligible and not after.
-- ============================================================================

BEGIN;

-- ============================================================================
--  1. The five views go first — they read columns that are about to fall
-- ============================================================================

-- Explicit, not DROP COLUMN ... CASCADE. What falls silently comes back
-- silently, and these five are the validators the whole curation stage is
-- checked by. All five are recreated in section 5.
DROP VIEW IF EXISTS v_eligible_missing_tags;
DROP VIEW IF EXISTS v_recipe_unreviewed_components;
DROP VIEW IF EXISTS v_recipe_inherited_allergens;
DROP VIEW IF EXISTS v_pool_depth;
DROP VIEW IF EXISTS v_kcal_outliers;


-- ============================================================================
--  2. food_curation — the hand-made layer, on its own table
-- ============================================================================

-- The key is source_code, not foods.id. RESTART IDENTITY renumbers foods.id on
-- every import, so curation keyed on the surrogate would come back pointing at
-- a different food — silently, with no error and no orphan. source_code comes
-- from the Ministry of Health file and survives a re-import.
--
-- Deliberately NO FOREIGN KEY to foods.
--   TRUNCATE ... CASCADE empties every table that references one on its list.
--   A FK here would CONDUCT the deletion, not prevent it — it would recreate
--   the exact failure this file exists to close, while looking like the
--   careful thing to do. Referential integrity is enforced by
--   v_curation_orphans, which must return 0 rows, and 04_transform.py aborts
--   the run when it does not. Do not "fix" this by adding the FK.
CREATE TABLE food_curation (
    source_code text PRIMARY KEY,               -- Code, from the source database

    category              food_category,
    kosher                kosher_type,
    allergens             text[] NOT NULL DEFAULT '{}',
    allergens_reviewed_at timestamptz,          -- '{}' = reviewed and clean · NULL here = not reviewed
    tags                  text[] NOT NULL DEFAULT '{}',   -- vegan · vegetarian · ...
    quality               smallint CHECK (quality BETWEEN 1 AND 3),
    supp                  boolean NOT NULL DEFAULT false, -- supplement (protein powder etc.)
    prep                  smallint CHECK (prep  BETWEEN 0 AND 2),
    price                 smallint CHECK (price BETWEEN 1 AND 3),

    -- Serving policy --------------------------------------------------------
    by_weight  boolean NOT NULL DEFAULT true,   -- measured in grams
    whole_only boolean NOT NULL DEFAULT false,  -- no such thing as half an egg
    max_g      numeric CHECK (max_g > 0),       -- ceiling against 400 g of avocado

    menu_eligible boolean NOT NULL DEFAULT false,

    curated_by text,
    curated_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),

    -- The safety gate travels with the fields it guards, unchanged. A CHECK
    -- cannot span tables — which is why by_weight had to move here too, since
    -- whole_only_requires_a_unit reads both of them.
    CONSTRAINT eligible_requires_safety_tagging CHECK (
        NOT menu_eligible OR (
            category              IS NOT NULL
        AND kosher                IS NOT NULL
        AND allergens_reviewed_at IS NOT NULL
        )
    ),
    CONSTRAINT eligible_protein_requires_quality CHECK (
        NOT (menu_eligible AND category = 'protein') OR quality IS NOT NULL
    ),
    CONSTRAINT whole_only_requires_a_unit CHECK (
        NOT whole_only OR NOT by_weight
    )
);

-- The three indexes travel with their columns. New names: the foods_* ones
-- fall together with the columns in section 3.
CREATE INDEX food_curation_eligible_idx  ON food_curation (category) WHERE menu_eligible;
CREATE INDEX food_curation_allergens_idx ON food_curation USING gin (allergens);
CREATE INDEX food_curation_tags_idx      ON food_curation USING gin (tags);

CREATE TRIGGER food_curation_touch_updated_at
    BEFORE UPDATE ON food_curation
    FOR EACH ROW EXECUTE FUNCTION touch_updated_at();


-- ============================================================================
--  3. The 15 columns come off foods
-- ============================================================================

-- The three CHECK constraints and the three indexes over these columns fall
-- with them; no separate DROP is needed.
--
-- `complete` stays on foods. It is derived from the nine essential amino acids
-- in 04_transform.py, not tagged by hand, so a rebuild is exactly what should
-- reproduce it.
ALTER TABLE foods
    DROP COLUMN category,
    DROP COLUMN kosher,
    DROP COLUMN allergens,
    DROP COLUMN allergens_reviewed_at,
    DROP COLUMN tags,
    DROP COLUMN quality,
    DROP COLUMN supp,
    DROP COLUMN prep,
    DROP COLUMN price,
    DROP COLUMN by_weight,
    DROP COLUMN whole_only,
    DROP COLUMN max_g,
    DROP COLUMN menu_eligible,
    DROP COLUMN curated_by,
    DROP COLUMN curated_at;


-- ============================================================================
--  4. The two new views
-- ============================================================================

-- The generator's input. INNER JOIN on purpose: a food with no curation row
-- cannot reach the prompt. That is the same rule as the old
-- `WHERE menu_eligible`, now carried by the join itself.
CREATE VIEW v_menu_foods AS
SELECT f.id, f.source_code, f.class_code, f.makor, f.source,
       f.name_he, f.name_en,
       f.kcal_source, f.kcal,
       f.protein_g, f.fat_g, f.carb_g,
       f.fiber_g, f.sugar_g, f.sat_fat_g, f.sodium_mg,
       f.complete,
       c.category, c.kosher, c.allergens, c.allergens_reviewed_at,
       c.tags, c.quality, c.supp, c.prep, c.price,
       c.by_weight, c.whole_only, c.max_g,
       c.curated_by, c.curated_at
FROM foods f
JOIN food_curation c ON c.source_code = f.source_code
WHERE c.menu_eligible;

-- This is what replaces the foreign key. A curation row whose source_code is
-- no longer in foods means the import dropped an item out from under tagging
-- work that still exists. Must return 0 rows; 04_transform.py checks it as a
-- stop condition and rolls the run back if it does not.
CREATE VIEW v_curation_orphans AS
SELECT c.source_code, c.category, c.menu_eligible, c.curated_by, c.curated_at
FROM food_curation c
WHERE NOT EXISTS (SELECT 1 FROM foods f WHERE f.source_code = c.source_code);


-- ============================================================================
--  5. The five validators, rebuilt over the join
-- ============================================================================

-- The join type is not cosmetic in any of these. Each one is noted.

-- INNER: menu_eligible cannot exist without a curation row.
CREATE VIEW v_eligible_missing_tags AS
SELECT f.id, c.source_code, f.name_he,
       c.category              IS NULL AS no_category,
       c.kosher                IS NULL AS no_kosher,
       c.allergens_reviewed_at IS NULL AS no_allergen_review,
       (c.category = 'protein' AND c.quality IS NULL) AS no_quality
FROM food_curation c
JOIN foods f ON f.source_code = c.source_code
WHERE c.menu_eligible
  AND (c.category IS NULL
       OR c.kosher IS NULL
       OR c.allergens_reviewed_at IS NULL
       OR (c.category = 'protein' AND c.quality IS NULL));


-- A curated recipe with an unreviewed component = an allergen that can slip
-- under the radar.
--
-- Two separate joins to food_curation, and they are not the same kind. The
-- recipe side is INNER — only a curated recipe can be eligible. The component
-- side must be LEFT: a component with no curation row AT ALL is the most
-- unreviewed a component can be, and an INNER join would hide exactly those.
CREATE VIEW v_recipe_unreviewed_components AS
SELECT r.id AS recipe_id, r.name_he AS recipe,
       c.id AS component_id, c.name_he AS component
FROM foods r
JOIN food_curation rc_cur ON rc_cur.source_code = r.source_code
JOIN food_recipe_components rc ON rc.recipe_id = r.id
JOIN foods c ON c.id = rc.component_id
LEFT JOIN food_curation c_cur ON c_cur.source_code = c.source_code
WHERE rc_cur.menu_eligible
  AND c_cur.allergens_reviewed_at IS NULL;


-- Allergens a recipe inherits from its components. A source of tagging
-- suggestions, not a substitute for human sign-off.
-- INNER: a component with no curation row carries no known allergens.
CREATE VIEW v_recipe_inherited_allergens AS
SELECT rc.recipe_id, array_agg(DISTINCT a ORDER BY a) AS inherited
FROM food_recipe_components rc
JOIN foods c ON c.id = rc.component_id
JOIN food_curation c_cur ON c_cur.source_code = c.source_code
CROSS JOIN LATERAL unnest(c_cur.allergens) AS a
GROUP BY rc.recipe_id;


-- Pool depth by category. This is the metric curation is meant to move, not
-- the total count. Fat and protein are the bottleneck (17% / 20% at p10).
-- One table now: every column it reads lives on food_curation.
CREATE VIEW v_pool_depth AS
SELECT category,
       count(*)                                                   AS eligible,
       count(*) FILTER (WHERE allergens = '{}')                   AS allergen_free,
       count(*) FILTER (WHERE 'vegan' = ANY(tags))                AS vegan,
       count(*) FILTER (WHERE kosher = 'parve')                   AS parve,
       count(*) FILTER (WHERE prep = 0)                           AS no_prep
FROM food_curation
WHERE menu_eligible
GROUP BY category
ORDER BY category;


-- The Atwater curation gate — the third validator, alongside
-- v_eligible_missing_tags and v_pool_depth.
--
-- The file's declared energy and the derived kcal disagree for three known
-- reasons: dietary fibre (carb_g is available carbohydrate, the label counts
-- fibre too), polyols and sucralose-bulked sweeteners (energy the macros
-- overstate), and ethanol (7 kcal/g, which sits in no macro field at all).
--
-- Two thresholds, both required. 12% relative catches the real disagreements;
-- the absolute 5 kcal floor keeps every 6-kcal diet drink from flooding the
-- list on rounding alone.
--
-- LEFT JOIN, and this one matters most. The gate has to work on an UNCURATED
-- database — that is its whole job, since an item is ruled on here before it
-- gets menu_eligible. An INNER join would empty the view today, when not one
-- curation row exists. COALESCE keeps the ordering column non-NULL.
--
-- This is NOT a CHECK constraint. Some items land here and are still correct
-- (sugar-free products). An item that appears here does not get menu_eligible
-- until a human has ruled on it — a curation decision, not an automatic block.
CREATE VIEW v_kcal_outliers AS
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


-- ============================================================================
--  6. Grants — seven views now, not five
-- ============================================================================

-- A view carries no RLS of its own and runs as its owner, so a view granted to
-- anon reads and writes straight past the policies on the tables underneath
-- it. Supabase grants anon full DML on new objects by default, and a
-- single-table view like v_pool_depth is auto-updatable — which made DELETE
-- through the view a live path into the base table with the public anon key.
--
-- security_invoker makes each view honour the caller's own RLS; the
-- REVOKE/GRANT pair leaves nothing but SELECT. v_menu_foods and
-- v_curation_orphans join the list, taking the array from five to seven.
DO $$
DECLARE v text;
BEGIN
  FOREACH v IN ARRAY ARRAY[
      'v_eligible_missing_tags',
      'v_recipe_unreviewed_components',
      'v_recipe_inherited_allergens',
      'v_pool_depth',
      'v_kcal_outliers',
      'v_menu_foods',
      'v_curation_orphans'
  ] LOOP
      EXECUTE format('ALTER VIEW %I SET (security_invoker = on)', v);
      EXECUTE format('REVOKE ALL ON %I FROM anon, authenticated', v);
      EXECUTE format('GRANT SELECT ON %I TO anon, authenticated', v);
  END LOOP;
END $$;


-- ============================================================================
--  7. RLS on food_curation — same shape as foods
-- ============================================================================

-- Public reference data. Public to read is not public to write, and on
-- Supabase anon holds full DML GRANTs by default, so RLS is what actually
-- blocks writes. The name follows the read_* policies already on the five
-- food tables in production.
ALTER TABLE food_curation ENABLE ROW LEVEL SECURITY;

CREATE POLICY read_curation ON food_curation
    FOR SELECT TO anon, authenticated
    USING (true);

COMMIT;

-- ============================================================================
--  Verification — run after COMMIT.
--
--    SELECT count(*) FROM v_curation_orphans;   -- must be 0, always
--    SELECT count(*) FROM v_menu_foods;         -- 0 until curation starts
--    SELECT count(*) FROM v_kcal_outliers;      -- unchanged by this migration
--
--  And the one that actually proves it: insert a fully tagged curation row,
--  run 04_transform.py end to end, and confirm the row is still there.
-- ============================================================================
