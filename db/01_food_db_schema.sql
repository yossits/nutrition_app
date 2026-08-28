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
    kcal      numeric NOT NULL CHECK (kcal      >= 0),
    protein_g numeric NOT NULL CHECK (protein_g >= 0),
    fat_g     numeric NOT NULL CHECK (fat_g     >= 0),
    carb_g    numeric NOT NULL CHECK (carb_g    >= 0),
    fiber_g   numeric,
    sugar_g   numeric,
    sat_fat_g numeric,
    sodium_mg numeric,

    -- Curation fields — none of these exist in the source --------------------
    category              food_category,
    kosher                kosher_type,
    allergens             text[] NOT NULL DEFAULT '{}',
    allergens_reviewed_at timestamptz,          -- '{}' = reviewed and clean · NULL here = not reviewed
    tags                  text[] NOT NULL DEFAULT '{}',   -- vegan · vegetarian · ...
    quality               smallint CHECK (quality BETWEEN 1 AND 3),
    complete              boolean NOT NULL DEFAULT false, -- all 9 essential amino acids
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

    -- The safety gate: eligible without tagging is a safety bug, not a data bug
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

CREATE INDEX foods_eligible_idx ON foods (category) WHERE menu_eligible;
CREATE INDEX foods_allergens_idx ON foods USING gin (allergens);
CREATE INDEX foods_tags_idx      ON foods USING gin (tags);
CREATE INDEX foods_name_trgm_idx ON foods USING gin (name_he gin_trgm_ops);
-- Requires:  CREATE EXTENSION IF NOT EXISTS pg_trgm;


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

-- Must return 0 rows before every release.
CREATE VIEW v_eligible_missing_tags AS
SELECT id, source_code, name_he,
       category              IS NULL AS no_category,
       kosher                IS NULL AS no_kosher,
       allergens_reviewed_at IS NULL AS no_allergen_review,
       (category = 'protein' AND quality IS NULL) AS no_quality
FROM foods
WHERE menu_eligible
  AND (category IS NULL
       OR kosher IS NULL
       OR allergens_reviewed_at IS NULL
       OR (category = 'protein' AND quality IS NULL));


-- A curated recipe with an unreviewed component = an allergen that can slip
-- under the radar.
CREATE VIEW v_recipe_unreviewed_components AS
SELECT r.id AS recipe_id, r.name_he AS recipe, c.id AS component_id, c.name_he AS component
FROM foods r
JOIN food_recipe_components rc ON rc.recipe_id = r.id
JOIN foods c ON c.id = rc.component_id
WHERE r.menu_eligible
  AND c.allergens_reviewed_at IS NULL;


-- Allergens a recipe inherits from its components. A source of tagging
-- suggestions, not a substitute for human sign-off.
CREATE VIEW v_recipe_inherited_allergens AS
SELECT rc.recipe_id, array_agg(DISTINCT a ORDER BY a) AS inherited
FROM food_recipe_components rc
JOIN foods c ON c.id = rc.component_id
CROSS JOIN LATERAL unnest(c.allergens) AS a
GROUP BY rc.recipe_id;


-- Pool depth by category. This is the metric curation is meant to move,
-- not the total count. Fat and protein are the bottleneck (17% / 20% at p10).
CREATE VIEW v_pool_depth AS
SELECT category,
       count(*)                                                   AS eligible,
       count(*) FILTER (WHERE allergens = '{}')                   AS allergen_free,
       count(*) FILTER (WHERE 'vegan' = ANY(tags))                AS vegan,
       count(*) FILTER (WHERE kosher = 'parve')                   AS parve,
       count(*) FILTER (WHERE prep = 0)                           AS no_prep
FROM foods
WHERE menu_eligible
GROUP BY category
ORDER BY category;


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

COMMIT;

-- ============================================================================
--  A note on RLS: foods · food_servings · food_nutrients · nutrients are
--  public reference data, with no personal information. RLS is enabled only
--  on the tables in spec §13.3 that carry user data.
-- ============================================================================
