-- Block 3ז4ג — the price column leaves the database.
-- Decision of 30.08.2026, see docs/decisions.md: price is dropped from the
-- product. The code side went first, in 3ז4ב: spike/filters.py stopped reading
-- it and spike/foods.py stopped carrying it. This is the schema side.
--
-- Three things depend on the column, measured in 3ז4א and re-measured at the
-- head of this block, and there is no fourth: the CHECK constraint
-- eligible_requires_menu_fields, the CHECK constraint food_curation_price_check,
-- and the view v_menu_foods. No function, no index, no policy expression and no
-- trigger references it. food_curation_touch_updated_at is a BEFORE UPDATE
-- trigger that only stamps updated_at; it is not column-scoped and it does not
-- fire on DDL.
--
-- Order matters. The view holds a rewrite-rule dependency on the column and
-- eligible_requires_menu_fields names it, so both have to go before the column
-- can be dropped. food_curation_price_check goes with the column automatically.
--
-- Rebuilding the view is the risk in this file. Two properties do not live in
-- the SELECT body. WITH (security_invoker = on), without which the view would
-- read food_curation as its owner and bypass row level security. And the
-- grants: Supabase hands anon and authenticated full DML on every new object,
-- so the rebuilt view comes back wider than the one it replaced unless the
-- REVOKE/GRANT pair from 01 and 06 is repeated here. Both are restored below
-- and asserted afterwards; V7 is what caught the second one.
--
-- 28 rows carried a price. Only three survive anywhere else in the repository:
-- 500 and 494 in db/12_cottage_swap.sql, and 493 in docs/decisions.md.
--
-- The 28 values, recorded here because after this runs they exist nowhere
-- else in git. price_backup.csv in the block scratch directory is one file
-- on one machine; this is the durable copy. source_code = price:
--   1267 = 2   1347 = 2   1854 = 3   1873 = 1
--   1898 = 1   2659 = 1   2721 = 1   3223 = 2
--   3459 = 1   3663 = 1   3793 = 1   3807 = 1
--   3837 = 1   4279 = 1   4387 = 2   4443 = 2
--   4446 = 1    493 = 1    494 = 1    500 = 1
--    805 = 2   8221 = 2   8348 = 1   8608 = 2
--   8712 = 2   8840 = 1    944 = 2   9793 = 1

BEGIN;

CREATE TEMP TABLE _pre ON COMMIT DROP AS
  SELECT source_code, updated_at, menu_eligible, category, kosher,
         quality, supp, prep, by_weight, whole_only, max_g,
         excluded_reason, curated_by, curated_at
    FROM food_curation;

-- 1 --------------------------------------------------------------- the view
DROP VIEW public.v_menu_foods;

-- 2 ------------------------------------------------- the constraint naming it
ALTER TABLE public.food_curation DROP CONSTRAINT eligible_requires_menu_fields;

-- 3 ------------------------------------------- the same constraint, minus price
ALTER TABLE public.food_curation ADD CONSTRAINT eligible_requires_menu_fields
    CHECK (menu_eligible = false OR (prep IS NOT NULL AND by_weight IS NOT NULL));

-- 4 ------------------------------------------------------------- the column
-- food_curation_price_check depends on the column and is dropped with it.
ALTER TABLE public.food_curation DROP COLUMN price;

-- 5 -------------------------------------------------- the view, without price
CREATE VIEW public.v_menu_foods WITH (security_invoker = on) AS
 SELECT f.id,
    f.source_code,
    f.class_code,
    f.makor,
    f.source,
    f.name_he,
    f.name_en,
    f.kcal_source,
    f.kcal,
    f.protein_g,
    f.fat_g,
    f.carb_g,
    f.fiber_g,
    f.sugar_g,
    f.sat_fat_g,
    f.sodium_mg,
    f.complete,
    c.category,
    c.kosher,
    c.allergens,
    c.allergens_reviewed_at,
    c.tags,
    c.quality,
    c.supp,
    c.prep,
    c.by_weight,
    c.whole_only,
    c.max_g,
    c.curated_by,
    c.curated_at
   FROM foods f
     JOIN food_curation c ON c.source_code = f.source_code
  WHERE c.menu_eligible;

