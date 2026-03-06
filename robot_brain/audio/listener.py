import queue
import sounddevice as sd
import json
from vosk import Model, KaldiRecognizer
import os
import time

MODEL_PATH = os.path.join(
    os.path.dirname(__file__),
    "models",
    "vosk-model-small-en-us-0.15"
)

class SpeechListener:
    def __init__(self):
        print("Loading speech model ...")
        if not os.path.exists(MODEL_PATH):
            print(f"⚠️ Model not found at {MODEL_PATH}. Voice commands will not work.")
            self.recognizer = None
            return
        try:
            self.model = Model(MODEL_PATH)
            self.recognizer = KaldiRecognizer(self.model, 16000)
            print("Speech recognizer ready")
        except Exception as e:
            print(f"⚠️ Failed to load speech model: {e}")
            self.recognizer = None

    def listen_once(self, listen_seconds=4):
        if self.recognizer is None:
            time.sleep(listen_seconds)
            return ""

        q = queue.Queue()

        def callback(indata, frames, time, status):
            q.put(bytes(indata))

        try:
            with sd.RawInputStream(samplerate=16000, blocksize=8000, dtype='int16',
                                   channels=1, callback=callback):
                start = time.time()
                while time.time() - start < listen_seconds:
                    try:
                        data = q.get(timeout=0.5)
                        if self.recognizer.AcceptWaveform(data):
                            result = json.loads(self.recognizer.Result())
                            text = result.get("text", "")
                            if text:
                                return text
                    except queue.Empty:
                        pass
        except Exception as e:
            print(f"🎤 Microphone error: {e}")
            time.sleep(listen_seconds)
        return ""