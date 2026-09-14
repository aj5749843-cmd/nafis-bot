#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===================================================================
   مساعد نافس الذكي — بوت تليجرام تدريبي تراكمي
   يعرض: رياضيات / علوم / لغتي  ←  ناتج التعلم  ←  تدريب تفاعلي
   يميّز: تصحيح فوري + تعلّم من الخطأ + نقاط + تتبّع الأداء
   لوحة تحكم للمعلّمة داخل تليجرام (/dashboard) + بيانات للوحة الويب
===================================================================
كيفية التشغيل باختصار (التفاصيل في ملف "دليل_التشغيل.md"):
  1) pip install "python-telegram-bot>=21"
  2) احصل على توكن من @BotFather وضعه في متغيّر البيئة BOT_TOKEN
  3) ضع رقم معرّفك (Telegram ID) في ADMIN_IDS لترى لوحة التحكم
  4) python nafis_bot.py
"""

import os, json, sqlite3, random, logging, datetime
from telegram import (Update, InlineKeyboardButton, InlineKeyboardMarkup,
                      ReplyKeyboardMarkup)
from telegram.ext import (Application, CommandHandler, CallbackQueryHandler,
                          ContextTypes, MessageHandler, filters)

# ------------------------------------------------------------------
# إعدادات أساسية — عدّليها حسب حاجتك
# ------------------------------------------------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN", "ضع_التوكن_هنا_أو_في_متغير_البيئة")
ADMIN_IDS = [int(x) for x in os.environ.get("ADMIN_IDS", "").split(",") if x.strip().isdigit()]
BANK_FILE = os.path.join(os.path.dirname(__file__), "nafis_bank.json")
DB_FILE   = os.path.join(os.path.dirname(__file__), "nafis_data.db")
QUESTIONS_PER_SESSION = 5          # عدد الأسئلة في الجلسة الواحدة
POINTS_FIRST_TRY = 10              # نقاط الإجابة الصحيحة من أول محاولة
POINTS_AFTER_RETRY = 5            # نقاط الإجابة الصحيحة بعد خطأ

LABELS = ["أ", "ب", "ج", "د"]
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                    level=logging.INFO)
log = logging.getLogger("nafis")

# ------------------------------------------------------------------
# تحميل بنك الأسئلة
# ------------------------------------------------------------------
with open(BANK_FILE, encoding="utf-8") as f:
    BANK = json.load(f)
SUBJECTS = list(BANK["subjects"].keys())

def outcomes_of(subject):
    return BANK["subjects"][subject]["outcomes"]

def questions_of(subject, outcome_id):
    return outcomes_of(subject)[outcome_id]["questions"]

# ------------------------------------------------------------------
# قاعدة البيانات (SQLite) — تتبّع الأداء
# ------------------------------------------------------------------
def db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with db() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS students(
            user_id INTEGER PRIMARY KEY, name TEXT, points INTEGER DEFAULT 0,
            answered INTEGER DEFAULT 0, correct INTEGER DEFAULT 0,
            joined TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS answers(
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
            subject TEXT, outcome TEXT, grade TEXT, q_id INTEGER,
            chosen INTEGER, correct INTEGER, first_try INTEGER, ts TEXT)""")
init_db()

def ensure_student(user):
    with db() as c:
        r = c.execute("SELECT 1 FROM students WHERE user_id=?", (user.id,)).fetchone()
        if not r:
            c.execute("INSERT INTO students(user_id,name,joined) VALUES(?,?,?)",
                      (user.id, user.full_name, datetime.datetime.now().isoformat()))

def record_answer(user_id, subject, outcome, grade, q_id, chosen, correct, first_try):
    with db() as c:
        c.execute("""INSERT INTO answers(user_id,subject,outcome,grade,q_id,
                     chosen,correct,first_try,ts) VALUES(?,?,?,?,?,?,?,?,?)""",
                  (user_id, subject, outcome, grade, q_id, chosen,
                   int(correct), int(first_try), datetime.datetime.now().isoformat()))
        c.execute("UPDATE students SET answered=answered+1, correct=correct+? WHERE user_id=?",
                  (int(correct), user_id))

