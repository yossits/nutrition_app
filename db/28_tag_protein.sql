-- Block 8ח-ח — protein tagging: 52 new food_curation rows, none menu_eligible.
-- The lists are db/block8_protein_codes.txt (46, the flip list of 29) and
-- db/block8_protein_label_codes.txt (6 branded meat substitutes, label condition: tagged here and
-- never flipped in 29; 7מ after #56). V0 proves that none of the 52 has a curation row today.
--
-- Values per 8ח-ו and 8ח-ז (docs/work/2026-09-20-block-8-protein.md, the table of section
-- "חלבון - 8ח-ו ו-8ח-ז"; docs/decisions.md 21.09.2026, rows 3 and 4). The VALUES were generated
-- by a script from that table, not typed, and every name was checked against foods and against
-- the two tagging sheets of 8ח-ה before this file was written.
--
-- Unlike 26, the allergen review is written here and not in the flip: allergens and
-- allergens_reviewed_at = now() on the 46. The 6 stay unreviewed - allergens '{}',
-- allergens_reviewed_at NULL - because only their label can tell (10126 and 1791), and tags carry
-- no vegan for the same reason. 29 then sets menu_eligible on the 46 and nothing else.
-- 'vegetarian' is not in the tag vocabulary - the only tag in use is 'vegan' - so the seven rows
-- the chat marked (v) carry '{}'. kosher follows 8ח-ד: 1667 is dairy (samna in its components).
-- whole_only_requires_a_unit (db/01_food_db_schema.sql) forbids by_weight together with
-- whole_only; no row here has both, and V4 asserts it over the whole table.
--
-- No row becomes eligible here. Expected canonical snapshot afterwards:
--   480 · 273 · 108 · 43 · 44 · 78 · 273 · 0 · 0
-- V0 pins the snapshot this file was written against, so a second run fails before it writes.

BEGIN;

CREATE TEMP TABLE _pre ON COMMIT DROP AS
  SELECT source_code, category, kosher, allergens, allergens_reviewed_at, tags,
         quality, supp, prep, by_weight, whole_only, max_g, menu_eligible,
         curated_by, curated_at, created_at, updated_at, excluded_reason,
         label_source, label_date, fiber_g_label
    FROM food_curation;

-- The 52 codes with the name each one carries in foods; flip = the 46 of the flip list
CREATE TEMP TABLE _52 (source_code text PRIMARY KEY, name_he text NOT NULL,
                       flip boolean NOT NULL) ON COMMIT DROP;
INSERT INTO _52 (source_code, name_he, flip) VALUES
    ('1000'  , 'בשר הודו, לבן או אדום, מבושל, נאכל ללא עור', true ),
    ('1012'  , 'בשר הודו, שוק, מבושל, נאכל ללא עור', true ),
    ('945'   , 'בשר הודו לבן, מבושל, נאכל עם עור', true ),
    ('801'   , 'בשר עוף, חזה, ללא עצם, בגריל, נאכל עם עור', true ),
    ('806'   , 'בשר עוף, חזה, ללא עצם, מבושל, נאכל עם עור', true ),
    ('855'   , 'בשר עוף, שוק, ללא עצם, מבושל, נאכל עם עור', true ),
    ('863'   , 'בשר עוף, שוק, ללא עצם, מטוגן, ללא ציפוי, נאכל ללא עור', true ),
    ('871'   , 'בשר עוף, ירך, ללא עצם, בגריל, נאכל עם עור', true ),
    ('885'   , 'בשר עוף, ירך, ללא עצם, מטוגן, ללא ציפוי, נאכל עם עור', true ),
    ('891'   , 'בשר עוף, כנף, ללא עצם, בגריל, נאכל עם עור', true ),
    ('1337'  , 'דג פורל, מעושן', true ),
    ('1241'  , 'דג מקרל, מעושן', true ),
    ('8509'  , 'דג סרדין סטאר בשמן סויה או שמן זית, יונה', true ),
    ('1316'  , 'דג סרדין, בגריל, ללא עצמות', true ),
    ('1269'  , 'דג נסיכת הנילוס מבושל', true ),
    ('1294'  , 'דג פרידה מטוגן ללא שמן, ללא בלילה', true ),
    ('9634'  , 'דג אמנון-מושט, מטוגן ללא שמן, ללא בלילה', true ),
    ('1336'  , 'דג פורל, מבושל במים או באדים, עם מלח', true ),
    ('9784'  , 'דג דניס בגריל, ללא ציפוי, ללא שמן', true ),
    ('751'   , 'בשר עגל, לפנ לנתח, מבושל, נאכל ללא שומן', true ),
    ('628'   , 'בשר בקר, צלי, מאודה או מבושל, נאכל ללא שומן', true ),
    ('725'   , 'בשר כבש, נתחים שונים, אפוי בתנור', true ),
    ('614'   , 'סטייק בשר בקר, מטוגן, נאכל עם שומן', true ),
    ('777'   , 'שניצל בשר עגל, מצופה או מקומח, מטוגן, נאכל עם שומן', true ),
    ('627'   , 'בשר בקר, גולש, מבושל, בשר בלבד', true ),
    ('776'   , 'בשר עגל, סטייק, מבושל', true ),
    ('8609'  , 'גבינה צהובה 15% שומן, עמק', true ),
    ('431'   , 'גבינה צהובה 22%  שומן, גלבוע, טרה, תנובה', true ),
    ('520'   , 'גבינה לבנה 5% שומן, טבורוג ללא תוספת מלח, צוריאל', true ),
    ('503'   , 'גבינת קוטג'' 5%, שטראוס', true ),
    ('496'   , 'גבינת קוטג'' 9%  שומן, תנובה', true ),
    ('1625'  , 'פול מטוגן בנוסח מצרי', true ),
    ('1605'  , 'שעועית לבנה יבשה מבושלת עם מלח, ללא תוספת שומן בבישול', true ),
    ('1624'  , 'שעועית לימה יבשה מבושלת ללא תוספת שמן', true ),
    ('1617'  , 'פול טרי מבושל, ללא תוספת שומן בבישול, עם מלח', true ),
    ('8305'  , 'שעועית אדומה מבושלת, מקפוא, סנפרוסט', true ),
    ('8261'  , 'שעועית שחורה, מבושלת, ללא תוספת מלח ושומן בבישול', true ),
    ('1629'  , 'פול יבש, מבושל', true ),
    ('1688'  , 'טופו מטוגן בשמן זית', true ),
    ('1711'  , 'קציצות טופו וירקות אפויות', true ),
    ('1606'  , 'סלט שעועית לבנה עם פטרוזיליה ומיץ לימון, ללא תוספת שמן', true ),
    ('1667'  , 'וואט עדשים אתיופי', true ),
    ('1623'  , 'פול טרי מבושל עם שמן זית', true ),
    ('9182'  , 'עדשים מבושלים עם בצל ושמן קנולה', true ),
    ('1663'  , 'אליצ''ה אפונה אתיופי', true ),
    ('1608'  , 'שעועית לבנה מבושלת ברסק עגבניות ושמן זית', true ),
    ('1796'  , 'שניצל מן הצומח, זוגלובק', false),
    ('1800'  , 'שניצל מן הצומח, סנפרוסט, טבעול', false),
    ('9758'  , 'חזה בגריל, מן הצומח, מופחת שומן/90, טבעול', false),
    ('1797'  , 'המבורגר, בורגר מן הצומח, טבע דלי', false),
    ('8865'  , 'שניצל דק מן הצומח, ביתי/צ''ילי חריף, טבעול', false),
    ('8866'  , 'שניצלונים מן הצומח, סוי ג''וי', false);

-- V0 — precondition and rerun guard: the snapshot this file expects; all 52 exist in foods
-- under the name the script checked; none has a curation row; 46 are on the flip list
DO $$
DECLARE tot int; el int; p int; f int; c int; v int; vm int; mt int; orph int;
        n52 int; named int; present int; fl int;
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
  SELECT count(*), count(*) FILTER (WHERE flip) INTO n52, fl FROM _52;
  SELECT count(*) FILTER (WHERE fd.name_he = s.name_he)
    INTO named FROM _52 s JOIN foods fd ON fd.source_code = s.source_code;
  SELECT count(*) INTO present
    FROM _52 s JOIN food_curation cu ON cu.source_code = s.source_code;
  IF tot<>428 OR el<>273 OR p<>108 OR f<>43 OR c<>44 OR v<>78 OR vm<>273 OR mt<>0 OR orph<>0
     OR n52<>52 OR named<>52 OR present<>0 OR fl<>46 THEN
    RAISE EXCEPTION 'V0 failed: tot=% el=% p=% f=% c=% v=% view=% missing_tags=% orphans=% · n52=% named=% present=% flip=%',
      tot, el, p, f, c, v, vm, mt, orph, n52, named, present, fl;
  END IF;
END $$;

-- The write — 52 rows. Column order:
--   source_code, category, kosher, allergens, allergens_reviewed_at, tags, quality, supp, prep,
--   by_weight, whole_only, max_g, menu_eligible, excluded_reason, curated_by, curated_at
INSERT INTO food_curation
  (source_code, category, kosher, allergens, allergens_reviewed_at, tags, quality, supp, prep,
   by_weight, whole_only, max_g, menu_eligible, excluded_reason, curated_by, curated_at)
VALUES
  ('1000'  , 'protein', 'meat' , '{}'                , now(), '{}'     , 3, false, 2, false, false, 175, false, NULL, 'yossi', now()),  -- בשר הודו, לבן או אדום, מבושל, נאכל ללא עור
  ('1012'  , 'protein', 'meat' , '{}'                , now(), '{}'     , 3, false, 2, true , false, 175, false, NULL, 'yossi', now()),  -- בשר הודו, שוק, מבושל, נאכל ללא עור
  ('945'   , 'protein', 'meat' , '{}'                , now(), '{}'     , 3, false, 2, false, false, 175, false, NULL, 'yossi', now()),  -- בשר הודו לבן, מבושל, נאכל עם עור
  ('801'   , 'protein', 'meat' , '{}'                , now(), '{}'     , 3, false, 2, false, false, 175, false, NULL, 'yossi', now()),  -- בשר עוף, חזה, ללא עצם, בגריל, נאכל עם עור
  ('806'   , 'protein', 'meat' , '{}'                , now(), '{}'     , 3, false, 2, false, false, 175, false, NULL, 'yossi', now()),  -- בשר עוף, חזה, ללא עצם, מבושל, נאכל עם עור
  ('855'   , 'protein', 'meat' , '{}'                , now(), '{}'     , 3, false, 2, false, true , 175, false, NULL, 'yossi', now()),  -- בשר עוף, שוק, ללא עצם, מבושל, נאכל עם עור
  ('863'   , 'protein', 'meat' , '{}'                , now(), '{}'     , 3, false, 2, false, true , 175, false, NULL, 'yossi', now()),  -- בשר עוף, שוק, ללא עצם, מטוגן, ללא ציפוי, נאכל ללא עור
  ('871'   , 'protein', 'meat' , '{}'                , now(), '{}'     , 3, false, 2, false, true , 175, false, NULL, 'yossi', now()),  -- בשר עוף, ירך, ללא עצם, בגריל, נאכל עם עור
  ('885'   , 'protein', 'meat' , '{}'                , now(), '{}'     , 3, false, 2, false, true , 175, false, NULL, 'yossi', now()),  -- בשר עוף, ירך, ללא עצם, מטוגן, ללא ציפוי, נאכל עם עור
  ('891'   , 'protein', 'meat' , '{}'                , now(), '{}'     , 3, false, 2, false, true , 175, false, NULL, 'yossi', now()),  -- בשר עוף, כנף, ללא עצם, בגריל, נאכל עם עור
  ('1337'  , 'protein', 'parve', '{Fish}'            , now(), '{}'     , 3, false, 0, true , false, 100, false, NULL, 'yossi', now()),  -- דג פורל, מעושן
  ('1241'  , 'protein', 'parve', '{Fish}'            , now(), '{}'     , 3, false, 0, false, true , 100, false, NULL, 'yossi', now()),  -- דג מקרל, מעושן
  ('8509'  , 'protein', 'parve', '{Fish,Soy}'        , now(), '{}'     , 3, false, 0, false, true , 130, false, NULL, 'yossi', now()),  -- דג סרדין סטאר בשמן סויה או שמן זית, יונה
  ('1316'  , 'protein', 'parve', '{Fish}'            , now(), '{}'     , 3, false, 2, true , false, 175, false, NULL, 'yossi', now()),  -- דג סרדין, בגריל, ללא עצמות
  ('1269'  , 'protein', 'parve', '{Fish}'            , now(), '{}'     , 3, false, 2, false, false, 175, false, NULL, 'yossi', now()),  -- דג נסיכת הנילוס מבושל
  ('1294'  , 'protein', 'parve', '{Fish}'            , now(), '{}'     , 3, false, 2, false, false, 175, false, NULL, 'yossi', now()),  -- דג פרידה מטוגן ללא שמן, ללא בלילה
  ('9634'  , 'protein', 'parve', '{Fish}'            , now(), '{}'     , 3, false, 2, true , false, 175, false, NULL, 'yossi', now()),  -- דג אמנון-מושט, מטוגן ללא שמן, ללא בלילה
  ('1336'  , 'protein', 'parve', '{Fish}'            , now(), '{}'     , 3, false, 2, true , false, 175, false, NULL, 'yossi', now()),  -- דג פורל, מבושל במים או באדים, עם מלח
  ('9784'  , 'protein', 'parve', '{Fish}'            , now(), '{}'     , 3, false, 2, true , false, 175, false, NULL, 'yossi', now()),  -- דג דניס בגריל, ללא ציפוי, ללא שמן
  ('751'   , 'protein', 'meat' , '{}'                , now(), '{}'     , 3, false, 2, true , false, 175, false, NULL, 'yossi', now()),  -- בשר עגל, לפנ לנתח, מבושל, נאכל ללא שומן
  ('628'   , 'protein', 'meat' , '{}'                , now(), '{}'     , 3, false, 2, false, false, 175, false, NULL, 'yossi', now()),  -- בשר בקר, צלי, מאודה או מבושל, נאכל ללא שומן
  ('725'   , 'protein', 'meat' , '{}'                , now(), '{}'     , 3, false, 2, false, false, 175, false, NULL, 'yossi', now()),  -- בשר כבש, נתחים שונים, אפוי בתנור
  ('614'   , 'protein', 'meat' , '{}'                , now(), '{}'     , 3, false, 2, false, false, 175, false, NULL, 'yossi', now()),  -- סטייק בשר בקר, מטוגן, נאכל עם שומן
  ('777'   , 'protein', 'meat' , '{Egg,Gluten}'      , now(), '{}'     , 3, false, 2, true , false, 175, false, NULL, 'yossi', now()),  -- שניצל בשר עגל, מצופה או מקומח, מטוגן, נאכל עם שומן
  ('627'   , 'protein', 'meat' , '{}'                , now(), '{}'     , 3, false, 2, false, false, 175, false, NULL, 'yossi', now()),  -- בשר בקר, גולש, מבושל, בשר בלבד
  ('776'   , 'protein', 'meat' , '{}'                , now(), '{}'     , 3, false, 2, true , false, 175, false, NULL, 'yossi', now()),  -- בשר עגל, סטייק, מבושל
  ('8609'  , 'protein', 'dairy', '{Milk}'            , now(), '{}'     , 3, false, 0, false, true , 100, false, NULL, 'yossi', now()),  -- גבינה צהובה 15% שומן, עמק
  ('431'   , 'protein', 'dairy', '{Milk}'            , now(), '{}'     , 3, false, 0, false, true , 100, false, NULL, 'yossi', now()),  -- גבינה צהובה 22%  שומן, גלבוע, טרה, תנובה
  ('520'   , 'protein', 'dairy', '{Milk}'            , now(), '{}'     , 3, false, 0, true , false, 100, false, NULL, 'yossi', now()),  -- גבינה לבנה 5% שומן, טבורוג ללא תוספת מלח, צוריאל
  ('503'   , 'protein', 'dairy', '{Milk}'            , now(), '{}'     , 3, false, 0, true , false, 250, false, NULL, 'yossi', now()),  -- גבינת קוטג' 5%, שטראוס
  ('496'   , 'protein', 'dairy', '{Milk}'            , now(), '{}'     , 3, false, 0, true , false, 250, false, NULL, 'yossi', now()),  -- גבינת קוטג' 9%  שומן, תנובה
  ('1625'  , 'protein', 'parve', '{}'                , now(), '{vegan}', 1, false, 0, true , false,  60, false, NULL, 'yossi', now()),  -- פול מטוגן בנוסח מצרי
  ('1605'  , 'protein', 'parve', '{}'                , now(), '{vegan}', 1, false, 2, true , false, 200, false, NULL, 'yossi', now()),  -- שעועית לבנה יבשה מבושלת עם מלח, ללא תוספת שומן בבישול
  ('1624'  , 'protein', 'parve', '{}'                , now(), '{vegan}', 1, false, 2, true , false, 200, false, NULL, 'yossi', now()),  -- שעועית לימה יבשה מבושלת ללא תוספת שמן
  ('1617'  , 'protein', 'parve', '{}'                , now(), '{vegan}', 1, false, 2, true , false, 200, false, NULL, 'yossi', now()),  -- פול טרי מבושל, ללא תוספת שומן בבישול, עם מלח
  ('8305'  , 'protein', 'parve', '{}'                , now(), '{vegan}', 1, false, 1, true , false, 200, false, NULL, 'yossi', now()),  -- שעועית אדומה מבושלת, מקפוא, סנפרוסט
  ('8261'  , 'protein', 'parve', '{}'                , now(), '{vegan}', 1, false, 2, true , false, 200, false, NULL, 'yossi', now()),  -- שעועית שחורה, מבושלת, ללא תוספת מלח ושומן בבישול
  ('1629'  , 'protein', 'parve', '{}'                , now(), '{vegan}', 1, false, 2, true , false, 200, false, NULL, 'yossi', now()),  -- פול יבש, מבושל
  ('1688'  , 'protein', 'parve', '{Soy}'             , now(), '{vegan}', 2, false, 2, false, false, 150, false, NULL, 'yossi', now()),  -- טופו מטוגן בשמן זית
  ('1711'  , 'protein', 'parve', '{Egg,Gluten,Soy}'  , now(), '{}'     , 2, false, 2, false, true , 150, false, NULL, 'yossi', now()),  -- קציצות טופו וירקות אפויות
  ('1606'  , 'protein', 'parve', '{}'                , now(), '{vegan}', 1, false, 2, true , false, 200, false, NULL, 'yossi', now()),  -- סלט שעועית לבנה עם פטרוזיליה ומיץ לימון, ללא תוספת שמן
  ('1667'  , 'protein', 'dairy', '{Milk}'            , now(), '{}'     , 1, false, 2, true , false, 200, false, NULL, 'yossi', now()),  -- וואט עדשים אתיופי
  ('1623'  , 'protein', 'parve', '{}'                , now(), '{vegan}', 1, false, 2, true , false, 200, false, NULL, 'yossi', now()),  -- פול טרי מבושל עם שמן זית
  ('9182'  , 'protein', 'parve', '{}'                , now(), '{vegan}', 1, false, 2, true , false, 200, false, NULL, 'yossi', now()),  -- עדשים מבושלים עם בצל ושמן קנולה
  ('1663'  , 'protein', 'parve', '{}'                , now(), '{vegan}', 1, false, 2, true , false, 200, false, NULL, 'yossi', now()),  -- אליצ'ה אפונה אתיופי
  ('1608'  , 'protein', 'parve', '{}'                , now(), '{vegan}', 1, false, 2, true , false, 200, false, NULL, 'yossi', now()),  -- שעועית לבנה מבושלת ברסק עגבניות ושמן זית
  ('1796'  , 'protein', 'parve', '{}'                , NULL , '{}'     , 2, false, 1, false, true , 150, false, NULL, 'yossi', now()),  -- שניצל מן הצומח, זוגלובק
  ('1800'  , 'protein', 'parve', '{}'                , NULL , '{}'     , 2, false, 1, false, true , 150, false, NULL, 'yossi', now()),  -- שניצל מן הצומח, סנפרוסט, טבעול
  ('9758'  , 'protein', 'parve', '{}'                , NULL , '{}'     , 2, false, 1, false, true , 150, false, NULL, 'yossi', now()),  -- חזה בגריל, מן הצומח, מופחת שומן/90, טבעול
  ('1797'  , 'protein', 'parve', '{}'                , NULL , '{}'     , 2, false, 1, false, true , 150, false, NULL, 'yossi', now()),  -- המבורגר, בורגר מן הצומח, טבע דלי
  ('8865'  , 'protein', 'parve', '{}'                , NULL , '{}'     , 2, false, 1, true , false, 150, false, NULL, 'yossi', now()),  -- שניצל דק מן הצומח, ביתי/צ'ילי חריף, טבעול
  ('8866'  , 'protein', 'parve', '{}'                , NULL , '{}'     , 2, false, 1, true , false, 150, false, NULL, 'yossi', now());  -- שניצלונים מן הצומח, סוי ג'וי

-- Raw output for the record, before the assertions
SELECT c.source_code, f.name_he, c.kosher, c.allergens, c.allergens_reviewed_at IS NOT NULL AS reviewed,
       c.tags, c.quality, c.prep, c.by_weight, c.whole_only, c.max_g, c.menu_eligible
  FROM food_curation c JOIN foods f ON f.source_code = c.source_code
  JOIN _52 s ON s.source_code = c.source_code
 ORDER BY c.source_code::int;

-- V1 — exactly 52 rows added, none removed, and the added set is exactly _52
DO $$
DECLARE tot int; added int; removed int; not_listed int; listed_missing int;
BEGIN
  SELECT count(*) INTO tot FROM food_curation;
  SELECT count(*) INTO added
    FROM food_curation c WHERE NOT EXISTS (SELECT 1 FROM _pre p WHERE p.source_code = c.source_code);
  SELECT count(*) INTO removed
    FROM _pre p WHERE NOT EXISTS (SELECT 1 FROM food_curation c WHERE c.source_code = p.source_code);
  SELECT count(*) INTO not_listed FROM (
    SELECT c.source_code FROM food_curation c
     WHERE NOT EXISTS (SELECT 1 FROM _pre p WHERE p.source_code = c.source_code)
    EXCEPT SELECT source_code FROM _52) x;
  SELECT count(*) INTO listed_missing FROM (
    SELECT source_code FROM _52
    EXCEPT SELECT c.source_code FROM food_curation c
     WHERE NOT EXISTS (SELECT 1 FROM _pre p WHERE p.source_code = c.source_code)) x;
  IF tot <> 480 OR added <> 52 OR removed <> 0 OR not_listed <> 0 OR listed_missing <> 0 THEN
    RAISE EXCEPTION 'V1 failed: tot=% added=% removed=% not_listed=% listed_missing=%',
      tot, added, removed, not_listed, listed_missing;
  END IF;
END $$;

-- V2 — the 52 as a group: not eligible, protein, supp false, no exclusion, curated by yossi, no
-- label fields; ready for 29 (kosher, quality, prep, by_weight set); reviewed exactly on the 46,
-- and the 6 unreviewed with '{}' and no vegan. The values themselves are checked outside this
-- file, against the journal table (lesson 51): this block cannot see the source it was made from.
DO $$
DECLARE n int; off int; not_ready int; rev46 int; unrev6 int;
BEGIN
  SELECT count(*),
         count(*) FILTER (WHERE NOT (c.menu_eligible = false AND c.category = 'protein'
                              AND c.supp = false AND c.excluded_reason IS NULL
                              AND c.curated_by = 'yossi' AND c.curated_at IS NOT NULL
                              AND c.label_source IS NULL AND c.label_date IS NULL
                              AND c.fiber_g_label IS NULL)),
         count(*) FILTER (WHERE c.kosher IS NULL OR c.quality IS NULL OR c.prep IS NULL
                              OR c.by_weight IS NULL OR c.max_g IS NULL)
    INTO n, off, not_ready
    FROM food_curation c JOIN _52 s ON s.source_code = c.source_code;
  SELECT count(*) INTO rev46
    FROM food_curation c JOIN _52 s ON s.source_code = c.source_code
   WHERE s.flip AND c.allergens_reviewed_at IS NOT NULL;
  SELECT count(*) INTO unrev6
    FROM food_curation c JOIN _52 s ON s.source_code = c.source_code
   WHERE NOT s.flip AND c.allergens_reviewed_at IS NULL AND c.allergens = '{}'::text[]
     AND NOT ('vegan' = ANY (c.tags));
  IF n <> 52 OR off <> 0 OR not_ready <> 0 OR rev46 <> 46 OR unrev6 <> 6 THEN
    RAISE EXCEPTION 'V2 failed: n=% off-spec=% not-ready=% reviewed46=% unreviewed6=%',
      n, off, not_ready, rev46, unrev6;
  END IF;
END $$;

-- V3 — the 428 rows that were there are identical in every column, updated_at included:
-- EXCEPT both ways against _pre, as 24's V4
DO $$
DECLARE only_now int; only_pre int; n_pre int;
BEGIN
  SELECT count(*) INTO only_now FROM (
    SELECT source_code, category, kosher, allergens, allergens_reviewed_at, tags,
         quality, supp, prep, by_weight, whole_only, max_g, menu_eligible,
         curated_by, curated_at, created_at, updated_at, excluded_reason,
         label_source, label_date, fiber_g_label
      FROM food_curation WHERE source_code NOT IN (SELECT source_code FROM _52)
    EXCEPT
    SELECT * FROM _pre) x;
  SELECT count(*) INTO only_pre FROM (
    SELECT * FROM _pre
    EXCEPT
    SELECT source_code, category, kosher, allergens, allergens_reviewed_at, tags,
         quality, supp, prep, by_weight, whole_only, max_g, menu_eligible,
         curated_by, curated_at, created_at, updated_at, excluded_reason,
         label_source, label_date, fiber_g_label
      FROM food_curation WHERE source_code NOT IN (SELECT source_code FROM _52)) x;
  SELECT count(*) INTO n_pre FROM _pre;
  IF n_pre <> 428 OR only_now <> 0 OR only_pre <> 0 THEN
    RAISE EXCEPTION 'V3 failed: _pre=% only_now=% only_pre=%', n_pre, only_now, only_pre;
  END IF;
END $$;

-- V4 — no row in the table violates whole_only_requires_a_unit
DO $$
DECLARE both_set int;
BEGIN
  SELECT count(*) INTO both_set FROM food_curation WHERE whole_only AND by_weight;
  IF both_set <> 0 THEN
    RAISE EXCEPTION 'V4 failed: % rows carry whole_only and by_weight together', both_set;
  END IF;
END $$;

-- V5 — counts afterwards: 52 more rows, eligibility untouched, the views unchanged
DO $$
DECLARE tot int; el int; p int; f int; c int; v int; vm int; mt int; orph int;
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
  IF tot<>480 OR el<>273 OR p<>108 OR f<>43 OR c<>44 OR v<>78 OR vm<>273 OR mt<>0 OR orph<>0 THEN
    RAISE EXCEPTION 'V5 failed: tot=% el=% p=% f=% c=% v=% view=% missing_tags=% orphans=%',
      tot, el, p, f, c, v, vm, mt, orph;
  END IF;
END $$;

COMMIT;
