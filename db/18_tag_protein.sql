-- Block 5ז — protein tagging: 130 new food_curation rows, tagged and NOT yet menu_eligible.
-- The list is db/block5_protein_codes.txt (141, the block-4 "yes" list) minus the 11
-- curated in 3ד and 3ח (494 500 805 944 1267 1347 8221 8608 8712 8840 9793), which
-- are not touched — V3 proves it.
-- Values per docs/work/2026-09-11-block-5-tagging.md (the owner's table and
-- exception groups of 11.09.2026) and docs/decisions.md 11.09.2026: quality by
-- §5.3, max_g by family with per-item exceptions, prep 0 ready · 1 heat or quick ·
-- 2 cooking required. kosher is 11's family proposal from the 5f-a sheet
-- (_scratch/block-5f/tagging_protein141.tsv, sha256 169f1475…) with one
-- override, 8547 pea protein = parve. by_weight and whole_only as that sheet
-- printed them: by_weight true on eleven (258 923 926 1698 8547 8625 9560 9589 9650 9768 9851),
-- whole_only true on 46. supp true on the five powders. tags {vegan} on the 28
-- plant items, {} on the animal ones. Allergens deliberately UNREVIEWED
-- (column default '{}', allergens_reviewed_at NULL) — block 6ח reviews them.
-- curated_by 'yossi', curated_at now(), mirroring the existing rows.
-- Counts asserted in V2: kosher meat 56 · dairy 23 · parve 51; quality 3/2/1 =
-- 102/19/9; prep 0/1/2 = 40/22/68; max_g 60×6 · 150×20 · 100×20 · 250×6 · 75×5 ·
-- 200×7 · 180×3 · 130 · 112 · 351 · 214 · 30 · 175×58.
-- Same pattern as 16_tag_fat.sql: one transaction, a _pre snapshot of every
-- column, one INSERT, assertions, COMMIT. V0 pins the snapshot this file was
-- written against, so a second run fails before it touches anything.
-- Expected canonical snapshot afterwards: 309 · 56 · 11 · 37 · 4 · 4 · 56 · 0 · 0.

BEGIN;

CREATE TEMP TABLE _pre ON COMMIT DROP AS
  SELECT source_code, category, kosher, allergens, allergens_reviewed_at, tags,
         quality, supp, prep, by_weight, whole_only, max_g, menu_eligible,
         curated_by, curated_at, created_at, updated_at, excluded_reason
    FROM food_curation;

-- V0 — precondition: the snapshot this file expects, and none of the 130 has a
-- curation row yet
DO $$
DECLARE tot int; el int; f int; vm int; present int;
BEGIN
  SELECT count(*), count(*) FILTER (WHERE menu_eligible),
         count(*) FILTER (WHERE menu_eligible AND category = 'fat')
    INTO tot, el, f FROM food_curation;
  SELECT count(*) INTO vm FROM v_menu_foods;
  SELECT count(*) INTO present FROM food_curation
   WHERE source_code IN ('258', '420', '446', '472', '499', '504', '508', '522',
                         '533', '539', '556', '561', '562', '572', '609', '615',
                         '619', '623', '624', '625', '626', '636', '649', '653',
                         '661', '662', '663', '670', '675', '680', '681', '683',
                         '717', '721', '729', '772', '780', '781', '782', '788',
                         '799', '802', '807', '825', '834', '838', '841', '846',
                         '856', '873', '880', '886', '889', '892', '894', '910',
                         '923', '926', '928', '941', '943', '963', '1040', '1152',
                         '1182', '1206', '1223', '1277', '1296', '1298', '1307', '1308',
                         '1311', '1332', '1340', '1360', '1561', '1564', '1565', '1566',
                         '1573', '1574', '1575', '1630', '1632', '1638', '1653', '1661',
                         '1669', '1674', '1679', '1698', '1704', '1724', '1790', '1791',
                         '1792', '1805', '1810', '8186', '8188', '8229', '8260', '8274',
                         '8506', '8547', '8584', '8598', '8601', '8604', '8605', '8625',
                         '8690', '8696', '8741', '8804', '8837', '8868', '9516', '9535',
                         '9560', '9589', '9635', '9650', '9717', '9768', '9851', '10126',
                         '10141', '10142');
  IF tot <> 179 OR el <> 56 OR f <> 37 OR vm <> 56 OR present <> 0 THEN
    RAISE EXCEPTION 'V0 failed: tot=% el=% f=% view=% of the 130 already present=%',
      tot, el, f, vm, present;
  END IF;
END $$;

-- The one write. Column order:
--   source_code, category, kosher, tags, quality, supp, prep,
--   by_weight, whole_only, max_g, menu_eligible, excluded_reason, curated_by, curated_at
-- allergens and allergens_reviewed_at are omitted on purpose (default '{}', NULL).
INSERT INTO food_curation
  (source_code, category, kosher, tags, quality, supp, prep,
   by_weight, whole_only, max_g, menu_eligible, excluded_reason, curated_by, curated_at)
