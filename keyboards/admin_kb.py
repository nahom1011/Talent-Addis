from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_admin_approval_keyboard(post_id: int) -> InlineKeyboardMarkup:
    from utils.security import sign_data
    
    approve_data = sign_data(f"approve_{post_id}")
    reject_data = sign_data(f"reject_{post_id}")
    
    buttons = [
        [
            InlineKeyboardButton(text="✅ Approve", callback_data=approve_data),
            InlineKeyboardButton(text="❌ Reject", callback_data=reject_data)
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
