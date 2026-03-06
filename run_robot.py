import cv2
import time
import threading
from datetime import datetime
import queue
import random
import numpy as np
from collections import deque
import socket
import requests  # Make sure this is imported

from robot_brain.audio.listener import SpeechListener
from robot_brain.audio.voice import RobotVoice
from robot_brain.core.llm_brain import LLMBrain
from robot_brain.camera.camera_stream import CameraStream
from robot_brain.vision.vision_node import VisionNode

def find_esp32_camera():
    """Find ESP32 camera on the network"""
    print("\n🔍 Scanning for ESP32 camera...")
    
    # Your ESP32's actual IP from the serial monitor
    correct_ip = "192.168.225.68"
    
    # CORRECT STREAM URL
    stream_url = f"http://{correct_ip}/stream"
    
    # Test the connection
    try:
        print(f"Testing connection to {stream_url}...")
        # Test with a quick stream request (we'll just check headers)
        response = requests.get(stream_url, timeout=2, stream=True)
        if response.status_code == 200:
            print(f"✅ ESP32 stream found at {stream_url}")
            return stream_url
    except requests.exceptions.ConnectionError:
        try:
            # Try alternative common ports
            alt_url = f"http://{correct_ip}:80/stream"
            response = requests.get(alt_url, timeout=2, stream=True)
            if response.status_code == 200:
                print(f"✅ ESP32 stream found at {alt_url}")
                return alt_url
        except:
            pass
    
    print(f"✅ Using ESP32 at {correct_ip}")
    return stream_url