def add_points(user_id, pts):
    with db() as c:
        c.execute("UPDATE students SET points=points+? WHERE user_id=?", (pts, user_id))

# ------------------------------------------------------------------
# لوحات الأزرار
# ------------------------------------------------------------------
def kb_home():
    rows = [[InlineKeyboardButton(f"📘 {s}", callback_data=f"subj|{s}")] for s in SUBJECTS]
    rows.append([InlineKeyboardButton("📊 تقدّمي", callback_data="me")])
    return InlineKeyboardMarkup(rows)

def kb_outcomes(subject):
    rows = []
    for loid, lo in outcomes_of(subject).items():
        title = lo["title"][:42] + ("…" if len(lo["title"]) > 42 else "")
        n = len(lo["questions"])
        rows.append([InlineKeyboardButton(f"🎯 {title} ({n})", callback_data=f"lo|{subject}|{loid}")])
    rows.append([InlineKeyboardButton("→ رجوع للرئيسية", callback_data="home")])
    return InlineKeyboardMarkup(rows)

def kb_question(q, answered=False, chosen=None):
    rows = []
    for i, opt in enumerate(q["options"]):
        prefix = LABELS[i]
        if answered:
            if i == q["answer"]:
                prefix = "✅"
            elif i == chosen:
                prefix = "❌"
        rows.append([InlineKeyboardButton(f"{prefix}  {opt}", callback_data=f"ans|{i}")])
    return InlineKeyboardMarkup(rows)

# ------------------------------------------------------------------
# أوامر البوت
# ------------------------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_student(update.effective_user)
    name = update.effective_user.first_name or "بطل"
    txt = (f"🚀 أهلًا بك يا {name} في *مساعد نافس الذكي*\n\n"
           "تدريب تراكمي على مهارات نافس — رياضيات، علوم، لغتي.\n"
           "كل سؤال مربوط بناتج تعلّم، مع تصحيح فوري وتعلّم من الخطأ.\n\n"
           "اختر مادة لتبدأ 👇")
    await update.message.reply_text(txt, reply_markup=kb_home(), parse_mode="Markdown")

async def on_home(update, context):
    q = update.callback_query; await q.answer()
    await q.edit_message_text("اختر مادة 👇", reply_markup=kb_home())

async def on_subject(update, context):
    q = update.callback_query; await q.answer()
    subject = q.data.split("|")[1]
    await q.edit_message_text(f"📘 *{subject}* — اختر ناتج التعلم الذي تريد التدرّب عليه:",
                              reply_markup=kb_outcomes(subject), parse_mode="Markdown")

async def on_outcome(update, context):
    q = update.callback_query; await q.answer()
    _, subject, loid = q.data.split("|")
    pool = list(questions_of(subject, loid))
    random.shuffle(pool)
    pool = pool[:QUESTIONS_PER_SESSION]
    context.user_data["session"] = {
        "subject": subject, "outcome": loid, "queue": pool,
        "idx": 0, "score": 0, "correct": 0, "wrong_once": False}
    await send_question(update, context, edit=True)

async def send_question(update, context, edit=False):
    s = context.user_data["session"]
    if s["idx"] >= len(s["queue"]):
        return await finish_session(update, context)
    q = s["queue"][s["idx"]]
    s["wrong_once"] = False
    head = (f"🎯 *ناتج التعلم:* {q['outcome_title'][:60]}\n"
            f"📎 المصدر: {q.get('src','')[:50]}\n"
            f"— سؤال {s['idx']+1} من {len(s['queue'])} —\n\n"
            f"*{q['text']}*")
    markup = kb_question(q)
    cq = update.callback_query
    if edit and cq:
        await cq.edit_message_text(head, reply_markup=markup, parse_mode="Markdown")
    else:
        await context.bot.send_message(update.effective_chat.id, head,
                                       reply_markup=markup, parse_mode="Markdown")

