from typing import List, Dict, Any, Optional
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


# Telegram Bot API callback tugmalariga maxsus rang berishni qo'llab-quvvatlamaydi.
# Shu sababli menyular Parfumerose uslubidagi aniq emoji va bloklarga ajratilgan
# ko'rinishda tuziladi. Bu hamma Telegram ilovalarida bir xil, toza ko'rinadi.
def get_admin_main_menu() -> InlineKeyboardMarkup:
    """Adminning doimiy, bitta-xabardagi bosh menyusi."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👥 Xodimlar", callback_data="admin:workers"),
            InlineKeyboardButton(text="💰 Moliya", callback_data="admin:finance"),
        ],
        [
            InlineKeyboardButton(text="⏰ Bugungi davomat", callback_data="admin:attendance"),
            InlineKeyboardButton(text="📊 Excel hisobot", callback_data="admin:reports"),
        ],
        [
            InlineKeyboardButton(text="🎭 Rollar", callback_data="admin:roles"),
            InlineKeyboardButton(text="⚙️ Sozlamalar", callback_data="admin:settings"),
        ],
    ])


def get_worker_main_menu() -> InlineKeyboardMarkup:
    """Xodimning doimiy, bitta-xabardagi bosh menyusi."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🟢 Ishga keldim", callback_data="worker:clock_in"),
            InlineKeyboardButton(text="🔴 Ishdan ketdim", callback_data="worker:clock_out"),
        ],
        [
            InlineKeyboardButton(text="🌙 Dam oldim", callback_data="worker:rest"),
            InlineKeyboardButton(text="📊 Mening hisobotim", callback_data="worker:stats"),
        ],
        [
            InlineKeyboardButton(text="👤 Profilim", callback_data="worker:profile"),
            InlineKeyboardButton(text="📞 Bog'lanish", callback_data="worker:contact"),
        ],
    ])


# ==========================================
# 🎭 ROLLARGA OID INLINE TUGMALAR
# ==========================================

def get_roles_selection_keyboard(
    roles: List[Dict[str, Any]],
    action_prefix: str = "role_select_",
    include_all_option: bool = False,
    back_callback: Optional[str] = None,
) -> InlineKeyboardMarkup:
    """Rollar tanlash uchun 2 ustunli (2x grid) inline keyboard."""
    inline_kb = []
    row = []

    if include_all_option:
        inline_kb.append([InlineKeyboardButton(text="🌟 Barcha Rollar", callback_data=f"{action_prefix}all")])

    for r in roles:
        role_btn = InlineKeyboardButton(
            text=f"{r['name']}",
            callback_data=f"{action_prefix}{r['id']}"
        )
        row.append(role_btn)
        if len(row) == 2:
            inline_kb.append(row)
            row = []

    if row:
        inline_kb.append(row)

    if back_callback:
        inline_kb.append([InlineKeyboardButton(text="⬅️ Ortga", callback_data=back_callback)])

    return InlineKeyboardMarkup(inline_keyboard=inline_kb)


