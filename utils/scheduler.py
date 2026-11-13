import datetime
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from aiogram.types import BufferedInputFile

import database as db
from config import MONTH_NAMES, RESTAURANT_NAME, TIMEZONE, monthly_report_filename
from loader import bot
from keyboards.inline_keyboards import get_worker_main_menu
from utils.excel_generator import generate_monthly_report_excel
from utils.ui import safe_html

logger = logging.getLogger(__name__)


async def send_morning_reminders():
    """Ertalabki ishga kelish eslatmasi."""
    try:
        now = datetime.datetime.now(TIMEZONE)
        today = now.date()

        summary = await db.get_today_attendance_summary(today)
        absent_workers = summary["absent"]

        for w in absent_workers:
            if w.get("tg_id"):
                try:
                    await bot.send_message(
                        chat_id=w["tg_id"],
                        text=(
                            f"☀️ <b>Xayrli tong, {safe_html(w['full_name'])}!</b>\n\n"
                            "Ishga yetib kelgach, quyidagi <b>🟢 Ishga keldim</b> tugmasini bosib "
                            "lokatsiya yuborishni unutmang!\n"
                            "Unumli kun tilaymiz! 🌟"
                        ),
                        reply_markup=get_worker_main_menu(),
                        parse_mode="HTML"
                    )
                except Exception:
                    pass
        logger.info("Ertalabki eslatmalar yuborildi.")
    except Exception as e:
        logger.error(f"Ertalabki eslatmalarda xatolik: {e}")


async def send_monthly_auto_report():
    """Har oyning 1-kunida o'tgan oyning tayyor Excel hisobotini barcha adminlarga va guruhga yuboradi."""
    try:
        now = datetime.datetime.now(TIMEZONE)
        prev_month = 12 if now.month == 1 else now.month - 1
        prev_year = now.year - 1 if now.month == 1 else now.year
        month_name = MONTH_NAMES.get(prev_month, str(prev_month))

        excel_buf = await generate_monthly_report_excel(prev_year, prev_month)
        excel_bytes = excel_buf.getvalue()
        file_name = monthly_report_filename(month_name, prev_year)

        caption = (
            f"📊 <b>{safe_html(RESTAURANT_NAME)} — OYLIK YAKUNIY HISOBOT ({month_name} {prev_year})</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Hurmatli ma'muriyat, o'tgan oy yakunlari bo'yicha to'liq davomat va moliya Excel hisoboti tayyorlandi.\n"
            f"📁 <i>Hujjat ilova qilindi.</i>"
        )

        admin_ids = await db.get_all_admin_tg_ids()
        for a_id in admin_ids:
            try:
                doc = BufferedInputFile(excel_bytes, filename=file_name)
                await bot.send_document(chat_id=a_id, document=doc, caption=caption, parse_mode="HTML")
            except Exception as e:
                logger.warning(f"Admin {a_id} ga oylik hisobot yuborishda xatolik: {e}")

        settings = await db.get_settings()
        group_id = settings.get("work_log_group_id")
        if group_id and group_id != 0:
            try:
                doc = BufferedInputFile(excel_bytes, filename=file_name)
                await bot.send_document(chat_id=group_id, document=doc, caption=caption, parse_mode="HTML")
            except Exception as e:
                logger.warning(f"Guruh {group_id} ga oylik hisobot yuborishda xatolik: {e}")

        logger.info(f"Oylik avtomatik hisobot ({month_name} {prev_year}) muvaffaqiyatli tarqatildi.")
    except Exception as e:
        logger.error(f"Oylik avtomatik hisobot yaratishda xatolik: {e}")


def setup_scheduler() -> AsyncIOScheduler:
    """Rejalashtiruvchi sozlamalari."""
    scheduler = AsyncIOScheduler(timezone=TIMEZONE)

    # Har kuni ertalab 09:00 da eslatma
    scheduler.add_job(
        send_morning_reminders,
        trigger=CronTrigger(hour=9, minute=0, timezone=TIMEZONE),
        id="morning_reminder",
        replace_existing=True,
    )

    # Har oyning 1-kunida soat 09:00 da o'tgan oy hisobotini avtomatik yuborish
    scheduler.add_job(
        send_monthly_auto_report,
        trigger=CronTrigger(day=1, hour=9, minute=0, timezone=TIMEZONE),
        id="monthly_auto_report",
        replace_existing=True,
    )

    return scheduler
