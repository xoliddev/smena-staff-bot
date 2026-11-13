from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def get_admin_main_menu() -> ReplyKeyboardMarkup:
    """Admin bosh menyu tugmalari"""
    kb = [
        [KeyboardButton(text="👥 Xodimlar"), KeyboardButton(text="💰 Moliya (Avans/Raschyot)")],
        [KeyboardButton(text="⏰ Bugungi Davomat"), KeyboardButton(text="📊 Hisobotlar (Excel)")],
        [KeyboardButton(text="🎭 Rollar Boshqaruvi"), KeyboardButton(text="⚙️ Sozlamalar")],
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def get_worker_main_menu() -> ReplyKeyboardMarkup:
    """Xodim bosh menyu tugmalari"""
    kb = [
        [KeyboardButton(text="🟢 Ishga keldim"), KeyboardButton(text="🔴 Ishdan ketdim")],
        [KeyboardButton(text="🌙 Dam oldim"), KeyboardButton(text="📊 Mening hisobotim")],
        [KeyboardButton(text="👤 Profilim"), KeyboardButton(text="📞 Bog'lanish")],
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def get_location_request_keyboard() -> ReplyKeyboardMarkup:
    """Joylashuvni yuborish tugmasi"""
    kb = [
        [KeyboardButton(text="📍 Hozirgi joylashuvimni yuborish", request_location=True)],
        [KeyboardButton(text="⬅️ Bekor qilish")],
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True, one_time_keyboard=True)


def get_phone_request_keyboard() -> ReplyKeyboardMarkup:
    """Telefon raqamni yuborish tugmasi"""
    kb = [
        [KeyboardButton(text="📱 Telefon raqamni yuborish", request_contact=True)],
        [KeyboardButton(text="⬅️ Bekor qilish")],
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True, one_time_keyboard=True)


def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    """Bekor qilish tugmasi"""
    kb = [
        [KeyboardButton(text="⬅️ Bekor qilish")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
