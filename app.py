
from flask import Flask, render_template, request, Response
from database import get_connection, create_table
from face_processing import recognize_uploaded_face, recognize_uploaded_face_with_details, train_face_model
import os
from flask import jsonify
import base64
import uuid
import sqlite3
import csv
import io

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

        image_path = None

        try:
            if not face_image.startswith("data:image/jpeg;base64,"):
                raise ValueError("Invalid image format")

            image_data = face_image.split(",", 1)[1]

            if len(image_data) > 5 * 1024 * 1024:
                raise ValueError("Image is too large")

            image_bytes = base64.b64decode(
                image_data,
                validate=True
            )

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

            try:
                train_face_model()
            except Exception:
                app.logger.exception("Face model training failed")

            return render_template(
                "register.html",
                message="Student registered successfully!"
            )

        except sqlite3.IntegrityError:
            if image_path and os.path.exists(image_path):
                os.remove(image_path)

            return render_template(
                "register.html",
                message="Student ID already exists!"
            )

        except (ValueError, base64.binascii.Error):
            if image_path and os.path.exists(image_path):
                os.remove(image_path)

            return render_template(
                "register.html",
                message="Invalid face image. Please capture again."
            )

        except Exception:
            app.logger.exception("Student registration failed")

            if image_path and os.path.exists(image_path):
                os.remove(image_path)

            return render_template(
                "register.html",
                message="Registration failed. Please try again."
            )

    return render_template("register.html")


@app.route("/mark-attendance-page")
def mark_attendance_page():
    return render_template("mark_attendance.html")


@app.route('/api/recognize-face', methods=['POST'])
def recognize_face_api():

    try:
        data = request.get_json()

        if not data or 'face_image' not in data:
            return jsonify({
                "recognized": False,
                "message": "Camera image is missing."
            }), 400

        image_data = data['face_image']

        if ',' in image_data:
            image_data = image_data.split(',', 1)[1]

        image_bytes = base64.b64decode(image_data)

        result = recognize_uploaded_face_with_details(image_bytes)

        return jsonify(result)

    except Exception as error:
        print("Live recognition error:", error)

        return jsonify({
            "recognized": False,
            "message": "Face recognition failed."
        }), 500

@app.route("/api/mark-attendance", methods=["POST"])
def mark_attendance_api():

    data = request.get_json(silent=True)

    if not data:
        return {
            "success": False,
            "message": "Invalid request."
        }, 400

    student_id = data.get("student_id", "").strip()
    face_image = data.get("face_image", "")

    if not student_id or not face_image:
        return {
            "success": False,
            "message": "Student ID and face image are required."
        }, 400

    try:
        if not face_image.startswith("data:image/jpeg;base64,"):
            return {
                "success": False,
                "message": "Invalid image format."
            }, 400

        image_data = face_image.split(",", 1)[1]
        image_bytes = base64.b64decode(
            image_data,
            validate=True
        )

        if len(image_bytes) > 5 * 1024 * 1024:
            return {
                "success": False,
                "message": "Image is too large."
            }, 400

        student = recognize_uploaded_face(image_bytes)

        if not student:
            return {
                "success": False,
                "message": "Face not recognized. Please try again."
            }, 401

        if student["student_id"] != student_id:
            return {
                "success": False,
                "message": "Face does not match the entered Student ID."
            }, 401

        connection = get_connection()

        try:
            connection.execute(
                """
                INSERT INTO attendance
                (student_id, attendance_date, attendance_time, status)
                VALUES (?, DATE('now', 'localtime'),
                        TIME('now', 'localtime'), 'Present')
                """,
                (student_id,)
            )

            connection.commit()

        except sqlite3.IntegrityError:
            return {
                "success": False,
                "message": "Attendance already marked for today."
            }, 409

        finally:
            connection.close()

        return {
            "success": True,
            "message": f"Attendance marked successfully for {student['name']}!"
        }

    except (ValueError, base64.binascii.Error):
        return {
            "success": False,
            "message": "Invalid face image."
        }, 400

    except Exception:
        app.logger.exception("Attendance marking failed")

        return {
            "success": False,
            "message": "Unable to mark attendance."
        }, 500


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
