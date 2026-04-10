from aiogram import Router, types, F
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.fsm.context import FSMContext
from database.models import add_user

router = Router()

@router.message(CommandStart())
async def cmd_start(message: types.Message, command: CommandObject, state: FSMContext):
    # Register/Update user
    await add_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
    
    args = command.args if command else None
    
    if args:
        if args.startswith("comment_"):
            try:
                post_id = int(args.split("_")[1])
                from handlers.comments import start_adding_comment_from_deep_link
                await start_adding_comment_from_deep_link(message, state, post_id)
                return
            except Exception:
                await message.answer("❌ Invalid comment link.")
        elif args.startswith("view_comments_"):
            try:
                parts = args.split("_")
                post_id = int(parts[2])
                from handlers.comments import view_comments_from_deep_link
                await view_comments_from_deep_link(message, post_id)
                return
            except Exception:
                await message.answer("❌ Invalid view link.")
        elif args.startswith("report_"):
            try:
                post_id = int(args.split("_")[1])
                from handlers.moderation import start_reporting_from_deep_link
                await start_reporting_from_deep_link(message, state, post_id)
                return
            except Exception:
                await message.answer("❌ Invalid report link.")
        elif args.startswith("profile_"):
             try:
                fake_id = args.split("_")[1]
                from handlers.secondary import show_public_profile
                await show_public_profile(message, fake_id)
                return
             except Exception:
                await message.answer("❌ Invalid profile link.")

    from keyboards.builders import get_main_menu_keyboard
    await message.answer(
      "🎉 Welcome to Talent Addis! 👋\n\n"
"Unleash your skills and shine in front of the whole university! ✨\n"
"🎨 Use /submit to share your talent.\n"
"📖 Use /help to explore all commands and tips.\n\n"
"Let’s make your talent go viral! 🚀",
        reply_markup=get_main_menu_keyboard()
    )

@router.message(Command("help"))
@router.message(F.text == "❓ Help")
async def cmd_help(message: types.Message):
    from keyboards.builders import get_main_menu_keyboard
    await message.answer(
        "🤖 Help Menu\n\n"
        "Welcome!\n"
        "This bot lets you submit talent, explore content, and build a public profile.\n\n"
        "📤 Submissions\n\n"
        "🔹 /submit — Submit your talent\n"
        "🔹 /dashboard — View your submissions\n\n"
        "👤 Profile & Sharing\n\n"
        "🔹 /profile — View your profile & badges\n"
        "🔹 /story — Generate a story card\n"
        "🔹 /portfolio — Download your PDF folder\n\n"
        "🔍 Discover\n\n"
        "🔹 /top — View leaderboard\n\n"
        "💡 Tip: Use the menu buttons below for faster navigation!",
        reply_markup=get_main_menu_keyboard()
    )
