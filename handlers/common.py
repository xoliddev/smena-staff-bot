import re
import logging
from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

import database as db
from config import RESTAURANT_NAME
from keyboards.inline_keyboards import (
    get_admin_main_menu,
    get_worker_main_menu,
    get_roles_selection_keyboard,
    get_job_application_keyboard,
)
from states import WorkerApplicationStates
from utils.notifier import notify_all_admins
from utils.ui import dismiss_legacy_reply_keyboard, edit_menu, safe_html

logger = logging.getLogger(__name__)
router = Router(name="common_router")


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Start buyrug'i — foydalanuvchi turini aniqlaydi va tegishli menyuni ochadi."""
    await state.clear()
    tg_id = message.from_user.id
    user_name = safe_html(message.from_user.full_name or "Hurmatli foydalanuvchi")

    # 1. Admin yoki Superadmin tekshiruvi
    is_admin = await db.is_admin_or_superadmin(tg_id)
    if is_admin:
        await dismiss_legacy_reply_keyboard(message.chat.id)
        await message.answer(
            f"Assalomu alaykum, <b>{user_name}</b>!\n"
            f"👑 <b>{safe_html(RESTAURANT_NAME)}</b> boshqaruv paneliga xush kelibsiz.",
            reply_markup=get_admin_main_menu()
        )
        return

    # 2. Xodim tekshiruvi
    worker = await db.get_worker_by_tg_id(tg_id)
    if worker:
        await dismiss_legacy_reply_keyboard(message.chat.id)
        role_name = safe_html(worker.get("role_name") or "Xodim")
        worker_name = safe_html(worker["full_name"])
        await message.answer(
            f"Assalomu alaykum, <b>{worker_name}</b> (<i>{role_name}</i>)!\n"
            f"🏢 <b>{safe_html(RESTAURANT_NAME)}</b> ishchi kabinetiga xush kelibsiz.",
            reply_markup=get_worker_main_menu()
        )
        return

    # 3. Kutilayotgan ariza tekshiruvi
    application = await db.get_application_by_tg_id(tg_id)
    if application and application.get("status") == "pending":
        role_name = safe_html(application.get("role_name") or "Tanlangan lavozim")
        app_name = safe_html(application["full_name"])
        await message.answer(
            f"⏳ Hurmatli <b>{app_name}</b>!\n\n"
            f"Sizning <b>{role_name}</b> lavozimiga topshirgan arizangiz ma'muriyat tomonidan ko'rib chiqilmoqda.\n"
            f"Tez orada javob beriladi. Iltimos kuting!",
        )
        return

    # 4. Yangi foydalanuvchi — Ariza topshirish taklifi
    await message.answer(
        f"Assalomu alaykum, <b>{user_name}</b>!\n\n"
        f"🏢 <b>{safe_html(RESTAURANT_NAME)}</b> korxonasining rasmiy botiga xush kelibsiz.\n"
        f"Agar siz korxonamiz xodimi bo'lsangiz yoki ishga kirmoqchi bo'lsangiz, iltimos ro'yxatdan o'tish arizasini to'ldiring.\n\n"
        f"✍️ Iltimos, <b>to'liq ism va familiyangizni</b> kiriting (Masalan: <i>Ali Valiyev</i>):",
    )
    await state.set_state(WorkerApplicationStates.waiting_for_name)


@router.callback_query(F.data == "admin:home")
async def cb_admin_home(callback: CallbackQuery, state: FSMContext):
    """Har bir admin bo'limidan bitta ekrandagi bosh menyuga qaytish."""
    await state.clear()
    if not await db.is_admin_or_superadmin(callback.from_user.id):
        await callback.answer("Ruxsat yo'q!", show_alert=True)
        return
    await edit_menu(
        callback.message,
        f"👑 <b>{safe_html(RESTAURANT_NAME.upper())} BOSHQARUV PANELI</b>\n\nKerakli bo'limni tanlang:",
        get_admin_main_menu(),
    )
    await callback.answer()


@router.callback_query(F.data == "worker:home")
async def cb_worker_home(callback: CallbackQuery, state: FSMContext):
    """Xodim kabinetining bosh ekraniga qaytish."""
    await state.clear()
    worker = await db.get_worker_by_tg_id(callback.from_user.id)
    if not worker:
        await callback.answer("Siz xodimlar ro'yxatida emassiz.", show_alert=True)
        return
    role_name = safe_html(worker.get("role_name") or "Xodim")
    worker_name = safe_html(worker["full_name"])
    await edit_menu(
        callback.message,
        f"👋 <b>{worker_name}</b> (<i>{role_name}</i>)\n"
        f"🏢 <b>{safe_html(RESTAURANT_NAME)}</b> ishchi kabinetiga xush kelibsiz.",
        get_worker_main_menu(),
    )
    await callback.answer()


@router.callback_query(F.data == "app:cancel")
async def cb_application_cancel(callback: CallbackQuery, state: FSMContext):
    """Ro'yxatdan o'tish jarayonini inline tugma bilan bekor qilish."""
    await state.clear()
    await edit_menu(callback.message, "Amal bekor qilindi. Qaytadan boshlash uchun /start bosing.", None)
    await callback.answer()


# ==========================================
# 📝 ARIZA TOPSHIRISH JARAYONI (FSM)
# ==========================================

