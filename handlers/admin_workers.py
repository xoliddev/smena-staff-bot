import math
import datetime
from datetime import date, time
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

import database as db
from config import RESTAURANT_NAME, TIMEZONE, format_currency, format_hours_mins
from loader import bot
from keyboards.inline_keyboards import (
    get_workers_2x_keyboard,
    get_worker_details_keyboard,
    get_roles_selection_keyboard,
    get_salary_type_keyboard,
    get_manual_attendance_keyboard,
    get_tx_void_keyboard,
    get_back_keyboard,
    get_worker_main_menu,
)
from states import WorkerManagementStates, ManualAttendanceStates
from utils.notifier import notify_all_admins
from utils.ui import edit_menu, remember_menu, update_menu_after_input, safe_html
from utils.middlewares import AdminOnlyCallbackMiddleware

logger = logging.getLogger(__name__)
router = Router(name="admin_workers_router")
router.callback_query.middleware(AdminOnlyCallbackMiddleware())

PER_PAGE = 8  # Har sahifada 8 ta xodim (4 qator x 2 ustun)


@router.callback_query(F.data == "admin:workers")
async def cb_workers_list(callback: CallbackQuery, state: FSMContext):
    """Xodimlar ro'yxatini 2x formatda va sahifalab ochish."""
    await state.clear()
    if not await db.is_admin_or_superadmin(callback.from_user.id):
        return

    total_count = await db.get_total_workers_count()
    total_pages = math.ceil(total_count / PER_PAGE) or 1
    workers = await db.get_workers_paginated(page=0, per_page=PER_PAGE)

    text = (
        f"👥 <b>XODIMLAR RO'YXATI</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>Jami faol xodimlar:</b> {total_count} nafar\n"
        f"Kerakli xodim ustiga bosing:"
    )

    await edit_menu(
        callback.message,
        text,
        get_workers_2x_keyboard(workers, page=0, total_pages=total_pages)
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data == "workers_back_to_list")
async def cb_workers_back_to_list(callback: CallbackQuery, state: FSMContext):
    """Xodimlar ro'yxatiga qaytish."""
    await cb_workers_list(callback, state)


@router.callback_query(F.data.startswith("workers_page_"))
async def cb_workers_pagination(callback: CallbackQuery):
    """Sahifadan sahifaga o'tish."""
    parts = callback.data.replace("workers_page_", "").split("_")
    page = int(parts[0])
    role_id = int(parts[1]) if len(parts) > 1 and parts[1] != "0" else None

    total_count = await db.get_total_workers_count(role_id=role_id)
    total_pages = math.ceil(total_count / PER_PAGE) or 1
    workers = await db.get_workers_paginated(page=page, per_page=PER_PAGE, role_id=role_id)

    role_title = ""
    if role_id:
        role = await db.get_role_by_id(role_id)
        if role:
            role_title = f" ({safe_html(role['name'])})"

    await edit_menu(
        callback.message,
        f"👥 <b>XODIMLAR RO'YXATI{role_title}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>Jami xodimlar:</b> {total_count} nafar\n"
        f"Kerakli xodim ustiga bosing:",
        get_workers_2x_keyboard(workers, page=page, total_pages=total_pages, role_id=role_id)
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data == "workers_filter_role")
async def cb_filter_roles(callback: CallbackQuery):
    """Rollar bo'yicha saralash menyusi."""
    roles = await db.get_all_roles(only_active=True)
    await edit_menu(
        callback.message,
        "🎭 <b>Qaysi rol bo'yicha filtrlashni xohlaysiz?</b>",
        get_roles_selection_keyboard(
            roles,
            action_prefix="w_filter_role_",
            include_all_option=True,
            back_callback="workers_back_to_list"
        )
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data.startswith("w_filter_role_"))
async def cb_apply_role_filter(callback: CallbackQuery):
    """Tanlangan rol bo'yicha xodimlarni filtrlash."""
    val = callback.data.replace("w_filter_role_", "")
    role_id = None if val == "all" else int(val)

    total_count = await db.get_total_workers_count(role_id=role_id)
    total_pages = math.ceil(total_count / PER_PAGE) or 1
    workers = await db.get_workers_paginated(page=0, per_page=PER_PAGE, role_id=role_id)

    role_title = ""
    if role_id:
        role = await db.get_role_by_id(role_id)
        if role:
            role_title = f" ({safe_html(role['name'])})"

    await edit_menu(
        callback.message,
        f"👥 <b>Xodimlar ro'yxati{role_title}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Jami: {total_count} nafar\n"
        f"Kerakli xodim ustiga bosing:",
        get_workers_2x_keyboard(workers, page=0, total_pages=total_pages, role_id=role_id)
    )
    try:
        await callback.answer()
    except Exception:
        pass


