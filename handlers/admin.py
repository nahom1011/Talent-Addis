from aiogram import Router, types, F, Bot, html
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from handlers.states import AdminState
from utils.config import CHANNEL_ID, ADMIN_IDS
from database.models import get_post, update_post_status
from aiogram.exceptions import TelegramBadRequest
import asyncio

router = Router()

@router.callback_query(F.data.startswith("approve_"))
async def admin_approve(callback: types.CallbackQuery, bot: Bot):
    if str(callback.from_user.id) not in ADMIN_IDS:
        await callback.answer("⚠️ You are not an admin.", show_alert=True)
        return

    # Verify HMAC
    from utils.security import verify_data
    original_data = verify_data(callback.data)
    
    if not original_data:
        await callback.answer("❌ Security check failed (HMAC).")
        return

    parts = original_data.split("_")
    # FORMAT: approve_{post_id}
    try:
        post_id = int(parts[1])
    except ValueError:
        await callback.answer("❌ Invalid Post ID.")
        return
        
    # ATOMIC STATUS UPDATE: Attempt to move from 'pending' to 'processing' (to lock)
    from database.models import atomic_update_post_status, get_post
    success = await atomic_update_post_status(post_id, 'processing', 'pending')
    
    if not success:
        # Check if already approved or currently processing
        post = await get_post(post_id)
        current_status = post['status'] if post else "unknown"
        await callback.answer(f"⚠️ Action failed: Post is currently '{current_status}'.", show_alert=True)
        await callback.message.edit_reply_markup(reply_markup=None)
        return

    # Post to Channel
    try:
        from keyboards.builders import get_reaction_keyboard, get_message_author_keyboard
        from database.models import get_user_profile
        
        # Get post data again to ensure we have latest (since we just locked it)
        post = await get_post(post_id)
        if not post:
             await callback.answer("❌ Post vanished.")
             return
             
        # Determine attribution
        if post['is_anonymous']:
             # Fetch Fake Profile
             user_profile = await get_user_profile(post['user_id'])
             fake_name = user_profile['fake_name'] if user_profile and user_profile['fake_name'] else "Anonymous"
             fake_id = user_profile['fake_id'] if user_profile and user_profile['fake_id'] else "UNK"
             
             author_text = f"{fake_name} ({fake_id})"
             # Add Message Button
             msg_kb = get_message_author_keyboard(fake_id)
        else:
             username = post['username'] if post['username'] else "Student"
             author_text = f"@{username}"
             msg_kb = None

        formatted_caption = f"#{html.quote(post['category'])}\n\n{html.quote(post['caption'])}\n\nBy: {html.quote(author_text)}"
        
        # Initial reaction keyboard (empty counts)
        reaction_kb = get_reaction_keyboard(post_id)
        final_buttons = list(reaction_kb.inline_keyboard)
        
        # Add Comment Buttons
        comments_enabled = post['comments_enabled'] if 'comments_enabled' in post.keys() else 1
        if comments_enabled:
             from keyboards.builders import get_comment_controls_keyboard
             comment_kb = get_comment_controls_keyboard(post_id)
             final_buttons.extend(comment_kb.inline_keyboard)

        # Add Author Actions (ID Request)
        if msg_kb:
            final_buttons.extend(msg_kb.inline_keyboard)
            
        # Add Report Button
        from keyboards.builders import get_report_button
        final_buttons.append([get_report_button(post_id)])
            
        final_kb = InlineKeyboardMarkup(inline_keyboard=final_buttons)

        # JITTER Implementation
        import random
        delay = random.randint(30, 60)
        
        async def delayed_post():
            await asyncio.sleep(delay)
            try:
                content_type = post['content_type']
                if content_type == 'text':
                      sent_msg = await bot.send_message(chat_id=CHANNEL_ID, text=formatted_caption, reply_markup=final_kb)
                elif content_type == 'photo':
                      sent_msg = await bot.send_photo(chat_id=CHANNEL_ID, photo=post['photo_file_id'], caption=formatted_caption, reply_markup=final_kb)
                elif content_type == 'voice':
                      sent_msg = await bot.send_voice(chat_id=CHANNEL_ID, voice=post['voice_file_id'], caption=formatted_caption, reply_markup=final_kb)
                
                if sent_msg:
                    from database.models import update_post_status
                    await update_post_status(post_id, 'approved', sent_msg.message_id)
            except Exception as e:
                # Revert if failed heavily? Or mark as failed.
                print(f"Jitter Post Failed: {e}")

        asyncio.create_task(delayed_post())

        # Edit Admin Message Immediately
        if callback.message.caption:
            await callback.message.edit_caption(
                caption=callback.message.caption + f"\n\n✅ APPROVED (Delayed {delay}s) by {html.quote(callback.from_user.full_name)}",
                reply_markup=None
            )
        elif callback.message.text:
             await callback.message.edit_text(
                text=callback.message.text + f"\n\n✅ APPROVED (Delayed {delay}s) by {html.quote(callback.from_user.full_name)}",
                reply_markup=None
            )
            
        await callback.answer("✅ Post Approved!")

    except Exception as e:
        await callback.answer(f"❌ Error: {str(e)}", show_alert=True)

