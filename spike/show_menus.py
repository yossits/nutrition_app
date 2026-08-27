# -*- coding: utf-8 -*-
"""
The test the validator cannot do: are these actually meals people would eat?

    Windows:    set ANTHROPIC_API_KEY=sk-ant-...
                python show_menus.py 8
    Mac/Linux:  ANTHROPIC_API_KEY=sk-ant-... python3 show_menus.py 8

Writes menus.html - open it in a browser. Hebrew renders correctly there,
so this doubles as a preview of the real product output.
"""
import os, sys, html, random
from engine import targets, split_meals, meal_times, SafetyBlock
from filters import eligible, validate, pool_health, sample_for_prompt, resolve
from portions import solve, feasible, describe
from generator import generate
from profiles import PROFILES

KEY = os.environ.get("ANTHROPIC_API_KEY")
if not KEY:
    sys.exit("Missing ANTHROPIC_API_KEY")

N = int(sys.argv[1]) if len(sys.argv) > 1 else 8

MEAL_NAMES = {
    3: ["ארוחת בוקר", "ארוחת צהריים", "ארוחת ערב"],
    4: ["ארוחת בוקר", "ארוחת צהריים", "ארוחת ביניים", "ארוחת ערב"],
    5: ["ארוחת בוקר", "ארוחת ביניים", "ארוחת צהריים",
        "ארוחת ביניים אחה\"צ", "ארוחת ערב"],
}
DIET_HE = {"omni": "רגיל", "vegetarian": "צמחוני", "vegan": "טבעוני"}
GOAL_HE = {"lose": "ירידה בשומן", "gain": "עלייה במסה", "maintain": "תחזוקה"}
KOSHER_HE = {"none": "ללא", "kosher": "כשר", "separated": "כשר בהפרדה"}

runnable = []
for p in PROFILES:
    try:
        t = targets(p)
    except SafetyBlock:
        continue
    pool = eligible(p)
    if not pool_health(pool, p)[0]:
        continue
    if not feasible(sample_for_prompt(pool, p), t)[0]:
        continue
    runnable.append((p, t, pool))

random.seed(11)
picked = random.sample(runnable, min(N, len(runnable)))

cards = []
for i, (p, t, pool) in enumerate(picked, 1):
    names = MEAL_NAMES[p["meals"]]
    sub = sample_for_prompt(pool, p)
    store = {}

    def vf(menu, _p=p, _t=t, _pool=pool, _s=store):
        picks = []
        for meal in menu:
            items = []
            for it in meal.get("items", []):
                f = resolve(it.get("food"), _pool)
                if f is None:
                    return False, ["UNKNOWN_FOOD: %s" % it.get("food")]
                it["food"] = f["name"]
                items.append((f, float(it.get("grams", 100))))
            if items:
                picks.append(items)
        if not picks:
            return False, ["EMPTY_MENU"]
        solved, _ok, info = solve(picks, split_meals(_t, len(picks)), _t,
                                  fat_floor=_p.get("weight", 0) * 0.6)
        for meal, sm in zip(menu, solved):
            meal["items"] = [{"food": f["name"], "grams": g} for f, g in sm]
        _s["solved"], _s["info"] = solved, info
        return validate(menu, _p, _t, _pool)

    menu, att, usage, errs = generate(p, t, split_meals(t, p["meals"]), names,
                                      sub, KEY, vf)
    print("  %d/%d  #%s  %s" % (i, len(picked), p["id"],
          ("OK attempt %d" % att) if menu
          else ("FAIL - %s" % (errs[0] if errs else ""))))
    if not menu:
        continue

    times = meal_times(p["wake"], p["sleep"], p["meals"])
    solved = store.get("solved", [])
    info = store.get("info", {})
    tot = info.get("totals", {})

    meals_html = ""
    for m, sm, tm in zip(menu, solved, times):
        rows = ""
        for f, g in sm:
            rows += ('<li><span class="fd">%s</span><span class="q">%s</span></li>'
                     % (html.escape(f["he"]), html.escape(describe(f, g))))
        mk = sum(f["kcal"] * g / 100 for f, g in sm)
        mp = sum(f["protein"] * g / 100 for f, g in sm)
        mf = sum(f["fat"] * g / 100 for f, g in sm)
        mc = sum(f["carb"] * g / 100 for f, g in sm)
        meals_html += (
            '<div class="meal"><div class="mh"><b>%s</b><time>%s</time></div>'
            '<ul>%s</ul><div class="mm">%.0f קק"ל · חלבון %.0f · שומן %.0f · פחמימה %.0f</div></div>'
            % (html.escape(str(m.get("name", ""))[:30]), tm, rows, mk, mp, mf, mc))

    cards.append(
        '<section class="card"><header><h2>פרופיל #%s</h2>'
        '<p>%s · %s · %s ק"ג · %s · %s · %s ארוחות</p>'
        '<p class="cons">אלרגיות: %s · לא אוכל: %d פריטים · כשרות: %s</p></header>'
        '<div class="tgt">יעד: <b>%s</b> קק"ל · חלבון <b>%s</b> · שומן <b>%s</b> · פחמימה <b>%s</b><br>'
        'בפועל: <b>%s</b> · <b>%s</b> · <b>%s</b> · <b>%s</b>'
        '<span class="err"> (סטייה %s%% / %s%%)</span></div>%s</section>'
        % (p["id"], "גבר" if p["sex"] == "male" else "אישה", p["age"], p["weight"],
           GOAL_HE[p["goal"]], DIET_HE[p["diet"]], p["meals"],
           ", ".join(p["allergies"]) or "אין", len(p["dislikes"]),
           KOSHER_HE.get(p["kosher"], p["kosher"]),
           t["kcal"], t["protein"], t["fat"], t["carb"],
           tot.get("kcal", "?"), tot.get("protein", "?"),
           tot.get("fat", "?"), tot.get("carb", "?"),
           info.get("kcal_err", "?"), info.get("protein_err", "?"), meals_html))