VALUES
  -- seitan & wheat gluten
  ('9851', 'protein', 'parve', '{vegan}', 1, false, 1, true , false, 150, false, NULL, 'yossi', now()),  -- סייטן, טבע דלי
  -- protein powders
  ('1724', 'protein', 'parve', '{vegan}', 2, true , 0, false, false,  60, false, NULL, 'yossi', now()),  -- סויה, חלבון סויה ISOLATE
  ('8274', 'protein', 'parve', '{vegan}', 2, true , 0, false, false,  60, false, NULL, 'yossi', now()),  -- סויה, חלבון סויה מרוכז, CONCENTRATE
  ('8547', 'protein', 'parve', '{vegan}', 1, true , 0, true , false,  60, false, NULL, 'yossi', now()),  -- חלבון, אפונה, PEA PROTEIN
  ('258', 'protein', 'dairy',      '{}', 3, true , 0, true , false,  60, false, NULL, 'yossi', now()),  -- תוסף חלבון, EASY WHEY, אבקה, איזיליין
  ('9560', 'protein', 'dairy',      '{}', 3, true , 0, true , false,  60, false, NULL, 'yossi', now()),  -- תמ"י, חלבון מי גבינה הדסה, אבקה, טעמים שונים
  -- eggs
  ('1564', 'protein', 'parve',      '{}', 3, false, 1, false, true , 150, false, NULL, 'yossi', now()),  -- ביצה קשה שלמה, ללא קליפה, עם מלח
  ('1566', 'protein', 'parve',      '{}', 3, false, 1, false, true , 150, false, NULL, 'yossi', now()),  -- ביצה רכה שלמה, ללא קליפה
  ('1561', 'protein', 'parve',      '{}', 3, false, 2, false, true , 150, false, NULL, 'yossi', now()),  -- ביצה שלמה בלי קליפה
  ('1565', 'protein', 'parve',      '{}', 3, false, 2, false, true , 150, false, NULL, 'yossi', now()),  -- ביצה פלוס ,מועשרת באומגה 3, ללא קליפה
  ('1575', 'protein', 'parve',      '{}', 3, false, 1, false, true , 150, false, NULL, 'yossi', now()),  -- ביצה חלבון מבושל, עם מלח
  ('1574', 'protein', 'parve',      '{}', 3, false, 2, false, true , 150, false, NULL, 'yossi', now()),  -- ביצה חלבון לא מבושל
  ('1573', 'protein', 'parve',      '{}', 3, false, 2, false, false, 150, false, NULL, 'yossi', now()),  -- ביצה או חביתה מטוגנת ללא שמן
  -- poultry
  ('807', 'protein', 'meat',      '{}', 3, false, 2, false, true , 175, false, NULL, 'yossi', now()),  -- בשר עוף, חזה, ללא עצם, מבושל, נאכל ללא עור
  ('799', 'protein', 'meat',      '{}', 3, false, 2, false, true , 175, false, NULL, 'yossi', now()),  -- בשר עוף, חזה, ללא עצם, לפנ לשיטת הבישול, נאכל ללא עור
  ('825', 'protein', 'meat',      '{}', 3, false, 2, false, true , 175, false, NULL, 'yossi', now()),  -- בשר עוף, חזה מטוגן ללא שמן
  ('802', 'protein', 'meat',      '{}', 3, false, 1, false, true , 175, false, NULL, 'yossi', now()),  -- בשר עוף, חזה בגריל, כולל רצועות, שישליק, מאמא עוף
  ('788', 'protein', 'meat',      '{}', 3, false, 2, false, false, 175, false, NULL, 'yossi', now()),  -- בשר עוף, לפנ לחלק, ללא עצם, צלוי, נאכל ללא עור
  ('8837', 'protein', 'meat',      '{}', 3, false, 2, false, false, 175, false, NULL, 'yossi', now()),  -- בשר עוף, נאכל ללא העור, לפנ לחלק או לשיטת הבישול
  ('8625', 'protein', 'meat',      '{}', 3, false, 2, true , false, 175, false, NULL, 'yossi', now()),  -- בשר עוף, חזה/פילה בתיבול גריל/ על האש 2.5-3% שומן, מאמא עוף
  ('834', 'protein', 'meat',      '{}', 3, false, 2, false, true , 175, false, NULL, 'yossi', now()),  -- בשר עוף, רגל, שוק וירך, ללא עור, ללא עצם, לפנ לשיטת הבישול
  ('838', 'protein', 'meat',      '{}', 3, false, 2, false, true , 175, false, NULL, 'yossi', now()),  -- בשר עוף, רגל, שוק וירך, ללא עצם, צלוי, נאכל ללא עור
  ('841', 'protein', 'meat',      '{}', 3, false, 2, false, true , 175, false, NULL, 'yossi', now()),  -- בשר עוף, רגל, שוק וירך, ללא עצם, מבושל, נאכל ללא עור
  ('846', 'protein', 'meat',      '{}', 3, false, 2, false, true , 175, false, NULL, 'yossi', now()),  -- בשר עוף, רגל, ללא עצם, מטוגן, ללא ציפוי, נאכל ללא עור
  ('856', 'protein', 'meat',      '{}', 3, false, 2, false, true , 175, false, NULL, 'yossi', now()),  -- בשר עוף, שוק, ללא עצם, מבושל, נאכל ללא עור
  ('8804', 'protein', 'meat',      '{}', 3, false, 2, false, true , 175, false, NULL, 'yossi', now()),  -- בשר עוף, בשר כהה, שוק, בשר בלבד, מבושל, צלוי
  ('8186', 'protein', 'meat',      '{}', 3, false, 2, false, true , 175, false, NULL, 'yossi', now()),  -- בשר עוף, ירך, בשר בלבד, מבושל, צלוי
  ('880', 'protein', 'meat',      '{}', 3, false, 2, false, true , 175, false, NULL, 'yossi', now()),  -- בשר עוף, ירך, ללא עצם, מבושל, נאכל ללא עור
  ('886', 'protein', 'meat',      '{}', 3, false, 2, false, true , 175, false, NULL, 'yossi', now()),  -- בשר עוף, ירך, ללא עצם, מטוגן, ללא ציפוי, נאכל ללא עור
  ('873', 'protein', 'meat',      '{}', 3, false, 1, false, true , 175, false, NULL, 'yossi', now()),  -- בשר עוף, ירך, ללא עצם, בגריל, נאכל ללא עור
  ('889', 'protein', 'meat',      '{}', 3, false, 0, false, false, 100, false, NULL, 'yossi', now()),  -- בשר עוף, מעושן, הוד חפר, מילי
  ('894', 'protein', 'meat',      '{}', 3, false, 2, false, true , 175, false, NULL, 'yossi', now()),  -- בשר עוף, כנף, ללא עצם, ללא עור, צלוי, נאכל בלי עור
  ('892', 'protein', 'meat',      '{}', 3, false, 2, false, true , 175, false, NULL, 'yossi', now()),  -- בשר עוף, כנף, ללא עצם, בגריל, נאכל ללא עור
  ('8188', 'protein', 'meat',      '{}', 3, false, 2, false, true , 175, false, NULL, 'yossi', now()),  -- בשר עוף, כנף, בשר בלבד, מבושל, מטוגן
  ('926', 'protein', 'meat',      '{}', 3, false, 2, true , false, 175, false, NULL, 'yossi', now()),  -- בשר עוף, טחון, 100% בשר, טיבון ויל
  ('928', 'protein', 'meat',      '{}', 3, false, 2, false, false, 175, false, NULL, 'yossi', now()),  -- בשר עוף, טחון, צלוי
  ('923', 'protein', 'meat',      '{}', 3, false, 2, true , false, 175, false, NULL, 'yossi', now()),  -- בשר עוף, שווארמה פרגיות אמיתית, טיבון ויל
  ('910', 'protein', 'meat',      '{}', 3, false, 1, false, true , 175, false, NULL, 'yossi', now()),  -- קציצות עוף אמיתיות, לחימום, עוף טוב
  ('941', 'protein', 'meat',      '{}', 3, false, 2, false, false, 175, false, NULL, 'yossi', now()),  -- בשר הודו לבן, מבושל, לפנ אם נאכל עם עור
  ('943', 'protein', 'meat',      '{}', 3, false, 2, false, false, 175, false, NULL, 'yossi', now()),  -- בשר הודו לבן, מבושל, נאכל ללא עור
  ('963', 'protein', 'meat',      '{}', 3, false, 2, false, false, 175, false, NULL, 'yossi', now()),  -- בשר הודו לבן, צלוי, נאכל ללא עור
  ('1040', 'protein', 'meat',      '{}', 3, false, 2, false, false, 175, false, NULL, 'yossi', now()),  -- בשר ברווז, צלוי, נאכל ללא עור
  -- fish & seafood
  ('1360', 'protein', 'parve',      '{}', 3, false, 0, false, false, 130, false, NULL, 'yossi', now()),  -- דג טונה, משומר במים
  ('8260', 'protein', 'parve',      '{}', 3, false, 2, false, false, 175, false, NULL, 'yossi', now()),  -- דג אמנון-מושט, מבושל ללא תוספת מלח, אפוי
  ('1182', 'protein', 'parve',      '{}', 3, false, 2, false, false, 175, false, NULL, 'yossi', now()),  -- דג קוד (בקלה) מבושל במים או באדים
  ('1152', 'protein', 'parve',      '{}', 3, false, 2, false, true , 351, false, NULL, 'yossi', now()),  -- דג אמנון-מושט, מבושל
  ('1206', 'protein', 'parve',      '{}', 3, false, 2, false, false, 175, false, NULL, 'yossi', now()),  -- דג בקלה מבושל ללא שמן
  ('1223', 'protein', 'parve',      '{}', 3, false, 0, false, true , 100, false, NULL, 'yossi', now()),  -- דג בקלה, זהבון, אלסקה, מרלוזה, מעושן
  ('1277', 'protein', 'parve',      '{}', 3, false, 2, false, false, 175, false, NULL, 'yossi', now()),  -- דג נסיכת הנילוס אפוי ללא תוספת שומן בבישול
  ('1308', 'protein', 'parve',      '{}', 3, false, 2, false, false, 175, false, NULL, 'yossi', now()),  -- דג סלמון-אילתית, מבושל במים או אדים, עם מלח
  ('1296', 'protein', 'parve',      '{}', 3, false, 2, false, true , 175, false, NULL, 'yossi', now()),  -- דג פרידה מבושל במים או אדים
  ('1332', 'protein', 'parve',      '{}', 3, false, 2, false, false, 175, false, NULL, 'yossi', now()),  -- דג לוקוס/דקר/בס מים מלוחים, מבושל במים או אדים, עם מלח
  ('1298', 'protein', 'parve',      '{}', 3, false, 2, false, false, 175, false, NULL, 'yossi', now()),  -- דג סלמון אפוי ללא תוספת שומן בבישול
  ('9635', 'protein', 'parve',      '{}', 3, false, 2, false, false, 175, false, NULL, 'yossi', now()),  -- דג סלמון מטוגן ללא תוספת שמן
  ('1311', 'protein', 'parve',      '{}', 3, false, 0, false, false, 100, false, NULL, 'yossi', now()),  -- דג סלמון, מעושן
  ('1307', 'protein', 'parve',      '{}', 3, false, 0, false, false, 100, false, NULL, 'yossi', now()),  -- דג סלמון נורבגי פרוס/קפוא, בעשון מסורתי, תנובה
  ('1340', 'protein', 'parve',      '{}', 3, false, 2, false, false, 175, false, NULL, 'yossi', now()),  -- דג טונה אפוי עם מיץ לימון ללא תוספת שומן בבישול
  ('8584', 'protein', 'parve',      '{}', 3, false, 0, false, false, 112, false, NULL, 'yossi', now()),  -- דג טונה 5% שומן, סוגים שונים, סטארקיסט
  -- beef, veal & lamb
  ('624', 'protein', 'meat',      '{}', 3, false, 2, false, false, 175, false, NULL, 'yossi', now()),  -- בשר בקר, צלוי, נאכל ללא שומן
  ('626', 'protein', 'meat',      '{}', 3, false, 2, false, false, 175, false, NULL, 'yossi', now()),  -- בשר בקר, צלי, מאודה או מבושל, נאכל עם שומן
  ('623', 'protein', 'meat',      '{}', 3, false, 2, false, false, 175, false, NULL, 'yossi', now()),  -- בשר בקר, צלוי, נאכל עם שומן
  ('625', 'protein', 'meat',      '{}', 3, false, 0, false, false, 100, false, NULL, 'yossi', now()),  -- בשר בקר, רוסטביף, אפוי, צלוי
  ('615', 'protein', 'meat',      '{}', 3, false, 2, false, true , 175, false, NULL, 'yossi', now()),  -- סטייק בשר בקר, מטוגן, נאכל ללא שומן
  ('609', 'protein', 'meat',      '{}', 3, false, 2, false, true , 175, false, NULL, 'yossi', now()),  -- סטייק בשר בקר, צלוי או אפוי, נאכל ללא שומן
  ('636', 'protein', 'meat',      '{}', 3, false, 2, false, false, 175, false, NULL, 'yossi', now()),  -- בשר בקר, מבושל, נאכל ללא שומן
  ('653', 'protein', 'meat',      '{}', 3, false, 0, false, false, 100, false, NULL, 'yossi', now()),  -- בשר בקר, חזה, מעושן או כבוש, יחיעם
  ('649', 'protein', 'meat',      '{}', 3, false, 0, false, false, 100, false, NULL, 'yossi', now()),  -- בשר בקר, מיובש
  ('619', 'protein', 'meat',      '{}', 3, false, 2, false, true , 175, false, NULL, 'yossi', now()),  -- בשר בקר, צלעות, מבושל, נאכל ללא שומן
  ('680', 'protein', 'meat',      '{}', 3, false, 2, false, false, 175, false, NULL, 'yossi', now()),  -- בשר בקר, טחון, עם חלבון צמחי, מבושל
  ('663', 'protein', 'meat',      '{}', 3, false, 1, false, true , 175, false, NULL, 'yossi', now()),  -- קציצות בקר מזרחי, זוגלובק
  ('661', 'protein', 'meat',      '{}', 3, false, 1, false, true , 175, false, NULL, 'yossi', now()),  -- קבב בקר אמיתי, טיבון ויל
  ('662', 'protein', 'meat',      '{}', 3, false, 1, false, true , 175, false, NULL, 'yossi', now()),  -- קבב בקר טורקי/רומני/יווני עם חלבון צמחי,טיבון ויל
  ('670', 'protein', 'meat',      '{}', 3, false, 1, false, true , 175, false, NULL, 'yossi', now()),  -- קציצות בקר אמיתיות לחימום, עוף טוב
  ('675', 'protein', 'meat',      '{}', 3, false, 2, false, true , 175, false, NULL, 'yossi', now()),  -- קציצות בשר בקר והודו, מטוגנות ללא שמן
  ('683', 'protein', 'meat',      '{}', 3, false, 0, false, false, 100, false, NULL, 'yossi', now()),  -- בשר בקר, רוסטביף, כתף, מעושן
  ('681', 'protein', 'meat',      '{}', 3, false, 0, false, false, 100, false, NULL, 'yossi', now()),  -- נקניק, פסטרמה בקר, כתף בקר פרוס, יחיעם
  ('8741', 'protein', 'meat',      '{}', 3, false, 0, false, true , 100, false, NULL, 'yossi', now()),  -- נקניק, פסטרמה הודו בדבש/ דק רומנית, טירת צבי
  ('9650', 'protein', 'meat',      '{}', 3, false, 2, true , false, 175, false, NULL, 'yossi', now()),  -- בשר בקר, המבורגר/סטייקבורגר כולל מזרחי,טיבון ויל
  ('772', 'protein', 'meat',      '{}', 3, false, 2, false, true , 214, false, NULL, 'yossi', now()),  -- סטייק בשר עגל, לפנ לשיטת הבישול, נאכל עם שומן
  ('781', 'protein', 'meat',      '{}', 3, false, 2, false, false, 175, false, NULL, 'yossi', now()),  -- בשר עגל, צלוי, נאכל ללא שומן
  ('780', 'protein', 'meat',      '{}', 3, false, 2, false, false, 175, false, NULL, 'yossi', now()),  -- בשר עגל, צלוי, נאכל עם שומן
  ('782', 'protein', 'meat',      '{}', 3, false, 2, false, false, 175, false, NULL, 'yossi', now()),  -- בשר עגל, טחון או קציצה, מבושל
  ('721', 'protein', 'meat',      '{}', 3, false, 2, false, false, 175, false, NULL, 'yossi', now()),  -- בשר כבש, צלי, מבושל, נאכל ללא שומן
  ('717', 'protein', 'meat',      '{}', 3, false, 2, false, false, 175, false, NULL, 'yossi', now()),  -- בשר כבש, כתף, מבושל, נאכל ללא שומן
  ('729', 'protein', 'meat',      '{}', 3, false, 2, false, false, 175, false, NULL, 'yossi', now()),  -- בשר כבש, טחון או קציצה, מבושל
  -- dairy & cheese
  ('499', 'protein', 'dairy',      '{}', 3, false, 0, false, false, 250, false, NULL, 'yossi', now()),  -- גבינת קוטג',3% שומן, מועשרת בסידן, סקי, שטראוס
  ('504', 'protein', 'dairy',      '{}', 3, false, 0, false, false, 250, false, NULL, 'yossi', now()),  -- גבינת קוטג' 3% שומן, מועשרת בסידן, טרה
  ('522', 'protein', 'dairy',      '{}', 3, false, 0, false, false, 250, false, NULL, 'yossi', now()),  -- גבינה לבנה 5% שומן, כנען, השף הלבן
  ('508', 'protein', 'dairy',      '{}', 3, false, 0, false, false, 250, false, NULL, 'yossi', now()),  -- גבינת ריקוטה/אורדה 5% שומן, מחלב עזים, גד
  ('533', 'protein', 'dairy',      '{}', 3, false, 0, false, false, 250, false, NULL, 'yossi', now()),  -- גבינה לבנה 3% שומן, טוב טעם, טרה
  ('8506', 'protein', 'dairy',      '{}', 3, false, 0, false, false, 250, false, NULL, 'yossi', now()),  -- גבינה לבנה 3% שומן, לבישול ואפיה, טוב טעם, טרה
  ('8605', 'protein', 'dairy',      '{}', 3, false, 0, false, false, 100, false, NULL, 'yossi', now()),  -- גבינת שמנת בטעם טבעי 5% שומן, תנובה
  ('539', 'protein', 'dairy',      '{}', 3, false, 0, false, false, 100, false, NULL, 'yossi', now()),  -- גבינת שמנת 5% שומן, סימפוניה, טעמים שונים, שטראוס
  ('556', 'protein', 'dairy',      '{}', 3, false, 0, false, false, 100, false, NULL, 'yossi', now()),  -- גבינת שמנת 3% שומן, בטעמים, סימפוניה, שטראוס
  ('8696', 'protein', 'dairy',      '{}', 3, false, 0, false, false, 100, false, NULL, 'yossi', now()),  -- גבינת שמנת זיתים 5% שומן, ניו יורק לייט, גד
  ('8690', 'protein', 'dairy',      '{}', 3, false, 0, false, false, 100, false, NULL, 'yossi', now()),  -- לאבנה, ציזיקי למריחה, 5% שומן, מחלב בקר, גד
  ('472', 'protein', 'dairy',      '{}', 3, false, 0, false, false,  75, false, NULL, 'yossi', now()),  -- גבינה צהובה 9% שומן, לייט, טל העמק /ירושלים /כתר,תנובה
  ('9516', 'protein', 'dairy',      '{}', 3, false, 0, false, false,  75, false, NULL, 'yossi', now()),  -- גבינה צהובה,הצהובה הטובה, 5% שומן, טעמים שונים, כפיר
  ('572', 'protein', 'dairy',      '{}', 3, false, 0, false, false,  75, false, NULL, 'yossi', now()),  -- גבינה צהובה, הצהובה הטובה, 9% שומן, לייט, כפיר
  ('420', 'protein', 'dairy',      '{}', 3, false, 0, false, false, 100, false, NULL, 'yossi', now()),  -- גבינה צפתית 4% שומן, מחלב בופאלו
  ('8601', 'protein', 'dairy',      '{}', 3, false, 0, false, false, 100, false, NULL, 'yossi', now()),  -- גבינה צפתית 5% שומן, מחלב עזים, פיראוס
  ('446', 'protein', 'dairy',      '{}', 3, false, 0, false, false, 100, false, NULL, 'yossi', now()),  -- גבינה בולגרית 5% שומן, כולל קוביות, פיראוס תנובה
  ('8604', 'protein', 'dairy',      '{}', 3, false, 0, false, false, 100, false, NULL, 'yossi', now()),  -- גבינה מלוחה 5% שומן, חמד, פיראוס
  ('8598', 'protein', 'dairy',      '{}', 3, false, 0, false, false, 100, false, NULL, 'yossi', now()),  -- גבינת פטה 5% שומן, מחלב כבשים, פיראוס
  ('562', 'protein', 'dairy',      '{}', 3, false, 0, false, true ,  75, false, NULL, 'yossi', now()),  -- גבינה מותכת 7% שומן, שומרון
  ('561', 'protein', 'dairy',      '{}', 3, false, 0, false, true ,  75, false, NULL, 'yossi', now()),  -- גבינה מותכת לייט, 7% שומן, שוויצרי/רוקפור/זיתים/סלמון/פיקנטי, מון בלאן
  -- legumes & soy
  ('1669', 'protein', 'parve', '{vegan}', 1, false, 2, false, false, 200, false, NULL, 'yossi', now()),  -- עדשים יבשים, מבושלים עם מלח, ללא תוספת שומן בבישול
  ('1653', 'protein', 'parve', '{vegan}', 1, false, 2, false, false, 200, false, NULL, 'yossi', now()),  -- חומוס, גרגירים, מבושלים עם מלח
  ('1661', 'protein', 'parve', '{vegan}', 1, false, 2, false, false, 200, false, NULL, 'yossi', now()),  -- אפונה יבשה, מבושלת, ללא תוספת שומן בבישול, עם מלח
  ('9717', 'protein', 'parve', '{vegan}', 1, false, 2, false, false, 200, false, NULL, 'yossi', now()),  -- שעועית לוביה, מבושלת, ללא תוספת שומן, עם מלח
  ('1674', 'protein', 'parve', '{vegan}', 1, false, 0, false, false,  60, false, NULL, 'yossi', now()),  -- חומוס קלוי, גת
  ('1630', 'protein', 'parve', '{vegan}', 1, false, 2, false, false, 200, false, NULL, 'yossi', now()),  -- תורמוס מבושל
  ('1632', 'protein', 'parve', '{vegan}', 2, false, 2, false, false, 180, false, NULL, 'yossi', now()),  -- סויה, פולים מבושלים, עם מלח, ללא תוספת שומן בבישול
  ('8229', 'protein', 'parve', '{vegan}', 2, false, 2, false, false, 180, false, NULL, 'yossi', now()),  -- סויה, פולים,ירוק, מבושל, מסונן ללא מלח, ללא תוספת שומן בבישול
  ('1638', 'protein', 'parve', '{vegan}', 2, false, 2, false, false, 180, false, NULL, 'yossi', now()),  -- סויה, פתיתים מבושלים ללא תוספת שומן בבישול
  ('9535', 'protein', 'parve', '{vegan}', 1, false, 2, false, false, 200, false, NULL, 'yossi', now()),  -- שעועית מש, מבושלת, ללא תוספת שומן בבישול, עם מלח
  ('1679', 'protein', 'parve', '{vegan}', 2, false, 0, false, false,  30, false, NULL, 'yossi', now()),  -- סויה, פולים קלויים עם מלח
  ('10141', 'protein', 'parve', '{vegan}', 2, false, 1, false, false, 150, false, NULL, 'yossi', now()),  -- טופו במרקם קשה, משק ווילר
  ('1704', 'protein', 'parve', '{vegan}', 2, false, 1, false, false, 150, false, NULL, 'yossi', now()),  -- טופו במרקם רך, כפרי בריא, משק ווילר
  ('10142', 'protein', 'parve', '{vegan}', 2, false, 1, false, false, 150, false, NULL, 'yossi', now()),  -- טופו במרקם רך, מועשר בסידן, משק ווילר
  ('1698', 'protein', 'parve', '{vegan}', 2, false, 2, true , false, 150, false, NULL, 'yossi', now()),  -- טמפה, מזון אינדונזי שורשי, קפוא, כפרי בריא
  ('9589', 'protein', 'parve', '{vegan}', 2, false, 2, true , false, 150, false, NULL, 'yossi', now()),  -- טמפה (פולי סויה מותססים), מבושל
  ('1790', 'protein', 'parve', '{vegan}', 2, false, 1, false, true , 200, false, NULL, 'yossi', now()),  -- טחון צמחוני, טבעול
  ('10126', 'protein', 'parve', '{vegan}', 2, false, 1, false, true , 150, false, NULL, 'yossi', now()),  -- המבורגר מן הצומח, מופחת שומן/99, טבעול
  ('8868', 'protein', 'parve', '{vegan}', 2, false, 1, false, true , 150, false, NULL, 'yossi', now()),  -- קבב מן הצומח, מופחת שומן/99, טבעול
  ('9768', 'protein', 'parve', '{vegan}', 2, false, 1, true , false, 150, false, NULL, 'yossi', now()),  -- שווארמה מן הצומח, טבעול
  ('1810', 'protein', 'parve', '{vegan}', 2, false, 1, false, true , 150, false, NULL, 'yossi', now()),  -- שניצל מן הצומח מופחת שומן/99, טבעול
  ('1805', 'protein', 'parve', '{vegan}', 2, false, 1, false, true , 150, false, NULL, 'yossi', now()),  -- קבב מן הצומח, זוגלובק
  ('1792', 'protein', 'parve', '{vegan}', 2, false, 1, false, true , 150, false, NULL, 'yossi', now()),  -- נקניקיות מן הצומח, זוגלובק
  ('1791', 'protein', 'parve', '{vegan}', 2, false, 1, false, true , 150, false, NULL, 'yossi', now());  -- נקניקיות מן הצומח, טבעול

