import cv2
import numpy as np
import time
from ultralytics import YOLO
import os
from collections import deque

cascade_path = os.path.join(os.path.dirname(__file__), "models", "haarcascade_frontalface_default.xml")

class VisionNode:
    def __init__(self):
        print("Loading AI vision models...")
        self.model = YOLO("yolov8n.pt")
        self.face_cascade = cv2.CascadeClassifier(cascade_path)
        
        # Person detection smoothing
        self.person_history = deque(maxlen=8)  # Last 8 frames for stability
        self.person_confirmed = False
        self.person_confirmed_threshold = 5    # Need 5/8 frames to confirm
        
        # Attention tracking
        self.attention_frames = 0
        self.looking_history = deque(maxlen=10)
        
        # Memory
        self.last_seen_time = 0
        self.person_present = False
        self.greet_cooldown = 10
        
        print("Vision ready.")
        if self.face_cascade.empty():
            print("Face cascade failed to load")
        else:
            print("Face detector loaded")

    def detect_faces(self, frame, annotated):
        """Enhanced face detection with attention tracking"""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(gray, 1.3, 5, minSize=(50, 50))
        
        face_data = []
        frame_center = frame.shape[1] // 2
        
        for (x, y, w, h) in faces:
            # Draw rectangle
            cv2.rectangle(annotated, (x, y), (x + w, y + h), (255, 100, 100), 2)
            
            # Calculate if looking at camera
            face_center = x + w//2
            looking_at_camera = abs(face_center - frame_center) < 120
            
            # Add to history
            self.looking_history.append(1 if looking_at_camera else 0)
            
            # Calculate average looking over recent frames
            avg_looking = sum(self.looking_history) / len(self.looking_history) if self.looking_history else 0
            sustained_looking = avg_looking > 0.6  # Looking most of the time
            
            face_data.append({
                'position': (x, y, w, h),
                'looking_at_camera': looking_at_camera,
                'sustained_looking': sustained_looking,
                'confidence': 0.9
            })
            
            # Add label with looking indicator
            if sustained_looking:
                label = "👀 LOOKING"
                color = (0, 255, 255)
            elif looking_at_camera:
                label = "looking"
                color = (200, 200, 0)
            else:
                label = "face"
                color = (255, 100, 100)
                
            cv2.putText(annotated, label, (x, y - 10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        
        return face_data

    def analyze_scene(self, frame):
        """Main scene analysis - returns annotated frame and vision data"""
        # YOLO detection
        results = self.model(frame, verbose=False)
        annotated = results[0].plot()
        
        # Check for person in YOLO
        yolo_person = False
        for box in results[0].boxes:
            if int(box.cls[0]) == 0:  # person class
                yolo_person = True
                break
        
        # Face detection
        faces = self.detect_faces(frame, annotated)
        face_person = len(faces) > 0
        
        # Smooth person detection (avoid flicker)
        person_now = yolo_person or face_person
        self.person_history.append(person_now)
        
        # Confirm person only after threshold
        if sum(self.person_history) >= self.person_confirmed_threshold:
            if not self.person_confirmed:
                self.person_confirmed = True
                print("👤 Person confirmed present")
            person_detected = True
        else:
            if self.person_confirmed:
                self.person_confirmed = False
                print("👤 Person left")
            person_detected = False
        
        # Update attention time (only when person confirmed)
        someone_looking = any(face.get('sustained_looking', False) for face in faces) if person_detected else False
        
        if person_detected and someone_looking:
            self.attention_frames += 1
        else:
            self.attention_frames = max(0, self.attention_frames - 1)
        
        attention_time = self.attention_frames / 10  # Approx seconds at 10fps
        
        # Track person presence changes for greeting logic
        if person_detected and not self.person_present:
            self.last_seen_time = time.time()
        self.person_present = person_detected
        
        # Build scene description
        scene_parts = []
        if faces:
            looking_count = sum(1 for face in faces if face.get('sustained_looking', False))
            if looking_count > 0:
                scene_parts.append(f"{looking_count} person(s) looking at me")
            else:
                scene_parts.append(f"{len(faces)} face(s) visible")
        
        # Add objects from YOLO (excluding people)
        objects = []
        for box in results[0].boxes:
            cls = int(box.cls[0])
            name = self.model.names[cls]
            if name != 'person':
                objects.append(name)
        
        if objects:
            # Count unique objects
            from collections import Counter
            obj_counts = Counter(objects)
            obj_desc = [f"{count} {name}{'s' if count>1 else ''}" 
                       for name, count in obj_counts.most_common(3)]
            scene_parts.append("I see " + ", ".join(obj_desc))
        
        scene_description = ". ".join(scene_parts) if scene_parts else "Nothing specific"
        
        # Add status to frame
        status = "PERSON PRESENT" if person_detected else "NO PERSON"
        status_color = (0, 255, 0) if person_detected else (0, 0, 255)
        cv2.putText(annotated, status, (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.6, status_color, 2)
        
        if someone_looking:
            cv2.putText(annotated, "👀 ATTENTION", (10, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        
        return annotated, {
            'person_present': person_detected,
            'someone_looking': someone_looking,
            'attention_time': attention_time,
            'scene_description': scene_description,
            'face_count': len(faces),
            'looking_count': sum(1 for face in faces if face.get('sustained_looking', False)),
            'objects_detected': objects[:5]
        }

    def process(self, frame):
        """Main entry point - returns annotated frame and vision data"""
        return self.analyze_scene(frame)