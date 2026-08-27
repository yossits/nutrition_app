# nutrition_app

אפליקציית ליווי תזונה אישי. המשתמש בונה פרופיל, המערכת מחשבת יעדים ומייצרת תפריט מותאם, ומעדכנת אותו לאורך התוכנית.

**סטטוס:** אפיון סגור · ליבה מוכחת (92% על 40 ייצורים) · שלב נוכחי: ייבוא מאגר משרד הבריאות

**להתחיל מ-[`docs/README.md`](docs/README.md), ואז [`docs/PROGRESS.md`](docs/PROGRESS.md).** שם הניווט, מצב העבודה, וכל השאר.

---

## ⚠️ לפני הכל — מפתחות API

**אף פעם לא לשמור מפתח API בתוך קובץ בריפו.** בוטים סורקים את זרם האירועים הציבורי של GitHub ומוצאים מפתחות תוך דקות.

המפתח נמסר כמשתנה סביבה בלבד:

```bash
# Windows
set ANTHROPIC_API_KEY=sk-ant-...

# Mac / Linux
export ANTHROPIC_API_KEY=sk-ant-...
```

ה-`.gitignore` חוסם `.env` וקבצי מפתחות. אם מפתח נחשף אי פעם — לבטל אותו מיד ב-console.anthropic.com ולהנפיק חדש. מחיקת הקומיט **לא** מספיקה; הוא נשאר בהיסטוריה.

---

## מבנה

```
nutrition_app/
├── docs/                 # התיעוד. נקודת הכניסה: docs/README.md
│   ├── PROGRESS.md       #   ★ מצב העבודה — המקור היחיד לאמת
│   ├── spec/             #   האפיון, 12 מודולים
│   ├── work/             #   יומני עבודה
│   └── prototypes/       #   אב-טיפוס מסך התפריט
├── db/                   # סכימת מאגר המזון (Postgres/Supabase)
└── spike/                # הליבה — מוכחת ונמדדת. מפת הקבצים: docs/spec/09-architecture.md
```

---

## הרצה

```bash
pip install -r requirements.txt

cd spike
python run_spike.py                 # ליבה דטרמיניסטית, ללא מפתח

set ANTHROPIC_API_KEY=sk-ant-...
python run_generation.py 40         # שיעור מעבר מול ה-API
python show_menus.py 8              # יוצר menus.html לפתיחה בדפדפן
```

---

## הארכיטקטורה בשורה אחת

> **המודל מרכיב. הקוד מחשב. הקוד מאמת.**

מודל שפה מרכיב ארוחה טוב ומחשב חשבון גרוע — כשביקשנו ממנו גם לחשב, שיעור המעבר היה 0%. וזה גם קו הבטיחות: אלרגן שלא נכנס לפרומפט לא יכול להופיע בפלט.

הפירוט: [`docs/spec/06-generator.md`](docs/spec/06-generator.md) · המספרים: [`docs/measurements.md`](docs/measurements.md)

---

## הערה

הפרויקט אינו תחליף לייעוץ רפואי או תזונתי מקצועי.
