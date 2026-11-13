import datetime
from datetime import date
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

import database as db
from config import TIMEZONE, MONTH_NAMES, format_currency, format_hours_mins
from keyboards.inline_keyboards import get_back_keyboard
from states import FinanceStates
from utils.ui import edit_menu, remember_menu, update_menu_after_input, safe_html
from utils.notifier import notify_finance_operation
from utils.middlewares import AdminOnlyCallbackMiddleware

logger = logging.getLogger(__name__)
router = Router(name="admin_finance_router")
router.callback_query.middleware(AdminOnlyCallbackMiddleware())


# ==========================================
# 💰 MOLIYA BOSH SAHIFASI
# ==========================================

@router.callback_query(F.data == "admin:finance")
async def cb_admin_finance(callback: CallbackQuery, state: FSMContext):
    """Moliya bo'limi bosh menyusi."""
    await state.clear()
    if not await db.is_admin_or_superadmin(callback.from_user.id):
        return

    now = datetime.datetime.now(TIMEZONE)
    today = now.date()

    async with db.pool.acquire() as conn:
        today_stats = await conn.fetchrow("""
            SELECT
                COALESCE(SUM(CASE WHEN transaction_type = 'advance' THEN amount ELSE 0 END), 0.0) as today_advances,
                COALESCE(SUM(CASE WHEN transaction_type = 'settlement' THEN amount ELSE 0 END), 0.0) as today_settlements,
                COUNT(id) as today_count
            FROM finance_transactions
            WHERE created_at >= $1::timestamp AT TIME ZONE 'Asia/Tashkent'
        """, today)

    today_adv = float(today_stats["today_advances"]) if today_stats else 0.0
    today_set = float(today_stats["today_settlements"]) if today_stats else 0.0
    today_cnt = today_stats["today_count"] if today_stats else 0

    text = (
        f"💵 <b>MOLIYA VA ISH HAQI BOSHQARUVI</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📅 <b>Bugungi sana:</b> {today.strftime('%d.%m.%Y')}\n"
        f"📊 <b>Bugungi amallar soni:</b> {today_cnt} ta\n"
        f"💸 <b>Bugun berilgan avanslar:</b> {format_currency(today_adv)}\n"
        f"💳 <b>Bugun to'langan raschyotlar:</b> {format_currency(today_set)}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Xodimlarga avans yoki oylik raschyot berish uchun xodimlar ro'yxatidan kerakli shaxsni tanlang:"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Xodimlar ro'yxatiga o'tish", callback_data="admin:workers")],
        [InlineKeyboardButton(text="📋 Bugungi tranzaksiyalar", callback_data="fin_today_txs")],
        [InlineKeyboardButton(text="⬅️ Bosh menyuga", callback_data="admin:home")]
    ])

    await edit_menu(callback.message, text, kb)
    await callback.answer()


