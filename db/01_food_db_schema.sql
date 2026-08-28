-- ============================================================================
--  Food database — target schema
--  Source: Israeli National Nutrient Database (Tzameret), Ministry of Health,
--          data.gov.il
--  Target: Postgres 15+ / Supabase
--
--  Principle: the src_* tables ingest the files exactly as they are (jsonb),
--             with no constraints. Transforming into foods is a separate,
--             re-runnable step. That way a change in the source files does
--             not force a schema change.
--
--  ⚠ The source column names had not been seen when this was written. The
--    loader is what maps raw->>'...' onto fields; the schema does not
--    depend on them.
-- ============================================================================

-- Outside the transaction: if the role lacks the privilege (managed Supabase),
-- enable it from the dashboard instead
CREATE EXTENSION IF NOT EXISTS pg_trgm;

BEGIN;

-- ------------------------------------------------------------------- Types --

CREATE TYPE kosher_type   AS ENUM ('meat', 'dairy', 'parve');
CREATE TYPE food_category AS ENUM ('protein', 'carb', 'veg', 'fat', 'fruit', 'drink');
CREATE TYPE source_kind   AS ENUM ('ingredient', 'recipe', 'industry');


-- ============================================================================
--  1. Staging layer — the files exactly as downloaded
-- ============================================================================

-- File 1: the ingredient and recipe list, nutrition values per 100 g
CREATE TABLE src_foods (
    row_num int PRIMARY KEY,
    code    text,
    raw     jsonb NOT NULL
);
CREATE INDEX src_foods_code_idx ON src_foods (code);

-- File 2: recipe composition — which ingredient, and how much of it
CREATE TABLE src_recipe_components (
    row_num        int PRIMARY KEY,
    recipe_code    text,
    component_code text,
    mida_code      text,
    amount         numeric,
    raw            jsonb NOT NULL
);
CREATE INDEX src_recipe_components_recipe_idx ON src_recipe_components (recipe_code);

-- File 3: serving weights / unit sizes
CREATE TABLE src_servings (
    row_num   int PRIMARY KEY,
    code      text,
    mida_code text,
    grams     numeric,
    raw       jsonb NOT NULL
);
CREATE INDEX src_servings_code_idx ON src_servings (code);

-- File 4: the measurement-unit key — decodes Mida
CREATE TABLE src_mida (
    mida_code text PRIMARY KEY,
    label_he  text,
    raw       jsonb NOT NULL
);


-- ============================================================================
--  2. Core layer
-- ============================================================================

-- The 74 nutrients. The macros sit denormalized on foods (the hot path);
-- everything else lives here, for search and enrichment.
CREATE TABLE nutrients (
    id      serial PRIMARY KEY,
    code    text UNIQUE NOT NULL,
    name_he text,
    name_en text,
    unit    text
);


