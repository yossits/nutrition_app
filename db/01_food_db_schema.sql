-- ============================================================================
--  מאגר המזון — סכימת יעד
--  מקור: מאגר התזונה הלאומי הישראלי (צמרת), משרד הבריאות, data.gov.il
--  יעד:   Postgres 15+ / Supabase
--
--  עיקרון: טבלאות src_* קולטות את הקבצים כמו שהם (jsonb), בלי אילוצים.
--          הטרנספורמציה ל-foods היא צעד נפרד ובר-הרצה-חוזרת.
--          כך שינוי בקבצי המקור לא דורש שינוי סכימה.
--
--  ⚠ שמות העמודות בקבצי המקור טרם נראו. ה-loader הוא זה שממפה
--    raw->>'...' לשדות; הסכימה עצמה לא תלויה בהם.
-- ============================================================================

BEGIN;

-- ---------------------------------------------------------------- טיפוסים --

CREATE TYPE kosher_type   AS ENUM ('meat', 'dairy', 'parve');
CREATE TYPE food_category AS ENUM ('protein', 'carb', 'veg', 'fat', 'fruit', 'drink');
CREATE TYPE source_kind   AS ENUM ('ingredient', 'recipe', 'industry');


-- ============================================================================
--  1. שכבת קליטה (staging) — הקבצים כפי שהורדו
-- ============================================================================

-- קובץ 1: רשימת המצרכים והמתכונים, ערכי תזונה ל-100 ג'
CREATE TABLE src_foods (
    row_num int PRIMARY KEY,
    code    text,
    raw     jsonb NOT NULL
);
CREATE INDEX src_foods_code_idx ON src_foods (code);

-- קובץ 2: הרכב המתכונים — איזה מצרך ובאיזו כמות
CREATE TABLE src_recipe_components (
    row_num        int PRIMARY KEY,
    recipe_code    text,
    component_code text,
    mida_code      text,
    amount         numeric,
    raw            jsonb NOT NULL
);
CREATE INDEX src_recipe_components_recipe_idx ON src_recipe_components (recipe_code);

-- קובץ 3: משקלי מנות / גדלי יחידה
CREATE TABLE src_servings (
    row_num   int PRIMARY KEY,
    code      text,
    mida_code text,
    grams     numeric,
    raw       jsonb NOT NULL
);
CREATE INDEX src_servings_code_idx ON src_servings (code);

-- קובץ 4: מפתח יחידות המידה — פענוח Mida
CREATE TABLE src_mida (
    mida_code text PRIMARY KEY,
    label_he  text,
    raw       jsonb NOT NULL
);


-- ============================================================================
--  2. שכבת ליבה
-- ============================================================================

-- 74 רכיבי התזונה. המאקרו יושב denormalized על foods (המסלול החם);
-- כל השאר כאן, לחיפוש והעשרה.
CREATE TABLE nutrients (
    id      serial PRIMARY KEY,
    code    text UNIQUE NOT NULL,
    name_he text,
    name_en text,
    unit    text
);


