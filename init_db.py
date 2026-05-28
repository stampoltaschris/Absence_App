import sqlite3
import os
from werkzeug.security import generate_password_hash

basedir = os.path.abspath(os.path.dirname(__file__))

def create_database():
    conn = sqlite3.connect(os.path.join(basedir, 'database.db'))
    cursor = conn.cursor()

    # Ενεργοποίηση περιορισμών ξένου κλειδιού
    cursor.execute('PRAGMA foreign_keys = ON;')

    # 1. Πίνακας Χρηστών (Καθηγητών)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    )''')

    # 2. Πίνακας Τμημάτων
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS classes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL
    )''')

    # 3. Πίνακας Μαθητών
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT NOT NULL,
        class_id INTEGER,
        FOREIGN KEY(class_id) REFERENCES classes(id)
    )''')

    # Εισαγωγή 2 Χρηστών με κρυπτογραφημένους κωδικούς
    cursor.executemany('INSERT OR REPLACE INTO users (username, password) VALUES (?, ?)', [
        ('teacher1', generate_password_hash('12345')),
        ('teacher2', generate_password_hash('abcde'))
    ])

    # Εισαγωγή 6 Τμημάτων
    departments = ['Α1', 'Α2', 'Β1', 'Β2', 'Γ1', 'Γ2']
    for dept in departments:
        cursor.execute('INSERT OR IGNORE INTO classes (name) VALUES (?)', (dept,))

    # Εισαγωγή 5 μαθητών ανά τμήμα (Σύνολο 30 μαθητές)
    cursor.execute('SELECT id, name FROM classes')
    classes_from_db = cursor.fetchall()

    cursor.execute('DELETE FROM students') # Καθαρισμός για αποφυγή διπλότυπων
    for class_id, class_name in classes_from_db:
        for i in range(1, 6):
            student_name = f"Μαθητής {i} ({class_name})"
            cursor.execute('INSERT INTO students (name, email, class_id) VALUES (?, ?, ?)', 
                           (student_name, 'aeppsta@gmail.com', class_id))

    conn.commit()
    conn.close()
    print("Η βάση δεδομένων δημιουργήθηκε και γεμίστηκε με επιτυχία!")

if __name__ == '__main__':
    create_database()