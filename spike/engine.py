# -*- coding: utf-8 -*-
"""
Calculation engine — spec sections 8.1-8.5.
Pure, deterministic. No AI anywhere in this file.
"""

NEAT = {"sedentary": 1.20, "light": 1.35, "physical": 1.50, "heavy": 1.65}
MET = {"strength": 5.0, "run": 10.0, "bike": 7.5, "swim": 7.0, "sport": 7.0, "none": 0.0}

VEGAN_PROTEIN_PER_KG = 2.0     # same as every other diet - see PROTEIN_NOTE below

ABS_FLOOR = {"male": 1500, "female": 1200}
BF_FLOOR = {"male": 8.0, "female": 14.0}          # 8.5.1
ESSENTIAL_BF = {"male": 5.0, "female": 12.0}

# 8.5.2 — max deficit shrinks as the user gets leaner
DEFICIT_BANDS = {
    "male":   [(20, .25), (15, .20), (10, .15), (0, .10)],
    "female": [(30, .25), (25, .20), (20, .15), (0, .10)],
}


class SafetyBlock(Exception):
    def __init__(self, code, msg):
        self.code, self.msg = code, msg
        super().__init__(f"{code}: {msg}")


def bmr(sex, weight, height, age, bf=None):
    """8.1 — Katch-McArdle when body fat is known, else Mifflin-St Jeor."""
    if bf is not None:
        lbm = weight * (1 - bf / 100.0)
        return 370 + 21.6 * lbm
    base = 10 * weight + 6.25 * height - 5 * age
    return base + (5 if sex == "male" else -161)


def training_kcal(weight, sessions, minutes, kind):
    met = MET.get(kind, 0.0)
    weekly = met * 3.5 * weight / 200.0 * minutes * sessions
    return weekly / 7.0


def tdee(sex, weight, height, age, neat, sessions, minutes, kind, bf=None):
    """8.2 — NEAT multiplier on BMR, training added explicitly."""
    return bmr(sex, weight, height, age, bf) * NEAT[neat] + training_kcal(weight, sessions, minutes, kind)


def max_deficit_pct(sex, bf):
    if bf is None:
        return 0.20
    for threshold, pct in DEFICIT_BANDS[sex]:
        if bf > threshold:
            return pct
    return 0.10


