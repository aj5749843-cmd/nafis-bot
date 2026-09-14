#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
مولّد لوحة تحكم المعلّمة (ويب)
يقرأ nafis_data.db وينتج ملف dashboard.html مستقلًّا (يفتح بأي متصفّح).
شغّليه متى شئت لتحديث اللوحة:  python make_dashboard.py
"""
import sqlite3, json, os, datetime

DB = os.path.join(os.path.dirname(__file__), "nafis_data.db")
BANK = json.load(open(os.path.join(os.path.dirname(__file__), "nafis_bank.json"), encoding="utf-8"))
OUT = os.path.join(os.path.dirname(__file__), "dashboard.html")

def qtext(subject, qid):
    for lo in BANK["subjects"].get(subject, {}).get("outcomes", {}).values():
        for q in lo["questions"]:
            if q["id"] == qid: return q["text"], q.get("outcome_title","")
    return f"سؤال #{qid}", ""

def fetch():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    kpis = {
        "students": c.execute("SELECT COUNT(*) n FROM students").fetchone()["n"],
        "answers":  c.execute("SELECT COUNT(*) n FROM answers").fetchone()["n"],
        "avg":      round(c.execute("SELECT AVG(correct)*100 a FROM answers").fetchone()["a"] or 0),
    }
    hard = []
    for r in c.execute("""SELECT subject,grade,q_id,COUNT(*) t,SUM(correct) ok
                          FROM answers GROUP BY q_id HAVING t>=1
                          ORDER BY 1.0*ok/t ASC LIMIT 8"""):
        txt, lo = qtext(r["subject"], r["q_id"])
        # الخطأ الشائع: أكثر خيار خاطئ اختير
        common = c.execute("""SELECT chosen,COUNT(*) c FROM answers
                              WHERE q_id=? AND correct=0 GROUP BY chosen
                              ORDER BY c DESC LIMIT 1""", (r["q_id"],)).fetchone()
        hard.append({"subject":r["subject"],"grade":r["grade"],"text":txt,"outcome":lo,
                     "err":100-round(r["ok"]/r["t"]*100), "t":r["t"]})
    gaps = []
    for r in c.execute("""SELECT subject,grade,COUNT(*) t,SUM(correct) ok
                          FROM answers GROUP BY subject,grade
                          ORDER BY 1.0*ok/NULLIF(t,0) ASC"""):
        gaps.append({"subject":r["subject"],"grade":r["grade"],
                     "pct":round((r["ok"] or 0)/r["t"]*100) if r["t"] else 0,"t":r["t"]})
    students = []
    for r in c.execute("""SELECT s.name,s.points,s.answered,s.correct
                          FROM students s ORDER BY s.points DESC"""):
        pct = round(r["correct"]/r["answered"]*100) if r["answered"] else 0
        students.append({"name":r["name"],"points":r["points"],
                         "answered":r["answered"],"pct":pct})
    subj = []
    for r in c.execute("""SELECT subject,COUNT(*) t,SUM(correct) ok
                          FROM answers GROUP BY subject"""):
        subj.append({"subject":r["subject"],"pct":round((r["ok"] or 0)/r["t"]*100) if r["t"] else 0,"t":r["t"]})
    c.close()
    return kpis, hard, gaps, students, subj

def html(kpis, hard, gaps, students, subj):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    def bars(items, key, label):
        out = ""
        for it in items:
            out += f"""<div class="row"><div class="rl">{it[label]}</div>
              <div class="track"><div class="fill" style="width:{it[key]}%"></div></div>
              <div class="rp">{it[key]}%</div></div>"""
        return out or '<div class="empty">لا توجد بيانات بعد — سيمتلئ عند تدرّب الطلاب.</div>'
    hard_html = ""
    for h in hard:
        hard_html += f"""<div class="qcard">
          <div class="qt">{h['text'][:70]}</div>
          <div class="qmeta">🎯 {h['outcome'][:40]} · {h['subject']} · {h['grade']}</div>
          <div class="rate"><div class="track"><div class="fill err" style="width:{h['err']}%"></div></div>
          <span class="ep">{h['err']}% خطأ</span></div></div>"""
    if not hard: hard_html = '<div class="empty">لا توجد بيانات بعد.</div>'
    stud_html = ""
    for i,s in enumerate(students[:20]):
        medal = ["🥇","🥈","🥉"][i] if i<3 else f"{i+1}."
        stud_html += f"""<tr><td>{medal}</td><td>{s['name']}</td>
          <td>{s['points']}</td><td>{s['answered']}</td><td>{s['pct']}%</td></tr>"""
    if not students: stud_html = '<tr><td colspan="5" class="empty">لا يوجد طلاب بعد.</td></tr>'

    return f"""<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>لوحة تحكم المعلّمة — مساعد نافس</title>
