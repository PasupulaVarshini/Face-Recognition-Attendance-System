
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


def recognize_uploaded_face(image_bytes):

    model_path = os.path.join(ENCODINGS_FOLDER, "face_model.yml")
    mapping_path = os.path.join(ENCODINGS_FOLDER, "student_mapping.npy")

    if not os.path.exists(model_path) or not os.path.exists(mapping_path):
        return None

    recognizer = cv2.face.LBPHFaceRecognizer_create()
    recognizer.read(model_path)

    student_mapping = np.load(
        mapping_path,
        allow_pickle=True
    ).item()

    image_array = np.frombuffer(image_bytes, np.uint8)
    frame = cv2.imdecode(image_array, cv2.IMREAD_COLOR)

    if frame is None:
        return None

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    face_detector = cv2.CascadeClassifier(
        cv2.data.haarcascades +
        "haarcascade_frontalface_default.xml"
    )

    detected_faces = face_detector.detectMultiScale(
        gray,
        scaleFactor=1.1,
        minNeighbors=5,
        minSize=(60, 60)
    )

    if len(detected_faces) != 1:
        return None

    x, y, w, h = detected_faces[0]

    face_region = gray[y:y+h, x:x+w]
    face_region = cv2.resize(face_region, (200, 200))

    label, confidence = recognizer.predict(face_region)

    if confidence < 80 and label in student_mapping:
        return student_mapping[label]

    return None

def recognize_uploaded_face_with_details(image_bytes):

    model_path = os.path.join(ENCODINGS_FOLDER, "face_model.yml")
    mapping_path = os.path.join(ENCODINGS_FOLDER, "student_mapping.npy")

    if not os.path.exists(model_path) or not os.path.exists(mapping_path):
        return {
            "recognized": False,
            "message": "Face recognition model not found."
        }

    recognizer = cv2.face.LBPHFaceRecognizer_create()
    recognizer.read(model_path)

    student_mapping = np.load(
        mapping_path,
        allow_pickle=True
    ).item()

    image_array = np.frombuffer(image_bytes, np.uint8)
    frame = cv2.imdecode(image_array, cv2.IMREAD_COLOR)

    if frame is None:
        return {
            "recognized": False,
            "message": "Invalid camera image."
        }

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    face_detector = cv2.CascadeClassifier(
        cv2.data.haarcascades +
        "haarcascade_frontalface_default.xml"
    )

    detected_faces = face_detector.detectMultiScale(
        gray,
        scaleFactor=1.1,
        minNeighbors=5,
        minSize=(60, 60)
    )

    if len(detected_faces) == 0:
        return {
            "recognized": False,
            "message": "No face detected."
        }

    if len(detected_faces) > 1:
        return {
            "recognized": False,
            "message": "Multiple faces detected. Only one person should be in the frame."
        }

    x, y, w, h = detected_faces[0]

    face_region = gray[y:y+h, x:x+w]
    face_region = cv2.resize(face_region, (200, 200))

    label, confidence = recognizer.predict(face_region)

    if confidence < 80 and label in student_mapping:

        student = student_mapping[label]

        return {
            "recognized": True,
            "student_id": student["student_id"],
            "name": student["name"],
            "box": [int(x), int(y), int(w), int(h)]
        }

    return {
        "recognized": False,
        "message": "Unknown face detected.",
        "box": [int(x), int(y), int(w), int(h)]
    }


def train_face_model():

    connection = get_connection()

    students = connection.execute(
        "SELECT student_id, name, face_image FROM students"
    ).fetchall()

    connection.close()

    face_detector = cv2.CascadeClassifier(
        cv2.data.haarcascades +
        "haarcascade_frontalface_default.xml"
    )

    faces = []
    labels = []
    student_mapping = {}

    dataset_folder = os.path.join(BASE_DIR, "dataset")
    os.makedirs(ENCODINGS_FOLDER, exist_ok=True)

    label_id = 0

    for student in students:

        image_path = os.path.join(
            dataset_folder,
            student["face_image"]
        )

        if not os.path.exists(image_path):
            continue

        image = cv2.imread(image_path)

        if image is None:
            continue

        gray = cv2.cvtColor(
            image,
            cv2.COLOR_BGR2GRAY
        )

        detected_faces = face_detector.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(60, 60)
        )

        if len(detected_faces) == 0:
            continue

        x, y, w, h = max(
            detected_faces,
            key=lambda face: face[2] * face[3]
        )

        face_region = gray[y:y+h, x:x+w]

        face_region = cv2.resize(
            face_region,
            (200, 200)
        )

        faces.append(face_region)
        labels.append(label_id)

        student_mapping[label_id] = {
            "student_id": student["student_id"],
            "name": student["name"]
        }

        label_id += 1

    if not faces:
        return False

    recognizer = cv2.face.LBPHFaceRecognizer_create()

    recognizer.train(
        faces,
        np.array(labels, dtype=np.int32)
    )

    recognizer.write(
        os.path.join(ENCODINGS_FOLDER, "face_model.yml")
    )

    np.save(
        os.path.join(ENCODINGS_FOLDER, "student_mapping.npy"),
        student_mapping
    )

    print("Face recognition model trained successfully!")

    return True


if __name__ == "__main__":
    recognize_faces()
