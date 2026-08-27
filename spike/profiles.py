# -*- coding: utf-8 -*-
"""100 diverse profiles, including deliberately hostile ones."""
import random
from foods import FOODS, ALL_ALLERGENS

random.seed(7)
NAMES = [f["name"] for f in FOODS]


def make(i):
    sex = random.choice(["male", "female"])
    age = random.randint(19, 62)
    height = random.randint(155, 192) if sex == "male" else random.randint(150, 180)
    weight = round(random.uniform(52, 118), 1)
    has_bf = random.random() < 0.55
    bf = round(random.uniform(9, 34) if sex == "male" else random.uniform(17, 44), 1) if has_bf else None
    goal = random.choice(["lose", "lose", "lose", "maintain", "gain"])

    p = dict(
        id=i, sex=sex, age=age, height=height, weight=weight, bf=bf, goal=goal,
        rate=random.choice(["slow", "moderate", "fast"]),
        neat=random.choice(["sedentary", "light", "physical", "heavy"]),
        sessions=random.randint(0, 6), minutes=random.choice([0, 30, 45, 60, 75]),
        kind=random.choice(["strength", "run", "bike", "none", "sport"]),
        meals=random.choice([3, 3, 4, 5]),
        diet=random.choices(["omni", "vegetarian", "vegan"], [.75, .17, .08])[0],
        kosher=random.choices(["none", "kosher", "separated"], [.45, .3, .25])[0],
        cooking=random.choices(["minimal", "medium", "loves"], [.3, .5, .2])[0],
        budget=random.choices(["cheap", "normal", "any"], [.25, .55, .2])[0],
        allergies=random.sample(ALL_ALLERGENS, random.choice([0, 0, 0, 1, 1, 2])),
        dislikes=random.sample(NAMES, random.choice([0, 1, 2, 3, 5, 8])),
        wake=random.choice(["05:30", "06:30", "07:00", "08:00", "10:00"]),
        sleep=random.choice(["22:00", "23:00", "00:00", "01:00"]),
    )
    if p["sessions"] == 0:
        p["kind"], p["minutes"] = "none", 0
    if goal == "lose" and random.random() < 0.25:
        p["target_weight"] = round(weight * random.uniform(0.72, 0.9), 1)
    if bf and goal == "lose" and random.random() < 0.2:
        p["target_bf"] = round(random.uniform(6, 18), 1)
    return p


PROFILES = [make(i) for i in range(1, 96)]

# ---- hand-built adversarial cases ----
PROFILES += [
    dict(id=96, sex="female", age=24, height=168, weight=54, bf=19.0, goal="lose", rate="fast",
         neat="sedentary", sessions=5, minutes=60, kind="run", meals=3, diet="omni",
         kosher="none", cooking="medium", budget="normal", allergies=[], dislikes=[],
         target_bf=10.0, wake="06:00", sleep="23:00", _expect="BF_FLOOR"),

    dict(id=97, sex="male", age=30, height=180, weight=70, bf=None, goal="lose", rate="fast",
         neat="sedentary", sessions=0, minutes=0, kind="none", meals=3, diet="omni",
         kosher="none", cooking="minimal", budget="cheap", allergies=[], dislikes=[],
         target_weight=55.0, wake="07:00", sleep="23:00", _expect="BMI_FLOOR"),

    dict(id=98, sex="female", age=45, height=160, weight=58, bf=26.0, goal="lose", rate="fast",
         neat="sedentary", sessions=0, minutes=0, kind="none", meals=3, diet="vegan",
         kosher="separated", cooking="minimal", budget="cheap",
         allergies=["Gluten", "Tree nuts", "Sesame"],
         dislikes=["Tofu", "Lentils, cooked", "Banana"],
         wake="07:00", sleep="23:00", _expect="TIGHT_POOL"),

    dict(id=99, sex="male", age=22, height=185, weight=95, bf=8.5, goal="lose", rate="fast",
         neat="heavy", sessions=6, minutes=75, kind="strength", meals=5, diet="omni",
         kosher="none", cooking="loves", budget="any", allergies=[], dislikes=[],
         wake="05:30", sleep="22:00", _expect="LEAN_CAP"),

    dict(id=100, sex="female", age=58, height=152, weight=49, bf=None, goal="lose", rate="fast",
         neat="sedentary", sessions=0, minutes=0, kind="none", meals=3, diet="omni",
         kosher="kosher", cooking="minimal", budget="cheap", allergies=[], dislikes=[],
         wake="08:00", sleep="00:00", _expect="ABS_FLOOR"),
]