-- The new rows, for the assertions below
CREATE TEMP TABLE _new ON COMMIT DROP AS
  SELECT c.* FROM food_curation c
   WHERE NOT EXISTS (SELECT 1 FROM _pre p WHERE p.source_code = c.source_code);

-- Raw output for the record, before the assertions
SELECT source_code, category, kosher, tags, quality, supp, prep, by_weight,
       whole_only, max_g, menu_eligible, allergens, allergens_reviewed_at, curated_by
  FROM _new ORDER BY source_code::int;

-- V1 — exactly 130 rows added, nothing removed, and the new set is exactly the 130 codes
DO $$
DECLARE added int; removed int; who text;
BEGIN
  SELECT count(*), string_agg(source_code, ',' ORDER BY source_code::int)
    INTO added, who FROM _new;
  SELECT count(*) INTO removed
    FROM _pre p LEFT JOIN food_curation c USING (source_code)
   WHERE c.source_code IS NULL;
  IF added <> 130 OR removed <> 0 OR who IS DISTINCT FROM
     '258,420,446,472,499,504,508,522,533,539,556,561,562,572,609,615,619,623,624,625,626,636,649,653,661,662,663,670,675,680,681,683,717,721,729,772,780,781,782,788,799,802,807,825,834,838,841,846,856,873,880,886,889,892,894,910,923,926,928,941,943,963,1040,1152,1182,1206,1223,1277,1296,1298,1307,1308,1311,1332,1340,1360,1561,1564,1565,1566,1573,1574,1575,1630,1632,1638,1653,1661,1669,1674,1679,1698,1704,1724,1790,1791,1792,1805,1810,8186,8188,8229,8260,8274,8506,8547,8584,8598,8601,8604,8605,8625,8690,8696,8741,8804,8837,8868,9516,9535,9560,9589,9635,9650,9717,9768,9851,10126,10141,10142' THEN
    RAISE EXCEPTION 'V1 failed: % added, % removed, new set = %', added, removed, who;
  END IF;
