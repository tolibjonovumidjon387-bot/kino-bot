# 🎬 Telegram Kino Bot

Python + aiogram 3.x asosida qurilgan to'liq funksiyali Telegram kino boti.

---

## 📋 Xususiyatlar

| Funksiya | Tavsif |
|---|---|
| Kino kodi | Kod orqali kino olish (arxiv kanaldan copy_message) |
| Kategoriyalar | 4 ta kategoriya, sahifalash bilan |
| Majburiy obuna | Bir nechta kanal, haqiqiy Telegram a'zolik tekshiruvi |
| Admin panel | Kino CRUD, kanal boshqaruvi, xabar yuborish |
| Broadcast | Bitta foydalanuvchi yoki hammaga, fonga ishlaydi |
| Jadval | Kunlik rejalashtirilgan xabarlar, APScheduler |
| Bot holati | To'xtatish/yoqish (admin panel ochiq qoladi) |

---

## 🗂 Loyiha tuzilmasi

```
kino_bot/
├── main.py                  # Ishga tushirish
├── config.py                # Sozlamalar (.env o'qish)
├── requirements.txt
├── .env.example
├── .gitignore
├── database/
│   ├── __init__.py
│   ├── engine.py            # SQLAlchemy async engine
│   ├── models.py            # ORM modellari
│   └── crud.py              # CRUD operatsiyalar
├── handlers/
│   ├── __init__.py
│   ├── user.py              # Foydalanuvchi handlerlari
│   └── admin.py             # Admin panel handlerlari
├── keyboards/
│   ├── __init__.py
│   ├── user_kb.py           # Foydalanuvchi klaviaturalari
│   └── admin_kb.py          # Admin klaviaturalari
├── middlewares/
│   ├── __init__.py
│   ├── db.py                # DB sessiya middleware
│   └── user_register.py     # Foydalanuvchi ro'yxatga olish
└── utils/
    ├── __init__.py
    ├── helpers.py           # Yordamchi funksiyalar
    ├── subscription.py      # Obuna tekshirish
    └── scheduler.py         # APScheduler moduli
```

---

## ⚙️ O'rnatish

### 1. Talablar

- Python 3.11 yoki yuqori
- pip

### 2. Reponi klonlash

```bash
git clone <repo_url>
cd kino_bot
```

### 3. Virtual muhit

**Windows:**
```cmd
python -m venv .venv
.venv\Scripts\activate
```

**Linux/Ubuntu:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 4. Kutubxonalarni o'rnatish

```bash
pip install -r requirements.txt
```

### 5. .env faylini sozlash

```bash
copy .env.example .env     # Windows
cp .env.example .env       # Linux
```

`.env` faylini oching va to'ldiring:

```env
BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ
ADMIN_IDS=123456789,987654321
DATABASE_URL=sqlite+aiosqlite:///kino_bot.db
ADMIN_CONTACT=admin_username
TIMEZONE=Asia/Tashkent
```

**Arxiv kanallar** (ixtiyoriy — admin paneldan ham sozlash mumkin):
```env
ARCHIVE_ISLAMIC=-1001234567890
ARCHIVE_CARTOONS=-1009876543210
ARCHIVE_ROMANTIC=-1001122334455
ARCHIVE_FANTASY=-1005544332211
```

