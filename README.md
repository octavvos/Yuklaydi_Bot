# YouTube / Instagram yuklovchi bot (aiogram 3)

Foydalanuvchi YouTube yoki Instagram havolasini yuboradi → bot **🎬 Video / 🎵 Audio** tugmalarini chiqaradi → tanlangan formatda yuklab, Telegramga yuboradi.

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
- Telegram Bot API orqali fayl hajmi **50 MB** gacha. Video 720p gacha olinadi, kattaroq bo'lsa bot ogohlantiradi.
- Instagram ba'zan login talab qiladi — unda brauzerdan `cookies.txt` eksport qilib, `COOKIES_FILE` ga ko'rsating.
- yt-dlp ni vaqti-vaqti bilan yangilab turing: `./venv/bin/pip install -U yt-dlp`
