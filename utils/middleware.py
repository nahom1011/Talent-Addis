import time
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from typing import Callable, Dict, Any, Awaitable

class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self, limit: float = 0.5):
        self.limit = limit  # Minimum interval between requests
        self.users: Dict[int, float] = {}

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if not user:
            return await handler(event, data)

        user_id = user.id
        current_time = time.time()
        last_time = self.users.get(user_id, 0)

        if current_time - last_time < self.limit:
            # Throttled
            if isinstance(event, CallbackQuery):
                await event.answer("⏳ Slow down!", show_alert=True)
            return  # Drop the update
        
        self.users[user_id] = current_time
        return await handler(event, data)