@router.callback_query(F.data == "fin_today_txs")
async def cb_finance_today_list(callback: CallbackQuery):
    """Bugungi barcha moliyaviy operatsiyalar ro'yxati."""
    now = datetime.datetime.now(TIMEZONE)
    today = now.date()

    async with db.pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT t.*, w.full_name as worker_name, r.name as role_name
            FROM finance_transactions t
            JOIN workers w ON w.id = t.worker_id
            LEFT JOIN roles r ON r.id = w.role_id
            WHERE t.created_at >= $1::timestamp AT TIME ZONE 'Asia/Tashkent'
            ORDER BY t.created_at DESC
        """, today)

    if not rows:
        await callback.answer("Bugun hali moliyaviy amallar bajarilmagan.", show_alert=True)
        return

    text = f"📋 <b>BUGUNGI MOLIYAVIY AMALLAR ({today.strftime('%d.%m.%Y')}):</b>\n━━━━━━━━━━━━━━━━━━━━\n"
    for r in rows:
        t_type = "💵 Avans" if r["transaction_type"] == "advance" else "💳 Raschyot"
        t_time = r["created_at"].astimezone(TIMEZONE).strftime("%H:%M")
        comm = f" ({safe_html(r['comment'])})" if r.get("comment") else ""
        text += (
            f"• <b>{safe_html(r['worker_name'])}</b> — <b>{format_currency(r['amount'])}</b>\n"
            f"  {t_type} | ⏰ {t_time} | 👨‍💼 {safe_html(r['admin_name'])}{comm}\n\n"
        )

    text += "━━━━━━━━━━━━━━━━━━━━"
    await edit_menu(callback.message, text, get_back_keyboard("admin:finance"))
    await callback.answer()


# ==========================================
# 💸 AVANS BERISH JARAYONI
# ==========================================

@router.callback_query(F.data.startswith("fin_advance_"))
async def cb_advance_start(callback: CallbackQuery, state: FSMContext):
    """Xodimga avans berishni boshlash."""
    worker_id = int(callback.data.replace("fin_advance_", ""))
    worker = await db.get_worker_by_id(worker_id)

    if not worker:
        await callback.answer("Xodim topilmadi!", show_alert=True)
        return

    now = datetime.datetime.now(TIMEZONE)
    stats = await db.get_worker_month_stats(worker_id, now.year, now.month)

    await state.update_data(
        worker_id=worker_id,
        worker_name=worker["full_name"],
        role_name=worker.get("role_name", "Xodim")
    )
    await remember_menu(state, callback.message)

    text = (
        f"💵 <b>AVANS BERISH</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Xodim:</b> {safe_html(worker['full_name'])}\n"
        f"🎭 <b>Lavozim:</b> {safe_html(worker.get('role_name') or 'Xodim')}\n"
        f"💰 <b>Shu oygi hisoblangan:</b> {format_currency(stats['earned_salary'])}\n"
        f"💸 <b>Olingan avanslar:</b> {format_currency(stats['advances_sum'])}\n"
        f"💳 <b>Hozirgi qoldiq:</b> {format_currency(stats['balance'])}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Berilayotgan <b>avans summasini</b> so'mda kiriting:\n"
        f"<i>(Masalan: <code>200000</code> yoki <code>500000</code>)</i>"
    )

    await edit_menu(callback.message, text, get_back_keyboard(f"worker_view_{worker_id}"))
    await state.set_state(FinanceStates.waiting_for_advance_amount)
    await callback.answer()


@router.message(FinanceStates.waiting_for_advance_amount)
async def process_advance_amount(message: Message, state: FSMContext):
    """Avans summasini qabul qilish va izoh so'rash."""
    clean_text = (message.text or "").replace(" ", "").replace(",", "").replace(".", "")
    if not clean_text.isdigit() or int(clean_text) <= 0:
        await message.answer("⚠️ Iltimos, musbat raqamlarda to'g'ri summa kiriting:")
        return

    amount = float(clean_text)
    await state.update_data(advance_amount=amount)
    data = await state.get_data()
    worker_id = data.get("worker_id")

    text = (
        f"💰 Summa: <b>{format_currency(amount)}</b>\n\n"
        f"Ushbu avans uchun <b>izoh (sabab)</b> yozing:\n"
        f"<i>(Agar izoh kerak bo'lmasa, 'yo'q' deb yuboring)</i>"
    )

    await update_menu_after_input(message, state, text, get_back_keyboard(f"worker_view_{worker_id}"))
    await state.set_state(FinanceStates.waiting_for_advance_comment)


