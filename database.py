import asyncpg
import datetime
from datetime import date, time
from typing import Optional, List, Dict, Any, Tuple
import logging
from config import (
    POSTGRES_USER,
    POSTGRES_PASSWORD,
    POSTGRES_HOST,
    POSTGRES_PORT,
    POSTGRES_DB,
    DATABASE_URL,
    DEFAULT_LAT,
    DEFAULT_LON,
    DEFAULT_RADIUS,
    RESTAURANT_NAME,
    SUPERADMINS,
    TIMEZONE,
)

logger = logging.getLogger(__name__)

# Connection pool
pool: Optional[asyncpg.Pool] = None


async def create_pool() -> asyncpg.Pool:
    global pool
    if pool is None:
        try:
            if DATABASE_URL:
                pool = await asyncpg.create_pool(
                    DATABASE_URL,
                    min_size=1,
                    max_size=10,
                    max_inactive_connection_lifetime=300,
                    timeout=15,
                    command_timeout=60,
                )
            else:
                pool = await asyncpg.create_pool(
                    user=POSTGRES_USER,
                    password=POSTGRES_PASSWORD,
                    host=POSTGRES_HOST,
                    port=POSTGRES_PORT,
                    database=POSTGRES_DB,
                    min_size=1,
                    max_size=10,
                    max_inactive_connection_lifetime=300,
                    timeout=15,
                    command_timeout=60,
                )
            logger.info("✅ PostgreSQL connection pool muvaffaqiyatli yaratildi.")
        except Exception as e:
            logger.error(f"❌ PostgreSQL connection pool yaratishda xatolik: {e}")
            raise e
    return pool


async def close_pool() -> None:
    """PostgreSQL pool'ini yopadi."""
    global pool
    if pool:
        await pool.close()
        pool = None
        logger.info("PostgreSQL pool yopildi.")