END $$;

-- V2a — the constants on every row, and the kosher split 56 / 23 / 51
DO $$
DECLARE n int; off int; k_meat int; k_dairy int; k_parve int;
BEGIN
  SELECT count(*),
         count(*) FILTER (WHERE NOT (
             category = 'protein' AND menu_eligible = false
             AND allergens = '{}'::text[] AND allergens_reviewed_at IS NULL
             AND excluded_reason IS NULL AND curated_by = 'yossi'
             AND curated_at IS NOT NULL AND by_weight IS NOT NULL
             AND quality IS NOT NULL AND prep IS NOT NULL AND max_g IS NOT NULL)),
         count(*) FILTER (WHERE kosher = 'meat'),
         count(*) FILTER (WHERE kosher = 'dairy'),
         count(*) FILTER (WHERE kosher = 'parve')
    INTO n, off, k_meat, k_dairy, k_parve FROM _new;
  IF n <> 130 OR off <> 0 OR k_meat <> 56 OR k_dairy <> 23 OR k_parve <> 51 THEN
    RAISE EXCEPTION 'V2a failed: n=% off-spec=% meat=% dairy=% parve=%', n, off, k_meat, k_dairy, k_parve;
  END IF;
END $$;

-- V2b — quality 102 / 19 / 9, groups 2 and 1 by name
DO $$
DECLARE q3 int; q2 int; q1 int; q2_who text; q1_who text;
BEGIN
  SELECT count(*) FILTER (WHERE quality = 3), count(*) FILTER (WHERE quality = 2),
         count(*) FILTER (WHERE quality = 1),
         string_agg(source_code, ',' ORDER BY source_code::int) FILTER (WHERE quality = 2),
         string_agg(source_code, ',' ORDER BY source_code::int) FILTER (WHERE quality = 1)
    INTO q3, q2, q1, q2_who, q1_who FROM _new;
  IF q3 <> 102 OR q2 <> 19 OR q1 <> 9
     OR q2_who IS DISTINCT FROM '1632,1638,1679,1698,1704,1724,1790,1791,1792,1805,1810,8229,8274,8868,9589,9768,10126,10141,10142'
     OR q1_who IS DISTINCT FROM '1630,1653,1661,1669,1674,8547,9535,9717,9851' THEN
    RAISE EXCEPTION 'V2b failed: q3=% q2=% (%) q1=% (%)', q3, q2, q2_who, q1, q1_who;
  END IF;