@router.message(FinanceStates.waiting_for_advance_comment)
async def process_advance_comment(message: Message, state: FSMContext):
    """Izohni qabul qilib, tasdiqlash tugmasini ko'rsatish."""
    comment_text = message.text.strip()
    comment = None if comment_text.lower() in ["yo'q", "yoq", "yo`q", "-", "none", "no"] else comment_text

    await state.update_data(advance_comment=comment)
    data = await state.get_data()

    worker_id = data.get("worker_id")
    worker_name = data.get("worker_name")
    amount = data.get("advance_amount")

    text = (
        f"⚠️ <b>AVANS BERISHNI TASDIQLAYSIZMI?</b>\n\n"
        f"👤 <b>Xodim:</b> {safe_html(worker_name)}\n"
        f"💰 <b>Summa:</b> <b>{format_currency(amount)}</b>\n"
    )
    if comment:
        text += f"💬 <b>Izoh:</b> <i>{safe_html(comment)}</i>\n"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Ha, berilsin", callback_data=f"fin_adv_confirm_{worker_id}"),
            InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"worker_view_{worker_id}"),
        ]
    ])

    await update_menu_after_input(message, state, text, kb)
    await state.set_state(FinanceStates.waiting_for_advance_confirm)


@router.callback_query(F.data.startswith("fin_adv_confirm_"))
async def cb_confirm_advance(callback: CallbackQuery, state: FSMContext):
    """Avansni bazaga yozish va barcha adminlarga bildirishnoma yuborish."""
    data = await state.get_data()
    worker_id = data.get("worker_id")
    amount = data.get("advance_amount")
    comment = data.get("advance_comment")
    worker_name = data.get("worker_name")
    role_name = data.get("role_name", "Xodim")

    if not worker_id or not amount:
        await callback.answer("Amal muddati o'tgan. Qaytadan urinib ko'ring.", show_alert=True)
        return

    admin_tg_id = callback.from_user.id
    admin_name = callback.from_user.full_name
    now_tashkent = datetime.datetime.now(TIMEZONE)
    datetime_str = now_tashkent.strftime("%d.%m.%Y %H:%M")

    await db.add_finance_transaction(
        worker_id=worker_id,
        admin_tg_id=admin_tg_id,
        admin_name=admin_name,
        transaction_type="advance",
        amount=amount,
        comment=comment
    )

    await state.clear()
    await edit_menu(
        callback.message,
        f"✅ <b>Avans muvaffaqiyatli berildi!</b>\n\n"
        f"👤 <b>Xodim:</b> {safe_html(worker_name)}\n"
        f"💰 <b>Summa:</b> {format_currency(amount)}\n"
        f"⏰ <b>Vaqt:</b> {datetime_str}",
        get_back_keyboard(f"worker_view_{worker_id}")
    )
    try:
        await callback.answer("Avans to'landi!")
    except Exception:
        pass

    # BARCHA ADMINLARGA BILDIRISHNOMA YUBORISH
    await notify_finance_operation(
        worker_name=worker_name,
        role_name=role_name,
        transaction_type="advance",
        amount=amount,
        admin_name=admin_name,
        datetime_str=datetime_str,
        comment=comment
    )


# ==========================================
# 💳 RASCHYOT QILISH JARAYONI (OY TANLASH BILAN)
# ==========================================

@router.callback_query(F.data.startswith("fin_settle_"))
async def cb_settle_choose_month(callback: CallbackQuery, state: FSMContext):
    """Raschyot qilish uchun oyni tanlash (joriy oy yoki o'tgan oy)."""
    worker_id = int(callback.data.replace("fin_settle_", ""))
    worker = await db.get_worker_by_id(worker_id)

    if not worker:
        await callback.answer("Xodim topilmadi!", show_alert=True)
        return

    now = datetime.datetime.now(TIMEZONE)
    curr_month = now.month
    curr_year = now.year

    prev_month = 12 if curr_month == 1 else curr_month - 1
    prev_year = curr_year - 1 if curr_month == 1 else curr_year

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"📅 {MONTH_NAMES[curr_month]} {curr_year} (Joriy oy)",
                callback_data=f"fin_calc_{worker_id}_{curr_year}_{curr_month}"
            )
        ],
        [
            InlineKeyboardButton(
                text=f"📁 {MONTH_NAMES[prev_month]} {prev_year} (O'tgan oy)",
                callback_data=f"fin_calc_{worker_id}_{prev_year}_{prev_month}"
            )
        ],
        [
            InlineKeyboardButton(text="⬅️ Ortga", callback_data=f"worker_view_{worker_id}")
        ]
    ])

    await edit_menu(
        callback.message,
        f"💳 <b>{safe_html(worker['full_name'])}</b> uchun qaysi oy hisob-kitobini (raschyot) amalga oshirmoqchisiz?\n\n"
        f"Odatda o'tgan oyning maoshi yangi oyning 1-10 sanalarida to'lanadi.",
        kb
    )
    await callback.answer()


