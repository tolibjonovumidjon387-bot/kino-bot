import os
from dotenv import load_dotenv

load_dotenv()

# Bot sozlamalari
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN .env faylida ko'rsatilmagan!")

# Admin ID lari
_admin_ids_raw = os.getenv("ADMIN_IDS", "")
ADMIN_IDS: list[int] = [
    int(aid.strip()) for aid in _admin_ids_raw.split(",") if aid.strip().isdigit()
]
if not ADMIN_IDS:
    raise ValueError("ADMIN_IDS .env faylida ko'rsatilmagan!")

# Ma'lumotlar bazasi
DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///kino_bot.db")

# Admin kontakt
ADMIN_CONTACT: str = os.getenv("ADMIN_CONTACT", "admin")

# Vaqt mintaqasi
TIMEZONE: str = os.getenv("TIMEZONE", "Asia/Tashkent")

# Kategoriyalar
CATEGORIES = [
    "Islomiy filmlar",
    "Multfilmlar",
    "Romantik filmlar",
    "Fantastik filmlar",
]

# Arxiv kanallari (har bir kategoriya uchun alohida)
ARCHIVE_CHANNELS = {
    "Islomiy filmlar": os.getenv("ARCHIVE_ISLAMIC", ""),
    "Multfilmlar": os.getenv("ARCHIVE_CARTOONS", ""),
    "Romantik filmlar": os.getenv("ARCHIVE_ROMANTIC", ""),
    "Fantastik filmlar": os.getenv("ARCHIVE_FANTASY", ""),
}

# Sahifalash
PAGE_SIZE = 10

# Broadcast
BROADCAST_DELAY = 0.05  # har xabar orasidagi kutish (soniya)
