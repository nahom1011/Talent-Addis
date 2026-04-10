from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram import html
from database.models import create_post, add_user, check_rate_limit
from keyboards.builders import get_categories_keyboard, get_content_type_keyboard, get_anonymity_keyboard
from handlers.states import Submission
from utils.config import CHANNEL_ID

router = Router()

@router.message(Command("submit"))
@router.message(F.text == "📤 Submit Talent")
async def cmd_submit(message: types.Message, state: FSMContext):
    # Ensure user is in DB
    await add_user(message.from_user.id, message.from_user.username, message.from_user.full_name)

    # Rate Limit Check
    if await check_rate_limit(message.from_user.id):
        await message.answer("⏳ You are posting too frequently. Please wait 5 minutes between submissions.")
        return


    await message.answer("Select a category for your talent:", reply_markup=get_categories_keyboard())
    await state.set_state(Submission.choosing_category)

# Category Rules Configuration
CATEGORY_RULES = {
    "Singing": {"allowed": ["voice"], "msg": "🎤 Singing Selected\n\nPlease record and send your Voice Message now.\n_Other formats will be rejected._"},
    "Drawing": {"allowed": ["photo"], "msg": "🎨 Drawing Selected\n\nPlease send a Photo of your drawing.\n_Text or Voice submissions are not allowed._"},
    "Writing": {"allowed": ["text"], "msg": "✍️ Writing / Poem Selected\n\nPlease type and send your Text submission below.\n_Photos or Voice messages are not allowed._"},
    "Random Thoughts": {"allowed": ["text", "photo"], "msg": "💭 Random Thoughts Selected\n\nPlease send a Photo or Text sharing your thought.\n_Voice messages are not allowed._"},
    "Photography": {"allowed": ["photo"], "msg": "📷 Photography Selected\n\nPlease send your Photo now.\n_Text or Voice submissions are not allowed._"}
}

# Override keys to match builders.py CATEGORIES exactly if needed. 
# builders.py has: "Singing", "Art", "Comedy", "Dance", "Writing", "Coding", "Others"
# User request added: "Random Thoughts", "Photography". 
# I need to ensure builders.py is updated too or I strictly map what's available.
# Let's assume I should update builders.py later to include these new categories or map "Art" -> Drawing? 
# The user request listed: Singing, Drawing, Writing/Poem, Coding, Random Thoughts, Photography.
# builders.py has: Singing, Art, Comedy, Dance, Writing, Coding, Others.
# I will map strictly to what User Requested. I'll need to update builders.py too.

