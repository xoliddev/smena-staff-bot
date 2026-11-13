import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

import database as db
from keyboards.inline_keyboards import get_roles_management_keyboard, get_back_keyboard
from states import RoleStates
from utils.ui import edit_menu, remember_menu, update_menu_after_input, safe_html
from utils.middlewares import AdminOnlyCallbackMiddleware

logger = logging.getLogger(__name__)
router = Router(name="admin_roles_router")
router.callback_query.middleware(AdminOnlyCallbackMiddleware())


@router.callback_query(F.data == "admin:roles")
async def cb_roles_management(callback: CallbackQuery, state: FSMContext):
    """Rollar boshqaruvi menyusini ochish."""
    await state.clear()
    if not await db.is_admin_or_superadmin(callback.from_user.id):
        return

    roles = await db.get_roles_with_worker_counts()

    text = (
        f"🎭 <b>KORXONA ROLLARI VA LAVOZIMLARI</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Bu bo'limda siz istalgan yangi rol (lavozim) qo'shishingiz, "
        f"nomini o'zgartirishingiz yoki o'chirishingiz mumkin.\n\n"
        f"📋 <b>Mavjud rollar soni:</b> {len(roles)} ta\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Tahrirlash yoki o'chirish uchun kerakli rolni tanlang:"
    )

    await edit_menu(callback.message, text, get_roles_management_keyboard(roles))
    await callback.answer()


@router.callback_query(F.data == "roles_management_back")
async def cb_roles_management_back(callback: CallbackQuery, state: FSMContext):
    """Ortga qaytish (Rollar boshqaruvi menyusiga)."""
    await state.clear()
    roles = await db.get_roles_with_worker_counts()
    
    text = (
        f"🎭 <b>KORXONA ROLLARI VA LAVOZIMLARI</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Bu bo'limda siz istalgan yangi rol (lavozim) qo'shishingiz, "
        f"nomini o'zgartirishingiz yoki o'chirishingiz mumkin.\n\n"
        f"📋 <b>Mavjud rollar soni:</b> {len(roles)} ta\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Tahrirlash yoki o'chirish uchun kerakli rolni tanlang:"
    )
    await edit_menu(callback.message, text, get_roles_management_keyboard(roles))
    try:
        await callback.answer()
    except Exception:
        pass


# ==========================================
# ➕ YANGI ROL QO'SHISH
# ==========================================

@router.callback_query(F.data == "role_add_new")
async def cb_add_role_start(callback: CallbackQuery, state: FSMContext):
    """Yangi rol nomini so'rash."""
    if not await db.is_admin_or_superadmin(callback.from_user.id):
        await callback.answer("Ruxsat yo'q!", show_alert=True)
        return

    await remember_menu(state, callback.message)
    await edit_menu(
        callback.message,
        "✍️ Yangi rol (lavozim) nomini kiriting:\n"
        "<i>(Masalan: 🥗 Salatchi, 🚚 Yetkazib beruvchi, ☕ Barista)</i>",
        get_back_keyboard("roles_management_back")
    )
    await state.set_state(RoleStates.waiting_for_role_name)
    try:
        await callback.answer()
    except Exception:
        pass


@router.message(RoleStates.waiting_for_role_name)
async def process_role_name(message: Message, state: FSMContext):
    """Rol nomini qabul qilish va tavsif so'rash."""
    role_name = (message.text or "").strip()
    if len(role_name) < 2:
        await update_menu_after_input(
            message, state, "⚠️ Rol nomi juda qisqa. Iltimos qaytadan kiriting:",
            get_back_keyboard("roles_management_back"),
        )
        return

    await state.update_data(new_role_name=role_name)
    await update_menu_after_input(
        message, state,
        f"Rol nomi: <b>{safe_html(role_name)}</b>\n\n"
        f"Endi ushbu rol uchun qisqa tavsif kiriting (yoki 'yoq' deb yozing):",
        get_back_keyboard("roles_management_back")
    )
    await state.set_state(RoleStates.waiting_for_role_desc)


