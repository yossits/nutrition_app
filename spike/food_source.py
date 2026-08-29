# -*- coding: utf-8 -*-
"""
Which food database the spike runs against.

Two paths, and the seed is the default:

  seed  spike/foods.py — the 63 items written by hand during stage A. No API
        key, no network, no database. This is what the 92% was measured on and
        it stays the default so that number remains reproducible.
  db    spike/menu_foods.py — generated from production by
        db/09_export_menu_foods.py out of v_menu_foods.

The swap is done by replacing the CONTENTS of foods.FOODS, not by rebinding the
name. spike/filters.py opens with `from foods import FOODS`, which copies the
reference at import time; assigning foods.FOODS = [...] would leave the filter
layer pointing at the old list. Mutating in place reaches every module that
already holds it, and it means the filter layer and the portion solver need no
change at all — both sit behind the regression gate in docs/measurements.md, and
a bridge that forced an edit there would be a bridge built in the wrong place.

ALL_ALLERGENS is deliberately NOT swapped. It is the vocabulary the synthetic
test profiles draw allergies from, not a property of the food pool; keeping it
fixed is what lets the same 100 profiles be posed to both paths.
"""

SEED = "seed"
DB = "db"
CHOICES = (SEED, DB)


def add_argument(parser):
    parser.add_argument(
        "--source", choices=CHOICES, default=SEED,
        help="which food database to run against (default: seed)")
    return parser


def activate(source):
    """Point the spike at `source`. Returns a one-line description for the log."""
    import foods

    if source == SEED:
        return f"seed · spike/foods.py · {len(foods.FOODS)} items"

    try:
        import menu_foods
    except ModuleNotFoundError:
        raise SystemExit(
            "spike/menu_foods.py is missing. It is generated, not written:\n"
            "    python db\\09_export_menu_foods.py")

    if not menu_foods.FOODS:
        raise SystemExit(
            "spike/menu_foods.py exports 0 items — v_menu_foods is empty.\n"
            "Nothing is menu_eligible yet; curation is block 3d.")

    foods.FOODS[:] = menu_foods.FOODS
    return f"db · spike/menu_foods.py · {len(foods.FOODS)} items"
