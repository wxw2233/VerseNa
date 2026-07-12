import random
from dataclasses import dataclass

@dataclass
class EmotionState:
    primary: str
    intensity: float
    emoji: str

EMOTION_EMOJIS = {
    "cheerful": ["😊", "😄", "✨", "🎉"],
    "shy": ["😳", "😅", "🙈"],
    "curious": ["🤔", "🧐", "💡"],
    "angry": ["😤", "💢"],
    "sad": ["😢", "😞", "💧"],
}

class EmotionEngine:
    def __init__(self, weights: dict):
        self.weights = weights

    def pick_emotion(self) -> EmotionState:
        emotions = list(self.weights.keys())
        probs = list(self.weights.values())
        chosen = random.choices(emotions, weights=probs, k=1)[0]
        intensity = self.weights[chosen]
        emoji = random.choice(EMOTION_EMOJIS.get(chosen, ["💬"]))
        return EmotionState(primary=chosen, intensity=intensity, emoji=emoji)