def get_roles_management_keyboard(roles: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """Rollar boshqaruvi menyusi (CRUD)."""
    inline_kb = []

    for r in roles:
        role_name = r['name']
        count = r.get('workers_count', 0)
        inline_kb.append([
            InlineKeyboardButton(text=f"🎭 {role_name} ({count} ta)", callback_data=f"role_view_{r['id']}"),
            InlineKeyboardButton(text="✏️", callback_data=f"role_edit_{r['id']}"),
            InlineKeyboardButton(text="🗑", callback_data=f"role_delete_{r['id']}"),
        ])

    inline_kb.append([
        InlineKeyboardButton(text="➕ Yangi Rol Qo'shish", callback_data="role_add_new")
    ])
    inline_kb.append([
        InlineKeyboardButton(text="⬅️ Bosh menyu", callback_data="admin:home")
    ])
    return InlineKeyboardMarkup(inline_keyboard=inline_kb)


# ==========================================
# 👥 XODIMLAR RO'YXATI (2X GRID VA PAGINATION)
# ==========================================

def get_workers_2x_keyboard(
    workers: List[Dict[str, Any]],
    page: int,
    total_pages: int,
    role_id: Optional[int] = None,
) -> InlineKeyboardMarkup:
    """
    Xodimlar ro'yxatini 2 ustunda (2x grid) va ostida pagination bilan chiqaradi.
    """
    inline_kb = []
    row = []

    role_param = f"_{role_id}" if role_id else "_0"

    # Xodimlarni 2 tadan qilib joylashtiramiz
    for w in workers:
        role_tag = f" ({w.get('role_name', 'Xodim')})" if w.get('role_name') else ""
        btn_text = f"👤 {w['full_name']}{role_tag}"
        # Matn uzun bo'lsa qisqartirish
        if len(btn_text) > 28:
            btn_text = f"👤 {w['full_name'][:22]}..."

        btn = InlineKeyboardButton(
            text=btn_text,
            callback_data=f"worker_view_{w['id']}"
        )
        row.append(btn)
        if len(row) == 2:
            inline_kb.append(row)
            row = []

    if row:
        inline_kb.append(row)

    # Pagination qatori
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"workers_page_{page-1}{role_param}"))

    nav_row.append(InlineKeyboardButton(text=f"📄 {page+1} / {max(total_pages, 1)}", callback_data="noop"))

    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"workers_page_{page+1}{role_param}"))

    if total_pages > 1 or len(nav_row) > 1:
        inline_kb.append(nav_row)

    # Filtr va Qidiruv qatori
    inline_kb.append([
        InlineKeyboardButton(text="🎭 Rollar bo'yicha filter", callback_data="workers_filter_role"),
        InlineKeyboardButton(text="🔍 Qidirish", callback_data="workers_search"),
    ])
    inline_kb.append([
        InlineKeyboardButton(text="⬅️ Bosh menyu", callback_data="admin:home")
    ])

    return InlineKeyboardMarkup(inline_keyboard=inline_kb)


def get_worker_details_keyboard(worker_id: int) -> InlineKeyboardMarkup:
    """Xodim kartasi ichidagi amallar tugmalari."""
    inline_kb = [
        [
            InlineKeyboardButton(text="💵 Avans Berish", callback_data=f"fin_advance_{worker_id}"),
            InlineKeyboardButton(text="💳 Raschyot Qilish", callback_data=f"fin_settle_{worker_id}"),
        ],
        [
            InlineKeyboardButton(text="🕒 Davomat Tarixi", callback_data=f"worker_att_history_{worker_id}"),
            InlineKeyboardButton(text="📋 To'lovlar Tarixi", callback_data=f"worker_pay_history_{worker_id}"),
        ],
        [
            InlineKeyboardButton(text="⏱ Davomatni Qo'lda Kiritish", callback_data=f"worker_manual_att_{worker_id}"),
        ],
        [
            InlineKeyboardButton(text="🎭 Lavozimni O'zgartirish", callback_data=f"worker_edit_role_{worker_id}"),
            InlineKeyboardButton(text="✏️ Maoshni O'zgartirish", callback_data=f"worker_edit_salary_{worker_id}"),
        ],
        [
            InlineKeyboardButton(text="🕒 Ish jadvalini O'zgartirish", callback_data=f"worker_edit_schedule_{worker_id}"),
            InlineKeyboardButton(text="🗑 Xodimni O'chirish", callback_data=f"worker_delete_{worker_id}"),
        ],
        [
            InlineKeyboardButton(text="⬅️ Xodimlar Ro'yxatiga", callback_data="workers_back_to_list"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=inline_kb)


def get_salary_type_keyboard(worker_id: int) -> InlineKeyboardMarkup:
    """Maosh turini tanlash klaviaturasi (Oylik yoki Kunlik)."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📅 Oylik maosh (oyiga)", callback_data=f"sal_type_{worker_id}_monthly"),
            InlineKeyboardButton(text="☀️ Kunlik stavka (kuniga)", callback_data=f"sal_type_{worker_id}_daily"),
        ],
        [
            InlineKeyboardButton(text="⬅️ Ortga", callback_data=f"worker_view_{worker_id}"),
        ]
    ])


def get_manual_attendance_keyboard(worker_id: int) -> InlineKeyboardMarkup:
    """Davomatni qo'lda kiritish varianti klaviaturasi."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🟢 To'liq smena (09:00 - 21:00)", callback_data=f"man_att_{worker_id}_full"),
        ],
        [
            InlineKeyboardButton(text="🟢 Hozir ishda (Keldi deb belgilash)", callback_data=f"man_att_{worker_id}_in"),
        ],
        [
            InlineKeyboardButton(text="🌙 Dam olish kuni", callback_data=f"man_att_{worker_id}_rest"),
        ],
        [
            InlineKeyboardButton(text="✍️ O'z vaqtini kiritish", callback_data=f"man_att_{worker_id}_custom"),
        ],
        [
            InlineKeyboardButton(text="⬅️ Ortga", callback_data=f"worker_view_{worker_id}"),
        ]
    ])