-- Supabase's default privileges hand anon and authenticated full DML on every
-- newly created object, so a bare CREATE VIEW comes back WIDER than the view it
-- replaced: anon would hold INSERT, UPDATE, DELETE and TRUNCATE on a view whose
-- predecessor granted it SELECT alone. This is the same REVOKE/GRANT pair that
-- 01_food_db_schema.sql and 06_split_curation.sql apply to all seven views,
-- narrowed to the one this file rebuilds. The first rehearsal of this migration
-- failed on exactly this, in V7.
REVOKE ALL   ON public.v_menu_foods FROM anon, authenticated;
GRANT SELECT ON public.v_menu_foods TO anon, authenticated;
GRANT ALL    ON public.v_menu_foods TO service_role;

-- Raw output for the record, before the assertions
SELECT count(*) AS v_menu_foods_rows FROM v_menu_foods;

-- V1 — the nine canonical metrics are untouched
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
  IF tot<>146 OR el<>27 OR p<>11 OR f<>8 OR c<>4 OR v<>4
     OR vm<>27 OR mt<>0 OR orph<>0 THEN
    RAISE EXCEPTION 'V1 failed: tot=% el=% p=% f=% c=% v=% view=% tags=% orph=%',
      tot, el, p, f, c, v, vm, mt, orph;
  END IF;
END $$;

-- V2 — the column is gone from the table and from the view
DO $$
DECLARE n int;
BEGIN
  SELECT count(*) INTO n FROM information_schema.columns
   WHERE table_schema='public' AND table_name IN ('food_curation','v_menu_foods')
     AND column_name='price';
  IF n <> 0 THEN RAISE EXCEPTION 'V2 failed: % price columns remain', n; END IF;
END $$;

-- V3 — the rebuilt constraint says exactly what it should, and nothing about price
DO $$
DECLARE d text;
BEGIN
  SELECT pg_get_constraintdef(oid) INTO d FROM pg_constraint
   WHERE conrelid='public.food_curation'::regclass
     AND conname='eligible_requires_menu_fields';
  IF d IS DISTINCT FROM
     'CHECK (((menu_eligible = false) OR ((prep IS NOT NULL) AND (by_weight IS NOT NULL))))'
  THEN RAISE EXCEPTION 'V3 failed: %', d; END IF;
END $$;

-- V4 — nine constraints, and the eight untouched ones are byte-identical
DO $$
DECLARE n int; got text; want text;
BEGIN
  SELECT count(*) INTO n FROM pg_constraint
   WHERE conrelid='public.food_curation'::regclass;
  IF n <> 9 THEN RAISE EXCEPTION 'V4 failed: % constraints, expected 9', n; END IF;

  SELECT string_agg(conname || '=' || pg_get_constraintdef(oid), E'\n' ORDER BY conname)
    INTO got FROM pg_constraint
   WHERE conrelid='public.food_curation'::regclass
     AND conname <> 'eligible_requires_menu_fields';

  want :=
    'eligible_protein_requires_quality=CHECK (((NOT (menu_eligible AND (category = ''protein''::food_category))) OR (quality IS NOT NULL)))' || E'\n' ||
    'eligible_requires_safety_tagging=CHECK (((NOT menu_eligible) OR ((category IS NOT NULL) AND (kosher IS NOT NULL) AND (allergens_reviewed_at IS NOT NULL))))' || E'\n' ||
    'excluded_reason_requires_ineligible=CHECK (((excluded_reason IS NULL) OR (NOT menu_eligible)))' || E'\n' ||
    'food_curation_max_g_check=CHECK ((max_g > (0)::numeric))' || E'\n' ||
    'food_curation_pkey=PRIMARY KEY (source_code)' || E'\n' ||
    'food_curation_prep_check=CHECK (((prep >= 0) AND (prep <= 2)))' || E'\n' ||
    'food_curation_quality_check=CHECK (((quality >= 1) AND (quality <= 3)))' || E'\n' ||
    'whole_only_requires_a_unit=CHECK (((NOT whole_only) OR (NOT by_weight)))';

  IF got IS DISTINCT FROM want THEN
    RAISE EXCEPTION 'V4 failed: the other constraints changed%', E'\n' || got;
  END IF;
END $$;

