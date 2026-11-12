"""Jharkhand Steno - institute website (Flask + SQLite).
Includes Shorthand & Typing Practice Examination Portal with Government Standards.

Run:  py app.py
Open: http://127.0.0.1:5000   Admin: /admin   Practice: /practice
"""
import io, os, random, sqlite3, string
from datetime import date
from flask import (Flask, g, redirect, render_template_string, request,
                   send_file, session, url_for, flash)
from markupsafe import Markup
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas

INST = "Jharkhand Steno"
PLACE = "2nd Floor, Boipai Niwas, P.C. Birua Path, Tungri, Chaibasa, Jharkhand 833201"
PHONES = ["6206852544", "9988239388"]
WA = "916206852544"
DB = os.path.join(os.path.dirname(__file__), "institute.db")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")  # CHANGE IT

GROUPS = {
    "cbse": "CBSE (Class 7-10)",
    "icse": "ICSE (Class 7-10)",
    "jac": "JAC Board (Class 7-10)",
    "cert": "Certificate Courses",
    "central": "Central Govt",
    "state": "State / Local",
    "court": "Court"
}
ICON = {
    "cbse": "📘",
    "icse": "🎓",
    "jac": "🏛️",
    "cert": "💻",
    "central": "🏛️",
    "state": "🚔",
    "court": "⚖️"
}

SCHOOL_COURSES = [
    # CBSE Board (Class 7 to 10)
    ("CBSE Class 7 - Maths, Science & English", "cbse", 1499),
    ("CBSE Class 8 - Maths, Science & English", "cbse", 1499),
    ("CBSE Class 9 - Maths & Science Foundation", "cbse", 1999),
    ("CBSE Class 10 - Board Exam Master Batch (Maths, Science, SST)", "cbse", 2499),
    ("CBSE Class 9 & 10 - Computer Applications & IT (402)", "cbse", 1299),

    # ICSE Board (Class 7 to 10)
    ("ICSE Class 7 - Maths, Science & English", "icse", 1799),
    ("ICSE Class 8 - Maths, Physics, Chemistry, Biology", "icse", 1799),
    ("ICSE Class 9 - Board Foundation (Maths & Sciences)", "icse", 2299),
    ("ICSE Class 10 - ICSE Board Exam Special Batch", "icse", 2799),
    ("ICSE Class 9 & 10 - Computer Applications (Java)", "icse", 1499),

    # JAC Board (Class 7 to 10)
    ("JAC Class 7 - गणित, विज्ञान एवं अंग्रेजी", "jac", 999),
    ("JAC Class 8 - बोर्ड परीक्षा विशेष बैच (गणित व विज्ञान)", "jac", 1199),
    ("JAC Class 9 - बोर्ड परीक्षा स्पेशल बैच", "jac", 1499),
    ("JAC Class 10 - मैट्रिक बोर्ड टॉपर बैच (सम्पूर्ण विषय)", "jac", 1999),
    ("JAC Class 9 & 10 - कम्प्यूटर एवं टाइपिंग कौशल", "jac", 999),
]

SEED = ([(n, "central", 4999) for n in ["SSC", "I.B.", "ISRO", "AIIMS", "Railway", "Ministry of Defence", "SSB", "CISF", "CRPF", "Income Tax", "Parliament"]]
        + [(n, "state", 4999) for n in ["UPSSSC", "Municipal Corporation", "Police", "DSSSB", "Sales Tax"]]
        + [(n, "court", 4999) for n in ["High Court", "Reporter"]])
SEED = [(f"{n} Stenographer", g, p) for n, g, p in SEED] + [
    ("Hindi Typing", "cert", 1499), ("English Typing", "cert", 1499), ("Ho Typing", "cert", 1499),
    ("DCA", "cert", 3999), ("CCC", "cert", 1999), ("Tally ERP", "cert", 3499)] + SCHOOL_COURSES


# ---------- database ----------
def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close(_):
    d = g.pop("db", None)
    if d: d.close()