END $$;

-- V2c — prep 40 / 22 / 68, groups 0 and 1 by name
DO $$
DECLARE p0 int; p1 int; p2 int; p0_who text; p1_who text;
BEGIN
  SELECT count(*) FILTER (WHERE prep = 0), count(*) FILTER (WHERE prep = 1),
         count(*) FILTER (WHERE prep = 2),
         string_agg(source_code, ',' ORDER BY source_code::int) FILTER (WHERE prep = 0),
         string_agg(source_code, ',' ORDER BY source_code::int) FILTER (WHERE prep = 1)
    INTO p0, p1, p2, p0_who, p1_who FROM _new;
  IF p0 <> 40 OR p1 <> 22 OR p2 <> 68
     OR p0_who IS DISTINCT FROM '258,420,446,472,499,504,508,522,533,539,556,561,562,572,625,649,653,681,683,889,1223,1307,1311,1360,1674,1679,1724,8274,8506,8547,8584,8598,8601,8604,8605,8690,8696,8741,9516,9560'
     OR p1_who IS DISTINCT FROM '661,662,663,670,802,873,910,1564,1566,1575,1704,1790,1791,1792,1805,1810,8868,9768,9851,10126,10141,10142' THEN
    RAISE EXCEPTION 'V2c failed: p0=% (%) p1=% (%) p2=%', p0, p0_who, p1, p1_who, p2;
  END IF;
