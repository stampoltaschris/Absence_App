import time
from flask import Flask, render_template, request, jsonify, send_from_directory, session, redirect, url_for
import sqlite3
import smtplib
import os
import re
from email.mime.text import MIMEText
from datetime import datetime
from openpyxl import load_workbook

try:
    from dotenv import load_dotenv
    load_dotenv()
    USING_DOTENV = True
except ImportError:
    USING_DOTENV = False

app = Flask(__name__)
app.secret_key = 'super_secret_key_for_sessions'

LOCKED_CLASSES = {}
ACTIVE_SESSIONS = {}
ADMIN_PASSWORD = "12345" 

@app.route('/manifest.json')
def serve_manifest():
    return app.send_static_file('manifest.json') if os.path.exists('static/manifest.json') else send_from_directory('.', 'manifest.json')

@app.route('/service-worker.js')
def serve_sw():
    return send_from_directory('.', 'service-worker.js')

# =========================================================================
# ΣΥΝΑΡΤΗΣΗ ΑΥΤΟΜΑΤΟΥ ΥΠΟΛΟΓΙΣΜΟΥ ΔΙΔΑΚΤΙΚΗΣ ΩΡΑΣ
# =========================================================================
def get_current_school_hour():
    now = datetime.now().time()
    current_time_str = now.strftime("%H:%M")
    
    # 1η Ώρα (08:15 - 09:00)
    if "08:15" <= current_time_str < "09:00":
        return "1η"
    # 1ο Διάλειμμα (09:00 - 09:10)
    elif "09:00" <= current_time_str < "09:05":
        return "Διάλειμμα"
        
    # 2η Ώρα (09:10 - 09:55)
    elif "09:05" <= current_time_str < "09:50":
        return "2η"
    # 2ο Διάλειμμα (09:55 - 10:05)
    elif "09:50" <= current_time_str < "10:00":
        return "Διάλειμμα"
        
    # 3η Ώρα (10:05 - 10:50)
    elif "10:00" <= current_time_str < "10:45":
        return "3η"
    # 3ο Διάλειμμα (10:50 - 11:00)
    elif "10:45" <= current_time_str < "10:55":
        return "Διάλειμμα"
        
    # 4η Ώρα (11:00 - 11:45)
    elif "10:55" <= current_time_str < "11:40":
        return "4η"
    # 4ο Διάλειμμα (11:45 - 11:55)
    elif "11:40" <= current_time_str < "11:50":
        return "Διάλειμμα"
        
    # 5η Ώρα (11:55 - 12:40)
    elif "11:50" <= current_time_str < "12:35":
        return "5η"
    # 5ο Διάλειμμα (12:40 - 12:50)
    elif "12:35" <= current_time_str < "12:45":
        return "Διάλειμμα"
        
    # 6η Ώρα (12:50 - 13:35)
    elif "12:45" <= current_time_str < "13:25":
        return "6η"
    # 6ο Διάλειμμα (13:35 - 13:40)
    elif "13:25" <= current_time_str < "13:30":
        return "Διάλειμμα"
        
    # 7η Ώρα (13:40 - 14:25)
    elif "13:30" <= current_time_str < "14:10":
        return "7η"
        
    else:
        return "Εκτός Ωραρίου"

def get_db_connection():
    conn = sqlite3.connect('database.db', timeout=20)
    conn.row_factory = sqlite3.Row
    return conn

# =========================================================================
# ROUTES ΔΙΑΧΕΙΡΙΣΤΗ (ADMIN)
# =========================================================================
@app.route('/')
@app.route('/login', methods=['GET'])
def show_login():
    auto_hour = get_current_school_hour()
    return render_template('login.html', auto_hour=auto_hour)

@app.route('/admin/monitor')
def admin_monitor_page():
    if not session.get('is_admin'):
        return "Μη εξουσιοδοτημένη πρόσβαση", 403
    return render_template('admin_monitor.html')

