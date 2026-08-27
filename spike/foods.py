# -*- coding: utf-8 -*-
"""
Seed food database - sample of the curated `menu_eligible` set.
Values are per 100g. Each food carries natural serving units.

NOTE: display names are English so terminal output is readable.
      The production Hebrew name is kept in the `he` field - switching
      the app to Hebrew is a one-line change (use f['he'] instead of f['name']).

kosher: 'meat' | 'dairy' | 'parve'
cat:    protein | carb | veg | fat | fruit | drink
prep:   0 = none, 1 = quick, 2 = cooking required
price:  1 = cheap, 2 = mid, 3 = expensive
"""

def F(name, he, cat, kcal, p, f, c, kosher, servings, allergens=(), tags=(),
      prep=0, price=1, complete=False, supp=False, quality=0):
    """
    complete=True -> all nine essential amino acids in useful amounts.
    quality: protein quality tier, roughly tracking biological value / DIAAS.
        3 = animal sources (whey, egg, dairy, meat, fish) - highest
        2 = soy and quinoa - complete but lower biological value
        1 = legumes, seitan, pea protein - incomplete or lower quality
    """
    return dict(name=name, he=he, cat=cat, kcal=kcal, protein=p, fat=f, carb=c,
                kosher=kosher, servings=servings, allergens=set(allergens),
                tags=set(tags), prep=prep, price=price, complete=complete, supp=supp, quality=quality)


