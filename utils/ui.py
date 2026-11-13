"""Bitta-xabarli inline interfeys uchun kichik yordamchilar."""
import html
from typing import Optional, Any
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message, ReplyKeyboardRemove

from loader import bot


def safe_html(text: Any) -> str:
    """Xavfsiz HTML matn formatlash (XSS va Parse xatolarini oldini olish)."""
    if text is None:
        return ""
    return html.escape(str(text))


async def dismiss_legacy_reply_keyboard(chat_id: int) -> None:
    """Avvalgi versiyadagi chat-pastki tugmalarni foydalanuvchiga ko'rinmasdan olib tashlaydi."""
    try:
        temporary = await bot.send_message(chat_id, "\u2063", reply_markup=ReplyKeyboardRemove())
        await temporary.delete()
    except Exception:
        pass


async def edit_menu(message: Message, text: str, reply_markup) -> None:
    """Mavjud bot xabarini yangi inline ekran bilan almashtiradi."""
    try:
        await message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest as exc:
        # Bir xil tugmani takror bosganda Telegram xato qaytarmasligi kerak.
        if "message is not modified" not in str(exc).lower():
            raise


async def remember_menu(state, message: Message) -> None:
    """Matn/lokatsiya kiritish bosqichidan keyin qaysi ekran yangilanishini saqlaydi."""
    await state.update_data(menu_message_id=message.message_id)


async def update_menu_after_input(message: Message, state, text: str, reply_markup) -> None:
    """Foydalanuvchi yuborgan ma'lumotni chatni to'ldirmasdan asosiy ekranga aks ettiradi."""
    data = await state.get_data()
    menu_message_id = data.get("menu_message_id")
    try:
        if menu_message_id:
            try:
                await bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=menu_message_id,
                    text=text,
                    reply_markup=reply_markup,
                )
            except TelegramBadRequest as exc:
                if "message is not modified" not in str(exc).lower():
                    # Agar boshqa sabab bilan edit qilib bo'lmasa, yangi xabar qilib yuboramiz
                    await message.answer(text, reply_markup=reply_markup)
        else:
            await message.answer(text, reply_markup=reply_markup)
    finally:
        try:
            await message.delete()
        except Exception:
            pass
