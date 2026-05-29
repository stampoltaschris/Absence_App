import sqlite3
import os

def reset_database():
    db_path = 'database.db'
    
    # Έλεγχος αν υπάρχει το αρχείο της βάσης
    if not os.path.exists(db_path):
        print(f"❌ Σφάλμα: Το αρχείο '{db_path}' δεν βρέθηκε στον φάκελο!")
        return

    try:
        # Σύνδεση στη βάση δεδομένων
        conn = sqlite3.connect(db_path)
        
        # Διαγραφή όλων των εγγραφών από τον πίνακα των υποβολών
        conn.execute('DELETE FROM submitted_attendance')
        
        # Οριστικοποίηση αλλαγών
        conn.commit()
        conn.close()
        
        print("=" * 60)
        print(" 🟢 Η ΒΑΣΗ ΕΠΑΝΗΛΘΕ ΕΠΙΤΥΧΩΣ ΣΤΗΝ ΑΡΧΙΚΗ ΤΗΣ ΚΑΤΑΣΤΑΣΗ! ")
        print(" Όλα τα τμήματα είναι πάλι διαθέσιμα για όλους τους καθηγητές. ")
        print("=" * 60)
        
    except sqlite3.OperationalError as e:
        print(f"❌ Σφάλμα SQLite: {e}")
        print("Πιθανόν ο πίνακας 'submitted_attendance' δεν έχει δημιουργηθεί ακόμα.")
    except Exception as e:
        print(f"❌ Προέκυψε ένα άγνωστο σφάλμα: {e}")

if __name__ == "__main__":
    reset_database()