CSS = """
body{background:#EAE8DE;font-family:Heebo,Arial,sans-serif;color:#2C3327;margin:0;padding:30px 16px}
h1{text-align:center;font-weight:700;margin-bottom:6px}
.sub{text-align:center;color:#8A8A7C;font-size:14px;margin-bottom:30px;font-weight:300}
.wrap{max-width:760px;margin:0 auto;display:flex;flex-direction:column;gap:22px}
.card{background:#FBFAF6;border:1px solid #D6D3C6;border-radius:14px;padding:20px}
header h2{font-size:19px;margin:0 0 4px}
header p{margin:0;font-size:13px;color:#5A6B4A;font-weight:300}
.cons{color:#8A8A7C!important;font-size:12px!important;margin-top:3px!important}
.tgt{background:#2C3327;color:#F0EEE4;border-radius:9px;padding:11px 13px;margin:14px 0;font-size:13px;line-height:1.7}
.err{color:#9AA38C;font-size:12px}
.meal{border-top:1px solid #E4E1D5;padding:13px 0 3px}
.mh{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:8px}
.mh b{font-size:16px}.mh time{font-size:12.5px;color:#8A8A7C}
ul{list-style:none;padding:0;margin:0 0 9px}
li{display:flex;justify-content:space-between;padding:3px 0;font-size:14px;font-weight:300}
.q{color:#5A6B4A;font-size:13px;white-space:nowrap;padding-inline-start:14px}
.mm{font-size:12px;color:#8A8A7C}
"""

doc = ('<!DOCTYPE html><html lang="he" dir="rtl"><head><meta charset="utf-8">'
       '<title>Generated menus</title>'
       '<link href="https://fonts.googleapis.com/css2?family=Heebo:wght@300;400;500;700&display=swap" rel="stylesheet">'
       '<style>%s</style></head><body><h1>תפריטים שנוצרו</h1>'
       '<p class="sub">%d תפריטים · המבחן: האם היית נותן את זה ללקוח?</p>'
       '<div class="wrap">%s</div></body></html>'
       % (CSS, len(cards), "".join(cards)))

with open("menus.html", "w", encoding="utf-8") as fh:
    fh.write(doc)
print("\nWrote menus.html (%d menus). Open it in a browser." % len(cards))
