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
| `COOKIES_FILE` | Ixtiyoriy. `cookies.txt` yo'li — yopiq/login talab qiladigan Instagram postlari uchun |
| `PROXY` | Ixtiyoriy. Telegram bloklangan bo'lsa: `http://host:port` yoki `socks5://host:port` |

## Cheklovlar
- Telegram Bot API orqali fayl hajmi **50 MB** gacha. Video 720p gacha olinadi, kattaroq bo'lsa bot ogohlantiradi.
- Instagram ba'zan login talab qiladi — unda brauzerdan `cookies.txt` eksport qilib, `COOKIES_FILE` ga ko'rsating.
- yt-dlp ni vaqti-vaqti bilan yangilab turing: `./venv/bin/pip install -U yt-dlp`
