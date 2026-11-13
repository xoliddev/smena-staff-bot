import os
import re
import urllib.parse
from typing import List
from dotenv import load_dotenv
import pytz

# .env faylini yuklaymiz
load_dotenv()

# Bot sozlamalari
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

# Restoran (korxona) nomi — white-label: bot matnlari, Excel fayl nomlari va loglarda ishlatiladi
DEFAULT_RESTAURANT_NAME = "Smena"


def _parse_restaurant_name(raw_value: str | None) -> str:
    """RESTAURANT_NAME qiymatini tozalaydi; bo'sh bo'lsa standart nomni qaytaradi."""
    name = " ".join(str(raw_value or "").split())
    return name or DEFAULT_RESTAURANT_NAME


def make_file_slug(name: str) -> str:
    """Nomni fayl nomi uchun xavfsiz ko'rinishga keltiradi (masalan: 'Mening Oshxonam' -> 'Mening_Oshxonam')."""
    slug = re.sub(r"[\\/:*?\"<>|'`]+", "", str(name or ""))
    slug = re.sub(r"\s+", "_", slug.strip())
    slug = re.sub(r"_+", "_", slug).strip("._")
    return slug or DEFAULT_RESTAURANT_NAME


RESTAURANT_NAME: str = _parse_restaurant_name(os.getenv("RESTAURANT_NAME"))
RESTAURANT_SLUG: str = make_file_slug(RESTAURANT_NAME)


def monthly_report_filename(month_name: str, year: int, restaurant_name: str | None = None) -> str:
    """Oylik Excel hisobot fayli nomi, masalan: 'Smena_Mart_2026_Hisoboti.xlsx'."""
    slug = make_file_slug(restaurant_name) if restaurant_name else RESTAURANT_SLUG
    return f"{slug}_{make_file_slug(month_name)}_{year}_Hisoboti.xlsx"

# Superadminlar ro'yxati
def _parse_id_list(raw_value: str) -> List[int]:
    if not raw_value:
        return []
    result = []
    for item in str(raw_value).split(","):
        item = item.strip()
        if item.isdigit():
            result.append(int(item))
    return result

SUPERADMINS: List[int] = _parse_id_list(os.getenv("SUPERADMINS", ""))

# Ma'lumotlar bazasi (PostgreSQL)
DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL:
    parsed_db = urllib.parse.urlparse(DATABASE_URL)
    POSTGRES_USER = parsed_db.username or "postgres"
    POSTGRES_PASSWORD = parsed_db.password or ""
    POSTGRES_HOST = parsed_db.hostname or "localhost"
    POSTGRES_PORT = parsed_db.port or 5432
    POSTGRES_DB = (parsed_db.path[1:] if parsed_db.path else "smena_db")
else:
    POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")
    POSTGRES_DB = os.getenv("POSTGRES_DB", "smena_db")
    POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", 5432))

# Korxona boshlang'ich lokatsiyasi va radiusi
DEFAULT_LAT = float(os.getenv("DEFAULT_LAT", 41.311081))
DEFAULT_LON = float(os.getenv("DEFAULT_LON", 69.240562))
DEFAULT_RADIUS = float(os.getenv("DEFAULT_RADIUS", 150)) # metr

# Log guruhi ID
WORK_LOG_GROUP_ID = int(os.getenv("WORK_LOG_GROUP_ID", "0") or 0)

# Vaqt mintaqasi - Toshkent
TIMEZONE = pytz.timezone("Asia/Tashkent")

# Oy nomlari (o'zbek tilida)
MONTH_NAMES = {
    1: "Yanvar",
    2: "Fevral",
    3: "Mart",
    4: "Aprel",
    5: "May",
    6: "Iyun",
    7: "Iyul",
    8: "Avgust",
    9: "Sentyabr",
    10: "Oktyabr",
    11: "Noyabr",
    12: "Dekabr"
}

# Formatlash yordamchilari
def format_currency(amount: float | int | None) -> str:
    """Raqamni chiroyli so'm formatiga o'tkazadi (masalan: 1,500,000 so'm)"""
    if amount is None:
        return "0 so'm"
    try:
        val = float(amount)
        if val.is_integer():
            return f"{int(val):,} so'm".replace(",", " ")
        return f"{val:,.2f} so'm".replace(",", " ")
    except Exception:
        return f"{amount} so'm"

def format_hours_mins(total_hours: float | None) -> str:
    """Soatni 'X soat Y daqiqa' formatiga o'tkazadi"""
    if not total_hours:
        return "0 soat"
    total_minutes = int(round(float(total_hours) * 60))
    hours = total_minutes // 60
    mins = total_minutes % 60
    if hours > 0 and mins > 0:
        return f"{hours} soat {mins} daq"
    elif hours > 0:
        return f"{hours} soat"
    else:
        return f"{mins} daqiqa"
