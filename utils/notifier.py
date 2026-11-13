import logging
from typing import Optional
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup
from loader import bot
import database as db
from config import RESTAURANT_NAME, format_currency
from utils.ui import safe_html

logger = logging.getLogger(__name__)


async def notify_all_admins(text: str, reply_markup: Optional[InlineKeyboardMarkup] = None, exclude_id: Optional[int] = None):
    """Barcha admin va superadminlarga xabar yuboradi."""
    admin_ids = await db.get_all_admin_tg_ids()
    for admin_id in admin_ids:
        if exclude_id and admin_id == exclude_id:
            continue
        try:
            await bot.send_message(
                chat_id=admin_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.warning(f"Admin {admin_id} ga xabar yuborishda xatolik: {e}")

    # Agar log guruhi sozlangan bo'lsa, guruhga ham yuboriladi
    settings = await db.get_settings()
    group_id = settings.get("work_log_group_id")
    if group_id and group_id != 0:
        try:
            await bot.send_message(
                chat_id=group_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.warning(f"Guruh {group_id} ga xabar yuborishda xatolik: {e}")


async def notify_finance_operation(
    worker_name: str,
    role_name: str,
    transaction_type: str, # 'advance' yoki 'settlement'
    amount: float,
    admin_name: str,
    datetime_str: str,
    comment: Optional[str] = None,
    extra_info: Optional[str] = None,
):
    """
    Kimgadir pul berilganda (Avans yoki Raschyot) BARCHA adminlarga
    va log guruhiga darhol to'liq va chiroyli hisobot yuboradi.
    """
    if transaction_type == "advance":
        header = "💸 <b>#AVANS_BERILDI</b>"
        type_str = "💵 Avans"
    elif transaction_type == "settlement":
        header = "💳 <b>#RASCHYOT_QILINDI</b>"
        type_str = "✅ Oylik Raschyot"
    else:
        header = "💰 <b>#MOLIYA_AMALIYOTI</b>"
        type_str = "To'lov"

    safe_w_name = safe_html(worker_name)
    safe_r_name = safe_html(role_name or "Xodim")
    safe_a_name = safe_html(admin_name)

    msg = (
        f"{header}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Xodim:</b> {safe_w_name} (<i>{safe_r_name}</i>)\n"
        f"💰 <b>Summa:</b> <b>{format_currency(amount)}</b>\n"
        f"📝 <b>Turi:</b> {type_str}\n"
        f"👨‍💼 <b>Bergan admin:</b> {safe_a_name}\n"
        f"🕑 <b>Vaqt:</b> {datetime_str}\n"
    )

    if extra_info:
        msg += f"📊 <b>Hisob-kitob:</b> {safe_html(extra_info)}\n"

    if comment:
        msg += f"💬 <b>Izoh:</b> <i>{safe_html(comment)}</i>\n"

    msg += "━━━━━━━━━━━━━━━━━━━━"

    await notify_all_admins(msg)


async def notify_attendance_event(
    worker_name: str,
    role_name: str,
    event_type: str, # 'in', 'out', 'rest'
    time_str: str,
    distance_m: Optional[float] = None,
    work_duration_str: Optional[str] = None,
):
    """Xodimning keldi-ketdi amallari haqida adminlarga xabar."""
    safe_w_name = safe_html(worker_name)
    safe_r_name = safe_html(role_name or "Xodim")

    if event_type == "in":
        dist_text = f" (📍 Masofa: {int(distance_m)}m)" if distance_m is not None else ""
        msg = (
            f"🟢 <b>#ISHGA_KELDI</b>\n"
            f"👤 <b>Xodim:</b> {safe_w_name} (<i>{safe_r_name}</i>)\n"
            f"⏰ <b>Kelgan vaqti:</b> {time_str}{dist_text}\n"
            f"🏢 <b>Joy:</b> {safe_html(RESTAURANT_NAME)}"
        )
    elif event_type == "out":
        duration_text = f"\n⏱ <b>Bugun ishladi:</b> {work_duration_str}" if work_duration_str else ""
        msg = (
            f"🔴 <b>#ISHDAN_KETDI</b>\n"
            f"👤 <b>Xodim:</b> {safe_w_name} (<i>{safe_r_name}</i>)\n"
            f"⏰ <b>Ketgan vaqti:</b> {time_str}{duration_text}"
        )
    elif event_type == "rest":
        msg = (
            f"🌙 <b>#DAM_OLISH</b>\n"
            f"👤 <b>Xodim:</b> {safe_w_name} (<i>{safe_r_name}</i>)\n"
            f"📅 <b>Bugun:</b> Dam olish kuni deb belgilandi."
        )
    else:
        return

    await notify_all_admins(msg)
