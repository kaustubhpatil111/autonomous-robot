import requests
import json
import time
import re
from datetime import datetime
from collections import deque
import random

class LLMBrain:
    def __init__(self, model="mistral", ollama_url="http://localhost:11434"):
        self.model = model
        self.ollama_url = ollama_url
        self.last_query_time = 0
        self.min_query_interval = 1.0
        self.conversation_history = deque(maxlen=10)
        self.long_term_memory = []
        self.user_preferences = {}
        self.personality_traits = {
            "curiosity": 0.8,
            "playfulness": 0.7,
            "protectiveness": 0.5,
            "independence": 0.6
        }
        self.mood = "neutral"
        self.mood_history = deque(maxlen=100)
        self.interaction_patterns = {}
        self.user_familiarity = {}
        
    def query(self, prompt, temperature=0.3, max_tokens=250):
        now = time.time()
        if now - self.last_query_time < self.min_query_interval:
            time.sleep(self.min_query_interval - (now - self.last_query_time))
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens
            }
        }
        
        try:
            response = requests.post(f"{self.ollama_url}/api/generate", 
                                    json=payload, 
                                    timeout=10)
            response.raise_for_status()
            self.last_query_time = time.time()
            return response.json()["response"].strip()
        except Exception as e:
            print(f"[LLM] Query error: {e}")
            return None

    def extract_json(self, text):
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            json_str = match.group()
            json_str = re.sub(r'//.*$', '', json_str, flags=re.MULTILINE)
            json_str = re.sub(r'#.*$', '', json_str, flags=re.MULTILINE)
            return json_str
        return None

    def get_contextual_response(self, vision_data, user_command=None, user_id="default"):
        """Advanced decision method with JSON output and fallback"""
        
        # Build rich context
        now = datetime.now()
        time_str = now.strftime("%H:%M")
        day = now.strftime("%A")
        time_of_day = "morning" if now.hour < 12 else "afternoon" if now.hour < 18 else "evening"
        
        vision_summary = vision_data.get('scene_description', 'Nothing visible')
        person_present = vision_data.get('person_present', False)
        someone_looking = vision_data.get('someone_looking', False)
        attention_time = vision_data.get('attention_time', 0)
        face_expression = vision_data.get('face_expression', 'unknown')
        # Ensure gaze_direction is a string, not a slice/tuple
        gaze_direction = vision_data.get('gaze_direction', 'unknown')
        if not isinstance(gaze_direction, str):
            gaze_direction = str(gaze_direction)
        
        context = f"""Current time: {time_str} on {day} ({time_of_day})
Location: Desk environment

Visual Analysis:
- Scene: {vision_summary}
- Person detected: {'yes' if person_present else 'no'}
- Looking at me: {'yes' if someone_looking else 'no'}
- Attention duration: {attention_time:.1f}s
- User expression: {face_expression}
- Gaze direction: {gaze_direction}

System State:
- Mood: {self.mood}
- Personality: Curious({self.personality_traits['curiosity']:.1f}), Playful({self.personality_traits['playfulness']:.1f})
- Recent interactions: {len(self.conversation_history)} in last hour
"""

        if user_command:
            context += f"\nUser command: '{user_command}'"
        
        prompt = f"""You are Sheru, an advanced AI desk companion with emotional intelligence and memory. 
Based on the context below, respond with a JSON object containing:
- "message": what you say (natural, contextual, emotionally appropriate)
- "mode": one of [idle, greet, explore, focus, entertain, comfort, guard, charge, learn]
- "emotion": one of [happy, curious, alert, sleepy, friendly, playful, concerned, focused]
- "suggestion": suggested action for the robot (e.g., "move_closer", "stay_still", "look_around")
- "confidence": float between 0-1 indicating decision confidence

Consider:
1. Time of day and user patterns
2. User's emotional state from visual cues
3. Your current mood and personality
4. Previous interactions
5. Environmental context

Examples:
{{"message": "Good morning! You seem focused on your work. I'll keep you company quietly.", 
  "mode": "focus", "emotion": "focused", "suggestion": "stay_still", "confidence": 0.9}}
{{"message": "You look like you need a break! Want to hear a joke?", 
  "mode": "entertain", "emotion": "playful", "suggestion": "move_closer", "confidence": 0.8}}

Context:
{context}

Respond with JSON only:"""

        # Try LLM query
        for attempt in range(2):
            response = self.query(prompt, temperature=0.4)
            if response:
                json_str = self.extract_json(response)
                if json_str:
                    try:
                        decision = json.loads(json_str)
                        required = ['message', 'mode', 'emotion', 'suggestion', 'confidence']
                        if all(k in decision for k in required):
                            # Store in history
                            self.conversation_history.append(decision)
                            return decision
                    except json.JSONDecodeError:
                        pass
            time.sleep(0.5)
        
        # Fallback intelligent response based on context
        if user_command:
            msg = self._generate_fallback_response(user_command)
            return {
                "message": msg,
                "mode": "idle",
                "emotion": "curious",
                "suggestion": "stay_still",
                "confidence": 0.5
            }
        elif person_present and someone_looking:
            return {
                "message": f"Good {time_of_day}! I notice you looking at me. How can I help?",
                "mode": "greet",
                "emotion": "happy",
                "suggestion": "look_back",
                "confidence": 0.7
            }
        else:
            return {
                "message": "I'm here and paying attention to my surroundings.",
                "mode": "idle",
                "emotion": "curious",
                "suggestion": "scan_environment",
                "confidence": 0.6
            }

    def _generate_fallback_response(self, command):
        """Generate a simple fallback response when LLM fails"""
        responses = [
            "I'm here to help! What would you like me to do?",
            "I understand you said something, but I need a moment to process.",
            "Tell me more about that.",
            "I'm listening. Please go on.",
            "How can I assist you with that?"
        ]
        return random.choice(responses)

    def decide(self, vision_data, user_command=None):
        """Simple wrapper for backward compatibility"""
        return self.get_contextual_response(vision_data, user_command)