async def init_db():
    """Barcha jadvallarni va boshlang'ich ma'lumotlarni yaratadi."""
    async with pool.acquire() as conn:
        # 1. Rollar jadvali (Dinamik Rollar)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS roles (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) UNIQUE NOT NULL,
                description TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Standart rollarni kiritamiz (agar mavjud bo'lmasa)
        default_roles = [
            ("👨‍🍳 Oshpaz", "Taomlar tayyorlovchi usta oshpaz"),
            ("🍽 Ofitsiant", "Mijozlarga xizmat ko'rsatuvchi xodim"),
            ("💰 Kassir", "Hisob-kitob va to'lovlar bilan ishlovchi xodim"),
            ("🔪 Zagatovkachi", "Go'sht va masalliqlarni tayyorlovchi"),
            ("🧼 Idish yuvuvchi", "Oshxona tozaligi va idishlar nazoratchisi"),
            ("👔 Menejer", "Zal va ish jarayoni boshqaruvchisi"),
            ("🔥 Mangalchi", "Mangal va gril taomlarini pishiruvchi usta"),
        ]
        for role_name, role_desc in default_roles:
            await conn.execute("""
                INSERT INTO roles (name, description)
                VALUES ($1, $2)
                ON CONFLICT (name) DO NOTHING;
            """, role_name, role_desc)

        # 2. Xodimlar jadvali
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS workers (
                id SERIAL PRIMARY KEY,
                tg_id BIGINT UNIQUE NOT NULL,
                full_name VARCHAR(255) NOT NULL,
                phone_number VARCHAR(50),
                username VARCHAR(255),
                role_id INTEGER REFERENCES roles(id) ON DELETE SET NULL,
                monthly_salary NUMERIC(14, 2) DEFAULT 0.00,
                salary_type VARCHAR(20) DEFAULT 'monthly',
                hourly_rate NUMERIC(14, 2) DEFAULT 0.00,
                daily_work_hours NUMERIC(4, 2) DEFAULT 8.00,
                work_start TIME DEFAULT '08:00:00',
                work_end TIME DEFAULT '20:00:00',
                is_active BOOLEAN DEFAULT TRUE,
                added_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Agar mavjud bazada salary_type bo'lmasa, qo'shib qo'yamiz
        await conn.execute("""
            ALTER TABLE workers ADD COLUMN IF NOT EXISTS salary_type VARCHAR(20) DEFAULT 'monthly';
        """)

        # 3. Ish sessiyalari va Davomat jadvali
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS work_sessions (
                id SERIAL PRIMARY KEY,
                worker_id INTEGER REFERENCES workers(id) ON DELETE CASCADE,
                date DATE NOT NULL,
                arrival_time TIMESTAMP WITH TIME ZONE,
                departure_time TIMESTAMP WITH TIME ZONE,
                total_hours NUMERIC(5, 2) DEFAULT 0.00,
                is_rest_day BOOLEAN DEFAULT FALSE,
                arrival_lat DOUBLE PRECISION,
                arrival_lon DOUBLE PRECISION,
                arrival_distance DOUBLE PRECISION,
                departure_lat DOUBLE PRECISION,
                departure_lon DOUBLE PRECISION,
                notes TEXT,
                UNIQUE(worker_id, date)
            );
        """)

        # 4. Moliya Tranzaksiyalari (Avans va Raschyotlar)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS finance_transactions (
                id SERIAL PRIMARY KEY,
                worker_id INTEGER REFERENCES workers(id) ON DELETE CASCADE,
                admin_tg_id BIGINT NOT NULL,
                admin_name VARCHAR(255),
                transaction_type VARCHAR(30) NOT NULL, -- 'advance', 'settlement', 'bonus', 'penalty'
                amount NUMERIC(14, 2) NOT NULL,
                period_start DATE,
                period_end DATE,
                worked_hours NUMERIC(6, 2),
                total_salary_calculated NUMERIC(14, 2),
                advances_deducted NUMERIC(14, 2),
                comment TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 5. Ishga kirish arizalari
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS job_applications (
                id SERIAL PRIMARY KEY,
                tg_id BIGINT UNIQUE NOT NULL,
                full_name VARCHAR(255) NOT NULL,
                phone_number VARCHAR(50),
                username VARCHAR(255),
                selected_role_id INTEGER REFERENCES roles(id) ON DELETE SET NULL,
                status VARCHAR(50) DEFAULT 'pending', -- 'pending', 'accepted', 'rejected'
                notification_message_id INTEGER,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 6. Adminlar jadvali
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS admins (\n                tg_id BIGINT PRIMARY KEY,
                full_name VARCHAR(255) NOT NULL,
                username VARCHAR(255),
                role VARCHAR(50) DEFAULT 'admin', -- 'superadmin', 'admin'
                added_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Superadminlarni bazaga kiritish
        for s_id in SUPERADMINS:
            await conn.execute("""
                INSERT INTO admins (tg_id, full_name, role)
                VALUES ($1, 'Bosh Administrator', 'superadmin')
                ON CONFLICT (tg_id) DO UPDATE SET role = 'superadmin';
            """, s_id)

        # 7. Tizim sozlamalari
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                location_lat DOUBLE PRECISION DEFAULT 41.311081,
                location_lon DOUBLE PRECISION DEFAULT 69.240562,
                location_radius DOUBLE PRECISION DEFAULT 150,
                location_name VARCHAR(255),
                work_log_group_id BIGINT DEFAULT 0,
                admin_contact VARCHAR(255),
                company_name VARCHAR(255)
            );
        """)

        # Settings jadvalida 1-qator bo'lishini ta'minlaymiz
        await conn.execute("""
            INSERT INTO settings (id, location_lat, location_lon, location_radius, location_name, company_name)
            VALUES (1, $1, $2, $3, $4, $4)
            ON CONFLICT (id) DO NOTHING;
        """, DEFAULT_LAT, DEFAULT_LON, DEFAULT_RADIUS, RESTAURANT_NAME)

    logger.info("🛠️ Barcha ma'lumotlar bazasi jadvallari muvaffaqiyatli tekshirildi.")


# ==========================================
# 🎭 ROLLAR BOSHQARUVI (ROLES CRUD)
# ==========================================

async def get_all_roles(only_active: bool = True) -> List[Dict[str, Any]]:
    """Barcha rollarni qaytaradi."""
    async with pool.acquire() as conn:
        query = "SELECT * FROM roles"
        if only_active:
            query += " WHERE is_active = TRUE"
        query += " ORDER BY id ASC"
        rows = await conn.fetch(query)
        return [dict(r) for r in rows]


async def get_role_by_id(role_id: int) -> Optional[Dict[str, Any]]:
    """ID bo'yicha rolni oladi."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM roles WHERE id = $1", role_id)
        return dict(row) if row else None


async def add_role(name: str, description: str = "") -> Optional[int]:
    """Yangi rol qo'shadi."""
    async with pool.acquire() as conn:
        try:
            return await conn.fetchval("""
                INSERT INTO roles (name, description, is_active)
                VALUES ($1, $2, TRUE)
                RETURNING id;
            """, name.strip(), description.strip())
        except asyncpg.UniqueViolationError:
            return None


async def update_role(role_id: int, name: str, description: str = "") -> bool:
    """Rol ma'lumotlarini yangilaydi."""
    async with pool.acquire() as conn:
        result = await conn.execute("""
            UPDATE roles
            SET name = $1, description = $2
            WHERE id = $3
        """, name.strip(), description.strip(), role_id)
        return "UPDATE 1" in result


async def delete_role(role_id: int) -> Tuple[bool, str]:
    """Rolni o'chiradi (agar xodimlar bo'lsa faol emas qiladi)."""
    async with pool.acquire() as conn:
        worker_count = await conn.fetchval(
            "SELECT COUNT(*) FROM workers WHERE role_id = $1 AND is_active = TRUE",
            role_id
        ) or 0
        if worker_count > 0:
            await conn.execute("UPDATE roles SET is_active = FALSE WHERE id = $1", role_id)
            return True, f"Ushbu rolda {worker_count} ta xodim bo'lgani uchun rol nofaol qilindi."
        else:
            await conn.execute("DELETE FROM roles WHERE id = $1", role_id)
            return True, "Rol muvaffaqiyatli o'chirildi."


async def get_roles_with_worker_counts() -> List[Dict[str, Any]]:
    """Har bir rolni unga tegishli xodimlar soni bilan qaytaradi."""
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT r.id, r.name, r.description, r.is_active,
                   COUNT(w.id) FILTER (WHERE w.is_active = TRUE) as workers_count
            FROM roles r
            LEFT JOIN workers w ON w.role_id = r.id
            GROUP BY r.id
            ORDER BY r.id ASC
        """)
        return [dict(r) for r in rows]


# ==========================================
# 👥 XODIMLAR BOSHQARUVI (WORKERS CRUD)
# ==========================================

async def get_worker_by_tg_id(tg_id: int) -> Optional[Dict[str, Any]]:
    """Telegram ID orqali xodimni qaytaradi."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT w.*, r.name as role_name
            FROM workers w
            LEFT JOIN roles r ON r.id = w.role_id
            WHERE w.tg_id = $1 AND w.is_active = TRUE
        """, tg_id)
        return dict(row) if row else None


async def get_worker_by_id(worker_id: int) -> Optional[Dict[str, Any]]:
    """Ichki ID orqali xodimni qaytaradi."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT w.*, r.name as role_name
            FROM workers w
            LEFT JOIN roles r ON r.id = w.role_id
            WHERE w.id = $1
        """, worker_id)
        return dict(row) if row else None


async def get_workers_paginated(
    page: int = 0,
    per_page: int = 8,
    role_id: Optional[int] = None,
    search_query: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Xodimlarni sahifalab (2x grid uchun) qaytaradi."""
    offset = page * per_page
    async with pool.acquire() as conn:
        params = []
        conditions = ["w.is_active = TRUE"]

        if role_id:
            params.append(role_id)
            conditions.append(f"w.role_id = ${len(params)}")

        if search_query:
            params.append(f"%{search_query.strip()}%")
            conditions.append(f"w.full_name ILIKE ${len(params)}")

        where_clause = " AND ".join(conditions)
        params.extend([per_page, offset])

        query = f"""
            SELECT w.*, r.name as role_name
            FROM workers w
            LEFT JOIN roles r ON r.id = w.role_id
            WHERE {where_clause}
            ORDER BY w.full_name ASC
            LIMIT ${len(params) - 1} OFFSET ${len(params)}
        """
        rows = await conn.fetch(query, *params)
        return [dict(r) for r in rows]


async def get_total_workers_count(
    role_id: Optional[int] = None,
    search_query: Optional[str] = None,
) -> int:
    """Xodimlar umumiy sonini qaytaradi."""
    async with pool.acquire() as conn:
        params = []
        conditions = ["is_active = TRUE"]

        if role_id:
            params.append(role_id)
            conditions.append(f"role_id = ${len(params)}")

        if search_query:
            params.append(f"%{search_query.strip()}%")
            conditions.append(f"full_name ILIKE ${len(params)}")

        where_clause = " AND ".join(conditions)
        query = f"SELECT COUNT(*) FROM workers WHERE {where_clause}"
        return await conn.fetchval(query, *params) or 0


async def add_worker(
    tg_id: int,
    full_name: str,
    phone_number: Optional[str] = None,
    username: Optional[str] = None,
    role_id: Optional[int] = None,
    monthly_salary: float = 0.0,
    daily_work_hours: float = 8.0,
    work_start: time = time(8, 0),
    work_end: time = time(20, 0),
    salary_type: str = "monthly",
) -> int:
    """Yangi xodim qo'shadi yoki mavjudini faollashtiradi."""
    async with pool.acquire() as conn:
        return await conn.fetchval("""
            INSERT INTO workers (
                tg_id, full_name, phone_number, username, role_id,
                monthly_salary, salary_type, daily_work_hours, work_start, work_end, is_active
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, TRUE)
            ON CONFLICT (tg_id) DO UPDATE SET
                full_name = EXCLUDED.full_name,
                phone_number = COALESCE(EXCLUDED.phone_number, workers.phone_number),
                username = EXCLUDED.username,
                role_id = COALESCE(EXCLUDED.role_id, workers.role_id),
                monthly_salary = EXCLUDED.monthly_salary,
                salary_type = EXCLUDED.salary_type,
                daily_work_hours = EXCLUDED.daily_work_hours,
                work_start = EXCLUDED.work_start,
                work_end = EXCLUDED.work_end,
                is_active = TRUE
            RETURNING id;
        """, tg_id, full_name, phone_number, username, role_id,
            monthly_salary, salary_type, daily_work_hours, work_start, work_end)


async def update_worker(worker_id: int, **kwargs) -> bool:
    """Xodim ma'lumotlarini qisman yangilash."""
    if not kwargs:
        return False
    async with pool.acquire() as conn:
        set_clauses = []
        values = []
        for i, (key, value) in enumerate(kwargs.items(), start=1):
            set_clauses.append(f"{key} = ${i}")
            values.append(value)
        values.append(worker_id)
        query = f"UPDATE workers SET {', '.join(set_clauses)} WHERE id = ${len(values)}"
        res = await conn.execute(query, *values)
        return "UPDATE 1" in res


async def delete_worker(worker_id: int) -> bool:
    """Xodimni nofaol qiladi (bazadan o'chirmay, tarixni saqlaydi)."""
    async with pool.acquire() as conn:
        res = await conn.execute("UPDATE workers SET is_active = FALSE WHERE id = $1", worker_id)
        return "UPDATE 1" in res


async def get_all_active_workers() -> List[Dict[str, Any]]:
    """Barcha faol xodimlarni oladi."""
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT w.*, r.name as role_name
            FROM workers w
            LEFT JOIN roles r ON r.id = w.role_id
            WHERE w.is_active = TRUE
            ORDER BY w.full_name ASC
        """)
        return [dict(r) for r in rows]


async def get_active_worker_tg_ids() -> List[int]:
    """Barcha faol xodimlarning Telegram ID'larini oladi."""
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT tg_id FROM workers WHERE is_active = TRUE")
        return [r["tg_id"] for r in rows]


async def get_report_workers_for_month(year: int, month: int) -> List[Dict[str, Any]]:
    """Shu oyda ishlagan, avans olgan yoki hozir faol bo'lgan barcha xodimlarni oladi."""
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT DISTINCT w.id, w.full_name, w.tg_id, w.phone_number, w.monthly_salary,
                            COALESCE(w.salary_type, 'monthly') as salary_type,
                            w.hourly_rate, w.daily_work_hours, w.is_active, r.name as role_name
            FROM workers w
            LEFT JOIN roles r ON r.id = w.role_id
            LEFT JOIN work_sessions s ON s.worker_id = w.id
                AND EXTRACT(YEAR FROM s.date) = $1
                AND EXTRACT(MONTH FROM s.date) = $2
            LEFT JOIN finance_transactions t ON t.worker_id = w.id
                AND EXTRACT(YEAR FROM t.created_at AT TIME ZONE 'Asia/Tashkent') = $1
                AND EXTRACT(MONTH FROM t.created_at AT TIME ZONE 'Asia/Tashkent') = $2
            WHERE w.is_active = TRUE OR s.id IS NOT NULL OR t.id IS NOT NULL
            ORDER BY w.full_name ASC
        """, year, month)
        return [dict(r) for r in rows]


# ==========================================
# 📝 ISHGA KIRISH ARIZALARI (JOB APPLICATIONS)
# ==========================================

async def create_or_update_application(
    tg_id: int,
    full_name: str,
    phone_number: Optional[str] = None,
    username: Optional[str] = None,
    selected_role_id: Optional[int] = None,
    notification_message_id: Optional[int] = None,
) -> int:
    """Yangi ariza yaratadi yoki yangilaydi."""
    async with pool.acquire() as conn:
        return await conn.fetchval("""
            INSERT INTO job_applications (
                tg_id, full_name, phone_number, username, selected_role_id,
                notification_message_id, status
            )
            VALUES ($1, $2, $3, $4, $5, $6, 'pending')
            ON CONFLICT (tg_id) DO UPDATE SET
                full_name = EXCLUDED.full_name,
                phone_number = COALESCE(EXCLUDED.phone_number, job_applications.phone_number),
                username = EXCLUDED.username,
                selected_role_id = EXCLUDED.selected_role_id,
                notification_message_id = COALESCE(EXCLUDED.notification_message_id, job_applications.notification_message_id),
                status = 'pending',
                created_at = CURRENT_TIMESTAMP
            RETURNING id;
        """, tg_id, full_name, phone_number, username, selected_role_id, notification_message_id)


async def has_recent_pending_application(tg_id: int, minutes: int = 10) -> bool:
    """Shu nomzodning yaqinda yuborilgan, hali ko'rib chiqilmagan arizasi bormi."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT 1 FROM job_applications WHERE tg_id = $1 AND status = 'pending' "
            "AND created_at > CURRENT_TIMESTAMP - make_interval(mins => $2)",
            tg_id, minutes,
        )
        return row is not None


