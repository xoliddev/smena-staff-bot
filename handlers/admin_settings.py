import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

import database as db
from config import RESTAURANT_NAME
from keyboards.inline_keyboards import (
    get_settings_keyboard,
    get_radius_selection_keyboard,
)
from states import SettingsStates
from utils.ui import edit_menu, remember_menu, update_menu_after_input, safe_html
from utils.middlewares import AdminOnlyCallbackMiddleware

logger = logging.getLogger(__name__)
router = Router(name="admin_settings_router")
router.callback_query.middleware(AdminOnlyCallbackMiddleware())


@router.callback_query(F.data == "admin:settings")
async def cb_settings_menu(callback: CallbackQuery, state: FSMContext):
    """Tizim sozlamalari menyusi."""
    await state.clear()
    if not await db.is_admin_or_superadmin(callback.from_user.id):
        return

    settings = await db.get_settings()
    lat = settings.get("location_lat")
    lon = settings.get("location_lon")
    radius = settings.get("location_radius")
    group_id = settings.get("work_log_group_id") or "Ulanmagan"
    contact = settings.get("admin_contact") or "O'rnatilmagan"

    text = (
        f"⚙️ <b>TIZIM SOZLAMALARI</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📍 <b>Korxona lokatsiyasi:</b> <code>{lat}, {lon}</code>\n"
        f"🎯 <b>Ruxsat etilgan radius:</b> <b>{int(radius)} metr</b>\n"
        f"📢 <b>Log Guruhi ID:</b> <code>{group_id}</code>\n"
        f"📞 <b>Aloqa kontakti:</b> {safe_html(contact)}\n"
        f"🏢 <b>Korxona:</b> {safe_html(RESTAURANT_NAME)}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"O'zgartirish uchun kerakli tugmani bosing:"
    )

    await edit_menu(callback.message, text, get_settings_keyboard())
    await callback.answer()


# ==========================================
# 📍 LOKATSIYANI OSON YANGILASH (TELEGRAM LOCATION ORQALI)
# ==========================================

@router.callback_query(F.data == "set_location_prompt")
async def cb_prompt_location(callback: CallbackQuery, state: FSMContext):
    """Admin lokatsiya yuborishi uchun taklif."""
    await remember_menu(state, callback.message)
    await edit_menu(
        callback.message,
        "📍 <b>Korxona lokatsiyasini belgilash juda oson!</b>\n\n"
        "Shunchaki Telegram orqali korxona turgan joyning <b>Joylashuvini (Location / Геопозиция)</b> yuboring.\n"
        "Bot avtomatik ravishda yangi koordinatalarni saqlab oladi.",
        InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Sozlamalarga qaytish", callback_data="settings_back")]])
    )
    await state.set_state(SettingsStates.waiting_for_location)
    await callback.answer()


@router.message(SettingsStates.waiting_for_location, F.location)
async def process_new_settings_location(message: Message, state: FSMContext):
    """Yuborilgan lokatsiyani bazaga saqlash."""
    lat = message.location.latitude
    lon = message.location.longitude

    await db.update_location(lat=lat, lon=lon)
    await update_menu_after_input(
        message, state,
        f"✅ <b>Korxona lokatsiyasi muvaffaqiyatli yangilandi!</b>\n\n"
        f"📍 <b>Kenglik (Latitude):</b> <code>{lat}</code>\n"
        f"📍 <b>Uzunlik (Longitude):</b> <code>{lon}</code>\n\n"
        f"Endi xodimlar ushbu nuqta atrofida davomat qiladilar.",
        get_settings_keyboard(),
    )
    await state.clear()


@router.message(SettingsStates.waiting_for_location)
async def process_new_settings_location_invalid(message: Message, state: FSMContext):
    """Lokatsiya o'rniga boshqa narsa yuborilganda ogohlantirish."""
    await update_menu_after_input(
        message, state,
        "⚠️ <b>Iltimos, faqat GPS Lokatsiya yuboring!</b>\n\n"
        "Telegramdagi 📎 (skrepka) tugmasi → <b>Location (Joylashuv)</b> orqali korxona joyini yuboring.\n\n"
        "Yoki ortga qaytish uchun tugmani bosing:",
        InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Sozlamalarga qaytish", callback_data="settings_back")]])
    )


