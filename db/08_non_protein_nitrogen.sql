-- ============================================================================
--  08_non_protein_nitrogen.sql — two items excluded for carrying nitrogen
--  that is not protein
--
--  4498 monosodium glutamate and 4839 instant tea powder both declare a large
--  protein figure with zero fat. That figure is an artefact of the Kjeldahl
--  conversion, which measures nitrogen and multiplies by a fixed factor: any
--  nitrogen-bearing compound reads as protein, whether or not it is one.
--
--  Why they cannot simply be left alone. 46.8 g of "protein" at zero fat is the
--  ideal item for every leanness ranking the solver runs — it wins on the exact
--  metric the sampler sorts by, and it is a seasoning. This is the same trap
--  the protein powders created (spec/05-food-db.md §5.4), arriving from a
--  different direction: there the ratio was real and the food was a supplement,
--  here the ratio is not real at all.
--
--  Run once against production, after 07_exclusion_reason.sql.
--  01_food_db_schema.sql carries the same enum value for a database built from
--  scratch — the two files must never disagree.
--
--  NOTE ON TRANSACTIONS. ALTER TYPE ... ADD VALUE may run inside a transaction
--  on Postgres 12+, but the new label cannot be USED until that transaction has
--  committed. The two steps below are therefore deliberately not wrapped in a
--  single BEGIN/COMMIT. Run step 1, then step 2.
-- ============================================================================

-- ---------------------------------------------------------------- step 1 --
ALTER TYPE exclusion_reason ADD VALUE IF NOT EXISTS 'non_protein_nitrogen';


-- ---------------------------------------------------------------- step 2 --
BEGIN;

INSERT INTO food_curation (source_code, menu_eligible, excluded_reason,
                           curated_by, curated_at)
VALUES ('4498', false, 'non_protein_nitrogen', 'block-1b', now()),   -- MSG
       ('4839', false, 'non_protein_nitrogen', 'block-1b', now())    -- instant tea powder
ON CONFLICT (source_code) DO NOTHING;

-- Stop condition, inside the writing transaction. A count checked after the
-- commit reports damage that is already done.
DO $$
DECLARE
    n_total integer;
    n_npn   integer;
    n_elig  integer;
BEGIN
    SELECT count(*) INTO n_total FROM food_curation;
    SELECT count(*) INTO n_npn   FROM food_curation WHERE excluded_reason = 'non_protein_nitrogen';
    SELECT count(*) INTO n_elig  FROM food_curation WHERE menu_eligible;

    IF n_total <> 118 OR n_npn <> 2 OR n_elig <> 0 THEN
        RAISE EXCEPTION
            'unexpected state: food_curation %, non_protein_nitrogen %, menu_eligible %',
            n_total, n_npn, n_elig;
    END IF;

    IF EXISTS (SELECT 1 FROM v_curation_orphans) THEN
        RAISE EXCEPTION 'v_curation_orphans is not empty';
    END IF;
END $$;

COMMIT;