FOODS = [
    # ---------- protein: meat ----------
    F("Chicken breast", "חזה עוף", "protein", 165, 31.0, 3.6, 0, "meat",
      [("100g", 100), ("portion (200g)", 200)], prep=2, price=2, complete=True, quality=3),
    F("Chicken thigh, skinless", "שוק עוף ללא עור", "protein", 175, 24.0, 8.0, 0, "meat",
      [("thigh (150g)", 150)], prep=2, price=1, complete=True, quality=3),
    F("Ground beef 10%", "בשר בקר טחון 10%", "protein", 200, 20.0, 13.0, 0, "meat",
      [("100g", 100), ("portion (150g)", 150)], prep=2, price=3, complete=True, quality=3),
    F("Ground turkey", "הודו טחון", "protein", 150, 22.0, 7.0, 0, "meat",
      [("100g", 100), ("portion (150g)", 150)], prep=2, price=2, complete=True, quality=3),
    F("Turkey schnitzel", "שניצל הודו", "protein", 160, 28.0, 5.0, 0, "meat",
      [("piece (120g)", 120)], prep=2, price=2, complete=True, quality=3),

    # ---------- protein: fish (parve) ----------
    F("Canned tuna in water", "טונה במים", "protein", 116, 26.0, 1.0, 0, "parve",
      [("can (100g drained)", 100)], allergens=["Fish"], prep=0, price=1, complete=True, quality=3),
    F("Salmon", "סלמון", "protein", 208, 20.0, 13.0, 0, "parve",
      [("fillet (150g)", 150)], allergens=["Fish"], prep=2, price=3, complete=True, quality=3),
    F("Tilapia fillet", "פילה מושט", "protein", 105, 23.0, 1.5, 0, "parve",
      [("fillet (150g)", 150)], allergens=["Fish"], prep=2, price=2, complete=True, quality=3),

    # ---------- protein: parve other ----------
    F("Egg", "ביצה", "protein", 143, 12.6, 9.5, 0.7, "parve",
      [("1 large (52g)", 52), ("2 eggs", 104), ("3 eggs", 156)],
      allergens=["Eggs"], prep=1, price=1, complete=True, quality=3),
    F("Tofu", "טופו", "protein", 76, 8.0, 4.8, 1.9, "parve",
      [("100g", 100)], allergens=["Soy"], tags=["vegan"], prep=1, price=2, complete=True, quality=2),
    F("Lentils, cooked", "עדשים מבושלות", "protein", 116, 9.0, 0.4, 20.0, "parve",
      [("cup (200g)", 200)], tags=["vegan"], prep=2, price=1, quality=1),
    F("Chickpeas, cooked", "חומוס גרגירים", "protein", 164, 8.9, 2.6, 27.0, "parve",
      [("cup (165g)", 165)], tags=["vegan"], prep=2, price=1, quality=1),
    F("Whey protein powder", "אבקת חלבון", "protein", 380, 78.0, 5.0, 8.0, "dairy",
      [("scoop (30g)", 30)], allergens=["Milk"], prep=0, price=2, complete=True, supp=True, quality=3),

    # ---------- protein: dairy ----------
    F("Cottage cheese 5%", "קוטג' 5%", "protein", 98, 11.0, 5.0, 3.0, "dairy",
      [("tub (250g)", 250), ("half tub (125g)", 125)], allergens=["Milk"], prep=0, price=1, complete=True, quality=3),
    F("White cheese 5%", "גבינה לבנה 5%", "protein", 100, 10.0, 5.0, 4.0, "dairy",
      [("tub (250g)", 250)], allergens=["Milk"], prep=0, price=1, complete=True, quality=3),
    F("White cheese 3%", "גבינה לבנה 3%", "protein", 85, 10.0, 3.0, 4.0, "dairy",
      [("tub (250g)", 250)], allergens=["Milk"], prep=0, price=1, complete=True, quality=3),
    F("Greek yogurt 0%", "יוגורט יווני 0%", "protein", 59, 10.0, 0.4, 3.6, "dairy",
      [("tub (150g)", 150)], allergens=["Milk"], prep=0, price=2, complete=True, quality=3),
    F("Plain yogurt 3%", "יוגורט טבעי 3%", "protein", 61, 3.5, 3.3, 4.7, "dairy",
      [("tub (200g)", 200)], allergens=["Milk"], prep=0, price=1, complete=True, quality=3),
    F("Yellow cheese 28%", "גבינה צהובה 28%", "protein", 350, 25.0, 28.0, 1.0, "dairy",
      [("slice (25g)", 25)], allergens=["Milk"], prep=0, price=2, complete=True, quality=3),
    F("Mozzarella", "מוצרלה", "protein", 300, 22.0, 22.0, 2.2, "dairy",
      [("100g", 100)], allergens=["Milk"], prep=0, price=2, complete=True, quality=3),

    # ---------- carbs ----------
    F("White rice, cooked", "אורז לבן מבושל", "carb", 130, 2.7, 0.3, 28.0, "parve",
      [("cup (158g)", 158), ("half cup (79g)", 79)], tags=["vegan"], prep=2, price=1),
    F("Brown rice, cooked", "אורז מלא מבושל", "carb", 112, 2.6, 0.9, 24.0, "parve",
      [("cup (195g)", 195)], tags=["vegan"], prep=2, price=1),
    F("Pasta, cooked", "פסטה מבושלת", "carb", 131, 5.0, 1.1, 25.0, "parve",
      [("cup (140g)", 140)], allergens=["Gluten"], tags=["vegan"], prep=2, price=1),
    F("Couscous, cooked", "קוסקוס מבושל", "carb", 112, 3.8, 0.2, 23.0, "parve",
      [("cup (157g)", 157)], allergens=["Gluten"], tags=["vegan"], prep=2, price=1),
    F("Sweet potato, baked", "בטטה אפויה", "carb", 90, 2.0, 0.1, 21.0, "parve",
      [("medium (150g)", 150)], tags=["vegan"], prep=2, price=1),
    F("Potato, boiled", "תפוח אדמה מבושל", "carb", 87, 1.9, 0.1, 20.0, "parve",
      [("medium (170g)", 170)], tags=["vegan"], prep=2, price=1),
    F("Whole wheat bread", "לחם מלא", "carb", 247, 13.0, 3.4, 41.0, "parve",
      [("slice (30g)", 30), ("2 slices", 60)], allergens=["Gluten"], tags=["vegan"], prep=0, price=1),
    F("White bread", "לחם לבן", "carb", 265, 9.0, 3.2, 49.0, "parve",
      [("slice (25g)", 25), ("2 slices", 50)], allergens=["Gluten"], tags=["vegan"], prep=0, price=1),
    F("Whole wheat pita", "פיתה מלאה", "carb", 275, 9.0, 1.7, 55.0, "parve",
      [("pita (60g)", 60)], allergens=["Gluten"], tags=["vegan"], prep=0, price=1),
    F("Oats", "שיבולת שועל", "carb", 389, 17.0, 7.0, 66.0, "parve",
      [("half cup (40g)", 40), ("cup (80g)", 80)], allergens=["Gluten"], tags=["vegan"], prep=1, price=1),
    F("Tortilla", "טורטייה", "carb", 310, 8.0, 8.0, 51.0, "parve",
      [("tortilla (50g)", 50)], allergens=["Gluten"], tags=["vegan"], prep=0, price=2),
    F("Quinoa, cooked", "קינואה מבושלת", "carb", 120, 4.4, 1.9, 21.0, "parve",
      [("cup (185g)", 185)], tags=["vegan"], prep=2, price=3, complete=True, quality=2),

    # ---------- vegetables ----------
    F("Cucumber", "מלפפון", "veg", 15, 0.7, 0.1, 3.6, "parve",
      [("1 (100g)", 100)], tags=["vegan"], price=1),
    F("Tomato", "עגבנייה", "veg", 18, 0.9, 0.2, 3.9, "parve",
      [("1 (120g)", 120)], tags=["vegan"], price=1),
    F("Lettuce", "חסה", "veg", 15, 1.4, 0.2, 2.9, "parve",
      [("cup chopped (50g)", 50)], tags=["vegan"], price=1),
    F("Red bell pepper", "פלפל אדום", "veg", 31, 1.0, 0.3, 6.0, "parve",
      [("1 (120g)", 120)], tags=["vegan"], price=1),
    F("Broccoli, cooked", "ברוקולי מבושל", "veg", 35, 2.4, 0.4, 7.0, "parve",
      [("cup (150g)", 150)], tags=["vegan"], prep=2, price=2),
    F("Carrot", "גזר", "veg", 41, 0.9, 0.2, 10.0, "parve",
      [("1 (70g)", 70)], tags=["vegan"], price=1),
    F("Onion", "בצל", "veg", 40, 1.1, 0.1, 9.0, "parve",
      [("half (55g)", 55)], tags=["vegan"], price=1),
    F("Zucchini", "קישוא", "veg", 17, 1.2, 0.3, 3.1, "parve",
      [("1 (180g)", 180)], tags=["vegan"], prep=2, price=1),
    F("Mixed vegetable salad", "סלט ירקות", "veg", 20, 1.0, 0.2, 4.2, "parve",
      [("bowl (200g)", 200)], tags=["vegan"], prep=1, price=1),

    # ---------- fats ----------
    F("Olive oil", "שמן זית", "fat", 884, 0.0, 100.0, 0.0, "parve",
      [("tbsp (13g)", 13), ("tsp (4.5g)", 4.5)], tags=["vegan"], price=2),
    F("Raw tahini", "טחינה גולמית", "fat", 595, 17.0, 53.0, 21.0, "parve",
      [("tbsp (15g)", 15), ("2 tbsp", 30)], allergens=["Sesame"], tags=["vegan"], price=1),
    F("Avocado", "אבוקדו", "fat", 160, 2.0, 15.0, 9.0, "parve",
      [("half (100g)", 100), ("whole (200g)", 200)], tags=["vegan"], price=2),
    F("Almonds", "שקדים", "fat", 579, 21.0, 50.0, 22.0, "parve",
      [("handful (30g)", 30)], allergens=["Tree nuts"], tags=["vegan"], price=3),
    F("Walnuts", "אגוזי מלך", "fat", 654, 15.0, 65.0, 14.0, "parve",
      [("handful (30g)", 30)], allergens=["Tree nuts"], tags=["vegan"], price=3),
    F("Peanut butter", "חמאת בוטנים", "fat", 588, 25.0, 50.0, 20.0, "parve",
      [("tbsp (16g)", 16)], allergens=["Peanuts"], tags=["vegan"], price=2),
    F("Green olives", "זיתים ירוקים", "fat", 145, 1.0, 15.0, 3.8, "parve",
      [("10 olives (40g)", 40)], tags=["vegan"], price=1),
    F("Sunflower seeds", "גרעיני חמנייה", "fat", 584, 21.0, 51.0, 20.0, "parve",
      [("handful (30g)", 30)], tags=["vegan"], price=1),

    # ---------- fruit ----------
    F("Banana", "בננה", "fruit", 89, 1.1, 0.3, 23.0, "parve",
      [("1 (118g)", 118)], tags=["vegan"], price=1),
    F("Apple", "תפוח", "fruit", 52, 0.3, 0.2, 14.0, "parve",
      [("1 (180g)", 180)], tags=["vegan"], price=1),
    F("Medjool date", "תמר מג'הול", "fruit", 277, 1.8, 0.2, 75.0, "parve",
      [("1 date (24g)", 24), ("2 dates", 48)], tags=["vegan"], price=2),
    F("Strawberries", "תות שדה", "fruit", 32, 0.7, 0.3, 7.7, "parve",
      [("cup (150g)", 150)], tags=["vegan"], price=3),
    F("Grapefruit", "אשכולית", "fruit", 42, 0.8, 0.1, 11.0, "parve",
      [("half (120g)", 120)], tags=["vegan"], price=1),

    # ---------- drinks ----------
    F("Milk 3%", "חלב 3%", "drink", 61, 3.2, 3.3, 4.8, "dairy",
      [("cup (240g)", 240)], allergens=["Milk"], price=1, complete=True, quality=3),
    F("Almond milk, unsweetened", "משקה שקדים", "drink", 15, 0.5, 1.2, 0.6, "parve",
      [("cup (240g)", 240)], allergens=["Tree nuts"], tags=["vegan"], price=2),
    # ---- plant proteins (added after the vegan feasibility finding) ----
    F("Seitan", "סייטן", "protein", 370, 75.0, 1.9, 14.0, "parve",
      [("100g", 100), ("portion (150g)", 150)], allergens=["Gluten"],
      tags=["vegan"], prep=1, price=2, quality=1),
    F("Tempeh", "טמפה", "protein", 192, 20.3, 10.8, 7.6, "parve",
      [("100g", 100)], allergens=["Soy"], tags=["vegan"], prep=2, price=2, complete=True, quality=2),
    F("Edamame", "אדממה", "protein", 121, 12.0, 5.2, 8.9, "parve",
      [("cup (155g)", 155)], allergens=["Soy"], tags=["vegan"], prep=1, price=2, complete=True, quality=2),
    F("Textured soy protein", "חלבון סויה", "protein", 330, 52.0, 1.2, 33.0, "parve",
      [("50g dry", 50)], allergens=["Soy"], tags=["vegan"], prep=1, price=1, complete=True, quality=2),
    F("Pea protein powder", "אבקת חלבון אפונה", "protein", 380, 80.0, 5.0, 3.0, "parve",
      [("scoop (30g)", 30)], tags=["vegan"], prep=0, price=2, supp=True, quality=1),
    F("Black beans, cooked", "שעועית שחורה", "protein", 132, 8.9, 0.5, 24.0, "parve",
      [("cup (172g)", 172)], tags=["vegan"], prep=2, price=1, quality=1),
    F("Soy milk", "משקה סויה", "drink", 54, 3.3, 1.8, 6.0, "parve",
      [("cup (240g)", 240)], allergens=["Soy"], tags=["vegan"], price=1, complete=True, quality=2),
]
# ---------------------------------------------------------------------------
# Serving units, split into two kinds:
#   tuple -> a DISCRETE item (a tub, an egg, a slice). The solver may only use
#            whole or half units of it. "0.8 of a tub" is not a thing.
#   None  -> sold by WEIGHT (chicken, mince, fish, tofu). Any gram amount is
#            fine; the UI shows grams.
UNIT = {'Chicken breast': None, 'Chicken thigh, skinless': ('שוק', 'שוקיים', 150),
        'Ground beef 10%': None, 'Ground turkey': None, 'Turkey schnitzel': ('פרוסה', 'פרוסות', 120),
        'Canned tuna in water': ('קופסה', 'קופסאות', 100),
        'Salmon': None, 'Tilapia fillet': None, 'Egg': ('ביצה', 'ביצים', 52),
        'Tofu': None, 'Lentils, cooked': None,
        'Chickpeas, cooked': None,
        'Whey protein powder': ('מנה', 'מנות', 30),
        'Cottage cheese 5%': ('גביע', 'גביעים', 250),
        'White cheese 5%': ('גביע', 'גביעים', 250),
        'White cheese 3%': ('גביע', 'גביעים', 250),
        'Greek yogurt 0%': ('גביע', 'גביעים', 150),
        'Plain yogurt 3%': ('גביע', 'גביעים', 200),
        'Yellow cheese 28%': ('פרוסה', 'פרוסות', 25),
        'Mozzarella': None, 'White rice, cooked': None,
        'Brown rice, cooked': None,
        'Pasta, cooked': None,
        'Couscous, cooked': None,
        'Sweet potato, baked': ('בטטה', 'בטטות', 150),
        'Potato, boiled': ('תפוח אדמה', 'תפוחי אדמה', 170),
        'Whole wheat bread': ('פרוסה', 'פרוסות', 30),
        'White bread': ('פרוסה', 'פרוסות', 25),
        'Whole wheat pita': ('פיתה', 'פיתות', 60),
        'Oats': None,
        'Tortilla': ('טורטייה', 'טורטיות', 50),
        'Quinoa, cooked': None,
        'Cucumber': ('מלפפון', 'מלפפונים', 100),
        'Tomato': ('עגבנייה', 'עגבניות', 120),
        'Lettuce': None,
        'Red bell pepper': ('פלפל', 'פלפלים', 120),
        'Broccoli, cooked': None, 'Carrot': ('גזר', 'גזרים', 70),
        'Onion': ('בצל', 'בצלים', 110),
        'Zucchini': ('קישוא', 'קישואים', 180),
        'Mixed vegetable salad': None, 'Olive oil': ('כף', 'כפות', 13),
        'Raw tahini': ('כף', 'כפות', 15),
        'Avocado': ('אבוקדו', 'אבוקדו', 200),
        'Almonds': ('חופן', 'חופנים', 30),
        'Walnuts': ('חופן', 'חופנים', 30),
        'Peanut butter': ('כף', 'כפות', 16),
        'Green olives': ('מנת זיתים', 'מנות זיתים', 40),
        'Sunflower seeds': ('חופן', 'חופנים', 30),
        'Banana': ('בננה', 'בננות', 118),
        'Apple': ('תפוח', 'תפוחים', 180),
        'Medjool date': ('תמר', 'תמרים', 24),
        'Strawberries': None,
        'Grapefruit': ('אשכולית', 'אשכוליות', 240),
        'Milk 3%': ('כוס', 'כוסות', 240),
        'Almond milk, unsweetened': ('כוס', 'כוסות', 240),
        'Seitan': None, 'Tempeh': None, 'Edamame': None,
        'Textured soy protein': None, 'Pea protein powder': ('מנה', 'מנות', 30),
        'Black beans, cooked': None,
        'Soy milk': ('כוס', 'כוסות', 240)}