END $$;

-- V2d — max_g: 175 on 58, every other group by name
DO $$
DECLARE m175 int; m60_who text; m150_who text; m100_who text; m250_who text; m75_who text; m200_who text; m180_who text; m130_who text; m112_who text; m351_who text; m214_who text; m30_who text;
BEGIN
  SELECT count(*) FILTER (WHERE max_g = 175),
         string_agg(source_code, ',' ORDER BY source_code::int) FILTER (WHERE max_g = 60),
         string_agg(source_code, ',' ORDER BY source_code::int) FILTER (WHERE max_g = 150),
         string_agg(source_code, ',' ORDER BY source_code::int) FILTER (WHERE max_g = 100),
         string_agg(source_code, ',' ORDER BY source_code::int) FILTER (WHERE max_g = 250),
         string_agg(source_code, ',' ORDER BY source_code::int) FILTER (WHERE max_g = 75),
         string_agg(source_code, ',' ORDER BY source_code::int) FILTER (WHERE max_g = 200),
         string_agg(source_code, ',' ORDER BY source_code::int) FILTER (WHERE max_g = 180),
         string_agg(source_code, ',' ORDER BY source_code::int) FILTER (WHERE max_g = 130),
         string_agg(source_code, ',' ORDER BY source_code::int) FILTER (WHERE max_g = 112),
         string_agg(source_code, ',' ORDER BY source_code::int) FILTER (WHERE max_g = 351),
         string_agg(source_code, ',' ORDER BY source_code::int) FILTER (WHERE max_g = 214),
         string_agg(source_code, ',' ORDER BY source_code::int) FILTER (WHERE max_g = 30)
    INTO m175, m60_who, m150_who, m100_who, m250_who, m75_who, m200_who, m180_who, m130_who, m112_who, m351_who, m214_who, m30_who FROM _new;
  IF m175 <> 58
     OR m60_who IS DISTINCT FROM '258,1674,1724,8274,8547,9560'
     OR m150_who IS DISTINCT FROM '1561,1564,1565,1566,1573,1574,1575,1698,1704,1791,1792,1805,1810,8868,9589,9768,9851,10126,10141,10142'
     OR m100_who IS DISTINCT FROM '420,446,539,556,625,649,653,681,683,889,1223,1307,1311,8598,8601,8604,8605,8690,8696,8741'
     OR m250_who IS DISTINCT FROM '499,504,508,522,533,8506'
     OR m75_who IS DISTINCT FROM '472,561,562,572,9516'
     OR m200_who IS DISTINCT FROM '1630,1653,1661,1669,1790,9535,9717'
     OR m180_who IS DISTINCT FROM '1632,1638,8229'
     OR m130_who IS DISTINCT FROM '1360'
     OR m112_who IS DISTINCT FROM '8584'
     OR m351_who IS DISTINCT FROM '1152'
     OR m214_who IS DISTINCT FROM '772'
     OR m30_who IS DISTINCT FROM '1679' THEN
    RAISE EXCEPTION 'V2d failed: 175=% 60=(%) 150=(%) 100=(%) 250=(%) 75=(%) 200=(%) 180=(%) 130=(%) 112=(%) 351=(%) 214=(%) 30=(%)', m175, m60_who, m150_who, m100_who, m250_who, m75_who, m200_who, m180_who, m130_who, m112_who, m351_who, m214_who, m30_who;
  END IF;
