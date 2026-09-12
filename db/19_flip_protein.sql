-- Block 6ח-ג — protein allergens: 94 tagged protein rows are reviewed for
-- allergens and become menu_eligible; the pool goes 56 → 150, protein 11 → 105.
-- The list is db/block6_protein_allergens.tsv (6ח-א, 12.09.2026): the
-- non-eligible rows of db/block5_protein_codes.txt minus 32 label-condition
-- codes (block 7, #45), 1698 and 9589 (fibre, #13), 1630 (Lupin not in the
-- vocabulary, #48) and 680 (no identity, no label). Allergen per code:
-- docs/work/2026-09-11-block-6-allergens.md, the owner's table of 12.09.2026,
-- under the rule of 11.09 (identity only, "may contain" is not tagged); the 8
-- recipes by their component list (decisions.md 12.09). Not touched: 493
-- (removed in 3ח, #35), the 32 label codes, 1698, 9589, 1630, 680, 1826.
-- Expected canonical snapshot afterwards: 309 · 150 · 105 · 37 · 4 · 4 · 150 · 0 · 0.
--   {}            609 615 619 623 624 626 636 717 721 729 772 780 781 782
--                 788 799 807 825 834 838 841 846 856 873 880 886 892 894
--                 926 928 941 943 963 1040 1653 1661 1669 8186 8188 8547
--                 8804 8837 9535 9717   (44)
--   {Milk}        258 420 446 472 499 504 508 522 533 562 572 8506 8598
--                 8601 8604 8605 9516 9560   (18)
--   {Fish}        1152 1182 1206 1223 1277 1296 1298 1308 1311 1332 1340
--                 1360 8260 9635   (14)
--   {Soy}         1632 1638 1679 1704 1724 8229 8274 10141 10142   (9)
--   {Egg}         1561 1564 1565 1566 1573 1574 1575   (7)
--   {Gluten}      9851   (1)
--   {Egg,Gluten}  675   (1)
-- The 8 recipes sit inside the groups by their component list: 825 {} ·
-- 1206 1298 9635 1340 {Fish} · 1573 {Egg} · 1638 {Soy} · 675 {Egg,Gluten}.
-- Same pattern as 17_flip_fat.sql: one transaction, a _pre snapshot of every
-- column, the writes — each followed by W1–W7, a row-count check against _pre —
-- then V0–V7, COMMIT. V0 pins the snapshot this file was written against, so a
-- second run fails before it touches anything. V6 looks at the two recipe
-- views for the first time on eligible recipes: v_recipe_unreviewed_components
-- is not 0 afterwards, on purpose (#49) — 13 of the 14 components have no
-- food_curation row — and the assertion compares it with an independent count.

BEGIN;

CREATE TEMP TABLE _pre ON COMMIT DROP AS
  SELECT source_code, category, kosher, allergens, allergens_reviewed_at, tags,
         quality, supp, prep, by_weight, whole_only, max_g, menu_eligible,
         curated_by, curated_at, created_at, updated_at, excluded_reason
    FROM food_curation;

-- V0 — precondition: the snapshot this file expects, so a second run fails
-- before it touches anything
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
  IF tot<>309 OR el<>56 OR p<>11 OR f<>37 OR c<>4 OR v<>4 OR vm<>56 OR mt<>0 OR orph<>0 THEN
    RAISE EXCEPTION 'V0 failed: tot=% el=% p=% f=% c=% v=% view=% missing_tags=% orphans=%',
      tot, el, p, f, c, v, vm, mt, orph;
  END IF;
END $$;

-- V1 — the 94 all exist: protein, not eligible, unreviewed, and the menu fields
-- the CHECK constraints read are in place (kosher, quality, prep, by_weight)
DO $$
DECLARE present int; ready int;
BEGIN
  SELECT count(*),
         count(*) FILTER (WHERE category = 'protein' AND menu_eligible = false
                            AND allergens_reviewed_at IS NULL
                            AND kosher IS NOT NULL AND quality IS NOT NULL
                            AND prep IS NOT NULL AND by_weight IS NOT NULL)
    INTO present, ready
    FROM food_curation
   WHERE source_code IN ('258','420','446','472','499','504','508','522','533',
                         '562','572','609','615','619','623','624','626','636',
                         '675','717','721','729','772','780','781','782','788',
                         '799','807','825','834','838','841','846','856','873',
                         '880','886','892','894','926','928','941','943','963',
                         '1040','1152','1182','1206','1223','1277','1296',
                         '1298','1308','1311','1332','1340','1360','1561',
                         '1564','1565','1566','1573','1574','1575','1632',
                         '1638','1653','1661','1669','1679','1704','1724',
                         '8186','8188','8229','8260','8274','8506','8547',
                         '8598','8601','8604','8605','8804','8837','9516',
                         '9535','9560','9635','9717','9851','10141','10142');
  IF present <> 94 OR ready <> 94 THEN
    RAISE EXCEPTION 'V1 failed: present=% ready=% of 94', present, ready;
  END IF;
END $$;

-- The writes: one UPDATE per allergen group, per the owner's table. Each is
-- followed by W<n>: against _pre, exactly the group's rows changed, and each
-- of them now carries the group's literal, is reviewed and eligible.
UPDATE food_curation
   SET allergens = '{}'::text[], allergens_reviewed_at = now(), menu_eligible = true
 WHERE source_code IN ('609','615','619','623','624','626','636','717','721',
                       '729','772','780','781','782','788','799','807','825',
                       '834','838','841','846','856','873','880','886','892',
                       '894','926','928','941','943','963','1040','1653','1661',
                       '1669','8186','8188','8547','8804','8837','9535','9717');

DO $$
DECLARE n int; changed int;
BEGIN
  SELECT count(*),
         count(*) FILTER (WHERE c.menu_eligible AND c.allergens_reviewed_at IS NOT NULL
                            AND c.allergens = '{}'::text[]
                            AND (c.allergens_reviewed_at, c.menu_eligible)
                                IS DISTINCT FROM (p.allergens_reviewed_at, p.menu_eligible))
    INTO n, changed
    FROM food_curation c JOIN _pre p USING (source_code)
   WHERE c.source_code IN ('609','615','619','623','624','626','636','717',
                           '721','729','772','780','781','782','788','799',
                           '807','825','834','838','841','846','856','873',
                           '880','886','892','894','926','928','941','943',
                           '963','1040','1653','1661','1669','8186','8188',
                           '8547','8804','8837','9535','9717');
  IF n <> 44 OR changed <> 44 THEN
    RAISE EXCEPTION 'W1 failed: {} group: in-list=% changed=% expected 44', n, changed;
  END IF;
END $$;

UPDATE food_curation
   SET allergens = '{Milk}'::text[], allergens_reviewed_at = now(), menu_eligible = true
 WHERE source_code IN ('258','420','446','472','499','504','508','522','533',
                       '562','572','8506','8598','8601','8604','8605','9516',
                       '9560');

DO $$
DECLARE n int; changed int;
BEGIN
  SELECT count(*),
         count(*) FILTER (WHERE c.menu_eligible AND c.allergens_reviewed_at IS NOT NULL
                            AND c.allergens = '{Milk}'::text[]
                            AND (c.allergens_reviewed_at, c.menu_eligible)
                                IS DISTINCT FROM (p.allergens_reviewed_at, p.menu_eligible))
    INTO n, changed
    FROM food_curation c JOIN _pre p USING (source_code)
   WHERE c.source_code IN ('258','420','446','472','499','504','508','522',
                           '533','562','572','8506','8598','8601','8604','8605',
                           '9516','9560');
  IF n <> 18 OR changed <> 18 THEN
    RAISE EXCEPTION 'W2 failed: {Milk} group: in-list=% changed=% expected 18', n, changed;
  END IF;
END $$;

UPDATE food_curation
   SET allergens = '{Fish}'::text[], allergens_reviewed_at = now(), menu_eligible = true
 WHERE source_code IN ('1152','1182','1206','1223','1277','1296','1298','1308',
                       '1311','1332','1340','1360','8260','9635');

DO $$
DECLARE n int; changed int;
BEGIN
  SELECT count(*),
         count(*) FILTER (WHERE c.menu_eligible AND c.allergens_reviewed_at IS NOT NULL
                            AND c.allergens = '{Fish}'::text[]
                            AND (c.allergens_reviewed_at, c.menu_eligible)
                                IS DISTINCT FROM (p.allergens_reviewed_at, p.menu_eligible))
    INTO n, changed
    FROM food_curation c JOIN _pre p USING (source_code)
   WHERE c.source_code IN ('1152','1182','1206','1223','1277','1296','1298',
                           '1308','1311','1332','1340','1360','8260','9635');
  IF n <> 14 OR changed <> 14 THEN
    RAISE EXCEPTION 'W3 failed: {Fish} group: in-list=% changed=% expected 14', n, changed;
  END IF;
END $$;

UPDATE food_curation
   SET allergens = '{Soy}'::text[], allergens_reviewed_at = now(), menu_eligible = true
 WHERE source_code IN ('1632','1638','1679','1704','1724','8229','8274','10141',
                       '10142');

DO $$
DECLARE n int; changed int;
BEGIN
  SELECT count(*),
         count(*) FILTER (WHERE c.menu_eligible AND c.allergens_reviewed_at IS NOT NULL
                            AND c.allergens = '{Soy}'::text[]
                            AND (c.allergens_reviewed_at, c.menu_eligible)
                                IS DISTINCT FROM (p.allergens_reviewed_at, p.menu_eligible))
    INTO n, changed
    FROM food_curation c JOIN _pre p USING (source_code)
   WHERE c.source_code IN ('1632','1638','1679','1704','1724','8229','8274',
                           '10141','10142');
  IF n <> 9 OR changed <> 9 THEN
    RAISE EXCEPTION 'W4 failed: {Soy} group: in-list=% changed=% expected 9', n, changed;
  END IF;
END $$;

UPDATE food_curation
   SET allergens = '{Egg}'::text[], allergens_reviewed_at = now(), menu_eligible = true
 WHERE source_code IN ('1561','1564','1565','1566','1573','1574','1575');

DO $$
DECLARE n int; changed int;
BEGIN
  SELECT count(*),
         count(*) FILTER (WHERE c.menu_eligible AND c.allergens_reviewed_at IS NOT NULL
                            AND c.allergens = '{Egg}'::text[]
                            AND (c.allergens_reviewed_at, c.menu_eligible)
                                IS DISTINCT FROM (p.allergens_reviewed_at, p.menu_eligible))
    INTO n, changed
    FROM food_curation c JOIN _pre p USING (source_code)
   WHERE c.source_code IN ('1561','1564','1565','1566','1573','1574','1575');
  IF n <> 7 OR changed <> 7 THEN
    RAISE EXCEPTION 'W5 failed: {Egg} group: in-list=% changed=% expected 7', n, changed;
  END IF;
END $$;

UPDATE food_curation
   SET allergens = '{Gluten}'::text[], allergens_reviewed_at = now(), menu_eligible = true
 WHERE source_code IN ('9851');

DO $$
DECLARE n int; changed int;
BEGIN
  SELECT count(*),
         count(*) FILTER (WHERE c.menu_eligible AND c.allergens_reviewed_at IS NOT NULL
                            AND c.allergens = '{Gluten}'::text[]
                            AND (c.allergens_reviewed_at, c.menu_eligible)
                                IS DISTINCT FROM (p.allergens_reviewed_at, p.menu_eligible))
    INTO n, changed
    FROM food_curation c JOIN _pre p USING (source_code)
   WHERE c.source_code IN ('9851');
  IF n <> 1 OR changed <> 1 THEN
    RAISE EXCEPTION 'W6 failed: {Gluten} group: in-list=% changed=% expected 1', n, changed;
  END IF;
END $$;

UPDATE food_curation
   SET allergens = '{Egg,Gluten}'::text[], allergens_reviewed_at = now(), menu_eligible = true
 WHERE source_code IN ('675');

DO $$
DECLARE n int; changed int;
BEGIN
  SELECT count(*),
         count(*) FILTER (WHERE c.menu_eligible AND c.allergens_reviewed_at IS NOT NULL
                            AND c.allergens = '{Egg,Gluten}'::text[]
                            AND (c.allergens_reviewed_at, c.menu_eligible)
                                IS DISTINCT FROM (p.allergens_reviewed_at, p.menu_eligible))
    INTO n, changed
    FROM food_curation c JOIN _pre p USING (source_code)
   WHERE c.source_code IN ('675');
  IF n <> 1 OR changed <> 1 THEN
    RAISE EXCEPTION 'W7 failed: {Egg,Gluten} group: in-list=% changed=% expected 1', n, changed;
  END IF;
END $$;

-- Raw output for the record, before the assertions: the 94 by allergen group
SELECT allergens, count(*) AS n,
       string_agg(source_code, ' ' ORDER BY source_code::int) AS codes
  FROM food_curation
 WHERE source_code IN ('258','420','446','472','499','504','508','522','533',
                       '562','572','609','615','619','623','624','626','636',
                       '675','717','721','729','772','780','781','782','788',
                       '799','807','825','834','838','841','846','856','873',
                       '880','886','892','894','926','928','941','943','963',
                       '1040','1152','1182','1206','1223','1277','1296','1298',
                       '1308','1311','1332','1340','1360','1561','1564','1565',
                       '1566','1573','1574','1575','1632','1638','1653','1661',
                       '1669','1679','1704','1724','8186','8188','8229','8260',
                       '8274','8506','8547','8598','8601','8604','8605','8804',
                       '8837','9516','9535','9560','9635','9717','9851','10141',
                       '10142')
 GROUP BY allergens
 ORDER BY n DESC, allergens;

-- V2 — 309 rows, nothing added or removed; the rows that differ from _pre in
-- any column are exactly the 94, and within them only allergens,
-- allergens_reviewed_at, menu_eligible and updated_at (the trigger) moved; the
-- other 215 rows are identical in every column, updated_at included
DO $$
DECLARE tot int; added int; removed int; touched int; touched_outside int;
        other_moved int; others int; others_moved int;
BEGIN
  SELECT count(*) INTO tot FROM food_curation;
  SELECT count(*) INTO added FROM food_curation c
    LEFT JOIN _pre p USING (source_code) WHERE p.source_code IS NULL;
  SELECT count(*) INTO removed FROM _pre p
    LEFT JOIN food_curation c USING (source_code) WHERE c.source_code IS NULL;
  SELECT count(*) INTO touched
    FROM food_curation c JOIN _pre p USING (source_code)
   WHERE (c.category, c.kosher, c.allergens, c.allergens_reviewed_at, c.tags,
            c.quality, c.supp, c.prep, c.by_weight, c.whole_only, c.max_g,
            c.menu_eligible, c.curated_by, c.curated_at, c.created_at, c.updated_at,
            c.excluded_reason)
         IS DISTINCT FROM
         (p.category, p.kosher, p.allergens, p.allergens_reviewed_at, p.tags,
            p.quality, p.supp, p.prep, p.by_weight, p.whole_only, p.max_g,
            p.menu_eligible, p.curated_by, p.curated_at, p.created_at, p.updated_at,
            p.excluded_reason);
  SELECT count(*) INTO touched_outside
    FROM food_curation c JOIN _pre p USING (source_code)
   WHERE c.source_code NOT IN ('258','420','446','472','499','504','508','522',
                               '533','562','572','609','615','619','623','624',
                               '626','636','675','717','721','729','772','780',
                               '781','782','788','799','807','825','834','838',
                               '841','846','856','873','880','886','892','894',
                               '926','928','941','943','963','1040','1152',
                               '1182','1206','1223','1277','1296','1298','1308',
                               '1311','1332','1340','1360','1561','1564','1565',
                               '1566','1573','1574','1575','1632','1638','1653',
                               '1661','1669','1679','1704','1724','8186','8188',
                               '8229','8260','8274','8506','8547','8598','8601',
                               '8604','8605','8804','8837','9516','9535','9560',
                               '9635','9717','9851','10141','10142')
     AND (c.category, c.kosher, c.allergens, c.allergens_reviewed_at, c.tags,
            c.quality, c.supp, c.prep, c.by_weight, c.whole_only, c.max_g,
            c.menu_eligible, c.curated_by, c.curated_at, c.created_at, c.updated_at,
            c.excluded_reason)
         IS DISTINCT FROM
         (p.category, p.kosher, p.allergens, p.allergens_reviewed_at, p.tags,
            p.quality, p.supp, p.prep, p.by_weight, p.whole_only, p.max_g,
            p.menu_eligible, p.curated_by, p.curated_at, p.created_at, p.updated_at,
            p.excluded_reason);
  SELECT count(*) FILTER (WHERE
           (c.category, c.kosher, c.tags, c.quality, c.supp, c.prep, c.by_weight,
            c.whole_only, c.max_g, c.curated_by, c.curated_at, c.created_at,
            c.excluded_reason)
           IS DISTINCT FROM
           (p.category, p.kosher, p.tags, p.quality, p.supp, p.prep, p.by_weight,
            p.whole_only, p.max_g, p.curated_by, p.curated_at, p.created_at,
            p.excluded_reason))
    INTO other_moved
    FROM food_curation c JOIN _pre p USING (source_code)
   WHERE c.source_code IN ('258','420','446','472','499','504','508','522',
                           '533','562','572','609','615','619','623','624',
                           '626','636','675','717','721','729','772','780',
                           '781','782','788','799','807','825','834','838',
                           '841','846','856','873','880','886','892','894',
                           '926','928','941','943','963','1040','1152','1182',
                           '1206','1223','1277','1296','1298','1308','1311',
                           '1332','1340','1360','1561','1564','1565','1566',
                           '1573','1574','1575','1632','1638','1653','1661',
                           '1669','1679','1704','1724','8186','8188','8229',
                           '8260','8274','8506','8547','8598','8601','8604',
                           '8605','8804','8837','9516','9535','9560','9635',
                           '9717','9851','10141','10142');
  SELECT count(*), count(*) FILTER (WHERE
           (c.category, c.kosher, c.allergens, c.allergens_reviewed_at, c.tags,
            c.quality, c.supp, c.prep, c.by_weight, c.whole_only, c.max_g,
            c.menu_eligible, c.curated_by, c.curated_at, c.created_at, c.updated_at,
            c.excluded_reason)
           IS DISTINCT FROM
           (p.category, p.kosher, p.allergens, p.allergens_reviewed_at, p.tags,
            p.quality, p.supp, p.prep, p.by_weight, p.whole_only, p.max_g,
            p.menu_eligible, p.curated_by, p.curated_at, p.created_at, p.updated_at,
            p.excluded_reason))
    INTO others, others_moved
    FROM _pre p JOIN food_curation c USING (source_code)
   WHERE p.source_code NOT IN ('258','420','446','472','499','504','508','522',
                               '533','562','572','609','615','619','623','624',
                               '626','636','675','717','721','729','772','780',
                               '781','782','788','799','807','825','834','838',
                               '841','846','856','873','880','886','892','894',
                               '926','928','941','943','963','1040','1152',
                               '1182','1206','1223','1277','1296','1298','1308',
                               '1311','1332','1340','1360','1561','1564','1565',
                               '1566','1573','1574','1575','1632','1638','1653',
                               '1661','1669','1679','1704','1724','8186','8188',
                               '8229','8260','8274','8506','8547','8598','8601',
                               '8604','8605','8804','8837','9516','9535','9560',
                               '9635','9717','9851','10141','10142');
  IF tot <> 309 OR added <> 0 OR removed <> 0 OR touched <> 94 OR touched_outside <> 0
     OR other_moved <> 0 OR others <> 215 OR others_moved <> 0 THEN
    RAISE EXCEPTION 'V2 failed: tot=% added=% removed=% touched=% touched-outside-94=% other-columns-moved=% others=% others-moved=%',
      tot, added, removed, touched, touched_outside, other_moved, others, others_moved;
  END IF;
END $$;

-- V3 — the 94 now: eligible and reviewed; count by allergens array
DO $$
DECLARE flipped int; g_empty int; g_milk int; g_fish int; g_soy int; g_egg int;
        g_gluten int; g_egg_gluten int;
BEGIN
  SELECT count(*) FILTER (WHERE menu_eligible AND allergens_reviewed_at IS NOT NULL),
         count(*) FILTER (WHERE allergens = '{}'::text[]),
         count(*) FILTER (WHERE allergens = '{Milk}'::text[]),
         count(*) FILTER (WHERE allergens = '{Fish}'::text[]),
         count(*) FILTER (WHERE allergens = '{Soy}'::text[]),
         count(*) FILTER (WHERE allergens = '{Egg}'::text[]),
         count(*) FILTER (WHERE allergens = '{Gluten}'::text[]),
         count(*) FILTER (WHERE allergens = '{Egg,Gluten}'::text[])
    INTO flipped, g_empty, g_milk, g_fish, g_soy, g_egg, g_gluten, g_egg_gluten
    FROM food_curation
   WHERE source_code IN ('258','420','446','472','499','504','508','522','533',
                         '562','572','609','615','619','623','624','626','636',
                         '675','717','721','729','772','780','781','782','788',
                         '799','807','825','834','838','841','846','856','873',
                         '880','886','892','894','926','928','941','943','963',
                         '1040','1152','1182','1206','1223','1277','1296',
                         '1298','1308','1311','1332','1340','1360','1561',
                         '1564','1565','1566','1573','1574','1575','1632',
                         '1638','1653','1661','1669','1679','1704','1724',
                         '8186','8188','8229','8260','8274','8506','8547',
                         '8598','8601','8604','8605','8804','8837','9516',
                         '9535','9560','9635','9717','9851','10141','10142');
  IF flipped <> 94 OR g_empty <> 44 OR g_milk <> 18 OR g_fish <> 14 OR g_soy <> 9
     OR g_egg <> 7 OR g_gluten <> 1 OR g_egg_gluten <> 1 THEN
    RAISE EXCEPTION 'V3 failed: flipped=% empty=% milk=% fish=% soy=% egg=% gluten=% egg+gluten=%',
      flipped, g_empty, g_milk, g_fish, g_soy, g_egg, g_gluten, g_egg_gluten;
  END IF;
END $$;

-- V4 — untouched by name: 493 as 3ח left it ({Milk}, reviewed 30.08, not
-- eligible); 680, 1630, 1698, 1826, 9589 and the 32 label codes
-- (db/block6_protein_label_codes.txt) still unreviewed and not eligible
DO $$
DECLARE cottage int; untouched int;
BEGIN
  SELECT count(*) INTO cottage FROM food_curation
   WHERE source_code = '493' AND allergens = '{Milk}'::text[]
     AND allergens_reviewed_at::date = DATE '2026-08-30' AND menu_eligible = false;
  SELECT count(*) INTO untouched FROM food_curation
   WHERE allergens_reviewed_at IS NULL AND menu_eligible = false
     AND (source_code IN ('680','1630','1698','1826','9589')
          OR source_code IN ('539','556','561','625','649','653','661','662',
                             '663','670','681','683','802','889','910','923',
                             '1307','1674','1790','1791','1792','1805','1810',
                             '8584','8625','8690','8696','8741','8868','9650',
                             '9768','10126'));
  IF cottage <> 1 OR untouched <> 37 THEN
    RAISE EXCEPTION 'V4 failed: 493-as-left=% untouched-of-37=%', cottage, untouched;
  END IF;
END $$;

-- V5 — counts: 94 more eligible, all of them protein, the view follows, the
-- safety views stay clean
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
  IF tot<>309 OR el<>150 OR p<>105 OR f<>37 OR c<>4 OR v<>4 OR vm<>150 OR mt<>0 OR orph<>0 THEN
    RAISE EXCEPTION 'V5 failed: tot=% el=% p=% f=% c=% v=% view=% missing_tags=% orphans=%',
      tot, el, p, f, c, v, vm, mt, orph;
  END IF;
END $$;

-- V6 — the 8 recipes, for the record and then asserted. (a) every row of
-- v_recipe_unreviewed_components belongs to one of the 8, and the view's row
-- count equals an independent count in this transaction: component rows of the
-- 8 whose component has no food_curation row with allergens_reviewed_at NOT
-- NULL (23 component rows minus the two rows of 1561, which this migration
-- reviews). (b) v_recipe_inherited_allergens on the 8: exactly 675 and 1573,
-- each {Egg}, inherited from 1561. (c) each recipe's inherited set (empty if
-- absent) is contained in the allergens written for it.
SELECT (SELECT count(*) FROM v_recipe_unreviewed_components) AS unreviewed_view_rows,
       (SELECT count(*) FROM v_recipe_unreviewed_components v
         WHERE v.recipe_id NOT IN (SELECT id FROM foods
                                    WHERE source_code IN ('675','825','1206',
                                                          '1298','1340','1573',
                                                          '1638','9635'))) AS unreviewed_outside_the_8,
       (SELECT count(*)
          FROM food_recipe_components rc
          JOIN foods r ON r.id = rc.recipe_id
          JOIN foods c ON c.id = rc.component_id
         WHERE r.source_code IN ('675','825','1206','1298','1340','1573','1638',
                                 '9635')
           AND NOT EXISTS (SELECT 1 FROM food_curation cur
                            WHERE cur.source_code = c.source_code
                              AND cur.allergens_reviewed_at IS NOT NULL)) AS independent_unreviewed_rows,
       (SELECT string_agg(r.source_code || ' ' || v.inherited::text, ' · ' ORDER BY r.source_code::int)
          FROM v_recipe_inherited_allergens v JOIN foods r ON r.id = v.recipe_id
         WHERE r.source_code IN ('675','825','1206','1298','1340','1573','1638',
                                 '9635')) AS inherited_on_the_8;

DO $$
DECLARE view_rows int; outside int; indep int; inh_rows int; inh_ok int; contained int;
BEGIN
  SELECT count(*) INTO view_rows FROM v_recipe_unreviewed_components;
  SELECT count(*) INTO outside FROM v_recipe_unreviewed_components v
   WHERE v.recipe_id NOT IN (SELECT id FROM foods
                              WHERE source_code IN ('675','825','1206','1298',
                                                    '1340','1573','1638','9635'));
  SELECT count(*) INTO indep
    FROM food_recipe_components rc
    JOIN foods r ON r.id = rc.recipe_id
    JOIN foods c ON c.id = rc.component_id
   WHERE r.source_code IN ('675','825','1206','1298','1340','1573','1638',
                           '9635')
     AND NOT EXISTS (SELECT 1 FROM food_curation cur
                      WHERE cur.source_code = c.source_code
                        AND cur.allergens_reviewed_at IS NOT NULL);
  SELECT count(*),
         count(*) FILTER (WHERE r.source_code IN ('675','1573') AND v.inherited = '{Egg}'::text[])
    INTO inh_rows, inh_ok
    FROM v_recipe_inherited_allergens v JOIN foods r ON r.id = v.recipe_id
   WHERE r.source_code IN ('675','825','1206','1298','1340','1573','1638',
                           '9635');
  SELECT count(*) INTO contained
    FROM foods r
    JOIN food_curation cur ON cur.source_code = r.source_code
    LEFT JOIN v_recipe_inherited_allergens v ON v.recipe_id = r.id
   WHERE r.source_code IN ('675','825','1206','1298','1340','1573','1638',
                           '9635')
     AND coalesce(v.inherited, '{}'::text[]) <@ cur.allergens;
  IF view_rows <> indep OR outside <> 0 OR inh_rows <> 2 OR inh_ok <> 2 OR contained <> 8 THEN
    RAISE EXCEPTION 'V6 failed: unreviewed view=% independent=% outside-the-8=% inherited-rows=% inherited-egg-on-675-1573=% contained-of-8=%',
      view_rows, indep, outside, inh_rows, inh_ok, contained;
  END IF;
END $$;

-- V7 — eligible protein with allergens = {} is 47 (805, 944, 9793 and the 44);
-- every label anywhere in food_curation.allergens is one of the eight words
DO $$
DECLARE clean_protein int; off_vocab int; off_list text;
BEGIN
  SELECT count(*) INTO clean_protein FROM food_curation
   WHERE menu_eligible AND category = 'protein' AND allergens = '{}'::text[];
  SELECT count(*), string_agg(DISTINCT a, ',') INTO off_vocab, off_list
    FROM food_curation, unnest(allergens) AS a
   WHERE a NOT IN ('Egg','Fish','Gluten','Milk','Peanuts','Sesame','Soy','Tree nuts');
  IF clean_protein <> 47 OR off_vocab <> 0 THEN
    RAISE EXCEPTION 'V7 failed: clean-protein=% off-vocabulary=% (%)',
      clean_protein, off_vocab, coalesce(off_list, '');
  END IF;
END $$;

COMMIT;