# 🎯 ΔΙΟΡΘΩΜΕΝΟ: Προσθήκη του API που καλεί το live monitor
@app.route('/admin/api/monitor-status')
def get_live_status_api():
    if not session.get('is_admin'):
        return jsonify({"error": "Unauthorized"}), 403
    return jsonify({
        "active_sessions": ACTIVE_SESSIONS,
        "locked_classes": LOCKED_CLASSES
    })

# 🎯 ΔΙΟΡΘΩΜΕΝΟ: Αναγκαστική αποσύνδεση εκπαιδευτικού από Admin
@app.route('/admin/api/kick-teacher', methods=['POST'])
def kick_teacher():
    if not session.get('is_admin'):
        return jsonify({"status": "error", "message": "Unauthorized"}), 403
    data = request.json
    target_user = data.get('username', '').strip().lower()
    
    if target_user in ACTIVE_SESSIONS:
        del ACTIVE_SESSIONS[target_user]
    
    to_remove = [k for k, v in LOCKED_CLASSES.items() if v == target_user]
    for k in to_remove:
        del LOCKED_CLASSES[k]
        
    return jsonify({"status": "success"})

# 🎯 ΔΙΟΡΘΩΜΕΝΟ: Αναγκαστικό ξεκλείδωμα τμήματος από Admin
@app.route('/admin/api/unlock-class', methods=['POST'])
def unlock_class_admin():
    if not session.get('is_admin'):
        return jsonify({"status": "error", "message": "Unauthorized"}), 403
    data = request.json
    class_name = data.get('class_name')
    
    if class_name in LOCKED_CLASSES:
        del LOCKED_CLASSES[class_name]
        
    return jsonify({"status": "success"})

@app.route('/admin')
def admin_panel():
    # Διαβάζουμε αν ο χρήστης έχει συνδεθεί επιτυχώς (True ή False)
    logged_in = session.get('is_admin', False)
    
    # 🎯 ΠΕΡΝΑΜΕ ΤΗ ΜΕΤΑΒΛΗΤΗ ΜΕΣΑ ΣΤΟ TEMPLATE ΓΙΑ ΝΑ ΞΕΚΛΕΙΔΩΣΕΙ!
    return render_template('admin.html', is_admin=logged_in)

@app.route('/admin/add-teacher-page')
def admin_add_teacher_page():
    if not session.get('is_admin'):
        return "Μη εξουσιοδοτημένη πρόσβαση", 403
    return render_template('add_teacher.html')

@app.route('/admin/add-teacher', methods=['POST'])
def admin_add_teacher():
    if not session.get('is_admin'):
        return jsonify({"status": "error", "message": "Μη εξουσιοδοτημένη πρόσβαση"}), 403
        
    data = request.get_json()
    full_name = data.get('name', '').strip()
    username = data.get('username', '').strip().lower()
    password = data.get('password', '').strip()
    
    if not full_name or not username or not password:
        return jsonify({"status": "error", "message": "Όλα τα πεδία είναι υποχρεωτικά!"}), 400
        
    conn = get_db_connection()
    try:
        existing = conn.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
        if existing:
            conn.close()
            return jsonify({"status": "error", "message": "Το username χρησιμοποιείται ήδη!"})
            
        conn.execute('INSERT INTO users (name, username, password) VALUES (?, ?, ?)', 
                     (full_name, username, password))
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "message": f"Ο/Η εκπαιδευτικός {full_name} προστέθηκε με επιτυχία!"})
    except Exception as e:
        if conn: conn.close()
        return jsonify({"status": "error", "message": str(e)}), 500

