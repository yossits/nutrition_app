-- Block 8ח-ט - migration 29: the 46 protein rows that 28 tagged and reviewed become
-- menu_eligible; the pool goes 273 -> 319 and protein goes 108 -> 154.
-- Decided in docs/decisions.md, 21.09.2026: the review of 8ח-ד (46 in, 6 label condition, 26 out),
-- the tagging of 8ח-ו and the allergens of 8ח-ז, all of it written to food_curation by
-- 28_tag_protein.sql. See docs/PROGRESS.md, row 8ח-ט, and docs/work/2026-09-20-block-8-protein.md.
--
-- The list is db/block8_protein_codes.txt (46 codes, sha256 49247571…). The names below were read
-- from foods.name_he by a read-only query when this file was generated, and are equal to the
-- flip = true rows of the _52 list in 28_tag_protein.sql; V0 stops the run if foods.name_he
-- differs. 431 and 496 carry a doubled space, as foods has them.
-- The six of db/block8_protein_label_codes.txt are not touched: label condition, 7מ after #56.
-- V0 and V4 pin them not eligible and unreviewed.
--
-- What this file writes, on the 46 only:
--   menu_eligible = true
-- Nothing else. This is what differs from 27: 27 wrote the allergen review in the flip -
-- allergens and allergens_reviewed_at = now() - because 26 had tagged the olives without
-- reviewing them. 29 does not, because 28 already did: allergens and allergens_reviewed_at on the
-- 46 are 28's (2026-09-21 11:28:44.628302 UTC), and so are tags, quality, kosher, curated_by and
-- curated_at. All of them stay; updated_at moves by itself, through the trigger
-- food_curation_touch_updated_at.
--
-- The CHECK constraints this satisfies (db/01_food_db_schema.sql; the live definitions were read
-- from pg_constraint before this file was written). Postgres enforces them on the UPDATE itself,
-- so a row that fails one stops the statement before any of V1-V5 runs. For the first two, V0
-- tests the same columns before the UPDATE and stops the run first; the CHECK is the backstop:
--   eligible_requires_safety_tagging    - category, kosher and allergens_reviewed_at are set (28)
--   eligible_protein_requires_quality   - the 46 are protein, and quality is set on all of them (28)
--   eligible_requires_menu_fields       - prep and by_weight are set (28)
--   excluded_reason_requires_ineligible - excluded_reason is NULL on all 46
--
-- Same pattern as 27_flip_fat.sql: one transaction, a _pre snapshot of all 21 columns, a temp table
-- _46 whose names are checked against foods, the UPDATE, assertions, COMMIT. V0 pins the state
-- this file was written against, so a second run fails before it touches anything. V0 also ties
-- _46 to 28: the rows that carry 28's review stamp are exactly the 46. Without it, _46 was checked
-- only against itself - its names come from foods by the same code, and "protein, not eligible,
-- reviewed, quality and kosher set" also fits 493, the cottage 12_cottage_swap.sql took off the
-- menu (measured read-only: one such row outside the 46, and it is 493). V3 is 28's
-- V3 - EXCEPT both ways against _pre - on the 434 rows outside the 46. V5 carries 27's table-wide
-- checks: the snapshot, the safety views, the allergen vocabulary, no eligible vegan row with Egg,
-- Milk or Fish, and the two recipe views. They run inside the transaction, so a violation rolls
-- the flip back; the same numbers are read again outside the file, read-only, after the apply.
--
-- Measured read-only before this file was written, through query() of db/_audit_block7a.py:
--   eligible vegan 182 -> 195: 13 of the 46 carry vegan, and none of the 13 Egg, Milk or Fish
--   v_recipe_unreviewed_components 31 -> 72: the view lists the unreviewed components of
--     eligible recipes. 12 of the 46 are recipes, tagged by their components (#49, closed
--     20.09.2026), and they bring 41 rows - 23 distinct components, none with a curation row.
--     Information, not a gate (#49); pinned here so the flip moves it by exactly what was measured
--   v_recipe_inherited_allergens 488, unchanged: the view does not read menu_eligible
-- Expected canonical snapshot afterwards: 480 · 319 · 154 · 43 · 44 · 78 · 319 · 0 · 0.

BEGIN;

CREATE TEMP TABLE _pre ON COMMIT DROP AS
  SELECT source_code, category, kosher, allergens, allergens_reviewed_at, tags,
         quality, supp, prep, by_weight, whole_only, max_g, menu_eligible,
         curated_by, curated_at, created_at, updated_at, excluded_reason,
         label_source, label_date, fiber_g_label
    FROM food_curation;

-- The 46 codes of db/block8_protein_codes.txt, with the name each one carries in foods
CREATE TEMP TABLE _46 (source_code text PRIMARY KEY, name_he text NOT NULL) ON COMMIT DROP;
INSERT INTO _46 (source_code, name_he) VALUES
    ('431' , 'גבינה צהובה 22%  שומן, גלבוע, טרה, תנובה'),
    ('496' , 'גבינת קוטג'' 9%  שומן, תנובה'),
    ('503' , 'גבינת קוטג'' 5%, שטראוס'),
    ('520' , 'גבינה לבנה 5% שומן, טבורוג ללא תוספת מלח, צוריאל'),
    ('614' , 'סטייק בשר בקר, מטוגן, נאכל עם שומן'),
    ('627' , 'בשר בקר, גולש, מבושל, בשר בלבד'),
    ('628' , 'בשר בקר, צלי, מאודה או מבושל, נאכל ללא שומן'),
    ('725' , 'בשר כבש, נתחים שונים, אפוי בתנור'),
    ('751' , 'בשר עגל, לפנ לנתח, מבושל, נאכל ללא שומן'),
    ('776' , 'בשר עגל, סטייק, מבושל'),
    ('777' , 'שניצל בשר עגל, מצופה או מקומח, מטוגן, נאכל עם שומן'),
    ('801' , 'בשר עוף, חזה, ללא עצם, בגריל, נאכל עם עור'),
    ('806' , 'בשר עוף, חזה, ללא עצם, מבושל, נאכל עם עור'),
    ('855' , 'בשר עוף, שוק, ללא עצם, מבושל, נאכל עם עור'),
    ('863' , 'בשר עוף, שוק, ללא עצם, מטוגן, ללא ציפוי, נאכל ללא עור'),
    ('871' , 'בשר עוף, ירך, ללא עצם, בגריל, נאכל עם עור'),
    ('885' , 'בשר עוף, ירך, ללא עצם, מטוגן, ללא ציפוי, נאכל עם עור'),
    ('891' , 'בשר עוף, כנף, ללא עצם, בגריל, נאכל עם עור'),
    ('945' , 'בשר הודו לבן, מבושל, נאכל עם עור'),
    ('1000', 'בשר הודו, לבן או אדום, מבושל, נאכל ללא עור'),
    ('1012', 'בשר הודו, שוק, מבושל, נאכל ללא עור'),
    ('1241', 'דג מקרל, מעושן'),
    ('1269', 'דג נסיכת הנילוס מבושל'),
    ('1294', 'דג פרידה מטוגן ללא שמן, ללא בלילה'),
    ('1316', 'דג סרדין, בגריל, ללא עצמות'),
    ('1336', 'דג פורל, מבושל במים או באדים, עם מלח'),
    ('1337', 'דג פורל, מעושן'),
    ('1605', 'שעועית לבנה יבשה מבושלת עם מלח, ללא תוספת שומן בבישול'),
    ('1606', 'סלט שעועית לבנה עם פטרוזיליה ומיץ לימון, ללא תוספת שמן'),
    ('1608', 'שעועית לבנה מבושלת ברסק עגבניות ושמן זית'),
    ('1617', 'פול טרי מבושל, ללא תוספת שומן בבישול, עם מלח'),
    ('1623', 'פול טרי מבושל עם שמן זית'),
    ('1624', 'שעועית לימה יבשה מבושלת ללא תוספת שמן'),
    ('1625', 'פול מטוגן בנוסח מצרי'),
    ('1629', 'פול יבש, מבושל'),
    ('1663', 'אליצ''ה אפונה אתיופי'),
    ('1667', 'וואט עדשים אתיופי'),
    ('1688', 'טופו מטוגן בשמן זית'),
    ('1711', 'קציצות טופו וירקות אפויות'),
    ('8261', 'שעועית שחורה, מבושלת, ללא תוספת מלח ושומן בבישול'),
    ('8305', 'שעועית אדומה מבושלת, מקפוא, סנפרוסט'),
    ('8509', 'דג סרדין סטאר בשמן סויה או שמן זית, יונה'),
    ('8609', 'גבינה צהובה 15% שומן, עמק'),
    ('9182', 'עדשים מבושלים עם בצל ושמן קנולה'),
    ('9634', 'דג אמנון-מושט, מטוגן ללא שמן, ללא בלילה'),
    ('9784', 'דג דניס בגריל, ללא ציפוי, ללא שמן');

-- V0 - precondition and rerun guard: the snapshot this file expects; the 46 exist, carry the name
-- foods gives them, and stand as 28 left them - protein, not eligible, reviewed at 28's stamp,
-- quality and kosher set - and no other row carries that stamp; the six of the label list exist,
-- not eligible and unreviewed
DO $$
DECLARE tot int; el int; p int; f int; c int; v int; vm int; mt int; orph int;
        n46 int; present int; named int; ready int; stamped int; six int; six_waiting int;
BEGIN
  SELECT count(*), count(*) FILTER (WHERE menu_eligible),
         count(*) FILTER (WHERE menu_eligible AND category = 'protein'),
         count(*) FILTER (WHERE menu_eligible AND category = 'fat'),
         count(*) FILTER (WHERE menu_eligible AND category = 'carb'),
         count(*) FILTER (WHERE menu_eligible AND category = 'veg')
    INTO tot, el, p, f, c, v FROM food_curation;
  SELECT count(*) INTO vm   FROM v_menu_foods;
  SELECT count(*) INTO mt   FROM v_eligible_missing_tags;
  SELECT count(*) INTO orph FROM v_curation_orphans;
  SELECT count(*) INTO n46  FROM _46;
  SELECT count(*),
         count(*) FILTER (WHERE fd.name_he = s.name_he),
         count(*) FILTER (WHERE cu.category = 'protein' AND cu.menu_eligible = false
                            AND cu.allergens_reviewed_at = '2026-09-21 11:28:44.628302+00'
                            AND cu.quality IS NOT NULL AND cu.kosher IS NOT NULL)
    INTO present, named, ready
    FROM _46 s
    JOIN food_curation cu ON cu.source_code = s.source_code
    JOIN foods fd ON fd.source_code = s.source_code;
  SELECT count(*) INTO stamped FROM food_curation
   WHERE allergens_reviewed_at = '2026-09-21 11:28:44.628302+00';
  SELECT count(*),
         count(*) FILTER (WHERE menu_eligible = false AND allergens_reviewed_at IS NULL)
    INTO six, six_waiting
    FROM food_curation
   WHERE source_code IN ('1796', '1797', '1800', '8865', '8866', '9758');
  IF tot<>480 OR el<>273 OR p<>108 OR f<>43 OR c<>44 OR v<>78 OR vm<>273 OR mt<>0 OR orph<>0
     OR n46<>46 OR present<>46 OR named<>46 OR ready<>46 OR stamped<>46
     OR six<>6 OR six_waiting<>6 THEN
    RAISE EXCEPTION 'V0 failed: tot=% el=% p=% f=% c=% v=% view=% missing_tags=% orphans=% · n46=% present=% named=% ready=% stamped=% · six=% six_waiting=%',
      tot, el, p, f, c, v, vm, mt, orph, n46, present, named, ready, stamped, six, six_waiting;
  END IF;
END $$;

-- The write: menu_eligible on the 46, and nothing else
UPDATE food_curation c
   SET menu_eligible = true
  FROM _46 s
 WHERE c.source_code = s.source_code;

-- Raw output for the record, before the assertions
SELECT c.source_code, f.name_he, c.kosher, c.quality, c.tags, c.allergens,
       c.allergens_reviewed_at, c.menu_eligible, c.prep, c.by_weight, c.whole_only, c.max_g,
       p.updated_at AS updated_before, c.updated_at AS updated_after
  FROM food_curation c JOIN _pre p USING (source_code) JOIN _46 s USING (source_code)
  JOIN foods f ON f.source_code = c.source_code
 ORDER BY c.source_code::int;

SELECT (SELECT count(*) FROM v_recipe_unreviewed_components) AS unreviewed_components,
       (SELECT count(*) FROM v_recipe_inherited_allergens) AS inherited_allergens,
       (SELECT count(*) FROM food_curation WHERE menu_eligible AND 'vegan' = ANY(tags)) AS eligible_vegan;

-- V1 - the 46 now eligible, and exactly 46 rows of the table changed, all of them in _46
DO $$
DECLARE n int; el int; changed int; changed46 int;
BEGIN
  SELECT count(*), count(*) FILTER (WHERE c.menu_eligible)
    INTO n, el
    FROM food_curation c JOIN _46 s USING (source_code);
  SELECT count(*), count(*) FILTER (WHERE c.source_code IN (SELECT source_code FROM _46))
    INTO changed, changed46
    FROM food_curation c JOIN _pre p USING (source_code)
   WHERE (c.category, c.kosher, c.allergens, c.allergens_reviewed_at, c.tags, c.quality, c.supp,
          c.prep, c.by_weight, c.whole_only, c.max_g, c.menu_eligible, c.curated_by, c.curated_at,
          c.created_at, c.updated_at, c.excluded_reason, c.label_source, c.label_date,
          c.fiber_g_label)
         IS DISTINCT FROM
         (p.category, p.kosher, p.allergens, p.allergens_reviewed_at, p.tags, p.quality, p.supp,
          p.prep, p.by_weight, p.whole_only, p.max_g, p.menu_eligible, p.curated_by, p.curated_at,
          p.created_at, p.updated_at, p.excluded_reason, p.label_source, p.label_date,
          p.fiber_g_label);
  IF n <> 46 OR el <> 46 OR changed <> 46 OR changed46 <> 46 THEN
    RAISE EXCEPTION 'V1 failed: n=% eligible=% rows-changed=% of-them-in-46=%', n, el, changed, changed46;
  END IF;
END $$;

-- V2 - on the 46: every column other than menu_eligible and updated_at is identical to _pre - the
-- review, tags, quality, kosher, curated_by and curated_at are 28's and stay; menu_eligible moved
-- false -> true on all 46, and updated_at moved on all 46, through the trigger
DO $$
DECLARE n int; moved int; flipped int; touched int;
BEGIN
  SELECT count(*),
         count(*) FILTER (WHERE
           (c.category, c.kosher, c.allergens, c.allergens_reviewed_at, c.tags, c.quality, c.supp,
            c.prep, c.by_weight, c.whole_only, c.max_g, c.curated_by, c.curated_at, c.created_at,
            c.excluded_reason, c.label_source, c.label_date, c.fiber_g_label)
           IS DISTINCT FROM
           (p.category, p.kosher, p.allergens, p.allergens_reviewed_at, p.tags, p.quality, p.supp,
            p.prep, p.by_weight, p.whole_only, p.max_g, p.curated_by, p.curated_at, p.created_at,
            p.excluded_reason, p.label_source, p.label_date, p.fiber_g_label)),
         count(*) FILTER (WHERE p.menu_eligible = false AND c.menu_eligible = true),
         count(*) FILTER (WHERE c.updated_at > p.updated_at)
    INTO n, moved, flipped, touched
    FROM food_curation c JOIN _pre p USING (source_code) JOIN _46 s USING (source_code);
  IF n <> 46 OR moved <> 0 OR flipped <> 46 OR touched <> 46 THEN
    RAISE EXCEPTION 'V2 failed: n=% untouched-columns-moved=% flipped=% updated_at-moved=%',
      n, moved, flipped, touched;
  END IF;
END $$;

-- V3 - the 434 rows outside the 46 are identical in every column, updated_at included: EXCEPT both
-- ways against _pre, as 28's V3; and the table still holds the 480 rows _pre held
DO $$
DECLARE only_now int; only_pre int; n_pre int; others int; tot int;
BEGIN
  SELECT count(*) INTO only_now FROM (
    SELECT source_code, category, kosher, allergens, allergens_reviewed_at, tags,
         quality, supp, prep, by_weight, whole_only, max_g, menu_eligible,
         curated_by, curated_at, created_at, updated_at, excluded_reason,
         label_source, label_date, fiber_g_label
      FROM food_curation WHERE source_code NOT IN (SELECT source_code FROM _46)
    EXCEPT
    SELECT * FROM _pre WHERE source_code NOT IN (SELECT source_code FROM _46)) x;
  SELECT count(*) INTO only_pre FROM (
    SELECT * FROM _pre WHERE source_code NOT IN (SELECT source_code FROM _46)
    EXCEPT
    SELECT source_code, category, kosher, allergens, allergens_reviewed_at, tags,
         quality, supp, prep, by_weight, whole_only, max_g, menu_eligible,
         curated_by, curated_at, created_at, updated_at, excluded_reason,
         label_source, label_date, fiber_g_label
      FROM food_curation WHERE source_code NOT IN (SELECT source_code FROM _46)) x;
  SELECT count(*), count(*) FILTER (WHERE source_code NOT IN (SELECT source_code FROM _46))
    INTO n_pre, others FROM _pre;
  SELECT count(*) INTO tot FROM food_curation;
  IF n_pre <> 480 OR others <> 434 OR tot <> 480 OR only_now <> 0 OR only_pre <> 0 THEN
    RAISE EXCEPTION 'V3 failed: _pre=% others=% tot=% only_now=% only_pre=%',
      n_pre, others, tot, only_now, only_pre;
  END IF;
END $$;

-- V4 - the six of db/block8_protein_label_codes.txt: still not eligible and unreviewed
DO $$
DECLARE six int; waiting int;
BEGIN
  SELECT count(*),
         count(*) FILTER (WHERE menu_eligible = false AND allergens_reviewed_at IS NULL)
    INTO six, waiting
    FROM food_curation
   WHERE source_code IN ('1796', '1797', '1800', '8865', '8866', '9758');
  IF six <> 6 OR waiting <> 6 THEN
    RAISE EXCEPTION 'V4 failed: six=% not-eligible-and-unreviewed=%', six, waiting;
  END IF;
END $$;

-- V5 - the canonical snapshot afterwards, the safety views, the allergen vocabulary, no eligible
-- row tagged vegan carrying Egg, Milk or Fish (decisions.md, 17.09.2026), and the two recipe
-- views: 27's V4 and V5 in one block. The expected values were measured read-only before this
-- file was written - eligible vegan 182 -> 195, v_recipe_unreviewed_components 31 -> 72,
-- v_recipe_inherited_allergens 488
DO $$
DECLARE tot int; el int; p int; f int; c int; v int; vm int; mt int; orph int; off_vocab int;
        vegan_bad int; vegan_el int; unrev int; inh int;
BEGIN
  SELECT count(*), count(*) FILTER (WHERE menu_eligible),
         count(*) FILTER (WHERE menu_eligible AND category = 'protein'),
         count(*) FILTER (WHERE menu_eligible AND category = 'fat'),
         count(*) FILTER (WHERE menu_eligible AND category = 'carb'),
         count(*) FILTER (WHERE menu_eligible AND category = 'veg')
    INTO tot, el, p, f, c, v FROM food_curation;
  SELECT count(*) INTO vm   FROM v_menu_foods;
  SELECT count(*) INTO mt   FROM v_eligible_missing_tags;
  SELECT count(*) INTO orph FROM v_curation_orphans;
  SELECT count(*) INTO off_vocab FROM food_curation, unnest(allergens) AS a
   WHERE a NOT IN ('Egg','Fish','Gluten','Milk','Peanuts','Sesame','Soy','Tree nuts');
  SELECT count(*) FILTER (WHERE allergens && '{Egg,Milk,Fish}'::text[]), count(*)
    INTO vegan_bad, vegan_el
    FROM food_curation WHERE menu_eligible AND 'vegan' = ANY(tags);
  SELECT count(*) INTO unrev FROM v_recipe_unreviewed_components;
  SELECT count(*) INTO inh   FROM v_recipe_inherited_allergens;
  IF tot<>480 OR el<>319 OR p<>154 OR f<>43 OR c<>44 OR v<>78 OR vm<>319 OR mt<>0 OR orph<>0
     OR off_vocab<>0 OR vegan_bad<>0 OR vegan_el<>195 OR unrev<>72 OR inh<>488 THEN
    RAISE EXCEPTION 'V5 failed: tot=% el=% p=% f=% c=% v=% view=% missing_tags=% orphans=% off-vocabulary=% eligible-vegan-with-Egg/Milk/Fish=% eligible-vegan=% unreviewed-components=% inherited-allergens=%',
      tot, el, p, f, c, v, vm, mt, orph, off_vocab, vegan_bad, vegan_el, unrev, inh;
  END IF;
END $$;

COMMIT;