@router.message(WorkerApplicationStates.waiting_for_name)
async def process_app_name(message: Message, state: FSMContext):
    """Ariza uchun ismni qabul qilish."""
    name = (message.text or "").strip()
    if len(name) < 3 or len(name) > 100:
        await message.answer("⚠️ Iltimos, ism va familiyangizni to'liq va to'g'ri kiriting:")
        return

    await state.update_data(full_name=name)
    await message.answer(
        f"Rahmat, <b>{safe_html(name)}</b>!\n\n"
        f"📱 Endi telefon raqamingizni yozing yoki kontakt sifatida yuboring:\n"
        f"<i>Masalan: +998 90 123 45 67</i>"
    )
    await state.set_state(WorkerApplicationStates.waiting_for_phone)


@router.message(WorkerApplicationStates.waiting_for_phone, F.contact | F.text)
async def process_app_phone(message: Message, state: FSMContext):
    """Telefon raqamni qabul qilish."""
    if message.contact:
        phone = message.contact.phone_number
    else:
        phone = (message.text or "").strip()

    # Faqat raqam va plyus belgilari qolishi uchun tozalash
    digits_only = re.sub(r"[^\d+]", "", phone)
    if len(re.sub(r"[^\d]", "", digits_only)) < 7:
        await message.answer("⚠️ Iltimos, to'g'ri telefon raqam kiriting (masalan: <code>+998901234567</code>):")
        return

    if not digits_only.startswith("+"):
        digits_only = "+" + digits_only

    await state.update_data(phone_number=digits_only)

    # Rollar ro'yxatini chiqaramiz
    roles = await db.get_all_roles(only_active=True)
    if not roles:
        await message.answer(
            "⚠️ Tizimda mavjud rollar topilmadi. Ma'muriyat bilan bog'laning.",
        )
        await state.clear()
        return

    await message.answer(
        "🎭 Qaysi lavozim / rolda ishlamoqchisiz? Tanlang:",
        reply_markup=get_roles_selection_keyboard(
            roles, action_prefix="app_role_", back_callback="app:cancel"
        )
    )
    await state.set_state(WorkerApplicationStates.waiting_for_role)


@router.callback_query(WorkerApplicationStates.waiting_for_role, F.data.startswith("app_role_"))
async def process_app_role(callback: CallbackQuery, state: FSMContext):
    """Rol tanlanganda arizani bazaga yozish va adminga bildirish."""
    role_id_str = callback.data.replace("app_role_", "")
    role_id = int(role_id_str)

    role = await db.get_role_by_id(role_id)
    role_name = role["name"] if role else "Noma'lum"

    data = await state.get_data()
    full_name = data.get("full_name") or "Nomzod"
    phone = data.get("phone_number") or ""
    tg_id = callback.from_user.id
    username = callback.from_user.username

    # Arizani bazaga yozamiz
    app_id = await db.create_or_update_application(
        tg_id=tg_id,
        full_name=full_name,
        phone_number=phone,
        username=username,
        selected_role_id=role_id
    )

    await state.clear()

    safe_name = safe_html(full_name)
    safe_phone = safe_html(phone)
    safe_role = safe_html(role_name)

    await edit_menu(
        callback.message,
        f"✅ <b>Arizangiz muvaffaqiyatli qabul qilindi!</b>\n\n"
        f"👤 <b>F.I.O:</b> {safe_name}\n"
        f"📱 <b>Telefon:</b> {safe_phone}\n"
        f"🎭 <b>Tanlangan rol:</b> {safe_role}\n\n"
        f"⏳ Ma'muriyat arizangizni tasdiqlashi bilan sizga xabar beriladi.",
        None
    )
    await callback.answer("Arizangiz yuborildi!")

    # Barcha adminlarga bildirishnoma yuboramiz
    u_display = f"@{safe_html(username)}" if username else "mavjud_emas"
    admin_msg = (
        f"📩 <b>YANGI ISHGA KIRISH ARIZASI!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Nomzod:</b> {safe_name}\n"
        f"📱 <b>Telefon:</b> {safe_phone}\n"
        f"🎭 <b>Lavozim:</b> {safe_role}\n"
        f"🔗 <b>Username:</b> {u_display}\n"
        f"🆔 <b>Telegram ID:</b> <code>{tg_id}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Qabul qilasizmi?"
    )
    await notify_all_admins(
        text=admin_msg,
        reply_markup=get_job_application_keyboard(app_id)
    )


@router.callback_query(F.data == "noop")
async def cb_noop(callback: CallbackQuery):
    """Inert / informativ tugmalar uchun xavfsiz javob."""
    try:
        await callback.answer()
    except Exception:
        pass


@router.message(F.text.in_([
    "👥 Xodimlar", "💰 Moliya (Avans/Raschyot)", "⏱ Bugungi Davomat",
    "📊 Hisobotlar (Excel)", "🎭 Rollar Boshqaruvi", "⚙️ Sozlamalar"
]))
async def handle_legacy_admin_buttons(message: Message, state: FSMContext):
    """Eski reply tugmalarni yangi zamonaviy inline menyuga yo'naltirish."""
    await state.clear()
    if not await db.is_admin_or_superadmin(message.from_user.id):
        return
    await dismiss_legacy_reply_keyboard(message.chat.id)
    await message.answer(
        f"👑 <b>{safe_html(RESTAURANT_NAME.upper())} BOSHQARUV PANELI</b>\n\nKerakli bo'limni tanlang:",
        reply_markup=get_admin_main_menu()
    )