@router.callback_query(F.data.startswith("fin_calc_"))
async def cb_settle_calc_month(callback: CallbackQuery, state: FSMContext):
    """Tanlangan oy bo'yicha raschyot hisob-kitobini ko'rsatish."""
    parts = callback.data.split("_")
    worker_id = int(parts[2])
    year = int(parts[3])
    month = int(parts[4])

    worker = await db.get_worker_by_id(worker_id)
    if not worker:
        await callback.answer("Xodim topilmadi!", show_alert=True)
        return

    stats = await db.get_worker_month_stats(worker_id, year, month)
    days = stats["days_worked"]
    hours = stats["total_hours"]
    earned = stats["earned_salary"]
    advances = stats["advances_sum"]
    settlements = stats.get("settlements_sum", 0.0)
    balance = stats["balance"]

    if balance < 0:
        balance = 0.0

    await state.update_data(
        target_worker_id=worker_id,
        target_year=year,
        target_month=month,
        worker_name=worker["full_name"],
        role_name=worker.get("role_name"),
        settle_amount=balance,
        days_worked=days,
        hours_worked=hours,
        earned_salary=earned,
        advances_deducted=advances
    )

    m_title = f"{MONTH_NAMES.get(month, month)} {year}"
    sal_type = stats.get("salary_type") or worker.get("salary_type") or "monthly"
    sal_label = "kunlik" if sal_type == "daily" else "oylik"
    sal_display = f"{format_currency(worker.get('monthly_salary'))} ({sal_label})"

    text = (
        f"💳 <b>RASCHYOT QILISH — {m_title}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Xodim:</b> {safe_html(worker['full_name'])} (<i>{safe_html(worker.get('role_name') or 'Xodim')}</i>)\n"
        f"💰 <b>Belgilangan stavka:</b> {sal_display}\n"
        f"⏱ <b>Ishlangan:</b> {days} kun ({format_hours_mins(hours)})\n"
        f"💵 <b>Jami hisoblangan haq:</b> {format_currency(earned)}\n"
        f"💸 <b>Olingan avanslar:</b> {format_currency(advances)}\n"
    )
    if settlements > 0:
        text += f"💳 <b>Avval to'langan raschyot:</b> {format_currency(settlements)}\n"

    text += (
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"✅ <b>TO'LANISHI KERAK BO'LGAN QOLDIQ:</b> <b>{format_currency(balance)}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Tasdiqlaysizmi yoki boshqa summa kiritasizmi?"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Raschyotni Tasdiqlash", callback_data=f"confirm_settle_{worker_id}_{year}_{month}_{int(balance)}"),
            InlineKeyboardButton(text="✏️ Boshqa summa", callback_data=f"custom_settle_{worker_id}_{year}_{month}"),
        ],
        [
            InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"worker_view_{worker_id}"),
        ]
    ])

    await remember_menu(state, callback.message)
    await edit_menu(callback.message, text, kb)
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_settle_"))
async def cb_confirm_settlement(callback: CallbackQuery, state: FSMContext):
    """Raschyot to'lovini bazaga saqlash."""
    parts = callback.data.split("_")
    worker_id = int(parts[2])
    year = int(parts[3])
    month = int(parts[4])
    amount = float(parts[5])

    data = await state.get_data()
    worker_name = data.get("worker_name", "Xodim")
    role_name = data.get("role_name", "Xodim")
    days = data.get("days_worked", 0)
    hours = data.get("hours_worked", 0.0)
    earned = data.get("earned_salary", 0.0)
    advances = data.get("advances_deducted", 0.0)

    admin_tg_id = callback.from_user.id
    admin_name = callback.from_user.full_name
    now_tashkent = datetime.datetime.now(TIMEZONE)
    datetime_str = now_tashkent.strftime("%d.%m.%Y %H:%M")

    period_start = date(year, month, 1)
    period_end = date(year, month + 1, 1) if month < 12 else date(year + 1, 1, 1)

    extra_info = (
        f"Ishlangan: {days} kun ({format_hours_mins(hours)}) | "
        f"Haq: {format_currency(earned)} | Avanslar: {format_currency(advances)}"
    )

    await db.add_finance_transaction(
        worker_id=worker_id,
        admin_tg_id=admin_tg_id,
        admin_name=admin_name,
        transaction_type="settlement",
        amount=amount,
        period_start=period_start,
        period_end=period_end,
        worked_hours=hours,
        total_salary_calculated=earned,
        advances_deducted=advances,
        comment=f"{MONTH_NAMES.get(month, month)} {year} oylik raschyoti"
    )

    await state.clear()
    await edit_menu(
        callback.message,
        f"✅ <b>Oylik raschyot muvaffaqiyatli amalga oshirildi!</b>\n\n"
        f"👤 <b>Xodim:</b> {safe_html(worker_name)}\n"
        f"📅 <b>Davr:</b> {MONTH_NAMES.get(month, month)} {year}\n"
        f"💰 <b>To'langan summa:</b> {format_currency(amount)}\n"
        f"⏰ <b>Vaqt:</b> {datetime_str}",
        get_back_keyboard(f"worker_view_{worker_id}")
    )
    try:
        await callback.answer("Raschyot to'landi!")
    except Exception:
        pass

    # Barcha adminlarga bildirishnoma
    await notify_finance_operation(
        worker_name=worker_name,
        role_name=role_name,
        transaction_type="settlement",
        amount=amount,
        admin_name=admin_name,
        datetime_str=datetime_str,
        extra_info=extra_info,
        comment=f"{MONTH_NAMES.get(month, month)} {year} yakuniy raschyoti"
    )