# ==========================================
# 🔍 QIDIRUV
# ==========================================

@router.callback_query(F.data == "workers_search")
async def cb_search_start(callback: CallbackQuery, state: FSMContext):
    """Qidiruv uchun ismni so'rash."""
    await remember_menu(state, callback.message)
    await edit_menu(
        callback.message,
        "🔍 <b>Qidiruv:</b> Qidirmoqchi bo'lgan xodimning ismini yozing:\n"
        "<i>(Bekor qilish uchun 'Ortga' tugmasini bosing)</i>",
        get_back_keyboard("workers_back_to_list")
    )
    await state.set_state(WorkerManagementStates.waiting_for_search_query)
    await callback.answer()


@router.message(WorkerManagementStates.waiting_for_search_query)
async def process_search_query(message: Message, state: FSMContext):
    """Qidiruv natijalarini ko'rsatish."""
    query = message.text.strip()
    total_count = await db.get_total_workers_count(search_query=query)
    total_pages = math.ceil(total_count / PER_PAGE) or 1
    workers = await db.get_workers_paginated(page=0, per_page=PER_PAGE, search_query=query)

    if not workers:
        await update_menu_after_input(
            message, state,
            f"🔍 '<b>{safe_html(query)}</b>' bo'yicha hech qanday xodim topilmadi.",
            get_back_keyboard("workers_back_to_list")
        )
        await state.clear()
        return

    await update_menu_after_input(
        message, state,
        f"🔍 '<b>{safe_html(query)}</b>' bo'yicha topilgan xodimlar ({total_count} nafar):",
        get_workers_2x_keyboard(workers, page=0, total_pages=total_pages)
    )
    await state.clear()


# ==========================================
# 👤 XODIM KARTASI (DETAILS VIEW)
# ==========================================

