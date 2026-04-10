import asyncio
import aiosqlite
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import BufferedInputFile
from database.models import Database, get_user_by_fake_id

router = Router()

# Resource protection for image generation
story_semaphore = asyncio.Semaphore(2)

@router.message(Command("profile"))
@router.message(F.text == "👤 My Profile")
async def cmd_profile(message: types.Message):
    user_id = message.from_user.id
    
    # Ensure user exists and has a fake profile
    from database.models import add_user, check_and_award_badges, get_profile_view_count
    await add_user(user_id, message.from_user.username, message.from_user.full_name)
    
    # Sync Badges (Lazy Load)
    await check_and_award_badges(user_id)
    
    db = await Database.get_db()
    db.row_factory = aiosqlite.Row
    
    # Get stats
    async with db.execute('SELECT COUNT(*) FROM posts WHERE user_id = ?', (user_id,)) as c:
        post_count = (await c.fetchone())[0]
        
    async with db.execute('SELECT category, created_at FROM posts WHERE user_id = ? ORDER BY created_at DESC LIMIT 1', (user_id,)) as c:
        latest_row = await c.fetchone()
        
    async with db.execute('SELECT fake_name, fake_id FROM users WHERE user_id = ?', (user_id,)) as c:
        user_row = await c.fetchone()
            
    # Get reaction stats & view count
    from database.models import get_user_total_reactions
    reaction_stats = await get_user_total_reactions(user_id)
    view_count = await get_profile_view_count(user_id)
    
    fake_name = user_row['fake_name'] if user_row and user_row['fake_name'] else "Not Generated"
    fake_id = user_row['fake_id'] if user_row and user_row['fake_id'] else "N/A"
    
    text = f"👤 <b>User Profile</b>: {message.from_user.full_name}\n"
    text += f"🎭 <b>Anonymous Alias</b>: {fake_name}\n"
    text += f"🆔 <b>Secret ID</b>: {fake_id}\n\n"
    
    # Badges
    from database.models import get_user_badges
    badges = await get_user_badges(user_id)
    if badges:
        text += f"🏅 <b>Badges</b>: {', '.join(badges)}\n\n"

    text += f"📊 <b>Total Submissions</b>: {post_count}\n"
    text += f"👀 <b>Total Profile Views</b>: {view_count}\n"
    
    if reaction_stats:
        stats_line = "  ".join([f"{emoji} {count}" for emoji, count in reaction_stats.items()])
        text += f"⭐ <b>Reactions Received</b>: {stats_line}\n"
    
    if latest_row:
        text += f"🆕 <b>Latest Submission</b>: {latest_row[0]} ({latest_row[1]})"
    else:
        text += "❌ No submissions yet."
        
    await message.answer(text)

@router.message(Command("story"))
@router.message(F.text == "📱 Story Card")
async def cmd_story(message: types.Message):
    user_id = message.from_user.id
    
    async with story_semaphore:
        from database.models import get_user_profile
        user = await get_user_profile(user_id)
        
        if not user:
            await message.answer("❌ Please use /start first.")
            return
            
        msg = await message.answer("🎨 Generating your Story Card...")
        
        from utils.image_generator import generate_story_image
        
        fake_name = user['fake_name'] or "Anonymous"
        fake_id = user['fake_id'] or "UNK"
        
        # CPU intensive work
        img_buffer = await asyncio.to_thread(generate_story_image, fake_name, fake_id)
        input_file = BufferedInputFile(img_buffer.read(), filename="story.png")
        
        await message.answer_photo(photo=input_file, caption="📱 <b>Your Story Card</b>\n\nForward this to your Saved Messages and post it to your Story!")
        await msg.delete()



@router.message(Command("top"))
@router.message(Command("leaderboard"))
@router.message(F.text == "🏆 Leaderboard")
async def cmd_leaderboard(message: types.Message):
    from database.models import get_leaderboard
    
    leaders = await get_leaderboard()
    
    if not leaders:
        await message.answer("🏆 <b>Leaderboard</b>\n\nNot enough data yet! Be the first to get reactions.")
        return
    
    text = "🏆 <b>All-Time Top Talent</b>\n(Ranked by Total Reactions)\n\n"
    
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    
    for idx, row in enumerate(leaders):
        medal = medals[idx] if idx < len(medals) else "•"
        name = row['fake_name'] if row['fake_name'] else "Anonymous"
        reactions = row['total_reactions']
        
        text += f"{medal} <b>{name}</b>: {reactions} reactions\n"
        
    await message.answer(text)