# =========================================================================
# ΛΟΓΙΚΗ LOGIN ΕΚΠΑΙΔΕΥΤΙΚΟΥ
# =========================================================================
@app.route('/login', methods=['POST'])
def process_login():
    auto_hour = get_current_school_hour()
    if auto_hour == "Διάλειμμα":
        return jsonify({"status": "error", "message": "Διάλειμμα! Η σύνδεση επιτρέπεται μόνο κατά τη διάρκεια των μαθημάτων."}), 403
        
    data = request.json
    if not data:
        return jsonify({"status": "error", "message": "Δεν ελήφθησαν δεδομένα JSON (Missing Content-Type)"}), 400
        
    username = data.get('username', '').strip().lower()
    password = data.get('password', '').strip()
    
    if username in ACTIVE_SESSIONS:
        return jsonify({"status": "error", "message": "Αυτός ο λογαριασμός είναι ήδη συνδεδεμένος σε άλλη συσκευή!"})
    
    conn = get_db_connection()
    try:
        user = conn.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, password)).fetchone()
        
        if user:
            ACTIVE_SESSIONS[username] = time.time()
            session['username'] = user['name'] if user['name'] else username
            session['raw_username'] = username  # Κρατάμε το καθαρό username για τα locks
            conn.close()
            return jsonify({"status": "success"})
            
        conn.close()
        return jsonify({"status": "error", "message": "Λάθος username ή password"})
    except Exception as e:
        if conn: conn.close()
        return jsonify({"status": "error", "message": f"Σφάλμα βάσης: {str(e)}"}), 500

# =========================================================================
# ROUTE DASHBOARD (ΔΙΟΡΘΩΜΕΝΟ)
# =========================================================================

# 🎯 ΝΕΟ ΕΝDPOINT: Ελέγχει live αν ο καθηγητής έχει υποστεί kick
@app.route('/api/auth-check')
def auth_check():
    current_user = session.get('username')
    raw_user = session.get('raw_username', current_user)
    
    # Αν δεν είναι καν συνδεδεμένος ή αν ο Admin τον διέγραψε από τα ACTIVE_SESSIONS
    if not raw_user or raw_user not in ACTIVE_SESSIONS:
        session.clear() # Καθαρίζει το session ΤΟΥ ΚΑΘΗΓΗΤΗ
        return jsonify({"status": "kicked"})
        
    return jsonify({"status": "ok"})

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('show_login'))
        
    auto_hour = get_current_school_hour()
    current_user = session.get('username') 
    raw_user = session.get('raw_username', current_user) 

    # 🎯 ΝΕΟΣ ΕΛΕΓΧΟΣ KICK: Αν ο Admin σε διέγραψε από τα ACTIVE_SESSIONS, έφυγες!
    if raw_user not in ACTIVE_SESSIONS:
        session.clear()
        return redirect(url_for('show_login'))
    
    if auto_hour == "Διάλειμμα":
        to_remove = [k for k, v in LOCKED_CLASSES.items() if v == raw_user]
        for k in to_remove:
            del LOCKED_CLASSES[k]
        if raw_user in ACTIVE_SESSIONS:
            del ACTIVE_SESSIONS[raw_user]
        session.clear()
        return render_template('login.html', auto_hour=auto_hour, error="Το μάθημα τελείωσε. Έγινε automatic αποσύνδεση λόγω διαλείμματος.")

    conn = get_db_connection()
    classes = conn.execute('SELECT * FROM classes').fetchall()

    submitted_classes = []
    has_submitted = False
    
    if auto_hour != "Εκτός Ωραρίου":
        current_date = datetime.now().strftime('%Y-%m-%d')
        
        done_rows = conn.execute('SELECT class_name FROM submitted_attendance WHERE school_hour = ? AND date = ?',(auto_hour, current_date)).fetchall()
        submitted_classes = [row['class_name'] for row in done_rows]
        
        teacher_check = conn.execute(
            'SELECT id FROM submitted_attendance WHERE school_hour = ? AND date = ? AND username = ?',
            (auto_hour, current_date, raw_user)
        ).fetchone()
        has_submitted = True if teacher_check else False
        
    conn.close()
    
    return render_template(
        'dashboard.html', 
        username=current_user, 
        raw_username=raw_user,  # 🎯 Περνάμε το raw_username στο template
        classes=classes, 
        locked=LOCKED_CLASSES, 
        auto_hour=auto_hour,
        submitted_classes=submitted_classes,
        has_submitted=has_submitted
    )

