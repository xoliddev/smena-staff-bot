import datetime
import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

import database as db
from config import TIMEZONE, format_hours_mins
from keyboards.inline_keyboards import get_back_keyboard
from utils.ui import edit_menu, safe_html
from utils.middlewares import AdminOnlyCallbackMiddleware

logger = logging.getLogger(__name__)
router = Router(name="admin_attendance_router")
router.callback_query.middleware(AdminOnlyCallbackMiddleware())


@router.callback_query(F.data == "admin:attendance")
async def cb_today_attendance(callback: CallbackQuery, state: FSMContext):
    """Bugungi kunlik davomat xulosasini ko'rsatish."""
    await state.clear()
    if not await db.is_admin_or_superadmin(callback.from_user.id):
        return

    now = datetime.datetime.now(TIMEZONE)
    today = now.date()

    summary = await db.get_today_attendance_summary(today)

    total = summary["total"]
    present = summary["present"]
    rest = summary["rest"]
    absent = summary["absent"]

    text = (
        f"⏱ <b>BUGUNGI DAVOMAT — {today.strftime('%d.%m.%Y')}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 <b>Jami xodimlar:</b> {total} nafar\n"
        f"🟢 <b>Ishga kelganlar:</b> {len(present)} nafar\n"
        f"🌙 <b>Damdagilar:</b> {len(rest)} nafar\n"
        f"❌ <b>Hali kelmaganlar:</b> {len(absent)} nafar\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    # 1. Ishga kelganlar ro'yxati
    if present:
        text += "🟢 <b>ISHGA KELGANLAR:</b>\n"
        for p in present:
            arr_str = p["arrival_time"].astimezone(TIMEZONE).strftime("%H:%M")
            w_name = safe_html(p["full_name"])
            r_name = safe_html(p.get("role_name") or "Xodim")
            if p.get("departure_time"):
                dep_str = p["departure_time"].astimezone(TIMEZONE).strftime("%H:%M")
                hrs = format_hours_mins(p.get("total_hours"))
                text += f"• <b>{w_name}</b> (<i>{r_name}</i>)\n  ⏰ {arr_str} ➔ 🔴 {dep_str} ({hrs})\n"
            else:
                text += f"• <b>{w_name}</b> (<i>{r_name}</i>)\n  ⏰ Keldi: {arr_str} (🟢 Hozir ishda)\n"
        text += "\n"

    # 2. Damdagilar
    if rest:
        text += "🌙 <b>DAM OLISH KUNIDAGILAR:</b>\n"
        for r in rest:
            w_name = safe_html(r["full_name"])
            r_name = safe_html(r.get("role_name") or "Xodim")
            text += f"• {w_name} (<i>{r_name}</i>)\n"
        text += "\n"

    # 3. Kelmaganlar
    if absent:
        text += "❌ <b>HALI KELMAGANLAR:</b>\n"
        for a in absent:
            w_name = safe_html(a["full_name"])
            r_name = safe_html(a.get("role_name") or "Xodim")
            text += f"• {w_name} (<i>{r_name}</i>)\n"
        text += "\n"

    text += "━━━━━━━━━━━━━━━━━━━━"
    await edit_menu(callback.message, text, get_back_keyboard("admin:home"))
    await callback.answer()
