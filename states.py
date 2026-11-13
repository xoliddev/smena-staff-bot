from aiogram.fsm.state import State, StatesGroup


class WorkerApplicationStates(StatesGroup):
    """Ishga kirish arizasi holatlari"""
    waiting_for_name = State()
    waiting_for_phone = State()
    waiting_for_role = State()


class WorkerAttendanceStates(StatesGroup):
    """Davomat (keldi-ketdi) holatlari"""
    waiting_for_arrival_location = State()
    waiting_for_departure_location = State()


class RoleStates(StatesGroup):
    """Rollar boshqaruvi holatlari"""
    waiting_for_role_name = State()
    waiting_for_role_desc = State()
    waiting_for_edit_role_name = State()
    waiting_for_edit_role_desc = State()


class WorkerManagementStates(StatesGroup):
    """Xodimlarni tahrirlash va qidirish holatlari"""
    waiting_for_search_query = State()
    waiting_for_salary_type = State()
    waiting_for_salary_input = State()
    waiting_for_hours_input = State()
    waiting_for_name_edit = State()
    waiting_for_phone_edit = State()
    waiting_for_work_schedule_start = State()
    waiting_for_work_schedule_end = State()


class ManualAttendanceStates(StatesGroup):
    """Admin tomonidan davomatni qo'lda kiritish holatlari"""
    waiting_for_custom_date = State()
    waiting_for_custom_times = State()


class FinanceStates(StatesGroup):
    """Moliya (Avans va Raschyot) holatlari"""
    waiting_for_advance_amount = State()
    waiting_for_advance_comment = State()
    waiting_for_advance_confirm = State()
    waiting_for_settlement_confirm = State()
    waiting_for_settlement_custom_amount = State()
    waiting_for_settlement_comment = State()


class SettingsStates(StatesGroup):
    """Sozlamalar holatlari"""
    waiting_for_location = State()
    waiting_for_radius = State()
    waiting_for_new_admin_id = State()
    waiting_for_new_admin_name = State()
    waiting_for_admin_contact = State()
    waiting_for_log_group = State()
