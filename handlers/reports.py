import datetime
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

import database as db
from config import RESTAURANT_NAME, TIMEZONE, format_currency, format_hours_mins, monthly_report_filename
from utils.excel_generator import generate_monthly_report_excel
from keyboards.inline_keyboards import get_back_keyboard
from utils.ui import edit_menu, safe_html
from utils.middlewares import AdminOnlyCallbackMiddleware

logger = logging.getLogger(__name__)
router = Router(name="reports_router")
router.callback_query.middleware(AdminOnlyCallbackMiddleware())


@router.callback_query(F.data == "admin:reports")
async def cb_reports_menu(callback: CallbackQuery, state: FSMContext):
    """Hisobotlar menyusi — oyni tanlash."""
    await state.clear()
    if not await db.is_admin_or_superadmin(callback.from_user.id):
        return

    now = datetime.datetime.now(TIMEZONE)
    current_month = now.month
    current_year = now.year

    prev_month = 12 if current_month == 1 else current_month - 1
    prev_year = current_year - 1 if current_month == 1 else current_year

    month_names = {
        1: "Yanvar", 2: "Fevral", 3: "Mart", 4: "Aprel",
        5: "May", 6: "Iyun", 7: "Iyul", 8: "Avgust",
        9: "Sentyabr", 10: "Oktyabr", 11: "Noyabr", 12: "Dekabr"
    }

    kb = [
        [
            InlineKeyboardButton(
                text=f"📅 {month_names[current_month]} {current_year} (Joriy oy)",
                callback_data=f"excel_rep_{current_year}_{current_month}"
            )
        ],
        [
            InlineKeyboardButton(
                text=f"📁 {month_names[prev_month]} {prev_year} (O'tgan oy)",
                callback_data=f"excel_rep_{prev_year}_{prev_month}"
            )
        ]
    ]

    kb.append([InlineKeyboardButton(text="⬅️ Bosh menyu", callback_data="admin:home")])
    await edit_menu(
        callback.message,
        "📊 <b>OYLIK DAVOMAT VA MOLIYA HISOBOTI (EXCEL)</b>\n\n"
        "Qaysi oy uchun Excel hisobot yuklab olmoqchisiz? Tanlang:",
        InlineKeyboardMarkup(inline_keyboard=kb)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("excel_rep_"))
async def cb_download_excel_report(callback: CallbackQuery):
    """Excel hisobotni generatsiya qilib yuborish."""
    parts = callback.data.split("_")
    year = int(parts[2])
    month = int(parts[3])

    await callback.answer("Excel fayl tayyorlanmoqda, iltimos kuting...", show_alert=False)

    month_names = {
        1: "Yanvar", 2: "Fevral", 3: "Mart", 4: "Aprel",
        5: "May", 6: "Iyun", 7: "Iyul", 8: "Avgust",
        9: "Sentyabr", 10: "Oktyabr", 11: "Noyabr", 12: "Dekabr"
    }
    m_name = month_names.get(month, f"{month}-oy")

    try:
        # 1. MATNLI HISOBOT (TELEGRAMDA KO'RSATISH UCHUN)
        workers = await db.get_report_workers_for_month(year, month)
        if not workers:
            await callback.message.answer(f"ℹ️ {m_name} {year} oyida hech qanday ish faoliyati qayd etilmagan.")
            return

        roles_dict = {}
        for w in workers:
            r_name = w.get("role_name") or "Boshqa"
            if r_name not in roles_dict:
                roles_dict[r_name] = []
            roles_dict[r_name].append(w)

        await callback.message.answer(f"📊 <b>{m_name} {year}</b> oyi uchun qisqacha hisobot:")

        for role_name, role_workers in roles_dict.items():
            text_chunks = []
            chunk = f"🎭 <b>LAVOZIM: {safe_html(role_name)}</b>\n━━━━━━━━━━━━━━━━━━━━\n"

            for w in role_workers:
                stats = await db.get_worker_month_stats(w["id"], year, month)
                w_text = (
                    f"👤 <b>{safe_html(w['full_name'])}</b>\n"
                    f"▪️ <b>Ishlangan:</b> {stats['days_worked']} kun ({format_hours_mins(stats['total_hours'])})\n"
                    f"▪️ <b>Hisoblandi:</b> {format_currency(stats['earned_salary'])}\n"
                    f"▪️ <b>Avans oldi:</b> {format_currency(stats['advances_sum'])}\n"
                    f"▪️ <b>Qoldiq (Raschyot):</b> <b>{format_currency(stats['balance'])}</b>\n"
                    f"──────────────\n"
                )
                if len(chunk) + len(w_text) > 3800:
                    text_chunks.append(chunk)
                    chunk = f"🎭 <b>LAVOZIM: {safe_html(role_name)} (davomi)</b>\n━━━━━━━━━━━━━━━━━━━━\n" + w_text
                else:
                    chunk += w_text

            text_chunks.append(chunk)
            for t in text_chunks:
                await callback.message.answer(t)

        # 2. EXCEL FAYL YARATISH VA YUBORISH
        excel_stream = await generate_monthly_report_excel(year, month)
        filename = monthly_report_filename(m_name, year)

        file = BufferedInputFile(
            file=excel_stream.getvalue(),
            filename=filename
        )

        await callback.message.answer_document(
            document=file,
            caption=(
                f"📊 <b>{safe_html(RESTAURANT_NAME)} — {m_name} {year} oylik to'liq hisoboti (Excel)</b>\n\n"
                f"✅ Davomat tabeli va barcha xodimlarning hisoblangan maoshi, avanslari va qoldiqlari kiritilgan."
            )
        )
    except Exception as e:
        logger.error(f"Hisobot yaratishda xatolik: {e}")
        await callback.message.answer(f"⚠️ Hisobot yaratishda xatolik yuz berdi: {safe_html(e)}")