END $$;

-- V2e — supp on the five, tags {vegan} on the 28, by_weight on the eleven,
-- whole_only on 46 and only where by_weight is false
DO $$
DECLARE supp_who text; vegan_who text; other_tags int; bw_who text; wo int; wo_bad int;
BEGIN
  SELECT string_agg(source_code, ',' ORDER BY source_code::int) FILTER (WHERE supp),
         string_agg(source_code, ',' ORDER BY source_code::int) FILTER (WHERE tags = '{vegan}'::text[]),
         count(*) FILTER (WHERE tags <> '{vegan}'::text[] AND tags <> '{}'::text[]),
         string_agg(source_code, ',' ORDER BY source_code::int) FILTER (WHERE by_weight),
         count(*) FILTER (WHERE whole_only),
         count(*) FILTER (WHERE whole_only AND by_weight)
    INTO supp_who, vegan_who, other_tags, bw_who, wo, wo_bad FROM _new;
  IF supp_who IS DISTINCT FROM '258,1724,8274,8547,9560'
     OR vegan_who IS DISTINCT FROM '1630,1632,1638,1653,1661,1669,1674,1679,1698,1704,1724,1790,1791,1792,1805,1810,8229,8274,8547,8868,9535,9589,9717,9768,9851,10126,10141,10142'
     OR other_tags <> 0
     OR bw_who IS DISTINCT FROM '258,923,926,1698,8547,8625,9560,9589,9650,9768,9851'
     OR wo <> 46 OR wo_bad <> 0 THEN
    RAISE EXCEPTION 'V2e failed: supp=(%) vegan=(%) other-tags=% by_weight=(%) whole_only=% whole-and-by-weight=%',
      supp_who, vegan_who, other_tags, bw_who, wo, wo_bad;
  END IF;