# ========== ADVANCED FEATURES CLASS ==========
class AdvancedFeatures:
    def __init__(self, voice, brain, vision):
        self.voice = voice
        self.brain = brain
        self.vision = vision
        self.start_time = time.time()
        
        # Feature 1: Productivity Tracking
        self.productivity_score = 0
        self.last_productive_time = None
        self.break_reminder_interval = 45 * 60
        
        # Feature 2: Mood Detection & Adaptation
        self.user_mood_history = deque(maxlen=100)
        self.current_user_mood = "neutral"
        
        # Feature 3: Smart Scheduling (simulated)
        self.schedule = {}
        
        # Feature 4: Learning Mode
        self.learning_mode = False
        self.learned_commands = {}
        
        # Feature 5: Environmental Awareness
        self.light_level = 0.5
        self.noise_level = 0.0
        self.temperature = 22.0
        
        # Feature 6: Gesture Recognition (placeholder)
        self.gesture_queue = deque(maxlen=10)
        
        # Feature 7: Focus Assistant
        self.focus_mode = False
        self.distractions_blocked = 0
        
        # Feature 8: Health Reminders
        self.last_eye_break = time.time()
        self.last_posture_check = time.time()
        
        # Feature 9: Entertainment System
        self.joke_library = [
            "Why do programmers prefer dark mode? Because light attracts bugs!",
            "Why did the robot go back to school? To improve its memory!",
            "What's a computer's favorite beat? An algorithm!",
        ]
        self.fact_library = [
            "Did you know? The first computer bug was an actual moth found in a computer in 1947.",
            "The term 'robot' comes from the Czech word 'robota', meaning forced labor.",
            "The human brain can process images in just 13 milliseconds!"
        ]
        
        # Feature 10: News/Weather Updates (simulated)
        self.last_weather_check = 0
        self.weather_cache = None
        
        # Feature 11: Music Mood Matcher (placeholder)
        self.current_music_mood = None
        
        # Feature 12: Smart Alerts
        self.alert_thresholds = {
            'face_too_close': 0.3,
            'low_light': 0.2,
            'high_noise': 0.8
        }
        
        # Feature 13: Daily Briefing
        self.briefing_delivered = False
        
        # Feature 14: Conversation Mode
        self.conversation_depth = 0
        self.topic_history = deque(maxlen=20)
        
        # Feature 15: Emotion Mirroring
        self.emotion_mirror_enabled = True
        
        # Feature 16: Personalized Greetings
        self.user_preferences = {}
        
        # Feature 17: Activity Suggestions
        self.activity_suggestions = [
            "Time to stretch!",
            "Want to do a quick eye exercise?",
            "How about a 5-minute break?",
            "I can tell you a joke if you're bored!"
        ]
        
        # Feature 18: Ambient Interaction
        self.ambient_messages = [
            "*curiously looks around*",
            "*notices you working*",
            "*subtly adjusts position*",
            "*quietly observes*"
        ]
        self.last_ambient_time = 0
        self.ambient_interval = 10  # seconds between ambient messages
        
        # Feature 19: Learning Progress Tracker
        self.learning_progress = {}
        
        # Feature 20: Social Media Integration (simulated)
        self.social_feeds = []
        
        print("✨ 20 Advanced Features Initialized")

    def track_productivity(self, vision_data):
        if vision_data.get('person_present', False):
            gaze = vision_data.get('gaze_direction', 'unknown')
            if isinstance(gaze, str) and (gaze == 'screen' or gaze == 'forward'):
                self.productivity_score = min(100, self.productivity_score + 1)
                if not self.last_productive_time:
                    self.last_productive_time = time.time()
            else:
                self.productivity_score = max(0, self.productivity_score - 0.5)
        
        if self.last_productive_time:
            elapsed = time.time() - self.last_productive_time
            if elapsed > self.break_reminder_interval and not self.voice.is_speaking():
                self.voice.speak("You've been working hard. Time for a short break!")
                self.last_productive_time = time.time()
        return self.productivity_score

    def detect_user_mood(self, vision_data):
        face_expression = vision_data.get('face_expression', 'neutral')
        attention_time = vision_data.get('attention_time', 0)
        
        mood_map = {
            'happy': 'positive',
            'surprised': 'excited',
            'neutral': 'neutral',
            'sad': 'concerned',
            'angry': 'alert'
        }
        detected_mood = mood_map.get(face_expression, 'neutral')
        
        if attention_time > 5:
            self.user_mood_history.append(detected_mood)
            if len(self.user_mood_history) > 10:
                moods = list(self.user_mood_history)
                self.current_user_mood = max(set(moods), key=moods.count)
        return detected_mood

    def check_health_metrics(self, vision_data):
        current_time = time.time()
        if current_time - self.last_eye_break > 1200:
            if self.productivity_score > 50 and not self.voice.is_speaking():
                self.voice.speak("Remember to look away from the screen for 20 seconds.")
                self.last_eye_break = current_time
        
        if current_time - self.last_posture_check > 1800:
            face_pos = vision_data.get('face_position', None)
            if face_pos and len(face_pos) >= 2:
                if face_pos[1] > 0.7:
                    self.voice.speak("Check your posture! Sit up straight.")
            self.last_posture_check = current_time

    def provide_entertainment(self, mood):
        if mood in ['positive', 'excited']:
            joke = random.choice(self.joke_library)
            self.voice.speak(joke)
        elif mood in ['neutral', 'bored']:
            fact = random.choice(self.fact_library)
            self.voice.speak(fact)
        elif mood == 'concerned':
            comforts = [
                "Is everything okay? I'm here if you need to talk.",
                "You seem a bit down. Want to hear something uplifting?"
            ]
            self.voice.speak(random.choice(comforts))

    def check_environmental_alerts(self, vision_data):
        face_distance = vision_data.get('face_distance', 1.0)
        if face_distance < self.alert_thresholds['face_too_close']:
            if not self.voice.is_speaking():
                self.voice.speak("You're sitting too close to the screen. Please move back.")
        
        brightness = vision_data.get('brightness', 0.5)
        if brightness < self.alert_thresholds['low_light']:
            # Just a notification, not spoken to avoid spam
            pass

    def generate_daily_briefing(self, awake):
        if not awake:
            return
        current_hour = datetime.now().hour
        if current_hour < 12 and not self.briefing_delivered:
            briefing = f"Good morning! It's {datetime.now().strftime('%A, %B %d')}. "
            briefing += "Have a productive day!"
            self.voice.speak(briefing)
            self.briefing_delivered = True

    def mirror_emotion(self, user_mood):
        if not self.emotion_mirror_enabled:
            return 'curious'
        emotion_map = {
            'positive': 'happy',
            'excited': 'playful',
            'neutral': 'curious',
            'concerned': 'alert',
            'focused': 'focused'
        }
        return emotion_map.get(user_mood, 'curious')

    def suggest_activity(self):
        current_hour = datetime.now().hour
        prod = self.productivity_score
        if prod > 80 and current_hour > 14:
            return "You're on fire! Keep up the great work!"
        elif prod < 30 and current_hour > 10:
            return random.choice(self.activity_suggestions)
        elif current_hour > 17:
            return "Great work today! Time to wind down?"
        return None

    def ambient_interaction(self, vision_data):
        if not self.voice.is_speaking() and vision_data.get('person_present', False):
            now = time.time()
            if now - self.last_ambient_time > self.ambient_interval:
                if random.random() < 0.3:  # 30% chance after interval
                    ambient = random.choice(self.ambient_messages)
                    print(f"[Ambient] {ambient}")
                    self.last_ambient_time = now

    def track_learning(self, command, response):
        if command not in self.learning_progress:
            self.learning_progress[command] = {
                'count': 0,
                'last_response': None,
                'success_rate': 0
            }
        self.learning_progress[command]['count'] += 1
        self.learning_progress[command]['last_response'] = response
        if len(self.user_mood_history) > 0:
            recent = list(self.user_mood_history)[-5:]
            pos = sum(1 for m in recent if m in ['positive', 'excited'])
            self.learning_progress[command]['success_rate'] = pos / len(recent) if recent else 0

