
from flask import Flask, render_template, request
from database import get_connection, create_table
import os
import base64
import uuid
import sqlite3
import csv
import io
from flask import Flask, render_template, request, Response

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_FOLDER = os.path.join(BASE_DIR, "dataset")

os.makedirs(DATASET_FOLDER, exist_ok=True)

create_table()


@app.route("/")
def home():

    connection = get_connection()

    total_students = connection.execute(
        "SELECT COUNT(*) FROM students"
    ).fetchone()[0]

    today_present = connection.execute(
        """
        SELECT COUNT(*)
        FROM attendance
        WHERE attendance_date = DATE('now', 'localtime')
        AND status = 'Present'
        """
    ).fetchone()[0]

    total_attendance = connection.execute(
        "SELECT COUNT(*) FROM attendance"
    ).fetchone()[0]

    absent_today = max(total_students - today_present, 0)

    if total_students > 0:
        attendance_rate = round(
            (today_present / total_students) * 100, 2
        )
    else:
        attendance_rate = 0

    recent_records = connection.execute("""
        SELECT
            students.student_id,
            students.name,
            attendance.attendance_date,
            attendance.attendance_time,
            attendance.status
        FROM attendance
        JOIN students
        ON attendance.student_id = students.student_id
        ORDER BY attendance.attendance_date DESC,
                 attendance.attendance_time DESC
        LIMIT 5
    """).fetchall()

    connection.close()

    return render_template(
        "index.html",
        total_students=total_students,
        today_present=today_present,
        total_attendance=total_attendance,
        absent_today=absent_today,
        attendance_rate=attendance_rate,
        recent_records=recent_records
    )


@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        student_id = request.form.get("student_id", "").strip()
        name = request.form.get("student_name", "").strip()
        email = request.form.get("email", "").strip()
        face_image = request.form.get("face_image", "")

        if not student_id or not name or not email or not face_image:
            return render_template(
                "register.html",
                message="Please complete all fields and capture your face."
            )

        try:
            if not face_image.startswith("data:image/jpeg;base64,"):
                raise ValueError("Invalid image format")

            image_data = face_image.split(",", 1)[1]

            if len(image_data) > 5 * 1024 * 1024:
                raise ValueError("Image is too large")

            image_bytes = base64.b64decode(image_data, validate=True)

            if not image_bytes.startswith(b"\xff\xd8"):
                raise ValueError("Invalid JPEG image")

            filename = f"{uuid.uuid4().hex}.jpg"
            image_path = os.path.join(DATASET_FOLDER, filename)

            with open(image_path, "wb") as image_file:
                image_file.write(image_bytes)

            connection = get_connection()

            try:
                connection.execute(
                    """
                    INSERT INTO students
                    (student_id, name, email, face_image)
                    VALUES (?, ?, ?, ?)
                    """,
                    (student_id, name, email, filename)
                )

                connection.commit()

            finally:
                connection.close()

            return render_template(
                "register.html",
                message="Student registered successfully!"
            )

        except sqlite3.IntegrityError:
            if "image_path" in locals() and os.path.exists(image_path):
                os.remove(image_path)

            return render_template(
                "register.html",
                message="Student ID already exists!"
            )

        except (ValueError, base64.binascii.Error):
            if "image_path" in locals() and os.path.exists(image_path):
                os.remove(image_path)

            return render_template(
                "register.html",
                message="Invalid face image. Please capture again."
            )

    return render_template("register.html")


@app.route("/attendance")
def attendance():

    connection = get_connection()

    records = connection.execute("""
        SELECT
            students.student_id,
            students.name,
            attendance.attendance_date,
            attendance.attendance_time,
            attendance.status
        FROM attendance
        JOIN students
        ON attendance.student_id = students.student_id
        ORDER BY attendance.attendance_date DESC,
                 attendance.attendance_time DESC
    """).fetchall()

    connection.close()

    return render_template(
        "attendance.html",
        records=records
    )


@app.route("/students")
def students():

    connection = get_connection()

    student_records = connection.execute("""
        SELECT student_id, name, email, registration_date
        FROM students
        ORDER BY registration_date DESC
    """).fetchall()

    total_students = len(student_records)

    connection.close()

    return render_template(
        "students.html",
        students=student_records,
        total_students=total_students
    )


@app.route("/admin")
def admin_dashboard():

    connection = get_connection()

    total_students = connection.execute(
        "SELECT COUNT(*) FROM students"
    ).fetchone()[0]

    total_attendance = connection.execute(
        "SELECT COUNT(*) FROM attendance"
    ).fetchone()[0]

    today_present = connection.execute(
        """
        SELECT COUNT(*)
        FROM attendance
        WHERE attendance_date = DATE('now', 'localtime')
        AND status = 'Present'
        """
    ).fetchone()[0]

    if total_students > 0:
        attendance_percentage = round(
            (today_present / total_students) * 100, 2
        )
    else:
        attendance_percentage = 0

    connection.close()

    return render_template(
        "admin.html",
        total_students=total_students,
        total_attendance=total_attendance,
        today_present=today_present,
        attendance_percentage=attendance_percentage
    )

@app.route("/export-attendance")
def export_attendance():

    connection = get_connection()

    records = connection.execute("""
        SELECT
            students.student_id,
            students.name,
            attendance.attendance_date,
            attendance.attendance_time,
            attendance.status
        FROM attendance
        JOIN students
        ON attendance.student_id = students.student_id
        ORDER BY attendance.attendance_date DESC,
                 attendance.attendance_time DESC
    """).fetchall()

    connection.close()

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "Student ID",
        "Student Name",
        "Attendance Date",
        "Attendance Time",
        "Status"
    ])

    for record in records:
        writer.writerow([
            record["student_id"],
            record["name"],
            record["attendance_date"],
            record["attendance_time"],
            record["status"]
        ])

    response = Response(
        "\ufeff" + output.getvalue(),
        mimetype="text/csv"
    )

    response.headers["Content-Disposition"] = (
        "attachment; filename=attendance_report.csv"
    )

    return response


if __name__ == "__main__":
    app.run(debug=True)
