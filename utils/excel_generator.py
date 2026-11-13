import datetime
from io import BytesIO
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

import database as db
from config import MONTH_NAMES, RESTAURANT_NAME


async def generate_monthly_report_excel(year: int, month: int) -> BytesIO:
    """
    Oylik to'liq hisobotni chiroyli va rasmiy Excel fayl ko'rinishida generatsiya qiladi.
    1-list: Xodimlarning oylik hisob-kitob varag'i (oylik, ishlagan kuni, hisoblangan haq, avanslar, raschyot).
    2-list: Kunlik davomat jadvali (tabel).
    """
    wb = openpyxl.Workbook()

    # 1-LIST: MOLIYA VA HISOB-KITOB
    ws_finance = wb.active
    month_str = MONTH_NAMES.get(month, f"{month}-oy")
    ws_finance.title = f"Ish haqi - {month_str}"

    # Ranglar va stillar
    header_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
    header_font = Font(name="Arial", size=11, bold=True, color="FFFFFF")
    title_font = Font(name="Arial", size=14, bold=True, color="1F4E78")
    bold_font = Font(name="Arial", size=10, bold=True)
    regular_font = Font(name="Arial", size=10)

    thin_border = Border(
        left=Side(style='thin', color='D9D9D9'),
        right=Side(style='thin', color='D9D9D9'),
        top=Side(style='thin', color='D9D9D9'),
        bottom=Side(style='thin', color='D9D9D9')
    )

    # Sarlavha (10 ta ustun)
    ws_finance.merge_cells("A1:J1")
    ws_finance["A1"] = f"{RESTAURANT_NAME.upper()} — {month_str} {year} OYLIK MOLIYA VA ISH HAQI HISOBOTI"
    ws_finance["A1"].font = title_font
    ws_finance["A1"].alignment = Alignment(horizontal="center", vertical="center")
    ws_finance.row_dimensions[1].height = 30

    headers_finance = [
        "№", "F.I.O", "Lavozimi / Roli", "Stavka Turi", "Belgilangan Stavka",
        "Ishlagan Kuni", "Jami Soat", "Hisoblangan Haq", "Berilgan Avanslar", "Qoldiq (Raschyot)"
    ]

    for col_num, h_text in enumerate(headers_finance, 1):
        cell = ws_finance.cell(row=3, column=col_num, value=h_text)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = thin_border
    ws_finance.row_dimensions[3].height = 25

    # Shu oyda ishlagan yoki faol bo'lgan barcha xodimlarni olamiz
    workers = await db.get_report_workers_for_month(year, month)
    row_idx = 4
    total_salaries = 0.0
    total_advances = 0.0
    total_balance = 0.0

    for i, w in enumerate(workers, 1):
        stats = await db.get_worker_month_stats(w["id"], year, month)
        m_salary = float(w.get("monthly_salary") or 0.0)
        sal_type = stats.get("salary_type") or w.get("salary_type") or "monthly"
        type_str = "Kunlik" if sal_type == "daily" else "Oylik"

        days = stats["days_worked"]
        hours = stats["total_hours"]
        earned = stats["earned_salary"]
        adv = stats["advances_sum"]
        bal = stats["balance"]

        total_salaries += earned
        total_advances += adv
        total_balance += bal

        ws_finance.cell(row=row_idx, column=1, value=i).alignment = Alignment(horizontal="center")
        ws_finance.cell(row=row_idx, column=2, value=w["full_name"])
        ws_finance.cell(row=row_idx, column=3, value=w.get("role_name") or "Xodim").alignment = Alignment(horizontal="center")
        ws_finance.cell(row=row_idx, column=4, value=type_str).alignment = Alignment(horizontal="center")
        ws_finance.cell(row=row_idx, column=5, value=m_salary).number_format = '#,##0 "so\'m"'
        ws_finance.cell(row=row_idx, column=6, value=days).alignment = Alignment(horizontal="center")
        ws_finance.cell(row=row_idx, column=7, value=round(hours, 1)).alignment = Alignment(horizontal="center")
        ws_finance.cell(row=row_idx, column=8, value=earned).number_format = '#,##0 "so\'m"'
        ws_finance.cell(row=row_idx, column=9, value=adv).number_format = '#,##0 "so\'m"'
        ws_finance.cell(row=row_idx, column=10, value=bal).number_format = '#,##0 "so\'m"'

        for c in range(1, 11):
            cell = ws_finance.cell(row=row_idx, column=c)
            cell.border = thin_border
            cell.font = regular_font

        row_idx += 1

    # Jami qatori
    ws_finance.cell(row=row_idx, column=1, value="")
    ws_finance.cell(row=row_idx, column=2, value="JAMI:").font = bold_font
    ws_finance.cell(row=row_idx, column=8, value=total_salaries).font = bold_font
    ws_finance.cell(row=row_idx, column=8).number_format = '#,##0 "so\'m"'
    ws_finance.cell(row=row_idx, column=9, value=total_advances).font = bold_font
    ws_finance.cell(row=row_idx, column=9).number_format = '#,##0 "so\'m"'
    ws_finance.cell(row=row_idx, column=10, value=total_balance).font = bold_font
    ws_finance.cell(row=row_idx, column=10).number_format = '#,##0 "so\'m"'

    for c in range(1, 11):
        ws_finance.cell(row=row_idx, column=c).border = thin_border

    # Ustun kengliklari
    for col in ws_finance.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws_finance.column_dimensions[col_letter].width = max(max_len + 4, 12)

    # 2-LIST: KUNLIK DAVOMAT TABELI
    ws_attendance = wb.create_sheet(f"Davomat - {month_str}")
    attendance_headers = [
        "Sana", "F.I.O", "Lavozimi / Roli", "Holat",
        "Kelgan vaqti", "Ketgan vaqti", "Jami soat", "Masofa (m)",
    ]
    for col_num, header in enumerate(attendance_headers, 1):
        cell = ws_attendance.cell(row=1, column=col_num, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = thin_border
    ws_attendance.freeze_panes = "A2"

    month_start = datetime.date(year, month, 1)
    month_end = datetime.date(year + (1 if month == 12 else 0), 1 if month == 12 else month + 1, 1)
    async with db.pool.acquire() as conn:
        attendance_rows = await conn.fetch(
            """
            SELECT s.date, w.full_name, COALESCE(r.name, 'Xodim') AS role_name,
                   s.is_rest_day, s.arrival_time, s.departure_time,
                   s.total_hours, s.arrival_distance
            FROM work_sessions s
            JOIN workers w ON w.id = s.worker_id
            LEFT JOIN roles r ON r.id = w.role_id
            WHERE s.date >= $1 AND s.date < $2
            ORDER BY s.date ASC, w.full_name ASC
            """,
            month_start,
            month_end,
        )

    for a_idx, row in enumerate(attendance_rows, 2):
        if row["is_rest_day"]:
            status = "Dam olish"
        elif row["arrival_time"]:
            status = "Ishladi" if row["departure_time"] else "Ochiq smena"
        else:
            status = "Kelmagan"
        values = [
            row["date"], row["full_name"], row["role_name"], status,
            row["arrival_time"].astimezone(db.TIMEZONE).strftime("%H:%M") if row["arrival_time"] else "—",
            row["departure_time"].astimezone(db.TIMEZONE).strftime("%H:%M") if row["departure_time"] else "—",
            float(row["total_hours"] or 0), float(row["arrival_distance"] or 0),
        ]
        for col_num, value in enumerate(values, 1):
            cell = ws_attendance.cell(row=a_idx, column=col_num, value=value)
            cell.border = thin_border
            cell.font = regular_font

    for col in ws_attendance.columns:
        max_len = max(len(str(cell.value or "")) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws_attendance.column_dimensions[col_letter].width = max(max_len + 4, 12)

    # Faylni xotiraga yozamiz
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return output
