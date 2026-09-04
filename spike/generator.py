# -*- coding: utf-8 -*-
"""
Menu generator - the ONE place AI is used for composition.

Design notes that matter:
  * Only the sampled, filtered pool enters the prompt. An allergen that never
    enters the prompt cannot appear in the output. That is the real safeguard.
  * The user's raw free text NEVER enters this prompt. Only validated
    structured profile fields do.
  * Output is a hard JSON schema. Code validates; on failure we retry and feed
    the specific validation errors back to the model.

PRODUCTION NOTE: this spike prompts in English so terminal output is readable.
For production, swap SYSTEM to Hebrew and use f['he'] instead of f['name']
in build_prompt(). The pipeline is otherwise identical.
"""
import json, requests

MODEL = "claude-sonnet-4-6"
API = "https://api.anthropic.com/v1/messages"
MAX_ATTEMPTS = 3

SYSTEM = """You compose daily meal plans for a nutrition app.

You choose WHICH foods go in each meal. You do NOT need to hit the numeric
targets - a separate deterministic solver sets the exact portions afterwards.
Do not do arithmetic. Focus entirely on whether the meal makes sense as food.

Absolute rules:
1. Use ONLY items from the provided list. Never invent an item.
2. Every meal needs at least one protein source and one carb source, plus a
   vegetable where it fits. Add a fat source when the dish calls for it.
   The main protein of every meal must be one marked "HIGH-QUALITY protein"
   whenever the diet allows - meat, fish, eggs and dairy have the highest
   biological value. Items marked "supporting protein" (legumes, grains,
   seitan) are side players, never the centrepiece. On vegan profiles lead
   with soy-based sources instead.
3. For meals above ~700 kcal, include two protein or two carb sources so the
   solver has room to work - but they must be DIFFERENT kinds of food. Never
   put white rice and brown rice in the same meal, or two near-identical items.
4. Never mix meat and dairy in the same meal.
5. A meal must make culinary sense - foods that are actually eaten together.
6. Use the meal names EXACTLY as given, in the order given, once each.
   Do not translate them, do not describe the dish in the name.
7. Every meal must be DIFFERENT from the others. Never repeat the same
   combination twice in one day.
8. No single food may appear in more than two meals across the whole day.
9. Protein powder is a supplement, not a meal. At most ONE shake in the whole
   day, and never as the main protein of a cooked meal. Whole foods carry the
   protein - a chicken breast should be a portion, not a garnish.
10. Match the food to the time of day. Eggs, dairy and spreads belong at
   breakfast; a cooked protein with a side belongs at lunch or dinner. Do not
   serve a breakfast plate as the evening meal.
11. Copy the food name EXACTLY as it appears inside the quotes in the list.
    Do not include the descriptor in parentheses that follows it.
12. Return JSON only. No prose before or after, no markdown fences.

Output schema (grams are a rough starting point, the solver will adjust them):
{"meals":[{"name":"<meal name>","items":[{"food":"<exact name from list>","grams":<approx>}]}]}"""


def build_prompt(day_targets, meal_targets, meal_names, pool):
    lines = []
    for f in pool:
        units = " / ".join(f"{lbl}={g}g" for lbl, g in f["servings"])
        lines.append(
            f"- \"{f['name']}\"  ({f['cat']}, {f['kosher']}"
            f"{', complete' if f.get('complete') else ''}"
            f"{', HIGH-QUALITY protein' if f.get('quality') == 3 else ''}"
            f"{', supporting protein' if f.get('quality') == 1 else ''}) per 100g: "
            f"{f['kcal']}kcal P{f['protein']} F{f['fat']} C{f['carb']} | {units}")

    per_meal = "\n".join(
        f"  {n}: {m['kcal']:.0f} kcal, {m['protein']:.0f}g protein"
        for n, m in zip(meal_names, meal_targets))

    return f"""Daily target: {day_targets['kcal']} kcal | {day_targets['protein']}g protein | {day_targets['fat']}g fat | {day_targets['carb']}g carbs

Per-meal targets:
{per_meal}

Available foods ({len(pool)} items - these and only these):
{chr(10).join(lines)}

Compose a {len(meal_names)}-meal plan. Pick foods that go together.
Portions are approximate - the solver will set the final grams.

Fat budget is {day_targets['fat']}g against {day_targets['protein']}g of protein.
When that ratio is tight, lean protein sources leave room; fatty ones do not."""


def call_api(prompt, key, feedback=None):
    msgs = [{"role": "user", "content": prompt}]
    if feedback:
        prev = (feedback.get("last") or "").strip()
        if not prev:
            prev = "(no output)"          # empty assistant content is a 400
        msgs.append({"role": "assistant", "content": prev})
        msgs.append({"role": "user", "content":
                     "The plan failed validation:\n" + "\n".join(feedback["errors"]) +
                     "\nFix it and return corrected JSON only."})
    r = requests.post(API, timeout=90,
        headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                 "content-type": "application/json"},
        json={"model": MODEL, "max_tokens": 4000, "system": SYSTEM, "messages": msgs})
    if r.status_code != 200:
        try:
            detail = r.json().get("error", {}).get("message", r.text[:200])
        except Exception:
            detail = r.text[:200]
        raise RuntimeError(f"HTTP {r.status_code}: {detail}")
    body = r.json()
    text = "".join(b.get("text", "") for b in body["content"] if b["type"] == "text")
    return text, body.get("usage", {})


def parse(text):
    t = text.strip()
    if t.startswith("```"):
        t = t.split("```")[1]
        t = t[4:] if t.startswith("json") else t
    return json.loads(t.strip())


def generate(profile, day_targets, meal_targets, meal_names, pool, key, validate_fn):
    """Returns (menu | None, attempts, usage_total, errors)."""
    prompt = build_prompt(day_targets, meal_targets, meal_names, pool)
    feedback, usage_total, last_errs = None, {"input_tokens": 0, "output_tokens": 0}, []

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            text, usage = call_api(prompt, key, feedback)
        except Exception as ex:
            last_errs = [f"API_ERROR: {ex}"]
            break
        for k in usage_total:
            usage_total[k] += usage.get(k, 0)
        try:
            menu = parse(text)["meals"]
        except Exception as ex:
            feedback = {"last": text, "errors": [f"Invalid JSON: {ex}"]}
            last_errs = [f"BAD_JSON: {ex}"]
            continue
        ok, errs = validate_fn(menu)
        if ok:
            return menu, attempt, usage_total, []
        feedback, last_errs = {"last": text, "errors": errs}, errs

    return None, MAX_ATTEMPTS, usage_total, last_errs
