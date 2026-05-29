import time
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import sqlite3
import smtplib
import os
from email.mime.text import MIMEText
from datetime import datetime

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

# =========================================================================
# ΣΥΝΑΡΤΗΣΗ ΑΥΤΟΜΑΤΟΥ ΥΠΟΛΟΓΙΣΜΟΥ ΔΙΔΑΚΤΙΚΗΣ ΩΡΑΣ (Διορθωμένα όρια)
# =========================================================================
def get_current_school_hour():
    now = datetime.now().time()
    current_time_str = now.strftime("%H:%M")
    
    # 1η Ώρα (08:15 - 09:00)
    if "08:15" <= current_time_str < "09:00":
        return "1η"
    # 1ο Διάλειμμα (09:00 - 09:10)
    elif "09:00" <= current_time_str < "09:10":
        return "Διάλειμμα"
        
    # 2η Ώρα (09:10 - 09:55)
    elif "09:10" <= current_time_str < "09:55":
        return "2η"
    # 2ο Διάλειμμα (09:55 - 10:05)
    elif "09:55" <= current_time_str < "10:05":
        return "Διάλειμμα"
        
    # 3η Ώρα (10:05 - 10:50)
    elif "10:05" <= current_time_str < "10:50":
        return "3η"
    # 3ο Διάλειμμα (10:50 - 11:00)
    elif "10:50" <= current_time_str < "11:00":
        return "Διάλειμμα"
        
    # 4η Ώρα (11:00 - 11:45)
    elif "11:00" <= current_time_str < "11:45":
        return "4η"
    # 4ο Διάλειμμα (11:45 - 11:55)
    elif "11:45" <= current_time_str < "11:55":
        return "Διάλειμμα"
        
    # 5η Ώρα (11:55 - 12:40)
    elif "11:55" <= current_time_str < "12:40":
        return "5η"
    # 5ο Διάλειμμα (12:40 - 12:50)
    elif "12:40" <= current_time_str < "12:50":
        return "Διάλειμμα"
        
    # 6η Ώρα (12:50 - 13:35)
    elif "12:50" <= current_time_str < "13:35":
        return "6η"
    # 6ο Διάλειμμα (13:35 - 13:40)
    elif "13:35" <= current_time_str < "13:40":
        return "Διάλειμμα"
        
    # 7η Ώρα (13:40 - 14:25)
    elif "13:40" <= current_time_str < "14:25":
        return "7η"
        
    else:
        return "Εκτός Ωραρίου"

def get_db_connection():
    conn = sqlite3.connect('database.db', timeout=20)
    conn.row_factory = sqlite3.Row
    return conn

# =========================================================================
# ROUTES ΓΙΑ LOGIN (GET και POST με διαφορετικά ονόματα συναρτήσεων!)
# =========================================================================
@app.route('/')
@app.route('/login', methods=['GET'])
def show_login():
    auto_hour = get_current_school_hour()
    return render_template('login.html', auto_hour=auto_hour)

# 1. Εμφάνιση της σελίδας Admin
@app.route('/admin')
def admin_panel():
    return render_template('admin.html')

@app.route('/login', methods=['POST'])
def process_login():
    # 🌟 Έλεγχος Διαλείμματος
    auto_hour = get_current_school_hour()
    if auto_hour == "Διάλειμμα":
        return jsonify({"status": "error", "message": "Διάλειμμα! Η σύνδεση επιτρέπεται μόνο κατά τη διάρκεια των μαθημάτων."}), 403
        
    data = request.json
    if not data:
        return jsonify({"status": "error", "message": "Δεν ελήφθησαν δεδομένα JSON (Missing Content-Type)"}), 400
        
    username = data.get('username')
    password = data.get('password')
    
    if username in ACTIVE_SESSIONS:
        return jsonify({"status": "error", "message": "Αυτός ο λογαριασμός είναι ήδη συνδεδεμένος σε άλλη συσκευή!"})
    
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, password)).fetchone()
    conn.close()
    
    if user:
        ACTIVE_SESSIONS[username] = time.time()
        session['username'] = username
        return jsonify({"status": "success"})
    return jsonify({"status": "error", "message": "Λάθος username ή password"})