<link href="https://fonts.googleapis.com/css2?family=Rubik:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
<style>
:root{{--void:#080b1a;--panel:#141a3d;--panel2:#1b2350;--line:#2a3372;--ink:#f0f3ff;
--soft:#a3aede;--dim:#6b76ad;--v:#8b7bff;--b:#5b8cff;--t:#3fe0d0;--red:#ff6b8a;--gold:#ffce5c;--green:#3ee6a0}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:Rubik,system-ui,sans-serif;color:var(--ink);min-height:100vh;
background:radial-gradient(1100px 640px at 88% -8%,rgba(139,123,255,.22),transparent 58%),
radial-gradient(900px 560px at 5% 108%,rgba(63,224,208,.14),transparent 55%),var(--void)}}
.wrap{{max-width:1000px;margin:0 auto;padding:28px 20px 60px}}
.top{{display:flex;align-items:center;justify-content:space-between;margin-bottom:24px;flex-wrap:wrap;gap:12px}}
.brand{{display:flex;align-items:center;gap:12px}}
.orb{{width:48px;height:48px;border-radius:14px;background:linear-gradient(140deg,var(--v),var(--b));
display:grid;place-items:center;font-weight:900;color:#fff;box-shadow:0 6px 18px rgba(139,123,255,.5)}}
h1{{font-size:20px;font-weight:800}} .sub{{font-size:12px;color:var(--soft)}}
.stamp{{font-size:12px;color:var(--dim)}}
.kpis{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-bottom:22px}}
.kpi{{background:var(--panel);border:1px solid var(--line);border-radius:18px;padding:18px}}
.kpi .n{{font-size:32px;font-weight:900}} .kpi .l{{font-size:13px;color:var(--soft);font-weight:600}}
.kpi.alert .n{{color:var(--red)}} .kpi.good .n{{color:var(--green)}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}
@media(max-width:760px){{.grid{{grid-template-columns:1fr}}.kpis{{grid-template-columns:1fr}}}}
.panel{{background:var(--panel);border:1px solid var(--line);border-radius:20px;padding:20px;margin-bottom:16px}}
.panel h2{{font-size:16px;font-weight:800;margin-bottom:4px}}
.panel .desc{{font-size:12px;color:var(--soft);margin-bottom:16px}}
.row{{display:flex;align-items:center;gap:12px;margin-bottom:11px}}
.rl{{flex:0 0 160px;font-size:13px;font-weight:600}} .rp{{font-size:13px;font-weight:700;color:var(--t);min-width:42px;text-align:left}}
.track{{flex:1;height:10px;border-radius:20px;background:rgba(0,0,0,.35);overflow:hidden}}
.fill{{height:100%;border-radius:20px;background:linear-gradient(90deg,var(--v),var(--t))}}
.fill.err{{background:linear-gradient(90deg,#ff9db0,var(--red))}}
.qcard{{padding:13px 0;border-bottom:1px solid var(--line)}} .qcard:last-child{{border:0}}
.qt{{font-size:14px;font-weight:600}} .qmeta{{font-size:11px;color:var(--b);font-weight:600;margin:3px 0 8px}}
.rate{{display:flex;align-items:center;gap:10px}} .ep{{font-size:12px;font-weight:700;color:var(--red);min-width:60px}}
table{{width:100%;border-collapse:collapse}}
th,td{{padding:10px 8px;font-size:13px;text-align:right;border-bottom:1px solid var(--line)}}
th{{color:var(--soft);font-weight:700;font-size:12px}}
tr:last-child td{{border:0}}
.empty{{color:var(--dim);font-size:13px;padding:14px;text-align:center}}
.foot{{text-align:center;font-size:11px;color:var(--dim);margin-top:24px}}
.gapnote{{background:rgba(139,123,255,.1);border:1px solid rgba(139,123,255,.3);
border-radius:12px;padding:12px 14px;font-size:12.5px;color:#d4dbff;margin-top:12px}}
.gapnote b{{color:var(--v)}}
</style></head><body><div class="wrap">
<div class="top"><div class="brand"><div class="orb">نافس</div>
<div><h1>لوحة تحكم المعلّمة</h1><div class="sub">مساعد نافس الذكي · متابعة الأداء حسب المهارات</div></div></div>
<div class="stamp">آخر تحديث: {now}</div></div>

<div class="kpis">
<div class="kpi"><div class="n">{kpis['students']}</div><div class="l">طالب نشط</div></div>
<div class="kpi {'good' if kpis['avg']>=70 else 'alert' if kpis['avg']<50 else ''}"><div class="n">{kpis['avg']}%</div><div class="l">متوسط الإتقان</div></div>
<div class="kpi"><div class="n">{kpis['answers']}</div><div class="l">إجابة مسجّلة</div></div>
</div>

<div class="panel"><h2>أصعب الأسئلة على الصف</h2>
<div class="desc">مرتّبة حسب نسبة الخطأ — ابدئي حصتك القادمة من هنا. كل سؤال مربوط بناتج التعلم ومصدره التراكمي.</div>
{hard_html}</div>

<div class="grid">
<div class="panel"><h2>الأداء حسب المادة</h2><div class="desc">نسبة الإتقان لكل مادة.</div>{bars(subj,'pct','subject')}</div>
<div class="panel"><h2>خريطة الفجوات التراكمية</h2><div class="desc">الأداء حسب المادة والصف — الأضعف أولًا.</div>
{bars(gaps,'pct','grade') if gaps else '<div class="empty">لا توجد بيانات بعد.</div>'}
<div class="gapnote"><b>قراءة سريعة:</b> ركّزي على الصفوف ذات الإتقان الأدنى — غالبًا الضعف قادم من أساس صف سابق، ومعالجته ترفع أداء نافس أكثر من التدريب على الصف الحالي.</div></div>
</div>

<div class="panel"><h2>أداء الطلاب</h2><div class="desc">مرتّب حسب النقاط.</div>
<table><thead><tr><th>#</th><th>الطالب</th><th>النقاط</th><th>أجاب</th><th>الإتقان</th></tr></thead>
<tbody>{stud_html}</tbody></table></div>

<div class="foot">مساعد نافس الذكي · لوحة تُولّد من قاعدة بيانات البوت · حدّثيها بتشغيل make_dashboard.py</div>
</div></body></html>"""

if __name__ == "__main__":
    data = fetch()
    open(OUT, "w", encoding="utf-8").write(html(*data))
    print(f"✅ تم توليد اللوحة: {OUT}")
