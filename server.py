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

# ΣΥΝΑΡΤΗΣΗ ΑΥΤΟΜΑΤΟΥ ΥΠΟΛΟΓΙΣΜΟΥ ΔΙΔΑΚΤΙΚΗΣ ΩΡΑΣ
def get_current_school_hour():
    now = datetime.now()
    current_minutes = now.hour * 60 + now.minute
    
    if 0 <= current_minutes <= 9 * 60:            
        return "1η"
    elif 9 * 60 < current_minutes <= 9 * 60 + 50:  
        return "2η"
    elif 9 * 60 + 50 < current_minutes <= 10 * 60 + 45: 
        return "3η"
    elif 10 * 60 + 45 < current_minutes <= 11 * 60 + 40: 
        return "4η"
    elif 11 * 60 + 40 < current_minutes <= 12 * 60 + 35: 
        return "5η"
    elif 12 * 60 + 35 < current_minutes <= 13 * 60 + 25: 
        return "6η"
    elif 13 * 60 + 25 < current_minutes <= 14 * 60 + 10: 
        return "7η"
    else:
        return "MANUAL" 

def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    if 'username' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
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
        ACTIVE_SESSIONS[username] =   time.time()
        session['username'] = username
        return jsonify({"status": "success"})
    return jsonify({"status": "error", "message": "Λάθος username ή password"})

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('index'))
        
    conn = get_db_connection()
    classes = conn.execute('SELECT * FROM classes').fetchall()
    conn.close()
    
    auto_hour = get_current_school_hour()
    
    return render_template('dashboard.html', username=session['username'], classes=classes, locked=LOCKED_CLASSES, auto_hour=auto_hour)

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
        return redirect(url_for('index'))
        
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

# 🌟 ΔΙΟΡΘΩΘΗΚΕ: Αφαιρέθηκε το "a" που έσπαγε το compile
@app.route('/back-to-dashboard')
def back_to_dashboard():
    current_user = session.get('username')
    if current_user:
        to_remove = [k for k, v in LOCKED_CLASSES.items() if v == current_user]
        for k in to_remove:
            del LOCKED_CLASSES[k]
            
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
    return redirect(url_for('index'))

@app.route('/send-absence', methods=['POST'])
def send_absence():
    if 'username' not in session:
        return jsonify({"status": "error", "message": "Μη εξουσιοδοτημένος χρήστης"}), 401
        
    data = request.json
    if not data:
        return jsonify({"status": "error", "message": "Missing JSON data"}), 400
        
    student_ids = data.get('student_ids', []) 
    hour = session.get('current_hour', '1η')
    
    if not student_ids:
        return jsonify({"status": "success", "message": "Δεν σημειώθηκαν απουσίες. Ο έλεγχος ολοκληρώθηκε!"})

    conn = get_db_connection()
    success_count = 0
    
    for s_id in student_ids:
        student = conn.execute('SELECT * FROM students WHERE id = ?', (s_id,)).fetchone()
        if student:
            email_status = send_email(student['name'], student['email'], hour)
            if email_status:
                success_count += 1
                
    conn.close()
    
    return jsonify({
        "status": "success", 
        "message": f"Η υποβολή ολοκληρώθηκε! Στάλθηκαν {success_count} email απουσίας."
    })

def send_email(student_name, to_email, hour):
    sender_email = os.getenv("EMAIL_USER")
    sender_password = os.getenv("EMAIL_PASS")
    
    if not sender_email or not sender_password:
        print("Σφάλμα: Δεν βρέθηκαν τα στοιχεία EMAIL_USER ή EMAIL_PASS στο αρχείο .env")
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
        print(f"Το email για τον μαθητή {student_name} στάλθηκε επιτυχώς!")
        return True
    except Exception as e:
        print(f"Σφάλμα κατά την αποστολή του email: {e}")
        return False

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)