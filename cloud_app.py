import os
import sqlite3
import urllib.parse
from datetime import datetime, date
from zoneinfo import ZoneInfo
import calendar
from flask import Flask, request, redirect, jsonify

app = Flask(__name__)
DB_FILE = "cloud_attendance.db"

# সিইও ও ম্যানেজার সিক্রেট পিন
ADMIN_PIN = "1234"

# বাংলাদেশ টাইমজোন (GMT+6)
DHAKA_TZ = ZoneInfo("Asia/Dhaka")

def get_dhaka_now():
    return datetime.now(DHAKA_TZ)

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
                phone TEXT,
                dept TEXT,
                desig TEXT,
                base_salary REAL DEFAULT 0.0
            )
        """)
        initial_emps = [
            ('2542', 'Nayeem Biswas', '01650106943', 'General', 'Staff', 20000.0),
            ('256854', 'Anik Mia', '01590092227', 'Study Abroad', 'Reception', 15000.0),
            ('25986', 'Sabbir Hossain', '01401337088', 'Study Abroad', 'Manager', 40000.0)
        ]
        for emp in initial_emps:
            conn.execute("""
                INSERT OR IGNORE INTO employees_cache (code, name, phone, dept, desig, base_salary)
                VALUES (?, ?, ?, ?, ?, ?)
            """, emp)
    conn.close()

init_db()

@app.route('/')
def home():
    return "<div style='font-family:sans-serif; text-align:center; padding-top:50px;'><h2>Unicorn HRMS Cloud Server is Live 🚀</h2><p><a href='/admin' style='color:#2563EB; font-weight:bold;'>Go to CEO & Manager Admin Portal</a></p></div>"

# --- TWO-WAY SYNC APIS FOR DESKTOP APP ---
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

@app.route('/api/sync_attendance_from_desktop', methods=['POST'])
def sync_attendance_from_desktop():
    records = request.json or []
    conn = sqlite3.connect(DB_FILE)
    with conn:
        for r in records:
            conn.execute("""
                INSERT INTO attendance_logs (
                    employee_code, employee_name, attendance_date,
                    in_time, lunch_start, lunch_end, out_time,
                    status, late_minutes, correction_reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(employee_code, attendance_date) DO UPDATE SET
                    in_time=coalesce(excluded.in_time, attendance_logs.in_time),
                    lunch_start=coalesce(excluded.lunch_start, attendance_logs.lunch_start),
                    lunch_end=coalesce(excluded.lunch_end, attendance_logs.lunch_end),
                    out_time=coalesce(excluded.out_time, attendance_logs.out_time),
                    status=coalesce(excluded.status, attendance_logs.status),
                    late_minutes=coalesce(excluded.late_minutes, attendance_logs.late_minutes),
                    correction_reason=coalesce(excluded.correction_reason, attendance_logs.correction_reason)
            """, (
                r.get('code'), r.get('name'), r.get('date'),
                r.get('in_time'), r.get('lunch_start'), r.get('lunch_end'), r.get('out_time'),
                r.get('status', 'PRESENT'), r.get('late_minutes', 0), r.get('notes', '')
            ))
    conn.close()
    return jsonify({"status": "success", "count": len(records)})

@app.route('/api/sync_employees', methods=['POST'])
def sync_employees():
    data = request.json or []
    conn = sqlite3.connect(DB_FILE)
    with conn:
        for emp in data:
            conn.execute("""
                INSERT INTO employees_cache (code, name, phone, dept, desig, base_salary)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(code) DO UPDATE SET
                    name=excluded.name, phone=excluded.phone, dept=excluded.dept,
                    desig=excluded.desig, base_salary=excluded.base_salary
            """, (emp.get('code'), emp.get('name'), emp.get('phone', ''), emp.get('dept', 'General'), emp.get('desig', 'Staff'), emp.get('base_salary', 0.0)))
    conn.close()
    return jsonify({"status": "ok", "synced": len(data)})

# --- CEO & MANAGER ADMIN PORTAL ---
@app.route('/admin')
def admin_portal():
    entered_pin = request.args.get('pin', '')
    active_tab = request.args.get('tab', 'live')
    today_str = get_dhaka_now().strftime('%Y-%m-%d')
    selected_date = request.args.get('date', today_str)
    selected_month = request.args.get('month', get_dhaka_now().strftime('%Y-%m'))

    if entered_pin != ADMIN_PIN:
        return f"""<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Management Login — Unicorn HRMS</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: #0F172A; display:flex; justify-content:center; align-items:center; min-height:100vh; margin:0; padding:20px; }}
        .box {{ background: white; padding: 36px 30px; border-radius: 20px; max-width: 380px; width:100%; text-align:center; box-shadow: 0 20px 40px rgba(0,0,0,0.4); }}
        h2 {{ color: #0F172A; margin-bottom: 6px; font-size: 22px; font-weight:800; }}
        p {{ color: #64748B; font-size: 13px; margin-bottom: 24px; }}
        input {{ width: 100%; box-sizing: border-box; padding: 14px; border: 2px solid #E2E8F0; border-radius: 10px; font-size: 18px; text-align: center; letter-spacing: 6px; margin-bottom: 18px; outline:none; }}
        input:focus {{ border-color: #2563EB; }}
        button {{ width: 100%; padding: 14px; background: #2563EB; color: white; border: none; border-radius: 10px; font-weight: 700; font-size: 15px; cursor: pointer; }}
        button:hover {{ background: #1D4ED8; }}
    </style>
</head>
<body>
    <div class="box">
        <h2>🔒 Executive Portal</h2>
        <p>Enter 4-Digit Security PIN (Default: <b>1234</b>)</p>
        <form method="GET" action="/admin">
            <input type="password" name="pin" placeholder="••••" required autofocus>
            <button type="submit">Unlock Dashboard</button>
        </form>
    </div>
</body>
</html>"""

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT code, name, phone, dept, desig, base_salary FROM employees_cache ORDER BY name ASC")
    employees = cur.fetchall()

    # TAB 1: TODAY'S LIVE ATTENDANCE
    cur.execute("""
        SELECT employee_code, employee_name, in_time, lunch_start, lunch_end, out_time, status, late_minutes, correction_reason
        FROM attendance_logs WHERE attendance_date = ?
    """, (selected_date,))
    daily_records = {r[0]: r for r in cur.fetchall()}

    live_rows = ""
    present_today = 0
    late_today = 0
    early_exit_today = 0

    for emp in employees:
        code, name, phone, dept, desig, sal = emp
        rec = daily_records.get(code)
        if rec:
            present_today += 1
            in_t = rec[2] or '--:--'
            l_out = rec[3] or '--:--'
            l_in = rec[4] or '--:--'
            out_t = rec[5] or '--:--'
            late_m = rec[7] or 0
            reason = rec[8] or ''

            if late_m > 0:
                late_today += 1
                status_badge = f"<span style='color:#DC2626; font-weight:bold;'>⚠️ {late_m}m Late</span>"
            else:
                status_badge = "<span style='color:#16A34A; font-weight:bold;'>On-Time</span>"

            if reason:
                early_exit_today += 1
                reason_badge = f"<span style='background:#FEE2E2; color:#991B1B; padding:3px 8px; border-radius:6px; font-size:12px; font-weight:600;'>🏃‍♂️ {reason}</span>"
            else:
                reason_badge = "<span style='color:#94A3B8;'>—</span>"

            live_rows += f"""
            <tr>
                <td><b>{code}</b></td>
                <td><b>{name}</b><br><small style='color:#64748B;'>{desig} • {dept}</small></td>
                <td><span style='color:#15803D; font-weight:bold;'>{in_t}</span><br>{status_badge}</td>
                <td>{l_out}</td>
                <td>{l_in}</td>
                <td><span style='color:#B91C1C; font-weight:bold;'>{out_t}</span></td>
                <td>{reason_badge}</td>
            </tr>
            """
        else:
            live_rows += f"""
            <tr style='background:#FFF1F2;'>
                <td><b>{code}</b></td>
                <td><b>{name}</b><br><small style='color:#64748B;'>{desig} • {dept}</small></td>
                <td colspan='5' style='color:#E11D48; font-weight:bold; padding-left:20px;'>❌ ABSENT (এখনও উপস্থিতি রেকর্ড নেই)</td>
            </tr>
            """

    # TAB 2 & 3: MONTHLY ABSENT TRACKER & PAYROLL ENGINE
    year_val, month_val = map(int, selected_month.split('-'))
    num_days_in_month = calendar.monthrange(year_val, month_val)[1]
    
    today_curr = get_dhaka_now()
    if today_curr.year == year_val and today_curr.month == month_val:
        days_passed = today_curr.day
    else:
        days_passed = num_days_in_month

    cur.execute("""
        SELECT employee_code, attendance_date, status, late_minutes 
        FROM attendance_logs 
        WHERE attendance_date LIKE ?
    """, (f"{selected_month}%",))
    monthly_logs = cur.fetchall()
    conn.close()

    emp_monthly_map = {emp[0]: [] for emp in employees}
    for m in monthly_logs:
        if m[0] in emp_monthly_map:
            emp_monthly_map[m[0]].append(m)

    monthly_rows = ""
    payroll_rows = ""
    total_payroll_cost = 0

    for emp in employees:
        code, name, phone, dept, desig, base_sal = emp
        logs = emp_monthly_map.get(code, [])
        
        attended_dates = set([l[1] for l in logs])
        present_days = len(attended_dates)
        total_late_mins = sum([l[3] for l in logs if l[3]])
        late_days_count = sum([1 for l in logs if l[3] and l[3] > 0])
        
        absent_days_list = []
        for d in range(1, days_passed + 1):
            check_date_str = f"{selected_month}-{d:02d}"
            cur_weekday = date(year_val, month_val, d).weekday()
            if cur_weekday == 4: # Friday holiday
                continue
            if check_date_str not in attended_dates:
                absent_days_list.append(f"{d:02d} {calendar.month_abbr[month_val]}")

        absent_count = len(absent_days_list)
        absent_display = ", ".join(absent_days_list[:5])
        if len(absent_days_list) > 5:
            absent_display += f" ... (+{len(absent_days_list)-5} more)"

        monthly_rows += f"""
        <tr>
            <td><b>{code}</b></td>
            <td><b>{name}</b><br><small style='color:#64748B;'>{dept}</small></td>
            <td><span style='color:#15803D; font-weight:bold;'>{present_days} Days</span></td>
            <td><span style='color:#DC2626; font-weight:bold;'>{absent_count} Days</span><br><small style='color:#64748B;'>({absent_display if absent_count else 'No Absents'})</small></td>
            <td><span style='color:#D97706; font-weight:bold;'>{late_days_count} Times</span><br><small style='color:#64748B;'>({total_late_mins} mins total)</small></td>
        </tr>
        """

        per_day_sal = base_sal / 30.0 if base_sal else 0.0
        absent_deduction = absent_count * per_day_sal
        late_deduction = (late_days_count // 3) * per_day_sal
        net_salary = max(0.0, base_sal - absent_deduction - late_deduction)
        total_payroll_cost += net_salary

        payroll_rows += f"""
        <tr>
            <td><b>{code}</b></td>
            <td><b>{name}</b><br><small style='color:#64748B;'>{desig}</small></td>
            <td><b>৳ {base_sal:,.2f}</b></td>
            <td><span style='color:#DC2626;'>- ৳ {absent_deduction:,.2f}</span><br><small>({absent_count}d absent)</small></td>
            <td><span style='color:#D97706;'>- ৳ {late_deduction:,.2f}</span><br><small>({late_days_count} late penalties)</small></td>
            <td><span style='color:#16A34A; font-weight:800; font-size:15px;'>৳ {net_salary:,.2f}</span></td>
        </tr>
        """

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Executive Attendance & Payroll Console</title>
    <style>
        * {{ margin:0; padding:0; box-sizing:border-box; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
        body {{ background: #F8FAFC; color: #0F172A; padding: 24px 16px; }}
        .header {{ max-width: 1200px; margin: 0 auto 24px auto; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 16px; }}
        .nav-tabs {{ display: flex; gap: 8px; margin-bottom: 20px; max-width: 1200px; margin: 0 auto 20px auto; }}
        .tab-btn {{ padding: 10px 18px; border-radius: 10px; text-decoration: none; font-weight: 700; font-size: 13.5px; border: 1.5px solid #CBD5E1; color: #475569; background: white; }}
        .tab-btn.active {{ background: #0F172A; color: white; border-color: #0F172A; }}
        .stats {{ max-width: 1200px; margin: 0 auto 20px auto; display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 14px; }}
        .card {{ background: white; padding: 20px; border-radius: 14px; border: 1px solid #E2E8F0; }}
        .num {{ font-size: 26px; font-weight: 800; margin-top: 4px; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; border-radius: 16px; border: 1px solid #E2E8F0; overflow-x: auto; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.04); }}
        table {{ width: 100%; border-collapse: collapse; text-align: left; font-size: 13.5px; min-width: 800px; }}
        th {{ background: #F1F5F9; color: #475569; padding: 14px 18px; font-weight: 700; border-bottom: 1px solid #E2E8F0; }}
        td {{ padding: 14px 18px; border-bottom: 1px solid #F1F5F9; vertical-align: middle; }}
    </style>
</head>
<body>
    <div class="header">
        <div>
            <h1 style="font-size:22px; font-weight:800;">Unicorn Central Control</h1>
            <p style="font-size:12px; color:#64748B;">CEO & Manager Cloud Dashboard</p>
        </div>
        <form method="GET" action="/admin" style="display:flex; gap:8px;">
            <input type="hidden" name="pin" value="{ADMIN_PIN}">
            <input type="hidden" name="tab" value="{active_tab}">
            {'<input type="date" name="date" value="' + selected_date + '" style="padding:8px 12px; border:1px solid #CBD5E1; border-radius:8px;">' if active_tab == 'live' else '<input type="month" name="month" value="' + selected_month + '" style="padding:8px 12px; border:1px solid #CBD5E1; border-radius:8px;">'}
            <button type="submit" style="padding:8px 16px; background:#2563EB; color:white; border:none; border-radius:8px; font-weight:bold; cursor:pointer;">Filter</button>
        </form>
    </div>

    <div class="nav-tabs">
        <a href="/admin?pin={ADMIN_PIN}&tab=live&date={selected_date}" class="tab-btn {'active' if active_tab == 'live' else ''}">🕒 Live Today</a>
        <a href="/admin?pin={ADMIN_PIN}&tab=absents&month={selected_month}" class="tab-btn {'active' if active_tab == 'absents' else ''}">📅 Monthly Attendance & Absents</a>
        <a href="/admin?pin={ADMIN_PIN}&tab=payroll&month={selected_month}" class="tab-btn {'active' if active_tab == 'payroll' else ''}">💰 Payroll & Salary Sheet</a>
    </div>

    {'<div class="stats"><div class="card"><div style="font-size:11px; color:#64748B; font-weight:700;">TOTAL PRESENT TODAY</div><div class="num" style="color:#16A34A;">' + str(present_today) + ' / ' + str(len(employees)) + '</div></div><div class="card"><div style="font-size:11px; color:#64748B; font-weight:700;">LATE ARRIVALS</div><div class="num" style="color:#DC2626;">' + str(late_today) + '</div></div><div class="card"><div style="font-size:11px; color:#64748B; font-weight:700;">EARLY DEPARTURES</div><div class="num" style="color:#D97706;">' + str(early_exit_today) + '</div></div></div>' if active_tab == 'live' else ''}

    {'<div class="stats"><div class="card"><div style="font-size:11px; color:#64748B; font-weight:700;">PROJECTED PAYROLL DISBURSEMENT</div><div class="num" style="color:#2563EB;">৳ ' + f"{total_payroll_cost:,.2f}" + '</div></div><div class="card"><div style="font-size:11px; color:#64748B; font-weight:700;">ACTIVE STAFF MONITORED</div><div class="num" style="color:#0F172A;">' + str(len(employees)) + ' People</div></div></div>' if active_tab == 'payroll' else ''}

    <div class="container">
        <table>
            {'''<thead>
                <tr><th>Code</th><th>Name</th><th>Entry (10:00 AM)</th><th>Lunch Out</th><th>Lunch In (2:15 PM)</th><th>Exit Time</th><th>Early Reason</th></tr>
            </thead><tbody>''' + live_rows + '</tbody>' if active_tab == 'live' else ''}

            {'''<thead>
                <tr><th>Code</th><th>Name</th><th>Total Present</th><th>Total Absent & Dates</th><th>Late Frequency</th></tr>
            </thead><tbody>''' + monthly_rows + '</tbody>' if active_tab == 'absents' else ''}

            {'''<thead>
                <tr><th>Code</th><th>Name</th><th>Base Salary</th><th>Absent Deduction</th><th>Late Penalty</th><th>Net Payable Salary</th></tr>
            </thead><tbody>''' + payroll_rows + '</tbody>' if active_tab == 'payroll' else ''}
        </table>
    </div>
</body>
</html>"""

# --- EMPLOYEE PUNCH PORTAL ---
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

    today_str = get_dhaka_now().strftime('%Y-%m-%d')
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
            document.getElementById('clock').innerText = now.toLocaleTimeString('en-US', {{ timeZone: 'Asia/Dhaka', hour12: true }});
            document.getElementById('cdate').innerText = now.toLocaleDateString('en-US', {{ timeZone: 'Asia/Dhaka', weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' }});
        }}
        setInterval(updateClock, 1000);
        updateClock();

        function handleExitClick() {{
            const now = new Date();
            const bdDate = new Date(now.toLocaleString("en-US", {{ timeZone: "Asia/Dhaka" }}));
            const currentMins = bdDate.getHours() * 60 + bdDate.getMinutes();
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

    # বাংলাদেশ টাইমজোনে রিয়েল-টাইম ক্যালকুলেশন
    now = get_dhaka_now()
    today_str = now.strftime('%Y-%m-%d')
    now_time_str = now.strftime('%I:%M %p')
    current_minute = now.hour * 60 + now.minute

    OFFICE_START = 10 * 60          # সকাল ১০:০০
    LUNCH_START_LIMIT = 13 * 60 + 15 # দুপুর ১:১৫
    LUNCH_END_LIMIT = 14 * 60 + 15   # দুপুর ২:১৫
    OFFICE_EXIT = 18 * 60 + 30       # সন্ধ্যা ৬:৩০

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