def init():
    c = sqlite3.connect(DB)
    c.executescript("""
    CREATE TABLE IF NOT EXISTS courses(id INTEGER PRIMARY KEY, name TEXT UNIQUE, grp TEXT, price INTEGER);
    CREATE TABLE IF NOT EXISTS enrollments(id TEXT PRIMARY KEY, name TEXT, phone TEXT, address TEXT,
        pay TEXT, total INTEGER, created TEXT, paid INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS items(eid TEXT, course TEXT, completed TEXT);

    CREATE TABLE IF NOT EXISTS practice_passages(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        category TEXT,
        lang TEXT,
        speed_wpm INTEGER,
        duration_mins INTEGER,
        content TEXT,
        notes TEXT,
        created TEXT
    );

    CREATE TABLE IF NOT EXISTS test_results(
        id TEXT PRIMARY KEY,
        student_name TEXT,
        student_phone TEXT,
        roll_no TEXT,
        passage_id INTEGER,
        passage_title TEXT,
        test_type TEXT,
        lang TEXT,
        wpm_gross REAL,
        wpm_net REAL,
        accuracy REAL,
        mistake_percentage REAL,
        mistakes REAL,
        master_word_count INTEGER,
        total_typed_words INTEGER,
        time_taken_seconds INTEGER,
        full_mistakes INTEGER,
        half_count INTEGER,
        omitted_count INTEGER,
        substituted_count INTEGER,
        inserted_count INTEGER,
        qualified INTEGER,
        scorecard_json TEXT,
        created TEXT
    );

    CREATE TABLE IF NOT EXISTS students(
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        phone TEXT UNIQUE NOT NULL,
        email TEXT,
        password_hash TEXT NOT NULL,
        enrolled_courses TEXT,
        created TEXT
    );

    CREATE TABLE IF NOT EXISTS student_exam_attempts(
        id TEXT PRIMARY KEY,
        student_id TEXT,
        student_name TEXT,
        course_code TEXT,
        course_name TEXT,
        score INTEGER,
        total_questions INTEGER,
        percentage REAL,
        grade TEXT,
        passed INTEGER,
        speed_wpm REAL,
        accuracy REAL,
        answers_json TEXT,
        created TEXT
    );

    CREATE TABLE IF NOT EXISTS student_levels(
        student_id TEXT NOT NULL,
        course_code TEXT NOT NULL,
        unlocked_level INTEGER DEFAULT 1,
        completed_levels TEXT DEFAULT '[]',
        level_scores TEXT DEFAULT '{}',
        cert_attempt_id TEXT,
        updated TEXT,
        PRIMARY KEY(student_id, course_code)
    );

    CREATE TABLE IF NOT EXISTS student_admissions(
        id TEXT PRIMARY KEY,
        student_id TEXT NOT NULL,
        student_name TEXT NOT NULL,
        course_code TEXT NOT NULL,
        course_name TEXT NOT NULL,
        class_mode TEXT NOT NULL,
        batch_timing TEXT,
        center_location TEXT,
        course_completed INTEGER DEFAULT 0,
        exam_applied INTEGER DEFAULT 0,
        exam_applied_date TEXT,
        created TEXT,
        status TEXT DEFAULT 'Confirmed'
    );
    """)
    # Seed courses if not present
    for item in SEED:
        c.execute("INSERT OR IGNORE INTO courses(name,grp,price) VALUES(?,?,?)", item)

    # Seed initial exam and practice passages
    if not c.execute("SELECT 1 FROM practice_passages").fetchone():
        import seed_passages
        for p in seed_passages.SAMPLE_PASSAGES:
            c.execute("""
                INSERT INTO practice_passages(title, category, lang, speed_wpm, duration_mins, content, notes, created)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (p["title"], p["category"], p["lang"], p["speed_wpm"], p["duration_mins"], p["content"], p.get("notes", ""), date.today().isoformat()))

    c.commit(); c.close()


# ---------- layout ----------
BASE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{ inst }} – Premier Institute of Shorthand, Typing & Academic Coaching, Chaibasa</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Hind:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Yatra+One&display=swap" rel="stylesheet">
<style>
:root{
  --bg: #f8fafc;
  --card: #ffffff;
  --ink: #0f172a;
  --mute: #64748b;
  --brand: #1e40af;
  --brand-hover: #1d4ed8;
  --deep: #0b1329;
  --header-bg: #09132b;
  --acc: #d97706;
  --acc-gold: #f59e0b;
  --acc-light: #fef3c7;
  --line: #e2e8f0;
  --ok: #15803d;
  --ok-light: #dcfce7;
  --bad: #b91c1c;
  --bad-light: #fee2e2;
  --shadow-sm: 0 1px 3px rgba(0,0,0,0.05);
  --shadow-md: 0 4px 6px -1px rgba(0,0,0,0.07), 0 2px 4px -2px rgba(0,0,0,0.04);
  --shadow-lg: 0 10px 15px -3px rgba(0,0,0,0.08), 0 4px 6px -4px rgba(0,0,0,0.03);
}
@media(prefers-color-scheme:dark){
  :root{
    --bg: #0b1120;
    --card: #131c31;
    --ink: #f8fafc;
    --mute: #94a3b8;
    --brand: #3b82f6;
    --brand-hover: #60a5fa;
    --deep: #060a14;
    --header-bg: #060a14;
    --line: #1e293b;
    --ok: #10b981;
    --bad: #ef4444;
  }
}
*{box-sizing:border-box}
html{scroll-behavior:smooth;overflow-x:hidden;scrollbar-width:none;-ms-overflow-style:none}
html::-webkit-scrollbar{display:none;width:0;height:0}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.6 'Plus Jakarta Sans','Hind',system-ui,sans-serif;overflow-x:hidden;scrollbar-width:none;-ms-overflow-style:none}
body::-webkit-scrollbar{display:none;width:0;height:0}
nav, .tablewrap, .top-bar, .ticker, *{scrollbar-width:none;-ms-overflow-style:none}
nav::-webkit-scrollbar, .tablewrap::-webkit-scrollbar, .top-bar::-webkit-scrollbar, .ticker::-webkit-scrollbar, *::-webkit-scrollbar{display:none;width:0;height:0}
.w{max-width:1100px;margin:0 auto;padding:0 20px}

/* Top Institutional Helpdesk Bar */
.top-bar{background:#060d1e;color:#cbd5e1;font-size:12.5px;border-bottom:1px solid rgba(255,255,255,.08);padding:6px 0;line-height:1.4}
.top-bar .w{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px}
.top-bar a{color:#fde047;text-decoration:none;font-weight:600}
.top-bar a:hover{text-decoration:underline}
.top-sep{opacity:.35;margin:0 4px}
@media(max-width:640px){.top-bar{font-size:11.5px;text-align:center}.top-bar .w{justify-content:center}}

/* Header & Nav */
header{position:sticky;top:0;background:var(--header-bg);border-bottom:3px solid var(--acc-gold);z-index:90;box-shadow:0 4px 20px rgba(0,0,0,.25)}
header .w{display:flex;justify-content:space-between;align-items:center;min-height:64px;gap:12px}
.logo{display:flex;flex-direction:column;text-decoration:none;color:#fff}
.logo-title{font:22px 'Yatra One',serif;color:#fde047;letter-spacing:.3px;display:flex;align-items:center;gap:6px}
.logo-sub{font-size:10.5px;color:#94a3b8;letter-spacing:.8px;text-transform:uppercase;font-weight:600}

nav{display:flex;gap:10px;align-items:center;overflow-x:auto;padding:4px 0}
nav a{color:#e2e8f0;text-decoration:none;font-weight:600;font-size:14.5px;white-space:nowrap;padding:6px 12px;border-radius:20px;transition:all .15s ease}
nav a:hover{background:rgba(255,255,255,.1);color:#fff}
.nav-portal{background:linear-gradient(135deg,#2563eb,#1d4ed8);color:#fff!important;box-shadow:0 2px 8px rgba(37,99,235,.4)}
.nav-portal:hover{background:#1e40af!important}
.nav-school{background:rgba(245,158,11,.15);color:#fde047!important;border:1px solid rgba(245,158,11,.4)}
.nav-school:hover{background:rgba(245,158,11,.25)!important}
.cart{background:var(--acc-gold);color:#0f172a!important;border-radius:20px;padding:5px 14px;font-weight:700;display:inline-flex;align-items:center;gap:6px;box-shadow:0 2px 8px rgba(245,158,11,.3)}

/* Buttons */
.btn,button{font:inherit;cursor:pointer;transition:all .15s ease}
.btn{display:inline-block;background:var(--brand);color:#fff;border:0;border-radius:30px;padding:11px 24px;font-weight:700;text-decoration:none;margin:0 10px 10px 0;box-shadow:var(--shadow-sm)}
.btn:hover{background:var(--brand-hover);transform:translateY(-1px);box-shadow:var(--shadow-md)}
.btn.y{background:var(--acc-gold);color:#0f172a}.btn.y:hover{background:#d97706;color:#fff}
.btn.g{background:rgba(255,255,255,.12);border:2px solid rgba(255,255,255,.6);color:#fff}.btn.g:hover{background:rgba(255,255,255,.25);border-color:#fff}
.btn.o{background:none;color:var(--brand);border:2px solid var(--brand)}.btn.o:hover{background:var(--brand);color:#fff}

/* Hero Section */
.hb{background:linear-gradient(135deg,#071026 0%,#0f1f4d 40%,#1e3a8a 100%);color:#fff;border-radius:0 0 32px 32px;padding:48px 0 54px;box-shadow:0 10px 25px rgba(15,23,42,.12);position:relative;overflow:hidden}
.hb::after{content:"";position:absolute;top:0;right:0;width:45%;height:100%;background:radial-gradient(circle at 70% 30%,rgba(59,130,246,.15),transparent 70%);pointer-events:none}
.hb h1{font:clamp(28px,5.5vw,46px)/1.25 'Yatra One',serif;margin:0 0 14px;max-width:20ch;color:#fff}
.hb p{color:#cbd5e1;max-width:58ch;font-size:16.5px;margin-bottom:22px;line-height:1.65}
.badge{display:inline-block;border:1.5px solid #fde047;background:rgba(253,224,71,.1);color:#fde047;border-radius:20px;padding:4px 14px;font-weight:700;font-size:13px;margin-bottom:14px;letter-spacing:.3px}

/* Sections & Typography */
section{padding:38px 0}.alt{background:#f1f5f9}@media(prefers-color-scheme:dark){.alt{background:#0e172a}}
h2{font:28px 'Yatra One',serif;font-weight:400;margin:0 0 10px;color:var(--ink)}
h2::after{content:"";display:block;width:54px;height:4px;border-radius:2px;background:var(--acc-gold);margin-top:6px}
.sub{color:var(--mute)}

/* Form Elements */
input,select,textarea{font:inherit;padding:11px 14px;border:2px solid var(--line);border-radius:10px;background:var(--card);color:var(--ink);width:100%;transition:border-color .15s ease}
input:focus,select:focus,textarea:focus{outline:none;border-color:var(--brand);box-shadow:0 0 0 3px rgba(37,99,235,.15)}
.row{display:flex;gap:10px;flex-wrap:wrap;margin:14px 0}.row input{flex:1;min-width:220px;width:auto}
.chip{border:1.5px solid var(--line);background:var(--card);color:var(--ink);border-radius:20px;padding:7px 16px;font-weight:600;font-size:14px;text-decoration:none;transition:all .15s}
.chip:hover{border-color:var(--brand);color:var(--brand)}
.chip.on{background:var(--brand);border-color:var(--brand);color:#fff}

/* Course Grid & Cards */
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:18px}
.course{background:var(--card);border-radius:18px;box-shadow:var(--shadow-md);border:1px solid var(--line);padding:20px;display:flex;flex-direction:column;gap:8px;border-top:5px solid var(--acc-gold);transition:transform .15s ease,box-shadow .15s ease}
.course:hover{transform:translateY(-2px);box-shadow:var(--shadow-lg)}
.course.in{border-top-color:var(--ok)}
.course .ic{font-size:30px}
.course b{font-size:17px;line-height:1.35}
.course small{color:var(--mute);font-weight:600;font-size:13px}
.price{font:24px 'Yatra One',serif;color:var(--brand);margin-top:auto;padding-top:8px}

/* Dynamic Cart Buttons on Course Card */
.cart-btn-wrap{width:100%;margin-top:8px}
.btn-cart-toggle.btn-add{width:100%;border:2px solid var(--brand);background:#fff;color:var(--brand);border-radius:24px;padding:9px;font-weight:700;transition:all .15s}
.btn-cart-toggle.btn-add:hover{background:var(--brand);color:#fff}
.cart-added-group{display:grid;grid-template-columns:1fr auto;gap:6px;align-items:center}
.btn-added-pill{background:var(--ok-light);color:var(--ok);border:1.5px solid var(--ok);border-radius:24px;padding:7px 12px;font-weight:700;font-size:13px;text-align:center}
.btn-cart-toggle.btn-cancel{background:var(--bad-light);color:var(--bad);border:1.5px solid var(--bad);border-radius:24px;padding:7px 14px;font-weight:700;font-size:13px}
.btn-cart-toggle.btn-cancel:hover{background:var(--bad);color:#fff}

/* Boxes & Two Column */
.box{background:var(--card);border-radius:18px;box-shadow:var(--shadow-md);border:1px solid var(--line);border-top:5px solid var(--acc-gold);padding:22px;display:grid;gap:14px}
.two{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px}label{font-weight:700;display:grid;gap:5px;font-size:14.5px}
.line{display:flex;justify-content:space-between;align-items:center;gap:10px;padding:8px 0;border-bottom:1px dashed var(--line)}
.flash{padding:12px 16px;border-radius:10px;font-weight:600;margin:14px 0;background:var(--card);border:2px solid var(--line);box-shadow:var(--shadow-sm)}
.flash.bad{color:var(--bad);border-color:var(--bad);background:var(--bad-light)}
.flash.ok{color:var(--ok);border-color:var(--ok);background:var(--ok-light)}
.id{font:26px 'Yatra One',serif;color:var(--brand)}
table{width:100%;border-collapse:collapse;font-size:14.5px}td,th{padding:10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{background:rgba(0,0,0,.02);font-weight:700}
.tablewrap{overflow-x:auto}

/* Floating Bottom Cart Bar */
.floating-cart{position:fixed;bottom:-100px;left:0;right:0;background:#09132b;color:#fff;border-top:3px solid var(--acc-gold);padding:14px 0;z-index:95;box-shadow:0 -6px 20px rgba(0,0,0,.25);transition:bottom .25s ease-in-out}
.floating-cart.on{bottom:0}

/* Toast Message */
.toast{position:fixed;top:76px;right:20px;background:#0f172a;color:#fff;padding:12px 20px;border-radius:12px;box-shadow:0 8px 24px rgba(0,0,0,.25);z-index:999;font-weight:600;font-size:14px;display:flex;align-items:center;gap:8px;transform:translateY(-20px);opacity:0;pointer-events:none;transition:all .2s ease}
.toast.show{transform:translateY(0);opacity:1}
.toast.ok{border-left:5px solid var(--ok)}
.toast.removed{border-left:5px solid var(--bad)}

/* Cart line item with Cancel */
.cart-line-item{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:10px 0;border-bottom:1px dashed var(--line);transition:all .2s ease}
.cart-line-item.removing{opacity:0;transform:translateX(20px)}
.btn-cancel-item{background:var(--bad-light);color:var(--bad);border:1px solid var(--bad);border-radius:16px;padding:4px 12px;font-size:12.5px;font-weight:700}
.btn-cancel-item:hover{background:var(--bad);color:#fff}

footer{background:linear-gradient(135deg,#060d1e,#0f1f4d);color:#fff;padding:34px 0 24px;border-radius:32px 32px 0 0;margin-top:40px}footer a{color:#cbd5e1;text-decoration:none}footer a:hover{color:#fff;text-decoration:underline}
.fab{position:fixed;right:18px;bottom:18px;background:#25a244;color:#fff;border-radius:30px;padding:12px 18px;font-weight:700;text-decoration:none;z-index:90;box-shadow:0 4px 14px rgba(37,162,68,.4);display:flex;align-items:center;gap:6px}
.fab:hover{background:#1e8436;transform:scale(1.03)}
</style></head><body>

<!-- Top Institutional Bar -->
<div class="top-bar">
  <div class="w">
    <div>
      <span>📍 Boipai Niwas, Tungri, Chaibasa, Jharkhand 833201</span>
      <span class="top-sep">|</span>
      <span>🏅 ISO 9001:2015 Certified Centre</span>
      <span class="top-sep">|</span>
      <span>Regd. Vocational Institute</span>
    </div>
    <div>
      <span>📞 Helpdesk: <a href="tel:+916206852544"><b>+91 6206852544</b></a> / <a href="tel:+919988239388"><b>9988239388</b></a></span>
      <span class="top-sep">|</span>
      <a href="{{ url_for('exam.student_dashboard') if session.get('student_id') else url_for('exam.student_login') }}">🎓 Student ID Exam Portal</a>
    </div>
  </div>
</div>

<header><div class="w">
  <a class="logo" href="{{ url_for('home') }}">
    <div class="logo-title"><span>🏛️</span> {{ inst }}</div>
    <div class="logo-sub">Skill Training & Academic Excellence Centre</div>
  </a>
  <nav>
    <a href="{{ url_for('exam.student_dashboard') if session.get('student_id') else url_for('exam.student_login') }}" class="nav-portal">🎓 Student Exam Portal</a>
    <a href="{{ url_for('practice.portal_home') }}" class="nav-portal" style="background:linear-gradient(135deg,#d97706,#b45309)">⚡ Practice Portal</a>
    <a href="{{ url_for('home') }}#school" class="nav-school">Class 7-10 Tuition</a>
    <a href="{{ url_for('home') }}#courses">Courses</a>
    <a href="{{ url_for('enroll') }}">Enroll</a>
    <a href="{{ url_for('certificate') }}">Certificate</a>
    <a href="{{ url_for('home') }}#contact">Contact</a>
    <a class="cart" href="{{ url_for('enroll') }}">🛒 Cart (<span class="cart-badge-count">{{ cart|length }}</span>)</a>
  </nav>
</div></header>

<div class="w">{% for c,m in get_flashed_messages(with_categories=true) %}<div class="flash {{ c }}">{{ m }}</div>{% endfor %}</div>
{{ body }}

<!-- Floating Bottom Cart Bar -->
<div id="floatingCartBar" class="floating-cart {{ 'on' if cart else '' }}">
  <div class="w" style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px">
    <div style="display:flex;align-items:center;gap:12px">
      <span style="font-size:24px">🛒</span>
      <div>
        <div style="font-weight:700"><span id="floatCartCount">{{ cart|length }}</span> Course(s) in Cart</div>
        <small style="color:#cbd5e1">Total Amount: <b id="floatCartTotal" style="color:#fde047">{{ total|rs }}</b></small>
      </div>
    </div>
    <div style="display:flex;gap:10px">
      <a class="btn y" style="margin:0;padding:8px 22px;border-radius:24px" href="{{ url_for('enroll') }}">Complete Enrollment ➔</a>
    </div>
  </div>
</div>

<!-- Floating Toast Message -->
<div id="toast" class="toast"></div>

<footer><div class="w">
  <div class="two" style="gap:24px;margin-bottom:20px">
    <div>
      <b style="font-size:20px;color:#fde047;font-family:'Yatra One',serif">{{ inst }}</b><br>
      <span style="font-size:14px;color:#cbd5e1">ISO 9001:2015 Certified Centre for Stenography, Computer Applications & Academic Board Tuition.</span><br>
      <small style="color:#94a3b8">{{ place }}</small>
    </div>
    <div style="display:flex;gap:18px;align-items:center;flex-wrap:wrap">
      <a href="{{ url_for('practice.portal_home') }}">Practice Portal</a>
      <a href="{{ url_for('exam.student_login') }}">Student CBT Portal</a>
      <a href="{{ url_for('certificate') }}">Certificate Download</a>
      <a href="{{ url_for('admin') }}">Staff Login</a>
    </div>
  </div>
  <div style="text-align:center;font-size:13px;color:#94a3b8;border-top:1px solid rgba(255,255,255,.1);padding-top:14px">
    © 2026 {{ inst }}, Chaibasa. All rights reserved.
  </div>
</div></footer>

<a class="fab" href="https://wa.me/{{ wa }}" target="_blank" rel="noopener"><span>💬 WhatsApp</span></a>

<!-- AJAX Cart & No-Refresh Script -->
<script>
(function(){
  const toast = document.getElementById("toast");
  let toastTimer = null;

  function showToast(msg, type){
    if (toastTimer) clearTimeout(toastTimer);
    toast.textContent = msg;
    toast.className = "toast show " + (type || "ok");
    toastTimer = setTimeout(() => {
      toast.classList.remove("show");
    }, 2400);
  }

  // Intercept all cart toggle and cancel clicks
  document.addEventListener("click", function(e){
    const btn = e.target.closest(".btn-cart-toggle, .btn-cancel-item");
    if (!btn) return;
    e.preventDefault();

    const name = btn.getAttribute("data-name");
    const isCancel = btn.classList.contains("btn-cancel") || btn.classList.contains("btn-cancel-item");
    const action = isCancel ? "remove" : "toggle";

    btn.disabled = true;

    const fd = new FormData();
    fd.append("name", name);
    fd.append("action", action);
    fd.append("ajax", "1");

    fetch("{{ url_for('toggle') }}", {
      method: "POST",
      body: fd,
      headers: { "X-Requested-With": "XMLHttpRequest" }
    })
    .then(r => r.json())
    .then(data => {
      btn.disabled = false;
      updateUI(data, name, isCancel);
    })
    .catch(err => {
      btn.disabled = false;
      console.error(err);
    });
  });

  function updateUI(data, courseName, isCancel){
    // 1. Update Header & Floating Badges
    document.querySelectorAll(".cart-badge-count").forEach(el => el.textContent = data.cart_count);
    const floatBar = document.getElementById("floatingCartBar");
    const floatCount = document.getElementById("floatCartCount");
    const floatTotal = document.getElementById("floatCartTotal");

    if (floatCount) floatCount.textContent = data.cart_count;
    if (floatTotal) floatTotal.textContent = data.cart_total_formatted;
    if (floatBar){
      floatBar.classList.toggle("on", data.cart_count > 0);
    }

    // 2. Update Course Card Wrappers Matching this course
    document.querySelectorAll('.cart-btn-wrap[data-name="' + courseName + '"]').forEach(wrap => {
      const courseCard = wrap.closest(".course");
      if (data.in_cart){
        if (courseCard) courseCard.classList.add("in");
        wrap.innerHTML = `
          <div class="cart-added-group">
            <span class="btn-added-pill">✓ Added</span>
            <button type="button" class="btn-cart-toggle btn-cancel" data-name="${courseName}">✕ Cancel</button>
          </div>
        `;
      } else {
        if (courseCard) courseCard.classList.remove("in");
        wrap.innerHTML = `
          <button type="button" class="btn-cart-toggle btn-add" data-name="${courseName}">＋ Add to enrollment</button>
        `;
      }
    });

    // 3. Update Cart Rows on /enroll page
    if (!data.in_cart){
      const row = document.querySelector('.cart-line-item[data-name="' + courseName + '"]');
      if (row){
        row.classList.add("removing");
        setTimeout(() => {
          row.remove();
          // Check if list is empty
          const remaining = document.querySelectorAll(".cart-line-item");
          if (remaining.length === 0){
            const itemsList = document.getElementById("enrollItemsList");
            if (itemsList){
              itemsList.innerHTML = '<span class="sub">No course added yet. <a href="{{ url_for('home') }}#courses">Choose a course</a></span>';
            }
            const totalRow = document.getElementById("enrollTotalRow");
            if (totalRow) totalRow.remove();
          }
        }, 200);
      }
      const enrollTotal = document.getElementById("enrollTotalVal");
      if (enrollTotal) enrollTotal.textContent = data.cart_total_formatted;
    }

    // 4. Show Feedback Toast
    if (data.in_cart){
      showToast("✓ " + courseName + " added to cart", "ok");
    } else {
      showToast("✕ " + courseName + " removed from cart", "removed");
    }
  }
})();
</script>
</body></html>"""


def rs(n):
    if n is None: return "₹0"
    try: return "₹{:,}".format(int(n))
    except (ValueError, TypeError): return "₹0"
app.jinja_env.filters["rs"] = rs

def page(tpl, **kw):
    body = Markup(render_template_string(tpl, **kw))
    return render_template_string(BASE, body=body, inst=INST, place=PLACE, phones=PHONES, wa=WA,
                                  cart=session.get("cart", []), total=cart_total())


# ---------- public pages ----------
HOME = """
<div class="hb"><div class="w"><span class="badge">ISO 9001:2015 Certified · Skill Training & Academic Coaching</span>
<h1>शॉर्टहैंड, टाइपिंग एवं कक्षा 7वीं से 10वीं (ICSE, CBSE, JAC) कोचिंग</h1>
<p>Premier coaching centre in Chaibasa for ICSE, CBSE & JAC Board students (Classes 7 to 10th) alongside professional Stenography and Typing certification. Complete preparation with experienced faculty, NCERT/ICSE solutions, and weekly mock tests.</p>
<div style="margin-top:14px">
  <a class="btn y" href="{{ url_for('exam.student_register') }}">🎓 Register for Online Exam (DCA, CCC, Tally)</a>
  <a class="btn y" href="#school">Class 7 to 10th Batches 📚</a>
  <a class="btn g" href="{{ url_for('practice.portal_home') }}">⚡ Free Online Mock Tests</a>
  <a class="btn g" href="#courses">All Courses</a>
  <a class="btn g" href="{{ url_for('certificate') }}">Get certificate</a>
</div>
</div></div>

<!-- Online Certification Exams Highlight Banner -->
<section style="background:linear-gradient(135deg,#1e1b4b,#312e81 60%,#4338ca);color:#fff;padding:28px 0;border-bottom:3px solid var(--acc)">
  <div class="w">
    <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:16px">
      <div>
        <span class="badge" style="border-color:#fde047;color:#fde047;background:rgba(253,224,71,.15)">CBT Online Exam Portal</span>
        <h2 style="margin:6px 0;font:26px 'Yatra One',serif;color:#fff">💻 Certificate Courses: DCA, CCC, Tally ERP & Typing Exam</h2>
        <p style="margin:0;color:#e0e7ff;max-width:62ch;font-size:15px">Create your Student ID and Password online to take the official 30-minute Computer Based Test (CBT) or 10-minute Typing Exam. Score 50%+ to generate and download your ISO 9001:2015 verified Certificate of Completion instantly.</p>
      </div>
      <div style="display:flex;gap:10px;flex-wrap:wrap">
        <a class="btn y" href="{{ url_for('exam.student_register') }}" style="margin:0">Register for Exam ➔</a>
        <a class="btn g" href="{{ url_for('exam.student_login') }}" style="margin:0">Student Login</a>
      </div>
    </div>
  </div>
</section>

<!-- School Coaching Section (Class 7th to 10th) -->
<section id="school" style="background:var(--card);border-top:3px solid var(--acc);border-bottom:3px solid var(--line);padding:36px 0">
  <div class="w">
    <h2>कक्षा 7वीं से 10वीं कोचिंग (ICSE, CBSE & JAC Board)</h2>
    <p class="sub">Comprehensive academic foundation and board exam preparation in Chaibasa with dedicated subject specialists.</p>
    
    <div class="two" style="grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px;margin-top:20px">
      <!-- ICSE Board Card -->
      <div class="box" style="border-top-color:#1e40af;padding:20px">
        <div style="display:flex;justify-content:space-between;align-items:center">
          <span style="font-size:32px">🎓</span>
          <span class="badge" style="border-color:#1e40af;color:#1e40af">ICSE Board</span>
        </div>
        <h3 style="margin:8px 0;font:20px 'Yatra One',serif">ICSE (Class 7th to 10th)</h3>
        <p class="sub" style="font-size:14px;line-height:1.6">
          • Comprehensive coverage of <b>Mathematics, Physics, Chemistry, Biology & English</b>.<br>
          • Special batch for <b>Computer Applications (Java Programming)</b> for 9th & 10th.<br>
          • Selina / Frank / Candid book solutions and ICSE 10-year board paper practice.<br>
          • Strong English communication, grammar and essay writing practice.
        </p>
        <div style="margin-top:12px">
          <a class="btn o" style="width:100%;text-align:center;margin:0" href="?cat=icse#courses">View ICSE Batches (Class 7-10)</a>
        </div>
      </div>

      <!-- CBSE Board Card -->
      <div class="box" style="border-top-color:#0284c7;padding:20px">
        <div style="display:flex;justify-content:space-between;align-items:center">
          <span style="font-size:32px">📘</span>
          <span class="badge" style="border-color:#0284c7;color:#0284c7">CBSE Board</span>
        </div>
        <h3 style="margin:8px 0;font:20px 'Yatra One',serif">CBSE (Class 7th to 10th)</h3>
        <p class="sub" style="font-size:14px;line-height:1.6">
          • Complete NCERT & Exemplar concept building for <b>Maths & Science</b>.<br>
          • <b>Class 10th Board Exam Booster Batch</b> (Maths, Science, SST & IT).<br>
          • Chapter-wise Daily Practice Problems (DPP) & regular test series.<br>
          • Information Technology (IT 402) & coding basics.
        </p>
        <div style="margin-top:12px">
          <a class="btn o" style="width:100%;text-align:center;margin:0" href="?cat=cbse#courses">View CBSE Batches (Class 7-10)</a>
        </div>
      </div>

      <!-- JAC Board Card -->
      <div class="box" style="border-top-color:#15803d;padding:20px">
        <div style="display:flex;justify-content:space-between;align-items:center">
          <span style="font-size:32px">🏛️</span>
          <span class="badge" style="border-color:#15803d;color:#15803d">JAC Board (झारखंड बोर्ड)</span>
        </div>
        <h3 style="margin:8px 0;font:20px 'Yatra One',serif">JAC (कक्षा 7वीं से 10वीं)</h3>
        <p class="sub" style="font-size:14px;line-height:1.6">
          • <b>मैट्रिक बोर्ड टॉपर बैच (Class 10th)</b>: गणित, विज्ञान, सामाजिक विज्ञान एवं हिन्दी/संस्कृत।<br>
          • JAC बोर्ड द्वारा जारी नवीनतम मॉडल प्रश्न पत्रों (Model Papers) का संपूर्ण अभ्यास।<br>
          • हिन्दी एवं अंग्रेजी दोनों माध्यमों के विद्यार्थियों के लिए विशेष ध्यान।<br>
          • कमजोर विद्यार्थियों के लिए रविवार को विशेष डाउट एवं रिवीजन कक्षाएं।
        </p>
        <div style="margin-top:12px">
          <a class="btn o" style="width:100%;text-align:center;margin:0" href="?cat=jac#courses">View JAC Batches (Class 7-10)</a>
        </div>
      </div>
    </div>

    <!-- Highlights Banner -->
    <div class="box" style="margin-top:20px;padding:18px;background:var(--bg)">
      <div class="two" style="grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;text-align:center">
        <div><b>👥 सीमित बैच साइज</b><br><span class="sub" style="font-size:13px">प्रत्येक छात्र पर व्यक्तिगत ध्यान</span></div>
        <div><b>📝 साप्ताहिक टेस्ट</b><br><span class="sub" style="font-size:13px">अभिभावकों को नियमित प्रगति रिपोर्ट</span></div>
        <div><b>💻 कम्प्यूटर फाउंडेशन</b><br><span class="sub" style="font-size:13px">टाइपिंग और कम्प्यूटर बेसिक्स का अभ्यास</span></div>
        <div><b>🎯 100% बोर्ड ओरिएंटेड</b><br><span class="sub" style="font-size:13px">पिछले 10 वर्षों के प्रश्नों का हल</span></div>
      </div>
    </div>
  </div>
</section>

<!-- Featured Mock Portal Banner -->
<section style="background:linear-gradient(135deg,#e0f2fe,#eff6ff);border-bottom:2px solid #bfdbfe;padding:24px 0">
  <div class="w">
    <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:14px">
      <div>
        <span class="badge" style="border-color:#1e40af;color:#1e40af;background:#dbeafe">NEW: Stenography & Typing Practice Engine</span>
        <h3 style="margin:6px 0;font:24px 'Yatra One',serif;color:#1e3a8a">Govt Exam Simulator: SSC Grade C/D & High Court</h3>
        <p style="margin:0;color:#334155;max-width:55ch">Practice 80/100/120 WPM audio dictation with reading time, real-time typing speed metrics, and official SSC mistake evaluation scorecards.</p>
      </div>
      <div>
        <a class="btn" style="background:#1e40af;margin:0" href="{{ url_for('practice.portal_home') }}">Launch Practice Portal ➔</a>
      </div>
    </div>
  </div>
</section>

<section id="courses"><div class="w"><h2>Our courses</h2><p class="sub">Add courses, then enroll in one step.</p>
<form class="row" method="get" action="#courses"><input name="q" value="{{ q }}" placeholder="Search courses (CBSE, ICSE, JAC, SSC, Tally, typing…)"><button class="btn" style="margin:0">Search</button></form>
<div class="row"><a class="chip {{ 'on' if not cat }}" href="?#courses">All</a>{% for k,v in groups.items() %}<a class="chip {{ 'on' if cat==k }}" href="?cat={{ k }}#courses">{{ v }}</a>{% endfor %}</div>
<div class="grid">{% for c in courses %}
<div class="course {{ 'in' if c.name in cart }}" id="course-card-{{ loop.index }}">
  <span class="ic">{{ icon[c.grp] }}</span>
  <b>{{ c.name }}</b>
  <small>{{ groups[c.grp] }}</small>
  <div class="price">{{ c.price|rs }}</div>
  <div class="cart-btn-wrap" data-name="{{ c.name }}">
    {% if c.name in cart %}
    <div class="cart-added-group">
      <span class="btn-added-pill">✓ Added</span>
      <button type="button" class="btn-cart-toggle btn-cancel" data-name="{{ c.name }}">✕ Cancel</button>
    </div>
    {% else %}
    <button type="button" class="btn-cart-toggle btn-add" data-name="{{ c.name }}">＋ Add to enrollment</button>
    {% endif %}
  </div>
</div>
{% else %}<p class="sub">No course found.</p>{% endfor %}</div>
{% if cart %}<p style="margin-top:20px"><a class="btn y" href="{{ url_for('enroll') }}">Enroll in <span class="cart-badge-count">{{ cart|length }}</span> course(s) – {{ total|rs }}</a></p>{% endif %}</div></section>
<section class="alt"><div class="w"><h2>What you get</h2><div class="two">
{% for t in feats %}<div class="box" style="padding:14px"><b>✔ {{ t }}</b></div>{% endfor %}</div></div></section>
<section id="contact"><div class="w"><h2>Visit or call</h2><p>{{ place }}</p>{% for p in phones %}<a class="btn" href="tel:+91{{ p }}">📞 {{ p }}</a>{% endfor %}</div></section>"""

FEATS = ["Experienced steno trainers", "Daily audio dictation at 80/100/120 WPM", "Steno sentences / outlines & phraseography", "Special high-speed batches",
         "Online typing test engine & SSC evaluation", "Weekly skill test", "Hindi and English shorthand", "Online certificate download"]

def cart_total():
    cart = session.get("cart", [])
    if not cart: return 0
    q = ",".join("?" * len(cart))
    return db().execute(f"SELECT COALESCE(SUM(price),0) FROM courses WHERE name IN ({q})", cart).fetchone()[0]

@app.route("/")
def home():
    q, cat = request.args.get("q", "").strip(), request.args.get("cat", "")
    sql, args = "SELECT * FROM courses WHERE name LIKE ?", [f"%{q}%"]
    if cat in GROUPS: sql += " AND grp=?"; args.append(cat)
    rows = db().execute(sql + " ORDER BY id", args).fetchall()
    return page(HOME, courses=rows, q=q, cat=cat, groups=GROUPS, icon=ICON, feats=FEATS,
                cart=session.get("cart", []), total=cart_total())

@app.route("/standalone")
def standalone():
    html_path = os.path.join(os.path.dirname(__file__), "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return f.read(), 200, {"Content-Type": "text/html; charset=utf-8"}

@app.post("/cart/toggle")
def toggle():
    name = request.form.get("name")
    action = request.form.get("action", "") # "add", "remove", or default toggle
    cart = session.get("cart", [])
    
    if name and db().execute("SELECT 1 FROM courses WHERE name=?", (name,)).fetchone():
        if action == "remove":
            cart = [c for c in cart if c != name]
        elif action == "add":
            if name not in cart:
                cart.append(name)
        else:
            cart = [c for c in cart if c != name] if name in cart else cart + [name]
            
    session["cart"] = cart
    tot = cart_total()
    
    # Return JSON for AJAX requests (no page refresh)
    if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.form.get("ajax") == "1":
        return {
            "status": "ok",
            "name": name,
            "in_cart": name in cart,
            "cart": cart,
            "cart_count": len(cart),
            "cart_total": tot,
            "cart_total_formatted": rs(tot)
        }
        
    return redirect(request.referrer or url_for("home"))

ENROLL = """<section><div class="w"><h2>Enroll online</h2>
<div class="box"><div id="enrollItemsList">{% for n,p in items %}<div class="cart-line-item" data-name="{{ n }}"><span><b>{{ n }}</b></span><div style="display:flex;align-items:center;gap:12px"><button type="button" class="btn-cancel-item" data-name="{{ n }}">✕ Cancel</button><b>{{ p|rs }}</b></div></div>{% else %}
<span class="sub" id="emptyCartNotice">No course added yet. <a href="{{ url_for('home') }}#courses">Choose a course</a></span>{% endfor %}
{% if items %}<div class="line" id="enrollTotalRow" style="margin-top:10px;padding-top:10px;border-top:2px solid var(--line);font-size:18px"><b>Total Amount</b><b id="enrollTotalVal">{{ total|rs }}</b></div>{% endif %}</div>
{% if items %}<form method="post" class="two">
<label>Student / Candidate Name<input name="name" required value="{{ f.get('name','') }}"></label>
<label>Parent / Student Mobile<input name="phone" required inputmode="numeric" maxlength="10" pattern="[6-9][0-9]{9}" value="{{ f.get('phone','') }}"></label>
<label>School / Board & Class (if School Student)<input name="school_info" placeholder="e.g. Class 10th - ICSE / CBSE / JAC" value="{{ f.get('school_info','') }}"></label>
<label>Place / Address<input name="address" value="{{ f.get('address','') }}"></label>
<label>Payment Preference<select name="pay"><option>Pay at centre</option><option>UPI (details on WhatsApp)</option><option>Cash / Card at centre</option></select></label>
<div style="grid-column:1/-1"><button class="btn">Confirm enrollment</button></div></form>{% endif %}</div></div></section>"""

@app.route("/enroll", methods=["GET", "POST"])
def enroll():
    cart = session.get("cart", [])
    if request.method == "POST" and cart:
        f = request.form
        name, phone = f["name"].strip(), "".join(ch for ch in f["phone"] if ch.isdigit())
        if not name or len(phone) != 10 or phone[0] not in "6789":
            flash("Enter your name and a valid 10-digit mobile number.", "bad")
        else:
            eid = "JS-" + date.today().strftime("%y%m%d") + "-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
            addr = f.get("address", "").strip()
            if f.get("school_info"):
                addr += f" [School/Class: {f.get('school_info').strip()}]"
            d = db()
            d.execute("INSERT INTO enrollments VALUES(?,?,?,?,?,?,?,0)",
                      (eid, name, phone, addr, f["pay"], cart_total(), date.today().isoformat()))
            d.executemany("INSERT INTO items VALUES(?,?,NULL)", [(eid, c) for c in cart])
            d.commit(); session["cart"] = []
            return redirect(url_for("receipt", eid=eid))
    rows = [(c, db().execute("SELECT price FROM courses WHERE name=?", (c,)).fetchone()[0]) for c in cart]
    return page(ENROLL, items=rows, total=cart_total(), f=request.form)

RECEIPT = """<section><div class="w"><h2>Enrollment saved</h2><div class="box">
<div>Your Enrollment ID<div class="id">{{ e.id }}</div></div>
{% for i in items %}<div class="line"><span>{{ i.course }}</span></div>{% endfor %}
<div class="line"><b>Total</b><b>{{ e.total|rs }}</b></div><p class="sub">Keep this ID. Send the details on WhatsApp to confirm your seat. Your certificate is available here after you complete the course.</p>
<div><a class="btn" target="_blank" rel="noopener" href="https://wa.me/{{ wa }}?text={{ msg }}">Send on WhatsApp</a></div></div></div></section>"""

@app.route("/receipt/<eid>")
def receipt(eid):
    e = db().execute("SELECT * FROM enrollments WHERE id=?", (eid,)).fetchone()
    if not e: return redirect(url_for("home"))
    items = db().execute("SELECT course FROM items WHERE eid=?", (eid,)).fetchall()
    from urllib.parse import quote
    msg = quote(f"Hello {INST}, I want to enroll.\nEnrollment ID: {e['id']}\nName: {e['name']}\nPhone: {e['phone']}\n"
                f"Courses: {', '.join(i['course'] for i in items)}\nTotal: {rs(e['total'])}\nPayment: {e['pay']}")
    return page(RECEIPT, e=e, items=items, msg=msg, wa=WA)


# ---------- certificate ----------
CERT = """<section><div class="w"><h2>Certificate download</h2><p class="sub">Enter your Enrollment ID and the mobile number you enrolled with.</p>
<div class="box"><form method="post" class="two"><label>Enrollment ID<input name="eid" value="{{ eid }}" required></label>
<label>Mobile number<input name="phone" inputmode="numeric" maxlength="10" required></label>
<div style="grid-column:1/-1"><button class="btn">Find my certificates</button></div></form>
{% if done is not none %}{% for c in done %}<div class="line"><span>🎓 {{ c.course }} <small class="sub">({{ c.completed }})</small></span>
<a class="btn y" style="margin:0" href="{{ url_for('cert_pdf', eid=eid, course=c.course) }}">Download PDF</a></div>
{% else %}<p class="sub">No completed course yet. The institute marks a course complete after your final test.</p>{% endfor %}{% endif %}</div></div></section>"""

@app.route("/certificate", methods=["GET", "POST"])
def certificate():
    eid, done = request.form.get("eid", "").strip().upper(), None
    if request.method == "POST":
        e = db().execute("SELECT * FROM enrollments WHERE id=? AND phone=?", (eid, request.form["phone"].strip())).fetchone()
        if not e: flash("ID and mobile number do not match.", "bad")
        else:
            session["verified"] = eid
            done = db().execute("SELECT course, completed FROM items WHERE eid=? AND completed IS NOT NULL", (eid,)).fetchall()
    return page(CERT, eid=eid, done=done)

@app.route("/certificate/<eid>.pdf")
def cert_pdf(eid):
    course = request.args.get("course", "")
    if session.get("verified") != eid: return redirect(url_for("certificate"))
    r = db().execute("""SELECT e.name, i.completed FROM enrollments e JOIN items i ON i.eid=e.id
                        WHERE e.id=? AND i.course=? AND i.completed IS NOT NULL""", (eid, course)).fetchone()
    if not r: return redirect(url_for("certificate"))
    buf = io.BytesIO(); W, H = landscape(A4); c = canvas.Canvas(buf, pagesize=(W, H))
    navy, gold, blue = (.06, .15, .4), (.96, .76, .05), (.12, .31, .85)
    c.setStrokeColorRGB(*navy); c.setLineWidth(8); c.rect(18, 18, W - 36, H - 36)
    c.setStrokeColorRGB(*gold); c.setLineWidth(2.5); c.rect(32, 32, W - 64, H - 64)
    c.setFillColorRGB(*navy); c.rect(32, H - 125, W - 64, 93, fill=1, stroke=0)
    c.setFillColorRGB(*gold); c.setFont("Helvetica-Bold", 34); c.drawCentredString(W / 2, H - 82, INST.upper())
    c.setFillColorRGB(1, 1, 1); c.setFont("Helvetica", 11); c.drawCentredString(W / 2, H - 105, "ISO 9001:2015 Certified Skill Training Centre · Chaibasa, Jharkhand")
    c.setFillColorRGB(*blue); c.setFont("Helvetica-Bold", 38); c.drawCentredString(W / 2, H - 200, "Certificate of Completion")
    c.setFillColorRGB(.42, .36, .25); c.setFont("Helvetica", 14); c.drawCentredString(W / 2, H - 245, "This is to certify that")
    c.setFillColorRGB(.16, .13, .07); c.setFont("Helvetica-Bold", 34); c.drawCentredString(W / 2, H - 295, r["name"])
    c.setStrokeColorRGB(*gold); c.line(150, H - 308, W - 150, H - 308)
    c.setFillColorRGB(.42, .36, .25); c.setFont("Helvetica", 14); c.drawCentredString(W / 2, H - 340, "has successfully completed the course")
    c.setFillColorRGB(*navy); c.setFont("Helvetica-Bold", 26); c.drawCentredString(W / 2, H - 382, course)
    c.setFillColorRGB(.42, .36, .25); c.setFont("Helvetica", 11)
    c.drawString(70, 78, f"Enrollment ID: {eid}"); c.drawString(70, 60, f"Date of completion: {r['completed']}")
    c.line(W - 260, 78, W - 70, 78); c.drawCentredString(W - 165, 62, "Director")
    c.setFillColorRGB(*gold); c.circle(W / 2, 80, 32, fill=1, stroke=0)
    c.setFillColorRGB(*navy); c.setFont("Helvetica-Bold", 12); c.drawCentredString(W / 2, 78, "ISO"); c.setFont("Helvetica", 7); c.drawCentredString(W / 2, 67, "CERTIFIED")
    c.showPage(); c.save(); buf.seek(0)
    return send_file(buf, mimetype="application/pdf", as_attachment=True, download_name=f"certificate-{eid}.pdf")


# ---------- admin ----------
LOGIN = """<section><div class="w"><h2>Staff login</h2><div class="box"><form method="post" class="two">
<label>Password<input type="password" name="pw" required></label><div style="align-self:end"><button class="btn">Login</button></div></form></div></div></section>"""

ADMIN = """<section><div class="w">
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
  <h2 style="margin:0">Staff Administration</h2>
  <a class="btn o" href="{{ url_for('logout') }}" style="margin:0">Logout</a>
</div>

<h2>Enrollments</h2>
<div class="tablewrap"><table><tr><th>ID / Date</th><th>Student</th><th>Courses</th><th>Paid</th></tr>
{% for e in rows %}<tr><td><b>{{ e.id }}</b><br>{{ e.created }}</td><td>{{ e.name }}<br><a href="tel:{{ e.phone }}">{{ e.phone }}</a><br>{{ e.address }}</td>
<td>{% for i in items[e.id] %}<form method="post" action="{{ url_for('complete') }}" style="margin:0 0 4px"><input type="hidden" name="eid" value="{{ e.id }}"><input type="hidden" name="course" value="{{ i.course }}">
{{ i.course }} – {% if i.completed %}✅ {{ i.completed }}{% else %}<button class="btn o" style="padding:2px 12px;margin:0">Mark complete</button>{% endif %}</form>{% endfor %}<b>{{ e.total|rs }}</b></td>
<td><form method="post" action="{{ url_for('paid') }}"><input type="hidden" name="eid" value="{{ e.id }}"><button class="btn {{ '' if e.paid else 'o' }}" style="padding:2px 12px;margin:0">{{ 'Paid ✓' if e.paid else 'Mark paid' }}</button></form></td></tr>
{% else %}<tr><td colspan="4">No enrollments yet.</td></tr>{% endfor %}</table></div>

<h2 style="margin-top:30px">Registered Students (CBT & Certification Portal)</h2>
<div class="tablewrap"><table>
<tr><th>Student ID</th><th>Name</th><th>Mobile</th><th>Email</th><th>Registered Courses</th><th>Joined</th></tr>
{% for s in students %}
<tr>
  <td><b>{{ s.id }}</b></td>
  <td><b>{{ s.name }}</b></td>
  <td><a href="tel:{{ s.phone }}">{{ s.phone }}</a></td>
  <td>{{ s.email or '-' }}</td>
  <td><small>{{ s.enrolled_courses }}</small></td>
  <td><small class="sub">{{ s.created }}</small></td>
</tr>
{% else %}
<tr><td colspan="6">No registered students yet.</td></tr>
{% endfor %}
</table></div>

<h2 style="margin-top:30px">Compulsory Class Admissions (Online / Offline Batches) & Exam Applications</h2>
<div class="tablewrap"><table>
<tr><th>Admission ID</th><th>Student</th><th>Course</th><th>Class Mode & Center</th><th>Batch Timing</th><th>Course Status</th><th>Exam Conduct</th></tr>
{% for a in admissions %}
<tr>
  <td><b>{{ a.id }}</b><br><small class="sub">{{ a.created }}</small></td>
  <td><b>{{ a.student_name }}</b><br><small>ID: {{ a.student_id }}</small></td>
  <td><b>{{ a.course_name }}</b></td>
  <td>
    {% if a.class_mode == 'offline' %}
    <span style="background:#fef3c7;color:#92400e;padding:3px 8px;border-radius:6px;font-weight:700;font-size:12px">🏛️ Offline Class</span>
    <br><small style="color:var(--sub)">{{ a.center_location }}</small>
    {% else %}
    <span style="background:#e0e7ff;color:#3730a3;padding:3px 8px;border-radius:6px;font-weight:700;font-size:12px">🌐 Online Class</span>
    <br><small style="color:var(--sub)">Digital Video Portal</small>
    {% endif %}
  </td>
  <td><small>{{ a.batch_timing }}</small></td>
  <td>
    {% if a.course_completed %}
    <span style="color:var(--ok);font-weight:700">✓ Course Completed</span>
    {% else %}
    <span style="color:#f59e0b;font-weight:700">⏳ In Progress</span>
    {% endif %}
  </td>
  <td>
    {% if a.exam_applied %}
    <span style="color:var(--ok);font-weight:700">✓ Applied for Exam</span>
    <br><small class="sub">{{ a.exam_applied_date or 'Approved' }}</small>
    {% elif a.course_completed %}
    <span style="color:var(--brand);font-weight:600">Eligible to Apply</span>
    {% else %}
    <span class="sub" style="font-size:12px">Coursework Incomplete</span>
    {% endif %}
  </td>
</tr>
{% else %}
<tr><td colspan="7">No class admissions recorded yet.</td></tr>
{% endfor %}
</table></div>

<h2 style="margin-top:30px">Certificate Exam Attempts (DCA, CCC, Tally, Typing)</h2>
<div class="tablewrap"><table>
<tr><th>Attempt ID</th><th>Student</th><th>Course</th><th>Score / Speed</th><th>Grade</th><th>Status</th><th>Action</th></tr>
{% for ea in exam_attempts %}
<tr>
  <td><b>{{ ea.id }}</b><br><small class="sub">{{ ea.created }}</small></td>
  <td><b>{{ ea.student_name }}</b><br><small>ID: {{ ea.student_id }}</small></td>
  <td><b>{{ ea.course_name }}</b></td>
  <td>
    {% if ea.score is not none %}
    <b>{{ ea.score }} / {{ ea.total_questions }}</b> ({{ ea.percentage }}%)
    {% else %}
    <b>{{ ea.speed_wpm }} WPM</b> ({{ ea.accuracy }}%)
    {% endif %}
  </td>
  <td>{{ ea.grade }}</td>
  <td>
    {% if ea.passed %}
    <span style="color:var(--ok);font-weight:700">✓ PASSED</span>
    {% else %}
    <span style="color:var(--bad);font-weight:700">✗ FAILED</span>
    {% endif %}
  </td>
  <td>
    {% if ea.passed %}
    <a class="btn y" style="padding:3px 10px;margin:0;font-size:12px" href="{{ url_for('exam.download_certificate', aid=ea.id) }}" target="_blank">Certificate PDF</a>
    {% else %}
    <span class="sub" style="font-size:12px">-</span>
    {% endif %}
  </td>
</tr>
{% else %}
<tr><td colspan="7">No exam attempts recorded yet.</td></tr>
{% endfor %}
</table></div>

</div></section>

<!-- Practice & Exam Mock Submissions -->
<section class="alt"><div class="w">
<h2>Recent Student Mock Test Results</h2>
<p class="sub">Latest submissions from the Online Typing and Shorthand Examination portal.</p>
<div class="tablewrap"><table>
<tr><th>ID / Date</th><th>Candidate</th><th>Exam / Type</th><th>Net WPM</th><th>Accuracy</th><th>Result</th><th>Action</th></tr>
{% for tr in test_results %}
<tr>
  <td><b>{{ tr.id }}</b><br><small class="sub">{{ tr.created }}</small></td>
  <td><b>{{ tr.student_name }}</b><br><small>{{ tr.student_phone }}</small></td>
  <td>{{ tr.passage_title }}<br><span style="font-size:12px;color:var(--brand)">{{ 'Typing Test' if tr.test_type=='typing' else 'Steno Dictation' }} ({{ tr.lang }})</span></td>
  <td><b>{{ tr.wpm_net }} WPM</b><br><small class="sub">Gross: {{ tr.wpm_gross }}</small></td>
  <td><b>{{ tr.accuracy }}%</b><br><small class="sub">{{ tr.mistake_percentage }}% err</small></td>
  <td>
    {% if tr.qualified %}
    <span style="color:var(--ok);font-weight:700">✓ QUALIFIED</span>
    {% else %}
    <span style="color:var(--bad);font-weight:700">✗ FAILED</span>
    {% endif %}
  </td>
  <td>
    <a class="btn o" style="padding:4px 10px;margin:0 4px 4px 0;font-size:13px" href="{{ url_for('practice.scorecard', rid=tr.id) }}" target="_blank">View Scorecard</a>
    <form method="post" action="{{ url_for('admin_delete_result') }}" style="display:inline" onsubmit="return confirm('Delete result record?')">
      <input type="hidden" name="rid" value="{{ tr.id }}">
      <button class="btn o" style="padding:4px 10px;margin:0;font-size:13px;color:var(--bad);border-color:var(--bad)">Delete</button>
    </form>
  </td>
</tr>
{% else %}
<tr><td colspan="7">No test submissions recorded yet.</td></tr>
{% endfor %}
</table></div>

<h2 style="margin-top:34px">Manage Practice & Exam Passages</h2>
<div class="tablewrap"><table>
<tr><th>ID</th><th>Title</th><th>Category</th><th>Lang</th><th>Speed</th><th>Time</th><th>Action</th></tr>
{% for p in passages %}
<tr>
  <td><b>#{{ p.id }}</b></td>
  <td><b>{{ p.title }}</b><br><small class="sub">{{ p.content[:80] }}...</small></td>
  <td>{{ 'Typing' if p.category=='typing' else 'Steno Dictation' }}</td>
  <td>{{ p.lang }}</td>
  <td><b>{{ p.speed_wpm }} WPM</b></td>
  <td>{{ p.duration_mins }}m</td>
  <td>
    <form method="post" action="{{ url_for('admin_delete_passage') }}" onsubmit="return confirm('Delete passage #{{ p.id }}?')">
      <input type="hidden" name="pid" value="{{ p.id }}">
      <button class="btn o" style="padding:3px 10px;margin:0;color:var(--bad);border-color:var(--bad)">Delete</button>
    </form>
  </td>
</tr>
{% endfor %}
</table></div>

<h3>Add New Exam / Practice Passage</h3>
<form method="post" action="{{ url_for('admin_add_passage') }}" class="box" style="padding:20px">
  <div class="two">
    <label>Title
      <input name="title" required placeholder="e.g. SSC Steno Grade D - Parliament Speech">
    </label>
    <label>Category
      <select name="category">
        <option value="typing">Typing Test</option>
        <option value="steno_dictation">Steno Audio Dictation</option>
      </select>
    </label>
    <label>Language
      <select name="lang">
        <option value="english">English</option>
        <option value="hindi">हिन्दी (Hindi)</option>
      </select>
    </label>
    <label>Target Speed (WPM)
      <input name="speed_wpm" type="number" min="10" max="200" value="80" required>
    </label>
    <label>Duration (Minutes)
      <input name="duration_mins" type="number" min="1" max="30" value="5" required>
    </label>
    <label>Exam Notes / Instructions
      <input name="notes" placeholder="e.g. Standard 80 WPM SSC format">
    </label>
  </div>
  <label>Passage Text Content (The master text to dictate and evaluate against):
    <textarea name="content" rows="6" required placeholder="Paste full examination passage text here..."></textarea>
  </label>
  <div>
    <button class="btn">Add Passage to Portal</button>
  </div>
</form>

</div></section>

<section><div class="w"><h2>Courses and fees</h2><div class="tablewrap"><table>
{% for c in courses %}<tr><form method="post" action="{{ url_for('course_save') }}"><td>{{ c.name }}<input type="hidden" name="id" value="{{ c.id }}"></td>
<td style="width:130px"><input name="price" type="number" min="0" value="{{ c.price }}"></td><td><button class="btn o" style="margin:0;padding:6px 14px">Save</button>
<button class="btn o" name="del" value="1" style="margin:0;padding:6px 14px" onclick="return confirm('Delete course?')">Delete</button></td></form></tr>{% endfor %}</table></div>
<h3>Add course</h3><form method="post" action="{{ url_for('course_save') }}" class="two"><label>Name<input name="name" required></label>
<label>Category<select name="grp">{% for k,v in groups.items() %}<option value="{{ k }}">{{ v }}</option>{% endfor %}</select></label>
<label>Fee (₹)<input name="price" type="number" min="0" required></label><div style="align-self:end"><button class="btn">Add</button></div></form></div></section>"""

def need_admin():
    return None if session.get("admin") else redirect(url_for("admin"))

@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST":
        if request.form.get("pw") == ADMIN_PASSWORD: session["admin"] = True
        else: flash("Wrong password.", "bad")
        return redirect(url_for("admin"))
    if not session.get("admin"): return page(LOGIN)
    rows = db().execute("SELECT * FROM enrollments ORDER BY created DESC, id DESC").fetchall()
    items = {e["id"]: db().execute("SELECT course, completed FROM items WHERE eid=?", (e["id"],)).fetchall() for e in rows}
    test_results = db().execute("SELECT * FROM test_results ORDER BY id DESC LIMIT 50").fetchall()
    passages = db().execute("SELECT * FROM practice_passages ORDER BY id").fetchall()
    students = db().execute("SELECT * FROM students ORDER BY id DESC LIMIT 50").fetchall()
    exam_attempts = db().execute("SELECT * FROM student_exam_attempts ORDER BY id DESC LIMIT 50").fetchall()
    admissions = db().execute("SELECT * FROM student_admissions ORDER BY id DESC LIMIT 50").fetchall()
    return page(ADMIN, rows=rows, items=items, courses=db().execute("SELECT * FROM courses ORDER BY id").fetchall(),
                groups=GROUPS, test_results=test_results, passages=passages,
                students=students, exam_attempts=exam_attempts, admissions=admissions)

@app.route("/logout")
def logout():
    session.pop("admin", None); return redirect(url_for("home"))

@app.post("/admin/complete")
def complete():
    if (r := need_admin()): return r
    db().execute("UPDATE items SET completed=? WHERE eid=? AND course=?", (date.today().strftime("%d %b %Y"), request.form["eid"], request.form["course"]))
    db().commit(); return redirect(url_for("admin"))

@app.post("/admin/paid")
def paid():
    if (r := need_admin()): return r
    db().execute("UPDATE enrollments SET paid=1-paid WHERE id=?", (request.form["eid"],)); db().commit()
    return redirect(url_for("admin"))

@app.post("/admin/course")
def course_save():
    if (r := need_admin()): return r
    f, d = request.form, db()
    if f.get("id"):
        if f.get("del"): d.execute("DELETE FROM courses WHERE id=?", (f["id"],))
        else: d.execute("UPDATE courses SET price=? WHERE id=?", (int(f["price"]), f["id"]))
    elif f.get("name"):
        try: d.execute("INSERT INTO courses(name,grp,price) VALUES(?,?,?)", (f["name"].strip(), f["grp"], int(f["price"])))
        except sqlite3.IntegrityError: flash("Course already exists.", "bad")
    d.commit(); return redirect(url_for("admin"))

@app.post("/admin/passage/save")
def admin_add_passage():
    if (r := need_admin()): return r
    f, d = request.form, db()
    d.execute("""
        INSERT INTO practice_passages(title, category, lang, speed_wpm, duration_mins, content, notes, created)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        f["title"].strip(), f["category"], f["lang"], int(f["speed_wpm"]),
        int(f["duration_mins"]), f["content"].strip(), f.get("notes", "").strip(),
        date.today().isoformat()
    ))
    d.commit()
    flash("New passage successfully added to practice portal.", "ok")
    return redirect(url_for("admin"))

@app.post("/admin/passage/del")
def admin_delete_passage():
    if (r := need_admin()): return r
    pid = request.form.get("pid")
    d = db()
    d.execute("DELETE FROM practice_passages WHERE id=?", (pid,))
    d.commit()
    flash("Passage deleted.", "ok")
    return redirect(url_for("admin"))

@app.post("/admin/result/del")
def admin_delete_result():
    if (r := need_admin()): return r
    rid = request.form.get("rid")
    d = db()
    d.execute("DELETE FROM test_results WHERE id=?", (rid,))
    d.commit()
    flash("Test result record deleted.", "ok")
    return redirect(url_for("admin"))


# ---------- Register Blueprints ----------
from practice_portal import practice_bp
app.register_blueprint(practice_bp)

from exam_portal import exam_bp
app.register_blueprint(exam_bp)

init()
if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