async def on_answer(update, context):
    q = update.callback_query; await q.answer()
    s = context.user_data.get("session")
    if not s:
        return await q.edit_message_text("انتهت الجلسة. اكتب /start للبدء من جديد.")
    chosen = int(q.data.split("|")[1])
    question = s["queue"][s["idx"]]
    correct = (chosen == question["answer"])
    user_id = update.effective_user.id

    if correct:
        first_try = not s["wrong_once"]
        pts = POINTS_FIRST_TRY if first_try else POINTS_AFTER_RETRY
        s["score"] += pts; s["correct"] += 1
        add_points(user_id, pts)
        record_answer(user_id, s["subject"], s["outcome"], question["grade"],
                      question["id"], chosen, True, first_try)
        praise = random.choice(["ممتاز! 🎯", "أحسنت! ⚡", "رائع! 🌟", "بطل! 🏆"])
        expl = question.get("explain", "")
        body = (f"*{praise}  +{pts} نقطة*\n\n{expl}")
        await q.edit_message_text(
            f"{question['text']}\n\n{body}", parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(
                "التالي ←" if s['idx'] < len(s['queue'])-1 else "إنهاء 🏁",
                callback_data="next")]]))
    else:
        s["wrong_once"] = True
        record_answer(user_id, s["subject"], s["outcome"], question["grade"],
                      question["id"], chosen, False, False)
        # تعلّم من الخطأ: شرح لماذا هذا الخيار خطأ إن توفّر
        why = ""
        if "why" in question and str(chosen) in question["why"]:
            why = question["why"][str(chosen)]
        elif "why" in question and chosen in question["why"]:
            why = question["why"][chosen]
        msg = (f"*لنتعلّم من هذا 🤔*\n{why}\n\n"
               f"الإجابة الصحيحة: *{LABELS[question['answer']]}) "
               f"{question['options'][question['answer']]}*")
        await q.edit_message_text(
            f"{question['text']}\n\n{msg}", parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("حاول التالي ←", callback_data="next")]]))

async def on_next(update, context):
    q = update.callback_query; await q.answer()
    s = context.user_data.get("session")
    if not s:
        return await q.edit_message_text("اكتب /start للبدء.")
    s["idx"] += 1
    await send_question(update, context, edit=True)

async def finish_session(update, context):
    s = context.user_data["session"]
    total = len(s["queue"]); pct = round(s["correct"]/total*100) if total else 0
    bar = "🟩"*round(pct/10) + "⬜"*(10-round(pct/10))
    txt = (f"🏁 *انتهى التدريب!*\n\n"
           f"{bar}  {pct}%\n"
           f"أجبت {s['correct']} من {total} صحيحة · ⭐ {s['score']} نقطة\n\n"
           f"💡 نصيحة: راجع أساس المهارة من الصفوف السابقة — معظم الأخطاء تبدأ من هناك.")
    await update.callback_query.edit_message_text(
        txt, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("تدرّب مجددًا ↺", callback_data=f"lo|{s['subject']}|{s['outcome']}")],
            [InlineKeyboardButton("→ الرئيسية", callback_data="home")]]))
    context.user_data.pop("session", None)

async def on_me(update, context):
    q = update.callback_query; await q.answer()
    uid = update.effective_user.id
    with db() as c:
        r = c.execute("SELECT * FROM students WHERE user_id=?", (uid,)).fetchone()
        rows = c.execute("""SELECT subject, COUNT(*) t, SUM(correct) ok
                            FROM answers WHERE user_id=? GROUP BY subject""", (uid,)).fetchall()
    if not r:
        return await q.edit_message_text("ابدأ التدريب أولًا! /start")
    lines = [f"📊 *تقدّمك*", f"⭐ النقاط: {r['points']}",
             f"✍️ أجبت: {r['answered']} · صحيح: {r['correct']}\n"]
    for row in rows:
        pct = round((row['ok'] or 0)/row['t']*100) if row['t'] else 0
        lines.append(f"• {row['subject']}: {pct}% ({row['ok']}/{row['t']})")
    await q.edit_message_text("\n".join(lines), parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("→ الرئيسية", callback_data="home")]]))

