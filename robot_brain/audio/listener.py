import queue
import sounddevice as sd
import json
from vosk import Model, KaldiRecognizer
import os
import time

# Use a larger model if available – change this path
MODEL_PATH = os.path.join(
    os.path.dirname(__file__),
    "models",
    "vosk-model-en-us-0.22"          # <-- change to your model folder name
)

class SpeechListerner:
    def __init__(self):
        print("Loading speech model ...")
        if not os.path.exists(MODEL_PATH):
            raise FileNotFoundError(f"Model not found at {MODEL_PATH}. Please download a Vosk model.")
        self.model = Model(MODEL_PATH)
        self.recognizer = KaldiRecognizer(self.model, 16000)
        print("Speech recognizer ready")

    def listen_once(self, listen_seconds=4):
        q = queue.Queue()

        def callback(indata, frames, time, status):
            q.put(bytes(indata))

        print("Listening...")
        with sd.RawInputStream(samplerate=16000, blocksize=8000, dtype='int16',
                               channels=1, callback=callback):
            start = time.time()
            while time.time() - start < listen_seconds:
                try:
                    data = q.get(timeout=1)
                    if self.recognizer.AcceptWaveform(data):
                        result = json.loads(self.recognizer.Result())
                        text = result.get("text", "")
                        if text:
                            return text
                except queue.Empty:
                    pass
        return ""