# ========== MAIN ROBOT CONTROLLER ==========
class AdvancedDeskCompanion:
    def __init__(self, esp32_url):
        print("\n" + "="*60)
        print(" INITIALIZING SHERU AI ADVANCED DESK COMPANION ")
        print("="*60 + "\n")
        
        # Initialize modules with ESP32 camera only
        print(f"📷 Connecting to ESP32 at: {esp32_url}")
        self.camera = CameraStream(esp32_url)
        self.vision = VisionNode()
        self.voice = RobotVoice()
        self.listener = SpeechListener()
        self.brain = LLMBrain()
        
        # Initialize advanced features
        self.features = AdvancedFeatures(self.voice, self.brain, self.vision)
        
        # Robot state
        self.state = {
            'awake': False,
            'mode': 'idle',
            'emotion': 'curious',
            'status': 'sleep',
            'battery': 100,
            'uptime': '00:00',
            'last_activity': datetime.now(),
            'current_user': 'default',
            'last_vision': None,
            'last_decision': None,
            'camera_connected': False,
            'camera_url': esp32_url
        }
        
        # Queues
        self.vision_queue = queue.Queue(maxsize=2)
        
        # Wake/sleep words
        self.wake_words = ("sheru", "shiru", "hey sheru","dog")
        self.sleep_words = ("sleep", "goodnight", "go to sleep")
        
        self.awake_timeout = 300
        self.greeting_cooldown = 20
        self.last_greeting = 0
        
        self.running = True
        
        print("✅ Core modules initialized")
        print("✨ Advanced features ready")
        print(f"📷 ESP32 Camera URL: {esp32_url}")
        print("🎯 System ready for launch\n")

    def contains_wake_word(self, text):
        if not text: return False
        t = text.lower()
        return any(w in t for w in self.wake_words)

    def contains_sleep_word(self, text):
        if not text: return False
        t = text.lower()
        return any(w in t for w in self.sleep_words)

    def wake_up(self):
        if self.state['awake']: return
        self.state['awake'] = True
        self.state['status'] = 'awake'
        self.state['mode'] = 'idle'
        self.state['emotion'] = 'happy'
        self.state['last_activity'] = datetime.now()
        
        hour = datetime.now().hour
        if hour < 12:
            greeting = "Good morning! I'm awake and ready to help!"
        elif hour < 18:
            greeting = "Good afternoon! I'm here to assist you!"
        else:
            greeting = "Good evening! Ready for our session!"
        
        self.voice.speak_and_wait(greeting, timeout=5)
        print("🤖 Robot awake")

    def go_to_sleep(self):
        if not self.state['awake']: return
        self.state['awake'] = False
        self.state['status'] = 'sleep'
        self.state['mode'] = 'sleep'
        self.state['emotion'] = 'sleepy'
        if not self.voice.is_speaking():
            self.voice.speak_and_wait("Going to sleep. Call me if you need me.", timeout=5)
        print("😴 Robot sleeping")

    def process_command(self, text):
        if not text or len(text.strip()) < 2:
            return
        self.state['last_activity'] = datetime.now()
        cmd = text.lower().strip()
        
        if self.contains_sleep_word(cmd):
            self.go_to_sleep()
            return
        
        print(f"🎯 Processing command: {text}")
        
        vision_data = self.state.get('last_vision', {
            'scene_description': 'Nothing visible',
            'person_present': False
        })
        
        decision = self.brain.get_contextual_response(
            vision_data,
            user_command=text,
            user_id=self.state['current_user']
        )
        
        if decision:
            self.state['mode'] = decision.get('mode', self.state['mode'])
            self.state['emotion'] = decision.get('emotion', self.state['emotion'])
            self.state['last_decision'] = decision
            
            self.features.track_learning(text, decision['message'])
            
            # Mirror emotion
            user_mood = self.features.current_user_mood
            self.state['emotion'] = self.features.mirror_emotion(user_mood)
            
            response = decision.get('message', "I understand.")
            self.voice.speak_and_wait(response, timeout=10)
        else:
            self.voice.speak_and_wait("I didn't catch that. Could you repeat?", timeout=5)

    def should_initiate_greeting(self, vision_data):
        if not self.state['awake']: return False
        if not vision_data.get('person_present', False): return False
        
        someone_looking = vision_data.get('someone_looking', False)
        attention_time = vision_data.get('attention_time', 0)
        current_time = time.time()
        
        if someone_looking and attention_time > 2.0:
            if current_time - self.last_greeting > self.greeting_cooldown:
                self.last_greeting = current_time
                return True
        return False

    def vision_thread_func(self):
        print("👁️ Vision thread started")
        connection_attempts = 0
        while self.running:
            try:
                frame = self.camera.get_frame()
                if frame is None:
                    connection_attempts += 1
                    if connection_attempts % 30 == 0:  # Print every ~30 attempts
                        print(f"⏳ Waiting for ESP32 camera stream... (attempt {connection_attempts})")
                    time.sleep(0.1)
                    continue
                
                # Optional: Rotate if needed (uncomment if image is upside down)
                # frame = cv2.rotate(frame, cv2.ROTATE_180)
                
                # Reset connection attempts on successful frame
                connection_attempts = 0
                
                # Update camera connection status
                self.state['camera_connected'] = self.camera.is_connected()
                
                annotated, vision_data = self.vision.process(frame)
                
                # Ensure gaze_direction is a string
                if 'gaze_direction' in vision_data and not isinstance(vision_data['gaze_direction'], str):
                    vision_data['gaze_direction'] = str(vision_data['gaze_direction'])
                
                self.state['last_vision'] = vision_data
                
                # Apply advanced features
                self.features.track_productivity(vision_data)
                user_mood = self.features.detect_user_mood(vision_data)
                self.features.check_health_metrics(vision_data)
                self.features.check_environmental_alerts(vision_data)
                self.features.ambient_interaction(vision_data)
                
                if self.vision_queue.qsize() < 2:
                    self.vision_queue.put((annotated, vision_data))
                
                if self.should_initiate_greeting(vision_data):
                    time_of_day = "morning" if datetime.now().hour < 12 else "afternoon" if datetime.now().hour < 18 else "evening"
                    greetings = [
                        f"Good {time_of_day}! I see you looking at me.",
                        f"Hello! How's your {time_of_day} going?",
                        "Hi there! Need any help?"
                    ]
                    self.voice.speak(random.choice(greetings))
                
                time.sleep(0.03)
            except Exception as e:
                print(f"Vision thread error: {e}")
                time.sleep(0.1)

    def speech_thread_func(self):
        print("🎤 Speech thread started")
        consecutive_silence = 0
        last_spoke_time = 0  # Track when robot last finished speaking
        
        while self.running:
            try:
                # If robot is speaking, wait
                if self.voice.is_speaking():
                    time.sleep(0.2)
                    continue
                
                # Add cooldown after speaking to avoid hearing own echo
                if time.time() - last_spoke_time < 1.0:
                    time.sleep(0.1)
                    continue
                
                if not self.state['awake']:
                    # Listen for wake word
                    text = self.listener.listen_once(listen_seconds=2)
                    if text:
                        print(f"[DEBUG] Heard while asleep: '{text}'")
                        if self.contains_wake_word(text):
                            print("✅ Wake word detected!")
                            self.wake_up()
                            last_spoke_time = time.time()  # After wake-up speech
                    continue
                
                idle = (datetime.now() - self.state['last_activity']).total_seconds()
                if idle > self.awake_timeout:
                    self.go_to_sleep()
                    continue
                
                text = self.listener.listen_once(listen_seconds=4)
                if text:
                    print(f"[DEBUG] Heard while awake: '{text}'")
                if not text or len(text.strip()) < 2:
                    consecutive_silence += 1
                    if consecutive_silence > 5:
                        time.sleep(0.2)
                    
                    # Ambient activity suggestion
                    if random.random() < 0.01 and self.state['last_vision']:
                        suggestion = self.features.suggest_activity()
                        if suggestion and not self.voice.is_speaking():
                            self.voice.speak(suggestion)
                            last_spoke_time = time.time()
                    continue
                
                consecutive_silence = 0
                self.process_command(text)
                last_spoke_time = time.time()  # After response
                
            except Exception as e:
                print(f"Speech thread error: {e}")
                time.sleep(0.1)

    def run_ui(self):
        print("📺 Starting UI (main thread)")
        cv2.namedWindow("SHERU AI Desk Companion - ESP32 Camera", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("SHERU AI Desk Companion - ESP32 Camera", 1024, 768)
        
        fps_time = time.time()
        frame_count = 0
        fps = 0
        start_time = time.time()
        
        # Ensure vision_queue exists
        if not hasattr(self, 'vision_queue') or self.vision_queue is None:
            self.vision_queue = queue.Queue(maxsize=2)
        
        while self.running:
            try:
                # Get latest frame
                frame = None
                vision_data = {}
                try:
                    if self.vision_queue is not None:
                        frame, vision_data = self.vision_queue.get(timeout=0.5)
                    else:
                        frame = self.camera.get_frame()
                except queue.Empty:
                    frame = self.camera.get_frame()
                    vision_data = self.state.get('last_vision', {})
                except Exception as e:
                    print(f"UI queue error: {e}")
                    frame = self.camera.get_frame()
                    vision_data = self.state.get('last_vision', {})
                
                if frame is None:
                    frame = np.zeros((480, 640, 3), dtype=np.uint8)
                    # Add connection instructions
                    cv2.putText(frame, "Connecting to ESP32 Camera...", (100, 200), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
                    cv2.putText(frame, f"URL: {self.state['camera_url']}", (100, 250),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
                    cv2.putText(frame, "Make sure ESP32 is powered on", (100, 300),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
                
                # FPS calculation
                frame_count += 1
                if frame_count >= 10:
                    fps = frame_count / (time.time() - fps_time)
                    fps_time = time.time()
                    frame_count = 0
                
                # Uptime
                uptime_sec = int(time.time() - start_time)
                hours = uptime_sec // 3600
                minutes = (uptime_sec % 3600) // 60
                self.state['uptime'] = f"{hours:02d}:{minutes:02d}"
                
                # Draw UI
                h, w = frame.shape[:2]
                
                # Semi-transparent overlay
                overlay = frame.copy()
                cv2.rectangle(overlay, (0, 0), (w, h), (20, 20, 30), -1)
                frame = cv2.addWeighted(frame, 0.7, overlay, 0.3, 0)
                
                # Top bar
                cv2.rectangle(frame, (0, 0), (w, 40), (30, 30, 50), -1)
                
                # Status
                status_color = (0, 255, 100) if self.state['awake'] else (100, 100, 255)
                status_text = "● AWAKE" if self.state['awake'] else "○ SLEEP"
                cv2.putText(frame, status_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, status_color, 2)
                
                # Camera connection status
                cam_color = (0, 255, 0) if self.state.get('camera_connected', False) else (0, 0, 255)
                cam_text = "📷 ESP32: CONNECTED" if self.state.get('camera_connected', False) else "📷 ESP32: DISCONNECTED"
                cv2.putText(frame, cam_text, (w-300, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, cam_color, 1)
                
                # Mode
                mode_text = f"MODE: {self.state['mode'].upper()}"
                cv2.putText(frame, mode_text, (150, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200,200,255), 1)
                
                # Emotion
                emotion_text = f"EMOTION: {self.state['emotion'].upper()}"
                cv2.putText(frame, emotion_text, (350, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200,255,200), 1)
                
                # FPS and uptime
                cv2.putText(frame, f"FPS: {int(fps)}", (w-150, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (150,150,150), 1)
                cv2.putText(frame, f"UPTIME: {self.state['uptime']}", (w-300, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (150,150,150), 1)
                
                # Person info
                if vision_data.get('person_present', False):
                    looking = vision_data.get('someone_looking', False)
                    color = (0,255,255) if looking else (200,200,200)
                    cv2.putText(frame, "👤 Person detected", (10, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 1)
                
                # Last response
                if self.state['last_decision'] and self.state['awake']:
                    msg = self.state['last_decision'].get('message', '')[:50]
                    cv2.putText(frame, f"🤖 {msg}", (10, h-30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (150,255,150), 1)
                
                # Battery
                battery_color = (0,255,0) if self.state['battery'] > 50 else (0,255,255) if self.state['battery'] > 20 else (0,0,255)
                cv2.putText(frame, f"🔋 {self.state['battery']}%", (w-100, h-20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, battery_color, 1)
                
                cv2.imshow("SHERU AI Desk Companion - ESP32 Camera", frame)
                
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    self.running = False
                    break
                elif key == ord('s'):
                    if self.state['awake']:
                        self.go_to_sleep()
                    else:
                        self.wake_up()
                elif key == ord('f'):
                    self.features.focus_mode = not self.features.focus_mode
                    print(f"Focus mode: {self.features.focus_mode}")
                elif key == ord('e'):
                    self.features.emotion_mirror_enabled = not self.features.emotion_mirror_enabled
                    print(f"Emotion mirror: {self.features.emotion_mirror_enabled}")
                
                # Daily briefing check (only if awake)
                if time.time() - self.features.last_weather_check > 3600:
                    self.features.generate_daily_briefing(self.state['awake'])
                    self.features.last_weather_check = time.time()
                
            except Exception as e:
                print(f"UI error: {e}")
                time.sleep(0.1)
        
        cv2.destroyAllWindows()
        self.cleanup()

    def cleanup(self):
        self.running = False
        self.camera.stop()
        self.voice.stop()
        print("✅ System shutdown complete")

    def run(self):
        # Start background threads
        threads = [
            threading.Thread(target=self.vision_thread_func, daemon=True),
            threading.Thread(target=self.speech_thread_func, daemon=True)
        ]
        for t in threads:
            t.start()
        
        print("\n" + "="*60)
        print(" SHERU AI DESK COMPANION - READY ")
        print("="*60)
        print("\n📷 Using ESP32 Camera")
        print(f"📷 Camera URL: {self.state['camera_url']}")
        print("\nCommands:")
        print("  • Say 'Sheru' to wake up")
        print("  • Say 'sleep' to put to sleep")
        print("  • Press 'S' to toggle sleep mode")
        print("  • Press 'F' to toggle focus mode")
        print("  • Press 'E' to toggle emotion mirror")
        print("  • Press 'Q' to quit")
        print("\n" + "="*60 + "\n")
        
        # Run UI in main thread
        self.run_ui()

# ========== MAIN ==========
if __name__ == "__main__":
    # Auto-detect ESP32 camera or prompt for URL
    esp32_url = find_esp32_camera()
    
    print("\n" + "="*60)
    print(" ESP32 CAMERA SETUP ")
    print("="*60)
    print(f"Using ESP32 camera at: {esp32_url}")
    print("Make sure your ESP32 is connected to the same network")
    print("="*60 + "\n")
    
    companion = AdvancedDeskCompanion(esp32_url)
    companion.run()