@router.callback_query(F.data.startswith("reject_"))
async def admin_reject_start(callback: types.CallbackQuery, state: FSMContext):
    if str(callback.from_user.id) not in ADMIN_IDS:
        await callback.answer("⚠️ You are not an admin.", show_alert=True)
        return

    # Verify HMAC
    from utils.security import verify_data
    original_data = verify_data(callback.data)
    
    if not original_data:
        await callback.answer("❌ Security check failed (HMAC).")
        return

    parts = original_data.split("_")
    try:
        post_id = int(parts[1])
    except ValueError:
        await callback.answer("❌ Invalid Post ID.")
        return
    
    # Store Post ID in state
    await state.update_data(reject_post_id=post_id, reject_message_id=callback.message.message_id) # Store msg id to edit later
    
    await callback.message.reply(
        f"📝 **Reject Post #{post_id}**\n\nPlease reply with the **reason for rejection** (sent to user)."
    )
    from handlers.states import AdminState
    await state.set_state(AdminState.waiting_for_rejection_reason)
    await callback.answer()

@router.message(AdminState.waiting_for_rejection_reason)
async def admin_reject_process(message: types.Message, state: FSMContext):
    if str(message.from_user.id) not in ADMIN_IDS:
        return

    reason = message.text
    data = await state.get_data()
    post_id = data.get('reject_post_id')
    # existing_msg_id = data.get('reject_message_id') # If we want to edit the original admin message
    
    from database.models import update_post_status, get_post
    
    # Update Status
    await update_post_status(post_id, 'rejected')
    
    # Notify User
    post = await get_post(post_id)
    if post:
        user_id = post['user_id']
        try:
             await message.bot.send_message(
                 chat_id=user_id,
                 text=f"❌ **Submission Rejected**\n\nYour submission (ID #{post_id}) was rejected by admins.\n\n**Reason:** {reason}"
             )
        except Exception:
            pass # User might have blocked bot
            
    await message.answer(f"✅ Post #{post_id} rejected with reason: {reason}")
    await state.clear()

@router.message(Command("banned"))
async def cmd_banned(message: types.Message, command: CommandObject):
    if str(message.from_user.id) not in ADMIN_IDS:
        return
        
    from database.models import get_banned_words, add_banned_word, remove_banned_word
    
    args = command.args
    if not args:
        # LIST BANNED WORDS
        words = await get_banned_words()
        if not words:
            await message.answer("🚫 No banned words set.")
        else:
            text = "🚫 **Banned Words**:\n\n" + ", ".join(words)
            await message.answer(text)
        return
        
    action, word = args.split(" ", 1) if " " in args else (args, None)
    
    if action == "add" and word:
        if await add_banned_word(word):
            await message.answer(f"✅ Added '{word}' to banned list.")
        else:
            await message.answer(f"⚠️ '{word}' is already banned.")
            
    elif action == "remove" and word:
        await remove_banned_word(word)
        await message.answer(f"🗑️ Removed '{word}' from banned list.")
        
    else:
        await message.answer("usage: `/banned` or `/banned add [word]` or `/banned remove [word]`")