async def get_application_by_id(app_id: int) -> Optional[Dict[str, Any]]:
    """ID orqali arizani oladi."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT a.*, r.name as role_name
            FROM job_applications a
            LEFT JOIN roles r ON r.id = a.selected_role_id
            WHERE a.id = $1
        """, app_id)
        return dict(row) if row else None


async def get_application_by_tg_id(tg_id: int) -> Optional[Dict[str, Any]]:
    """Telegram ID orqali arizani oladi."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT a.*, r.name as role_name
            FROM job_applications a
            LEFT JOIN roles r ON r.id = a.selected_role_id
            WHERE a.tg_id = $1
        """, tg_id)
        return dict(row) if row else None


async def get_pending_applications() -> List[Dict[str, Any]]:
    """Kutilayotgan barcha arizalarni oladi."""
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT a.*, r.name as role_name
            FROM job_applications a
            LEFT JOIN roles r ON r.id = a.selected_role_id
            WHERE a.status = 'pending'
            ORDER BY a.created_at DESC
        """)
        return [dict(r) for r in rows]


async def update_application_status(app_id: int, status: str) -> bool:
    """Ariza holatini yangilaydi (accepted, rejected)."""
    async with pool.acquire() as conn:
        res = await conn.execute("UPDATE job_applications SET status = $1 WHERE id = $2", status, app_id)
        return "UPDATE 1" in res


# ==========================================
# ⏰ DAVOMAT VA ISH SESSIYALARI
# ==========================================

async def get_worker_today_session(worker_id: int, target_date: date) -> Optional[Dict[str, Any]]:
    """Xodimning belgilangan kungi ish sessiyasini qaytaradi."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT * FROM work_sessions
            WHERE worker_id = $1 AND date = $2
        """, worker_id, target_date)
        return dict(row) if row else None


async def get_worker_open_session(worker_id: int) -> Optional[Dict[str, Any]]:
    """Xodimning oxirgi 24 soat ichida ochilgan va hali ketishi belgilanmagan sessiyasini qaytaradi (tungi smenalar uchun)."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT * FROM work_sessions
            WHERE worker_id = $1
              AND arrival_time IS NOT NULL
              AND departure_time IS NULL
              AND is_rest_day = FALSE
              AND arrival_time >= NOW() - INTERVAL '24 hours'
            ORDER BY arrival_time DESC
            LIMIT 1
        """, worker_id)
        return dict(row) if row else None


async def clock_in(
    worker_id: int,
    target_date: date,
    arrival_time: datetime.datetime,
    lat: float,
    lon: float,
    distance: float,
) -> Dict[str, Any]:
    """Ishga kelishni qayd etadi."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            INSERT INTO work_sessions (
                worker_id, date, arrival_time, arrival_lat, arrival_lon, arrival_distance, is_rest_day
            )
            VALUES ($1, $2, $3, $4, $5, $6, FALSE)
            ON CONFLICT (worker_id, date) DO UPDATE SET
                arrival_time = COALESCE(work_sessions.arrival_time, EXCLUDED.arrival_time),
                arrival_lat = EXCLUDED.arrival_lat,
                arrival_lon = EXCLUDED.arrival_lon,
                arrival_distance = EXCLUDED.arrival_distance,
                is_rest_day = FALSE
            RETURNING *;
        """, worker_id, target_date, arrival_time, lat, lon, distance)
        return dict(row)


async def clock_out(
    worker_id: int,
    target_date: date,
    departure_time: datetime.datetime,
    total_hours: float,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    """Ishdan ketishni qayd etadi va ishlangan soatni hisoblaydi."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            UPDATE work_sessions
            SET departure_time = $1,
                total_hours = $2,
                departure_lat = $3,
                departure_lon = $4
            WHERE worker_id = $5 AND date = $6
            RETURNING *;
        """, departure_time, total_hours, lat, lon, worker_id, target_date)
        return dict(row) if row else None


async def mark_rest_day(worker_id: int, target_date: date) -> Dict[str, Any]:
    """Bugungi kunni dam olish kuni deb belgilaydi."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            INSERT INTO work_sessions (worker_id, date, is_rest_day, total_hours)
            VALUES ($1, $2, TRUE, 0.00)
            ON CONFLICT (worker_id, date) DO UPDATE SET
                is_rest_day = TRUE,
                total_hours = 0.00
            RETURNING *;
        """, worker_id, target_date)
        return dict(row)


async def set_manual_attendance(
    worker_id: int,
    target_date: date,
    arrival_time: Optional[datetime.datetime] = None,
    departure_time: Optional[datetime.datetime] = None,
    is_rest_day: bool = False,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Admin tomonidan davomatni qo'lda kiritish yoki to'g'rilash."""
    total_hours = 0.00
    if is_rest_day:
        arrival_time = None
        departure_time = None
    elif arrival_time and departure_time:
        diff = departure_time - arrival_time
        total_hours = round(max(0.0, diff.total_seconds() / 3600.0), 2)
    elif arrival_time and not departure_time:
        total_hours = 0.00

    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            INSERT INTO work_sessions (worker_id, date, arrival_time, departure_time, total_hours, is_rest_day, notes)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (worker_id, date) DO UPDATE SET
                arrival_time = EXCLUDED.arrival_time,
                departure_time = EXCLUDED.departure_time,
                total_hours = EXCLUDED.total_hours,
                is_rest_day = EXCLUDED.is_rest_day,
                notes = EXCLUDED.notes
            RETURNING *;
        """, worker_id, target_date, arrival_time, departure_time, total_hours, is_rest_day, notes)
        return dict(row)


async def get_worker_attendance_history(worker_id: int, limit: int = 15) -> List[Dict[str, Any]]:
    """Xodimning oxirgi davomat yozuvlarini qaytaradi."""
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT * FROM work_sessions
            WHERE worker_id = $1
            ORDER BY date DESC, id DESC
            LIMIT $2
        """, worker_id, limit)
        return [dict(r) for r in rows]