async def show_public_profile(message: types.Message, fake_id: str):
    # Public View of a Profile
    from database.models import get_user_by_fake_id, aiosqlite, DB_PATH, record_profile_view
    user_row = await get_user_by_fake_id(fake_id)
    
    if not user_row:
        await message.answer("❌ Profile not found.")
        return
        
    target_user_id = user_row['user_id']
    target_fake_name = user_row['fake_name'] or "Anonymous"
    viewer_id = message.from_user.id
    
    # Check if viewing own profile or if viewer is admin
    from utils.config import ADMIN_IDS
    is_admin = str(viewer_id) in ADMIN_IDS
    
    if target_user_id != viewer_id and not is_admin:
        # Record the view (deduplicated by 24h in DB via UNIQUE constraint)
        await record_profile_view(viewer_id, target_user_id)
    
    if target_user_id == viewer_id:
        await message.answer("👋 This is your own public profile!")
        
    async with aiosqlite.connect(DB_PATH) as db:
        # Get post count
        cursor = await db.execute('SELECT COUNT(*) FROM posts WHERE user_id = ? AND status="approved"', (target_user_id,))
        count_row = await cursor.fetchone()
        post_count = count_row[0]
        
    from database.models import get_user_total_reactions, get_user_badges
    
    # Stats
    reaction_stats = await get_user_total_reactions(target_user_id)
    badges = await get_user_badges(target_user_id)
    
    text = f"👤 **Public Profile**\n\n"
    text += f"🎭 **Alias**: {target_fake_name}\n"
    text += f"🆔 **Secret ID**: {fake_id}\n\n"
    
    if badges:
        text += f"🏅 **Badges**: {', '.join(badges)}\n\n"
        
    text += f"📊 **Approved Submissions**: {post_count}\n"
    
    if reaction_stats:
        stats_line = "  ".join([f"{emoji} {count}" for emoji, count in reaction_stats.items()])
        text += f"⭐ **Reactions**: {stats_line}\n"
    else:
         text += f"⭐ **Reactions**: No reactions yet.\n"
    
    # Keyboard with Request ID
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    markup = InlineKeyboardMarkup(inline_keyboard=[])
    if target_user_id != viewer_id:
        markup.inline_keyboard.append([InlineKeyboardButton(text="🔗 Request Telegram ID", callback_data=f"req_id_{target_user_id}")])
         
    await message.answer(text, reply_markup=markup if target_user_id != viewer_id else None)

@router.callback_query(F.data.startswith("req_id_"))
async def process_request_id(callback: types.CallbackQuery):
    target_user_id = int(callback.data.split("_")[2])
    viewer_id = callback.from_user.id
    
    # Get viewer's fake profile for anonymity info
    from database.models import get_user_profile
    viewer_profile = await get_user_profile(viewer_id)
    viewer_alias = viewer_profile['fake_name'] if viewer_profile else "Anonymous"
    
    try:
        # Notify the author
        from main import bot
        notif_text = f"🔔 **Telegram ID Request!**\n\n"
        notif_text += f"🎭 Someone (Alias: **{viewer_alias}**) viewed your profile and wants to connect!\n\n"
        notif_text += f"_If you click the button below, your Telegram ID will be shared with them._"
        
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Accept & Share My ID", callback_data=f"share_id_{viewer_id}")]
        ])
        
        await bot.send_message(target_user_id, notif_text, reply_markup=markup)
        await callback.answer("✅ Request sent! The author has been notified.", show_alert=True)
    except Exception as e:
        await callback.answer("❌ Could not send request. Author might have blocked the bot.", show_alert=True)

@router.callback_query(F.data.startswith("share_id_"))
async def process_share_id(callback: types.CallbackQuery):
    requester_id = int(callback.data.split("_")[2])
    author_name = callback.from_user.full_name
    author_username = f"@{callback.from_user.username}" if callback.from_user.username else "No Username"
    
    try:
        # Notify the requester
        from main import bot
        notif_text = f"🤝 **Request Accepted!**\n\n"
        notif_text += f"User has accepted your request to connect.\n\n"
        notif_text += f"👤 **Name**: {author_name}\n"
        notif_text += f"🔗 **Telegram**: {author_username}\n\n"
        notif_text += f"You can now reach out to them! 🚀"
        
        await bot.send_message(requester_id, notif_text)
        await callback.message.edit_text("✅ Your Telegram ID has been shared with the requester!")
        await callback.answer()
    except Exception:
        await callback.answer("❌ Could not share ID. Requester might have blocked the bot.", show_alert=True)
