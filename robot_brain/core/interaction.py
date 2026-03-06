# robot_brain/core/interaction.py
from robot_brain.core.llm_brain import LLMBrain
import datetime

class InteractionBrain:
    def __init__(self, voice=None):
        self.voice = voice
        self.llm = LLMBrain()   # connects to Ollama
        self.context = {
            "battery": 100,          # placeholder, update from main loop
            "location": "living room",
            "detections": "none",
            "time": datetime.datetime.now().strftime("%H:%M")
        }

    def update_context(self, **kwargs):
        """Update context from sensors (called from main loop)."""
        self.context.update(kwargs)

    def handle_command(self, text: str):
        """
        Returns: (reply_text, should_sleep)
        """
        if not text:
            return "I didn't hear anything.", False

        # If "sleep" is in command, handle locally for quick response
        if "sleep" in text.lower():
            return "Going to sleep. Goodnight!", True

        # Prepare context for LLM
        self.context["user_command"] = text
        self.context["time"] = datetime.datetime.now().strftime("%H:%M")

        # Get decision from LLM
        decision = self.llm.decide(self.context)

        # Extract reply message (if any)
        reply = decision.get("message", "Okay.")
        mode = decision.get("mode", "idle")

        # You can also use 'mode' and 'target' to trigger behaviors in main loop
        # For now, we just return the message
        return reply, False