# Halves make no sense for these - you do not cook half an egg.
WHOLE_ONLY = {"Egg", "Medjool date", "Whole wheat pita", "Tortilla",
              "Turkey schnitzel", "Cucumber", "Tomato", "Red bell pepper",
              "Banana", "Apple"}

# Hard ceilings in grams where the unit maths allows an absurd amount.
MAX_G = {"Avocado": 200, "Green olives": 60, "Olive oil": 40, "Raw tahini": 45,
         "Peanut butter": 48, "Almonds": 45, "Walnuts": 45, "Sunflower seeds": 45,
         "Whey protein powder": 60, "Pea protein powder": 60,
         "Medjool date": 72, "Yellow cheese 28%": 75}

for i, f in enumerate(FOODS):
    u = UNIT.get(f["name"])
    f["whole_only"] = f["name"] in WHOLE_ONLY
    f["max_g"] = MAX_G.get(f["name"])
    f["unit"] = {"he": u[0], "he_plural": u[1], "grams": u[2]} if u else None
    f["by_weight"] = u is None

    f["id"] = i + 1
    f["menu_eligible"] = True

ALL_ALLERGENS = sorted({a for f in FOODS for a in f["allergens"]})


def macros_for(food, grams):
    k = grams / 100.0
    return dict(kcal=food["kcal"] * k, protein=food["protein"] * k,
                fat=food["fat"] * k, carb=food["carb"] * k)