@router.callback_query(F.data.startswith("custom_settle_"))
async def cb_custom_settle_start(callback: CallbackQuery, state: FSMContext):
    """Raschyot uchun qo'lda boshqa summa kiritish."""
    parts = callback.data.split("_")
    worker_id = int(parts[2])
    year = int(parts[3])
    month = int(parts[4])

    await state.update_data(target_worker_id=worker_id, target_year=year, target_month=month)
    await remember_menu(state, callback.message)

    await edit_menu(
        callback.message,
        "✏️ <b>To'lanadigan aniq raschyot summasini kiriting:</b>\n<i>(Masalan: <code>1500000</code>)</i>",
        get_back_keyboard(f"fin_calc_{worker_id}_{year}_{month}")
    )
    await state.set_state(FinanceStates.waiting_for_settlement_custom_amount)
    await callback.answer()


@router.message(FinanceStates.waiting_for_settlement_custom_amount)
async def process_custom_settle_amount(message: Message, state: FSMContext):
    """Kiritilgan summani qabul qilish va tasdiqlashga yo'naltirish."""
    clean_text = (message.text or "").replace(" ", "").replace(",", "").replace(".", "")
    if not clean_text.isdigit() or int(clean_text) < 0:
        await message.answer("⚠️ Iltimos, musbat raqamlarda to'g'ri summa kiriting:")
        return

    amount = float(clean_text)
    data = await state.get_data()
    worker_id = data.get("target_worker_id")
    year = data.get("target_year")
    month = data.get("target_month")

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Tasdiqlash va To'lash", callback_data=f"confirm_settle_{worker_id}_{year}_{month}_{int(amount)}"),
            InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"worker_view_{worker_id}"),
        ]
    ])

    await update_menu_after_input(
        message, state,
        f"⚠️ <b>Raschyot summasi:</b> <b>{format_currency(amount)}</b>\n\nTo'lovni tasdiqlaysizmi?",
        kb
    )
