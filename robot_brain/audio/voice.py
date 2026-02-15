# robot_brain/audio/voice.py
import subprocess
import threading
import queue
import time
import sys
import platform

class RobotVoice:
    def __init__(self):
        self.queue = queue.Queue()
        self.running = True

        # start worker thread
        t = threading.Thread(target=self._worker, daemon=True)
        t.start()
        print("🔊 Voice system ready (PowerShell SAPI)")

    def _worker(self):
        """
        Worker thread that takes (text, done_event) from the queue
        and speaks the text using Windows PowerShell SAPI.
        """
        while self.running:
            try:
                item = self.queue.get()
                if item is None:          # sentinel to stop
                    break
                text, done_event = item

                # Speak using PowerShell (blocks until finished)
                success = self._speak_powershell(text)
                if not success:
                    print("[VOICE] All TTS methods failed for:", repr(text), file=sys.stderr)

                # Signal completion if an event was provided
                if done_event is not None:
                    done_event.set()

            except Exception as e:
                print("[VOICE] Worker exception:", e, file=sys.stderr)

        print("[VOICE] Worker exiting")

    def _speak_powershell(self, text: str) -> bool:
        """
        Use PowerShell's SpeechSynthesizer to speak the text.
        Returns True if successful, False otherwise.
        """
        try:
            # Escape double quotes inside the text
            safe_text = text.replace('"', '\\"')
            ps_command = (
                f'Add-Type -AssemblyName System.Speech; '
                f'$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; '
                f'$synth.Speak("{safe_text}");'
            )
            # Run PowerShell hidden, wait for completion
            subprocess.run(
                ["powershell", "-Command", ps_command],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
            )
            return True
        except Exception as e:
            print("[VOICE] PowerShell failed:", e, file=sys.stderr)
            return False

    def speak(self, text: str):
        """Enqueue text to be spoken (non‑blocking)."""
        self.queue.put((text, None))

    def speak_and_wait(self, text: str, timeout: float | None = None):
        """
        Enqueue text and block until it has been spoken (or timeout).
        """
        done = threading.Event()
        self.queue.put((text, done))
        waited = done.wait(timeout=timeout)
        if not waited:
            print("[VOICE] speak_and_wait timed out for:", repr(text))

    def stop(self):
        """Shut down the worker thread gracefully."""
        self.running = False
        self.queue.put(None)   # sentinel