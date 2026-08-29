-- ============================================================================
--  10_menu_fields_check.sql — the three fields the spike reads and the schema
--  did not require
--
--  Why: eligible_requires_safety_tagging (db/06_split_curation.sql) covers
--  category, kosher and the allergen review. prep, price and by_weight are not
--  in it, and all three are read by the spike:
--
--    filters.eligible()   if f["prep"] > max_prep      → TypeError on NULL
--    filters.eligible()   if f["price"] > max_price    → TypeError on NULL
--    portions._options()  if food.get("by_weight"):    → checked BEFORE unit
--
--  The first two fail loudly, five frames from anything actionable. The third
--  does not fail at all, and that is the worse one: by_weight DEFAULT true
--  means a curator who never touches the column gets a row whose chosen serving
--  unit is dead data, and the menu is phrased in grams with nothing to notice.
--  That is the failure mode the kcal NULL rule was chosen to avoid — an
--  unfilled field must fail, not quietly assume.
--
--  So by_weight loses both its DEFAULT and its NOT NULL: NULL now means "not
--  yet decided" and the constraint refuses to let it near menu_eligible.
--
--  A SEPARATE constraint, deliberately not an extension of
--  eligible_requires_safety_tagging. That one is the safety gate — kashrut and
--  allergens — and a safety gate that also enforces a price field is a gate
--  whose name lies about what its failure means.
--
--  Run once against production, after db/06_split_curation.sql.
--  db/01_food_db_schema.sql carries the same shape for a database built from
--  scratch — the two must never disagree, or a rebuild silently restores the
--  old defaults.
--
--  Safe only while nothing is menu_eligible yet. Before running, this must
--  return 0:
--
--      SELECT count(*) FROM food_curation WHERE menu_eligible;
--
--  Verified 0 against production on 30.08.2026, over 118 rows — the 116 FFQ
--  entries and the two non-protein-nitrogen exclusions, none of them eligible.
--  Curation is block 3d and had not started.
--
--  Decided 30.08.2026 — see docs/decisions.md.
-- ============================================================================

BEGIN;

-- NULL is now a state, not an accident: "nobody has ruled on this yet". The
-- old DEFAULT true made every untouched row claim to be sold by weight.
ALTER TABLE food_curation ALTER COLUMN by_weight DROP DEFAULT;
ALTER TABLE food_curation ALTER COLUMN by_weight DROP NOT NULL;

ALTER TABLE food_curation ADD CONSTRAINT eligible_requires_menu_fields
  CHECK (menu_eligible = false OR
         (prep IS NOT NULL AND price IS NOT NULL AND by_weight IS NOT NULL));

COMMIT;

-- ----------------------------------------------------------------------------
--  The export gate in db/09_export_menu_foods.py stays. It refuses to emit a
--  record whose prep, price or kcal is NULL and names the item and the field.
--  Two guards on one question is not duplication here: the CHECK catches a bad
--  write, the exporter catches a bad read — including kcal, which lives on
--  foods and no constraint on food_curation can reach.
-- ----------------------------------------------------------------------------