CREATE TABLE foods (
    id          bigserial PRIMARY KEY,
    source_code text UNIQUE NOT NULL,           -- Code, from the source database
    class_code  text,                           -- smlmitzrach — classification code; leading digits = food group
    makor       smallint,                       -- makor as-is from the source. 7 values; decoded in the column dictionary
    source      source_kind,                    -- derived: 'recipe' if Code appears as a recipe in the composition
                                                -- file; ingredient/industry by decoded makor. NULL until then
    name_he     text NOT NULL,
    name_en     text,

    -- Values per 100 g ------------------------------------------------------
    -- Two calorie fields because the file's energy and the macro sum disagree by
    -- up to 24%, and the solver needs one number that its macro targets agree with.
    -- kcal is nullable on purpose: a derivation that never ran must read NULL, not
    -- a stale file value that looks fine. Derived in 04_transform.py, after
    -- food_nutrients — the ethanol term is read from there.
    kcal_source numeric,                             -- the file's value, as-is. Never overwritten
    kcal        numeric CHECK (kcal        >= 0),    -- derived: P*4 + F*9 + C*4 + fibre*2 + ethanol*7
    protein_g   numeric NOT NULL CHECK (protein_g >= 0),
    fat_g       numeric NOT NULL CHECK (fat_g     >= 0),
    carb_g      numeric NOT NULL CHECK (carb_g    >= 0),
    fiber_g     numeric,
    sugar_g     numeric,
    sat_fat_g   numeric,
    sodium_mg   numeric,

    -- Derived, not tagged ----------------------------------------------------
    -- The only non-source field left on foods. It is computed from the nine
    -- essential amino acids in 04_transform.py, so a rebuild is exactly what
    -- should reproduce it. Everything a human types lives on food_curation.
    complete    boolean NOT NULL DEFAULT false, -- all 9 essential amino acids

    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX foods_name_trgm_idx ON foods USING gin (name_he gin_trgm_ops);
-- Requires:  CREATE EXTENSION IF NOT EXISTS pg_trgm;


-- The hand-made layer. None of these fields exist in the source.
--
-- Why it is a separate table: 04_transform.py runs
--   TRUNCATE ... foods ... RESTART IDENTITY CASCADE
-- and rebuilds foods from src_*. That is correct for derived data and was
-- verified against production. It is fatal for data that was typed by hand —
-- one re-import after curation begins would erase the whole tagging effort.
-- foods now holds only what a rebuild can reproduce.
--
-- The key is source_code, not foods.id. RESTART IDENTITY renumbers foods.id on
-- every import, so curation keyed on the surrogate would come back pointing at
-- a different food — silently, with no error and no orphan.
--
-- Deliberately NO FOREIGN KEY to foods.
--   TRUNCATE ... CASCADE empties every table that references one on its list.
--   A FK here would CONDUCT the deletion, not prevent it — it would recreate
--   the exact failure this split exists to close, while looking like the
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

    -- The safety gate: eligible without tagging is a safety bug, not a data
    -- bug. A CHECK cannot span tables, which is why by_weight lives here and
    -- not on foods — whole_only_requires_a_unit reads both of them.
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

CREATE INDEX food_curation_eligible_idx  ON food_curation (category) WHERE menu_eligible;
CREATE INDEX food_curation_allergens_idx ON food_curation USING gin (allergens);
CREATE INDEX food_curation_tags_idx      ON food_curation USING gin (tags);


-- Serving units — this is what turns "170 g" into "בטטה וחצי"
CREATE TABLE food_servings (
    id              bigserial PRIMARY KEY,
    food_id         bigint NOT NULL REFERENCES foods(id) ON DELETE CASCADE,
    mida_code       text,
    label_he        text NOT NULL,              -- "גביע" · "פרוסה" · "כף"
    label_he_plural text,                       -- "גביעים" — not in the source, derived
    grams           numeric NOT NULL CHECK (grams > 0),
    is_default      boolean NOT NULL DEFAULT false,
    UNIQUE (food_id, label_he)
);

CREATE UNIQUE INDEX one_default_serving_per_food
    ON food_servings (food_id) WHERE is_default;


CREATE TABLE food_nutrients (
    food_id     bigint NOT NULL REFERENCES foods(id) ON DELETE CASCADE,
    nutrient_id int    NOT NULL REFERENCES nutrients(id),
    value       numeric NOT NULL,
    PRIMARY KEY (food_id, nutrient_id)
);


-- Recipe composition. This is what makes it possible to infer allergens
-- automatically for ~1,400 recipes instead of tagging them by hand.
CREATE TABLE food_recipe_components (
    recipe_id    bigint NOT NULL REFERENCES foods(id) ON DELETE CASCADE,
    component_id bigint NOT NULL REFERENCES foods(id),
    grams        numeric,
    PRIMARY KEY (recipe_id, component_id)
);


-- ============================================================================
--  3. Validators — spec §9.7 step 7, not optional
-- ============================================================================

-- The generator's input. INNER JOIN on purpose: a food with no curation row
-- cannot reach the prompt. That is the same rule the old `WHERE menu_eligible`
-- carried, now expressed by the join itself.
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


-- This is what replaces the foreign key food_curation deliberately does not
-- have. A curation row whose source_code is no longer in foods means an import
-- dropped an item out from under tagging work that still exists. Must return
-- 0 rows; 04_transform.py checks it as a stop condition and rolls the run back
-- if it does not.
CREATE VIEW v_curation_orphans AS
SELECT c.source_code, c.category, c.menu_eligible, c.curated_by, c.curated_at
FROM food_curation c
WHERE NOT EXISTS (SELECT 1 FROM foods f WHERE f.source_code = c.source_code);


-- Must return 0 rows before every release.
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


-- Pool depth by category. This is the metric curation is meant to move,
-- not the total count. Fat and protein are the bottleneck (17% / 20% at p10).
-- One table: every column it reads lives on food_curation.
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
-- This is NOT a CHECK constraint. Some items land here and are still correct
-- (sugar-free products). An item that appears here does not get menu_eligible
-- until a human has ruled on it — a curation decision, not an automatic block.
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


-- A view carries no RLS of its own and runs as its owner, so a view granted to
-- anon reads and writes straight past the policies on the tables underneath it.
-- Supabase grants anon full DML on new objects by default, and a single-table
-- view like v_pool_depth is auto-updatable — which made DELETE through the
-- view a live path into the base table with the public anon key.
--
-- security_invoker makes each view honour the caller's own RLS; the
-- REVOKE/GRANT pair leaves nothing but SELECT. This block must stay in this
-- file: applied to production only, the next run of the schema would recreate
-- all seven views wide open again.
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
--  4. Maintenance
-- ============================================================================

CREATE OR REPLACE FUNCTION touch_updated_at() RETURNS trigger AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER foods_touch_updated_at
    BEFORE UPDATE ON foods
    FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

CREATE TRIGGER food_curation_touch_updated_at
    BEFORE UPDATE ON food_curation
    FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

COMMIT;

-- ============================================================================
--  A note on RLS. The view grants above are in this file; the table policies
--  below are not — they were applied to production separately and are recorded
--  here so the gap is visible. What is in place there:
--
--    foods · food_servings · food_nutrients · food_recipe_components ·
--    nutrients · food_curation
--                       RLS on, one SELECT policy for anon + authenticated,
--                       named read_<table>. Public reference data — public to
--                       read is not public to write, and on Supabase anon
--                       holds full DML GRANTs by default, so RLS is what
--                       actually blocks writes. food_curation's policy is
--                       created by db/06_split_curation.sql, the same way the
--                       other five were applied separately.
--
--    src_foods · src_recipe_components · src_servings · src_mida
--                       RLS on, no policy at all — service_role only. This is
--                       the layer the import scripts TRUNCATE.
--
--    the v_* views      Views carry no RLS of their own. They run as their
--                       owner, so a view granted to anon is a hole straight
--                       past the policies above. Set security_invoker = on and
--                       granted SELECT only — by the block in section 3, so a
--                       rebuild cannot reopen them.
--
--  Verified against production 28.08.2026: no view reads from any src_* table,
--  so security_invoker cannot silently empty one for anon.
-- ============================================================================
