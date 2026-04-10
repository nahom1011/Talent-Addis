from aiogram.fsm.state import State, StatesGroup

class Submission(StatesGroup):
    choosing_category = State()
    choosing_content_type = State() # Deprecated but kept for safety if needed
    waiting_for_content = State() # General state for waiting for Text/Photo/Voice
    input_text = State()
    input_photo = State()
    input_voice = State()
    waiting_for_caption = State()
    choosing_anonymity = State()
    choosing_comments_enabled = State()

class AddingComment(StatesGroup):
    input_comment = State()

class AdminState(StatesGroup):
    waiting_for_rejection_reason = State()
