from aiogram import Router, types, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.models import add_comment, get_comments, get_post, add_user, get_comment_by_id, map_message_to_comment, get_comment_id_from_message
from handlers.states import AddingComment

router = Router()

# --- Helper for Pagination ---
# --- Helper for Single Comment Actions ---
def get_single_comment_keyboard(post_id: int, comment_id: int) -> InlineKeyboardMarkup:
    # Just one button to reply to this specific comment
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="↩️ Reply", callback_data=f"reply_single_{post_id}_{comment_id}")
    ]])

# --- Start Input Logic ---
async def start_adding_comment(message: types.Message, state: FSMContext, post_id: int, parent_id: int = None, reply_to_name: str = None, reply_to_content: str = None):
    await state.update_data(post_id=post_id, parent_id=parent_id)
    
    prompt = f"📝 Add Comment to Post #{post_id}"
    if reply_to_name:
        prompt += f"\nReplying to: <b>{reply_to_name}</b>"
        
    if reply_to_content:
        # truncate if too long
        preview = reply_to_content[:50] + "..." if len(reply_to_content) > 50 else reply_to_content
        prompt += f"\n> <i>{preview}</i>"
        
    prompt += "\n\nReply to this message with your text."
    
    await message.answer(prompt)
    await state.set_state(AddingComment.input_comment)

# Deep Link Entry
async def start_adding_comment_from_deep_link(message: types.Message, state: FSMContext, post_id: int):
    await start_adding_comment(message, state, post_id)

# --- Button Handlers ---

@router.callback_query(F.data.startswith("reply_post_"))
async def process_reply_post_callback(callback: types.CallbackQuery, state: FSMContext):
    post_id = int(callback.data.split("_")[2])
    await add_user(callback.from_user.id, callback.from_user.username, callback.from_user.full_name)
    await callback.answer()
    await start_adding_comment(callback.message, state, post_id)

@router.callback_query(F.data.startswith("reply_single_"))
async def process_reply_single_callback(callback: types.CallbackQuery, state: FSMContext):
    # Data: reply_single_{post_id}_{comment_id}
    parts = callback.data.split("_")
    post_id = int(parts[2])
    comment_id = int(parts[3])

    # Fetch comment to get author and content
    comment = await get_comment_by_id(comment_id)
    
    if comment:
        author_name = comment['fake_name'] or "Anonymous"
        content_snippet = comment['content']
        
        await add_user(callback.from_user.id, callback.from_user.username, callback.from_user.full_name)
        await callback.answer()
        await start_adding_comment(callback.message, state, post_id, parent_id=comment_id, reply_to_name=author_name, reply_to_content=content_snippet)
    else:
        await callback.answer("Comment not found.", show_alert=True)


# --- Process Input ---
@router.message(AddingComment.input_comment)
async def process_comment_input(message: types.Message, state: FSMContext):
    data = await state.get_data()
    post_id = data.get('post_id')
    parent_id = data.get('parent_id') # None if top-level
    content = message.text
    
    if not content:
        await message.answer("Please send text.")
        return

    # Quote HTML to avoid breaking formatting
    from aiogram import html
    safe_content = html.quote(content)

    # Add comment
    await add_comment(post_id, message.from_user.id, safe_content, parent_id)
    
    # Update Channel Post Keyboard (Count)
    from handlers.keyboard_utils import update_post_keyboard
    try:
        await update_post_keyboard(message.bot, post_id)
    except Exception:
        pass # Might fail if message too old etc

    await message.answer("✅ Your comment has been added.")
    await state.clear()


# --- Native Reply Handler ---
# Catch-all for text messages that are replies, but not in state
@router.message(F.reply_to_message)
async def handle_native_reply(message: types.Message, state: FSMContext):
    # Check if we are already in a state (don't interfere)
    current_state = await state.get_state()
    if current_state:
        return # Let the state handler deal with it

    # Check if the replied message is a comment
    replied_msg_id = message.reply_to_message.message_id
    chat_id = message.chat.id
    
    comment_id = await get_comment_id_from_message(replied_msg_id, chat_id)
    
    if comment_id:
        # It IS a reply to a comment!
        # Fetch the comment to get post_id and details
        target_comment = await get_comment_by_id(comment_id)
        if target_comment:
            post_id = target_comment['post_id']
            content = message.text
            
            if not content:
                await message.reply("Please send text.")
                return

            # Quote HTML
            from aiogram import html
            safe_content = html.quote(content)

            # Add the comment directly
            await add_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
            
            await add_comment(post_id, message.from_user.id, safe_content, parent_id=comment_id)
            
            # Update keyboard if possible
            from handlers.keyboard_utils import update_post_keyboard
            try:
                await update_post_keyboard(message.bot, post_id)
            except Exception:
                pass

            await message.reply("✅ Reply added via native reply!")
        else:
            await message.reply("❌ The comment you replied to was not found (maybe deleted).")

# --- View Comments Logic ---
async def show_comments(message: types.Message, post_id: int, page: int = 1, edit_mode: bool = False):
    # Fetch 10 comments (users want 10 separated comments)
    comments, total_count = await get_comments(post_id, page=1, limit=10)
    
    # Header Message
    header_text = f"💬 **Comments for Post #{post_id}**"
    header_kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="💬 Reply to Post", callback_data=f"reply_post_{post_id}")
    ]])
    
    if edit_mode:
        await message.delete() 
        await message.answer(header_text, reply_markup=header_kb)
    else:
        await message.answer(header_text, reply_markup=header_kb)

    if not comments:
        await message.answer("No comments yet. Be the first!")
        return
        
    # Send each comment as a separate message
    for c in comments:
        # Display Real Name
        user_display = c['fake_name'] or "Anonymous"
        
        # Helper to get snippet if it is a reply
        content_prefix = ""
        if c['parent_id']:
            parent = await get_comment_by_id(c['parent_id'])
            if parent:
                # Snippet (first 50 chars)
                snippet = parent['content'][:50] + "..." if len(parent['content']) > 50 else parent['content']
                content_prefix = f"↳ Reply to \"{snippet}\"\n"
            else:
                content_prefix = "↳ Reply\n"
        
        # Format: 
        # ↳ Reply to "Snippet..."
        # 💬 Alias: Content
        
        text = f"{content_prefix}<b>{user_display}</b>: {c['content']}"

        # Keyboard for this specific comment
        kb = get_single_comment_keyboard(post_id, c['comment_id'])
        
        sent_msg = await message.answer(text, reply_markup=kb)
        
        # MAP MESSAGE ID TO COMMENT ID
        await map_message_to_comment(sent_msg.message_id, sent_msg.chat.id, c['comment_id'])

async def view_comments_from_deep_link(message: types.Message, post_id: int):
    await show_comments(message, post_id, 1, edit_mode=False)

@router.callback_query(F.data.startswith("view_comments_"))
async def process_view_comments(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    post_id = int(parts[2])
    # page = int(parts[3]) # Unused in this mode
    
    await show_comments(callback.message, post_id, page=1, edit_mode=True)
    await callback.answer()
