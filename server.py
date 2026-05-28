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
    # Μετατρέπουμε την τρέχουσα ώρα σε λεπτά από την έναρξη της ημέρας (00:00) για εύκολη σύγκριση
    current_minutes = now.hour * 60 + now.minute
    
    # Ορισμός των χρονικών ορίων με βάση το screenshot (σε λεπτά)
    # Αν ο χρήστης είναι στο διάλειμμα, του δίνουμε την ώρα που έρχεται!
    if 0 <= current_minutes <= 9 * 60:            # Μέχρι τις 09:00 (Καλύπτει 1η ώρα & το 1ο διάλειμμα)
        return "1η"
    elif 9 * 60 < current_minutes <= 9 * 60 + 50:  # 09:01 έως 09:50 (2η ώρα)
        return "2η"
    elif 9 * 60 + 50 < current_minutes <= 10 * 60 + 45: # 09:51 έως 10:45 (Διάλειμμα + 3η ώρα)
        return "3η"
    elif 10 * 60 + 45 < current_minutes <= 11 * 60 + 40: # 10:46 έως 11:40 (Διάλειμμα + 4η ώρα)
        return "4η"
    elif 11 * 60 + 40 < current_minutes <= 12 * 60 + 35: # 11:41 έως 12:35 (Διάλειμμα + 5η ώρα)
        return "5η"
    elif 12 * 60 + 35 < current_minutes <= 13 * 60 + 25: # 12:36 έως 13:25 (Διάλειμμα + 6η ώρα)
        return "6η"
    elif 13 * 60 + 25 < current_minutes <= 14 * 60 + 10: # 13:26 έως 14:10 (Διάλειμμα + 7η ώρα)
        return "7η"
    else:
        return "MANUAL" # Εκτός ωραρίου (π.χ. απόγευμα), ενεργοποιείται η χειροκίνητη επιλογή

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
    username = data.get('username')
    password = data.get('password')
    
    if username in ACTIVE_SESSIONS:
        return jsonify({"status": "error", "message": "Αυτός ο λογαριασμός είναι ήδη συνδεδεμένος σε άλλη συσκευή!"})
    
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, password)).fetchone()
    conn.close()
    
    if user:
        ACTIVE_SESSIONS[username] = True
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
    
    # Υπολογίζουμε την αυτόματη ώρα
    auto_hour = get_current_school_hour()
    
    return render_template('dashboard.html', username=session['username'], classes=classes, locked=LOCKED_CLASSES, auto_hour=auto_hour)

@app.route('/select-class', methods=['POST'])
def select_class():
    if 'username' not in session:
        return jsonify({"status": "error", "message": "Μη εξουσιοδοτημένος χρήστης"}), 401
        
    data = request.json
    class_name = data.get('class_name')
    hour = data.get('hour') # Μπορεί να έρθει από το αυτόματο ή το χειροκίνητο μενού
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
# ΝΕΟ ΜΟΝΟΠΑΤΙ: Επιστροφή στο Dashboard ξεκλειδώνοντας μόνο το τμήμα
@app.route('/back-to-dashboard')
def back_to_dashboard():
    current_user = session.get('username')
    # Ξεκλειδώνουμε μόνο το τμήμα που είχε κρατήσει ο συγκεκριμένος χρήστης
    if current_user:
        to_remove = [k for k, v in LOCKED_CLASSES.items() if v == current_user]
        for k in to_remove:
            del LOCKED_CLASSES[k]
            
    # Στέλνουμε τον καθηγητή πίσω στο Dashboard (όχι στο Login!)
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
    student_ids = data.get('student_ids', []) # Δεχόμαστε πλέον λίστα από IDs (π.χ. [3, 5])
    hour = session.get('current_hour', '1η')
    
    # Αν η λίστα είναι άδεια (δηλαδή όλοι ήταν παρόντες)
    if not student_ids:
        return jsonify({"status": "success", "message": "Δεν σημειώθηκαν απουσίες. Ο έλεγχος ολοκληρώθηκε!"})

    conn = get_db_connection()
    success_count = 0
    
    # Στέλνουμε email μόνο για τους μαθητές που είναι στη λίστα των απόντων
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
    # Η Python διαβάζει τα στοιχεία σου κρυφά από το αρχείο .env
    sender_email = os.getenv("EMAIL_USER")
    sender_password = os.getenv("EMAIL_PASS")
    
    # Αν για κάποιο λόγο δεν βρει το αρχείο, εμφανίζει προειδοποίηση
    if not sender_email or not sender_password:
        print("Σφάλμα: Δεν βρέθηκαν τα στοιχεία EMAIL_USER ή EMAIL_PASS στο αρχείο .env")
        return False

    subject = f"Ενημέρωση Απουσίας - {hour} Ώρα"
    body = f"Αγαπητέ κηδεμόνα,\n\nΣας ενημερώνουμε ότι ο/η μαθητής/τρια {student_name} σημειώθηκε ως απών/ούσα την {hour} διδακτική ώρα."
    
    # Δημιουργία του μηνύματος με υποστήριξη Ελληνικών
    msg = MIMEText(body, _charset='utf-8')
    msg['Subject'] = subject
    msg['From'] = sender_email
    msg['To'] = to_email
    
    try:
        # Ασφαλής σύνδεση με την Google
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, to_email, msg.as_string())
        print(f"Το email για τον μαθητή {student_name} στάλθηκε επιτυχώς μέσω .env!")
        return True
    except Exception as e:
        print(f"Σφάλμα κατά την αποστολή του email: {e}")
        return False