async def get_today_attendance_summary(target_date: date) -> Dict[str, Any]:
    """Bugungi umumiy davomat xulosasini oladi."""
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT w.id, w.full_name, w.tg_id, r.name as role_name,
                   s.arrival_time, s.departure_time, s.total_hours, s.is_rest_day, s.arrival_distance
            FROM workers w
            LEFT JOIN roles r ON r.id = w.role_id
            LEFT JOIN work_sessions s ON s.worker_id = w.id AND s.date = $1
            WHERE w.is_active = TRUE
            ORDER BY w.full_name ASC
        """, target_date)

        total = len(rows)
        present = []
        rest = []
        absent = []

        for r in rows:
            r_dict = dict(r)
            if r_dict["is_rest_day"]:
                rest.append(r_dict)
            elif r_dict["arrival_time"]:
                present.append(r_dict)
            else:
                absent.append(r_dict)

        return {
            "total": total,
            "present": present,
            "rest": rest,
            "absent": absent,
        }


async def get_worker_month_stats(worker_id: int, year: int, month: int) -> Dict[str, Any]:
    """Xodimning oylik ish statistikasi (kunlar, soatlar, maosh)."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT
                COUNT(s.id) FILTER (WHERE s.arrival_time IS NOT NULL) as days_worked,
                COUNT(s.id) FILTER (WHERE s.is_rest_day = TRUE) as rest_days,
                COALESCE(SUM(s.total_hours), 0.00) as total_hours,
                w.monthly_salary,
                w.daily_work_hours,
                COALESCE(w.salary_type, 'monthly') as salary_type
            FROM workers w
            LEFT JOIN work_sessions s ON s.worker_id = w.id
                AND EXTRACT(YEAR FROM s.date) = $2
                AND EXTRACT(MONTH FROM s.date) = $3
            WHERE w.id = $1
            GROUP BY w.id, w.monthly_salary, w.daily_work_hours, w.salary_type
        """, worker_id, year, month)

        if not row:
            return {
                "days_worked": 0,
                "rest_days": 0,
                "total_hours": 0.0,
                "earned_salary": 0.0,
                "advances_sum": 0.0,
                "settlements_sum": 0.0,
                "balance": 0.0,
                "monthly_salary": 0.0,
                "salary_type": "monthly",
            }

        days_worked = row["days_worked"] or 0
        rest_days = row["rest_days"] or 0
        total_hours = float(row["total_hours"] or 0.0)
        salary_val = float(row["monthly_salary"] or 0.0)
        salary_type = row["salary_type"] or "monthly"

        if salary_type == "daily":
            daily_rate = salary_val
            earned_salary = daily_rate * days_worked
        else:
            # 1 oyda 26 ish kuni deb hisoblanadi (kunlik stavka = monthly_salary / 26)
            daily_rate = salary_val / 26 if salary_val > 0 else 0.0
            earned_salary = daily_rate * days_worked

        # Shu oyda olingan avanslar (Toshkent vaqti bo'yicha to'g'ri oyga tushishi uchun)
        advances_sum = await conn.fetchval("""
            SELECT COALESCE(SUM(amount), 0.00)
            FROM finance_transactions
            WHERE worker_id = $1
              AND transaction_type = 'advance'
              AND EXTRACT(YEAR FROM created_at AT TIME ZONE 'Asia/Tashkent') = $2
              AND EXTRACT(MONTH FROM created_at AT TIME ZONE 'Asia/Tashkent') = $3
        """, worker_id, year, month) or 0.0

        advances_sum = float(advances_sum)

        # Shu oyda to'langan raschyotlar
        settlements_sum = await conn.fetchval("""
            SELECT COALESCE(SUM(amount), 0.00)
            FROM finance_transactions
            WHERE worker_id = $1
              AND transaction_type = 'settlement'
              AND EXTRACT(YEAR FROM created_at AT TIME ZONE 'Asia/Tashkent') = $2
              AND EXTRACT(MONTH FROM created_at AT TIME ZONE 'Asia/Tashkent') = $3
        """, worker_id, year, month) or 0.0

        settlements_sum = float(settlements_sum)
        balance = earned_salary - advances_sum - settlements_sum

        return {
            "days_worked": days_worked,
            "rest_days": rest_days,
            "total_hours": total_hours,
            "earned_salary": earned_salary,
            "advances_sum": advances_sum,
            "settlements_sum": settlements_sum,
            "balance": balance,
            "monthly_salary": salary_val,
            "salary_type": salary_type,
        }


# ==========================================
# 💰 MOLIYA: AVANS VA RASCHYOT (FINANCE CRUD)
# ==========================================

async def add_finance_transaction(
    worker_id: int,
    admin_tg_id: int,
    admin_name: str,
    transaction_type: str, # 'advance', 'settlement', 'bonus', 'penalty'
    amount: float,
    comment: Optional[str] = None,
    period_start: Optional[date] = None,
    period_end: Optional[date] = None,
    worked_hours: Optional[float] = None,
    total_salary_calculated: Optional[float] = None,
    advances_deducted: Optional[float] = None,
) -> int:
    """Yangi moliya operatsiyasini yozadi."""
    async with pool.acquire() as conn:
        return await conn.fetchval("""
            INSERT INTO finance_transactions (
                worker_id, admin_tg_id, admin_name, transaction_type, amount,
                period_start, period_end, worked_hours,
                total_salary_calculated, advances_deducted, comment
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            RETURNING id;
        """, worker_id, admin_tg_id, admin_name, transaction_type, amount,
            period_start, period_end, worked_hours,
            total_salary_calculated, advances_deducted, comment)


async def get_worker_transactions_history(worker_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    """Xodimning oxirgi moliya operatsiyalarini oladi."""
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT * FROM finance_transactions
            WHERE worker_id = $1
            ORDER BY created_at DESC
            LIMIT $2
        """, worker_id, limit)
        return [dict(r) for r in rows]