@app.route('/select-class', methods=['POST'])
def select_class():
    if 'username' not in session:
        return jsonify({"status": "error", "message": "Μη εξουσιοδοτημένος χρήστης"}), 401
        
    data = request.json
    if not data:
        return jsonify({"status": "error", "message": "Missing JSON data"}), 400
        
    class_name = data.get('class_name')
    hour = data.get('hour') 
    raw_user = session.get('raw_username')
    
    # 🎯 ΔΙΟΡΘΩΣΗ: Έλεγχος κατάληψης με βάση το raw_user
    if class_name in LOCKED_CLASSES and LOCKED_CLASSES[class_name] != raw_user:
        return jsonify({"status": "error", "message": f"Το τμήμα {class_name} είναι ήδη κατειλημμένο!"})
    
    LOCKED_CLASSES[class_name] = raw_user
    session['current_class'] = class_name
    session['current_hour'] = hour
    
    return jsonify({"status": "success"})

@app.route('/attendance')
def attendance():
    if 'username' not in session or 'current_class' not in session:
        return redirect(url_for('show_login'))
        
    class_name = session['current_class']
    hour = session['current_hour']
    
    conn = get_db_connection()
    students = conn.execute('''
        SELECT students.id, students.name, students.email 
        FROM students 
        JOIN classes ON students.class_id = classes.id 
        WHERE classes.name = ?''', (class_name,)).fetchall()
    conn.close()
    
    return render_template('attendance.html', username=session['username'], students=students, class_name=class_name, hour=hour)

@app.route('/back-to-dashboard')
def back_to_dashboard():
    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    current_user = session.get('username')
    raw_user = session.get('raw_username', current_user)
    if raw_user:
        to_remove = [k for k, v in LOCKED_CLASSES.items() if v == raw_user]
        for k in to_remove:
            del LOCKED_CLASSES[k]
        if raw_user in ACTIVE_SESSIONS:
            del ACTIVE_SESSIONS[raw_user]
    session.clear()
    return redirect(url_for('show_login'))

@app.route('/send-absence', methods=['POST'])
def send_absence():
    if 'username' not in session:
        return jsonify({"status": "error", "message": "Μη εξουσιοδοτημένος χρήστης"}), 401
        
    data = request.json
    if not data:
        return jsonify({"status": "error", "message": "Δεν ελήφθησαν δεδομένα JSON"}), 400
        
    student_ids = data.get('student_ids', [])
    hour = session.get('current_hour', '1η')
    class_name = session.get('current_class')
    raw_user = session.get('raw_username')
    
    if not class_name:
        return jsonify({"status": "error", "message": "Δεν βρέθηκε ενεργό τμήμα στο session"}), 400

    sender_email = os.getenv("EMAIL_USER")
    sender_password = os.getenv("EMAIL_PASS")
    
    if not sender_email or not sender_password:
        return jsonify({"status": "error", "message": "Σφάλμα παραμετροποίησης Email στο διακομιστή"}), 500

    conn = get_db_connection()
    success_count = 0
    
    if student_ids:
        try:
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                server.login(sender_email, sender_password)
                for s_id in student_ids:
                    student = conn.execute('SELECT * FROM students WHERE id = ?', (s_id,)).fetchone()
                    if student and student['email']:
                        subject = f"Ενημέρωση Απουσίας - {hour} Ώρα"
                        body = f"Αγαπητέ κηδεμόνα,\n\nΣας ενημερώνουμε ότι ο/η μαθητής/τρια {student['name']} σημειώθηκε ως απών/ούσα την {hour} διδακτική ώρα."
                        
                        msg = MIMEText(body, _charset='utf-8')
                        msg['Subject'] = subject
                        msg['From'] = sender_email
                        msg['To'] = student['email']
                        
                        server.sendmail(sender_email, student['email'], msg.as_string())
                        success_count += 1
                        
        except Exception as e:
            conn.close()
            return jsonify({"status": "error", "message": f"Αποτυχία αποστολής email: {str(e)}"}), 500

    try:
        current_date = datetime.now().strftime('%Y-%m-%d')
        current_hour = get_current_school_hour()
        
        conn.execute(
            'INSERT INTO submitted_attendance (class_name, school_hour, date, username) VALUES (?, ?, ?, ?)',
            (class_name, current_hour, current_date, raw_user)
        )
        conn.commit()
        
        if class_name in LOCKED_CLASSES:
            del LOCKED_CLASSES[class_name]
            
        session.pop('current_class', None)
        session.pop('current_hour', None)
        
    except Exception as e:
        conn.close()
        return jsonify({"status": "error", "message": "Οι απουσίες στάλθηκαν αλλά απέτυχε το κλείδωμα"}), 500

    conn.close()
    return jsonify({"status": "success", "message": f"Η υποβολή ολοκληρώθηκε! Στάλθηκαν {success_count} email."})

