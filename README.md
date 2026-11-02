# YouTube / Instagram yuklovchi bot (aiogram 3)

- **YouTube** havolasi → bot sifat tugmalarini chiqaradi: **360p / 480p / 720p** yoki **🎵 Audio (MP3)** → tanlangan sifatda yuklab, Telegramga yuboradi.
- **Instagram** havolasi → video tanlovsiz, darhol yuklanadi.

## O'rnatish
```bash
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
cp .env.example .env      # ichiga BOT_TOKEN ni yozing (@BotFather dan)
./venv/bin/python bot.py
```

ffmpeg tizimda bo'lmasa ham ishlaydi: `imageio-ffmpeg` paketi ichidagi ffmpeg ishlatiladi.

## Sozlamalar (.env)
| O'zgaruvchi | Tavsif |
|---|---|
| `BOT_TOKEN` | Bot tokeni (majburiy) |
| `ADMIN_IDS` | Adminlar Telegram ID lari, vergul bilan: `111,222`. ID ni botga `/id` yozib bilasiz |
| `DB_PATH` | SQLite baza fayli (standart: `bot.db`) |
| `COOKIES_FILE` | Ixtiyoriy. `cookies.txt` yo'li — yopiq/login talab qiladigan Instagram postlari uchun |
| `PROXY` | Ixtiyoriy. Telegram bloklangan bo'lsa: `http://host:port` yoki `socks5://host:port` |
| `TELEGRAM_API_URL` | Ixtiyoriy. Lokal Bot API server manzili (masalan `http://127.0.0.1:8081`). Bo'lsa fayl chegarasi **2000 MB**, bo'lmasa 50 MB |

## Admin panel
`.env` dagi `ADMIN_IDS` ga ID ingizni yozib, botni qayta ishga tushiring. Admin buyruqlari faqat adminlarga ishlaydi va faqat ularning menyusida ko'rinadi:

| Buyruq | Vazifasi |
|---|---|
| `/admin` | Admin panel (tugmalar bilan) |
| `/users` | Foydalanuvchilar ro'yxati (sahifalab, oxirgi faollik bo'yicha) |
| `/user ID` yoki `/user @username` | Foydalanuvchi ma'lumotlari va oxirgi yuklashlari |
| `/u_123456` | Ro'yxatdagi foydalanuvchini bitta bosishda ochish |
| `/stats` | Statistika: foydalanuvchilar, faollar, yuklashlar |
| `/export` | Barcha foydalanuvchilar CSV faylda (Excel'da ochiladi) |

Yangi foydalanuvchi botga kirganda adminlarga avtomatik xabar keladi.

## Cheklovlar
- Telegram'ning umumiy Bot API serveri orqali fayl hajmi **50 MB** gacha. Undan kattasi uchun lokal Bot API server kerak (pastda), u bilan **2000 MB** gacha.
- YouTube uchun eng yuqori sifat 720p.

## 50 MB dan katta fayllar (lokal Bot API server)
1. [my.telegram.org](https://my.telegram.org) → **API development tools** → `api_id` va `api_hash` oling.
2. Serverda `deploy/install.sh` ni ishga tushiring va so'ralganda ularni kiriting. Skript Docker'da `aiogram/telegram-bot-api` ni ishga tushiradi, botni umumiy serverdan chiqaradi (`logOut`) va `.env` ga `TELEGRAM_API_URL` yozadi.

Qo'lda sozlash:
```bash
docker run -d --name telegram-bot-api --restart always -p 127.0.0.1:8081:8081 \
  -e TELEGRAM_API_ID=... -e TELEGRAM_API_HASH=... -e TELEGRAM_LOCAL=1 \
  -v telegram-bot-api-data:/var/lib/telegram-bot-api aiogram/telegram-bot-api:latest
curl https://api.telegram.org/bot<TOKEN>/logOut      # bir marta
echo "TELEGRAM_API_URL=http://127.0.0.1:8081" >> .env
```
- Instagram ba'zan login talab qiladi — unda brauzerdan `cookies.txt` eksport qilib, `COOKIES_FILE` ga ko'rsating.
- yt-dlp ni vaqti-vaqti bilan yangilab turing: `./venv/bin/pip install -U "yt-dlp[default]"`
- YouTube uchun serverda [deno](https://deno.com) bo'lgani yaxshi (yt-dlp talab qiladi); `install.sh` uni o'rnatadi.

## Serverga joylash (Ubuntu/Debian)
Python 3.10 yoki undan yangi versiya kerak.

```bash
sudo apt update && sudo apt install -y git python3-venv ffmpeg
git clone https://github.com/octavvos/Yuklaydi_Bot.git
cd Yuklaydi_Bot
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
cp .env.example .env && nano .env        # BOT_TOKEN va ADMIN_IDS ni yozing
./venv/bin/python bot.py                 # sinab ko'ring, keyin Ctrl+C
```

Doimiy ishlashi uchun (server qayta yonganda ham o'zi ishga tushadi):
```bash
sed -i "s/USER/$USER/g" deploy/yuklaydi-bot.service
sudo cp deploy/yuklaydi-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now yuklaydi-bot
sudo journalctl -u yuklaydi-bot -f       # loglarni ko'rish
```

Yangilash:
```bash
git pull && ./venv/bin/pip install -r requirements.txt && sudo systemctl restart yuklaydi-bot
```

Yoki hammasini bitta skript bilan (root sifatida, serverda):
```bash
curl -fsSLO https://raw.githubusercontent.com/octavvos/Yuklaydi_Bot/main/deploy/install.sh && bash install.sh
```

> Bitta token bilan faqat bitta bot ishlay oladi: serverda ishga tushirgandan keyin kompyuteringizdagi botni o'chiring.
