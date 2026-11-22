
import cv2
import os
import numpy as np
from datetime import datetime
from database import get_connection

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENCODINGS_FOLDER = os.path.join(BASE_DIR, "encodings")

def mark_attendance(student_id):

    connection = get_connection()

    today = datetime.now().strftime("%Y-%m-%d")
    current_time = datetime.now().strftime("%H:%M:%S")

    try:
        connection.execute(
            """
            INSERT INTO attendance
            (student_id, attendance_date, attendance_time, status)
            VALUES (?, ?, ?, 'Present')
            """,
            (student_id, today, current_time)
        )

        connection.commit()
        print(f"Attendance marked for {student_id}")

        return True

    except Exception as error:
        if "UNIQUE constraint failed" in str(error):
            print(f"Attendance already marked for {student_id} today")
        else:
            print("Attendance error:", error)

        return False

    finally:
        connection.close()


def recognize_faces():

    model_path = os.path.join(ENCODINGS_FOLDER, "face_model.yml")
    mapping_path = os.path.join(ENCODINGS_FOLDER, "student_mapping.npy")

    recognizer = cv2.face.LBPHFaceRecognizer_create()
    recognizer.read(model_path)

    student_mapping = np.load(
        mapping_path,
        allow_pickle=True
    ).item()

    face_detector = cv2.CascadeClassifier(
        cv2.data.haarcascades +
        "haarcascade_frontalface_default.xml"
    )

    camera = cv2.VideoCapture(0)

    if not camera.isOpened():
        print("Unable to open camera")
        return

    marked_students = set()

    print("Automatic Attendance System Started")
    print("Press Q to exit")

    while True:

        success, frame = camera.read()

        if not success:
            print("Unable to read camera")
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        detected_faces = face_detector.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(60, 60)
        )

        for (x, y, w, h) in detected_faces:

            face_region = gray[y:y+h, x:x+w]
            face_region = cv2.resize(face_region, (200, 200))

            label, confidence = recognizer.predict(face_region)

            if confidence < 80 and label in student_mapping:

                student = student_mapping[label]
                student_id = student["student_id"]
                student_name = student["name"]

                if student_id not in marked_students:
                    mark_attendance(student_id)
                    marked_students.add(student_id)

                display_text = student_name
                color = (0, 255, 0)

            else:
                display_text = "Unknown"
                color = (0, 0, 255)

            cv2.rectangle(
                frame, (x, y), (x+w, y+h), color, 2
            )

            cv2.putText(
                frame,
                display_text,
                (x, y-10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                color,
                2
            )

        cv2.imshow("Automatic Attendance System", frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    camera.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    recognize_faces()
