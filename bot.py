import asyncio
import logging
import sys

# Windows konsolida UTF-8 kodlashni to'g'rilash
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from config import RESTAURANT_NAME
from loader import bot, dp
import database as db
from utils.scheduler import setup_scheduler

# Handler routerlarini import qilish
from handlers.common import router as common_router
from handlers.worker_handlers import router as worker_router
from handlers.admin_roles import router as roles_router
from handlers.admin_workers import router as workers_router
from handlers.admin_finance import router as finance_router
from handlers.admin_attendance import router as attendance_router
from handlers.admin_settings import router as settings_router
from handlers.reports import router as reports_router

# Logging sozlamalari
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("smena_bot")


async def main():
    logger.info(f"🚀 Smena boti ishga tushmoqda (restoran: {RESTAURANT_NAME})...")

    # 1. Ma'lumotlar bazasi poolini yaratish va jadvallarni initsializatsiya qilish
    await db.create_pool()
    await db.init_db()

    # 2. Routerlarni dispatcherga ulash
    dp.include_router(common_router)
    dp.include_router(worker_router)
    dp.include_router(roles_router)
    dp.include_router(workers_router)
    dp.include_router(finance_router)
    dp.include_router(attendance_router)
    dp.include_router(settings_router)
    dp.include_router(reports_router)

    # 3. Schedulerni ishga tushirish
    scheduler = setup_scheduler()
    scheduler.start()
    logger.info("⏰ APScheduler eslatmalari faollashtirildi.")

    # 4. Bot webhooklarni tozalash va pollingni boshlash
    # Tarmoq uzilib qolgan paytda kelgan ariza/davomat xabarlarini yo'qotmaymiz.
    await bot.delete_webhook(drop_pending_updates=False)
    logger.info("✅ Bot muvaffaqiyatli ishga tushdi va xabarlarni qabul qilishga tayyor!")

    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown()
        await db.close_pool()
        await bot.session.close()
        logger.info("🛑 Bot to'xtatildi.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot qo'lda to'xtatildi.")