@router.callback_query(F.data.startswith("worker_view_"))
async def cb_worker_view(callback: CallbackQuery, state: FSMContext):
    """Xodimning batafsil kartasi va unga oid amallar."""
    await state.clear()
    worker_id = int(callback.data.replace("worker_view_", ""))
    worker = await db.get_worker_by_id(worker_id)

    if not worker:
        await callback.answer("Xodim topilmadi!", show_alert=True)
        return

    now = datetime.datetime.now(TIMEZONE)
    today = now.date()

    # Bugungi davomati
    session = await db.get_worker_today_session(worker_id, today)
    if not session:
        today_status = "❌ Kelmagan"
    elif session.get("is_rest_day"):
        today_status = "🌙 Dam olgan"
    elif session.get("departure_time"):
        dep_str = session["departure_time"].astimezone(TIMEZONE).strftime("%H:%M")
        arr_str = session["arrival_time"].astimezone(TIMEZONE).strftime("%H:%M") if session.get("arrival_time") else "—"
        today_status = f"🔴 Ishni yakunlagan ({arr_str} - {dep_str})"
    elif session.get("arrival_time"):
        arr_str = session["arrival_time"].astimezone(TIMEZONE).strftime("%H:%M")
        today_status = f"🟢 Ishda (Kelgan: {arr_str})"
    else:
        today_status = "❌ Kelmagan"

    # Oylik statistikasi
    stats = await db.get_worker_month_stats(worker_id, now.year, now.month)
    days = stats["days_worked"]
    hours = stats["total_hours"]
    earned = stats["earned_salary"]
    adv = stats["advances_sum"]
    balance = stats["balance"]

    sal_type = stats.get("salary_type") or worker.get("salary_type") or "monthly"
    sal_unit = "kunlik" if sal_type == "daily" else "oylik"
    sal_display = f"{format_currency(worker.get('monthly_salary'))} ({sal_unit})"

    phone = safe_html(worker.get("phone_number") or "Kiritilmagan")
    username = f"@{safe_html(worker['username'])}" if worker.get("username") else "mavjud_emas"

    text = (
        f"👤 <b>XODIM PROFILI</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📝 <b>F.I.O:</b> <b>{safe_html(worker['full_name'])}</b>\n"
        f"🎭 <b>Lavozimi:</b> {safe_html(worker.get('role_name') or 'Belgilanmagan')}\n"
        f"📱 <b>Telefon:</b> {phone}\n"
        f"🔗 <b>Telegram:</b> {username} (<code>{worker['tg_id']}</code>)\n"
        f"💰 <b>Belgilangan stavka:</b> <b>{sal_display}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📅 <b>Bugungi holat:</b> {today_status}\n"
        f"⏰ <b>Ish jadvali:</b> {worker.get('work_start').strftime('%H:%M') if worker.get('work_start') else '08:00'} - {worker.get('work_end').strftime('%H:%M') if worker.get('work_end') else '20:00'}\n"
        f"⏱ <b>Shu oygi ishlagan:</b> {days} kun ({format_hours_mins(hours)})\n"
        f"💵 <b>Hisoblangan haq:</b> {format_currency(earned)}\n"
        f"💸 <b>Olingan avanslar:</b> {format_currency(adv)}\n"
        f"💳 <b>Hozirgi qoldiq (Raschyot):</b> <b>{format_currency(balance)}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )

    await edit_menu(
        callback.message,
        text,
        get_worker_details_keyboard(worker_id)
    )
    try:
        await callback.answer()
    except Exception:
        pass


# ==========================================
# 🔄 LAVOZIMNI O'ZGARTIRISH
# ==========================================

@router.callback_query(F.data.startswith("worker_edit_role_"))
async def cb_worker_edit_role(callback: CallbackQuery):
    """Xodimning rolini o'zgartirish menyusi."""
    worker_id = int(callback.data.replace("worker_edit_role_", ""))
    roles = await db.get_all_roles(only_active=True)

    await edit_menu(
        callback.message,
        "🎭 <b>Xodim uchun yangi lavozimni tanlang:</b>",
        get_roles_selection_keyboard(
            roles,
            action_prefix=f"set_w_role_{worker_id}_",
            include_all_option=False,
            back_callback=f"worker_view_{worker_id}"
        )
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data.startswith("set_w_role_"))
async def cb_set_worker_role(callback: CallbackQuery, state: FSMContext):
    """Yangi lavozimni saqlash."""
    parts = callback.data.split("_")
    worker_id = int(parts[3])
    role_id = int(parts[4])

    await db.update_worker(worker_id, role_id=role_id)
    role = await db.get_role_by_id(role_id)
    role_name = role["name"] if role else "Noma'lum"

    await callback.answer(f"Lavozim '{role_name}'ga o'zgartirildi!", show_alert=True)
    callback.data = f"worker_view_{worker_id}"
    await cb_worker_view(callback, state)


# ==========================================
# 📋 TO'LOVLAR TARIXI VA TRANZAKSIYANI BEKOR QILISH (TASK 2)
# ==========================================

@router.callback_query(F.data.startswith("worker_pay_history_"))
async def cb_worker_pay_history(callback: CallbackQuery):
    """Xodimning to'lovlar tarixi va xatolik bo'lsa bekor qilish imkoniyati."""
    worker_id = int(callback.data.replace("worker_pay_history_", ""))
    worker = await db.get_worker_by_id(worker_id)
    history = await db.get_worker_transactions_history(worker_id, limit=10)

    if not history:
        await callback.answer("To'lovlar tarixi mavjud emas.", show_alert=True)
        return

    text = f"📋 <b>{safe_html(worker['full_name'])} — To'lovlar tarixi:</b>\n━━━━━━━━━━━━━━━━━━━━\n"
    kb = []

    for h in history:
        t_type = "💵 Avans" if h["transaction_type"] == "advance" else "💳 Raschyot"
        t_date = h["created_at"].astimezone(TIMEZONE).strftime("%d.%m.%Y %H:%M")
        comm = f" ({safe_html(h['comment'])})" if h.get("comment") else ""
        text += (
            f"• <b>#{h['id']}: {format_currency(h['amount'])}</b> — {t_type}\n"
            f"  ⏰ {t_date} | 👨‍💼 {safe_html(h['admin_name'])}{comm}\n\n"
        )
        kb.append([
            InlineKeyboardButton(
                text=f"🗑 Bekor qilish: #{h['id']} ({format_currency(h['amount'])})",
                callback_data=f"ask_void_tx_{worker_id}_{h['id']}"
            )
        ])

    text += "━━━━━━━━━━━━━━━━━━━━\n<i>Agar biror to'lov yanglish kiritilgan bo'lsa, uni bekor qilishingiz mumkin:</i>"
    kb.append([InlineKeyboardButton(text="⬅️ Xodim profiliga", callback_data=f"worker_view_{worker_id}")])

    await edit_menu(callback.message, text, InlineKeyboardMarkup(inline_keyboard=kb))
    try:
        await callback.answer()
    except Exception:
        pass

@router.callback_query(F.data.startswith("worker_att_history_"))
async def cb_worker_att_history(callback: CallbackQuery):
    """Xodimning oxirgi davomat tarixi ro'yxatini ko'rsatish."""
    worker_id = int(callback.data.replace("worker_att_history_", ""))
    worker = await db.get_worker_by_id(worker_id)

    if not worker:
        await callback.answer("Xodim topilmadi!", show_alert=True)
        return

    history = await db.get_worker_attendance_history(worker_id, limit=15)
    if not history:
        await callback.answer("Davomat tarixi mavjud emas.", show_alert=True)
        return

    text = (
        f"🕒 <b>{safe_html(worker['full_name'])} — Davomat tarixi:</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
    )

    for h in history:
        d_str = h["date"].strftime("%d.%m.%Y")
        if h.get("is_rest_day"):
            text += f"🌙 <b>{d_str}</b> — Dam olish kuni\n"
        elif h.get("arrival_time"):
            arr_str = h["arrival_time"].astimezone(TIMEZONE).strftime("%H:%M")
            if h.get("departure_time"):
                dep_str = h["departure_time"].astimezone(TIMEZONE).strftime("%H:%M")
                dur_str = format_hours_mins(h.get("total_hours") or 0.0)
                text += f"🟢 <b>{d_str}</b>: ⏰ {arr_str} ➔ 🔴 {dep_str} ({dur_str})\n"
            else:
                text += f"🟢 <b>{d_str}</b>: ⏰ {arr_str} (Hozir ishda)\n"
        else:
            text += f"⚪ <b>{d_str}</b>: Qayd qilinmagan\n"

        if h.get("notes"):
            text += f"   <i>💬 {safe_html(h['notes'])}</i>\n"
        text += "\n"

    text += "━━━━━━━━━━━━━━━━━━━━"

    await edit_menu(
        callback.message,
        text,
        get_back_keyboard(f"worker_view_{worker_id}")
    )
    try:
        await callback.answer()
    except Exception:
        pass



@router.callback_query(F.data.startswith("ask_void_tx_"))
async def cb_ask_void_tx(callback: CallbackQuery):
    """Tranzaksiyani bekor qilishdan oldin tasdiqlash so'rovi."""
    parts = callback.data.split("_")
    worker_id = int(parts[3])
    tx_id = int(parts[4])

    tx = await db.get_transaction_by_id(tx_id)
    if not tx:
        await callback.answer("Tranzaksiya topilmadi!", show_alert=True)
        return

    t_type = "Avans" if tx["transaction_type"] == "advance" else "Raschyot"
    text = (
        f"⚠️ <b>DIQQAT! Tranzaksiyani bekor qilmoqchimisiz?</b>\n\n"
        f"🆔 <b>Tranzaksiya ID:</b> #{tx['id']}\n"
        f"👤 <b>Xodim:</b> {safe_html(tx.get('worker_name', 'Xodim'))}\n"
        f"💰 <b>Summa:</b> {format_currency(tx['amount'])}\n"
        f"📋 <b>Turi:</b> {t_type}\n"
        f"👨‍💼 <b>Kiritgan:</b> {safe_html(tx.get('admin_name', 'Admin'))}\n\n"
        "Ushbu amal o'chirilsa, xodim balansi va oylik hisobot avtomatik qayta hisoblanadi."
    )
    await edit_menu(callback.message, text, get_tx_void_keyboard(worker_id, tx_id))
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_void_tx_"))
async def cb_confirm_void_tx(callback: CallbackQuery, state: FSMContext):
    """Tranzaksiyani o'chirish va barcha adminlarga bildirishnoma yuborish."""
    parts = callback.data.split("_")
    worker_id = int(parts[3])
    tx_id = int(parts[4])

    tx = await db.get_transaction_by_id(tx_id)
    if not tx:
        await callback.answer("Tranzaksiya allaqachon o'chirilgan!", show_alert=True)
        callback.data = f"worker_pay_history_{worker_id}"
        await cb_worker_pay_history(callback)
        return

    await db.delete_finance_transaction(tx_id)
    await callback.answer("✅ Tranzaksiya muvaffaqiyatli bekor qilindi!", show_alert=True)

    # Barcha adminlarga xabar berish
    t_type = "Avans" if tx["transaction_type"] == "advance" else "Raschyot"
    await notify_all_admins(
        f"🗑 <b>#TRANZAKSIYA_BEKOR_QILINDI</b>\n\n"
        f"🆔 <b>Tranzaksiya:</b> #{tx['id']}\n"
        f"👤 <b>Xodim:</b> {safe_html(tx.get('worker_name', 'Xodim'))}\n"
        f"💰 <b>Summa:</b> {format_currency(tx['amount'])}\n"
        f"📋 <b>Turi:</b> {t_type}\n"
        f"👨‍💼 <b>Bekor qilgan admin:</b> {safe_html(callback.from_user.full_name)}\n"
    )

    callback.data = f"worker_view_{worker_id}"
    await cb_worker_view(callback, state)


# ==========================================
# ⏱ DAVOMATNI QO'LDA KIRITISH / TO'G'RILASH (TASK 1)
# ==========================================

@router.callback_query(F.data.startswith("worker_manual_att_"))
async def cb_worker_manual_att(callback: CallbackQuery, state: FSMContext):
    """Admin tomonidan davomatni qo'lda kiritish varianti menyusi."""
    await state.clear()
    worker_id = int(callback.data.replace("worker_manual_att_", ""))
    worker = await db.get_worker_by_id(worker_id)

    if not worker:
        await callback.answer("Xodim topilmadi!", show_alert=True)
        return

    today_str = datetime.datetime.now(TIMEZONE).strftime("%d.%m.%Y")
    text = (
        f"⏱ <b>DAVOMATNI QO'LDA BELGILASH</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Xodim:</b> {safe_html(worker['full_name'])}\n"
        f"📅 <b>Sana:</b> {today_str}\n\n"
        f"Kerakli holatni tanlang:"
    )
    await edit_menu(callback.message, text, get_manual_attendance_keyboard(worker_id))
    await callback.answer()


@router.callback_query(F.data.startswith("man_att_"))
async def cb_man_att_action(callback: CallbackQuery, state: FSMContext):
    """Davomat variantini saqlash."""
    parts = callback.data.split("_")
    worker_id = int(parts[2])
    action = parts[3]

    now_tashkent = datetime.datetime.now(TIMEZONE)
    today = now_tashkent.date()
    worker = await db.get_worker_by_id(worker_id)

    if not worker:
        await callback.answer("Xodim topilmadi!", show_alert=True)
        return

    if action == "full":
        # 09:00 dan 21:00 gacha (12 soat) to'liq smena
        arr_time = datetime.datetime.combine(today, time(9, 0), tzinfo=TIMEZONE)
        dep_time = datetime.datetime.combine(today, time(21, 0), tzinfo=TIMEZONE)
        await db.set_manual_attendance(
            worker_id=worker_id,
            target_date=today,
            arrival_time=arr_time,
            departure_time=dep_time,
            is_rest_day=False,
            notes=f"Admin {callback.from_user.full_name} tomonidan to'liq smena kiritildi."
        )
        await callback.answer("✅ To'liq smena (12 soat) kiritildi!", show_alert=True)
        callback.data = f"worker_view_{worker_id}"
        await cb_worker_view(callback, state)

    elif action == "in":
        # Hozirgi vaqt bilan ishga kelgan deb belgilash
        await db.set_manual_attendance(
            worker_id=worker_id,
            target_date=today,
            arrival_time=now_tashkent,
            departure_time=None,
            is_rest_day=False,
            notes=f"Admin {callback.from_user.full_name} tomonidan 'Keldi' deb belgilandi."
        )
        await callback.answer("✅ Ishga kelgan deb qayd etildi!", show_alert=True)
        callback.data = f"worker_view_{worker_id}"
        await cb_worker_view(callback, state)

    elif action == "rest":
        # Dam olish kuni
        await db.set_manual_attendance(
            worker_id=worker_id,
            target_date=today,
            is_rest_day=True,
            notes=f"Admin {callback.from_user.full_name} tomonidan dam olish belgilandi."
        )
        await callback.answer("✅ Dam olish kuni deb belgilandi!", show_alert=True)
        callback.data = f"worker_view_{worker_id}"
        await cb_worker_view(callback, state)

    elif action == "custom":
        # O'z vaqtini kiritish
        await state.update_data(editing_worker_id=worker_id)
        await remember_menu(state, callback.message)
        await edit_menu(
            callback.message,
            f"✍️ <b>{safe_html(worker['full_name'])}</b> uchun ish vaqtini kiriting.\n\n"
            f"<b>Format:</b> <code>09:00 - 22:00</code>\n"
            f"<i>(Agar boshqa kun bo'lsa: <code>20.09.2026 09:00 - 22:00</code>)</i>",
            get_back_keyboard(f"worker_manual_att_{worker_id}")
        )
        await state.set_state(ManualAttendanceStates.waiting_for_custom_times)
        await callback.answer()


@router.message(ManualAttendanceStates.waiting_for_custom_times)
async def process_custom_att_input(message: Message, state: FSMContext):
    """Admin kiritgan erkin vaqt formatini o'qib bazaga kiritish."""
    data = await state.get_data()
    worker_id = data.get("editing_worker_id")
    raw_text = (message.text or "").strip()

    now_tashkent = datetime.datetime.now(TIMEZONE)
    target_date = now_tashkent.date()

    try:
        if "-" not in raw_text:
            raise ValueError("Chiziqcha bo'lishi kerak")

        # Agar sana berilgan bo'lsa: "20.09.2026 09:00 - 22:00"
        parts = raw_text.split("-")
        left_part = parts[0].strip()
        right_part = parts[1].strip()

        # Chap qismda sana bormi?
        left_tokens = left_part.split()
        if len(left_tokens) == 2:
            target_date = datetime.datetime.strptime(left_tokens[0], "%d.%m.%Y").date()
            start_str = left_tokens[1]
        else:
            start_str = left_tokens[0]

        start_t = datetime.datetime.strptime(start_str, "%H:%M").time()
        end_t = datetime.datetime.strptime(right_part, "%H:%M").time()

        arr_dt = datetime.datetime.combine(target_date, start_t, tzinfo=TIMEZONE)
        # Agar ketish vaqti kelish vaqtidan kichik bo'lsa (tungi smena, ertasi kuni)
        if end_t <= start_t:
            dep_dt = datetime.datetime.combine(target_date + datetime.timedelta(days=1), end_t, tzinfo=TIMEZONE)
        else:
            dep_dt = datetime.datetime.combine(target_date, end_t, tzinfo=TIMEZONE)

        diff = dep_dt - arr_dt
        hours = round(diff.total_seconds() / 3600.0, 2)

        await db.set_manual_attendance(
            worker_id=worker_id,
            target_date=target_date,
            arrival_time=arr_dt,
            departure_time=dep_dt,
            is_rest_day=False,
            notes=f"Admin qo'lda kiritdi: {arr_dt.strftime('%H:%M')} - {dep_dt.strftime('%H:%M')} ({hours} soat)"
        )

        await update_menu_after_input(
            message, state,
            f"✅ <b>Davomat muvaffaqiyatli saqlandi!</b>\n\n"
            f"📅 <b>Sana:</b> {target_date.strftime('%d.%m.%Y')}\n"
            f"⏰ <b>Vaqt:</b> {arr_dt.strftime('%H:%M')} - {dep_dt.strftime('%H:%M')}\n"
            f"⏱ <b>Ishlangan soat:</b> {format_hours_mins(hours)}",
            get_back_keyboard(f"worker_view_{worker_id}")
        )
        await state.clear()

    except Exception:
        await message.answer(
            "⚠️ <b>Vaqt formati noto'g'ri kiritildi!</b>\n\n"
            "Iltimos, namunadagidek kiriting:\n"
            "<code>09:00 - 22:00</code> yoki <code>20.09.2026 09:00 - 22:00</code>",
            reply_markup=get_back_keyboard(f"worker_manual_att_{worker_id}"),
            parse_mode="HTML"
        )


# ==========================================
# 💰 MAOSH TURI VA MIQDORINI BELGILASH (TASK 4)
# ==========================================

@router.callback_query(F.data.startswith("worker_edit_salary_"))
async def cb_edit_salary_start(callback: CallbackQuery, state: FSMContext):
    """Xodimning maosh turini tanlash (Oylik yoki Kunlik stavka)."""
    worker_id = int(callback.data.replace("worker_edit_salary_", ""))
    worker = await db.get_worker_by_id(worker_id)

    if not worker:
        await callback.answer("Xodim topilmadi!", show_alert=True)
        return

    text = (
        f"💰 <b>MAOSH VA STAVKA SOZLAMALARI</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Xodim:</b> {safe_html(worker['full_name'])}\n\n"
        f"Hisob-kitob turini tanlang:\n"
        f"• <b>📅 Oylik maosh</b> — har oy qat'iy maosh, kunlik stavka (oylik / 26) hisoblanadi.\n"
        f"• <b>☀️ Kunlik stavka</b> — har bir ishlagan kun uchun to'g'ridan-to'g'ri belgilangan summa to'lanadi."
    )
    await edit_menu(callback.message, text, get_salary_type_keyboard(worker_id))
    await callback.answer()


@router.callback_query(F.data.startswith("sal_type_"))
async def cb_select_salary_type(callback: CallbackQuery, state: FSMContext):
    """Tanlangan stavka turiga mos summa kiritishni so'rash."""
    parts = callback.data.split("_")
    worker_id = int(parts[2])
    sal_type = parts[3]  # 'monthly' yoki 'daily'

    await state.update_data(editing_worker_id=worker_id, salary_type=sal_type)
    await remember_menu(state, callback.message)

    if sal_type == "daily":
        prompt_text = "☀️ <b>Kunlik stavka summasini</b> kiriting (masalan: <code>150000</code>):"
    else:
        prompt_text = "📅 <b>Oylik maosh summasini</b> kiriting (masalan: <code>3500000</code>):"

    await edit_menu(
        callback.message,
        prompt_text,
        get_back_keyboard(f"worker_view_{worker_id}")
    )
    await state.set_state(WorkerManagementStates.waiting_for_salary_input)
    await callback.answer()


@router.message(WorkerManagementStates.waiting_for_salary_input)
async def process_salary_input(message: Message, state: FSMContext):
    """Yangi maosh va stavka turini bazaga yozish."""
    clean_text = (message.text or "").replace(" ", "").replace(",", "").replace(".", "")
    if not clean_text.isdigit():
        await message.answer("⚠️ Iltimos faqat musbat raqamlarda kiriting:")
        return

    salary = float(clean_text)
    data = await state.get_data()
    worker_id = data.get("editing_worker_id")
    sal_type = data.get("salary_type", "monthly")

    await db.update_worker(worker_id, monthly_salary=salary, salary_type=sal_type)
    unit_str = "kunlik stavka" if sal_type == "daily" else "oylik maosh"

    await update_menu_after_input(
        message, state,
        f"✅ Xodimning <b>{unit_str}</b>i <b>{format_currency(salary)}</b> qilib belgilandi!",
        get_back_keyboard(f"worker_view_{worker_id}"),
    )
    await state.clear()


# ==========================================
# 🗑 XODIMNI O'CHIRISH (XAVFSIZ TASDIQ BILAN)
# ==========================================

@router.callback_query(F.data.startswith("worker_delete_"))
async def cb_delete_worker_prompt(callback: CallbackQuery, state: FSMContext):
    """Xodimni o'chirishdan oldin tasdiqlash so'rovi (tasodifiy o'chirishdan himoya)."""
    worker_id = int(callback.data.replace("worker_delete_", ""))
    worker = await db.get_worker_by_id(worker_id)

    if not worker:
        await callback.answer("Xodim topilmadi!", show_alert=True)
        return

    text = (
        f"⚠️ <b>DIQQAT! Xodimni o'chirishni tasdiqlaysizmi?</b>\n\n"
        f"👤 <b>F.I.O:</b> {safe_html(worker['full_name'])}\n"
        f"🎭 <b>Lavozim:</b> {safe_html(worker.get('role_name') or 'Xodim')}\n\n"
        "Xodim nofaol qilinadi. Uning o'tgan oylardagi davomati va to'lov tarixi hisobotlarda to'liq saqlanib qoladi."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🗑 Ha, o'chirilsin", callback_data=f"worker_del_confirm_{worker_id}"),
            InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"worker_view_{worker_id}"),
        ]
    ])
    await edit_menu(callback.message, text, kb)
    await callback.answer()


