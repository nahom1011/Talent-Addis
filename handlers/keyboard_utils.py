from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup
from database.models import get_post, get_reaction_counts, get_comment_count, get_user_profile
from keyboards.builders import get_reaction_keyboard, get_comment_controls_keyboard, get_message_author_keyboard, get_report_button
from utils.config import CHANNEL_ID

async def update_post_keyboard(bot: Bot, post_id: int):
    # Fetch Post Details
    post = await get_post(post_id)
    if not post or not post['message_id']:
        return

    # Counts
    reaction_counts = await get_reaction_counts(post_id)
    comment_count = await get_comment_count(post_id)
    
    # 1. Reaction Keyboard
    reaction_kb = get_reaction_keyboard(post_id, reaction_counts)
    final_buttons = list(reaction_kb.inline_keyboard)
    
    # 2. Comment Keyboard
    comments_enabled = post['comments_enabled'] if 'comments_enabled' in post.keys() else 1
    if comments_enabled:
         comment_kb = get_comment_controls_keyboard(post_id, comment_count)
         final_buttons.extend(comment_kb.inline_keyboard)

    # 3. ID Request / Message Author
    # Need to check anonymity
    if post['is_anonymous']:
         # Fetch Fake Profile
         user_profile = await get_user_profile(post['user_id'])
         fake_id = user_profile['fake_id'] if user_profile else "UNK"
         msg_kb = get_message_author_keyboard(fake_id)
         msg_kb = get_message_author_keyboard(fake_id)
         final_buttons.extend(msg_kb.inline_keyboard)
         
    # 4. Report Button (Fix: Restore if missing)
    final_buttons.append([get_report_button(post_id)])
         
    final_kb = InlineKeyboardMarkup(inline_keyboard=final_buttons)
    
    # Edit Message
    try:
        await bot.edit_message_reply_markup(
            chat_id=CHANNEL_ID,
            message_id=post['message_id'],
            reply_markup=final_kb
        )
    except Exception as e:
        print(f"Failed to update keyboard for post {post_id}: {e}")