CREATE TABLE foods (
    id          bigserial PRIMARY KEY,
    source_code text UNIQUE NOT NULL,           -- CODE מהמאגר
    source      source_kind NOT NULL,
    name_he     text NOT NULL,
    name_en     text,

    -- ערכים ל-100 גרם -----------------------------------------------------
    kcal      numeric NOT NULL CHECK (kcal      >= 0),
    protein_g numeric NOT NULL CHECK (protein_g >= 0),
    fat_g     numeric NOT NULL CHECK (fat_g     >= 0),
    carb_g    numeric NOT NULL CHECK (carb_g    >= 0),
    fiber_g   numeric,
    sugar_g   numeric,
    sat_fat_g numeric,
    sodium_mg numeric,

    -- שדות אצירה — אף אחד מהם לא קיים במקור --------------------------------
    category              food_category,
    kosher                kosher_type,
    allergens             text[] NOT NULL DEFAULT '{}',
    allergens_reviewed_at timestamptz,          -- '{}' = נבדק ונקי · NULL כאן = לא נבדק
    tags                  text[] NOT NULL DEFAULT '{}',   -- vegan · vegetarian · ...
    quality               smallint CHECK (quality BETWEEN 1 AND 3),
    complete              boolean NOT NULL DEFAULT false, -- 9 חומצות אמינו חיוניות
    supp                  boolean NOT NULL DEFAULT false, -- תוסף (אבקת חלבון וכו')
    prep                  smallint CHECK (prep  BETWEEN 0 AND 2),
    price                 smallint CHECK (price BETWEEN 1 AND 3),

    -- מדיניות מנות ---------------------------------------------------------
    by_weight  boolean NOT NULL DEFAULT true,   -- נמדד בגרמים
    whole_only boolean NOT NULL DEFAULT false,  -- אין חצי ביצה
    max_g      numeric CHECK (max_g > 0),       -- תקרה נגד 400 ג' אבוקדו

    menu_eligible boolean NOT NULL DEFAULT false,

    curated_by text,
    curated_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),

    -- שער הבטיחות: אצירה בלי תיוג היא באג בטיחותי, לא באג נתונים ------------
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
-- דורש:  CREATE EXTENSION IF NOT EXISTS pg_trgm;


-- יחידות הגשה — זה מה שהופך "170 ג'" ל"בטטה וחצי"
CREATE TABLE food_servings (
    id              bigserial PRIMARY KEY,
    food_id         bigint NOT NULL REFERENCES foods(id) ON DELETE CASCADE,
    mida_code       text,
    label_he        text NOT NULL,              -- "גביע" · "פרוסה" · "כף"
    label_he_plural text,                       -- "גביעים" — לא קיים במקור, נגזר
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


-- הרכב המתכונים. זה מה שמאפשר להסיק אלרגנים אוטומטית ל-~1,400 מתכונים
-- במקום לתייג אותם ביד.
CREATE TABLE food_recipe_components (
    recipe_id    bigint NOT NULL REFERENCES foods(id) ON DELETE CASCADE,
    component_id bigint NOT NULL REFERENCES foods(id),
    grams        numeric,
    PRIMARY KEY (recipe_id, component_id)
);


-- ============================================================================
--  3. ולידטורים — סעיף 9.7 שלב 7, לא אופציונלי
-- ============================================================================

-- חייב להחזיר 0 שורות לפני כל שחרור.
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


-- מתכון מובחר שרכיב שלו לא נבדק לאלרגנים = אלרגן שעלול לעבור מתחת לרדאר.
CREATE VIEW v_recipe_unreviewed_components AS
SELECT r.id AS recipe_id, r.name_he AS recipe, c.id AS component_id, c.name_he AS component
FROM foods r
JOIN food_recipe_components rc ON rc.recipe_id = r.id
JOIN foods c ON c.id = rc.component_id
WHERE r.menu_eligible
  AND c.allergens_reviewed_at IS NULL;


-- אלרגנים שמתכון יורש מרכיביו. מקור ההצעה לתיוג, לא תחליף לאישור אנושי.
CREATE VIEW v_recipe_inherited_allergens AS
SELECT rc.recipe_id, array_agg(DISTINCT a ORDER BY a) AS inherited
FROM food_recipe_components rc
JOIN foods c ON c.id = rc.component_id
CROSS JOIN LATERAL unnest(c.allergens) AS a
GROUP BY rc.recipe_id;


-- עומק המאגר לפי קטגוריה. זה המדד שהאצירה אמורה להזיז,
-- לא המספר הכולל. שומן וחלבון הם הצוואר הצר (17% / 20% באחוזון 10).
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
--  4. תחזוקה
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
--  הערה על RLS: foods · food_servings · food_nutrients · nutrients הם
--  נתוני ייחוס ציבוריים, בלי מידע אישי. RLS מופעל רק על הטבלאות
--  שבסעיף 13.3 שנושאות מידע משתמש.
-- ============================================================================