@router.callback_query(F.data.startswith("worker_del_confirm_"))
async def cb_delete_worker_confirmed(callback: CallbackQuery, state: FSMContext):
    """Tasdiqlangandan so'ng xodimni nofaol qilish."""
    worker_id = int(callback.data.replace("worker_del_confirm_", ""))
    worker = await db.get_worker_by_id(worker_id)

    if not worker:
        await callback.answer("Xodim topilmadi!", show_alert=True)
        return

    await db.delete_worker(worker_id)
    await callback.answer("Xodim muvaffaqiyatli o'chirildi!", show_alert=True)
    await cb_workers_list(callback, state)


# ==========================================
# ⏰ ISH JADVALINI O'ZGARTIRISH (CRUD)
# ==========================================

@router.callback_query(F.data.startswith("worker_edit_schedule_"))
async def cb_edit_schedule_start(callback: CallbackQuery, state: FSMContext):
    """Xodimning ish jadvalini o'zgartirish."""
    worker_id = int(callback.data.replace("worker_edit_schedule_", ""))
    await state.update_data(editing_worker_id=worker_id)
    await remember_menu(state, callback.message)
    await edit_menu(
        callback.message,
        "⏰ Ish boshlanish vaqtini kiriting (masalan: <code>07:00</code>):",
        get_back_keyboard(f"worker_view_{worker_id}")
    )
    await state.set_state(WorkerManagementStates.waiting_for_work_schedule_start)
    await callback.answer()