async def get_transaction_by_id(tx_id: int) -> Optional[Dict[str, Any]]:
    """Tranzaksiyani ID bo'yicha olish."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT t.*, w.full_name as worker_name, r.name as role_name
            FROM finance_transactions t
            JOIN workers w ON w.id = t.worker_id
            LEFT JOIN roles r ON r.id = w.role_id
            WHERE t.id = $1
        """, tx_id)
        return dict(row) if row else None


async def delete_finance_transaction(tx_id: int) -> bool:
    """Tranzaksiyani bekor qilish / o'chirish."""
    async with pool.acquire() as conn:
        res = await conn.execute("DELETE FROM finance_transactions WHERE id = $1", tx_id)
        return "DELETE 1" in res


async def get_worker_unsettled_advances(worker_id: int, year: int, month: int) -> float:
    """Xodimning shu oygi avanslari yig'indisini oladi."""
    async with pool.acquire() as conn:
        val = await conn.fetchval("""
            SELECT COALESCE(SUM(amount), 0.00)
            FROM finance_transactions
            WHERE worker_id = $1
              AND transaction_type = 'advance'
              AND EXTRACT(YEAR FROM created_at AT TIME ZONE 'Asia/Tashkent') = $2
              AND EXTRACT(MONTH FROM created_at AT TIME ZONE 'Asia/Tashkent') = $3
        """, worker_id, year, month)
        return float(val or 0.0)