# ==========================================
# 📐 RADIUSNI O'ZGARTIRISH
# ==========================================

@router.callback_query(F.data == "set_radius_menu")
async def cb_radius_menu(callback: CallbackQuery):
    """Radius tanlash menyusi."""
    await edit_menu(
        callback.message,
        "📐 <b>Ruxsat etilgan masofa (radius)ni tanlang:</b>\n\n"
        "Xodim ishga kelganda ushbu radius ichida bo'lsa, tizim uni ishda deb qabul qiladi.",
        get_radius_selection_keyboard()
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data.startswith("radius_set_"))
async def cb_set_radius_value(callback: CallbackQuery):
    """Tanlangan radiusni saqlash."""
    radius = float(callback.data.replace("radius_set_", ""))
    await db.update_location_radius(radius)

    try:
        await callback.answer(f"Radius {int(radius)} metr qilib belgilandi!", show_alert=True)
    except Exception:
        pass

    settings = await db.get_settings()
    await edit_menu(
        callback.message,
        f"✅ <b>Radius {int(radius)} metrga o'zgartirildi!</b>",
        get_settings_keyboard()
    )


@router.callback_query(F.data == "settings_back")
async def cb_settings_back(callback: CallbackQuery, state: FSMContext):
    """Sozlamalar boshiga qaytish."""
    await state.clear()
    settings = await db.get_settings()
    lat = settings.get("location_lat")
    lon = settings.get("location_lon")
    radius = settings.get("location_radius")
    group_id = settings.get("work_log_group_id") or "Ulanmagan"
    contact = settings.get("admin_contact") or "O'rnatilmagan"

    text = (
        f"⚙️ <b>TIZIM SOZLAMALARI</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📍 <b>Korxona lokatsiyasi:</b> <code>{lat}, {lon}</code>\n"
        f"🎯 <b>Ruxsat etilgan radius:</b> <b>{int(radius)} metr</b>\n"
        f"📢 <b>Log Guruhi ID:</b> <code>{group_id}</code>\n"
        f"📞 <b>Aloqa kontakti:</b> {safe_html(contact)}\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )
    await edit_menu(callback.message, text, get_settings_keyboard())
    try:
        await callback.answer()
    except Exception:
        pass


# ==========================================
# 👥 ADMINLAR BOSHQARUVI
# ==========================================

@router.callback_query(F.data == "set_admins_menu")
async def cb_admins_menu(callback: CallbackQuery):
    """Adminlar ro'yxati va boshqaruvi."""
    if not await db.is_superadmin(callback.from_user.id):
        await callback.answer("Adminlarni faqat Superadmin boshqara oladi!", show_alert=True)
        return

    admins = await db.get_all_admins()
    kb = []

    for a in admins:
        role_label = "👑 Superadmin" if a["role"] == "superadmin" else "👨‍💼 Admin"
        btn_text = f"{a['full_name']} ({role_label})"
        del_btn = [
            InlineKeyboardButton(text=btn_text, callback_data="noop"),
            InlineKeyboardButton(text="🗑", callback_data=f"del_admin_{a['tg_id']}")
        ] if a["role"] != "superadmin" else [InlineKeyboardButton(text=btn_text, callback_data="noop")]
        kb.append(del_btn)

    kb.append([InlineKeyboardButton(text="➕ Yangi Admin Qo'shish", callback_data="add_admin_start")])
    kb.append([InlineKeyboardButton(text="⬅️ Ortga", callback_data="settings_back")])

    await edit_menu(
        callback.message,
        "👥 <b>ADMINLAR RO'YXATI VA BOSHQARUVI</b>\n\n"
        "Barcha xabarlar va moliya hisobotlari ushbu adminlarga yuboriladi:",
        InlineKeyboardMarkup(inline_keyboard=kb)
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data == "add_admin_start")
async def cb_add_admin_start(callback: CallbackQuery, state: FSMContext):
    """Yangi admin Telegram ID sini so'rash."""
    await remember_menu(state, callback.message)
    await edit_menu(
        callback.message,
        "✍️ Yangi adminning <b>Telegram ID raqamini</b> kiriting:\n"
        "<i>(Masalan: <code>123456789</code>)</i>",
        InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Adminlarga qaytish", callback_data="set_admins_menu")]]),
    )
    await state.set_state(SettingsStates.waiting_for_new_admin_id)
    await callback.answer()


@router.message(SettingsStates.waiting_for_new_admin_id)
async def process_new_admin_id(message: Message, state: FSMContext):
    """Admin ID sini qabul qilish va ismini so'rash."""
    clean_id = (message.text or "").strip()
    if not clean_id.isdigit():
        await message.answer("⚠️ Iltimos faqat sonlardan iborat Telegram ID kiriting:")
        return

    await state.update_data(new_admin_tg_id=int(clean_id))
    await update_menu_after_input(
        message, state, "Endi yangi adminning <b>Ism va Familiyasini</b> kiriting:",
        InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Adminlarga qaytish", callback_data="set_admins_menu")]]),
    )
    await state.set_state(SettingsStates.waiting_for_new_admin_name)


@router.message(SettingsStates.waiting_for_new_admin_name)
async def process_new_admin_name(message: Message, state: FSMContext):
    """Admin ismini qabul qilib saqlash."""
    name = (message.text or "").strip()
    data = await state.get_data()
    tg_id = data["new_admin_tg_id"]
    await db.add_admin(tg_id=tg_id, full_name=name, role="admin")
    await update_menu_after_input(
        message, state, f"✅ <b>{safe_html(name)}</b> muvaffaqiyatli Admin qilib tayinlandi!",
        get_settings_keyboard(),
    )
    await state.clear()


@router.callback_query(F.data.startswith("del_admin_"))
async def cb_del_admin(callback: CallbackQuery):
    """Adminni o'chirish."""
    tg_id = int(callback.data.replace("del_admin_", ""))
    success = await db.remove_admin(tg_id)

    try:
        if success:
            await callback.answer("Admin o'chirildi!", show_alert=True)
        else:
            await callback.answer("Superadminni o'chirib bo'lmaydi!", show_alert=True)
    except Exception:
        pass

    await cb_admins_menu(callback)


# ==========================================
# 📞 ALOQA KONTAKTI VA LOG GURUHI
# ==========================================

@router.callback_query(F.data == "set_contact_menu")
async def cb_contact_menu(callback: CallbackQuery, state: FSMContext):
    """Admin aloqa kontaktini kiritish."""
    await remember_menu(state, callback.message)
    await edit_menu(
        callback.message,
        "📞 Xodimlar murojaat qilishi uchun Telegram username yoki telefon kiriting "
        "(Masalan: <code>@restoran_menejeri</code>):",
        InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Sozlamalarga qaytish", callback_data="settings_back")]]),
    )
    await state.set_state(SettingsStates.waiting_for_admin_contact)
    await callback.answer()


@router.message(SettingsStates.waiting_for_admin_contact)
async def process_contact_input(message: Message, state: FSMContext):
    """Kontaktni saqlash."""
    contact = (message.text or "").strip()
    await db.update_admin_contact(contact)
    await update_menu_after_input(
        message, state, f"✅ Aloqa kontakti <b>{safe_html(contact)}</b> qilib belgilandi!", get_settings_keyboard()
    )
    await state.clear()


@router.callback_query(F.data == "set_group_menu")
async def cb_group_menu(callback: CallbackQuery, state: FSMContext):
    """Log guruhi ID sini toza inline oynada so'rash."""
    await remember_menu(state, callback.message)
    await edit_menu(
        callback.message,
        "📢 Davomat va to'lov loglari yuboriladigan <b>Telegram guruh ID</b>sini kiriting.\n"
        "<i>Masalan: <code>-1001234567890</code></i>",
        InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Sozlamalarga qaytish", callback_data="settings_back")]]),
    )
    await state.set_state(SettingsStates.waiting_for_log_group)
    await callback.answer()


@router.message(SettingsStates.waiting_for_log_group)
async def process_log_group_input(message: Message, state: FSMContext):
    raw_group_id = (message.text or "").strip()
    if not raw_group_id.lstrip("-").isdigit():
        await message.answer("⚠️ Guruh ID faqat sonlardan iborat bo'lishi kerak.")
        return
    group_id = int(raw_group_id)
    await db.update_work_log_group(group_id)
    await update_menu_after_input(
        message, state, f"✅ Log guruhi <code>{group_id}</code> qilib belgilandi.", get_settings_keyboard()
    )
    await state.clear()