@router.message(Command("reports"))
async def cmd_reports(message: types.Message):
    if str(message.from_user.id) not in ADMIN_IDS:
        return
        
    from database.models import get_pending_reports
    reports = await get_pending_reports()
    
    if not reports:
        await message.answer("✅ No pending reports.")
        return
        
    for r in reports:
        report_id = r['report_id']
        post_id = r['post_id']
        reason = r['reason']
        caption = r['caption']
        
        text = (
            f"🚨 **Report #{report_id}**\n"
            f"Post ID: {post_id}\n"
            f"Reason: {reason}\n"
            f"Content Snippet: {caption[:50]}...\n"
        )
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🗑️ Delete Post", callback_data=f"resolve_report_{report_id}_delete_{post_id}"),
                InlineKeyboardButton(text="✅ Ignore Report", callback_data=f"resolve_report_{report_id}_ignore")
            ]
        ])
        
        await message.answer(text, reply_markup=kb)

@router.callback_query(F.data.startswith("resolve_report_"))
async def resolve_report_action(callback: types.CallbackQuery):
    if str(callback.from_user.id) not in ADMIN_IDS:
        return

    parts = callback.data.split("_")
    # Format: resolve_report_{report_id}_{action}_{post_id?}
    if len(parts) < 4:
         await callback.answer("❌ Invalid data format.")
         return

    try:
        report_id = int(parts[2])
        action = parts[3]
    except ValueError:
        await callback.answer("❌ Invalid ID.")
        return
    
    from database.models import resolve_report, update_post_status, get_post
    
    if action == "delete":
        if len(parts) < 5:
             await callback.answer("❌ Missing Post ID.")
             return
        post_id = int(parts[4])
        
        # Delete from Channel
        post = await get_post(post_id)
        if post and post['message_id']:
            try:
                from utils.config import CHANNEL_ID
                await callback.bot.delete_message(chat_id=CHANNEL_ID, message_id=int(post['message_id']))
            except Exception as e:
                await callback.answer(f"⚠️ Channel Delete Failed: {e}", show_alert=True)
                
        # Mark post as rejected/deleted
        await update_post_status(post_id, 'deleted_by_moderation')
        await resolve_report(report_id, 'resolved_deleted')
        await callback.message.edit_text(f"✅ Report #{report_id} Resolved: Post Deleted.")
        
    elif action == "ignore":
        await resolve_report(report_id, 'resolved_ignored')
        await callback.message.edit_text(f"✅ Report #{report_id} Resolved: Ignore.")
    
    await callback.answer()


@router.message(Command("stats"))
async def cmd_stats(message: types.Message):
    if str(message.from_user.id) not in ADMIN_IDS:
        return # Silent ignore
        
    from database.models import get_bot_stats
    stats = await get_bot_stats()
    
    text = (
        "📊 <b>Bot Statistics</b>\n\n"
        f"👥 Total Users: <b>{stats['total_users']}</b>\n"
        f"📝 Total Posts: <b>{stats['total_posts']}</b>\n"
        f"📅 Posts Today: <b>{stats['posts_today']}</b>"
    )
    await message.answer(text)

@router.message(Command("broadcast"))
async def cmd_broadcast(message: types.Message, command: CommandObject, bot: Bot):
    if str(message.from_user.id) not in ADMIN_IDS:
        return
        
    # Get broadcast content
    text_to_send = command.args
    photo_to_send = message.photo[-1].file_id if message.photo else None
    
    # Require some content
    if not text_to_send and not photo_to_send and not message.caption:
        await message.answer(
            "📢 <b>Broadcast Help</b>\n\n"
            "Use: `/broadcast [Message]`\n"
            "Or send a photo with caption starting with `/broadcast`"
        )
        return

    # If photo with caption
    final_text = text_to_send
    if message.caption and message.caption.startswith("/broadcast"):
         final_text = message.caption.replace("/broadcast", "").strip()
         
    status_msg = await message.answer("⏳ Broadcast started...")
    
    from database.models import get_all_users
    user_ids = await get_all_users()
    
    success = 0
    fail = 0
    
    for uid in user_ids:
        try:
            if photo_to_send:
                await bot.send_photo(chat_id=uid, photo=photo_to_send, caption=final_text)
            else:
                 await bot.send_message(chat_id=uid, text=final_text)
            success += 1
            await asyncio.sleep(0.05) # Rate limit protection
        except Exception:
            fail += 1
            
    await status_msg.edit_text(
        f"📢 <b>Broadcast Complete</b>\n\n"
        f"✅ Sent: {success}\n"
        f"❌ Failed: {fail} (Blocked bot, etc.)"
    )
