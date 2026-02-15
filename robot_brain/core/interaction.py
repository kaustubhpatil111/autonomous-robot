from fuzzywuzzy import fuzz, process

class InteractionBrain:
    def __init__(self, voice=None):
        self.voice = voice
        # Define commands and their responses, and whether they trigger sleep
        self.commands = {
            "hello": ("Hello Kaustubh!", False),
            "hi": ("Hello Kaustubh!", False),
            "how are you": ("I am functioning perfectly, thank you.", False),
            "what do you see": ("I am watching the room through my camera.", False),
            "sleep": ("Going to sleep mode.", True),
            "goodbye": ("Goodbye! Going to sleep.", True),
            "shut down": ("Shutting down. Goodnight.", True),
            "what is your name": ("My name is Sheru, your desktop companion.", False),
            "who are you": ("I am Sheru, your robotic dog.", False),
            "tell me a joke": ("Why don't scientists trust atoms? Because they make up everything!", False),
            "what time is it": (self._get_time, False),   # dynamic response
        }
        # For fuzzy matching, we use the keys as choices
        self.command_keys = list(self.commands.keys())

    def _get_time(self):
        from datetime import datetime
        now = datetime.now().strftime("%I:%M %p")
        return f"The time is {now}."

    def handle_command(self, text: str):
        text = text.lower().strip()
        print("Command:", text)

        if not text:
            return "I did not hear that.", False

        # Fuzzy match against known commands (threshold 60)
        best_match, score = process.extractOne(text, self.command_keys, scorer=fuzz.ratio)
        if score >= 60:
            response, should_sleep = self.commands[best_match]
            # If response is a function, call it
            if callable(response):
                response = response()
            return response, should_sleep
        else:
            return "I did not understand.", False