async def get_daily_transactions(target_date: date) -> List[Dict[str, Any]]:
    """Bugungi barcha to'lovlar (avans va raschyotlar) ro'yxati."""
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT t.*, w.full_name as worker_name, r.name as role_name
            FROM finance_transactions t
            JOIN workers w ON w.id = t.worker_id
            LEFT JOIN roles r ON r.id = w.role_id
            WHERE DATE(t.created_at AT TIME ZONE 'Asia/Tashkent') = $1
            ORDER BY t.created_at DESC
        """, target_date)
        return [dict(r) for r in rows]


async def get_monthly_finance_summary(year: int, month: int) -> Dict[str, Any]:
    """Oylik umumiy moliya statistikasi."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT
                COALESCE(SUM(amount) FILTER (WHERE transaction_type = 'advance'), 0.00) as total_advances,
                COALESCE(SUM(amount) FILTER (WHERE transaction_type = 'settlement'), 0.00) as total_settlements,
                COALESCE(SUM(amount), 0.00) as grand_total,
                COUNT(id) as transactions_count
            FROM finance_transactions
            WHERE EXTRACT(YEAR FROM created_at AT TIME ZONE 'Asia/Tashkent') = $1
              AND EXTRACT(MONTH FROM created_at AT TIME ZONE 'Asia/Tashkent') = $2
        """, year, month)
        return dict(row) if row else {
            "total_advances": 0.0,
            "total_settlements": 0.0,
            "grand_total": 0.0,
            "transactions_count": 0,
        }


# ==========================================
# ⚙️ ADMINLAR VA TIZIM SOZLAMALARI
# ==========================================

async def get_all_admins() -> List[Dict[str, Any]]:
    """Barcha adminlarni oladi."""
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM admins ORDER BY added_at ASC")
        return [dict(r) for r in rows]


async def get_all_admin_tg_ids() -> List[int]:
    """Barcha admin va superadminlarning Telegram ID'larini oladi."""
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT tg_id FROM admins")
        db_admins = [r["tg_id"] for r in rows]
        return list(set(db_admins + SUPERADMINS))