def get_tx_void_keyboard(worker_id: int, tx_id: int) -> InlineKeyboardMarkup:
    """Tranzaksiyani bekor qilishni tasdiqlash klaviaturasi."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🗑 Ha, bekor qilinsin", callback_data=f"confirm_void_tx_{worker_id}_{tx_id}"),
            InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"worker_pay_history_{worker_id}"),
        ]
    ])


def get_back_keyboard(callback_data: str) -> InlineKeyboardMarkup:
    """Yagona 'Ortga' tugmasini yaratish."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Ortga", callback_data=callback_data)]
    ])


# ==========================================
# 💰 MOLIYA TASDIQLASH VA AMALLAR
# ==========================================

def get_advance_confirm_keyboard(worker_id: int, amount: float) -> InlineKeyboardMarkup:
    """Avans berishni tasdiqlash klaviaturasi."""
    inline_kb = [
        [
            InlineKeyboardButton(text="✅ Tasdiqlash va To'lash", callback_data=f"confirm_adv_{worker_id}_{int(amount)}"),
            InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"worker_view_{worker_id}"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=inline_kb)


def get_settlement_confirm_keyboard(worker_id: int, amount: float) -> InlineKeyboardMarkup:
    """Raschyot to'lovini tasdiqlash klaviaturasi."""
    inline_kb = [
        [
            InlineKeyboardButton(text="✅ Raschyotni Tasdiqlash", callback_data=f"confirm_settle_{worker_id}_{int(amount)}"),
            InlineKeyboardButton(text="✏️ Boshqa summa", callback_data=f"custom_settle_{worker_id}"),
        ],
        [
            InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"worker_view_{worker_id}"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=inline_kb)


# ==========================================
# 📝 ARIZALAR VA ADMIN SOZLAMALARI
# ==========================================

def get_job_application_keyboard(app_id: int) -> InlineKeyboardMarkup:
    """Ishga kirish arizasini ko'rib chiqish."""
    inline_kb = [
        [
            InlineKeyboardButton(text="✅ Ishga Qabul Qilish", callback_data=f"app_accept_{app_id}"),
            InlineKeyboardButton(text="❌ Rad Etish", callback_data=f"app_reject_{app_id}"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=inline_kb)


def get_settings_keyboard() -> InlineKeyboardMarkup:
    """Sozlamalar menyusi."""
    inline_kb = [
        [
            InlineKeyboardButton(text="📍 Korxona Lokatsiyasini Yangilash", callback_data="set_location_prompt"),
        ],
        [
            InlineKeyboardButton(text="📐 Ruxsat Etilgan Radiusni O'zgartirish", callback_data="set_radius_menu"),
        ],
        [
            InlineKeyboardButton(text="👥 Adminlar Boshqaruvi", callback_data="set_admins_menu"),
        ],
        [
            InlineKeyboardButton(text="📢 Log Guruhini Sozlash", callback_data="set_group_menu"),
        ],
        [
            InlineKeyboardButton(text="📞 Admin Aloqa Kontaktini O'rnatish", callback_data="set_contact_menu"),
        ],
        [
            InlineKeyboardButton(text="⬅️ Bosh menyu", callback_data="admin:home"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=inline_kb)


def get_radius_selection_keyboard() -> InlineKeyboardMarkup:
    """Radius variantlari."""
    inline_kb = [
        [
            InlineKeyboardButton(text="50 metr", callback_data="radius_set_50"),
            InlineKeyboardButton(text="100 metr", callback_data="radius_set_100"),
        ],
        [
            InlineKeyboardButton(text="150 metr", callback_data="radius_set_150"),
            InlineKeyboardButton(text="200 metr", callback_data="radius_set_200"),
        ],
        [
            InlineKeyboardButton(text="300 metr", callback_data="radius_set_300"),
            InlineKeyboardButton(text="500 metr", callback_data="radius_set_500"),
        ],
        [
            InlineKeyboardButton(text="⬅️ Sozlamalarga Qaytish", callback_data="settings_back"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=inline_kb)
