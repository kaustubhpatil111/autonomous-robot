import subprocess
import threading
import queue
import time
import platform

class RobotVoice:
    def __init__(self):
        self.queue = queue.Queue()
        self.running = True
        self._is_speaking = False
        self._lock = threading.Lock()
        
        t = threading.Thread(target=self._worker, daemon=True)
        t.start()
        print("🔊 Voice system ready")

    def _worker(self):
        while self.running:
            try:
                item = self.queue.get(timeout=0.5)
                if item is None:
                    break
                    
                text, done_event = item
                
                with self._lock:
                    self._is_speaking = True
                
                try:
                    self._speak_powershell(text)
                finally:
                    with self._lock:
                        self._is_speaking = False
                    time.sleep(1.5)  # Pause to avoid echo
                
                if done_event:
                    done_event.set()
                    
            except queue.Empty:
                continue
            except Exception as e:
                print(f"[VOICE] Worker exception: {e}")
        
        print("[VOICE] Worker exiting")

    def _speak_powershell(self, text):
        try:
            safe_text = text.replace('"', '\\"')
            ps_cmd = f'Add-Type -AssemblyName System.Speech; $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; $synth.Speak("{safe_text}");'
            
            # Add timeout to prevent hanging
            subprocess.run(
                ["powershell", "-Command", ps_cmd],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
            )
            return True
        except subprocess.TimeoutExpired:
            print(f"[VOICE] PowerShell timeout for: {text}")
        except Exception as e:
            print(f"[VOICE] PowerShell failed: {e}")
        return False

    def is_speaking(self):
        with self._lock:
            return self._is_speaking

    def speak(self, text):
        self.queue.put((text, None))

    def speak_and_wait(self, text, timeout=None):
        done = threading.Event()
        self.queue.put((text, done))
        waited = done.wait(timeout)
        if not waited:
            print(f"[VOICE] speak_and_wait timed out for: {repr(text)}")

    def stop(self):
        self.running = False
        self.queue.put(None)