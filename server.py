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
    conn = sqlite3.connect('database.db', timeout=20)
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
    # 🌟 ΝΕΟΣ ΕΛΕΓΧΟΣ: Βρίσκουμε ποια τμήματα έχουν ήδη υποβάλει για ΤΩΡΑ
    current_date = datetime.now().strftime('%Y-%m-%d')
    auto_hour = get_current_school_hour()
    
    done_rows = conn.execute(
        'SELECT class_name FROM submitted_attendance WHERE school_hour = ? AND date = ?',
        (auto_hour, current_date)
    ).fetchall()
    
    # Μετατρέπουμε τα αποτελέσματα σε μια απλή λίστα Python, π.χ. ['Α1', 'Β2']
    submitted_classes = [row['class_name'] for row in done_rows]
    conn.close()
    
    auto_hour = get_current_school_hour()
    
    return render_template('dashboard.html', username=session['username'], classes=classes, locked=LOCKED_CLASSES, auto_hour=auto_hour,submitted_classes=submitted_classes)

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
    # 🌟 Πλέον ΔΕΝ διαγράφουμε το τμήμα από το LOCKED_CLASSES.
    # Απλά επιστρέφουμε τον καθηγητή στο Dashboard.
    # Επειδή το session['current_class'] υπάρχει ακόμα, η HTML θα του κλειδώσει τα υπόλοιπα κουμπιά!
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
    # 1. Έλεγχος αν ο χρήστης είναι συνδεδεμένος
    if 'username' not in session:
        return jsonify({"status": "error", "message": "Μη εξουσιοδοτημένος χρήστης"}), 401
        
    data = request.json
    if not data:
        return jsonify({"status": "error", "message": "Δεν ελήφθησαν δεδομένα JSON"}), 400
        
    student_ids = data.get('student_ids', []) # Λίστα με τα ID των απόντων (π.χ. [3, 5])
    hour = session.get('current_hour', '1η')
    class_name = session.get('current_class')
    
    # Αν για κάποιο λόγο χάθηκε το session του τμήματος
    if not class_name:
        return jsonify({"status": "error", "message": "Δεν βρέθηκε ενεργό τμήμα στο session"}), 400

    # Διαβάζουμε τα στοιχεία email από το αρχείο .env
    sender_email = os.getenv("EMAIL_USER")
    sender_password = os.getenv("EMAIL_PASS")
    
    if not sender_email or not sender_password:
        print("Σφάλμα: Δεν βρέθηκαν τα στοιχεία EMAIL_USER ή EMAIL_PASS στο αρχείο .env")
        return jsonify({"status": "error", "message": "Σφάλμα παραμετροποίησης Email στο διακομιστή"}), 500

    conn = get_db_connection()
    success_count = 0
    
    # ----------------------------------------------------------------------
    # ΛΟΓΙΚΗ ΑΠΟΣΤΟΛΗΣ EMAIL (Βελτιστοποιημένη για ταυτόχρονη χρήση/τάμπλετ)
    # ----------------------------------------------------------------------
    if student_ids:
        try:
            # Ανοίγουμε τη σύνδεση με την Google ΜΙΑ ΦΟΡΑ πριν το loop
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                server.login(sender_email, sender_password)
                
                # Loop μόνο για τους μαθητές που είναι στη λίστα των απόντων
                for s_id in student_ids:
                    student = conn.execute('SELECT * FROM students WHERE id = ?', (s_id,)).fetchone()
                    if student and student['email']:
                        subject = f"Ενημέρωση Απουσίας - {hour} Ώρα"
                        body = f"Αγαπητέ κηδεμόνα,\n\nΣας ενημερώνουμε ότι ο/η μαθητής/τρια {student['name']} σημειώθηκε ως απών/ούσα την {hour} διδακτική ώρα."
                        
                        # Δημιουργία μηνύματος
                        msg = MIMEText(body, _charset='utf-8')
                        msg['Subject'] = subject
                        msg['From'] = sender_email
                        msg['To'] = student['email']
                        
                        # Αποστολή
                        server.sendmail(sender_email, student['email'], msg.as_string())
                        success_count += 1
                        print(f"Το email για τον μαθητή {student['name']} στάλθηκε επιτυχώς!")
                        
        except Exception as e:
            print(f"Σφάλμα κατά την ομαδική αποστολή email: {e}")
            conn.close()
            return jsonify({"status": "error", "message": f"Αποτυχία αποστολής email: {str(e)}"}), 500

    # ----------------------------------------------------------------------
    # ΛΟΓΙΚΗ ΜΟΝΙΜΟΥ ΚΛΕΙΔΩΜΑΤΟΣ ΤΜΗΜΑΤΟΣ ΓΙΑ ΤΗ ΣΥΓΚΕΚΡΙΜΕΝΗ ΩΡΑ
    # ----------------------------------------------------------------------
    try:
        current_date = datetime.now().strftime('%Y-%m-%d')
        current_hour = get_current_school_hour() # Παίρνουμε την πραγματική ώρα συστήματος
        
        # Εισάγουμε την εγγραφή στον πίνακα για να ξέρει το Dashboard ότι το τμήμα τελείωσε
        conn.execute(
            'INSERT INTO submitted_attendance (class_name, school_hour, date) VALUES (?, ?, ?)',
            (class_name, current_hour, current_date)
        )
        conn.commit()
        
        # Ξεκλειδώνουμε το τμήμα από τη live λίστα LOCKED_CLASSES, αφού ο καθηγητής ολοκλήρωσε
        current_user = session.get('username')
        to_remove = [k for k, v in LOCKED_CLASSES.items() if v == current_user]
        for k in to_remove:
            del LOCKED_CLASSES[k]
            
        # Καθαρίζουμε τις πληροφορίες του τμήματος από το session του συγκεκριμένου καθηγητή
        session.pop('current_class', None)
        session.pop('current_hour', None)
        
    except Exception as e:
        print(f"Σφάλμα κατά το κλείδωμα της ώρας στη βάση: {e}")
        conn.close()
        return jsonify({"status": "error", "message": "Οι απουσίες στάλθηκαν αλλά απέτυχε το κλείδωμα της ώρας στη βάση"}), 500

    conn.close()
    
    # Επιστροφή επιτυχίας στην JavaScript
    return jsonify({
        "status": "success", 
        "message": f"Η υποβολή ολοκληρώθηκε! Στάλθηκαν {success_count} email απουσίας και το τμήμα {class_name} κλείδωσε για την {current_hour} ώρα."
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

    conn = sqlite3.connect('database.db')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS submitted_attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_name TEXT,
            school_hour TEXT,
            date TEXT
        )
    ''')
    conn.commit()
    conn.close()

    app.run(debug=True, host='0.0.0.0', port=5000)