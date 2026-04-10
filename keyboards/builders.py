from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

def get_main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Persistent main menu at the bottom."""
    buttons = [
        [KeyboardButton(text="📤 Submit Talent")],
        [KeyboardButton(text="👤 My Profile"), KeyboardButton(text="🏆 Leaderboard")],
        [KeyboardButton(text="📂 Dashboard"), KeyboardButton(text="📱 Story Card")],
        [KeyboardButton(text="📄 My Portfolio")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True, persistent=True)

CATEGORIES = [
    "Photography", "Drawing", "Writing", 
    "Singing", "Random Thoughts"
]

def get_categories_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=cat, callback_data=f"cat_{cat}")] 
        for cat in CATEGORIES
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_content_type_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="📝 Text", callback_data="type_text")],
        [InlineKeyboardButton(text="📷 Photo", callback_data="type_photo")],
        [InlineKeyboardButton(text="🎤 Voice Message", callback_data="type_voice")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_anonymity_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="👤 Use Real Name", callback_data="anon_false")],
        [InlineKeyboardButton(text="🎭 Use Anonymous ID", callback_data="anon_true")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_yes_no_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="✅ Yes", callback_data="yes"), InlineKeyboardButton(text="❌ No", callback_data="no")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_skip_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="Skip Voice Note", callback_data="skip_voice")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_message_author_keyboard(author_fake_id: str) -> InlineKeyboardMarkup:
    from utils.config import BOT_USERNAME
    buttons = [
        [InlineKeyboardButton(text="👤 Check Profile", url=f"https://t.me/{BOT_USERNAME}?start=profile_{author_fake_id}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_reaction_keyboard(post_id: int, counts: dict = None) -> InlineKeyboardMarkup:
    if counts is None:
        counts = {}
        
    # Default emojis
    emojis = ["❤️", "👏", "🔥"]
    buttons = []
    
    for emoji in emojis:
        count = counts.get(emoji, 0)
        label = f"{emoji} {count}" if count > 0 else emoji
        buttons.append(InlineKeyboardButton(text=label, callback_data=f"react_{emoji}_{post_id}"))
        
    return InlineKeyboardMarkup(inline_keyboard=[buttons])

def get_comment_controls_keyboard(post_id: int, comment_count: int = 0) -> InlineKeyboardMarkup:
    from utils.config import BOT_USERNAME
    buttons = [
        [
            InlineKeyboardButton(text=f"💬 Comment ({comment_count})", url=f"https://t.me/{BOT_USERNAME}?start=comment_{post_id}"),
            InlineKeyboardButton(text="📝 View Comments", url=f"https://t.me/{BOT_USERNAME}?start=view_comments_{post_id}")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_report_button(post_id: int) -> InlineKeyboardButton:
    from utils.config import BOT_USERNAME
    return InlineKeyboardButton(text="⚠️ Report", url=f"https://t.me/{BOT_USERNAME}?start=report_{post_id}")
