from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.models import submit_report

# States for Report Flow
class Report(StatesGroup):
    choosing_reason = State()

router = Router()

# Reasons for reporting
REPORT_REASONS = {
    "spam": "Spam/Scam",
    "offensive": "Offensive/Hate Speech",
    "inappropriate": "Inappropriate Content",
    "other": "Other"
}

def get_report_reasons_keyboard(post_id):
    buttons = []
    for key, label in REPORT_REASONS.items():
        buttons.append([InlineKeyboardButton(text=label, callback_data=f"report_{post_id}_{key}")])
    buttons.append([InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_report")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

async def start_reporting_from_deep_link(message: types.Message, state: FSMContext, post_id: int):
    await message.answer(
        "🚨 Report Post\n\nWhy do you want to report this post?",
        reply_markup=get_report_reasons_keyboard(post_id)
    )

# @router.callback_query(F.data.startswith("start_report_"))
# async def start_report_flow(callback: types.CallbackQuery, state: FSMContext):
#    # Legacy/Deprecated
#    pass

@router.callback_query(F.data.startswith("report_"))
async def process_report_reason(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    post_id = int(parts[1])
    reason_key = parts[2]
    
    reason_text = REPORT_REASONS.get(reason_key, "Other")
    reporter_id = callback.from_user.id
    
    # Save report
    await submit_report(post_id, reporter_id, reason_text)
    
    # Notify Admins
    from utils.config import ADMIN_IDS
    from main import bot
    from database.models import get_post
    import html
    
    post = await get_post(post_id)
    admin_msg = (
        f"🚨 <b>New Report Submitted</b>\n\n"
        f"<b>Post ID:</b> {post_id}\n"
        f"<b>Reason:</b> {html.escape(reason_text)}\n"
        f"<b>Reporter:</b> {callback.from_user.id} (@{callback.from_user.username or 'N/A'})\n\n"
        f"<b>Post Caption:</b>\n<i>{html.escape(post['caption'] if post else 'N/A')}</i>"
    )
    
    for admin_id in ADMIN_IDS:
        try:
            if admin_id:
                await bot.send_message(chat_id=admin_id, text=admin_msg)
        except Exception as e:
            print(f"Failed to notify admin {admin_id}: {e}")

    await callback.message.edit_text("✅ Report Received\n\nThank you for helping keep the community safe. Moderators will review this shortly.")
    await callback.answer("Report submitted.")

@router.callback_query(F.data == "cancel_report")
async def cancel_report(callback: types.CallbackQuery):
    await callback.message.delete()
    await callback.answer("Cancelled")
