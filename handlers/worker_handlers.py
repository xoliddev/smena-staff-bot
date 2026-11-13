import datetime
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext

import database as db
from config import RESTAURANT_NAME, TIMEZONE, format_currency, format_hours_mins
from keyboards.inline_keyboards import get_back_keyboard, get_worker_main_menu
from keyboards.reply_keyboards import get_location_request_keyboard
from states import WorkerAttendanceStates
from utils.geo import is_within_radius
from utils.notifier import notify_attendance_event
from utils.ui import edit_menu, safe_html

logger = logging.getLogger(__name__)
router = Router(name="worker_handlers_router")


# ==========================================
# 🟢 ISHGA KELISH (CLOCK-IN)
# ==========================================

async def prompt_arrival_action(user_id: int, reply_func, state: FSMContext, answer_cb=None):
    """Ishga kelish uchun geolokatsiya so'rash mantiqi."""
    await state.clear()
    worker = await db.get_worker_by_tg_id(user_id)
    if not worker:
        if answer_cb:
            await answer_cb("Siz xodimlar ro'yxatida emassiz.", show_alert=True)
        else:
            await reply_func("Siz xodimlar ro'yxatida emassiz.")
        return

    now_tashkent = datetime.datetime.now(TIMEZONE)
    today = now_tashkent.date()

    # Ochiq sessiya bormi yoki bugun allaqachon kelganmi?
    session = await db.get_worker_today_session(worker["id"], today)
    if session and session.get("is_rest_day"):
        text = "Siz bugun dam olish kuni deb belgilagansiz!"
        if answer_cb:
            await answer_cb(text, show_alert=True)
        else:
            await reply_func(text)
        return

    if session and session.get("arrival_time"):
        arr_str = session["arrival_time"].astimezone(TIMEZONE).strftime("%H:%M")
        if session.get("departure_time"):
            dep_str = session["departure_time"].astimezone(TIMEZONE).strftime("%H:%M")
            text = f"Siz bugun ishni yakunlagansiz ({arr_str} - {dep_str})!"
        else:
            text = f"Siz bugun soat {arr_str} da ishga kelgansiz. Hozir ishdasiz!"
        if answer_cb:
            await answer_cb(text, show_alert=True)
        else:
            await reply_func(text)
        return

    await reply_func(
        "📍 <b>Ishga kelganingizni tasdiqlash uchun</b> pastdagi tugmani bosing va joylashuvingizni (GPS) yuboring:",
        reply_markup=get_location_request_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(WorkerAttendanceStates.waiting_for_arrival_location)
    if answer_cb:
        await answer_cb()


@router.callback_query(F.data.in_(["worker:arrival", "worker:clock_in"]))
async def cb_arrival_prompt(callback: CallbackQuery, state: FSMContext):
    """Ishga kelish uchun geolokatsiya so'rash (Inline tugma)."""
    await prompt_arrival_action(
        user_id=callback.from_user.id,
        reply_func=callback.message.answer,
        state=state,
        answer_cb=callback.answer
    )


@router.message(F.text.in_(["🟢 Ishga keldim", "Ishga keldim"]))
async def msg_arrival_prompt(message: Message, state: FSMContext):
    """Ishga kelish uchun geolokatsiya so'rash (Reply tugma / Matn)."""
    await prompt_arrival_action(
        user_id=message.from_user.id,
        reply_func=message.answer,
        state=state
    )


@router.message(WorkerAttendanceStates.waiting_for_arrival_location, F.location)
async def process_arrival_location(message: Message, state: FSMContext):
    """Xodim yuborgan lokatsiyani tekshirish va ishga kelishni yozish."""
    worker = await db.get_worker_by_tg_id(message.from_user.id)
    if not worker:
        await message.answer("Siz xodimlar ro'yxatida emassiz.", reply_markup=ReplyKeyboardRemove())
        await state.clear()
        return

    settings = await db.get_settings()
    target_lat = settings.get("location_lat", 41.311081)
    target_lon = settings.get("location_lon", 69.240562)
    radius = settings.get("location_radius", 150)

    u_lat = message.location.latitude
    u_lon = message.location.longitude

    in_range, dist = is_within_radius(u_lat, u_lon, target_lat, target_lon, radius)

    if not in_range:
        await message.answer(
            f"⚠️ <b>Siz korxona hududida emassiz!</b>\n\n"
            f"📏 Belgilangan radius: <b>{int(radius)} metr</b>\n"
            f"📍 Sizning masofangiz: <b>{int(dist)} metr</b>\n\n"
            "Iltimos, korxona hududiga kelib qaytadan urinib ko'ring.",
            reply_markup=ReplyKeyboardRemove(),
            parse_mode="HTML"
        )
        await state.clear()
        return

    now_tashkent = datetime.datetime.now(TIMEZONE)
    today = now_tashkent.date()

    await db.clock_in(
        worker_id=worker["id"],
        target_date=today,
        arrival_time=now_tashkent,
        lat=u_lat,
        lon=u_lon,
        distance=dist
    )

    arr_time_str = now_tashkent.strftime("%H:%M")
    await message.answer(
        f"✅ <b>Xush kelibsiz! Ishga kelganingiz qayd etildi.</b>\n\n"
        f"⏰ Vaqt: <b>{arr_time_str}</b>\n"
        f"📍 Masofa: <b>{int(dist)} metr</b>\n\n"
        "Bugungi ish kuningizga omad tilaymiz! 👨‍🍳",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="HTML"
    )
    await state.clear()

    # Barcha adminlarga va guruhga bildirishnoma
    await notify_attendance_event(
        worker_name=worker["full_name"],
        role_name=worker.get("role_name", "Xodim"),
        event_type="in",
        time_str=arr_time_str,
        distance_m=dist
    )


# ==========================================
# 🔴 ISHDAN KETISH (CLOCK-OUT)
# ==========================================

async def prompt_departure_action(user_id: int, reply_func, state: FSMContext, answer_cb=None):
    """Ishdan ketish uchun geolokatsiya so'rash mantiqi."""
    await state.clear()
    worker = await db.get_worker_by_tg_id(user_id)
    if not worker:
        if answer_cb:
            await answer_cb("Siz xodimlar ro'yxatida emassiz.", show_alert=True)
        else:
            await reply_func("Siz xodimlar ro'yxatida emassiz.")
        return

    # Ochiq sessiyani qidiramiz (tungi smena hisobga olingan holda)
    session = await db.get_worker_open_session(worker["id"])
    if not session:
        now_tashkent = datetime.datetime.now(TIMEZONE)
        session = await db.get_worker_today_session(worker["id"], now_tashkent.date())

    if not session or not session.get("arrival_time"):
        text = "Siz bugun ishga kelishni qayd etmagansiz!"
        if answer_cb:
            await answer_cb(text, show_alert=True)
        else:
            await reply_func(text)
        return

    if session.get("departure_time"):
        dep_str = session["departure_time"].astimezone(TIMEZONE).strftime("%H:%M")
        text = f"Siz allaqachon soat {dep_str} da ishni yakunlagansiz!"
        if answer_cb:
            await answer_cb(text, show_alert=True)
        else:
            await reply_func(text)
        return

    await reply_func(
        "📍 <b>Ishdan ketishingizni tasdiqlash uchun</b> pastdagi tugmani bosing va joylashuvingizni (GPS) yuboring:",
        reply_markup=get_location_request_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(WorkerAttendanceStates.waiting_for_departure_location)
    if answer_cb:
        await answer_cb()


@router.callback_query(F.data.in_(["worker:departure", "worker:clock_out"]))
async def cb_departure_prompt(callback: CallbackQuery, state: FSMContext):
    """Ishdan ketish uchun geolokatsiya so'rash (Inline tugma)."""
    await prompt_departure_action(
        user_id=callback.from_user.id,
        reply_func=callback.message.answer,
        state=state,
        answer_cb=callback.answer
    )


@router.message(F.text.in_(["🔴 Ishdan ketdim", "Ishdan ketdim"]))
async def msg_departure_prompt(message: Message, state: FSMContext):
    """Ishdan ketish uchun geolokatsiya so'rash (Reply tugma / Matn)."""
    await prompt_departure_action(
        user_id=message.from_user.id,
        reply_func=message.answer,
        state=state
    )


@router.message(WorkerAttendanceStates.waiting_for_departure_location, F.location)
async def process_departure_location(message: Message, state: FSMContext):
    """Xodim yuborgan lokatsiyani tekshirish va ketish vaqtini yozish."""
    worker = await db.get_worker_by_tg_id(message.from_user.id)
    if not worker:
        await message.answer("Siz xodimlar ro'yxatida emassiz.", reply_markup=ReplyKeyboardRemove())
        await state.clear()
        return

    # Ochiq sessiyani olamiz
    session = await db.get_worker_open_session(worker["id"])
    if not session:
        now_tashkent = datetime.datetime.now(TIMEZONE)
        session = await db.get_worker_today_session(worker["id"], now_tashkent.date())

    if not session or not session.get("arrival_time"):
        await message.answer("Ochiq ish sessiyasi topilmadi.", reply_markup=ReplyKeyboardRemove())
        await state.clear()
        return

    settings = await db.get_settings()
    target_lat = settings.get("location_lat", 41.311081)
    target_lon = settings.get("location_lon", 69.240562)
    radius = settings.get("location_radius", 150)

    u_lat = message.location.latitude
    u_lon = message.location.longitude

    in_range, dist = is_within_radius(u_lat, u_lon, target_lat, target_lon, radius)

    if not in_range:
        await message.answer(
            f"⚠️ <b>Siz korxona hududida emassiz!</b>\n\n"
            f"📏 Belgilangan radius: <b>{int(radius)} metr</b>\n"
            f"📍 Sizning masofangiz: <b>{int(dist)} metr</b>\n\n"
            "Iltimos, ish joyida turgan holda ketishni qayd eting.",
            reply_markup=ReplyKeyboardRemove(),
            parse_mode="HTML"
        )
        await state.clear()
        return

    now_tashkent = datetime.datetime.now(TIMEZONE)
    arrival_time = session["arrival_time"]
    diff = now_tashkent - arrival_time
    total_hours = round(max(0.0, diff.total_seconds() / 3600.0), 2)
    session_date = session["date"]

    await db.clock_out(
        worker_id=worker["id"],
        target_date=session_date,
        departure_time=now_tashkent,
        total_hours=total_hours,
        lat=u_lat,
        lon=u_lon
    )

    dep_time_str = now_tashkent.strftime("%H:%M")
    dur_str = format_hours_mins(total_hours)

    await message.answer(
        f"✅ <b>Ish kuni yakunlandi! Rahmat!</b>\n\n"
        f"⏰ Ketgan vaqtingiz: <b>{dep_time_str}</b>\n"
        f"⏱ Bugun ishladingiz: <b>{dur_str}</b>\n\n"
        "Yaxshi dam oling! 🌙",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="HTML"
    )
    await state.clear()

    # Adminlarga bildirishnoma
    await notify_attendance_event(
        worker_name=worker["full_name"],
        role_name=worker.get("role_name", "Xodim"),
        event_type="out",
        time_str=dep_time_str,
        work_duration_str=dur_str
    )


# ==========================================
# 🌙 DAM OLISH KUNI (REST DAY)
# ==========================================

async def handle_rest_day_action(user_id: int, state: FSMContext):
    """Dam olish kunini belgilash mantiqi."""
    await state.clear()
    worker = await db.get_worker_by_tg_id(user_id)
    if not worker:
        return "Siz xodimlar ro'yxatida emassiz.", False

    now_tashkent = datetime.datetime.now(TIMEZONE)
    session = await db.get_worker_today_session(worker["id"], now_tashkent.date())

    if session and session.get("arrival_time"):
        return "⚠️ Siz bugun ishga kelgansiz, dam olish deb belgilay olmaysiz.", False
    else:
        await db.mark_rest_day(worker["id"], now_tashkent.date())
        await notify_attendance_event(
            worker_name=worker["full_name"],
            role_name=worker.get("role_name", "Xodim"),
            event_type="rest",
            time_str=now_tashkent.strftime("%H:%M"),
        )
        return "🌙 <b>Bugungi kuningiz dam olish kuni deb belgilandi.</b>\nYaxshi hordiq chiqaring!", True


@router.callback_query(F.data == "worker:rest")
async def cb_rest_day(callback: CallbackQuery, state: FSMContext):
    """Dam olish kunini belgilash (Inline tugma)."""
    text, _ = await handle_rest_day_action(callback.from_user.id, state)
    await edit_menu(callback.message, text, get_back_keyboard("worker:home"))
    await callback.answer()


@router.message(F.text.in_(["🌙 Dam oldim", "Dam oldim"]))
async def msg_rest_day(message: Message, state: FSMContext):
    """Dam olish kunini belgilash (Reply tugma / Matn)."""
    text, _ = await handle_rest_day_action(message.from_user.id, state)
    await message.answer(text, reply_markup=get_back_keyboard("worker:home"), parse_mode="HTML")


# ==========================================
# 📊 SHAXSIY HISOBOT VA PROFIL
# ==========================================

async def get_worker_stats_text(user_id: int):
    """Xodimning oylik statistikasi matni."""
    worker = await db.get_worker_by_tg_id(user_id)
    if not worker:
        return None
    now = datetime.datetime.now(TIMEZONE)
    stats = await db.get_worker_month_stats(worker["id"], now.year, now.month)
    sal_type = stats.get("salary_type") or worker.get("salary_type") or "monthly"
    sal_unit = "kunlik" if sal_type == "daily" else "oylik"
    sal_display = f"{format_currency(worker.get('monthly_salary'))} ({sal_unit})"

    text = (
        f"📊 <b>SHAXSIY HISOBOT — {now.strftime('%B %Y')}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Xodim:</b> {safe_html(worker['full_name'])}\n"
        f"🎭 <b>Lavozim:</b> {safe_html(worker.get('role_name', 'Xodim'))}\n"
        f"💰 <b>Belgilangan stavka:</b> {sal_display}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📅 <b>Ishlangan kunlar:</b> {stats['days_worked']} kun\n"
        f"🌙 <b>Dam olingan kunlar:</b> {stats['rest_days']} kun\n"
        f"⏱ <b>Jami ishlangan soat:</b> {format_hours_mins(stats['total_hours'])}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💵 <b>Hisoblangan ish haqi:</b> {format_currency(stats['earned_salary'])}\n"
        f"💸 <b>Olingan avanslar:</b> {format_currency(stats['advances_sum'])}\n"
        f"💳 <b>Hozirgi qoldiq (Raschyot):</b> <b>{format_currency(stats['balance'])}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )
    return text


@router.callback_query(F.data == "worker:stats")
async def cb_my_stats(callback: CallbackQuery, state: FSMContext):
    """Xodimning o'z shaxsiy oylik hisobotini ko'rishi (Inline tugma)."""
    await state.clear()
    text = await get_worker_stats_text(callback.from_user.id)
    if not text:
        await callback.answer("Siz xodimlar ro'yxatida emassiz.", show_alert=True)
        return
    await edit_menu(callback.message, text, get_back_keyboard("worker:home"))
    await callback.answer()


@router.message(F.text.in_(["📊 Mening hisobotim", "Mening hisobotim"]))
async def msg_my_stats(message: Message, state: FSMContext):
    """Xodimning o'z shaxsiy oylik hisobotini ko'rishi (Reply tugma / Matn)."""
    await state.clear()
    text = await get_worker_stats_text(message.from_user.id)
    if not text:
        await message.answer("Siz xodimlar ro'yxatida emassiz.")
        return
    await message.answer(text, reply_markup=get_back_keyboard("worker:home"), parse_mode="HTML")


async def get_worker_profile_text(user_id: int):
    """Xodim profili ma'lumotlari matni."""
    worker = await db.get_worker_by_tg_id(user_id)
    if not worker:
        return None
    added_str = worker["added_date"].astimezone(TIMEZONE).strftime("%d.%m.%Y") if worker.get("added_date") else "—"
    sal_type = worker.get("salary_type") or "monthly"
    sal_label = "Kunlik stavka" if sal_type == "daily" else "Oylik maosh"

    text = (
        "👤 <b>SIZNING PROFILINGIZ</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📝 <b>F.I.O:</b> {safe_html(worker['full_name'])}\n"
        f"🎭 <b>Lavozim:</b> {safe_html(worker.get('role_name', 'Xodim'))}\n"
        f"📱 <b>Telefon:</b> {safe_html(worker.get('phone_number') or 'Kiritilmagan')}\n"
        f"🆔 <b>Telegram ID:</b> <code>{worker['tg_id']}</code>\n"
        f"💰 <b>{sal_label}:</b> {format_currency(worker.get('monthly_salary'))}\n"
        f"📅 <b>Ishga qabul qilingan:</b> {added_str}\n"
        f"🏢 <b>Korxona:</b> {safe_html(RESTAURANT_NAME)}\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )
    return text


@router.callback_query(F.data == "worker:profile")
async def cb_my_profile(callback: CallbackQuery, state: FSMContext):
    """Xodimning shaxsiy profili (Inline tugma)."""
    await state.clear()
    text = await get_worker_profile_text(callback.from_user.id)
    if not text:
        await callback.answer("Siz xodimlar ro'yxatida emassiz.", show_alert=True)
        return
    await edit_menu(callback.message, text, get_back_keyboard("worker:home"))
    await callback.answer()


@router.message(F.text.in_(["👤 Profilim", "Profilim"]))
async def msg_my_profile(message: Message, state: FSMContext):
    """Xodimning shaxsiy profili (Reply tugma / Matn)."""
    await state.clear()
    text = await get_worker_profile_text(message.from_user.id)
    if not text:
        await message.answer("Siz xodimlar ro'yxatida emassiz.")
        return
    await message.answer(text, reply_markup=get_back_keyboard("worker:home"), parse_mode="HTML")


async def get_contact_text():
    """Ma'muriyat aloqa ma'lumotlari matni."""
    settings = await db.get_settings()
    contact = settings.get("admin_contact") or "@admin"
    return (
        f"📞 <b>Ma'muriyat bilan bog'lanish:</b>\n\n"
        f"Savollar yoki murojaatlar bo'lsa: {safe_html(contact)}\n"
        f"🏢 <b>{safe_html(RESTAURANT_NAME)}</b> ma'muriyati"
    )


@router.callback_query(F.data == "worker:contact")
async def cb_contact_admin(callback: CallbackQuery, state: FSMContext):
    """Ma'muriyat bilan bog'lanish (Inline tugma)."""
    await state.clear()
    text = await get_contact_text()
    await edit_menu(callback.message, text, get_back_keyboard("worker:home"))
    await callback.answer()


@router.message(F.text.in_(["📞 Bog'lanish", "Bog'lanish"]))
async def msg_contact_admin(message: Message, state: FSMContext):
    """Ma'muriyat bilan bog'lanish (Reply tugma / Matn)."""
    await state.clear()
    text = await get_contact_text()
    await message.answer(text, reply_markup=get_back_keyboard("worker:home"), parse_mode="HTML")


@router.message(F.text == "⬅️ Bekor qilish")
async def cancel_reply_action(message: Message, state: FSMContext):
    """Reply klaviaturadagi bekor qilish tugmasi."""
    await state.clear()
    await message.answer(
        "Amal bekor qilindi.",
        reply_markup=ReplyKeyboardRemove()
    )