@app.route('/admin-login', methods=['POST'])
def admin_login_process():
    data = request.json
    password = data.get('password')
    
    if password == ADMIN_PASSWORD:
        session['is_admin'] = True
        return jsonify({"status": "success"})
    return jsonify({"status": "error", "message": "Λάθος κωδικός πρόσβασης διαχειριστή!"})

# 🎯 ΝΕΟ ΣΥΜΒΑΤΟ ROUTE: Διαβάζει τον κωδικό από την κλασική φόρμα HTML και κάνει redirect
@app.route('/admin-login-direct', methods=['POST'])
def admin_login_direct():
    password = request.form.get('password') # Διαβάζει το input της φόρμας
    
    if password == ADMIN_PASSWORD:
        session['is_admin'] = True
        return redirect(url_for('admin_panel')) # Σε στέλνει «καρφωτό» μέσα στο ξεκλείδωτο /admin
        
    # Αν ο κωδικός είναι λάθος, επιστρέφει στην είσοδο
    return "Λάθος κωδικός πρόσβασης διαχειριστή! <a href='/admin'>Δοκιμάστε ξανά</a>"

# =========================================================================
# ΔΗΜΙΟΥΡΓΙΑ ΤΜΗΜΑΤΟΣ ΚΑΙ PARSING EXCEL
# =========================================================================
@app.route('/admin/add-class', methods=['POST'])
def admin_add_class():
    if not session.get('is_admin'):
        return jsonify({"status": "error", "message": "Μη εξουσιοδοτημένη πρόσβαση"}), 403
        
    class_name = request.form.get('class_name', '').strip().upper()
    excel_file = request.files.get('excel_file')
    # 🎯 ΔΙΚΛΕΙΔΑ ΑΣΦΑΛΕΙΑΣ: Αν για κάποιο λόγο περιέχει .XLSX ή .XLS, το αφαιρούμε κι εδώ
    class_name = class_name.replace('.XLSX', '').replace('.XLS', '').strip()
    
    if not class_name:
        return jsonify({"status": "error", "message": "Το όνομα τμήματος δεν μπορεί να είναι κενό"}), 400
        
    if not re.match(r'^[Α-Ω0-9]+$', class_name):
        return jsonify({"status": "error", "message": "Το όνομα πρέπει να περιέχει μόνο ελληνικά κεφαλαία και αριθμούς!"}), 400

    conn = get_db_connection()
    try:
        existing = conn.execute('SELECT id FROM classes WHERE name = ?', (class_name,)).fetchone()
        if existing:
            conn.close()
            return jsonify({"status": "error", "message": f"Το τμήμα {class_name} υπάρχει ήδη στη βάση!"})
            
        cursor = conn.cursor()
        cursor.execute('INSERT INTO classes (name) VALUES (?)', (class_name,))
        class_id = cursor.lastrowid
        
        students_added = 0
        
        if excel_file and excel_file.filename != '':
            wb = load_workbook(excel_file, data_only=True)
            sheet = wb.active
            
            for row in sheet.iter_rows(min_row=2, max_row=sheet.max_row, values_only=True):
                if not row or row[0] is None:
                    continue
                
                student_name = str(row[0]).strip()
                student_email = str(row[1]).strip() if len(row) > 1 and row[1] is not None else ""
                
                cursor.execute(
                    'INSERT INTO students (name, email, class_id) VALUES (?, ?, ?)',
                    (student_name, student_email, class_id)
                )
                students_added += 1
                
        conn.commit()
        conn.close()
        
        msg = f"Το τμήμα {class_name} δημιουργήθηκε!"
        if students_added > 0:
            msg += f" Εισήχθησαν επιτυχώς {students_added} μαθητές."
        return jsonify({"status": "success", "message": msg})
        
    except Exception as e:
        if conn: conn.close()
        return jsonify({"status": "error", "message": f"Σφάλμα κατά την επεξεργασία του Excel: {str(e)}"}), 500