@router.message(WorkerManagementStates.waiting_for_work_schedule_start)
async def process_schedule_start_input(message: Message, state: FSMContext):
    try:
        start_time = datetime.datetime.strptime(message.text.strip(), "%H:%M").time()
    except ValueError:
        data = await state.get_data()
        worker_id = data.get("editing_worker_id")
        await message.answer(
            "⚠️ Vaqtni noto'g'ri kiritdingiz! Masalan: <code>07:00</code>",
            reply_markup=get_back_keyboard(f"worker_view_{worker_id}")
        )
        return

    await state.update_data(work_start=start_time.strftime("%H:%M:%S"))
    data = await state.get_data()
    worker_id = data.get("editing_worker_id")
    await update_menu_after_input(
        message, state,
        f"Ish boshlanish vaqti: <b>{start_time.strftime('%H:%M')}</b>\n\n"
        "⏰ Endi ish tugash vaqtini kiriting (masalan: <code>18:00</code> yoki <code>00:00</code>):",
        get_back_keyboard(f"worker_view_{worker_id}")
    )
    await state.set_state(WorkerManagementStates.waiting_for_work_schedule_end)


@router.message(WorkerManagementStates.waiting_for_work_schedule_end)
async def process_schedule_end_input(message: Message, state: FSMContext):
    try:
        end_time = datetime.datetime.strptime(message.text.strip(), "%H:%M").time()
    except ValueError:
        data = await state.get_data()
        worker_id = data.get("editing_worker_id")
        await message.answer(
            "⚠️ Vaqtni noto'g'ri kiritdingiz! Masalan: <code>18:00</code>",
            reply_markup=get_back_keyboard(f"worker_view_{worker_id}")
        )
        return

    data = await state.get_data()
    worker_id = data.get("editing_worker_id")
    start_time_str = data.get("work_start")
    start_time_obj = datetime.datetime.strptime(start_time_str, "%H:%M:%S").time()

    await db.update_worker(worker_id, work_start=start_time_obj, work_end=end_time)
    await update_menu_after_input(
        message, state,
        f"✅ Xodimning ish jadvali <b>{start_time_obj.strftime('%H:%M')} - {end_time.strftime('%H:%M')}</b> etib belgilandi!",
        get_back_keyboard(f"worker_view_{worker_id}"),
    )
    await state.clear()


