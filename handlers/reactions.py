from aiogram import Router, types, F
from database.models import toggle_reaction, get_reaction_counts
from keyboards.builders import get_reaction_keyboard

router = Router()

@router.callback_query(F.data.startswith("react_"))
async def process_reaction(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    # react_❤️_POSTID
    if len(parts) < 3:
        await callback.answer("Invalid reaction data")
        return
        
    emoji = parts[1]
    post_id = int(parts[2])
    user_id = callback.from_user.id
    
    # Toggle reaction in DB
    result = await toggle_reaction(post_id, user_id, emoji)
    
    # Gamification: Check Creator's stats
    from database.models import get_post, check_and_award_badges
    post = await get_post(post_id)
    if post and post['user_id']:
        await check_and_award_badges(post['user_id'])
    
    # Update Full Keyboard (Reactions + Comments + ID Request)
    from handlers.keyboard_utils import update_post_keyboard
    await update_post_keyboard(callback.bot, post_id)
    
    # Acknowledge
    await callback.answer(f"Reaction {result}")
        
    # Answer callback
    # feedback_text = f"Reaction {result}!"
    # await callback.answer(feedback_text)
    await callback.answer() # Silent update is smoother
