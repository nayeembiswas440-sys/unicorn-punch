import os
import sqlite3
import urllib.parse
from datetime import datetime
from flask import Flask, request, redirect, jsonify

app = Flask(__name__)
DB_FILE = "cloud_attendance.db"

# ম্যানেজার এবং সিইও-দের জন্য গোপন পিন কোড
ADMIN_PIN = "1234"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS attendance_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_code TEXT,
                employee_name TEXT,
                attendance_date TEXT,
                in_time TEXT,
                lunch_start TEXT,
                lunch_end TEXT,
                out_time TEXT,
                status TEXT DEFAULT 'PRESENT',
                late_minutes INTEGER DEFAULT 0,
                correction_reason TEXT,
                UNIQUE(employee_code, attendance_date)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS employees_cache (
                code TEXT PRIMARY KEY,
                name TEXT,
                desig TEXT,
                dept TEXT
            )
        """)
    conn.close()

init_db()

@app.route('/')
def home():
    return "<div style='font-family:sans-serif; text-align:center; padding-top:50px;'><h2>Unicorn HRMS Cloud Server is Live 🚀</h2><p><a href='/admin'>Go to CEO & Manager Live Dashboard</a></p></div>"

# --- CEO & MANAGER LIVE MONITORING PORTAL ---
@app.route('/admin')
def admin_dashboard():
    entered_pin = request.args.get('pin', '')
    selected_date = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))

    if entered_pin != ADMIN_PIN:
        return f"""<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Management Access Portal</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: #0F172A; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin:0; padding:20px; }}
        .box {{ background: white; padding: 32px 28px; border-radius: 18px; max-width: 360px; width: 100%; text-align: center; box-shadow: 0 20px 40px rgba(0,0,0,0.3); }}
        h2 {{ color: #0F172A; margin-bottom: 6px; font-size: 20px; }}
        p {{ color: #64748B; font-size: 13px; margin-bottom: 20px; }}
        input {{ width: 100%; box-sizing: border-box; padding: 12px; border: 1.5px solid #CBD5E1; border-radius: 8px; font-size: 16px; text-align: center; letter-spacing: 4px; margin-bottom: 16px; outline:none; }}
        button {{ width: 100%; padding: 12px; background: #2563EB; color: white; border: none; border-radius: 8px; font-weight: bold; font-size: 14px; cursor: pointer; }}
    </style>
</head>
<body>
    <div class="box">
        <h2>🔒 Management Portal</h2>
        <p>Enter 4-Digit Security PIN (Default: 1234)</p>
        <form method="GET" action="/admin">
            <input type="password" name="pin" placeholder="••••" required autofocus>
            <button type="submit">Unlock Dashboard</button>
        </form>
    </div>
</body>
</html>"""

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("""
        SELECT employee_code, employee_name, in_time, lunch_start, lunch_end, out_time, status, late_minutes, correction_reason
        FROM attendance_logs
        WHERE attendance_date = ?
        ORDER BY in_time ASC
    """, (selected_date,))
    rows = cur.fetchall()
    conn.close()

    total_present = len(rows)
    late_count = sum(1 for r in rows if r[6] == 'LATE' or (r[7] and r[7] > 0))
    early_exit_count = sum(1 for r in rows if r[8] and len(r[8].strip()) > 0)

    rows_html = ""
    for r in rows:
        code, name, in_t, l_out, l_in, out_t, st, late_m, reason = r
        late_badge = f"<span style='color:#DC2626; font-weight:bold;'>⚠️ {late_m}m Late</span>" if late_m and late_m > 0 else "<span style='color:#16A34A; font-weight:bold;'>On-Time</span>"
        reason_html = f"<span style='background:#FEE2E2; color:#991B1B; padding:3px 8px; border-radius:6px; font-size:12px; display:inline-block;'>🏃‍♂️ {reason}</span>" if reason else "<span style='color:#94A3B8;'>—</span>"
        
        rows_html += f"""
        <tr>
            <td><b>{code}</b></td>
            <td><b>{name}</b></td>
            <td><span style='color:#15803D; font-weight:600;'>{in_t or '--:--'}</span> ({late_badge})</td>
            <td>{l_out or '--:--'}</td>
            <td>{l_in or '--:--'}</td>
            <td><span style='color:#B91C1C; font-weight:600;'>{out_t or '--:--'}</span></td>
            <td>{reason_html}</td>
        </tr>
        """

    if not rows_html:
        rows_html = "<tr><td colspan='7' style='text-align:center; padding:30px; color:#94A3B8;'>আজকের দিনে এখনো কেউ পাঞ্চ করেনি।</td></tr>"

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CEO & Manager Live Attendance Console</title>
    <style>
        * {{ margin:0; padding:0; box-sizing:border-box; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
        body {{ background: #F8FAFC; color: #0F172A; padding: 20px; }}
        .header {{ max-width: 1100px; margin: 0 auto 20px auto; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; }}
        .stats {{ max-width: 1100px; margin: 0 auto 20px auto; display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 14px; }}
        .card {{ background: white; padding: 18px; border-radius: 14px; border: 1px solid #E2E8F0; }}
        .num {{ font-size: 26px; font-weight: 800; margin-top: 4px; }}
        .container {{ max-width: 1100px; margin: 0 auto; background: white; border-radius: 16px; border: 1px solid #E2E8F0; overflow-x: auto; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.03); }}
        table {{ width: 100%; border-collapse: collapse; text-align: left; font-size: 13.5px; min-width: 750px; }}
        th {{ background: #F1F5F9; color: #475569; padding: 14px 16px; font-weight: 700; border-bottom: 1px solid #E2E8F0; }}
        td {{ padding: 14px 16px; border-bottom: 1px solid #F1F5F9; }}
    </style>
</head>
<body>
    <div class="header">
        <div>
            <h1 style="font-size:20px; font-weight:800;">Unicorn Live Attendance Board</h1>
            <p style="font-size:12px; color:#64748B;">Manager & CEO Executive View</p>
        </div>
        <form method="GET" action="/admin" style="display:flex; gap:8px;">
            <input type="hidden" name="pin" value="{ADMIN_PIN}">
            <input type="date" name="date" value="{selected_date}" style="padding:8px 12px; border:1px solid #CBD5E1; border-radius:8px;">
            <button type="submit" style="padding:8px 14px; background:#0F172A; color:white; border:none; border-radius:8px; font-weight:bold; cursor:pointer;">Filter</button>
        </form>
    </div>

    <div class="stats">
        <div class="card"><div style="font-size:11px; color:#64748B; font-weight:700;">TOTAL PRESENT</div><div class="num" style="color:#2563EB;">{total_present}</div></div>
        <div class="card"><div style="font-size:11px; color:#64748B; font-weight:700;">LATE ARRIVALS</div><div class="num" style="color:#DC2626;">{late_count}</div></div>
        <div class="card"><div style="font-size:11px; color:#64748B; font-weight:700;">EARLY EXITS</div><div class="num" style="color:#D97706;">{early_exit_count}</div></div>
    </div>

    <div class="container">
        <table>
            <thead>
                <tr>
                    <th>Code</th>
                    <th>Name</th>
                    <th>Office In (10:00 AM)</th>
                    <th>Lunch Out</th>
                    <th>Lunch In (2:15 PM)</th>
                    <th>Exit Time</th>
                    <th>Early Exit Reason</th>
                </tr>
            </thead>
            <tbody>
                {rows_html}
            </tbody>
        </table>
    </div>
</body>
</html>"""

# --- EMPLOYEE PUNCH PORTAL & APIS ---
@app.route('/api/sync_employees', methods=['POST'])
def sync_employees():
    data = request.json or []
    conn = sqlite3.connect(DB_FILE)
    with conn:
        for emp in data:
            conn.execute("""
                INSERT INTO employees_cache (code, name, desig, dept)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(code) DO UPDATE SET
                    name=excluded.name, desig=excluded.desig, dept=excluded.dept
            """, (emp.get('code'), emp.get('name'), emp.get('desig', 'Staff'), emp.get('dept', 'General')))
    conn.close()
    return jsonify({"status": "ok", "synced": len(data)})

@app.route('/api/get_attendance')
def get_attendance():
    date_filter = request.args.get('date', '')
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    if date_filter:
        cur.execute("SELECT employee_code, employee_name, attendance_date, in_time, lunch_start, lunch_end, out_time, status, late_minutes, correction_reason FROM attendance_logs WHERE attendance_date = ?", (date_filter,))
    else:
        cur.execute("SELECT employee_code, employee_name, attendance_date, in_time, lunch_start, lunch_end, out_time, status, late_minutes, correction_reason FROM attendance_logs ORDER BY attendance_date DESC LIMIT 500")
    rows = cur.fetchall()
    conn.close()

    result = []
    for r in rows:
        result.append({
            "code": r[0], "name": r[1], "date": r[2],
            "in_time": r[3], "lunch_start": r[4], "lunch_end": r[5],
            "out_time": r[6], "status": r[7], "late_minutes": r[8],
            "notes": r[9]
        })
    return jsonify(result)

@app.route('/p/<code>')
def employee_portal(code):
    msg = request.args.get('msg', '')
    alert_type = request.args.get('type', 'info')

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT name, desig, dept FROM employees_cache WHERE code = ?", (code,))
    emp = cur.fetchone()
    
    name = emp[0] if emp else f"Employee {code}"
    desig = emp[1] if emp else "Staff"
    dept = emp[2] if emp else "Studio"

    today_str = datetime.now().strftime('%Y-%m-%d')
    cur.execute("SELECT in_time, lunch_start, lunch_end, out_time, correction_reason FROM attendance_logs WHERE employee_code = ? AND attendance_date = ?", (code, today_str))
    att = cur.fetchone()
    conn.close()

    in_t = att[0] if att and att[0] else '--:--'
    l_start = att[1] if att and att[1] else '--:--'
    l_end = att[2] if att and att[2] else '--:--'
    out_t = att[3] if att and att[3] else '--:--'
    reason_note = att[4] if att and att[4] else ''

    banner_colors = {
        "success": "background: #DCFCE7; color: #166534; border: 1.5px solid #86EFAC;",
        "warning": "background: #FEF3C7; color: #92400E; border: 1.5px solid #FCD34D;",
        "danger": "background: #FEE2E2; color: #991B1B; border: 1.5px solid #FCA5A5;",
        "info": "background: #EFF6FF; color: #1E40AF; border: 1.5px solid #93C5FD;"
    }
    banner_style = banner_colors.get(alert_type, banner_colors["info"])
    banner_html = f'<div style="{banner_style} padding: 14px 18px; border-radius: 12px; margin-bottom: 20px; font-weight: 700; font-size: 14px; text-align: left; line-height: 1.5;">{msg}</div>' if msg else ""
    reason_row = f'<div class="row" style="background:#FEF2F2; padding:10px 12px; border-radius:10px; margin-top:8px; border:1px solid #FECACA;"><span class="lbl" style="color:#DC2626; font-weight:bold;">🏃‍♂️ Exit Reason:</span><span class="val" style="color:#991B1B;">{reason_note}</span></div>' if reason_note else ""

    return f"""<!DOCTYPE html>
<html lang="bn">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{name} — Workstation Cloud</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
        body {{ background-color: #F8FAFC; color: #0F172A; display: flex; justify-content: center; align-items: center; min-height: 100vh; padding: 20px; }}
        .card {{ background: #FFFFFF; width: 100%; max-width: 460px; border-radius: 24px; border: 1.5px solid #E2E8F0; box-shadow: 0 15px 35px -5px rgba(0, 0, 0, 0.06); padding: 32px 26px; text-align: center; }}
        .badge {{ display: inline-block; background: #EFF6FF; color: #2563EB; font-weight: 800; font-size: 11px; padding: 5px 12px; border-radius: 9999px; margin-bottom: 10px; letter-spacing: 0.5px; text-transform: uppercase; }}
        .greet {{ font-size: 22px; font-weight: 800; color: #0F172A; margin-bottom: 4px; }}
        .sub {{ font-size: 13px; color: #64748B; margin-bottom: 20px; font-weight: 500; }}
        .clock-box {{ background: #0F172A; color: #F8FAFC; border-radius: 16px; padding: 18px; text-align: center; margin-bottom: 22px; }}
        .clock-time {{ font-size: 32px; font-weight: 800; letter-spacing: 1px; font-variant-numeric: tabular-nums; }}
        .clock-date {{ font-size: 12px; color: #94A3B8; margin-top: 4px; font-weight: 500; }}
        .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 22px; }}
        button {{ width: 100%; padding: 15px 12px; border: none; border-radius: 14px; font-size: 14px; font-weight: 700; cursor: pointer; transition: all 0.2s ease; display: flex; flex-direction: column; align-items: center; gap: 4px; }}
        button:hover {{ transform: translateY(-2px); filter: brightness(0.96); }}
        .btn-in {{ background: #DCFCE7; color: #15803D; border: 1px solid #BBF7D0; }}
        .btn-lunch-start {{ background: #FEF3C7; color: #B45309; border: 1px solid #FDE68A; }}
        .btn-lunch-end {{ background: #E0E7FF; color: #4338CA; border: 1px solid #C7D2FE; }}
        .btn-out {{ background: #FEE2E2; color: #B91C1C; border: 1px solid #FECACA; }}
        .summary {{ background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 14px; padding: 16px; text-align: left; }}
        .row {{ display: flex; justify-content: space-between; font-size: 13px; padding: 7px 0; border-bottom: 1px dashed #E2E8F0; }}
        .row:last-child {{ border-bottom: none; }}
        .lbl {{ color: #64748B; font-weight: 500; }}
        .val {{ font-weight: 700; color: #0F172A; }}

        .modal-overlay {{ display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(15, 23, 42, 0.6); backdrop-filter: blur(4px); justify-content: center; align-items: center; z-index: 999; padding: 20px; }}
        .modal-box {{ background: white; width: 100%; max-width: 420px; border-radius: 20px; padding: 26px; text-align: center; box-shadow: 0 20px 40px rgba(0,0,0,0.2); }}
        .modal-box h3 {{ font-size: 20px; color: #DC2626; font-weight: 800; margin-bottom: 8px; }}
        .modal-box p {{ font-size: 13px; color: #475569; margin-bottom: 16px; line-height: 1.5; }}
        .modal-box textarea {{ width: 100%; height: 80px; padding: 12px; border: 1.5px solid #CBD5E1; border-radius: 10px; font-size: 13px; margin-bottom: 16px; outline: none; }}
        .modal-actions {{ display: flex; gap: 10px; }}
        .btn-cancel {{ background: #F1F5F9; color: #475569; flex: 1; }}
        .btn-submit-early {{ background: #DC2626; color: white; flex: 1.5; }}
    </style>
</head>
<body>
    <div class="card">
        <span class="badge">Unicorn Workstation • Cloud 24/7</span>
        <h1 class="greet">Hello, {name}! 👋</h1>
        <p class="sub">{desig} • {dept} (Code: {code})</p>

        {banner_html}

        <div class="clock-box">
            <div class="clock-time" id="clock">--:--:--</div>
            <div class="clock-date" id="cdate">--</div>
        </div>

        <div class="grid">
            <form method="POST" action="/punch/{code}">
                <input type="hidden" name="action" value="in_time">
                <button type="submit" class="btn-in"><span>🟢 Office In</span><small style="font-size:11px; opacity:0.8;">Starts 10:00 AM</small></button>
            </form>
            <form method="POST" action="/punch/{code}">
                <input type="hidden" name="action" value="lunch_start">
                <button type="submit" class="btn-lunch-start"><span>☕ Lunch Out</span><small style="font-size:11px; opacity:0.8;">1:15 PM - 2:15 PM</small></button>
            </form>
            <form method="POST" action="/punch/{code}">
                <input type="hidden" name="action" value="lunch_end">
                <button type="submit" class="btn-lunch-end"><span>🍱 Lunch In</span><small style="font-size:11px; opacity:0.8;">Before 2:15 PM</small></button>
            </form>
            <form id="outForm" method="POST" action="/punch/{code}">
                <input type="hidden" name="action" value="out_time">
                <input type="hidden" id="earlyReasonInput" name="early_reason" value="">
                <button type="button" class="btn-out" onclick="handleExitClick()"><span>🔴 Exit Out</span><small style="font-size:11px; opacity:0.8;">Close 6:30 PM</small></button>
            </form>
        </div>

        <div class="summary">
            <div class="row"><span class="lbl">🟢 Today's Entry:</span><span class="val">{in_t}</span></div>
            <div class="row"><span class="lbl">☕ Lunch Break Started:</span><span class="val">{l_start}</span></div>
            <div class="row"><span class="lbl">🍱 Lunch Break Ended:</span><span class="val">{l_end}</span></div>
            <div class="row"><span class="lbl">🔴 Office Departure:</span><span class="val">{out_t}</span></div>
            {reason_row}
        </div>
    </div>

    <div id="earlyModal" class="modal-overlay">
        <div class="modal-box">
            <h3>🏃‍♂️ এত তাড়া কিসের?</h3>
            <p>আমাদের অফিস ছুটি তো <b>সন্ধ্যা ৬:৩০ টায়</b>!<br/>আপনি নির্দিষ্ট সময়ের আগেই অফিস ত্যাগ করছেন। দ্রুত চলে যাওয়ার কারণটি উল্লেখ করুন:</p>
            <textarea id="earlyReasonText" placeholder="জরুরি কারণ বিস্তারিত লিখুন..."></textarea>
            <div class="modal-actions">
                <button type="button" class="btn-cancel" onclick="closeModal()">বাতিল</button>
                <button type="button" class="btn-submit-early" onclick="submitEarlyExit()">সাবমিট ও প্রস্থান</button>
            </div>
        </div>
    </div>

    <script>
        function updateClock() {{
            const now = new Date();
            document.getElementById('clock').innerText = now.toLocaleTimeString('en-US', {{ hour12: true }});
            document.getElementById('cdate').innerText = now.toLocaleDateString('en-US', {{ weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' }});
        }}
        setInterval(updateClock, 1000);
        updateClock();

        function handleExitClick() {{
            const now = new Date();
            const currentMins = now.getHours() * 60 + now.getMinutes();
            const targetMins = 18 * 60 + 30;
            if (currentMins < targetMins) {{
                document.getElementById('earlyModal').style.display = 'flex';
            }} else {{
                document.getElementById('outForm').submit();
            }}
        }}

        function closeModal() {{
            document.getElementById('earlyModal').style.display = 'none';
        }}

        function submitEarlyExit() {{
            const reason = document.getElementById('earlyReasonText').value.trim();
            if (!reason) {{
                alert('অনুগ্রহ করে আগে চলে যাওয়ার কারণটি লিখুন!');
                return;
            }}
            document.getElementById('earlyReasonInput').value = reason;
            document.getElementById('outForm').submit();
        }}
    </script>
</body>
</html>"""

@app.route('/punch/<code>', methods=['POST'])
def punch_action(code):
    action = request.form.get('action', '')
    early_reason = request.form.get('early_reason', '').strip()

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT name FROM employees_cache WHERE code = ?", (code,))
    row = cur.fetchone()
    emp_name = row[0] if row else f"Employee {code}"

    now = datetime.now()
    today_str = now.strftime('%Y-%m-%d')
    now_time_str = now.strftime('%I:%M %p')
    current_minute = now.hour * 60 + now.minute

    OFFICE_START = 10 * 60
    LUNCH_START_LIMIT = 13 * 60 + 15
    LUNCH_END_LIMIT = 14 * 60 + 15
    OFFICE_EXIT = 18 * 60 + 30

    msg = "Punch recorded successfully!"
    alert_type = "success"

    with conn:
        conn.execute("""
            INSERT OR IGNORE INTO attendance_logs (employee_code, employee_name, attendance_date, status, late_minutes)
            VALUES (?, ?, ?, 'PRESENT', 0)
        """, (code, emp_name, today_str))

        if action == 'in_time':
            if current_minute > OFFICE_START:
                late_mins = current_minute - OFFICE_START
                msg = f"⚠️ আপনি {late_mins} মিনিট লেইট করেছেন! অফিস শুরু সকাল ১০:০০ টায়। নিয়মিত সময়মতো অফিসে আসুন।"
                alert_type = "warning"
                conn.execute("UPDATE attendance_logs SET in_time = ?, late_minutes = ?, status = 'LATE' WHERE employee_code = ? AND attendance_date = ?", (now_time_str, late_mins, code, today_str))
            else:
                msg = "👏 দারুণ! একদম সময়মতো অফিসে উপস্থিত হয়েছেন। আজকের দিনটি সুন্দর হোক!"
                alert_type = "success"
                conn.execute("UPDATE attendance_logs SET in_time = ?, late_minutes = 0, status = 'PRESENT' WHERE employee_code = ? AND attendance_date = ?", (now_time_str, code, today_str))

        elif action == 'lunch_start':
            if current_minute > (LUNCH_START_LIMIT + 5):
                late_break_mins = current_minute - LUNCH_START_LIMIT
                msg = f"⏰ On-time break নিতে হবে! আপনি {late_break_mins} মিনিট দেরিতে ব্রেক শুরু করলেন।"
                alert_type = "warning"
            else:
                msg = "🍱 লাঞ্চ ব্রেক শুরু হলো! দুপুর ২:১৫ PM এর মধ্যে খাওয়া শেষ করে ডেস্কে ফিরুন।"
                alert_type = "info"
            conn.execute("UPDATE attendance_logs SET lunch_start = ? WHERE employee_code = ? AND attendance_date = ?", (now_time_str, code, today_str))

        elif action == 'lunch_end':
            if current_minute > LUNCH_END_LIMIT:
                late_end_mins = current_minute - LUNCH_END_LIMIT
                msg = f"⚠️ আপনি {late_end_mins} মিনিট দেরি করে ব্রেক শেষ করলেন! এভাবে দেরি করা যাবে না।"
                alert_type = "danger"
            else:
                msg = "✅ অন-টাইমে লাঞ্চ শেষ করে কাজে ফিরেছেন! ওয়েল ডান!"
                alert_type = "success"
            conn.execute("UPDATE attendance_logs SET lunch_end = ? WHERE employee_code = ? AND attendance_date = ?", (now_time_str, code, today_str))

        elif action == 'out_time':
            if current_minute < OFFICE_EXIT:
                early_mins = OFFICE_EXIT - current_minute
                reason_entry = early_reason if early_reason else "Early Departure"
                msg = f"🏃‍♂️ নির্দিষ্ট সময়ের {early_mins} মিনিট আগেই অফিস ত্যাগের কারণ রেকর্ড হয়েছে: '{reason_entry}'"
                alert_type = "warning"
                conn.execute("UPDATE attendance_logs SET out_time = ?, correction_reason = ? WHERE employee_code = ? AND attendance_date = ?", (now_time_str, reason_entry, code, today_str))
            else:
                msg = "🎉 আজ সারাদিন নিষ্ঠার সাথে কাজ করেছেন! অফিস ছুটি, সাবধানে বাড়ি পৌঁছান।"
                alert_type = "success"
                conn.execute("UPDATE attendance_logs SET out_time = ? WHERE employee_code = ? AND attendance_date = ?", (now_time_str, code, today_str))

    conn.close()
    return redirect(f"/p/{code}?msg={urllib.parse.quote(msg)}&type={alert_type}")

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)