from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database.models import get_user_by_fake_id, get_user_profile

# FSM for Messaging
class Messaging(StatesGroup):
    writing_message = State()

router = Router()

@router.callback_query(F.data.startswith("msg_"))
async def start_messaging(callback: types.CallbackQuery, state: FSMContext):
    target_fake_id = callback.data.split("_")[1]
    
    # Resolve target user
    target_user_row = await get_user_by_fake_id(target_fake_id)
    
    if not target_user_row:
        await callback.answer("❌ User not found.", show_alert=True)
        return
        
    target_user_id = target_user_row['user_id']
    target_fake_name = target_user_row['fake_name']
    
    # Prevent self-messaging
    if target_user_id == callback.from_user.id:
        await callback.answer("⚠️ You cannot message yourself.", show_alert=True)
        return

    # Store target info in state
    await state.update_data(target_user_id=target_user_id, target_fake_name=target_fake_name)
    
    await callback.message.answer(
        f"📝 You are sending a message to {target_fake_name}.\n\n"
        "Please type your message below:"
    )
    await state.set_state(Messaging.writing_message)
    await callback.answer()

@router.message(Messaging.writing_message)
async def process_message_sending(message: types.Message, state: FSMContext):
    data = await state.get_data()
    target_user_id = data['target_user_id']
    target_fake_name = data['target_fake_name']
    
    # Get Sender's Fake Profile
    sender_user_row = await get_user_profile(message.from_user.id)
    sender_fake_name = sender_user_row['fake_name'] if sender_user_row else "Stranger"
    sender_fake_id = sender_user_row['fake_id'] if sender_user_row else "UNK"
    
    # Forward Message Logic (Send as Bot)
    try:
        from keyboards.builders import get_message_author_keyboard
        
        # We send a message to the target
        # We attach a "Reply" button which is just "Message Author" pointing back to Sender
        reply_kb = get_message_author_keyboard(sender_fake_id)
        
        await message.bot.send_message(
            chat_id=target_user_id,
            text=f"📩 New Message from {sender_fake_name}:\n\n{message.text}",
            reply_markup=reply_kb
        )
        
        await message.answer(f"✅ Message sent to {target_fake_name}!")
        
    except Exception as e:
        await message.answer(f"❌ Failed to send message: {e}")
        
    await state.clear()
