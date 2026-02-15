import cv2
import numpy as np
import time
from ultralytics import YOLO
import os

cascade_path = os.path.join(os.path.dirname(__file__), "models", "haarcascade_frontalface_default.xml")

class VisionNode:
    def __init__(self):
        print("Loading AI model ...")
        self.model = YOLO("yolov8n.pt")
        self.face_cascade = cv2.CascadeClassifier(cascade_path)

        self.last_seen_time = 0
        self.person_present = False
        self.greet_cooldown = 10
        print("vision ready.")
        if self.face_cascade.empty():
            print("face cascade failed to load")   # fixed typo
        else:
            print("face detector loaded")

    def detect_faces(self, frame, annotated):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(gray, 1.3, 5)

        for (x, y, w, h) in faces:
            cv2.rectangle(annotated, (x, y), (x + w, y + h), (255, 0, 0), 2)
            cv2.putText(annotated, "Face", (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)

        return len(faces)

    def person_interaction_logic(self, person_detected):
        current_time = time.time()

        if person_detected and not self.person_present:
            if current_time - self.last_seen_time > self.greet_cooldown:
                print("👋 Human detected: Hello Kaustubh!")
                self.last_seen_time = current_time

        if not person_detected and self.person_present:
            print("😴 Human left. Going idle.")

        self.person_present = person_detected

    def free_space_navigation(self, frame, annotated):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)

        roi = edges[300:480, :]
        left = np.sum(roi[:, :213])
        centre = np.sum(roi[:, 213:426])
        right = np.sum(roi[:, 426:])

        if centre < left and centre < right:
            decision = "FORWARD"
        elif left < right:
            decision = "LEFT"
        else:
            decision = "RIGHT"

        cv2.putText(annotated, "Nav: " + decision, (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

    def process(self, frame):
        results = self.model(frame, verbose=False)
        annotated = results[0].plot()

        person_detected = False
        for box in results[0].boxes:
            cls = int(box.cls[0])
            if self.model.names[cls] == "person":
                person_detected = True

        face_count = self.detect_faces(frame, annotated)

        if face_count > 0:
            person_detected = True

        self.person_interaction_logic(person_detected)

        self.free_space_navigation(frame, annotated)

        status = "Human present" if person_detected else "IDLE"
        color = (0, 255, 0) if person_detected else (0, 0, 255)

        cv2.putText(annotated, status, (10, 120), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)

        return annotated