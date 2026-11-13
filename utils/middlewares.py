"""Umumiy xavfsizlik middleware'lari."""
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery

import database as db


class AdminOnlyCallbackMiddleware(BaseMiddleware):
    """Admin routerlaridagi callback'larni server tomonda himoya qiladi.

    Tugma boshqa foydalanuvchiga forward qilingan yoki eski xabardan bosilgan
    bo'lsa ham, callback_data'ning o'zi ruxsat hisoblanmaydi.
    """

    async def __call__(
        self,
        handler: Callable[[CallbackQuery, Dict[str, Any]], Awaitable[Any]],
        event: CallbackQuery,
        data: Dict[str, Any],
    ) -> Any:
        if not await db.is_admin_or_superadmin(event.from_user.id):
            await event.answer("Bu bo'lim faqat adminlar uchun.", show_alert=True)
            return None
        return await handler(event, data)