# =========================================================================
# ROUTE ΓΙΑ DASHBOARD (Καθαρισμένο και σωστά δομημένο)
# =========================================================================
@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('show_login'))
        
    auto_hour = get_current_school_hour()
    
    # 🌟 Αυτόματο Logout αν χτυπήσει κουδούνι για διάλειμμα
    if auto_hour == "Διάλειμμα":
        current_user = session.get('username')
        if current_user:
            to_remove = [k for k, v in LOCKED_CLASSES.items() if v == current_user]
            for k in to_remove:
                del LOCKED_CLASSES[k]
            if current_user in ACTIVE_SESSIONS:
                del ACTIVE_SESSIONS[current_user]
        session.clear()
        return render_template('login.html', auto_hour=auto_hour, error="Το μάθημα τελείωσε. Έγινε αυτόματη αποσύνδεση λόγω διαλείμματος.")

    # Κανονική ροή μαθήματος
    current_user = session.get('username')
    conn = get_db_connection()
    classes = conn.execute('SELECT * FROM classes').fetchall()

    submitted_classes = []
    has_submitted = False
    
    if auto_hour != "Εκτός Ωραρίου":
        current_date = datetime.now().strftime('%Y-%m-%d')
        
        done_rows = conn.execute(
            'SELECT class_name FROM submitted_attendance WHERE school_hour = ? AND date = ?',
            (auto_hour, current_date)
        ).fetchall()
        submitted_classes = [row['class_name'] for row in done_rows]
        
        teacher_check = conn.execute(
            'SELECT id FROM submitted_attendance WHERE school_hour = ? AND date = ? AND username = ?',
            (auto_hour, current_date, current_user)
        ).fetchone()
        has_submitted = True if teacher_check else False
        
    conn.close()
    
    return render_template(
        'dashboard.html', 
        username=current_user, 
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
    current_user = session['username']
    
    if class_name in LOCKED_CLASSES and LOCKED_CLASSES[class_name] != current_user:
        return jsonify({"status": "error", "message": f"Το τμήμα {class_name} είναι ήδη κατειλημμένο από τον χρήστη {LOCKED_CLASSES[class_name]}!"})
    
    LOCKED_CLASSES[class_name] = current_user
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
    if current_user:
        to_remove = [k for k, v in LOCKED_CLASSES.items() if v == current_user]
        for k in to_remove:
            del LOCKED_CLASSES[k]
        if current_user in ACTIVE_SESSIONS:
            del ACTIVE_SESSIONS[current_user]
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

    # Μόνιμο κλείδωμα
    try:
        current_date = datetime.now().strftime('%Y-%m-%d')
        current_hour = get_current_school_hour()
        current_user = session.get('username')
        
        conn.execute(
            'INSERT INTO submitted_attendance (class_name, school_hour, date, username) VALUES (?, ?, ?, ?)',
            (class_name, current_hour, current_date, current_user)
        )
        conn.commit()
        
        to_remove = [k for k, v in LOCKED_CLASSES.items() if v == current_user]
        for k in to_remove:
            del LOCKED_CLASSES[k]
            
        session.pop('current_class', None)
        session.pop('current_hour', None)
        
    except Exception as e:
        conn.close()
        return jsonify({"status": "error", "message": "Οι απουσίες στάλθηκαν αλλά απέτυχε το κλείδωμα"}), 500

    conn.close()
    return jsonify({"status": "success", "message": f"Η υποβολή ολοκληρώθηκε! Στάλθηκαν {success_count} email."})

# Βοηθητική συνάρτηση (αν χρειάζεται αλλού)
def send_email(student_name, to_email, hour):
    sender_email = os.getenv("EMAIL_USER")
    sender_password = os.getenv("EMAIL_PASS")
    if not sender_email or not sender_password:
        return False
    subject = f"Ενημέρωση Απουσίας - {hour} Ώρα"
    body = f"Αγαπητέ κηδεμόνα,\n\nΣας ενημερώνουμε ότι ο/η μαθητής/τρια {student_name} σημειώθηκε ως απών/ούσα την {hour} διδακτική ώρα."
    msg = MIMEText(body, _charset='utf-8')
    msg['Subject'] = subject
    msg['From'] = sender_email
    msg['To'] = to_email
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, to_email, msg.as_string())
        return True
    except:
        return False


# 2. Ταυτοποίηση Διαχειριστή (Login)
@app.route('/admin-login', methods=['POST'])
def admin_login_process():
    data = request.json
    password = data.get('password')
    
    if password == ADMIN_PASSWORD:
        session['is_admin'] = True
        return jsonify({"status": "success"})
    return jsonify({"status": "error", "message": "Λάθος κωδικός πρόσβασης διαχειριστή!"})

# 3. Αυτόματη Δημιουργία Τμήματος στη Βάση Δεδομένων
@app.route('/admin/add-class', methods=['POST'])
def admin_add_class():
    # Ασφάλεια: Έλεγχος αν είναι όντως συνδεδεμένος ως admin
    if not session.get('is_admin'):
        return jsonify({"status": "error", "message": "Μη εξουσιοδοτημένη πρόσβαση"}), 403
        
    data = request.json
    class_name = data.get('class_name', '').strip().upper() # Μετατροπή σε κεφαλαία (π.χ. α1 -> Α1)
    
    if not class_name:
        return jsonify({"status": "error", "message": "Το όνομα τμήματος δεν μπορεί να είναι κενό"}), 400
        
    conn = get_db_connection()
    try:
        # Έλεγχος αν το τμήμα υπάρχει ήδη στη βάση
        existing = conn.execute('SELECT id FROM classes WHERE name = ?', (class_name,)).fetchone()
        if existing:
            conn.close()
            return jsonify({"status": "error", "message": "Αυτό το τμήμα υπάρχει ήδη στη βάση δεδομένων!"})
            
        # Αυτόματο INSERT στον πίνακα classes
        conn.execute('INSERT INTO classes (name) VALUES (?)', (class_name,))
        conn.commit()
        conn.close()
        
        print(f"📦 Ο Admin δημιούργησε επιτυχώς το νέο τμήμα: {class_name}")
        return jsonify({"status": "success"})
        
    except Exception as e:
        conn.close()
        return jsonify({"status": "error", "message": f"Σφάλμα βάσης δεδομένων: {str(e)}"}), 500



if __name__ == '__main__':
    conn = sqlite3.connect('database.db')
    # 🌟 ΔΙΟΡΘΩΘΗΚΕ: Προστέθηκε η στήλη username TEXT στο CREATE TABLE
    conn.execute('''
        CREATE TABLE IF NOT EXISTS submitted_attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_name TEXT,
            school_hour TEXT,
            date TEXT,
            username TEXT
        )
    ''')
    conn.commit()
    conn.close()

    app.run(debug=True, host='0.0.0.0', port=5000)