# ------------------------------------------------------------------
# لوحة تحكم المعلّمة داخل تليجرام
# ------------------------------------------------------------------
async def dashboard(update, context):
    uid = update.effective_user.id
    if ADMIN_IDS and uid not in ADMIN_IDS:
        return await update.message.reply_text("هذا الأمر خاص بالمعلّمة فقط.")
    with db() as c:
        nstud = c.execute("SELECT COUNT(*) n FROM students").fetchone()["n"]
        nans  = c.execute("SELECT COUNT(*) n FROM answers").fetchone()["n"]
        avg = c.execute("SELECT AVG(correct)*100 a FROM answers").fetchone()["a"] or 0
        # أصعب الأسئلة (الأعلى خطأً)
        hard = c.execute("""SELECT subject,outcome,grade,q_id,
                            COUNT(*) t, SUM(correct) ok
                            FROM answers GROUP BY q_id HAVING t>=1
                            ORDER BY (1.0*ok/t) ASC LIMIT 5""").fetchall()
        # الفجوات حسب المادة والصف
        gaps = c.execute("""SELECT subject,grade, COUNT(*) t, SUM(correct) ok
                            FROM answers GROUP BY subject,grade
                            ORDER BY (1.0*ok/NULLIF(t,0)) ASC LIMIT 6""").fetchall()

    lines = [f"👩‍🏫 *لوحة تحكم المعلّمة*",
             f"👥 الطلاب: {nstud} · ✍️ الإجابات: {nans} · 📈 متوسط الإتقان: {round(avg)}%\n",
             "*أصعب الأسئلة (الأعلى خطأً):*"]
    if hard:
        for h in hard:
            errp = 100-round((h['ok'] or 0)/h['t']*100) if h['t'] else 0
            qtext = find_qtext(h['subject'], h['q_id'])
            lines.append(f"• [{errp}% خطأ] {qtext[:45]} — {h['grade']}")
    else:
        lines.append("لا توجد بيانات بعد.")
    lines.append("\n*خريطة الفجوات (مادة/صف):*")
    if gaps:
        for g in gaps:
            pct = round((g['ok'] or 0)/g['t']*100) if g['t'] else 0
            lines.append(f"• {g['subject']} — {g['grade']}: {pct}% إتقان")
    else:
        lines.append("لا توجد بيانات بعد.")
    lines.append("\n🌐 للوحة التفصيلية بالرسوم: افتحي ملف dashboard.html بعد توليد التقرير (انظري الدليل).")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

def find_qtext(subject, qid):
    for lo in outcomes_of(subject).values():
        for q in lo["questions"]:
            if q["id"] == qid:
                return q["text"]
    return f"سؤال #{qid}"

# ------------------------------------------------------------------
# التشغيل
# ------------------------------------------------------------------
def main():
    if "ضع_التوكن" in BOT_TOKEN:
        print("⚠️  ضع توكن البوت في متغيّر البيئة BOT_TOKEN أو في أعلى الملف.")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("dashboard", dashboard))
    app.add_handler(CallbackQueryHandler(on_home, pattern=r"^home$"))
    app.add_handler(CallbackQueryHandler(on_subject, pattern=r"^subj\|"))
    app.add_handler(CallbackQueryHandler(on_outcome, pattern=r"^lo\|"))
    app.add_handler(CallbackQueryHandler(on_answer, pattern=r"^ans\|"))
    app.add_handler(CallbackQueryHandler(on_next, pattern=r"^next$"))
    app.add_handler(CallbackQueryHandler(on_me, pattern=r"^me$"))
    log.info("بوت نافس يعمل الآن…")
    app.run_polling()

if __name__ == "__main__":
    main()