async def is_admin_or_superadmin(tg_id: int) -> bool:
    """Foydalanuvchi admin yoki superadmin ekanligini tekshiradi."""
    if tg_id in SUPERADMINS:
        return True
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT tg_id FROM admins WHERE tg_id = $1", tg_id)
        return row is not None


async def is_superadmin(tg_id: int) -> bool:
    """Foydalanuvchi Superadmin ekanligini tekshiradi."""
    if tg_id in SUPERADMINS:
        return True
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT role FROM admins WHERE tg_id = $1 AND role = 'superadmin'", tg_id)
        return row is not None


async def add_admin(tg_id: int, full_name: str, username: Optional[str] = None, role: str = "admin") -> bool:
    """Yangi admin qo'shadi."""
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO admins (tg_id, full_name, username, role)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (tg_id) DO UPDATE SET
                full_name = EXCLUDED.full_name,
                username = EXCLUDED.username,
                role = EXCLUDED.role;
        """, tg_id, full_name, username, role)
        return True


async def remove_admin(tg_id: int) -> bool:
    """Adminni o'chiradi (Superadminlarni o'chirib bo'lmaydi)."""
    if tg_id in SUPERADMINS:
        return False
    async with pool.acquire() as conn:
        res = await conn.execute("DELETE FROM admins WHERE tg_id = $1 AND role <> 'superadmin'", tg_id)
        return "DELETE 1" in res