# ==========================================
# 📩 ISHGA QABUL QILISH ARIZALARINI TASDIQLASH
# ==========================================

@router.callback_query(F.data.startswith("app_accept_"))
async def cb_accept_application(callback: CallbackQuery):
    """Arizani tasdiqlab xodim sifatida qabul qilish."""
    app_id = int(callback.data.replace("app_accept_", ""))
    app = await db.get_application_by_id(app_id)

    if not app or app.get("status") != "pending":
        await callback.answer("Ushbu ariza allaqachon ko'rib chiqilgan!", show_alert=True)
        return

    # Xodim sifatida bazaga qo'shamiz
    worker_id = await db.add_worker(
        tg_id=app["tg_id"],
        full_name=app["full_name"],
        phone_number=app.get("phone_number"),
        username=app.get("username"),
        role_id=app.get("selected_role_id"),
        monthly_salary=0.0
    )

    await db.update_application_status(app_id, "accepted")

    role_name = app.get("role_name") or "Xodim"
    accept_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Maosh belgilash", callback_data=f"worker_edit_salary_{worker_id}")],
        [InlineKeyboardButton(text="👤 Xodim profili", callback_data=f"worker_view_{worker_id}")],
        [InlineKeyboardButton(text="👥 Xodimlar ro'yxati", callback_data="admin:workers")]
    ])

    await edit_menu(
        callback.message,
        f"✅ <b>Xodim ishga qabul qilindi!</b>\n\n"
        f"👤 <b>F.I.O:</b> {safe_html(app['full_name'])}\n"
        f"🎭 <b>Lavozim:</b> {safe_html(role_name)}\n"
        f"📱 <b>Telefon:</b> {safe_html(app.get('phone_number') or '—')}\n"
        f"Tasdiqladi: {safe_html(callback.from_user.full_name)}",
        accept_kb
    )
    try:
        await callback.answer("Xodim qabul qilindi!")
    except Exception:
        pass

    # Xodimga tabrik xabari yuboramiz
    try:
        await bot.send_message(
            chat_id=app["tg_id"],
            text=(
                f"🎉 <b>TABRIKLAYMIZ!</b>\n\n"
                f"Hurmatli <b>{safe_html(app['full_name'])}</b>, sizning <b>{safe_html(RESTAURANT_NAME)}</b> korxonasiga "
                f"<b>{safe_html(role_name)}</b> lavozimiga topshirgan arizangiz ma'muriyat tomonidan tasdiqlandi!\n\n"
                "Endi bot orqali ishga keldi-ketdilaringizni qayd etishingiz mumkin."
            ),
            reply_markup=get_worker_main_menu()
        )
    except Exception as e:
        logger.warning(f"Xodim {app['tg_id']} ga tasdiq xabarini yuborib bo'lmadi: {e}")


@router.callback_query(F.data.startswith("app_reject_"))
async def cb_reject_application(callback: CallbackQuery):
    """Arizani rad etish."""
    app_id = int(callback.data.replace("app_reject_", ""))
    app = await db.get_application_by_id(app_id)

    if not app:
        return

    await db.update_application_status(app_id, "rejected")

    await edit_menu(
        callback.message,
        f"❌ <b>Ariza rad etildi.</b>\n"
        f"👤 Nomzod: {safe_html(app['full_name'])}\n"
        f"Rad etdi: {safe_html(callback.from_user.full_name)}",
        None
    )
    try:
        await callback.answer("Ariza rad etildi.")
    except Exception:
        pass
