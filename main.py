# main.py
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
import asyncio, logging, sys

from utils.config import BOT_TOKEN
from database.models import init_db
from handlers import common, submission, secondary

# Initialize Bot and Dispatcher globally
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# Middleware
from utils.middleware import ThrottlingMiddleware
dp.message.middleware(ThrottlingMiddleware(limit=0.5))
dp.callback_query.middleware(ThrottlingMiddleware(limit=0.2))

async def cleanup_task():
    """Background task to clean up old data."""
    from database.models import cleanup_mapping_table
    while True:
        try:
            await cleanup_mapping_table(days=1)
            # await cleanup_event_queue() # If needed later
            print("Background cleanup completed.")
        except Exception as e:
            print(f"Cleanup task failed: {e}")
        await asyncio.sleep(24 * 3600)  # Run every 24h

async def main():
    if not BOT_TOKEN:
        print("Error: BOT_TOKEN not found inside .env file.")
        return

    # Initialize Database
    await init_db()

    # Register Routers
    from handlers import submission, admin, common, messaging, reactions, secondary, requests, comments, moderation, dashboard, portfolio
    
    dp.include_router(common.router)
    dp.include_router(submission.router)
    dp.include_router(admin.router)
    dp.include_router(messaging.router)
    dp.include_router(reactions.router)
    dp.include_router(secondary.router)
    dp.include_router(requests.router)
    dp.include_router(comments.router)
    dp.include_router(moderation.router)
    dp.include_router(dashboard.router)
    dp.include_router(portfolio.router)
    
    # Start periodic tasks
    asyncio.create_task(cleanup_task())
    
    print("Bot started polling...")
    try:
        await dp.start_polling(bot)
    finally:
        from database.models import Database
        await Database.close()
        await bot.session.close()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