async def get_settings() -> Dict[str, Any]:
    """Tizim sozlamalarini oladi."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM settings WHERE id = 1")
        if not row:
            return {
                "location_lat": DEFAULT_LAT,
                "location_lon": DEFAULT_LON,
                "location_radius": DEFAULT_RADIUS,
                "location_name": RESTAURANT_NAME,
                "work_log_group_id": 0,
                "admin_contact": None,
            }
        return dict(row)


async def update_location(lat: float, lon: float, radius: Optional[float] = None, name: Optional[str] = None) -> bool:
    """Korxona lokatsiyasini yangilaydi."""
    async with pool.acquire() as conn:
        if radius is not None:
            await conn.execute("""
                UPDATE settings
                SET location_lat = $1, location_lon = $2, location_radius = $3,
                    location_name = COALESCE($4, location_name)
                WHERE id = 1
            """, lat, lon, radius, name)
        else:
            await conn.execute("""
                UPDATE settings
                SET location_lat = $1, location_lon = $2,
                    location_name = COALESCE($3, location_name)
                WHERE id = 1
            """, lat, lon, name)
        return True


async def update_location_radius(radius: float) -> bool:
    """Faqat radiusni yangilaydi."""
    async with pool.acquire() as conn:
        res = await conn.execute("UPDATE settings SET location_radius = $1 WHERE id = 1", radius)
        return "UPDATE 1" in res


async def update_work_log_group(group_id: int) -> bool:
    """Log guruhini yangilaydi."""
    async with pool.acquire() as conn:
        res = await conn.execute("UPDATE settings SET work_log_group_id = $1 WHERE id = 1", group_id)
        return "UPDATE 1" in res


async def update_admin_contact(contact: Optional[str]) -> bool:
    """Admin bilan bog'lanish kontaktini yangilaydi."""
    async with pool.acquire() as conn:
        res = await conn.execute("UPDATE settings SET admin_contact = $1 WHERE id = 1", contact)
        return "UPDATE 1" in res