# =========================================================================
# ΜΗΔΕΝΙΣΜΟΙ ΒΑΣΗΣ (RESETS)
# =========================================================================
@app.route('/admin/reset-attendance', methods=['POST'])
def admin_reset_attendance():
    if not session.get('is_admin'):
        return jsonify({"status": "error", "message": "Μη εξουσιοδοτημένη πρόσβαση"}), 403
        
    global LOCKED_CLASSES
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM submitted_attendance')
        cursor.execute("UPDATE sqlite_sequence SET seq = 0 WHERE name = 'submitted_attendance'")
        conn.commit()
        conn.close()
        LOCKED_CLASSES.clear()
        return jsonify({"status": "success", "message": "Οι απουσίες μηδενίστηκαν επιτυχώς!"})
    except Exception as e:
        if conn: conn.close()
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/admin/hard-reset', methods=['POST'])
def admin_hard_reset():
    if not session.get('is_admin'):
        return jsonify({"status": "error", "message": "Μη εξουσιοδοτημένη πρόσβαση"}), 403
        
    global LOCKED_CLASSES, ACTIVE_SESSIONS
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM submitted_attendance')
        cursor.execute('DELETE FROM students')
        cursor.execute('DELETE FROM classes')
        cursor.execute("UPDATE sqlite_sequence SET seq = 0 WHERE name IN ('submitted_attendance', 'students', 'classes')")
        conn.commit()
        conn.close()
        
        LOCKED_CLASSES.clear()
        ACTIVE_SESSIONS.clear()
        return jsonify({"status": "success", "message": "Η βάση μηδενίστηκε πλήρως (εκτός χρηστών)!"})
    except Exception as e:
        if conn: conn.close()
        return jsonify({"status": "error", "message": str(e)}), 500

# 🎯 ΔΙΚΛΕΙΔΑ ΑΣΦΑΛΕΙΑΣ: Απαγόρευση Cache για να μην κρατάει ο browser τη σελίδα του Admin μετά την έξοδο
@app.after_request
def add_header(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response
# =========================================================================
# INITIALIZATION ΚΑΙ RUN (ΔΙΟΡΘΩΜΕΝΟ)
# =========================================================================
if __name__ == '__main__':
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    
    # 1. Πίνακας Υποβολών
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS submitted_attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_name TEXT,
            school_hour TEXT,
            date TEXT,
            username TEXT
        )
    ''')
    
    # 2. Πίνακας Χρηστών/Εκπαιδευτικών (με τη στήλη name!)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            username TEXT UNIQUE,
            password TEXT
        )
    ''')
    
    # 3. 🎯 Πίνακας Τμημάτων (Αυτός που έλειπε!)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS classes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE
        )
    ''')
    
    # 4. 🎯 Πίνακας Μαθητών (Κι αυτός έλειπε!)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT,
            class_id INTEGER,
            FOREIGN KEY(class_id) REFERENCES classes(id)
        )
    ''')
    
    conn.commit()
    conn.close()

    app.run(debug=True, host='0.0.0.0', port=5000)