@router.message(RoleStates.waiting_for_role_desc)
async def process_role_desc(message: Message, state: FSMContext):
    """Rol tavsifini qabul qilish va bazaga yozish."""
    desc = (message.text or "").strip()
    if desc.lower() in ("yoq", "yo'q", "yo’q", "-"):
        desc = ""

    data = await state.get_data()
    role_name = data.get("new_role_name")

    role_id = await db.add_role(name=role_name, description=desc)
    if role_id:
        roles = await db.get_roles_with_worker_counts()
        await update_menu_after_input(
            message, state,
            f"✅ <b>Yangi rol muvaffaqiyatli qo'shildi!</b>\n\n"
            f"🎭 <b>Rol:</b> {safe_html(role_name)}\n"
            f"📝 <b>Tavsif:</b> {safe_html(desc or 'Kiritilmagan')}",
            get_roles_management_keyboard(roles)
        )
    else:
        await update_menu_after_input(
            message, state, "⚠️ Bunday nomdagi rol allaqachon mavjud!",
            get_back_keyboard("roles_management_back"),
        )
    await state.clear()


# ==========================================
# ✏️ ROLNI TAHRIRLASH
# ==========================================

@router.callback_query(F.data.startswith("role_edit_"))
async def cb_edit_role_start(callback: CallbackQuery, state: FSMContext):
    """Rolni tahrirlash — yangi nom so'rash."""
    if not await db.is_admin_or_superadmin(callback.from_user.id):
        return

    role_id = int(callback.data.replace("role_edit_", ""))
    role = await db.get_role_by_id(role_id)

    if not role:
        await callback.answer("Rol topilmadi!", show_alert=True)
        return

    await state.update_data(editing_role_id=role_id)
    await remember_menu(state, callback.message)
    await edit_menu(
        callback.message,
        f"✏️ <b>{safe_html(role['name'])}</b> rolining yangi nomini kiriting:",
        get_back_keyboard("roles_management_back")
    )
    await state.set_state(RoleStates.waiting_for_edit_role_name)
    try:
        await callback.answer()
    except Exception:
        pass


@router.message(RoleStates.waiting_for_edit_role_name)
async def process_edit_role_name(message: Message, state: FSMContext):
    """Tahrirlangan rol nomini saqlash."""
    new_name = (message.text or "").strip()
    data = await state.get_data()
    role_id = data.get("editing_role_id")

    await db.update_role(role_id=role_id, name=new_name)
    roles = await db.get_roles_with_worker_counts()
    await update_menu_after_input(
        message, state,
        f"✅ Rol nomi <b>{safe_html(new_name)}</b> ga o'zgartirildi!",
        get_roles_management_keyboard(roles)
    )
    await state.clear()


@router.callback_query(F.data.startswith("role_view_"))
async def cb_view_role(callback: CallbackQuery):
    """Rol haqida qisqa ma'lumotni toza ekranda ko'rsatish."""
    role_id = int(callback.data.replace("role_view_", ""))
    role = await db.get_role_by_id(role_id)
    if not role:
        await callback.answer("Rol topilmadi!", show_alert=True)
        return
    await edit_menu(
        callback.message,
        f"🎭 <b>{safe_html(role['name'])}</b>\n\n📝 {safe_html(role.get('description') or 'Tavsif kiritilmagan.')}",
        get_back_keyboard("roles_management_back"),
    )
    await callback.answer()


# ==========================================
# 🗑 ROLNI O'CHIRISH
# ==========================================

@router.callback_query(F.data.startswith("role_delete_"))
async def cb_delete_role(callback: CallbackQuery, state: FSMContext):
    """Rolni o'chirish."""
    if not await db.is_admin_or_superadmin(callback.from_user.id):
        return

    role_id = int(callback.data.replace("role_delete_", ""))
    success, msg = await db.delete_role(role_id)

    try:
        await callback.answer(msg, show_alert=True)
    except Exception:
        pass

    roles = await db.get_roles_with_worker_counts()
    text = (
        f"🎭 <b>KORXONA ROLLARI VA LAVOZIMLARI</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Bu bo'limda siz istalgan yangi rol (lavozim) qo'shishingiz, "
        f"nomini o'zgartirishingiz yoki o'chirishingiz mumkin.\n\n"
        f"📋 <b>Mavjud rollar soni:</b> {len(roles)} ta\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Tahrirlash yoki o'chirish uchun kerakli rolni tanlang:"
    )
    await edit_menu(
        callback.message,
        text,
        get_roles_management_keyboard(roles)
    )
