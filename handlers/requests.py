from aiogram import Router, types, F, Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.models import (
    get_user_by_fake_id, 
    get_user_profile, 
    create_id_request, 
    check_existing_request, 
    get_id_request, 
    update_id_request_status
)

router = Router()

# Helper keyboard for request actions
def get_request_actions_keyboard(request_id: int, requester_id: int, target_user_id: int) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(text="✅ Approve", callback_data=f"req_approve_{request_id}_{target_user_id}_{requester_id}"),
            InlineKeyboardButton(text="❌ Reject", callback_data=f"req_reject_{request_id}_{target_user_id}_{requester_id}")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

@router.callback_query(F.data.startswith("req_id_"))
async def process_id_request_start(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    if len(parts) < 3:
        await callback.answer("❌ Invalid data.")
        return
    target_fake_id = parts[2]
    requester_user_id = callback.from_user.id
    
    # 1. Resolve Target
    target_user_row = await get_user_by_fake_id(target_fake_id)
    if not target_user_row:
        await callback.answer("❌ User not found.", show_alert=True)
        return
        
    target_user_id = target_user_row['user_id']
    
    # Self-check
    if target_user_id == requester_user_id:
        await callback.answer("⚠️ You cannot request your own ID.", show_alert=True)
        return

    # 2. Check Existing Request
    existing = await check_existing_request(requester_user_id, target_user_id)
    if existing:
        status = existing['status']
        if status == 'pending':
            await callback.answer("⏳ Request already sent. Waiting for approval.", show_alert=True)
        elif status == 'approved':
            await callback.answer("✅ Request already approved! Check your DMs.", show_alert=True)
            # Optional: Resend ID?
        elif status == 'rejected':
            await callback.answer("❌ Request was previously rejected.", show_alert=True)
        return

    # 3. Create Request
    request_id = await create_id_request(requester_user_id, target_user_id)
    if not request_id:
        await callback.answer("⚠️ Error creating request.", show_alert=True)
        return

    # 4. Notify Target
    # Get Requester's Mock Profile
    requester_profile = await get_user_profile(requester_user_id)
    requester_fake_name = requester_profile['fake_name'] if requester_profile else "Stranger"
    
    try:
        await callback.bot.send_message(
            chat_id=target_user_id,
            text=f"🔒 ID Request\n\nUser {requester_fake_name} wants to know your real Telegram username.\n\nDo you approve?",
            reply_markup=get_request_actions_keyboard(request_id, requester_user_id, target_user_id)
        )
        await callback.answer("✅ Request sent! You will be notified if they approve.", show_alert=True)
    except Exception as e:
        await callback.answer("❌ Failed to send request (User might be unavailable).", show_alert=True)
        # Cleanup request if failed?
        await update_id_request_status(request_id, 'failed')

@router.callback_query(F.data.startswith("req_approve_"))
async def process_id_request_approval(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    if len(parts) < 4:
        await callback.answer("❌ Invalid data.")
        return
    try:
        request_id = int(parts[2])
        target_user_id_cb = int(parts[3])
    except ValueError:
        return

    # Access Check (Callback Level)
    if callback.from_user.id != target_user_id_cb:
         await callback.answer("⚠️ This button is not for you.", show_alert=True)
         return
    
    # Get Request Info
    request = await get_id_request(request_id)
    if not request:
        await callback.answer("❌ Request not found.")
        return
        
    if request['status'] != 'pending':
        await callback.answer("⚠️ Request already processed.")
        await callback.message.edit_reply_markup(reply_markup=None)
        return

    requester_id = request['requester_id']
    target_user_id = request['target_user_id']
    
    # Access Check (DB Level)
    if callback.from_user.id != target_user_id:
         await callback.answer("⚠️ Unauthorized.")
         return

    # Approve
    await update_id_request_status(request_id, 'approved')
    
    # Edit Target's Message
    await callback.message.edit_text(
        f"{callback.message.text}\n\n✅ Approved! Your ID has been shared.",
        reply_markup=None
    )
    
    # Send Identity to Requester
    target_username = callback.from_user.username
    target_val = f"@{target_username}" if target_username else f"User ID: {target_user_id}"
    
    # Get Target Fake Name for context
    target_profile = await get_user_profile(target_user_id)
    target_fake_name = target_profile['fake_name'] if target_profile else "User"

    try:
        await callback.bot.send_message(
            chat_id=requester_id,
            text=f"🔓 Request Approved!\n\n{target_fake_name} has approved your request.\n\nTheir identity: {target_val}"
        )
    except Exception:
        pass # Requester blocked bot?

    await callback.answer("✅ Approved.")

@router.callback_query(F.data.startswith("req_reject_"))
async def process_id_request_rejection(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    if len(parts) < 4:
        await callback.answer("❌ Invalid data.")
        return
    try:
        request_id = int(parts[2])
        target_user_id_cb = int(parts[3])
    except ValueError:
        return
    
    # Access Check (Callback Level)
    if callback.from_user.id != target_user_id_cb:
         await callback.answer("⚠️ This button is not for you.", show_alert=True)
         return

    # Get Request Info
    request = await get_id_request(request_id)
    if not request:
        await callback.answer("❌ Request not found.")
        return

    if request['status'] != 'pending':
        await callback.answer("⚠️ Request already processed.")
        await callback.message.edit_reply_markup(reply_markup=None)
        return
        
    requester_id = request['requester_id']
    target_user_id = request['target_user_id']
    
    # Access Check (DB Level)
    if callback.from_user.id != target_user_id:
         await callback.answer("⚠️ Unauthorized.")
         return

    # Reject
    await update_id_request_status(request_id, 'rejected')
    
    # Edit Target's Message
    await callback.message.edit_text(
        f"{callback.message.text}\n\n❌ **Rejected.**",
        reply_markup=None
    )
    
    # Notify Requester
    target_profile = await get_user_profile(target_user_id)
    target_fake_name = target_profile['fake_name'] if target_profile else "User"
    
    try:
        await callback.bot.send_message(
            chat_id=requester_id,
            text=f"🚫 **Request Rejected**\n\n**{target_fake_name}** declined your request to see their identity."
        )
    except Exception:
        pass

    await callback.answer("❌ Rejected.")
