from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.models import aiosqlite, DB_PATH
from utils.time_utils import get_time_ago

router = Router()

@router.message(Command("my_submissions"))
@router.message(Command("dashboard"))
@router.message(F.text == "📂 Dashboard")
async def cmd_dashboard(message: types.Message):
    await show_dashboard_page(message, 1)

async def show_dashboard_page(message: types.Message | types.CallbackQuery, page: int):
    user_id = message.from_user.id
    limit = 5
    offset = (page - 1) * limit
    
    from database.models import Database
    db = await Database.get_db()
    db.row_factory = aiosqlite.Row
    
    # Get total count
    async with db.execute('SELECT COUNT(*) FROM posts WHERE user_id = ?', (user_id,)) as cursor:
        res = await cursor.fetchone()
        total_count = res[0] if res else 0

    # Get page posts
    async with db.execute('''
        SELECT * FROM posts 
        WHERE user_id = ? 
        ORDER BY created_at DESC 
        LIMIT ? OFFSET ?
    ''', (user_id, limit, offset)) as cursor:
        posts = await cursor.fetchall()
            
    if not posts:
        msg_text = "📭 You haven't made any submissions yet."
        if isinstance(message, types.CallbackQuery):
            await message.message.edit_text(msg_text)
        else:
            await message.answer(msg_text)
        return

    text = f"📂 <b>My Submissions (Page {page})</b>\n\n"
    buttons = []
    
    for post in posts:
        status_emoji = {
            "pending": "⏳",
            "approved": "✅",
            "rejected": "❌",
            "deleted_by_user": "🗑️",
            "deleted_by_moderation": "⛔"
        }.get(post['status'], "❓")
        
        caption_preview = (post['caption'][:30] + "...") if post['caption'] else "No Caption"
        text += f"{status_emoji} <b>{post['category']}</b> (ID: {post['post_id']})\n"
        text += f"└ <i>{caption_preview}</i>\n\n"
        
        # Action Button for Active Posts
        if post['status'] not in ['deleted_by_user', 'deleted_by_moderation', 'deleted']:
            buttons.append([InlineKeyboardButton(
                text=f"🗑️ Delete #{post['post_id']}", 
                callback_data=f"del_init_{post['post_id']}"
            )])
            
    # Pagination Row
    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton(text="⬅️ Previous", callback_data=f"dash_page_{page-1}"))
    if total_count > offset + limit:
        nav_row.append(InlineKeyboardButton(text="Next ➡️", callback_data=f"dash_page_{page+1}"))
    
    if nav_row:
        buttons.append(nav_row)
        
    markup = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    if isinstance(message, types.CallbackQuery):
        await message.message.edit_text(text, reply_markup=markup)
    else:
        await message.answer(text, reply_markup=markup)

@router.callback_query(F.data.startswith("dash_page_"))
async def process_dash_pagination(callback: types.CallbackQuery):
    page = int(callback.data.split("_")[2])
    await show_dashboard_page(callback, page)
    await callback.answer()

@router.callback_query(F.data.startswith("del_init_"))
async def process_delete_init(callback: types.CallbackQuery):
    post_id = int(callback.data.split("_")[2])
    
    # Ask for confirmation
    confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Yes, Delete", callback_data=f"del_confirm_{post_id}"),
            InlineKeyboardButton(text="❌ Cancel", callback_data=f"del_cancel")
        ]
    ])
    
    await callback.message.reply(
        f"⚠️ Delete Submission #{post_id}?\n\n"
        "Are you sure you want to delete this submission?\n"
        "This action cannot be undone.",
        reply_markup=confirm_kb
    )
    await callback.answer()

@router.callback_query(F.data == "del_cancel")
async def process_delete_cancel(callback: types.CallbackQuery):
    await callback.message.delete()
    await callback.answer("Cancelled")

@router.callback_query(F.data.startswith("del_confirm_"))
async def process_delete_confirm(callback: types.CallbackQuery):
    post_id = int(callback.data.split("_")[2])
    user_id = callback.from_user.id
    
    from database.models import get_post, update_post_status
    post = await get_post(post_id)
    
    if not post:
        await callback.answer("❌ Post not found.")
        await callback.message.delete()
        return
        
    if post['user_id'] != user_id:
        await callback.answer("⚠️ Not your post.")
        await callback.message.delete()
        return

    # If Approved, delete from Channel
    if post['status'] == 'approved' and post['message_id']:
        try:
            from utils.config import CHANNEL_ID
            await callback.bot.delete_message(chat_id=CHANNEL_ID, message_id=int(post['message_id']))
        except Exception:
            pass # Message might already be deleted or too old
            
    # Mark user deleted
    await update_post_status(post_id, 'deleted_by_user')
    
    await callback.message.edit_text(f"✅ Your submission \"{post['category']}\" (#{post_id}) has been deleted successfully.", reply_markup=None)
    await callback.answer("Submission deleted.")
