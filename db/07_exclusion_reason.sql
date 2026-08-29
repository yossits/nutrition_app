-- ============================================================================
--  07_exclusion_reason.sql — an exclusion becomes a fact that explains itself
--
--  Why: food_curation was empty, so "not fit for a menu" and "nobody has looked
--  at this yet" were the same state — the absence of a row. That is the same
--  failure the schema already refuses elsewhere: allergens = '{}' (reviewed and
--  clean) is not allergens_reviewed_at IS NULL (not reviewed), and kcal = NULL
--  is not kcal = 0. A blanket exclusion has to be written down, with its reason,
--  or the next person reads it as work not yet done.
--
--  The first case is the FFQ block: 116 food-frequency-questionnaire categories
--  that carry valid nutrition values and pass every automatic check, but are
--  survey buckets rather than food anyone can buy. Filtering them in a query
--  would work once and be forgotten; a row with a reason survives.
--
--  Run once against production, after 06_split_curation.sql.
--  01_food_db_schema.sql carries the same column for a database built from
--  scratch — the two files must never disagree, or a rebuild silently drops it.
-- ============================================================================

BEGIN;

-- An enum and not free text. Every closed vocabulary in this schema is an enum
-- (food_category, kosher_type, source_kind); every genuinely open field is text
-- (curated_by). Free text across 116 rows invites 116 spellings of "FFQ" and
-- cannot be counted. A new reason therefore costs a migration — which is the
-- point, not the price: it forces the reason through docs/decisions.md before
-- it reaches the data.
--
-- One value, because one reason has been decided. Seeding plausible future
-- values (kcal_outlier, not_purchasable) would put undecided policy into the
-- schema.
CREATE TYPE exclusion_reason AS ENUM (
    'ffq'       -- a food-frequency-questionnaire category, not a purchasable food
);

ALTER TABLE food_curation
    ADD COLUMN excluded_reason exclusion_reason;

-- One-directional on purpose. "Has a reason ⇒ not eligible" is a real
-- invariant. The converse — "not eligible ⇒ must have a reason" — would break
-- ordinary curation, where a row exists with partial tagging and is simply not
-- eligible yet.
ALTER TABLE food_curation
    ADD CONSTRAINT excluded_reason_requires_ineligible
        CHECK (excluded_reason IS NULL OR NOT menu_eligible);


-- ============================================================================
--  The FFQ exclusion itself
-- ============================================================================

-- The discriminant is class_code, not the name. The FFQ block occupies
-- 90000001–90000116 contiguously, which is structural and survives a rewording
-- in the Ministry of Health file. Two independent discriminants were measured
-- against production on 29.08.2026 and agreed exactly, with zero rows on either
-- side of the disagreement:
--
--     class_code ~ '^9000[0-9]{4}$'   116
--     name_he LIKE 'FFQ%'             116   (name_en agrees)
--     makor IS NULL                   114   <- biased, misses 10115 and 10116
--
-- makor is the trap: two of the 116 carry makor = 5, so the obvious "these rows
-- have no makor" test silently leaves two survey buckets curatable. One of them
-- is olive oil with za'atar — a fat, in the category the narrow track is
-- bottlenecked on.
--
-- The rest of class group 9 (533 sweets and drinks) is not caught: water is
-- 94000039, which is 9% but not 9000xxxx.
INSERT INTO food_curation (source_code, menu_eligible, excluded_reason,
                           curated_by, curated_at)
SELECT f.source_code, false, 'ffq', 'block-1', now()
FROM foods f
WHERE f.class_code ~ '^9000[0-9]{4}$'
ON CONFLICT (source_code) DO NOTHING;

-- Stop condition, not a report. The cross-check has to run inside the same
-- transaction that writes the rows, or it verifies a state that has already
-- been committed.
DO $$
DECLARE
    n_by_class integer;
    n_by_name  integer;
    n_written  integer;
BEGIN
    SELECT count(*) INTO n_by_class FROM foods WHERE class_code ~ '^9000[0-9]{4}$';
    SELECT count(*) INTO n_by_name  FROM foods WHERE name_he LIKE 'FFQ%';
    SELECT count(*) INTO n_written  FROM food_curation WHERE excluded_reason = 'ffq';

    IF n_by_class <> n_by_name OR n_written <> n_by_class THEN
        RAISE EXCEPTION
            'FFQ discriminants disagree: by class_code %, by name %, rows written %',
            n_by_class, n_by_name, n_written;
    END IF;

    IF EXISTS (SELECT 1 FROM v_curation_orphans) THEN
        RAISE EXCEPTION 'v_curation_orphans is not empty';
    END IF;
END $$;

COMMIT;