@router.callback_query(Submission.choosing_category, F.data.startswith("cat_"))
async def process_category(callback: types.CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    if len(parts) < 2: return
    category = parts[1]
    
    # Handle legacy or mapped categories if necessary, but for now trust the button data.
    # If category not in rules, default to generic
    rule = CATEGORY_RULES.get(category, {"allowed": ["text", "photo", "voice"], "msg": f"**{category} Selected\n\nPlease send your submission."})
    
    await state.update_data(category=category)
    
    # Skip content type selection -> Go straight to waiting for content
    await callback.message.edit_text(rule["msg"], parse_mode="Markdown")
    
    # We use a single state for waiting for ANY content, then validate in the handler
    await state.set_state(Submission.waiting_for_content)

# --- TEXT FLOW ---

# --- CONTENT HANDLERS with VALIDATION ---

@router.message(Submission.waiting_for_content, F.text)
async def process_content_text(message: types.Message, state: FSMContext):
    data = await state.get_data()
    category = data.get("category")
    rule = CATEGORY_RULES.get(category)
    
    if "text" not in rule["allowed"]:
        await message.answer(f"❌ This category only accepts: {', '.join(rule['allowed'])}.")
        return

    # Valid Text Submission
    text = message.text
    if len(text) > 1000: text = text[:1000] + "..."
    text = html.quote(text)
    
    # Banned words check
    from database.models import get_banned_words
    banned_words = await get_banned_words()
    if any(word in text.lower() for word in banned_words):
         await message.answer("⚠️ Content contains banned words. Please try again.")
         return

    await state.update_data(content_type="text", caption=text, photo_id=None, voice_id=None)
    await ask_anonymity(message, state)

@router.message(Submission.waiting_for_content, F.photo)
async def process_content_photo(message: types.Message, state: FSMContext):
    data = await state.get_data()
    category = data.get("category")
    rule = CATEGORY_RULES.get(category)
    
    if "photo" not in rule["allowed"]:
        await message.answer(f"❌ This category only accepts: {', '.join(rule['allowed'])}.")
        return

    photo_id = message.photo[-1].file_id
    await state.update_data(content_type="photo", photo_id=photo_id)
    
    await message.answer("Great! Now describe your photo (Caption):")
    await state.set_state(Submission.waiting_for_caption)

@router.message(Submission.waiting_for_content, F.voice)
async def process_content_voice(message: types.Message, state: FSMContext):
    data = await state.get_data()
    category = data.get("category")
    rule = CATEGORY_RULES.get(category)
    
    if "voice" not in rule["allowed"]:
        # Specific error message as requested
        await message.answer(f"❌ This category only accepts: {', '.join(rule['allowed'])}.")
        return
        
    voice_id = message.voice.file_id
    await state.update_data(content_type="voice", voice_id=voice_id)
    
    await message.answer("Awesome! Now write a short description (Caption) for your voice message:")
    await state.set_state(Submission.waiting_for_caption)

# --- CAPTION FOR MEDIA ---
@router.message(Submission.waiting_for_caption, F.text)
async def process_media_caption(message: types.Message, state: FSMContext):
    text = message.text
    if not text: return

    if len(text) > 1000: text = text[:1000] + "..."
    text = html.quote(text)

    from database.models import get_banned_words
    banned_words = await get_banned_words()
    if any(word in text.lower() for word in banned_words):
         await message.answer("⚠️ Description contains banned words. Please try again.")
         return

    await state.update_data(caption=text)
    await ask_anonymity(message, state)

async def ask_anonymity(message: types.Message, state: FSMContext):
    await message.answer(
        "Do you want your username to be displayed publicly?",
        reply_markup=get_anonymity_keyboard()
    )
    await state.set_state(Submission.choosing_anonymity)

@router.callback_query(Submission.choosing_anonymity, F.data.startswith("anon_"))
async def process_anonymity(callback: types.CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    if len(parts) < 2: return
    is_anon_str = parts[1]
    is_anonymous = 1 if is_anon_str == "true" else 0
    await state.update_data(is_anonymous=is_anonymous)
    
    # New Step: Ask for Comments
    # Import locally if needed or rely on top level import
    from keyboards.builders import get_yes_no_keyboard 
    await callback.message.edit_text(
        "💬 Enable Comments?\n\nDo you want to allow users to comment on this post?",
        reply_markup=get_yes_no_keyboard()
    )
    await state.set_state(Submission.choosing_comments_enabled)

@router.callback_query(Submission.choosing_comments_enabled)
async def process_comments_enabled(callback: types.CallbackQuery, state: FSMContext):
    answer = callback.data
    comments_enabled = True if answer == "yes" else False
    await state.update_data(comments_enabled=comments_enabled)
    
    await callback.message.edit_text("Processing submission...")
    await finalize_submission(callback.message, state)

async def finalize_submission(message: types.Message, state: FSMContext):
    data = await state.get_data()
    category = data.get('category')
    content_type = data.get('content_type')
    is_anonymous = data.get('is_anonymous')
    caption = data.get('caption')
    photo_id = data.get('photo_id')
    voice_id = data.get('voice_id')
    comments_enabled = data.get('comments_enabled', True) # Default True
    user = message.chat # Use message.chat or callback user context. 
    # finalize_submission called from callback, so message is the bot's message.
    # We need the Original User. 
    # message.chat is correct because it's a DM with the user.
    # Note: message.from_user if called from message handler is user. 
    # If called from callback, message is the message edited. But chat is still the DM chat.
    # Let's trust message.chat.id is the user.
    
    # We need user details for the DB
    # The 'request' user is who tapped the button.
    # Warning: finalizing from callback means message.from_user is the BOT.
    # We should have stored user info earlier or trust message.chat.
    
    # Let's use the 'user_id' from the chat, assuming private chat.
    user_id = message.chat.id
    username = message.chat.username or "Unknown"
    
    # Save to DB
    post_id = await create_post(user_id, category, content_type, is_anonymous, photo_id, caption, voice_id, comments_enabled)
    
    # Gamification Check
    from database.models import check_and_award_badges
    await check_and_award_badges(user_id)
    
    # Notify Admins
    from keyboards.admin_kb import get_admin_approval_keyboard
    from utils.config import ADMIN_IDS

    # Notify Admins
    from keyboards.admin_kb import get_admin_approval_keyboard
    from utils.config import ADMIN_IDS
    from database.models import get_user_profile

    # Construct Admin Caption
    if is_anonymous:
        # Fetch Fake Profile for Admin Context
        user_profile = await get_user_profile(user_id)
        fake_name = user_profile['fake_name'] if user_profile else "Anonymous"
        fake_id = user_profile['fake_id'] if user_profile else "UNK"
        anon_tag = f"🎭 {fake_name} ({fake_id})"
    else:
        anon_tag = f"@{username} ({user_id})"

    admin_caption = (
        f"🚨 New {content_type.capitalize()} Submission(ID: {post_id})\n\n"
        f"Category: #{category}\n"
        f"User: {anon_tag}\n\n"
        f"📝 {caption}"
    )

    sent_count = 0
    bot = message.bot
    
    for admin_id in ADMIN_IDS:
        try:
            admin_id = admin_id.strip()
            if not admin_id: continue
            
            # Send based on content type
            if content_type == "photo" and photo_id:
                await bot.send_photo(
                    chat_id=admin_id, 
                    photo=photo_id, 
                    caption=admin_caption,
                    reply_markup=get_admin_approval_keyboard(post_id)
                )
            elif content_type == "voice" and voice_id:
                # Send voice, put caption in... voice caption? or separate message?
                # Voice messages support captions.
                await bot.send_voice(
                    chat_id=admin_id,
                    voice=voice_id,
                    caption=admin_caption,
                    reply_markup=get_admin_approval_keyboard(post_id)
                )
            else: # Text
                await bot.send_message(
                    chat_id=admin_id,
                    text=admin_caption,
                    reply_markup=get_admin_approval_keyboard(post_id)
                )
            
            sent_count += 1
        except Exception as e:
            print(f"Failed to send to admin BLVCKTHUNDER: {e}")
            
    if sent_count == 0:
        await message.answer("⚠️ Submission saved, but no admins were notified. Please contact support.")
    else:
        # User confirmation
        # Check anonymity for user feedback
        feedback = "You are posting as your Anonymous Alias." if is_anonymous else "Your username will be shown."
        await message.answer(f"✅ Submission Received!\n{feedback}\nYour post has been sent to admins for approval.")
    
    await state.clear()
