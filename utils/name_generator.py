import random
import uuid

ADJECTIVES = [
    "Neon", "Cyber", "Silent", "Hidden", "Shadow", "Mystic", "Solar", "Lunar",
    "Digital", "Quantum", "Velvet", "Iron", "Frozen", "Rapid", "Echo", "Cosmic",
    "Vivid", "Hollow", "Glitch", "Turbo", "Ghost", "Phantom", "Rogue", "Elite"
]

NOUNS = [
    "Tiger", "Wolf", "Eagle", "Falcon", "Ghost", "Shadow", "Ninja", "Samurai",
    "Wizard", "Knight", "Rider", "Pilot", "Walker", "Drifter", "Hunter", "Seeker",
    "Panda", "Fox", "Bear", "Lion", "Dragon", "Phoenix", "Shark", "Whale"
]

def generate_fake_name() -> str:
    adj = random.choice(ADJECTIVES)
    noun = random.choice(NOUNS)
    num = random.randint(10, 99)
    return f"{adj} {noun} {num}"

def generate_fake_id() -> str:
    """Detailed unique ID, but we might just use the name as ID if unique enough.
    For system robustness, let's use a short UUID segment."""
    return str(uuid.uuid4())[:8]