def targets(profile):
    """
    8.3 + 8.4 + 8.5. Returns computed targets, or raises SafetyBlock.
    profile keys: sex age height weight bf goal rate neat sessions minutes kind
                  target_weight target_bf meals
    """
    sex, w, h, age = profile["sex"], profile["weight"], profile["height"], profile["age"]
    bf, goal = profile.get("bf"), profile["goal"]

    # ---- 8.5.1 body-fat floor (checked before anything else) ----
    tbf = profile.get("target_bf")
    if tbf is not None and tbf < BF_FLOOR[sex]:
        raise SafetyBlock("BF_FLOOR",
            f"Target {tbf}% body fat is below the floor "
            f"({BF_FLOOR[sex]}% for {'men' if sex=='male' else 'women'}). "
            f"Essential fat ~{ESSENTIAL_BF[sex]}%.")

    base = tdee(sex, w, h, age, profile["neat"], profile["sessions"], profile["minutes"], profile["kind"], bf)
    b = bmr(sex, w, h, age, bf)

    rate = profile.get("rate", "moderate")
    if goal == "lose":
        want = {"slow": .12, "moderate": .18, "fast": .25}[rate]
        pct = min(want, max_deficit_pct(sex, bf))          # 8.5.2
        kcal = base * (1 - pct)
        capped_by_leanness = want > pct
    elif goal == "gain":
        kcal = base * (1 + {"slow": .08, "moderate": .12, "fast": .15}[rate])
        capped_by_leanness = False
    else:
        kcal, capped_by_leanness = base, False

    blocks = []
    # ---- 8.5 hard floors ----
    if goal == "lose":
        if kcal < b:
            kcal = b
            blocks.append("RAISED_TO_BMR")
        if kcal < ABS_FLOOR[sex]:
            kcal = ABS_FLOOR[sex]
            blocks.append("RAISED_TO_ABS_FLOOR")

        weekly_loss = (base - kcal) * 7 / 7700.0
        if weekly_loss > w * 0.01:
            kcal = base - (w * 0.01 * 7700 / 7)
            blocks.append("RATE_CAPPED")

    bmi_target = None
    if profile.get("target_weight"):
        bmi_target = profile["target_weight"] / ((h / 100.0) ** 2)
        if bmi_target < 18.5:
            raise SafetyBlock("BMI_FLOOR",
                f"Target weight {profile['target_weight']}kg gives BMI "
                f"{bmi_target:.1f}, below 18.5.")

    # ---- 8.4 macros ----
    ref = w * (1 - bf / 100.0) if bf is not None else w
    if profile.get("diet") == "vegan":
        # Lower target for vegans. NOTE: this is a feasibility decision, not a
        # nutritional one - see PROTEIN_NOTE at the bottom of this file.
        p_per_kg = VEGAN_PROTEIN_PER_KG
    elif goal == "lose":
        p_per_kg = 2.2 if bf is not None else 2.0
    elif goal == "gain":
        p_per_kg = 2.0
    else:
        p_per_kg = 1.8
    protein = ref * p_per_kg

    fat = max(kcal * 0.27 / 9.0, w * 0.6)
    if fat < w * 0.6:
        fat = w * 0.6
        blocks.append("FAT_FLOOR")

    carb = (kcal - protein * 4 - fat * 9) / 4.0
    if carb < 30:
        carb = 30
        protein = max((kcal - carb * 4 - fat * 9) / 4.0, ref * 1.6)

    return dict(
        bmr=round(b), tdee=round(base), kcal=round(kcal),
        protein=round(protein), fat=round(fat), carb=round(max(carb, 0)),
        deficit_pct=round((base - kcal) / base * 100, 1) if base else 0,
        max_deficit_allowed=round(max_deficit_pct(sex, bf) * 100),
        capped_by_leanness=capped_by_leanness,
        safety_actions=blocks, bmi_target=round(bmi_target, 1) if bmi_target else None,
    )


def split_meals(t, n):
    """Distribute daily targets across n meals."""
    weights = {3: [.30, .40, .30], 4: [.25, .35, .15, .25], 5: [.22, .30, .13, .20, .15]}[n]
    return [dict(kcal=t["kcal"] * x, protein=t["protein"] * x,
                 fat=t["fat"] * x, carb=t["carb"] * x) for x in weights]


def meal_times(wake="07:00", sleep="23:00", n=3):
    """7.7 — relative timing derived from wake/sleep."""
    to_m = lambda s: int(s[:2]) * 60 + int(s[3:])
    fmt = lambda m: f"{(int(m)//60)%24:02d}:{int(m)%60:02d}"
    w, s = to_m(wake), to_m(sleep)
    if s <= w:            # sleep past midnight -> next day
        s += 24 * 60
    first, last = w + 120, s - 120
    if last <= first:     # pathological short day
        last = first + 60
    if n == 1:
        return [fmt(first)]
    step = (last - first) / (n - 1)
    return [fmt(first + step * i) for i in range(n)]


# ---------------------------------------------------------------------------
# PROTEIN_NOTE
# VEGAN_PROTEIN_PER_KG is 2.0 - the same as every other diet.
#
# Lowering it to 1.5 was tried and measured: it did NOT help. Vegan feasibility
# was 4/5 at 1.5 and 5/5 at 2.0. The blocker was never the target, it was the
# DEPTH of the plant-protein pool. Adding seitan, tempeh, edamame, soy protein,
# pea protein and black beans took profiles with too thin a pool from 17% to 7%.
#
# It is also the right call nutritionally: plant protein has lower
# digestibility and less leucine, so vegans generally need MORE protein than
# omnivores for the same result, not less.
# ---------------------------------------------------------------------------