-- V5 — the view: no price in the definition, and exactly the 30 expected columns in order
DO $$
DECLARE d text; cols text;
BEGIN
  SELECT pg_get_viewdef('public.v_menu_foods'::regclass, true) INTO d;
  IF d ILIKE '%price%' THEN RAISE EXCEPTION 'V5 failed: the view still mentions price'; END IF;

  SELECT string_agg(column_name, ',' ORDER BY ordinal_position) INTO cols
    FROM information_schema.columns
   WHERE table_schema='public' AND table_name='v_menu_foods';

  IF cols IS DISTINCT FROM
     'id,source_code,class_code,makor,source,name_he,name_en,kcal_source,kcal,'
     'protein_g,fat_g,carb_g,fiber_g,sugar_g,sat_fat_g,sodium_mg,complete,'
     'category,kosher,allergens,allergens_reviewed_at,tags,quality,supp,prep,'
     'by_weight,whole_only,max_g,curated_by,curated_at'
  THEN RAISE EXCEPTION 'V5 failed: columns are %', cols; END IF;
END $$;

-- V6 — security_invoker survived the rebuild
DO $$
DECLARE o text[];
BEGIN
  SELECT reloptions INTO o FROM pg_class WHERE oid='public.v_menu_foods'::regclass;
  IF o IS DISTINCT FROM ARRAY['security_invoker=on'] THEN
    RAISE EXCEPTION 'V6 failed: reloptions = %', o;
  END IF;
END $$;

-- V7 — the grants are back, all sixteen rows
DO $$
DECLARE got text; want text;
BEGIN
  SELECT string_agg(grantee || ':' || privilege_type, ',' ORDER BY grantee, privilege_type)
    INTO got FROM information_schema.role_table_grants
   WHERE table_schema='public' AND table_name='v_menu_foods';
  want := 'anon:SELECT,authenticated:SELECT,'
       || 'postgres:DELETE,postgres:INSERT,postgres:REFERENCES,postgres:SELECT,'
       || 'postgres:TRIGGER,postgres:TRUNCATE,postgres:UPDATE,'
       || 'service_role:DELETE,service_role:INSERT,service_role:REFERENCES,'
       || 'service_role:SELECT,service_role:TRIGGER,service_role:TRUNCATE,service_role:UPDATE';
  IF got IS DISTINCT FROM want THEN
    RAISE EXCEPTION 'V7 failed: grants are %', got;
  END IF;
END $$;

-- V8 — owner, and row level security on the table underneath
DO $$
DECLARE o text; rls boolean; pol int;
BEGIN
  SELECT pg_get_userbyid(relowner) INTO o FROM pg_class WHERE oid='public.v_menu_foods'::regclass;
  IF o <> 'postgres' THEN RAISE EXCEPTION 'V8 failed: view owner is %', o; END IF;
  SELECT relrowsecurity INTO rls FROM pg_class WHERE oid='public.food_curation'::regclass;
  SELECT count(*) INTO pol FROM pg_policy WHERE polrelid='public.food_curation'::regclass;
  IF rls IS NOT true OR pol <> 1 THEN
    RAISE EXCEPTION 'V8 failed: rls=% policies=%', rls, pol;
  END IF;
END $$;

-- V9 — the touch_updated_at trigger is still attached
DO $$
DECLARE n int;
BEGIN
  SELECT count(*) INTO n FROM pg_trigger
   WHERE tgrelid='public.food_curation'::regclass AND NOT tgisinternal
     AND tgname='food_curation_touch_updated_at';
  IF n <> 1 THEN RAISE EXCEPTION 'V9 failed: trigger count %', n; END IF;
END $$;

-- V10 — blast radius: not one curation row changed
DO $$
DECLARE touched int; missing int; added int;
BEGIN
  SELECT count(*) INTO touched
    FROM food_curation c JOIN _pre p USING (source_code)
   WHERE (c.updated_at, c.menu_eligible, c.category, c.kosher, c.quality, c.supp,
          c.prep, c.by_weight, c.whole_only, c.max_g, c.excluded_reason,
          c.curated_by, c.curated_at)
      IS DISTINCT FROM
         (p.updated_at, p.menu_eligible, p.category, p.kosher, p.quality, p.supp,
          p.prep, p.by_weight, p.whole_only, p.max_g, p.excluded_reason,
          p.curated_by, p.curated_at);
  SELECT count(*) INTO missing FROM _pre p
    LEFT JOIN food_curation c USING (source_code) WHERE c.source_code IS NULL;
  SELECT count(*) INTO added FROM food_curation c
    LEFT JOIN _pre p USING (source_code) WHERE p.source_code IS NULL;
  IF touched <> 0 OR missing <> 0 OR added <> 0 THEN
    RAISE EXCEPTION 'V10 failed: touched=% missing=% added=%', touched, missing, added;
  END IF;
END $$;

COMMIT;
