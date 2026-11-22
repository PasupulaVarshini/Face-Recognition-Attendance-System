
import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "instance", "attendance.db")

def get_connection():
    os.makedirs(os.path.dirname(DATABASE), exist_ok=True)
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection

def create_table():
    connection = get_connection()

    connection.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            face_image TEXT NOT NULL,
            registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            attendance_date TEXT NOT NULL DEFAULT (DATE('now','localtime')),
            attendance_time TEXT NOT NULL DEFAULT (TIME('now','localtime')),
            status TEXT NOT NULL DEFAULT 'Present',
            UNIQUE(student_id, attendance_date),
            FOREIGN KEY (student_id) REFERENCES students(student_id)
        )
    """)

    connection.commit()
    connection.close()

if __name__ == "__main__":
    create_table()
    print("Database tables created successfully!")
