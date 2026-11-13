# 🚀 Smena — Telegram Botini Serverga O'rnatish va 24/7 Ishga Tushirish Qo'llanmasi

Ushbu qo'llanma loyihani Linux VPS (Ubuntu 22.04 yoki 24.04 LTS) serverida 24/7 rejimda, uzluksiz va avtomatik qayta tiklanadigan qilib ishga tushirish uchun mo'ljallangan.

---

## 📌 Minimal Server Talablari
- **Operatsion tizim:** Ubuntu 22.04 LTS / Ubuntu 24.04 LTS / Debian 12
- **Protsessor (CPU):** 1-2 vCPU
- **Operativ xotira (RAM):** Kamida 1 GB (2 GB tavsiya etiladi)
- **Disk:** 15-20 GB SSD
- **Internet:** Doimiy ochiq chiquvchi tarmoq (Telegram API uchun)

---

## 📁 1-QADAM: Loyihani Serverga Yuklash

Serverga SSH orqali kiring va loyihani `/var/www/smena-bot` papkasiga joylashtiring:

```bash
# Loyiha fayllarini yuklash (Git orqali; yoki fayllarni SCP/SFTP bilan shu papkaga ko'chiring)
git clone https://github.com/xoliddev/smena-staff-bot.git /var/www/smena-bot
cd /var/www/smena-bot

# Loglar uchun papka
mkdir -p /var/www/smena-bot/logs
```

Fayllar orasida `.env` faylini shakllantiring:
```bash
nano .env
```

`.env` fayli ichiga quyidagi ma'lumotlarni to'ldiring:
```env
BOT_TOKEN=123456789:replace-me
POSTGRES_USER=postgres
POSTGRES_PASSWORD=change-me
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=smena_db

SUPERADMINS=111111111
RESTAURANT_NAME="Mening Restoranim"
WORK_LOG_GROUP_ID=0

DEFAULT_LAT=41.311081
DEFAULT_LON=69.240562
DEFAULT_RADIUS=150
```

---

## 🐳 2-QADAM: Ishga Tushirish (2 xil usul)

Siz o'zingizga qulay 2 ta usuldan birini tanlashingiz mumkin:

### 1-USUL (Tavsiya etiladi): Docker & Docker-Compose Orqali

Bu usul eng oson va ishonchli bo'lib, PostgreSQL va Python muhitini avtomatik sozlaydi.

1. **Docker va Docker Compose o'rnatish:**
   ```bash
   curl -fsSL https://get.docker.com -o get-docker.sh
   sh get-docker.sh
   apt-get install -y docker-compose-plugin
   ```

2. **Konteynerlarni fonda (daemon) ishga tushirish:**
   ```bash
   docker compose up -d --build
   ```

3. **Holatni tekshirish:**
   ```bash
   docker compose ps
   docker compose logs -f bot
   ```
*Server o'chib-yonsa ham, `restart: always` parametri tufayli bot va baza avtomatik ishga tushadi.*

---

### 2-USUL: Systemd Xizmati Orqali (To'g'ridan-to'g'ri Python & PostgreSQL)

Agar serverda allaqachon PostgreSQL o'rnatilgan bo'lsa:

1. **Kerakli dasturlarni o'rnatish:**
   ```bash
   apt update
   apt install -y python3 python3-pip python3-venv postgresql postgresql-contrib
   ```

2. **PostgreSQL ma'lumotlar bazasini tayyorlash:**
   ```bash
   sudo -u postgres psql
   ```
   PostgreSQL konsolida:
   ```sql
   CREATE DATABASE smena_db;
   ALTER USER postgres WITH PASSWORD 'change-me';
   \q
   ```

3. **Python Virtual Muhitini sozlash:**
   ```bash
   cd /var/www/smena-bot
   python3 -m venv venv
   source venv/bin/activate
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. **Systemd Unit faylini o'rnatish:**
   ```bash
   cp /var/www/smena-bot/smena-bot.service /etc/systemd/system/smena-bot.service
   systemctl daemon-reload
   systemctl enable smena-bot
   systemctl start smena-bot
   ```

5. **Xizmat holatini tekshirish:**
   ```bash
   systemctl status smena-bot
   ```

---

## 📋 3-QADAM: Loglarni Jonli Kuzatish

Bot qanday ishlayotganini kuzatish uchun:

- **Docker orqali:**
  ```bash
  docker compose logs -f bot
  ```

- **Systemd orqali:**
  ```bash
  journalctl -u smena-bot -f
  # Yoki log faylidan:
  tail -f /var/www/smena-bot/logs/bot.log
  ```

---

## 💾 4-QADAM: Bazani Har Kuni Avtomatik Zaxiralash (Backup Cron)

Ma'lumotlar yo'qolmasligi uchun har kecha soat 03:00 da bazani zaxiraga olib turish:

```bash
crontab -e
```
Fayl oxiriga qo'shing:
```bash
0 3 * * * pg_dump -U postgres -d smena_db > /var/backups/smena_db_$(date +\%F).sql
```

---

## ✅ Ishga Tushirgandan Keyin Tekshiruv (Checklist)

- [ ] Bot `@BotFather` dan olingan token bilan ulandi.
- [ ] Superadmin ID'lari `.env` dagi `SUPERADMINS` da to'g'ri ko'rsatildi.
- [ ] `RESTAURANT_NAME` ga restoran nomi yozildi (bot xabarlari va Excel hisobotlarida shu nom chiqadi).
- [ ] Ishchilar bot orqali ishga kirish arizasini muvaffaqiyatli jo'nata olmoqda.
- [ ] Ish joyi GPS koordinatasi va radiusi bot sozlamalarida to'g'ri belgilandi.
- [ ] Avans va hisob-kitoblar to'g'ri hisoblanib, barcha adminlarga bildirishnoma bormoqda.
- [ ] Oylik Excel hisobot yaratilmoqda va har oyning 1-kunida avtomatik jo'natiladi.
- [ ] Server o'chib-yonganda bot avtomatik ko'tariladi (`systemctl is-enabled smena-bot` yoki Docker `restart: always`).
