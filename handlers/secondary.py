import asyncio
import aiosqlite
from aiogram import Router, types, F
from aiogram.filters import Command
from database.models import Database, get_user_by_fake_id

router = Router()

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
    from database.models import get_user_by_fake_id, Database, record_profile_view
    user_row = await get_user_by_fake_id(fake_id)
    
    if not user_row:
        await message.answer("❌ Profile not found.\nThis user or submission profile is not available.")
        return
        
    target_user_id = user_row['user_id']
    target_fake_name = user_row['fake_name'] or "Anonymous"
    target_fake_id = user_row['fake_id'] or fake_id
    viewer_id = message.from_user.id
    
    # Check if viewing own profile or if viewer is admin
    from utils.config import ADMIN_IDS
    is_admin = str(viewer_id) in ADMIN_IDS
    
    if target_user_id != viewer_id and not is_admin:
        # Record the view (deduplicated by 24h in DB via UNIQUE constraint)
        await record_profile_view(viewer_id, target_user_id)
    
    if target_user_id == viewer_id:
        await message.answer("👋 This is your own public profile!")
        
    db = await Database.get_db()
    cursor = await db.execute('SELECT COUNT(*) FROM posts WHERE user_id = ? AND status="approved"', (target_user_id,))
    count_row = await cursor.fetchone()
    post_count = count_row[0] if count_row else 0
        
    from database.models import get_user_total_reactions, get_user_badges
    
    # Stats
    reaction_stats = await get_user_total_reactions(target_user_id)
    badges = await get_user_badges(target_user_id)
    
    text = f"👤 <b>Public Profile</b>\n\n"
    text += f"🎭 <b>Alias</b>: {target_fake_name}\n"
    text += f"🆔 <b>Secret ID</b>: {target_fake_id}\n\n"
    
    if badges:
        text += f"🏅 <b>Badges</b>: {', '.join(badges)}\n\n"
        
    text += f"📊 <b>Approved Submissions</b>: {post_count}\n"
    
    if reaction_stats:
        stats_line = "  ".join([f"{emoji} {count}" for emoji, count in reaction_stats.items()])
        text += f"⭐ <b>Reactions</b>: {stats_line}\n"
    else:
        text += f"⭐ <b>Reactions</b>: No reactions yet.\n"
    
    # Keyboard with Request ID
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    markup = InlineKeyboardMarkup(inline_keyboard=[])
    if target_user_id != viewer_id:
        markup.inline_keyboard.append([InlineKeyboardButton(text="🔗 Request Telegram ID", callback_data=f"req_id_{target_fake_id}")])
         
    await message.answer(text, reply_markup=markup if target_user_id != viewer_id else None)