#### BOT_TOKEN olish:
1. Telegramda [@BotFather](https://t.me/BotFather) ga boring
2. `/newbot` yuboring, ko'rsatmalarga amal qiling
3. Token nusxalab `.env` ga joylashtiring

#### ADMIN_IDS aniqlash:
1. [@userinfobot](https://t.me/userinfobot) ga `/start` yuboring
2. Ko'rsatilgan `Id` raqamini `.env` ga qo'ying

#### Arxiv kanal ID aniqlash:
1. Kanalga botni **admin** sifatida qo'shing
2. [@username_to_id_bot](https://t.me/username_to_id_bot) yoki boshqa usulda kanal ID ni aniqlang
3. `-100` bilan boshlanadigan raqam (masalan: `-1001234567890`)

### 6. Ishga tushirish (Windows mahalliy)

```cmd
python main.py
```

---

## 🖥 Ubuntu serverga o'rnatish

### Serverga yuklash

```bash
scp -r kino_bot/ user@server_ip:/home/user/
```

### Serverda o'rnatish

```bash
cd /home/user/kino_bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env   # sozlamalarni to'ldiring
```

### systemd service — avtomatik ishga tushirish

`/etc/systemd/system/kino_bot.service` faylini yarating:

```ini
[Unit]
Description=Telegram Kino Bot
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/home/your_username/kino_bot
ExecStart=/home/your_username/kino_bot/.venv/bin/python main.py
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal
EnvironmentFile=/home/your_username/kino_bot/.env

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable kino_bot
sudo systemctl start kino_bot
sudo systemctl status kino_bot
```

### Loglarni ko'rish

```bash
sudo journalctl -u kino_bot -f        # real vaqt
sudo journalctl -u kino_bot -n 100    # oxirgi 100 satr
cat /home/user/kino_bot/bot.log       # fayl logi
```

### Botni qayta ishga tushirish

```bash
sudo systemctl restart kino_bot
```

---

## 🤖 Bot ishlatish

### Foydalanuvchi uchun

| Amal | Tavsif |
|---|---|
| `/start` | Botni boshlash |
| `🎬 Kategoriyalar` | Kinolar ro'yxati kategoriya bo'yicha |
| `🔍 Kino kodi` | Kino kodi so'rash eslatmasi |
| `kod yuboring` | Istalgan matn → kino kodi sifatida qabul qilinadi |
| `📩 Admin bilan bog'lanish` | Admin Telegram profiliga havola |

### Admin uchun

| Komanda | Tavsif |
|---|---|
| `/admin` | Admin panelni ochish |

**Admin panelda:**
- **🎬 Kinolar** — qo'shish (forward yoki ID orqali), tahrirlash, o'chirish, ro'yxat
- **📢 Majburiy kanallar** — qo'shish/olib tashlash
- **📨 Xabar yuborish** — bitta foydalanuvchi yoki hammaga
- **📅 Jadvallar** — kunlik rejalashtirilgan xabarlar
- **⚙️ Sozlamalar** — admin kontakt, arxiv kanal
- **⏸/▶️ Bot holati** — to'xtatish/yoqish

### Kino qo'shish (2 xil usul)

**1. Forward orqali (tavsiya etiladi):**
1. Admin paneldan `➕ Kino qo'shish` bosing
2. Arxiv kanaldan kino xabarini botga forward qiling
3. Kod, nom, kategoriyani kiriting

**2. ID orqali:**
1. `➕ Kino qo'shish` bosing
2. `kanal_id:xabar_id` formatida yuboring (masalan: `-1001234567890:123`)
3. Kod, nom, kategoriyani kiriting

---

## 🗄 Ma'lumotlar bazasi

SQLite (standart) yoki PostgreSQL ishlatish mumkin.

**SQLite** (oddiy, bitta fayl):
```env
DATABASE_URL=sqlite+aiosqlite:///kino_bot.db
```

**PostgreSQL** (server uchun tavsiya):
```bash
pip install asyncpg
```
```env
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/kino_bot
```

Jadvallar birinchi ishga tushirishda **avtomatik** yaratiladi.

---

## ✅ Tekshirilgan funksiyalar

> ⚠️ Quyidagi tekshiruvlar real Telegram token va kanal talab qiladi.
> Kod sintaktik jihatdan to'g'ri va mantiqiy tekshirishdan o'tkazilgan.

| Tekshiruv | Holat |
|---|---|
| Sintaksis xatosi yo'q (Python compile) | ✅ |
| Import zanjiri to'g'ri | ✅ |
| DB modellari va CRUD mos keladi | ✅ |
| FSM holatlari to'liq | ✅ |
| Admin tekshiruvi har joyda | ✅ |
| Kino kodi takrorlanmasligi | ✅ (DB UNIQUE) |
| Obuna tekshiruvi kino yuborishdan oldin | ✅ |
| Scheduler restart-dan keyin tiklanadi | ✅ (APScheduler + DB) |
| Broadcast fonga ishlaydi | ✅ (asyncio.create_task) |
| Bot to'xtatilganda scheduler yubormayd | ✅ |
| Real Telegram API bilan test | ⚙️ Token kerak |

---

## 🔁 Qayta ishga tushirish siyosati (Scheduler)

- Bot o'chib qolgan paytdagi **o'tkazib yuborilgan** kunlik yuborishlar **yuborilmaydi**
- Ular `skipped` deb belgilanadi va admin xabardor qilinadi
- Kelgusi yuborishlar odatdagidek davom etadi
- `exactly-once` kafolati: `ScheduledSendLog` jadvalidagi `UNIQUE(schedule_id, user_id, send_date)` constraint orqali

---

## ⚠️ Muhim eslatmalar

1. **Bot arxiv kanalda admin bo'lishi shart** — a'zolik tekshirish va xabarni copy qilish uchun
2. **Majburiy obuna kanallarda ham bot admin bo'lishi shart** — a'zolikni tekshirish uchun
3. `.env` faylini **hech qachon** git repoga pushlang (`.gitignore` da ko'rsatilgan)
4. `ADMIN_IDS` ga faqat ishonchli odamlarning Telegram ID larini yozing
