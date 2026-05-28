import sqlite3

def create_database():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

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

    # Εισαγωγή 2 Χρηστών (Για απλότητα, οι κωδικοί είναι σε απλό κείμενο προς το παρόν)
    cursor.executemany('INSERT OR IGNORE INTO users (username, password) VALUES (?, ?)', [
        ('teacher1', '12345'),
        ('teacher2', 'abcde')
    ])

    # Εισαγωγή 6 Τμημάτων
    departments = ['Α1', 'Α2', 'Β1', 'Β2', 'Γ1', 'Γ2']
    for dept in departments:
        cursor.execute('INSERT OR IGNORE INTO classes (name) VALUES (?)', (dept,))

    # Εισαγωγή 5 μαθητών ανά τμήμα (Σύνολο 30 μαθητές)
    cursor.execute('SELECT id, name FROM classes')
    classes_from_db = cursor.fetchall()

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