import cv2
import time
import threading
from datetime import datetime, timedelta

from robot_brain.audio.listener import SpeechListerner
from robot_brain.audio.voice import RobotVoice
from robot_brain.core.interaction import InteractionBrain
from robot_brain.camera.camera_stream import CameraStream
from robot_brain.vision.vision_node import VisionNode

print("🚀 Starting Robot Brain ...")

# Wake words
WAKE_WORDS = ("sheru", "shiru", "she ru", "shero", "dog")

# ---------------- INIT MODULES ---------------- #
camera   = CameraStream("http://192.168.4.1:81/stream")
vision   = VisionNode()
voice    = RobotVoice()
listener = SpeechListerner()
brain    = InteractionBrain()

# ---------------- STATE ---------------- #
awake = False                     # are we in command-listening mode?
last_activity = datetime.now()    # used for auto‑sleep timeout
AWAKE_TIMEOUT = 300               # 5 minutes in seconds

# ---------------- HELPERS ---------------- #
def contains_wake(text: str) -> bool:
    t = (text or "").lower()
    return any(w in t for w in WAKE_WORDS)

def go_to_sleep():
    global awake
    awake = False
    voice.speak_and_wait("Going to sleep.", timeout=4)
    print("😴 Robot is now asleep.")

# ---------------- SPEECH THREAD ---------------- #
def speech_loop():
    global awake, last_activity

    print("🎤 Speech loop started")

    while True:
        # --- ASLEEP: listen for wake word ---
        if not awake:
            text = listener.listen_once(listen_seconds=3)
            if text and contains_wake(text):
                print("💬 Wake word detected")
                voice.speak_and_wait("Yes, I am listening.", timeout=6)
                time.sleep(0.6)                # avoid hearing ourselves
                awake = True
                last_activity = datetime.now()
                print("🤖 Robot is now awake for 5 minutes.")
            continue

        # --- AWAKE: listen for commands ---
        # Check timeout
        if (datetime.now() - last_activity).total_seconds() > AWAKE_TIMEOUT:
            print("⏰ 5‑minute inactivity timeout reached.")
            go_to_sleep()
            continue

        # Listen for a command (shorter window, repeated)
        command = listener.listen_once(listen_seconds=5)

        if not command or len(command.strip()) < 2:
            # No command heard – stay awake, just loop again
            continue

        cmd_lc = command.lower().strip()

        # Ignore echoes of our own voice
        if contains_wake(cmd_lc) or "yes i am listening" in cmd_lc:
            continue

        print("🧠 Command heard:", command)

        # Process command (InteractionBrain returns reply + optional sleep flag)
        reply, should_sleep = brain.handle_command(command)

        if not reply:
            reply = "I did not understand."

        print("[MAIN] Reply to speak:", repr(reply))
        voice.speak_and_wait(reply, timeout=8)

        # Update activity time (unless it was a sleep command)
        if should_sleep:
            go_to_sleep()
        else:
            last_activity = datetime.now()

        time.sleep(0.3)

# start speech thread
threading.Thread(target=speech_loop, daemon=True).start()

# ---------------- CAMERA LOOP (unchanged) ---------------- #
fps_time = time.time()
frame_count = 0

print("📹 Camera + Vision running")
print("Press Q to quit\n")

while True:
    frame = camera.get_frame()
    if frame is None:
        continue

    annotated = vision.process(frame)

    frame_count += 1
    if frame_count >= 10:
        fps = frame_count / (time.time() - fps_time)
        fps_time = time.time()
        frame_count = 0
        cv2.putText(annotated, f"FPS: {int(fps)}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

    # Show awake status on video
    status_text = "AWAKE" if awake else "ASLEEP"
    cv2.putText(annotated, status_text, (10, 60),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0) if awake else (0, 0, 255), 2)

    cv2.imshow("🤖 Robot Brain", annotated)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

camera.stop()
cv2.destroyAllWindows()
voice.stop()
print("🛑 Robot stopped")