END $$;

-- V3 — the 179 pre-existing rows are identical, every column, updated_at included
DO $$
DECLARE n int; moved int;
BEGIN
  SELECT count(*) INTO n FROM _pre;
  SELECT count(*) INTO moved
    FROM _pre p JOIN food_curation c USING (source_code)
   WHERE (c.category, c.kosher, c.allergens, c.allergens_reviewed_at, c.tags,
          c.quality, c.supp, c.prep, c.by_weight, c.whole_only, c.max_g,
          c.menu_eligible, c.curated_by, c.curated_at, c.created_at, c.updated_at,
          c.excluded_reason)
         IS DISTINCT FROM
         (p.category, p.kosher, p.allergens, p.allergens_reviewed_at, p.tags,
          p.quality, p.supp, p.prep, p.by_weight, p.whole_only, p.max_g,
          p.menu_eligible, p.curated_by, p.curated_at, p.created_at, p.updated_at,
          p.excluded_reason);
  IF n <> 179 OR moved <> 0 THEN
    RAISE EXCEPTION 'V3 failed: _pre holds % rows, % of them changed', n, moved;
  END IF;
END $$;

-- V4 — counts: 130 more rows, eligibility untouched, the view unchanged
DO $$
DECLARE tot int; el int; p int; f int; c int; v int; vm int;
BEGIN
  SELECT count(*), count(*) FILTER (WHERE menu_eligible),
         count(*) FILTER (WHERE menu_eligible AND category='protein'),
         count(*) FILTER (WHERE menu_eligible AND category='fat'),
         count(*) FILTER (WHERE menu_eligible AND category='carb'),
         count(*) FILTER (WHERE menu_eligible AND category='veg')
    INTO tot, el, p, f, c, v FROM food_curation;
  SELECT count(*) INTO vm FROM v_menu_foods;
  IF tot<>309 OR el<>56 OR p<>11 OR f<>37 OR c<>4 OR v<>4 OR vm<>56 THEN
    RAISE EXCEPTION 'V4 failed: tot=% el=% p=% f=% c=% v=% view=%', tot, el, p, f, c, v, vm;
  END IF;
END $$;

-- V5 — the safety views stay clean
DO $$
DECLARE mt int; orph int;
BEGIN
  SELECT count(*) INTO mt   FROM v_eligible_missing_tags;
  SELECT count(*) INTO orph FROM v_curation_orphans;
  IF mt <> 0 OR orph <> 0 THEN
    RAISE EXCEPTION 'V5 failed: missing_tags=% orphans=%', mt, orph;
  END IF;
END $$;

COMMIT;
