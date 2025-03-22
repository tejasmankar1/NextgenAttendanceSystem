import cv2
import dlib
import os
import numpy as np
from database import Database

class FaceRecognition:
    def __init__(self, db_path):
        self.detector = dlib.get_frontal_face_detector()
        self.predictor = dlib.shape_predictor("models/shape_predictor_68_face_landmarks.dat")
        self.encoder = dlib.face_recognition_model_v1("models/dlib_face_recognition_resnet_model_v1.dat")
        self.db = Database(db_path)

    def capture_faces(self):
        cap = cv2.VideoCapture(0)
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # Detect faces
            faces = self.detector(frame)
            for i, face in enumerate(faces):
                # Extract features and save to database
                face_image = frame[face.top():face.bottom(), face.left():face.right()]
                face_id = f"face_{i}.jpg"
                cv2.imwrite(os.path.join('captured_faces', face_id), face_image)

                # Encode and store face data in the database
                shape = self.predictor(frame, face)
                face_encoding = np.array(self.encoder.compute_face_descriptor(frame, shape)).tolist()
                self.db.add_face("Student Name", "USN", "Year", "Branch", face_id, face_encoding)  # Replace with actual data

            cv2.imshow('Face Capture', frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        cap.release()
        cv2.destroyAllWindows()

    def recognize_faces(self):
        # Add recognition logic here if needed
        pass
